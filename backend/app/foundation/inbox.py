"""F2b：消费者幂等收件箱。

foundation_inbox 是 F1 已建表，F2b 起启用。Dispatcher 的 handler 在同一事务里
先 claim 再执行副作用；重复投递（重放、人工重试、多实例竞争）不会再次判成就。
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.foundation.stores.base import OutboxEvent

logger = logging.getLogger(__name__)

_INSERT = text(
    "INSERT OR IGNORE INTO foundation_inbox "
    "(consumer, event_id, event_name, processed_at) "
    "VALUES (:consumer, :event_id, :event_name, :processed_at)"
)


def claim(session: Session, consumer: str, event: OutboxEvent) -> bool:
    """尝试占用 (consumer, event_id)；首次返回 True，已处理返回 False。

    不 commit：由 Dispatcher 与 handler 副作用一起提交，失败时一起回滚。
    """
    result = session.execute(
        _INSERT,
        {
            "consumer": consumer,
            "event_id": event.event_id,
            "event_name": event.event_name,
            "processed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        },
    )
    return result.rowcount == 1
