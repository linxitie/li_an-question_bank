"""本地投影（F1 用它对事件流做最小可验证消费）。

F1 不接业务投影——业务投影在 F2/F3 各域实现。这里的投影只做两件事：
1. 按聚合记录已应用版本（乱序守卫）；
2. 记录 payload 校验和（重放幂等与对账比对）。
"""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.foundation.stores.base import OutboxEvent

PROJECTION_NAME = "foundation.local_projection"


def payload_checksum(payload) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


class LocalProjection:
    name = PROJECTION_NAME

    def state(self, session: Session, aggregate_type: str, aggregate_id: str):
        return session.execute(
            text(
                """SELECT source_version, checksum FROM foundation_projection_state
                   WHERE projection=:p AND aggregate_type=:t AND aggregate_id=:i"""
            ),
            {"p": self.name, "t": aggregate_type, "i": aggregate_id},
        ).first()

    def apply(self, session: Session, event: OutboxEvent) -> bool:
        """应用事件；旧版本或被覆盖版本返回 False（不视为失败）。"""
        current = self.state(session, event.aggregate_type, event.aggregate_id)
        if current is not None and current.source_version >= event.aggregate_ver:
            return False

        checksum = payload_checksum(event.payload)
        now = _now()
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
                "p": self.name, "t": event.aggregate_type, "i": event.aggregate_id,
                "v": event.aggregate_ver, "c": checksum, "now": now,
            },
        )
        return True


def _now() -> str:
    from datetime import datetime

    return datetime.now().astimezone().isoformat(timespec="seconds")
