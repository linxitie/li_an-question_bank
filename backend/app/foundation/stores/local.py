"""SQLite 本地实现（F1 唯一实现；F4 起再加 PG/MySQL 版本）。"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.foundation.stores.base import OutboxEvent


class SqliteOutboxStore:
    def __init__(self, session: Session):
        self.session = session

    def fetch_pending(self, limit: int, now: str) -> list[OutboxEvent]:
        rows = self.session.execute(
            text(
                """SELECT id, event_id, event_name, schema_version, aggregate_type,
                          aggregate_id, aggregate_ver, payload, producer, trace_id,
                          occurred_at, attempts
                   FROM foundation_outbox
                   WHERE status = 'pending'
                     AND (next_retry_at IS NULL OR next_retry_at <= :now)
                   ORDER BY id LIMIT :limit"""
            ),
            {"now": now, "limit": limit},
        ).all()
        return [OutboxEvent.from_row(r) for r in rows]

    def mark_dispatched(self, event_id: str) -> None:
        self.session.execute(
            text(
                """UPDATE foundation_outbox
                   SET status='dispatched', dispatched_at=:now, last_error=NULL
                   WHERE event_id=:id"""
            ),
            {"id": event_id, "now": _now()},
        )

    def mark_retry(self, event_id: str, error: str, next_retry_at: str) -> int:
        result = self.session.execute(
            text(
                """UPDATE foundation_outbox
                   SET attempts=attempts+1, last_error=:err, next_retry_at=:next
                   WHERE event_id=:id"""
            ),
            {"id": event_id, "err": error[:2000], "next": next_retry_at},
        )
        row = self.session.execute(
            text("SELECT attempts FROM foundation_outbox WHERE event_id=:id"), {"id": event_id}
        ).first()
        return int(row.attempts) if row else result.rowcount

    def mark_dead(self, event_id: str, error: str) -> int:
        row = self.session.execute(
            text("SELECT attempts FROM foundation_outbox WHERE event_id=:id"), {"id": event_id}
        ).first()
        self.session.execute(
            text(
                """UPDATE foundation_outbox
                   SET status='dead', last_error=:err, dispatched_at=NULL
                   WHERE event_id=:id"""
            ),
            {"id": event_id, "err": error[:2000]},
        )
        return int(row.attempts) if row else 0


class SqliteCursorStore:
    def __init__(self, session: Session):
        self.session = session

    def get(self, projection: str) -> int:
        row = self.session.execute(
            text("SELECT last_outbox_id FROM foundation_projection_cursor WHERE projection=:p"),
            {"p": projection},
        ).first()
        return int(row.last_outbox_id) if row else 0

    def advance(self, projection: str, outbox_id: int, occurred_at: str) -> None:
        now = _now()
        lag = _seconds_between(occurred_at, now)
        self.session.execute(
            text(
                """INSERT INTO foundation_projection_cursor
                       (projection, last_outbox_id, updated_at, status, lag_seconds)
                   VALUES (:p, :id, :now, 'ok', :lag)
                   ON CONFLICT(projection) DO UPDATE SET
                       last_outbox_id=excluded.last_outbox_id,
                       updated_at=excluded.updated_at,
                       status='ok',
                       lag_seconds=excluded.lag_seconds"""
            ),
            {"p": projection, "id": outbox_id, "now": now, "lag": lag},
        )


def _now() -> str:
    from datetime import datetime

    return datetime.now().astimezone().isoformat(timespec="seconds")


def _seconds_between(start: str, end: str) -> int:
    from datetime import datetime

    try:
        a = datetime.fromisoformat(start)
        b = datetime.fromisoformat(end)
        return max(0, int((b - a).total_seconds()))
    except (TypeError, ValueError):
        return 0
