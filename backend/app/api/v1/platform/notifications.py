"""站内信接口（P0）。

学生、教师、管理员共用；只返回当前用户自己的通知。
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import SysUser, UserNotification

router = APIRouter(prefix="/api/notifications", tags=["站内信"])


def _serialize(n: UserNotification) -> dict:
    return {
        "notification_id": n.notification_id,
        "type": n.type,
        "title": n.title,
        "content": n.content,
        "link": n.link,
        "related_type": n.related_type,
        "related_id": n.related_id,
        "is_read": bool(n.is_read),
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@router.get("", summary="我的通知列表")
async def list_notifications(
    unread_only: bool = Query(False, description="只看未读"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(UserNotification).filter(
        UserNotification.user_id == current_user.user_id
    )
    if unread_only:
        query = query.filter(UserNotification.is_read == 0)

    total = query.count()
    unread = (
        db.query(UserNotification)
        .filter(
            UserNotification.user_id == current_user.user_id,
            UserNotification.is_read == 0,
        )
        .count()
    )
    rows = (
        query.order_by(desc(UserNotification.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "unread": unread,
        "page": page,
        "page_size": page_size,
        "items": [_serialize(n) for n in rows],
    }


@router.put("/{notification_id}/read", summary="标记单条已读")
async def mark_read(
    notification_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(UserNotification)
        .filter(
            UserNotification.notification_id == notification_id,
            UserNotification.user_id == current_user.user_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="通知不存在")
    row.is_read = 1
    db.commit()
    return {"success": True}


@router.put("/read-all", summary="全部标记已读")
async def mark_all_read(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(UserNotification).filter(
        UserNotification.user_id == current_user.user_id,
        UserNotification.is_read == 0,
    ).update({UserNotification.is_read: 1})
    db.commit()
    return {"success": True}
