"""
论坛 API - 论坛模块完善版
关键词工程:发帖/评论前 DFA 敏感词检测 + 审计日志

接口清单(共 12 个):
  GET    /api/forum/posts                    帖子列表(含 user 信息)
  GET    /api/forum/posts/{post_id}          帖子详情
  POST   /api/forum/posts                    发帖(关键词过滤 + 附件)
  DELETE /api/forum/posts/{post_id}          删除帖子(本人或管理员)
  POST   /api/forum/posts/{post_id}/like     帖子点赞切换
  GET    /api/forum/posts/{post_id}/comments 评论列表
  POST   /api/forum/posts/{post_id}/comments 发评论(关键词过滤)
  POST   /api/forum/comments/{comment_id}/like 评论点赞切换
  POST   /api/forum/upload                   上传学习资料附件
  GET    /api/forum/users/{user_id}/public   用户公开信息
  GET    /api/forum/my-posts                 我的帖子(需登录)
  GET    /api/forum/stats                    论坛统计
"""
import os
import json
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from ...core.database import get_db
from ...core.config import settings
from ...core.security import get_current_user, get_optional_user
from ...models.models import (
    ForumPost, ForumComment, ForumLike, SysUser, SysOperationLog
)
from ...services.sensitive_words import sensitive_filter, SensitiveLevel
from ...core.exceptions import BusinessLogicError, ValidationError, ResourceNotFoundError

router = APIRouter(prefix="/api/forum", tags=["论坛"])
logger = logging.getLogger(__name__)


# ============================== 辅助函数 ==============================

def _serialize_post(
    post: ForumPost,
    user: Optional[SysUser] = None,
    liked: bool = False,
    content_full: bool = False
) -> Dict[str, Any]:
    """序列化帖子为响应字典"""
    return {
        "id": post.post_id,
        "title": post.title,
        "content": post.content if content_full else (
            (post.content[:200] + "...") if (post.content or "") and len(post.content) > 200 else post.content
        ),
        "shareType": post.share_type,
        "tags": post.tags.split(",") if post.tags else [],
        "attachments": post.attachments or [],
        "isTop": bool(post.is_top),
        "isEssence": bool(post.is_essence),
        "likeCount": post.like_count or 0,
        "commentCount": post.comment_count or 0,
        "viewCount": post.view_count or 0,
        "createTime": post.create_time.isoformat() if post.create_time else None,
        "userId": post.user_id,
        "liked": liked,
        "user": {
            "id": user.user_id if user else None,
            "nickname": user.username if user else "匿名",
            "avatar": user.avatar if user and user.avatar else "",
            "userType": user.user_type if user else "student",
        } if user else {
            "id": post.user_id,
            "nickname": "匿名",
            "avatar": "",
            "userType": "student",
        },
    }


def _serialize_comment(
    comment: ForumComment,
    user: Optional[SysUser] = None,
    liked: bool = False
) -> Dict[str, Any]:
    """序列化评论为响应字典"""
    return {
        "id": comment.comment_id,
        "content": comment.content,
        "likeCount": comment.like_count or 0,
        "createTime": comment.create_time.isoformat() if comment.create_time else None,
        "parentCommentId": comment.parent_comment_id,
        "liked": liked,
        "user": {
            "id": user.user_id if user else None,
            "nickname": user.username if user else "匿名",
            "avatar": user.avatar if user and user.avatar else "",
            "userType": user.user_type if user else "student",
        } if user else {
            "id": comment.user_id,
            "nickname": "匿名",
            "avatar": "",
            "userType": "student",
        },
    }


def _log_violation(
    db: Session,
    user_id: int,
    request: Request,
    filter_result: Dict,
    action: str,
    content_snippet: str
) -> None:
    """记录敏感词违规审计日志(只存前 100 字,保护隐私)"""
    try:
        log = SysOperationLog(
            user_id=user_id,
            user_name="",
            operation_type="敏感词拦截",
            module_name="论坛",
            operation_desc=f"敏感词触发 等级={filter_result.get('level')} 动作={action} 命中词={','.join(filter_result.get('words', []))}",
            request_method=request.method if request else "POST",
            request_url=str(request.url) if request else "",
            request_params=content_snippet[:100],
            response_result=action,
            ip_address=request.client.host if request and request.client else "",
            operation_time=datetime.now(),
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"记录违规日志失败: {e}")
        db.rollback()


# ============================== 帖子接口 ==============================

@router.get("/posts", summary="获取论坛帖子列表")
async def get_forum_posts(
    share_type: Optional[str] = Query(None, description="分享类型: EXPERIENCE/RESOURCE/DISCUSSION/FEELING"),
    limit: int = Query(20, ge=1, le=50, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    获取论坛帖子列表(公开访问)
    - 支持按 share_type 筛选
    - 批量查询 user 信息(避免 N+1)
    - 返回当前用户点赞状态
    """
    query = db.query(ForumPost).filter(ForumPost.status == "NORMAL")

    if share_type:
        query = query.filter(ForumPost.share_type == share_type)

    total = query.count()
    posts = query.order_by(
        ForumPost.is_top.desc(),
        ForumPost.create_time.desc()
    ).offset(offset).limit(limit).all()

    if not posts:
        return {"total": total, "limit": limit, "offset": offset, "posts": []}

    # 批量查询 user 信息
    user_ids = list({p.user_id for p in posts})
    users = db.query(SysUser).filter(SysUser.user_id.in_(user_ids)).all()
    user_map = {u.user_id: u for u in users}

    # 批量查询当前用户的点赞状态
    liked_post_ids: set = set()
    if current_user:
        liked_post_ids = {
            row[0] for row in db.query(ForumLike.post_id).filter(
                ForumLike.post_id.in_([p.post_id for p in posts]),
                ForumLike.user_id == current_user.user_id
            ).all()
        }

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "posts": [
            _serialize_post(p, user_map.get(p.user_id), p.post_id in liked_post_ids)
            for p in posts
        ]
    }


@router.get("/posts/{post_id}", summary="获取帖子详情")
async def get_post_detail(
    post_id: int,
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取帖子详情(含完整 content + 附件),并增加浏览量"""
    post = db.query(ForumPost).filter(
        ForumPost.post_id == post_id,
        ForumPost.status == "NORMAL"
    ).first()
    if not post:
        raise ResourceNotFoundError("帖子", post_id)

    # 浏览量 +1(原子操作,即使失败也不影响读取)
    try:
        post.view_count = (post.view_count or 0) + 1
        db.commit()
        db.refresh(post)
    except Exception as e:
        logger.warning(f"浏览量更新失败: {e}")
        db.rollback()

    user = db.query(SysUser).filter(SysUser.user_id == post.user_id).first()
    liked = False
    if current_user:
        liked = db.query(ForumLike).filter(
            ForumLike.post_id == post_id,
            ForumLike.user_id == current_user.user_id
        ).first() is not None

    return _serialize_post(post, user, liked, content_full=True)


@router.post("/posts", summary="发布新帖")
async def create_post(
    request: Request,
    title: str = Form(..., max_length=200),
    content: str = Form(..., max_length=10000),
    share_type: str = Form("EXPERIENCE"),
    tags: Optional[str] = Form(None),
    attachments: Optional[str] = Form(None, description="附件列表 JSON 字符串"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    发布新帖
    - 必须登录
    - 关键词过滤:blocked 直接拒绝,masked 自动屏蔽后发布
    - 支持附件(attachments 为 JSON 字符串)
    """
    # 1. 关键词过滤(关键词工程核心)
    filter_result = sensitive_filter.detect(f"{title} {content}")

    if filter_result["level"] == SensitiveLevel.BLOCKED:
        # 记录审计日志
        _log_violation(db, current_user.user_id, request, filter_result, "rejected", f"{title} {content}")
        raise BusinessLogicError(
            message=f"内容包含违规词: {','.join(filter_result['words'])}, 请修改后发布",
            code="SENSITIVE_CONTENT_BLOCKED"
        )

    # masked 级别:自动屏蔽后发布
    final_content = content
    if filter_result["level"] == SensitiveLevel.MASKED:
        final_content = filter_result["masked_text"]
        _log_violation(db, current_user.user_id, request, filter_result, "masked", f"{title} {content}")

    # reviewed 级别:记录但不阻断
    if filter_result["level"] == SensitiveLevel.REVIEWED:
        _log_violation(db, current_user.user_id, request, filter_result, "reviewed", f"{title} {content}")

    # 2. 解析附件
    parsed_attachments = None
    if attachments:
        try:
            parsed_attachments = json.loads(attachments)
            if not isinstance(parsed_attachments, list):
                raise ValueError("attachments 必须是数组")
        except (json.JSONDecodeError, ValueError) as e:
            raise ValidationError(f"附件格式错误: {e}")

    # 3. 创建帖子
    post = ForumPost(
        user_id=current_user.user_id,
        title=title.strip(),
        content=final_content,
        share_type=share_type if share_type in ("EXPERIENCE", "RESOURCE", "DISCUSSION", "FEELING") else "EXPERIENCE",
        tags=tags,
        attachments=parsed_attachments,
        status="NORMAL",
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    logger.info(f"用户 {current_user.user_id} 发布帖子 {post.post_id}")

    # 触发社交成就
    try:
        from ...services import achievement_service
        achievement_service.check_and_grant(current_user.user_id, "post", db)
    except Exception as e:
        logger.warning(f"发帖成就判定失败: {e}")

    # 4. 返回完整数据(前端 unshift 到列表头)
    return _serialize_post(post, current_user, liked=False, content_full=True)


@router.delete("/posts/{post_id}", summary="删除帖子")
async def delete_post(
    post_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    删除帖子(软删除)
    - 本人可删自己的帖子
    - 管理员(role_level >= 2)可删任何帖子
    """
    post = db.query(ForumPost).filter(ForumPost.post_id == post_id).first()
    if not post:
        raise ResourceNotFoundError("帖子", post_id)

    # 权限校验:本人或管理员
    is_owner = post.user_id == current_user.user_id
    is_admin = current_user.role_level >= 2
    if not is_owner and not is_admin:
        raise BusinessLogicError("无权删除他人帖子", code="PERMISSION_DENIED")

    # 软删除
    post.status = "DELETED"
    db.commit()

    logger.info(f"用户 {current_user.user_id} 删除帖子 {post_id} (is_admin={is_admin})")
    return {"success": True, "message": "删除成功"}


@router.post("/posts/{post_id}/like", summary="帖子点赞切换")
async def toggle_post_like(
    post_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    帖子点赞切换(已赞则取消,未赞则点赞)
    - 利用 forum_like 表唯一约束 uk_post_user_like 防止重复点赞
    """
    post = db.query(ForumPost).filter(
        ForumPost.post_id == post_id,
        ForumPost.status == "NORMAL"
    ).first()
    if not post:
        raise ResourceNotFoundError("帖子", post_id)

    existing = db.query(ForumLike).filter(
        ForumLike.post_id == post_id,
        ForumLike.user_id == current_user.user_id
    ).first()

    if existing:
        # 已赞 → 取消
        db.delete(existing)
        post.like_count = max(0, (post.like_count or 0) - 1)
        liked = False
    else:
        # 未赞 → 点赞
        db.add(ForumLike(
            post_id=post_id,
            user_id=current_user.user_id,
        ))
        post.like_count = (post.like_count or 0) + 1
        liked = True

    db.commit()

    # 触发社交成就（被点赞者：获赞/热门楼主）
    try:
        from ...services import achievement_service
        achievement_service.check_and_grant(post.user_id, "post", db)
    except Exception as e:
        logger.warning(f"点赞成就判定失败: {e}")

    return {"liked": liked, "likeCount": post.like_count}


# ============================== 评论接口 ==============================

@router.get("/posts/{post_id}/comments", summary="获取帖子评论列表")
async def get_post_comments(
    post_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取帖子评论列表(分页,仅返回 status=1 的评论)"""
    post = db.query(ForumPost).filter(ForumPost.post_id == post_id).first()
    if not post:
        raise ResourceNotFoundError("帖子", post_id)

    query = db.query(ForumComment).filter(
        ForumComment.post_id == post_id,
        ForumComment.status == 1
    )
    total = query.count()
    comments = query.order_by(ForumComment.create_time.asc()).offset(offset).limit(limit).all()

    if not comments:
        return {"total": total, "limit": limit, "offset": offset, "comments": []}

    # 批量查询 user 信息
    user_ids = list({c.user_id for c in comments})
    users = db.query(SysUser).filter(SysUser.user_id.in_(user_ids)).all()
    user_map = {u.user_id: u for u in users}

    # 批量查询当前用户对评论的点赞状态
    liked_comment_ids: set = set()
    if current_user:
        liked_comment_ids = {
            row[0] for row in db.query(ForumLike.comment_id).filter(
                ForumLike.comment_id.in_([c.comment_id for c in comments]),
                ForumLike.user_id == current_user.user_id
            ).all()
        }

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "comments": [
            _serialize_comment(c, user_map.get(c.user_id), c.comment_id in liked_comment_ids)
            for c in comments
        ]
    }


@router.post("/posts/{post_id}/comments", summary="发表评论")
async def create_comment(
    post_id: int,
    request: Request,
    content: str = Form(..., max_length=2000),
    parent_comment_id: Optional[int] = Form(None),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    发表评论
    - 必须登录
    - 关键词过滤(同发帖逻辑)
    - 支持楼中楼回复(parent_comment_id)
    """
    post = db.query(ForumPost).filter(
        ForumPost.post_id == post_id,
        ForumPost.status == "NORMAL"
    ).first()
    if not post:
        raise ResourceNotFoundError("帖子", post_id)

    # 校验父评论是否存在且属于同一帖子
    if parent_comment_id:
        parent = db.query(ForumComment).filter(
            ForumComment.comment_id == parent_comment_id,
            ForumComment.post_id == post_id
        ).first()
        if not parent:
            raise ValidationError("父评论不存在或不属于该帖子")

    # 关键词过滤
    filter_result = sensitive_filter.detect(content)
    if filter_result["level"] == SensitiveLevel.BLOCKED:
        _log_violation(db, current_user.user_id, request, filter_result, "rejected", content)
        raise BusinessLogicError(
            message=f"评论包含违规词: {','.join(filter_result['words'])}, 请修改后发布",
            code="SENSITIVE_CONTENT_BLOCKED"
        )

    final_content = content
    if filter_result["level"] == SensitiveLevel.MASKED:
        final_content = filter_result["masked_text"]
        _log_violation(db, current_user.user_id, request, filter_result, "masked", content)
    elif filter_result["level"] == SensitiveLevel.REVIEWED:
        _log_violation(db, current_user.user_id, request, filter_result, "reviewed", content)

    # 创建评论
    comment = ForumComment(
        post_id=post_id,
        user_id=current_user.user_id,
        parent_comment_id=parent_comment_id,
        content=final_content,
        status=1,
    )
    db.add(comment)

    # 帖子评论数 +1
    post.comment_count = (post.comment_count or 0) + 1

    db.commit()
    db.refresh(comment)

    # 触发社交成就（评论计数）
    try:
        from ...services import achievement_service
        achievement_service.check_and_grant(current_user.user_id, "post", db)
    except Exception as e:
        logger.warning(f"评论成就判定失败: {e}")

    return _serialize_comment(comment, current_user, liked=False)


@router.post("/comments/{comment_id}/like", summary="评论点赞切换")
async def toggle_comment_like(
    comment_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """评论点赞切换"""
    comment = db.query(ForumComment).filter(
        ForumComment.comment_id == comment_id,
        ForumComment.status == 1
    ).first()
    if not comment:
        raise ResourceNotFoundError("评论", comment_id)

    existing = db.query(ForumLike).filter(
        ForumLike.comment_id == comment_id,
        ForumLike.user_id == current_user.user_id
    ).first()

    if existing:
        db.delete(existing)
        comment.like_count = max(0, (comment.like_count or 0) - 1)
        liked = False
    else:
        db.add(ForumLike(
            comment_id=comment_id,
            user_id=current_user.user_id,
        ))
        comment.like_count = (comment.like_count or 0) + 1
        liked = True

    db.commit()

    # 触发社交成就（被点赞的评论作者）
    try:
        from ...services import achievement_service
        achievement_service.check_and_grant(comment.user_id, "post", db)
    except Exception as e:
        logger.warning(f"评论点赞成就判定失败: {e}")

    return {"liked": liked, "likeCount": comment.like_count}


# ============================== 文件上传 ==============================

@router.post("/upload", summary="上传学习资料附件")
async def upload_attachment(
    file: UploadFile = File(...),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    上传学习资料附件(Word/PDF/Excel)
    - 白名单扩展名 + MIME 校验
    - 大小限制 20MB
    - UUID 重命名 + 独立目录 uploads/forum/
    """
    # 1. 白名单校验(扩展名 + MIME 双重校验)
    ALLOWED_EXT = {".doc", ".docx", ".pdf", ".xls", ".xlsx"}
    ALLOWED_MIME = {
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/pdf",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    original_name = file.filename or ""
    ext = os.path.splitext(original_name)[1].lower()

    if ext not in ALLOWED_EXT:
        raise ValidationError(f"仅支持 Word/PDF/Excel 文件, 不允许 {ext} 格式")

    if file.content_type not in ALLOWED_MIME:
        raise ValidationError(f"文件 MIME 类型不合法: {file.content_type}")

    # 2. 大小校验(< 20MB)
    MAX_SIZE = 20 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise ValidationError("文件大小不能超过 20MB")

    # 3. 安全存储(UUID 重命名)
    filename = f"{uuid.uuid4().hex}{ext}"
    save_dir = os.path.join(settings.UPLOAD_DIR, "forum")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, filename)

    with open(save_path, "wb") as f:
        f.write(contents)

    logger.info(f"用户 {current_user.user_id} 上传附件 {original_name} → {filename}")

    return {
        "name": original_name,
        "url": f"/uploads/forum/{filename}",
        "size": len(contents),
        "type": ext.lstrip(".")
    }


# ============================== 用户公开信息 ==============================

@router.get("/users/{user_id}/public", summary="获取用户公开信息")
async def get_user_public(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    获取用户公开信息(点击头像调用)
    - 不含敏感信息(邮箱/手机号/身份证等)
    - 聚合查询发帖数和获赞数
    """
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user:
        raise ResourceNotFoundError("用户", user_id)

    # 聚合查询:发帖数
    post_count = db.query(func.count(ForumPost.post_id)).filter(
        ForumPost.user_id == user_id,
        ForumPost.status == "NORMAL"
    ).scalar() or 0

    # 聚合查询:获赞数(帖子点赞 + 评论点赞)
    post_like_count = db.query(func.count(ForumLike.like_id)).join(
        ForumPost, ForumLike.post_id == ForumPost.post_id
    ).filter(ForumPost.user_id == user_id).scalar() or 0

    comment_like_count = db.query(func.count(ForumLike.like_id)).join(
        ForumComment, ForumLike.comment_id == ForumComment.comment_id
    ).filter(ForumComment.user_id == user_id).scalar() or 0

    return {
        "id": user.user_id,
        "nickname": user.username,
        "avatar": user.avatar or "",
        "userType": user.user_type,
        "school": user.school,
        "department": user.department,
        "className": user.class_name,
        "createdAt": user.register_time.isoformat() if user.register_time else None,
        "postCount": post_count,
        "likeReceived": post_like_count + comment_like_count,
    }


# ============================== 我的帖子 ==============================

@router.get("/my-posts", summary="获取我的帖子")
async def get_my_posts(
    limit: int = Query(20, ge=1, le=50, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    获取当前登录用户的所有帖子
    - 必须登录
    - 按时间倒序排列
    """
    query = db.query(ForumPost).filter(
        ForumPost.user_id == current_user.user_id,
        ForumPost.status == "NORMAL"
    )
    total = query.count()
    posts = query.order_by(ForumPost.create_time.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "posts": [_serialize_post(p, current_user, False) for p in posts]
    }


# ============================== 论坛统计 ==============================

@router.get("/stats", summary="论坛统计数据")
async def get_forum_stats(
    db: Session = Depends(get_db)
):
    """
    论坛统计数据(右下角活跃展示)
    - 帖子总数
    - 用户总数(有过发帖行为的)
    - 在线数(简化:最近 5 分钟活跃用户,此处用总用户数替代,前端可定期刷新)
    """
    posts_total = db.query(func.count(ForumPost.post_id)).filter(
        ForumPost.status == "NORMAL"
    ).scalar() or 0

    users_total = db.query(func.count(func.distinct(ForumPost.user_id))).filter(
        ForumPost.status == "NORMAL"
    ).scalar() or 0

    # 在线数简化处理:返回总注册用户数(实际在线需 WebSocket,本期不做)
    total_users = db.query(func.count(SysUser.user_id)).filter(
        SysUser.status == 1
    ).scalar() or 0

    return {
        "posts": posts_total,
        "users": users_total,
        "online": total_users,
    }
