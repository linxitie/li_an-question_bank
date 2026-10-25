"""教师端/管理员端论坛管理接口（P3/P4）。

- 教师：隐藏本班学生内容（必填原因），进入管理员复核队列；
- 管理员：删除任意角色内容、复核教师删除、回收站恢复/彻底删除。
所有动作软删除 + 审计。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user, require_admin, require_teacher_or_admin
from ....models.models import (
    ForumComment,
    ForumModeration,
    ForumPost,
    SysOperationLog,
    SysUser,
)
from .forum import _serialize_comment, _serialize_post, _user_brief

teacher_router = APIRouter(prefix="/api/teacher/forum", tags=["教师端-论坛"])
admin_router = APIRouter(prefix="/api/admin/forum", tags=["管理员端-论坛"])


class ReasonPayload(BaseModel):
    reason: str = Field(..., min_length=1, max_length=200)


class ReviewPayload(BaseModel):
    note: Optional[str] = Field(None, max_length=200)


def _audit(
    db: Session,
    user: SysUser,
    operation_type: str,
    description: str,
) -> None:
    db.add(
        SysOperationLog(
            user_id=user.user_id,
            user_name=user.username,
            operation_type=operation_type,
            module_name="论坛",
            operation_desc=description[:200],
            request_method="POST",
            request_url="",
            request_params="",
            response_result="success",
            ip_address="",
            operation_time=datetime.now(),
        )
    )


def _is_my_student(teacher: SysUser, author: Optional[SysUser]) -> bool:
    return bool(
        author
        and author.user_type == "student"
        and teacher.class_name
        and author.class_name == teacher.class_name
    )


def _post_item(
    post: ForumPost,
    author: Optional[SysUser],
    *,
    can_delete: bool,
    moderation_status: Optional[str] = None,
) -> Dict[str, Any]:
    data = _serialize_post(post, author)
    data.update(
        {
            "status": post.status,
            "deletedBy": post.deleted_by,
            "deletedReason": post.deleted_reason,
            "deletedAt": post.deleted_at.isoformat() if post.deleted_at else None,
            "moderationStatus": moderation_status,
            "canDelete": can_delete,
            "authorClass": author.class_name if author else None,
            "authorType": author.user_type if author else None,
        }
    )
    return data


def _comment_item(
    comment: ForumComment,
    author: Optional[SysUser],
    *,
    can_delete: bool,
    moderation_status: Optional[str] = None,
) -> Dict[str, Any]:
    data = _serialize_comment(comment, author)
    data.update(
        {
            "status": comment.status,
            "deletedBy": comment.deleted_by,
            "deletedReason": comment.deleted_reason,
            "deletedAt": comment.deleted_at.isoformat() if comment.deleted_at else None,
            "moderationStatus": moderation_status,
            "canDelete": can_delete,
            "authorClass": author.class_name if author else None,
            "authorType": author.user_type if author else None,
        }
    )
    return data


def _latest_moderation_status(db: Session, target_type: str, target_id: int):
    row = (
        db.query(ForumModeration)
        .filter(
            ForumModeration.target_type == target_type,
            ForumModeration.target_id == target_id,
        )
        .order_by(desc(ForumModeration.created_at))
        .first()
    )
    return row


# ============================== 教师端 ==============================

@teacher_router.get("/posts", summary="教师端帖子列表（全校可见）")
async def teacher_posts(
    keyword: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    class_name: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: SysUser = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    query = db.query(ForumPost).filter(ForumPost.status == "NORMAL")
    if category:
        query = query.filter(ForumPost.share_type == category)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(ForumPost.title.like(like), ForumPost.content.like(like))
        )
    if class_name:
        user_ids = [
            row[0]
            for row in db.query(SysUser.user_id)
            .filter(SysUser.class_name == class_name)
            .all()
        ]
        query = query.filter(ForumPost.user_id.in_(user_ids or [-1]))

    total = query.count()
    rows = (
        query.order_by(ForumPost.create_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    user_ids = {p.user_id for p in rows}
    users = db.query(SysUser).filter(SysUser.user_id.in_(user_ids)).all() if user_ids else []
    user_map = {u.user_id: u for u in users}

    items = []
    for post in rows:
        author = user_map.get(post.user_id)
        admin_view = current_user.user_type == "admin"
        items.append(
            _post_item(
                post,
                author,
                can_delete=admin_view or _is_my_student(current_user, author),
            )
        )
    return {"total": total, "items": items}


@teacher_router.get("/posts/{post_id}/comments", summary="教师端评论列表")
async def teacher_comments(
    post_id: int,
    limit: int = Query(100, ge=1, le=200),
    current_user: SysUser = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    post = db.query(ForumPost).filter(ForumPost.post_id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    rows = (
        db.query(ForumComment)
        .filter(
            ForumComment.post_id == post_id,
            ForumComment.status.in_([1, 2]),
        )
        .order_by(ForumComment.is_pinned.desc(), ForumComment.create_time.desc())
        .limit(limit)
        .all()
    )
    user_ids = {c.user_id for c in rows}
    users = db.query(SysUser).filter(SysUser.user_id.in_(user_ids)).all() if user_ids else []
    user_map = {u.user_id: u for u in users}
    return {
        "items": [
            _comment_item(
                c,
                user_map.get(c.user_id),
                can_delete=current_user.user_type == "admin"
                or _is_my_student(current_user, user_map.get(c.user_id)),
            )
            for c in rows
        ]
    }


def _hide_post(db: Session, post: ForumPost, user: SysUser, reason: str):
    if post.status != "NORMAL":
        raise HTTPException(status_code=400, detail="该帖子已不是正常状态")
    author = db.query(SysUser).filter(SysUser.user_id == post.user_id).first()
    if user.user_type != "admin" and not _is_my_student(user, author):
        raise HTTPException(status_code=403, detail="只能处理本班学生的帖子")

    post.status = "BLOCKED"
    post.deleted_by = user.user_id
    post.deleted_reason = reason
    post.deleted_at = datetime.now()
    moderation = ForumModeration(
        target_type="POST",
        target_id=post.post_id,
        action="TEACHER_HIDE",
        reason=reason,
        actor_id=user.user_id,
        status="PENDING",
    )
    db.add(moderation)
    _audit(db, user, "教师隐藏帖子", f"post_id={post.post_id} reason={reason}")
    db.commit()
    return moderation


def _hide_comment(db: Session, comment: ForumComment, user: SysUser, reason: str):
    if comment.status != 1:
        raise HTTPException(status_code=400, detail="该评论已不是正常状态")
    author = db.query(SysUser).filter(SysUser.user_id == comment.user_id).first()
    if user.user_type != "admin" and not _is_my_student(user, author):
        raise HTTPException(status_code=403, detail="只能处理本班学生的评论")

    comment.status = 2
    comment.deleted_by = user.user_id
    comment.deleted_reason = reason
    comment.deleted_at = datetime.now()
    moderation = ForumModeration(
        target_type="COMMENT",
        target_id=comment.comment_id,
        action="TEACHER_HIDE",
        reason=reason,
        actor_id=user.user_id,
        status="PENDING",
    )
    db.add(moderation)
    _audit(db, user, "教师隐藏评论", f"comment_id={comment.comment_id} reason={reason}")
    db.commit()
    return moderation


@teacher_router.post("/posts/{post_id}/hide", summary="教师隐藏本班学生帖子")
async def hide_post(
    post_id: int,
    payload: ReasonPayload,
    current_user: SysUser = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    post = db.query(ForumPost).filter(ForumPost.post_id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    moderation = _hide_post(db, post, current_user, payload.reason.strip())
    return {"success": True, "moderation_id": moderation.id}


@teacher_router.post("/comments/{comment_id}/hide", summary="教师隐藏本班学生评论")
async def hide_comment(
    comment_id: int,
    payload: ReasonPayload,
    current_user: SysUser = Depends(require_teacher_or_admin),
    db: Session = Depends(get_db),
):
    comment = db.query(ForumComment).filter(ForumComment.comment_id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    moderation = _hide_comment(db, comment, current_user, payload.reason.strip())
    return {"success": True, "moderation_id": moderation.id}


# ============================== 管理员端 ==============================

@admin_router.get("/posts", summary="管理员端帖子列表")
async def admin_posts(
    keyword: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    class_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    _: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(ForumPost)
    if status:
        query = query.filter(ForumPost.status == status)
    if category:
        query = query.filter(ForumPost.share_type == category)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(ForumPost.title.like(like), ForumPost.content.like(like))
        )
    if class_name:
        user_ids = [
            row[0]
            for row in db.query(SysUser.user_id)
            .filter(SysUser.class_name == class_name)
            .all()
        ]
        query = query.filter(ForumPost.user_id.in_(user_ids or [-1]))

    total = query.count()
    rows = (
        query.order_by(ForumPost.create_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    user_ids = {p.user_id for p in rows}
    users = db.query(SysUser).filter(SysUser.user_id.in_(user_ids)).all() if user_ids else []
    user_map = {u.user_id: u for u in users}
    return {
        "total": total,
        "items": [
            _post_item(
                p,
                user_map.get(p.user_id),
                can_delete=True,
                moderation_status=(
                    _latest_moderation_status(db, "POST", p.post_id).status
                    if _latest_moderation_status(db, "POST", p.post_id)
                    else None
                ),
            )
            for p in rows
        ],
    }


@admin_router.get("/comments", summary="管理员端评论列表")
async def admin_comments(
    post_id: int = Query(...),
    limit: int = Query(200, ge=1, le=300),
    _: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ForumComment)
        .filter(ForumComment.post_id == post_id)
        .order_by(ForumComment.create_time.desc())
        .limit(limit)
        .all()
    )
    user_ids = {c.user_id for c in rows}
    users = db.query(SysUser).filter(SysUser.user_id.in_(user_ids)).all() if user_ids else []
    user_map = {u.user_id: u for u in users}
    return {
        "items": [
            _comment_item(
                c, user_map.get(c.user_id), can_delete=True,
                moderation_status=(
                    _latest_moderation_status(db, "COMMENT", c.comment_id).status
                    if _latest_moderation_status(db, "COMMENT", c.comment_id)
                    else None
                ),
            )
            for c in rows
        ]
    }


@admin_router.delete("/posts/{post_id}", summary="管理员删除帖子")
async def admin_delete_post(
    post_id: int,
    reason: Optional[str] = Query(None, max_length=200),
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    post = db.query(ForumPost).filter(ForumPost.post_id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    post.status = "DELETED"
    post.deleted_by = current_user.user_id
    post.deleted_reason = reason
    post.deleted_at = datetime.now()
    db.add(
        ForumModeration(
            target_type="POST",
            target_id=post_id,
            action="ADMIN_DELETE",
            reason=reason,
            actor_id=current_user.user_id,
            status="APPROVED",
            reviewed_by=current_user.user_id,
            reviewed_at=datetime.now(),
        )
    )
    _audit(db, current_user, "管理员删除帖子", f"post_id={post_id} reason={reason or ''}")
    db.commit()
    return {"success": True}


@admin_router.delete("/comments/{comment_id}", summary="管理员删除评论")
async def admin_delete_comment(
    comment_id: int,
    reason: Optional[str] = Query(None, max_length=200),
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    comment = db.query(ForumComment).filter(ForumComment.comment_id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    comment.status = 0
    comment.deleted_by = current_user.user_id
    comment.deleted_reason = reason
    comment.deleted_at = datetime.now()
    db.add(
        ForumModeration(
            target_type="COMMENT",
            target_id=comment_id,
            action="ADMIN_DELETE",
            reason=reason,
            actor_id=current_user.user_id,
            status="APPROVED",
            reviewed_by=current_user.user_id,
            reviewed_at=datetime.now(),
        )
    )
    _audit(db, current_user, "管理员删除评论", f"comment_id={comment_id} reason={reason or ''}")
    db.commit()
    return {"success": True}


@admin_router.get("/moderation", summary="教师删除待复核队列")
async def moderation_queue(
    status: str = Query("PENDING"),
    limit: int = Query(50, ge=1, le=200),
    _: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(ForumModeration)
        .filter(ForumModeration.status == status)
        .order_by(ForumModeration.created_at.desc())
        .limit(limit)
        .all()
    )
    items = []
    for row in rows:
        target = None
        if row.target_type == "POST":
            post = db.query(ForumPost).filter(ForumPost.post_id == row.target_id).first()
            if post:
                author = db.query(SysUser).filter(SysUser.user_id == post.user_id).first()
                target = _post_item(post, author, can_delete=True, moderation_status=row.status)
        else:
            comment = db.query(ForumComment).filter(
                ForumComment.comment_id == row.target_id
            ).first()
            if comment:
                author = db.query(SysUser).filter(SysUser.user_id == comment.user_id).first()
                target = _comment_item(
                    comment, author, can_delete=True, moderation_status=row.status
                )
        items.append(
            {
                "id": row.id,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "action": row.action,
                "reason": row.reason,
                "status": row.status,
                "actor_id": row.actor_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "target": target,
            }
        )
    return {"items": items}


def _set_target_status(db: Session, row: ForumModeration, *, approve: bool):
    if row.target_type == "POST":
        target = db.query(ForumPost).filter(ForumPost.post_id == row.target_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="目标帖子不存在")
        target.status = "DELETED" if approve else "NORMAL"
        if not approve:
            target.deleted_by = None
            target.deleted_reason = None
            target.deleted_at = None
    else:
        target = db.query(ForumComment).filter(
            ForumComment.comment_id == row.target_id
        ).first()
        if not target:
            raise HTTPException(status_code=404, detail="目标评论不存在")
        target.status = 0 if approve else 1
        if not approve:
            target.deleted_by = None
            target.deleted_reason = None
            target.deleted_at = None


@admin_router.post("/moderation/{moderation_id}/approve", summary="确认教师删除")
async def approve_moderation(
    moderation_id: int,
    payload: ReviewPayload,
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.query(ForumModeration).filter(ForumModeration.id == moderation_id).first()
    if not row or row.status != "PENDING":
        raise HTTPException(status_code=404, detail="待复核记录不存在")
    _set_target_status(db, row, approve=True)
    row.status = "APPROVED"
    row.reviewed_by = current_user.user_id
    row.reviewed_at = datetime.now()
    row.review_note = payload.note
    _audit(db, current_user, "复核确认删除", f"moderation_id={moderation_id}")
    db.commit()
    return {"success": True}


@admin_router.post("/moderation/{moderation_id}/reject", summary="驳回教师删除并恢复")
async def reject_moderation(
    moderation_id: int,
    payload: ReviewPayload,
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    row = db.query(ForumModeration).filter(ForumModeration.id == moderation_id).first()
    if not row or row.status != "PENDING":
        raise HTTPException(status_code=404, detail="待复核记录不存在")
    _set_target_status(db, row, approve=False)
    row.status = "REJECTED"
    row.reviewed_by = current_user.user_id
    row.reviewed_at = datetime.now()
    row.review_note = payload.note
    _audit(db, current_user, "复核驳回恢复", f"moderation_id={moderation_id}")
    db.commit()
    return {"success": True}


@admin_router.get("/recycle", summary="回收站")
async def recycle_bin(
    limit: int = Query(50, ge=1, le=200),
    _: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    posts = (
        db.query(ForumPost)
        .filter(ForumPost.status.in_(["DELETED", "BLOCKED"]))
        .order_by(ForumPost.deleted_at.desc())
        .limit(limit)
        .all()
    )
    comments = (
        db.query(ForumComment)
        .filter(ForumComment.status.in_([0, 2]))
        .order_by(ForumComment.deleted_at.desc())
        .limit(limit)
        .all()
    )
    post_user_ids = {p.user_id for p in posts}
    comment_user_ids = {c.user_id for c in comments}
    user_ids = post_user_ids | comment_user_ids
    users = db.query(SysUser).filter(SysUser.user_id.in_(user_ids)).all() if user_ids else []
    user_map = {u.user_id: u for u in users}
    return {
        "posts": [
            _post_item(p, user_map.get(p.user_id), can_delete=True) for p in posts
        ],
        "comments": [
            _comment_item(c, user_map.get(c.user_id), can_delete=True) for c in comments
        ],
    }


@admin_router.post("/posts/{post_id}/restore", summary="恢复帖子")
async def restore_post(
    post_id: int,
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    post = db.query(ForumPost).filter(ForumPost.post_id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    post.status = "NORMAL"
    post.deleted_by = None
    post.deleted_reason = None
    post.deleted_at = None
    _audit(db, current_user, "恢复帖子", f"post_id={post_id}")
    db.commit()
    return {"success": True}


@admin_router.post("/comments/{comment_id}/restore", summary="恢复评论")
async def restore_comment(
    comment_id: int,
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    comment = db.query(ForumComment).filter(ForumComment.comment_id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    comment.status = 1
    comment.deleted_by = None
    comment.deleted_reason = None
    comment.deleted_at = None
    _audit(db, current_user, "恢复评论", f"comment_id={comment_id}")
    db.commit()
    return {"success": True}


@admin_router.delete("/posts/{post_id}/purge", summary="彻底删除帖子（超级管理员）")
async def purge_post(
    post_id: int,
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if current_user.role_level < 3:
        raise HTTPException(status_code=403, detail="仅超级管理员可彻底删除")
    post = db.query(ForumPost).filter(ForumPost.post_id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    db.query(ForumComment).filter(ForumComment.post_id == post_id).delete()
    db.delete(post)
    _audit(db, current_user, "彻底删除帖子", f"post_id={post_id}")
    db.commit()
    return {"success": True}


@admin_router.delete("/comments/{comment_id}/purge", summary="彻底删除评论（超级管理员）")
async def purge_comment(
    comment_id: int,
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if current_user.role_level < 3:
        raise HTTPException(status_code=403, detail="仅超级管理员可彻底删除")
    comment = db.query(ForumComment).filter(ForumComment.comment_id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    db.delete(comment)
    _audit(db, current_user, "彻底删除评论", f"comment_id={comment_id}")
    db.commit()
    return {"success": True}
