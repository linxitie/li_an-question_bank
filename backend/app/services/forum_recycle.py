"""论坛回收站：30 天保留与到期彻底删除。

规则（2026-11-07 用户决策）：
- 作者/管理员删除 = 软删除（status=DELETED + deleted_at），进回收站；
- 回收站保留 30 天，超期由每日定时任务物理删除（帖子 + 其下评论）；
- 学生只可恢复自己的帖子，管理员可在回收站彻底删除。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from ..models.models import ForumComment, ForumPost

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30


def purge_expired(db: Session, days: int = RETENTION_DAYS) -> dict:
    """物理删除超过保留期的已删除帖子及其评论。返回统计，供定时任务记录。"""
    cutoff = datetime.now() - timedelta(days=days)
    rows = (
        db.query(ForumPost.post_id)
        .filter(
            ForumPost.status == "DELETED",
            ForumPost.deleted_at.isnot(None),
            ForumPost.deleted_at < cutoff,
        )
        .all()
    )
    post_ids = [row[0] for row in rows]
    if not post_ids:
        return {"purged_posts": 0, "purged_comments": 0, "cutoff": cutoff.isoformat()}
    comments = (
        db.query(ForumComment)
        .filter(ForumComment.post_id.in_(post_ids))
        .delete(synchronize_session=False)
    )
    posts = (
        db.query(ForumPost)
        .filter(ForumPost.post_id.in_(post_ids))
        .delete(synchronize_session=False)
    )
    db.commit()
    logger.info("回收站到期清理: 帖子 %s 条, 评论 %s 条, cutoff=%s", posts, comments, cutoff)
    return {"purged_posts": posts, "purged_comments": comments, "cutoff": cutoff.isoformat()}
