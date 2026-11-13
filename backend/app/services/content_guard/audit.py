"""追加式哈希链审计：每一次知识变更都可回溯、可校验。"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from ...models.content_guard import CgAuditEvent

GENESIS = "GENESIS"


def canonical(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(payload: Any) -> str:
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def _last_hash(db: Session) -> str:
    row = db.query(CgAuditEvent).order_by(CgAuditEvent.event_id.desc()).first()
    return row.hash if row else GENESIS


def _hash_input(event: CgAuditEvent) -> dict:
    return {
        "event_id": event.event_id,
        "ts": event.ts.isoformat() if event.ts else None,
        "actor": event.actor,
        "actor_role": event.actor_role,
        "action": event.action,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "before_hash": event.before_hash,
        "after_hash": event.after_hash,
        "payload": event.payload or {},
        "prev_hash": event.prev_hash,
        "ip": event.ip,
    }


def record(
    db: Session,
    action: str,
    *,
    actor: str = "system",
    actor_role: str = "system",
    target_type: Optional[str] = None,
    target_id: Any = None,
    before: Any = None,
    after: Any = None,
    payload: Optional[dict] = None,
    ip: Optional[str] = None,
) -> CgAuditEvent:
    """写入一条事件；hash 依赖自增 event_id，因此先 flush 后回填。"""
    event = CgAuditEvent(
        ts=datetime.now(),
        actor=actor or "system",
        actor_role=actor_role or "system",
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        before_hash=digest(before) if before is not None else None,
        after_hash=digest(after) if after is not None else None,
        payload=payload or {},
        prev_hash=_last_hash(db),
        hash=f"pending-{uuid.uuid4().hex}",
        ip=ip,
    )
    db.add(event)
    db.flush()
    event.hash = hashlib.sha256(
        (event.prev_hash + canonical(_hash_input(event))).encode("utf-8")
    ).hexdigest()
    db.flush()
    return event


def verify_chain(db: Session) -> dict:
    """重算整条链；返回 {ok, total, broken_at, detail}。"""
    rows = db.query(CgAuditEvent).order_by(CgAuditEvent.event_id.asc()).all()
    prev = GENESIS
    for row in rows:
        expected = hashlib.sha256(
            (row.prev_hash + canonical(_hash_input(row))).encode("utf-8")
        ).hexdigest()
        if row.prev_hash != prev:
            return {
                "ok": False,
                "total": len(rows),
                "broken_at": row.event_id,
                "detail": "prev_hash 与上一条事件不一致",
            }
        if row.hash != expected:
            return {
                "ok": False,
                "total": len(rows),
                "broken_at": row.event_id,
                "detail": "事件内容与哈希不匹配",
            }
        prev = row.hash
    return {"ok": True, "total": len(rows), "broken_at": None, "detail": "哈希链完整"}


def recent(db: Session, limit: int = 50, action: Optional[str] = None) -> list[dict]:
    query = db.query(CgAuditEvent)
    if action:
        query = query.filter(CgAuditEvent.action == action)
    rows = query.order_by(CgAuditEvent.event_id.desc()).limit(min(limit, 500)).all()
    return [
        {
            "event_id": r.event_id,
            "ts": r.ts.isoformat(timespec="seconds") if r.ts else None,
            "actor": r.actor,
            "actor_role": r.actor_role,
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "before_hash": r.before_hash,
            "after_hash": r.after_hash,
            "payload": r.payload,
            "prev_hash": r.prev_hash,
            "hash": r.hash,
        }
        for r in rows
    ]
