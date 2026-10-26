"""Dispatcher 依赖的存储协议（只读/推进位点，不做业务判断）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class OutboxEvent:
    id: int
    event_id: str
    event_name: str
    schema_version: int
    aggregate_type: str
    aggregate_id: str
    aggregate_ver: int
    payload: Any
    producer: str
    trace_id: str | None
    occurred_at: str
    attempts: int

    @classmethod
    def from_row(cls, row) -> "OutboxEvent":
        import json

        payload = row.payload
        try:
            payload = json.loads(payload) if isinstance(payload, str) else payload
        except json.JSONDecodeError:
            payload = {"_raw": row.payload}
        return cls(
            id=row.id,
            event_id=row.event_id,
            event_name=row.event_name,
            schema_version=row.schema_version,
            aggregate_type=row.aggregate_type,
            aggregate_id=row.aggregate_id,
            aggregate_ver=row.aggregate_ver,
            payload=payload,
            producer=row.producer,
            trace_id=row.trace_id,
            occurred_at=row.occurred_at,
            attempts=row.attempts,
        )


class OutboxStore(Protocol):
    def fetch_pending(self, limit: int, now: str) -> list[OutboxEvent]: ...
    def mark_dispatched(self, event_id: str) -> None: ...
    def mark_retry(self, event_id: str, error: str, next_retry_at: str) -> int: ...
    def mark_dead(self, event_id: str, error: str) -> int: ...


class CursorStore(Protocol):
    def get(self, projection: str) -> int: ...
    def advance(self, projection: str, outbox_id: int, occurred_at: str) -> None: ...
