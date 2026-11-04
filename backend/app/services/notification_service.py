"""站内信统一写入服务。

所有业务域（反馈、论坛、提及、系统）通过这里写通知，
避免各自直接拼 UserNotification 造成字段不一致。
"""
from typing import Optional

from sqlalchemy.orm import Session

from ..models.models import UserNotification


def create_notification(
    db: Session,
    user_id: int,
    *,
    type: str = "system",
    title: str,
    content: Optional[str] = None,
    link: Optional[str] = None,
    related_type: Optional[str] = None,
    related_id: Optional[int] = None,
) -> UserNotification:
    notification = UserNotification(
        user_id=user_id,
        type=type,
        title=title,
        content=content,
        link=link,
        related_type=related_type,
        related_id=related_id,
    )
    db.add(notification)
    return notification
