"""foundation 健康快照：供 GET /health/foundation 使用（只读，不写库）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from app.foundation.config import FOUNDATION_DISPATCH_MS, FOUNDATION_ENABLED
from app.foundation.projection import PROJECTION_NAME
from app.foundation.schema import FOUNDATION_TABLES

LAG_WARN_SECONDS = 300


def snapshot(engine) -> dict:
    if not FOUNDATION_ENABLED:
        return {"status": "disabled", "enabled": False, "projection": PROJECTION_NAME}

    with engine.connect() as conn:
        tables = {
            row[0]
            for row in conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        missing = [t for t in FOUNDATION_TABLES if t not in tables]
        if missing:
            return {
                "status": "degraded", "enabled": True, "schema": "missing",
                "missing_tables": missing, "projection": PROJECTION_NAME,
            }

        pending = conn.execute(
            text("SELECT COUNT(*) FROM foundation_outbox WHERE status='pending'")
        ).scalar_one()
        dead = conn.execute(
            text("SELECT COUNT(*) FROM foundation_outbox WHERE status='dead'")
        ).scalar_one()
        oldest = conn.execute(
            text("SELECT MIN(occurred_at) FROM foundation_outbox WHERE status='pending'")
        ).scalar_one()
        cursor = conn.execute(
            text("SELECT last_outbox_id, updated_at FROM foundation_projection_cursor WHERE projection=:p"),
            {"p": PROJECTION_NAME},
        ).first()
        last_run = conn.execute(
            text("""SELECT status, finished_at FROM foundation_reconcile_run
                    ORDER BY started_at DESC LIMIT 1""")
        ).first()

    lag = _lag_seconds(oldest)
    healthy = dead == 0 and lag <= LAG_WARN_SECONDS
    return {
        "status": "ok" if healthy else "degraded",
        "enabled": True,
        "schema": "ok",
        "projection": PROJECTION_NAME,
        "pending": int(pending),
        "dead": int(dead),
        "lag_seconds": lag,
        "cursor": None if cursor is None else {
            "last_outbox_id": int(cursor[0]), "updated_at": cursor[1],
        },
        "last_reconcile": None if last_run is None else {
            "status": last_run[0], "finished_at": last_run[1],
        },
        "dispatch_interval_ms": FOUNDATION_DISPATCH_MS,
    }


def _lag_seconds(oldest: str | None) -> int:
    if not oldest:
        return 0
    try:
        started = datetime.fromisoformat(oldest)
        delta = datetime.now().astimezone() - started
        return max(0, int(delta.total_seconds()))
    except (TypeError, ValueError):
        return 0
