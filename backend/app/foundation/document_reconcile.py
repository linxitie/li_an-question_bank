"""F4 文档对账：以 SoT 重算文档，和 DocumentStore 中的副本比较。

只报告不自动修复。missing=文档缺失，orphan=文档库多出，mismatched=内容
哈希不一致。version 是投影写入序号，合法地随事件变化，比较时剔除。
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.foundation.config import BACKEND_DIR
from app.foundation.document_schema import (
    build_exam_resource,
    build_forum_content,
    build_import_snapshot,
)
from app.foundation.stores.document import (
    COLLECTIONS,
    DocumentStore,
    build_document_store,
    canonical_json,
)

SCOPE = "document"


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def import_key(source_table: str, import_id: int | str) -> str:
    return f"{source_table}:{import_id}"


def iter_sources(
    session: Session, collection: str, limit: int | None = None
) -> Iterator[tuple[str, Any]]:
    """按 id 升序产出 (key, builder)；builder() 返回 None 表示当前不该投影。"""
    if collection == "exam_resources":
        from app.models.models import ExamPaper

        query = session.query(ExamPaper.paper_id).order_by(ExamPaper.paper_id)
        if limit:
            query = query.limit(int(limit))
        for (paper_id,) in query:
            yield str(paper_id), (lambda pid=paper_id: build_exam_resource(session, pid))
        return

    if collection == "import_snapshots":
        from app.models.models import MaterialImportRecord, QuestionImportRecord

        rows: list[tuple[str, int, str]] = []
        for (import_id,) in session.query(QuestionImportRecord.import_id).order_by(
            QuestionImportRecord.import_id
        ):
            rows.append(("question_import_record", import_id, "q"))
        for (import_id,) in session.query(MaterialImportRecord.import_id).order_by(
            MaterialImportRecord.import_id
        ):
            rows.append(("material_import_record", import_id, "m"))
        # 两张来源表都有自增 id，按来源+id 排序保证回填断点稳定。
        rows.sort(key=lambda item: (item[2], item[1]))
        if limit:
            rows = rows[: int(limit)]
        for source_table, import_id, _ in rows:
            yield import_key(source_table, import_id), (
                lambda table=source_table, iid=import_id: build_import_snapshot(
                    session, table, iid
                )
            )
        return

    if collection == "forum_contents":
        from app.models.models import ForumPost

        query = session.query(ForumPost.post_id).order_by(ForumPost.post_id)
        if limit:
            query = query.limit(int(limit))
        for (post_id,) in query:
            yield str(post_id), (lambda pid=post_id: build_forum_content(session, pid))
        return

    raise ValueError(f"未知文档集合: {collection}")


def _comparable(doc: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(doc)
    normalized.pop("version", None)
    return normalized


def document_hash(doc: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(_comparable(doc)).encode("utf-8")).hexdigest()


def _document_bytes(doc: dict[str, Any]) -> int:
    return len(canonical_json(doc).encode("utf-8"))


@dataclass
class DocumentReconcileResult:
    run_id: str
    mode: str = "full"
    checked: int = 0
    drifted: int = 0
    missing: int = 0
    orphan: int = 0
    mismatched: int = 0
    skipped: int = 0
    started_at: str = field(default_factory=_now)
    finished_at: str = field(default_factory=_now)
    status: str = "ok"
    report_path: str | None = None
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
        return {
            **self.as_row(),
            "missing": self.missing,
            "orphan": self.orphan,
            "mismatched": self.mismatched,
            "skipped": self.skipped,
            "details": self.details,
        }


def inspect(
    session: Session,
    store: DocumentStore | None = None,
    *,
    collection: str | None = None,
    limit: int | None = None,
    mode: str = "full",
) -> DocumentReconcileResult:
    if store is None:
        store = build_document_store()
    targets = [collection] if collection else list(COLLECTIONS)
    for name in targets:
        if name not in COLLECTIONS:
            raise ValueError(f"未知文档集合: {name}")

    run = DocumentReconcileResult(run_id=uuid.uuid4().hex[:16], mode=mode, checked=0)
    for name in targets:
        expected_keys: set[str] = set()
        for key, builder in iter_sources(session, name, limit):
            expected_keys.add(key)
            doc = builder()
            if doc is None:
                run.skipped += 1
                continue
            run.checked += 1
            stored = store.get(name, key)
            if stored is None:
                run.missing += 1
                run.drifted += 1
                run.details.append({"collection": name, "key": key, "issue": "missing"})
                continue
            if document_hash(stored) != document_hash(doc):
                run.mismatched += 1
                run.drifted += 1
                run.details.append(
                    {"collection": name, "key": key, "issue": "mismatched"}
                )
        # 孤儿只统计本次完整扫描的集合；limit 抽样时差集不可信。
        if limit is None:
            try:
                for key in store.iter_keys(name):
                    if key not in expected_keys:
                        run.orphan += 1
                        run.drifted += 1
                        run.details.append(
                            {"collection": name, "key": key, "issue": "orphan"}
                        )
            except Exception as exc:  # noqa: BLE001 — 枚举失败只降级
                run.status = "warn"
                run.details.append(
                    {"collection": name, "issue": "orphan_scan_failed",
                     "error": f"{type(exc).__name__}: {exc}"}
                )
    run.finished_at = _now()
    if run.drifted:
        run.status = "drift"
    run.report_path = _write_report(run)
    return run


def record(session: Session, run: DocumentReconcileResult) -> None:
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
                   WHERE scope='document' ORDER BY finished_at DESC LIMIT 1"""
            )
        ).first()
    except Exception:
        return None
    return None if row is None else dict(row._mapping)


def freshness_days(
    latest: dict[str, Any] | None, now: datetime | None = None
) -> float | None:
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


def _write_report(run: DocumentReconcileResult) -> str | None:
    try:
        out_dir = BACKEND_DIR / "data" / "reports" / "reconcile"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"document_{run.run_id}.json"
        path.write_text(
            json.dumps(run.as_json(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return str(Path(path).relative_to(BACKEND_DIR))
    except OSError:
        return None
