"""事务性发件箱：与业务写共用同一个 Session，保证「业务行 + 事件行」同生共死。

纪律（§19）：
- 只用参数化 SQL，禁止拼串；
- payload 必须是可解析 JSON；
- dedupe_key 命中直接返回 None，不抛错、不重复写；
- aggregate_ver 缺省按聚合内 MAX+1 递增，消费者据此丢弃旧版本。
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

_INSERT = text(
    """
    INSERT INTO foundation_outbox (
        event_id, event_name, schema_version, aggregate_type, aggregate_id,
        aggregate_ver, dedupe_key, payload, producer, trace_id, occurred_at, status
    ) VALUES (
        :event_id, :event_name, :schema_version, :aggregate_type, :aggregate_id,
        :aggregate_ver, :dedupe_key, :payload, :producer, :trace_id, :occurred_at, 'pending'
    )
    """
)


def next_aggregate_version(session: Session, aggregate_type: str, aggregate_id: str) -> int:
    row = session.execute(
        text(
            """SELECT COALESCE(MAX(aggregate_ver), -1) FROM foundation_outbox
               WHERE aggregate_type = :t AND aggregate_id = :i"""
        ),
        {"t": aggregate_type, "i": str(aggregate_id)},
    ).scalar_one()
    return int(row) + 1


def _encode_payload(payload: Any) -> str:
    if isinstance(payload, str):
        try:
            json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f"payload 不是合法 JSON: {exc}") from exc
        return payload
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def emit(
    session: Session,
    *,
    event_name: str,
    aggregate_type: str,
    aggregate_id: Any,
    payload: Any,
    producer: str,
    aggregate_ver: int | None = None,
    dedupe_key: str | None = None,
    trace_id: str | None = None,
    schema_version: int = 1,
    occurred_at: str | None = None,
) -> str | None:
    """写一条 pending 事件，返回 event_id；dedupe 命中返回 None。

    不 commit —— 由调用方与业务写一起提交，这是「原子」的全部含义。
    """
    aggregate_id = str(aggregate_id)
    payload_json = _encode_payload(payload)
    if aggregate_ver is None:
        aggregate_ver = next_aggregate_version(session, aggregate_type, aggregate_id)
    if dedupe_key:
        hit = session.execute(
            text("SELECT 1 FROM foundation_outbox WHERE dedupe_key = :k"), {"k": dedupe_key}
        ).first()
        if hit:
            return None

    event_id = uuid.uuid4().hex
    params = {
        "event_id": event_id,
        "event_name": event_name,
        "schema_version": schema_version,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "aggregate_ver": aggregate_ver,
        "dedupe_key": dedupe_key,
        "payload": payload_json,
        "producer": producer,
        "trace_id": trace_id,
        "occurred_at": occurred_at or datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    try:
        with session.begin_nested():
            session.execute(_INSERT, params)
    except IntegrityError:
        if dedupe_key:
            return None
        raise
    return event_id
