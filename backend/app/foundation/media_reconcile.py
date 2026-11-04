"""媒体对账：以 media_assets 为源，核对对象存储中的字节；只报告不自动修复。

方向：DB active 行 -> store.stat（缺字节、大小不符）；可选 store.list_keys ->
DB active object_key 差集（孤儿）。孤儿删除由 gc_media_orphans.py 单独执行，
默认为 dry-run 且带宽限期，避免误删刚写完、事务尚未提交的字节。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.foundation.config import BACKEND_DIR
from app.foundation.stores.object import ObjectStore, ObjectStoreUnavailable


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class MediaReconcileResult:
    run_id: str
    scope: str = "media"
    mode: str = "sample"
    checked: int = 0
    drifted: int = 0
    missing_blob: int = 0
    size_mismatch: int = 0
    orphans: int = 0
    orphan_bytes: int = 0
    started_at: str = field(default_factory=_now)
    finished_at: str = field(default_factory=_now)
    status: str = "ok"
    report_path: str | None = None
    details: list[dict[str, Any]] = field(default_factory=list)
    orphan_scan: bool = False
    orphan_error: str | None = None

    def as_row(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scope": self.scope,
            "mode": self.mode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "checked": self.checked,
            "drifted": self.drifted,
            "repaired": 0,
            "report_path": self.report_path,
            "status": self.status,
        }


def active_assets(session: Session, limit: int | None = None) -> list[Any]:
    sql = """SELECT asset_id, sha256, object_key, size_bytes, content_type, kind
             FROM media_assets WHERE status='active' ORDER BY created_at, asset_id"""
    if limit:
        sql += f" LIMIT {int(limit)}"
    return session.execute(text(sql)).all()


def orphan_keys(session: Session, store: ObjectStore, limit: int | None = None) -> list[tuple[str, int]]:
    """返回 (object_key, size) 的孤儿列表；store 不可枚举时抛 ObjectStoreUnavailable。"""
    refs = {
        row.object_key
        for row in session.execute(
            text("SELECT object_key FROM media_assets WHERE status='active'")
        )
    }
    found: list[tuple[str, int]] = []
    for key in store.list_keys(""):
        if key in refs:
            continue
        stat = store.stat(key)
        if stat is None:
            continue
        found.append((key, stat.size))
        if limit and len(found) >= limit:
            break
    return found


def inventory(
    session: Session,
    store: ObjectStore | None = None,
    *,
    limit: int | None = None,
    include_orphans: bool = False,
    mode: str = "sample",
) -> MediaReconcileResult:
    """核对 DB -> 字节；默认 sample（limit），full 传 limit=None。"""
    if store is None:
        from app.foundation.stores.object import build_object_store

        store = build_object_store()
    rows = active_assets(session, limit)
    run = MediaReconcileResult(
        run_id=uuid.uuid4().hex[:16], mode=mode, checked=len(rows)
    )
    for row in rows:
        stat = store.stat(row.object_key)
        if stat is None:
            run.missing_blob += 1
            run.drifted += 1
            run.details.append({"asset_id": row.asset_id, "issue": "missing_blob",
                                "object_key": row.object_key})
        elif stat.size != row.size_bytes:
            run.size_mismatch += 1
            run.drifted += 1
            run.details.append({
                "asset_id": row.asset_id, "issue": "size_mismatch",
                "object_key": row.object_key, "expected": row.size_bytes,
                "actual": stat.size,
            })
    if include_orphans:
        run.orphan_scan = True
        try:
            orphans = orphan_keys(session, store)
            run.orphans = len(orphans)
            run.orphan_bytes = sum(size for _, size in orphans)
            for key, size in orphans:
                run.details.append({"issue": "orphan", "object_key": key, "size": size})
        except ObjectStoreUnavailable as exc:
            # 孤儿方向不可用只降级，不影响 DB->字节方向结论。
            run.orphan_error = str(exc)
    run.finished_at = _now()
    if run.drifted:
        run.status = "drift"
    elif run.orphan_error:
        run.status = "warn"
    else:
        run.status = "ok"
    run.report_path = _write_report(run)
    return run


def record(session: Session, run: MediaReconcileResult) -> None:
    session.execute(
        text(
            """INSERT INTO foundation_reconcile_run
                   (run_id, scope, mode, started_at, finished_at, checked, drifted,
                    repaired, report_path, status)
               VALUES (:run_id, :scope, :mode, :started_at, :finished_at, :checked,
                       :drifted, :repaired, :report_path, :status)"""
        ),
        run.as_row(),
    )
    session.commit()


def latest_run(session: Session) -> dict[str, Any] | None:
    try:
        row = session.execute(
            text(
                """SELECT run_id, started_at, finished_at, checked, drifted,
                          status, report_path
                   FROM foundation_reconcile_run
                   WHERE scope='media' ORDER BY finished_at DESC LIMIT 1"""
            )
        ).first()
    except Exception:
        return None
    return None if row is None else dict(row._mapping)


def freshness_days(latest: dict[str, Any] | None, now: datetime | None = None) -> float | None:
    if not latest or not latest.get("finished_at"):
        return None
    try:
        finished = datetime.fromisoformat(str(latest["finished_at"]))
    except ValueError:
        return None
    ref = now or datetime.now().astimezone()
    if finished.tzinfo is None:
        finished = finished.astimezone()
    return max(0.0, (ref - finished).total_seconds() / 86400.0)


def _write_report(run: MediaReconcileResult) -> str | None:
    try:
        out_dir = BACKEND_DIR / "data" / "reports" / "reconcile"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"media_{run.run_id}.json"
        payload = {**run.as_row(), "missing_blob": run.missing_blob,
                   "size_mismatch": run.size_mismatch, "orphans": run.orphans,
                   "orphan_bytes": run.orphan_bytes,
                   "orphan_error": run.orphan_error, "details": run.details}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path.relative_to(BACKEND_DIR))
    except OSError:
        return None
