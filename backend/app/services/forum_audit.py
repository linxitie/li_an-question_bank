"""论坛回收站定期审计。

每日统计软删除、教师隐藏、待复核积压情况，写入操作日志；
不自动物理删除，彻底删除仍由超级管理员手动执行。
"""
from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy.orm import Session

from ..models.models import ForumComment, ForumModeration, ForumPost, SysOperationLog

AUDIT_OPERATION_TYPE = "论坛回收站审计"


def collect_forum_recycle_stats(db: Session) -> Dict[str, int]:
    deleted_posts = (
        db.query(ForumPost).filter(ForumPost.status == "DELETED").count()
    )
    hidden_posts = (
        db.query(ForumPost).filter(ForumPost.status == "BLOCKED").count()
    )
    deleted_comments = (
        db.query(ForumComment).filter(ForumComment.status == 0).count()
    )
    hidden_comments = (
        db.query(ForumComment).filter(ForumComment.status == 2).count()
    )
    pending_moderation = (
        db.query(ForumModeration)
        .filter(ForumModeration.status == "PENDING")
        .count()
    )
    seven_days_ago = datetime.now() - timedelta(days=7)
    stale_pending = (
        db.query(ForumModeration)
        .filter(
            ForumModeration.status == "PENDING",
            ForumModeration.created_at < seven_days_ago,
        )
        .count()
    )
    return {
        "deleted_posts": deleted_posts,
        "hidden_posts": hidden_posts,
        "deleted_comments": deleted_comments,
        "hidden_comments": hidden_comments,
        "pending_moderation": pending_moderation,
        "stale_pending": stale_pending,
    }


def run_forum_recycle_audit(db: Session) -> Dict[str, int]:
    stats = collect_forum_recycle_stats(db)
    description = (
        f"回收站审计: 已删帖子={stats['deleted_posts']} "
        f"隐藏帖子={stats['hidden_posts']} "
        f"已删评论={stats['deleted_comments']} "
        f"隐藏评论={stats['hidden_comments']} "
        f"待复核={stats['pending_moderation']} "
        f"超7天未复核={stats['stale_pending']}"
    )
    db.add(
        SysOperationLog(
            user_id=None,
            user_name="system",
            operation_type=AUDIT_OPERATION_TYPE,
            module_name="论坛",
            operation_desc=description[:200],
            request_method="CRON",
            request_url="",
            request_params="",
            response_result="success",
            ip_address="",
            operation_time=datetime.now(),
        )
    )
    db.commit()
    return stats
