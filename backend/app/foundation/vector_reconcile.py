"""向量投影对账（F6）。

期望值来自 question_bank（status=1 且题干非空）；实际值来自 VectorStore。
只读，不修复。full 比全部 id + contentHash，sample 只比抽样条目的元数据。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.foundation import config as cfg
from app.foundation.stores.vector import (
    VectorStore,
    VectorStoreError,
    build_vector_store,
)
from app.foundation.vector_builder import expected_records

SCOPE = "vector"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VectorReconcileResult:
    run_id: str
    mode: str = "full"
    checked: int = 0
    drifted: int = 0
    missing: int = 0
    orphan: int = 0
    mismatched: int = 0
    sampled: int = 0
    sample_mismatch: int = 0
    started_at: str = field(default_factory=_now)
    finished_at: str = ""
    status: str = "ok"
    report_path: str = ""
    details: list[dict[str, Any]] = field(default_factory=list)

    def as_row(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scope": SCOPE,
            "mode": self.mode,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "checked": self.checked,
            "drifted": self.drifted,
            "repaired": 0,
            "report_path": self.report_path,
            "status": self.status,
        }

    def as_json(self) -> dict[str, Any]:
        payload = self.as_row()
        payload.update({
            "missing": self.missing,
            "orphan": self.orphan,
            "mismatched": self.mismatched,
            "sampled": self.sampled,
            "sample_mismatch": self.sample_mismatch,
            "details": self.details,
        })
        return payload


def _write_report(run: VectorReconcileResult) -> str:
    path = cfg.BACKEND_DIR / "data" / "reports" / "reconcile" / f"vector_{run.run_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(run.as_json(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return str(path)


def _sample_ids(ids: list[str], sample: int) -> list[str]:
    if sample <= 0 or len(ids) <= sample:
        return ids
    step = len(ids) / sample
    return [ids[min(len(ids) - 1, int(index * step))] for index in range(sample)]


def inspect(
    session: Session,
    store: VectorStore | None = None,
    *,
    mode: str = "full",
    sample: int = 100,
    limit: int | None = None,
    collection: str | None = None,
) -> VectorReconcileResult:
    if mode not in ("full", "sample"):
        raise ValueError(f"mode 只支持 full/sample: {mode!r}")
    if store is None:
        store = build_vector_store()
    name = collection or cfg.VECTOR_COLLECTION
    records = expected_records(session, limit=limit)
    expected = {record.id: record.meta for record in records}
    run = VectorReconcileResult(run_id=uuid.uuid4().hex[:16], mode=mode)
    run.checked = len(expected)
    actual_ids: list[str] = []
    try:
        actual_ids = store.list_ids(name)
        actual_set = set(actual_ids)
        expected_set = set(expected)
        run.missing = len(expected_set - actual_set)
        run.orphan = len(actual_set - expected_set)
        run.drifted += run.missing + run.orphan
        for item_id in sorted(expected_set - actual_set)[:100]:
            _detail(run, "missing_vector", item_id)
        for item_id in sorted(actual_set - expected_set)[:100]:
            _detail(run, "orphan_vector", item_id)

        targets = actual_ids if mode == "full" else _sample_ids(actual_ids, sample)
        targets = [item_id for item_id in targets if item_id in expected]
        if mode != "full":
            run.sampled = len(targets)
        fetched: dict[str, dict[str, Any]] = {}
        for start in range(0, len(targets), 500):
            fetched.update(store.fetch(name, targets[start:start + 500]))
        for item_id in targets:
            actual_meta = fetched.get(item_id)
            if actual_meta is None:
                run.missing += 1
                run.drifted += 1
                _detail(run, "missing_meta", item_id)
                continue
            if actual_meta.get("contentHash") != expected[item_id].get("contentHash"):
                if mode == "full":
                    run.mismatched += 1
                    run.drifted += 1
                else:
                    run.sample_mismatch += 1
                    run.drifted += 1
                _detail(run, "content_hash_mismatch", item_id)
        if mode != "full":
            run.sampled = len(targets)
    except VectorStoreError as exc:
        run.status = "warn"
        run.details.append({
            "issue": "vector_store_unavailable",
            "error": f"{type(exc).__name__}: {exc}",
        })
    except Exception as exc:  # noqa: BLE001 — 对账不能因单点异常崩溃
        run.status = "warn"
        run.details.append({
            "issue": "reconcile_error",
            "error": f"{type(exc).__name__}: {exc}",
        })

    run.finished_at = _now()
    if run.drifted:
        run.status = "drift"
    run.details.insert(0, {
        "expected": len(expected),
        "actual": len(actual_ids),
        "collection": name,
        "backend": getattr(store, "backend", "unknown"),
    })
    run.report_path = _write_report(run)
    return run


def _detail(run: VectorReconcileResult, issue: str, key: Any) -> None:
    if len(run.details) >= 200:
        return
    run.details.append({"issue": issue, "key": str(key)})


def record(session: Session, run: VectorReconcileResult) -> None:
    from sqlalchemy import text

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
    from sqlalchemy import text

    try:
        row = session.execute(
            text(
                """SELECT run_id, started_at, finished_at, checked, drifted,
                          status, report_path
                   FROM foundation_reconcile_run
                   WHERE scope='vector' ORDER BY finished_at DESC LIMIT 1"""
            )
        ).first()
    except Exception:
        return None
    return None if row is None else dict(row._mapping)


def freshness_days(latest: dict[str, Any] | None, now: datetime | None = None) -> float | None:
    if not latest:
        return None
    raw = latest.get("finished_at")
    if not raw:
        return None
    try:
        finished = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    if finished.tzinfo is None:
        finished = finished.astimezone()
    moment = now or datetime.now(timezone.utc)
    return max(0.0, (moment - finished).total_seconds() / 86400)
