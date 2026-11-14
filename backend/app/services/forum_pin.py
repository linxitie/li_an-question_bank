"""论坛置顶到期自动取消（2026-11-10）。

置顶接口支持「置顶 N 天」，到期后必须自动回到普通排序，否则会永久占位。
调度任务每 10 分钟调用一次 expire_due()；查询侧不额外过滤，
因为最多存在 10 分钟的延迟窗口，且列表排序本身以 is_top 为准。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..models.models import ForumPost

logger = logging.getLogger(__name__)


def expire_due(db: Session, now: Optional[datetime] = None) -> int:
    """取消所有 pin_until <= now 的置顶，返回处理条数。"""
    now = now or datetime.now()
    rows = (
        db.query(ForumPost)
        .filter(
            ForumPost.is_top == 1,
            ForumPost.pin_until.isnot(None),
            ForumPost.pin_until <= now,
        )
        .all()
    )
    for post in rows:
        post.is_top = 0
        post.pin_until = None
    if rows:
        db.commit()
        logger.info("到期置顶自动取消: %s 条", len(rows))
    return len(rows)
