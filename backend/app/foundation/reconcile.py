"""对账：以发件箱为源，核对本地投影的版本与校验和；可修复。

用法：
  python -m app.foundation.reconcile sample  [--limit 100]
  python -m app.foundation.reconcile rebuild
  python -m app.foundation.reconcile sample --db <path>   # 默认 SQLITE_PATH
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.foundation.projection import LocalProjection, payload_checksum


@dataclass
class ReconcileRun:
    run_id: str
    scope: str
    mode: str
    checked: int = 0
    drifted: int = 0
    repaired: int = 0
    status: str = "running"
    report_path: str | None = None

    def as_row(self) -> dict:
        now = _now()
        return {
            "run_id": self.run_id, "scope": self.scope, "mode": self.mode,
            "started_at": now, "finished_at": now, "checked": self.checked,
            "drifted": self.drifted, "repaired": self.repaired,
            "report_path": self.report_path, "status": self.status,
        }


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _latest_events(session: Session, limit: int | None = None) -> list:
    """每个聚合取最新一条 dispatched 事件（对账只比最终态）。"""
    sql = """SELECT id, event_name, aggregate_type, aggregate_id, aggregate_ver, payload
             FROM foundation_outbox WHERE status='dispatched' ORDER BY id DESC"""
    rows = session.execute(text(sql)).all()
    seen: set[tuple[str, str]] = set()
    picked = []
    for row in rows:
        key = (row.aggregate_type, row.aggregate_id)
        if key in seen:
            continue
        seen.add(key)
        picked.append(row)
        if limit and len(picked) >= limit:
            break
    return picked


def sample(session: Session, limit: int = 100, projection: LocalProjection | None = None) -> ReconcileRun:
    proj = projection or LocalProjection()
    run = ReconcileRun(uuid.uuid4().hex[:16], scope="sample", mode="sample")
    details = []
    for row in _latest_events(session, limit):
        run.checked += 1
        state = proj.state(session, row.aggregate_type, row.aggregate_id)
        try:
            payload = json.loads(row.payload) if isinstance(row.payload, str) else row.payload
        except json.JSONDecodeError:
            payload = {}
        expected = payload_checksum(payload)
        if state is None or state.source_version != row.aggregate_ver or state.checksum != expected:
            run.drifted += 1
            details.append(
                {
                    "aggregate": f"{row.aggregate_type}:{row.aggregate_id}",
                    "outbox_id": row.id,
                    "expected_version": row.aggregate_ver,
                    "actual_version": None if state is None else state.source_version,
                }
            )
    run.status = "ok" if run.drifted == 0 else "drift"
    run.report_path = _write_report(run, details)
    return run


def rebuild(session: Session, projection: LocalProjection | None = None) -> ReconcileRun:
    proj = projection or LocalProjection()
    run = ReconcileRun(uuid.uuid4().hex[:16], scope="all", mode="rebuild")
    for row in _latest_events(session):
        run.checked += 1
        state = proj.state(session, row.aggregate_type, row.aggregate_id)
        try:
            payload = json.loads(row.payload) if isinstance(row.payload, str) else row.payload
        except json.JSONDecodeError:
            payload = {}
        expected = payload_checksum(payload)
        if state is not None and state.source_version == row.aggregate_ver and state.checksum == expected:
            continue
        session.execute(
            text(
                """INSERT INTO foundation_projection_state
                       (projection, aggregate_type, aggregate_id, source_version, checksum, updated_at)
                   VALUES (:p, :t, :i, :v, :c, :now)
                   ON CONFLICT(projection, aggregate_type, aggregate_id) DO UPDATE SET
                       source_version=excluded.source_version,
                       checksum=excluded.checksum,
                       updated_at=excluded.updated_at"""
            ),
            {
                "p": proj.name, "t": row.aggregate_type, "i": row.aggregate_id,
                "v": row.aggregate_ver, "c": expected, "now": _now(),
            },
        )
        run.repaired += 1
    session.commit()
    run.status = "ok" if run.repaired == 0 else "ok"
    run.report_path = _write_report(run, [])
    return run


def record(session: Session, run: ReconcileRun) -> None:
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


def _write_report(run: ReconcileRun, details: list[dict]) -> str | None:
    try:
        from app.foundation.config import BACKEND_DIR

        out_dir = BACKEND_DIR / "data" / "reports" / "reconcile"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{run.run_id}.json"
        path.write_text(
            json.dumps({"run": run.as_row(), "details": details}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return str(path.relative_to(BACKEND_DIR))
    except OSError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="foundation 对账")
    parser.add_argument("action", choices=["sample", "rebuild"])
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--db", default=None)
    args = parser.parse_args(argv)

    from app.foundation.config import sqlite_path

    db = Path(args.db).resolve() if args.db else sqlite_path()
    engine = create_engine(f"sqlite:///{db}")
    with Session(engine) as session:
        run = sample(session, args.limit) if args.action == "sample" else rebuild(session)
        record(session, run)
    print(json.dumps({**run.as_row(), "report": run.report_path}, ensure_ascii=False))
    if run.status == "drift":
        print(f"DRIFT {run.drifted}/{run.checked} —— 运行 rebuild 修复")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
