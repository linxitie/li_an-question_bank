"""教师端/管理员端论坛管理接口（P3/P4）。

- 教师：隐藏本班学生内容（必填原因），进入管理员复核队列；
- 管理员：删除任意角色内容、复核教师删除、回收站恢复/彻底删除。
所有动作软删除 + 审计。
"""
from datetime import datetime, timedelta
from collections import Counter
from typing import Any, Dict, List, Optional
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user, require_admin, require_teacher_or_admin
from ....services.class_scope import teacher_class_names, is_my_student  # 班级范围下沉 services（边界门禁）
from ....models.models import (
    ForumComment,
    ForumModeration,
    ForumPost,
    SysOperationLog,
    SysUser,
)
from ....services.forum_audit import collect_forum_recycle_stats
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


# 班级范围查询已下沉：from ....services.class_scope import teacher_class_names, is_my_student
# 原因：本文件此前直接 import platform 域的 Banji 模型，触发边界门禁 cross_write 违规。


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
            "author": (author.nickname or author.username) if author else "匿名",
            "authorAvatar": author.avatar if author else "",
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
            "author": (author.nickname or author.username) if author else "匿名",
            "authorAvatar": author.avatar if author else "",
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
    date_from: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD（含当天）"),
    date_to: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD（含当天）"),
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

    # P3：日期区间（两端含当天，与 /api/forum/posts 口径一致）
    if date_from:
        try:
            query = query.filter(ForumPost.create_time >= datetime.strptime(date_from, "%Y-%m-%d"))
        except ValueError:
            raise ValidationError("date_from 格式应为 YYYY-MM-DD")
    if date_to:
        try:
            _end = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            raise ValidationError("date_to 格式应为 YYYY-MM-DD")
        query = query.filter(ForumPost.create_time < _end)

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

    class_names = sorted(teacher_class_names(db, current_user))
    admin_view = current_user.user_type == "admin"
    can_moderate = admin_view or bool(class_names)

    items = []
    for post in rows:
        author = user_map.get(post.user_id)
        items.append(
            _post_item(
                post,
                author,
                can_delete=admin_view or is_my_student(db, current_user, author),
            )
        )
    return {
        "total": total,
        "teacherClasses": class_names,
        "canModerate": can_moderate,
        "items": items,
    }


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
                or is_my_student(db, current_user, user_map.get(c.user_id)),
            )
            for c in rows
        ]
    }


def _hide_post(db: Session, post: ForumPost, user: SysUser, reason: str):
    if post.status != "NORMAL":
        raise HTTPException(status_code=400, detail="该帖子已不是正常状态")
    author = db.query(SysUser).filter(SysUser.user_id == post.user_id).first()
    if user.user_type != "admin" and not is_my_student(db, user, author):
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
    if user.user_type != "admin" and not is_my_student(db, user, author):
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
    date_from: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD（含当天）"),
    date_to: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD（含当天）"),
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
        # 关键词同时命中作者昵称/账号，对齐管理端「搜索标题 / 内容 / 作者」的单一搜索框
        like = f"%{keyword.strip()}%"
        author_ids = [
            row[0]
            for row in db.query(SysUser.user_id)
            .filter(or_(SysUser.nickname.like(like), SysUser.username.like(like)))
            .all()
        ]
        conditions = [ForumPost.title.like(like), ForumPost.content.like(like)]
        if author_ids:
            conditions.append(ForumPost.user_id.in_(author_ids))
        query = query.filter(or_(*conditions))
    if date_from or date_to:
        try:
            if date_from:
                query = query.filter(
                    ForumPost.create_time >= datetime.strptime(date_from, "%Y-%m-%d")
                )
            if date_to:
                # 结束日期含当天：右开区间到次日 0 点
                query = query.filter(
                    ForumPost.create_time
                    < datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD") from exc
    if class_name:
        user_ids = [
            row[0]
            for row in db.query(SysUser.user_id)
            .filter(SysUser.class_name == class_name)
            .all()
        ]
        query = query.filter(ForumPost.user_id.in_(user_ids or [-1]))

    total = query.count()
    classes = sorted({row[0] for row in db.query(SysUser.class_name).distinct().all() if row[0]})
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
        "classes": classes,
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
    # 与批量接口共用同一实现，避免两条路径的软删除语义漂移
    _apply_post_action(db, "delete", post, current_user, reason, single=True)
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


@admin_router.get("/recycle/audit", summary="回收站审计统计")
async def recycle_audit(
    _: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return collect_forum_recycle_stats(db)


@admin_router.get("/recycle", summary="回收站")
async def recycle_bin(
    kind: Optional[str] = Query(None, pattern="^(post|comment)$", description="只取某类"),
    status: Optional[str] = Query(None, pattern="^(DELETED|BLOCKED)$", description="只取某状态"),
    keyword: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """回收站（软删除 + 被隐藏）。分类别分页，返回各自 total 供前端分页器使用。"""
    post_query = db.query(ForumPost).filter(ForumPost.status.in_(["DELETED", "BLOCKED"]))
    if status:
        post_query = post_query.filter(ForumPost.status == status)
    if keyword:
        like = f"%{keyword.strip()}%"
        post_query = post_query.filter(
            or_(ForumPost.title.like(like), ForumPost.content.like(like))
        )

    comment_query = db.query(ForumComment).filter(ForumComment.status.in_([0, 2]))
    if keyword:
        like = f"%{keyword.strip()}%"
        comment_query = comment_query.filter(ForumComment.content.like(like))

    total_posts = 0 if kind == "comment" else post_query.count()
    total_comments = 0 if kind == "post" else comment_query.count()

    posts = (
        []
        if kind == "comment"
        else post_query.order_by(ForumPost.deleted_at.desc()).offset(offset).limit(limit).all()
    )
    comments = (
        []
        if kind == "post"
        else comment_query.order_by(ForumComment.deleted_at.desc())
        .offset(offset)
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
        "totalPosts": total_posts,
        "totalComments": total_comments,
        "offset": offset,
        "limit": limit,
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
    _apply_post_action(db, "restore", post, current_user, None, single=True)
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
    _apply_post_action(db, "purge", post, current_user, None, single=True)
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


# =====================================================================
# 管理员端增强（P3a）：隐藏 / 取消隐藏 / 批量操作
#
# 设计约束：
#   - 隐藏 = status='BLOCKED'，与「教师隐藏待复核」同一状态位，但管理员操作直接 APPROVED；
#   - 取消隐藏 = status='NORMAL'，并把该帖仍处 PENDING 的复核记录一并驳回，避免队列残留；
#   - 批量接口逐条执行，单条失败不中断，返回 affected/skipped 便于前端提示；
#   - 彻底删除仍受 role_level >= 3 限制（与单条接口一致）。
# =====================================================================


class BatchActionPayload(BaseModel):
    """批量操作载荷。ids 上限 100，避免单次请求过重。"""

    action: str = Field(..., pattern="^(hide|unhide|delete|restore|purge)$")
    ids: List[int] = Field(..., min_length=1, max_length=100)
    reason: Optional[str] = Field(None, max_length=200)


def _resolve_pending_moderations(db: Session, post_id: int, user: SysUser, note: str) -> None:
    """把该帖所有 PENDING 复核记录标记为已驳回，避免「已取消隐藏却还在队列里」。"""
    pending = (
        db.query(ForumModeration)
        .filter(
            ForumModeration.target_type == "POST",
            ForumModeration.target_id == post_id,
            ForumModeration.status == "PENDING",
        )
        .all()
    )
    for record in pending:
        record.status = "REJECTED"
        record.reviewed_by = user.user_id
        record.reviewed_at = datetime.now()
        record.review_note = note


def _admin_hide_post(db: Session, post: ForumPost, user: SysUser, reason: Optional[str]) -> None:
    post.status = "BLOCKED"
    post.deleted_by = user.user_id
    post.deleted_reason = reason
    post.deleted_at = datetime.now()
    db.add(
        ForumModeration(
            target_type="POST",
            target_id=post.post_id,
            action="ADMIN_HIDE",
            reason=reason,
            actor_id=user.user_id,
            status="APPROVED",
            reviewed_by=user.user_id,
            reviewed_at=datetime.now(),
        )
    )
    _audit(db, user, "管理员隐藏帖子", f"post_id={post.post_id} reason={reason or ''}")


def _admin_unhide_post(db: Session, post: ForumPost, user: SysUser) -> None:
    post.status = "NORMAL"
    post.deleted_by = None
    post.deleted_reason = None
    post.deleted_at = None
    _resolve_pending_moderations(db, post.post_id, user, "管理员取消隐藏")
    _audit(db, user, "管理员取消隐藏帖子", f"post_id={post.post_id}")


def _admin_soft_delete_post(db: Session, post: ForumPost, user: SysUser, reason: Optional[str]) -> None:
    post.status = "DELETED"
    post.deleted_by = user.user_id
    post.deleted_reason = reason
    post.deleted_at = datetime.now()
    db.add(
        ForumModeration(
            target_type="POST",
            target_id=post.post_id,
            action="ADMIN_DELETE",
            reason=reason,
            actor_id=user.user_id,
            status="APPROVED",
            reviewed_by=user.user_id,
            reviewed_at=datetime.now(),
        )
    )
    _audit(db, user, "管理员删除帖子", f"post_id={post.post_id} reason={reason or ''}")


def _admin_restore_post(db: Session, post: ForumPost, user: SysUser) -> None:
    post.status = "NORMAL"
    post.deleted_by = None
    post.deleted_reason = None
    post.deleted_at = None
    _resolve_pending_moderations(db, post.post_id, user, "管理员恢复帖子")
    _audit(db, user, "恢复帖子", f"post_id={post.post_id}")


def _admin_purge_post(db: Session, post: ForumPost, user: SysUser) -> None:
    db.query(ForumComment).filter(ForumComment.post_id == post.post_id).delete()
    db.delete(post)
    _audit(db, user, "彻底删除帖子", f"post_id={post.post_id}")


def _apply_post_action(
    db: Session,
    action: str,
    post: ForumPost,
    user: SysUser,
    reason: Optional[str],
    *,
    single: bool,
) -> None:
    """按 action 分派。single=True 时复用既有单条接口的语义。"""
    if action == "hide":
        _admin_hide_post(db, post, user, reason)
    elif action == "unhide":
        _admin_unhide_post(db, post, user)
    elif action == "delete":
        _admin_soft_delete_post(db, post, user, reason)
    elif action == "restore":
        _admin_restore_post(db, post, user)
    elif action == "purge":
        if user.role_level < 3:
            raise HTTPException(status_code=403, detail="仅超级管理员可彻底删除")
        _admin_purge_post(db, post, user)
    else:  # pragma: no cover - 由 pydantic 正则保证
        raise HTTPException(status_code=422, detail=f"不支持的操作: {action}")
    if single:
        db.commit()


@admin_router.post("/posts/{post_id}/hide", summary="管理员隐藏帖子")
async def admin_hide_post(
    post_id: int,
    reason: Optional[str] = Query(None, max_length=200),
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    post = db.query(ForumPost).filter(ForumPost.post_id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    _apply_post_action(db, "hide", post, current_user, reason, single=True)
    return {"success": True, "status": "BLOCKED"}


@admin_router.post("/posts/{post_id}/unhide", summary="管理员取消隐藏帖子")
async def admin_unhide_post(
    post_id: int,
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    post = db.query(ForumPost).filter(ForumPost.post_id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    _apply_post_action(db, "unhide", post, current_user, None, single=True)
    return {"success": True, "status": "NORMAL"}


@admin_router.post("/posts/batch", summary="管理员批量操作帖子")
async def admin_batch_posts(
    payload: BatchActionPayload,
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """逐条执行，单条失败只跳过，不中断整批；返回 affected/skipped 供前端提示。"""
    if payload.action == "purge" and current_user.role_level < 3:
        raise HTTPException(status_code=403, detail="仅超级管理员可彻底删除")

    affected = 0
    skipped: List[int] = []
    for post_id in payload.ids:
        post = db.query(ForumPost).filter(ForumPost.post_id == post_id).first()
        if not post:
            skipped.append(post_id)
            continue
        try:
            _apply_post_action(
                db, payload.action, post, current_user, payload.reason, single=False
            )
            affected += 1
        except HTTPException:
            db.rollback()
            skipped.append(post_id)
    db.commit()
    return {"success": True, "affected": affected, "skipped": skipped}


class PinPayload(BaseModel):
    pinned: bool = True


@admin_router.post("/posts/{post_id}/pin", summary="管理员置顶/取消置顶帖子")
async def admin_pin_post(
    post_id: int,
    payload: PinPayload,
    current_user: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    post = db.query(ForumPost).filter(ForumPost.post_id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="帖子不存在")
    post.is_top = 1 if payload.pinned else 0
    _audit(
        db,
        current_user,
        "管理员置顶帖子" if payload.pinned else "管理员取消置顶帖子",
        f"post_id={post_id}",
    )
    db.commit()
    return {"success": True, "isTop": bool(post.is_top)}


# =====================================================================
# 管理员端论坛数据看板（P3b）
#
# 口径说明（避免「看起来对」）：
#   - 趋势 / 班级 / 关键词：按 forum_post.create_time 落在窗口内统计，含已被隐藏/删除的帖子
#     （管理端要看的是「发生过什么」，不是「现在还剩什么」）；
#   - 违规处理量：按 forum_moderation.created_at 的 ISO 周聚合，删除与隐藏分线；
#   - 科目热度：帖子标题/正文里命中科目关键词的条数（帖子没有科目外键，这是可解释的近似口径）；
#   - 关键词：jieba 分词 + 停用词 + 纯中文且长度 ≥2，取 TOP N。
# =====================================================================

_SUBJECT_KEYWORDS = {
    "行测": ["行测", "行政职业能力", "言语理解", "数量关系", "判断推理", "资料分析", "常识判断"],
    "申论": ["申论", "大作文", "归纳概括", "综合分析", "贯彻执行"],
    "公安专业科目": ["公安专业", "公专", "执法", "警务", "治安", "刑侦"],
    "面试": ["面试", "结构化", "无领导"],
}

_KEYWORD_STOPWORDS = {
    "我们", "你们", "他们", "自己", "大家", "什么", "怎么", "可以", "这个", "那个",
    "一下", "已经", "还是", "就是", "没有", "不是", "因为", "所以", "但是", "而且",
    "如果", "然后", "现在", "今天", "昨天", "明天", "一个", "一些", "东西", "问题",
    "帖子", "内容", "分享", "求助", "请问", "谢谢", "感觉", "觉得", "真的", "非常",
    # 结构性噪声：不是话题词，只是空标题占位与测试痕迹
    "无标题", "测试",
}

_CHINESE_WORD = re.compile(r"^[\u4e00-\u9fa5]{2,}$")


def _top_keywords(texts: List[str], limit: int = 22) -> List[Dict[str, Any]]:
    """jieba 分词取高频中文词。jieba 首次加载会读词典（约数百毫秒），故按需导入。"""
    import jieba  # 延迟导入：只有看板接口需要

    counter: Counter = Counter()
    for text in texts:
        if not text:
            continue
        for word in jieba.lcut(text):
            word = word.strip()
            if len(word) < 2 or word in _KEYWORD_STOPWORDS:
                continue
            if not _CHINESE_WORD.match(word):
                continue
            counter[word] += 1
    return [{"word": w, "count": c} for w, c in counter.most_common(limit)]


def _subject_heat(texts: List[str]) -> List[Dict[str, Any]]:
    """按科目关键词命中条数计算讨论量指数（占比归一化到 100）。"""
    counts = {name: 0 for name in _SUBJECT_KEYWORDS}
    for text in texts:
        if not text:
            continue
        for name, words in _SUBJECT_KEYWORDS.items():
            if any(word in text for word in words):
                counts[name] += 1
    total = sum(counts.values()) or 1
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [
        {"name": name, "value": value, "ratio": round(value / total * 100)}
        for name, value in ordered
    ]


def _delta_pct(current: int, previous: int) -> Optional[int]:
    """环比百分比；上期为 0 时返回 None（前端显示「—」，不编造无穷增长）。"""
    if previous <= 0:
        return None
    return round((current - previous) / previous * 100)


@admin_router.post("/ai-titles/backfill", summary="为无标题帖批量生成 AI 标题")
async def backfill_ai_titles(
    limit: int = Query(5, ge=1, le=20, description="本次最多处理多少条，控制 token 成本"),
    dry_run: bool = Query(False, description="只统计候选，不调用模型"),
    _: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """给存量「无标题 + 有正文」的帖子补 AI 标题（2026-11-03 第 3 轮）。

    为什么手动触发而不是自动/定时：大模型按调用计费，自动跑会让成本脱离管理员视线。
    只填空标题，已有标题绝不动；单条失败不影响其它帖子。
    """
    from ....services.forum_title_ai import (
        clean_title,
        generate_forum_title,
        needs_ai_title,
    )

    rows = (
        db.query(ForumPost)
        .filter(ForumPost.status == "NORMAL")
        .order_by(ForumPost.create_time.desc())
        .limit(200)
        .all()
    )
    candidates = [p for p in rows if needs_ai_title(p.title, p.content)]

    stats = {
        "candidates": len(candidates),
        "processed": 0,
        "generated": 0,
        "skipped": 0,
        "errors": 0,
        "dryRun": dry_run,
    }
    if dry_run:
        return {"success": True, **stats}

    for post in candidates[:limit]:
        stats["processed"] += 1
        try:
            title = clean_title(await generate_forum_title(post.content, post.content_format or "TEXT"))
        except Exception:  # noqa: BLE001 - 单条失败不影响其它
            stats["errors"] += 1
            continue

        if not title or title == "无标题":
            stats["skipped"] += 1
            continue

        # 再校验一次：避免并发下把用户刚填的标题覆盖掉
        fresh = db.query(ForumPost).filter(ForumPost.post_id == post.post_id).first()
        if not fresh or not needs_ai_title(fresh.title, fresh.content):
            stats["skipped"] += 1
            continue

        fresh.title = title
        fresh.ai_title = 1
        stats["generated"] += 1

    db.commit()
    return {"success": True, **stats}


@admin_router.get("/dashboard", summary="管理员端论坛数据看板")
async def admin_dashboard(
    days: int = Query(7, ge=1, le=180, description="统计窗口天数：7 / 30 / 180"),
    _: SysUser = Depends(require_admin),
    db: Session = Depends(get_db),
):
    now = datetime.now()
    today = datetime(now.year, now.month, now.day)
    start = today - timedelta(days=days - 1)
    prev_start = start - timedelta(days=days)

    posts = db.query(ForumPost).filter(ForumPost.create_time >= start).all()
    comments = db.query(ForumComment).filter(ForumComment.create_time >= start).all()
    prev_posts = (
        db.query(ForumPost)
        .filter(ForumPost.create_time >= prev_start, ForumPost.create_time < start)
        .count()
    )
    prev_comments = (
        db.query(ForumComment)
        .filter(ForumComment.create_time >= prev_start, ForumComment.create_time < start)
        .count()
    )

    pending_records = db.query(ForumModeration).filter(ForumModeration.status == "PENDING").all()
    stale_before = now - timedelta(days=7)
    stale_pending = [r for r in pending_records if r.created_at and r.created_at < stale_before]

    hidden_posts = [p for p in posts if p.status == "BLOCKED"]
    deleted_posts = [p for p in posts if p.status == "DELETED"]

    # ---- 趋势：逐日发帖/评论 ----
    labels: List[str] = []
    day_keys: List[str] = []
    for i in range(days):
        d = start + timedelta(days=i)
        labels.append(d.strftime("%m-%d"))
        day_keys.append(d.strftime("%Y-%m-%d"))
    bucket = {key: {"posts": 0, "comments": 0} for key in day_keys}
    for p in posts:
        key = p.create_time.strftime("%Y-%m-%d") if p.create_time else None
        if key in bucket:
            bucket[key]["posts"] += 1
    for c in comments:
        key = c.create_time.strftime("%Y-%m-%d") if c.create_time else None
        if key in bucket:
            bucket[key]["comments"] += 1

    # ---- 班级分布（TOP 6 + 其他）----
    class_ids = {p.user_id for p in posts}
    users = db.query(SysUser).filter(SysUser.user_id.in_(class_ids)).all() if class_ids else []
    class_map = {u.user_id: (u.class_name or "未分班") for u in users}
    class_counter: Counter = Counter(class_map.get(p.user_id, "未分班") for p in posts)
    class_top = class_counter.most_common(6)
    classes = [{"name": name, "value": value} for name, value in class_top]
    rest = sum(class_counter.values()) - sum(v for _, v in class_top)
    if rest > 0:
        classes.append({"name": "其他", "value": rest})

    # ---- 关键词 / 科目热度 ----
    texts = [f"{p.title or ''} {p.content or ''}" for p in posts]
    keywords = _top_keywords(texts)
    subjects = _subject_heat(texts)

    # ---- 违规处理量：近 8 个 ISO 周 ----
    week_labels: List[str] = []
    week_keys: List[str] = []
    for i in range(7, -1, -1):
        d = today - timedelta(weeks=i)
        iso = d.isocalendar()
        week_labels.append(f"W{iso[1]:02d}")
        week_keys.append(f"{iso[0]}-{iso[1]:02d}")
    week_bucket = {key: {"deleted": 0, "hidden": 0} for key in week_keys}
    moderation_rows = (
        db.query(ForumModeration)
        .filter(ForumModeration.created_at >= today - timedelta(weeks=8))
        .all()
    )
    for row in moderation_rows:
        if not row.created_at:
            continue
        iso = row.created_at.isocalendar()
        key = f"{iso[0]}-{iso[1]:02d}"
        if key not in week_bucket:
            continue
        if row.action in ("ADMIN_DELETE", "TEACHER_HIDE"):
            week_bucket[key]["deleted" if row.action == "ADMIN_DELETE" else "hidden"] += 1
        elif row.action == "ADMIN_HIDE":
            week_bucket[key]["hidden"] += 1

    # ---- 风险提示（全部由真实计数推导，不写死文案）----
    risks: List[Dict[str, Any]] = []
    if stale_pending:
        risks.append(
            {
                "level": "high",
                "text": f"{len(stale_pending)} 条教师隐藏内容超过 7 天未复核",
                "count": len(stale_pending),
                "tab": "review",
            }
        )
    if hidden_posts:
        risks.append(
            {
                "level": "mid",
                "text": f"窗口内有 {len(hidden_posts)} 篇帖子处于隐藏状态",
                "count": len(hidden_posts),
                "tab": "trash",
            }
        )
    if deleted_posts:
        risks.append(
            {
                "level": "mid",
                "text": f"窗口内有 {len(deleted_posts)} 篇帖子被删除（回收站可恢复）",
                "count": len(deleted_posts),
                "tab": "trash",
            }
        )
    if keywords and keywords[0]["count"] >= 3:
        risks.append(
            {
                "level": "low",
                "text": f"高频词「{keywords[0]['word']}」出现 {keywords[0]['count']} 次，建议关注话题集中度",
                "count": keywords[0]["count"],
                "tab": "list",
            }
        )
    if not risks:
        risks.append({"level": "low", "text": "窗口内未发现需要人工介入的异常", "count": 0, "tab": "list"})

    return {
        "range": {"days": days, "from": start.strftime("%Y-%m-%d"), "to": now.strftime("%Y-%m-%d")},
        "kpi": {
            "posts": len(posts),
            "postsDelta": _delta_pct(len(posts), prev_posts),
            "comments": len(comments),
            "commentsDelta": _delta_pct(len(comments), prev_comments),
            "pending": len(pending_records),
            "hidden": len(hidden_posts),
            "deleted": len(deleted_posts),
            "classes": len([c for c in class_counter if c != "未分班"]),
        },
        "trend": {
            "labels": labels,
            "posts": [bucket[k]["posts"] for k in day_keys],
            "comments": [bucket[k]["comments"] for k in day_keys],
        },
        "classes": classes,
        "keywords": keywords,
        "subjects": subjects,
        "violations": {
            "labels": week_labels,
            "deleted": [week_bucket[k]["deleted"] for k in week_keys],
            "hidden": [week_bucket[k]["hidden"] for k in week_keys],
        },
        "risks": risks,
    }
