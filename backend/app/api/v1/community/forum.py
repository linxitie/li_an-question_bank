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
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Literal

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, Request
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func, or_, and_, String

from ....core.database import get_db
from ....core.config import settings
from ....core.security import get_current_user, get_optional_user
from ....models.models import (
    ForumPost, ForumComment, ForumLike, ForumFavorite, ForumSticker, ForumReport,
    SysUser, SysOperationLog
)
from ....services.sensitive_words import sensitive_filter, SensitiveLevel
from ....services.event_consumer import record_user_action
from ....core.trigger_types import TRIGGER_FORUM_POSTED
from ....core.exceptions import (
    BusinessLogicError,
    DuplicateResourceError,
    ValidationError,
    ResourceNotFoundError,
)

router = APIRouter(prefix="/api/forum", tags=["论坛"])

TITLE_COLORS = {"default", "red", "gold", "blue", "green", "purple"}
logger = logging.getLogger(__name__)

# 点赞表情白名单：只接受固定码，避免任意文本/图片进入
REACTION_CODES = ("like", "love", "haha", "wow", "sad", "angry")


# ============================== 辅助函数 ==============================

# === E6 发帖事件去重（P2-28） ===
# 统一上报 forum.posted，且按 post id 幂等：同一帖子的创建/回复/重复上报
# 只计一次。仅发帖创建与回帖尝试上报（回复在帖子已上报后被去重），
# 点赞/删除等只读或非创建行为一律不上报。
_FORUM_POSTED_EVENT_IDS: "OrderedDict[int, None]" = OrderedDict()
_FORUM_POSTED_EVENT_LIMIT = 4096


def reset_forum_posted_events() -> None:
    """清空 E6 去重缓存（测试隔离用）。"""
    _FORUM_POSTED_EVENT_IDS.clear()


def _claim_forum_posted_event(post_id: int) -> bool:
    """抢占该帖子的 forum.posted 上报资格；已上报过返回 False。"""
    if post_id in _FORUM_POSTED_EVENT_IDS:
        return False
    _FORUM_POSTED_EVENT_IDS[post_id] = None
    while len(_FORUM_POSTED_EVENT_IDS) > _FORUM_POSTED_EVENT_LIMIT:
        _FORUM_POSTED_EVENT_IDS.popitem(last=False)
    return True


def _release_forum_posted_event(post_id: int) -> None:
    """上报失败时归还资格，允许后续重试。"""
    _FORUM_POSTED_EVENT_IDS.pop(post_id, None)


async def _publish_forum_posted(
    db: Session,
    user_id: int,
    post_id: int,
    *,
    action: str = "created",
) -> bool:
    """按 post id 幂等上报 E6 ``forum.posted``。

    - 只发一次：同一帖子的重复上报（回复 / 重试 / 并发重复）直接忽略；
    - 上报异常不影响业务流程，但归还去重资格以便下次重试。
    """
    if not _claim_forum_posted_event(post_id):
        logger.info("E6 事件已上报，跳过重复上报: post_id=%s action=%s", post_id, action)
        return False

    payload = {"post_id": post_id, "action": action}
    try:
        return await record_user_action(
            db, user_id, TRIGGER_FORUM_POSTED, session=payload
        )
    except Exception as e:  # noqa: BLE001 —— 事件失败不影响发帖/回复主流程
        logger.warning(f"发帖成就判定失败: {e}")
        _release_forum_posted_event(post_id)
        return False

def _user_brief(user: Optional[SysUser], fallback_id: Optional[int] = None) -> Dict[str, Any]:
    """用户公开摘要：昵称回退 username，并带出头像框/签名。"""
    if not user:
        return {
            "id": fallback_id,
            "nickname": "匿名",
            "avatar": "",
            "avatarFrame": None,
            "signature": None,
            "userType": "student",
        }
    return {
        "id": user.user_id,
        "nickname": user.nickname or user.username,
        "avatar": user.avatar or "",
        "avatarFrame": user.avatar_frame,
        "signature": user.signature,
        "userType": user.user_type,
        "className": user.class_name,
        "school": user.school,
        "department": user.department,
    }


def _serialize_post(
    post: ForumPost,
    user: Optional[SysUser] = None,
    liked: bool = False,
    content_full: bool = False,
    reactions: Optional[Dict[str, int]] = None,
    my_reaction: Optional[str] = None,
    favorite_count: int = 0,
    favorited: bool = False,
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
        "isLocked": bool(post.is_locked),
        "titleColor": post.title_color or "default",
        "questionId": post.question_id,
        "feedbackId": post.feedback_id,
        "lastActivityTime": post.last_activity_time.isoformat() if post.last_activity_time else None,
        "likeCount": post.like_count or 0,
        "commentCount": post.comment_count or 0,
        "viewCount": post.view_count or 0,
        "createTime": post.create_time.isoformat() if post.create_time else None,
        "updateTime": post.update_time.isoformat() if post.update_time else None,
        "userId": post.user_id,
        "liked": liked or my_reaction is not None,
        "myReaction": my_reaction,
        "reactions": reactions or {},
        # === P3：收藏（五角星）与可见范围 ===
        "favoriteCount": favorite_count or 0,
        "favorited": bool(favorited),
        "visibility": post.visibility or "ALL",
        "visibleClasses": post.visible_classes or [],
        "user": _user_brief(user, post.user_id),
    }


def _apply_visibility_filter(query, current_user: Optional[SysUser]):
    """按可见范围过滤帖子（唯一事实来源，列表/详情/我的收藏都必须走这里）。

    - 教师 / 管理员：不过滤
    - 游客：只能看 ALL
    - 学生：ALL，或 CLASSES 且本人 class_name 在 visible_classes 里
    - 学生没填班级：按 ALL 处理（否则他自己的帖子会谁都看不到）
    """
    if current_user is not None and current_user.user_type in ("teacher", "admin"):
        return query
    if current_user is None:
        return query.filter(
            or_(ForumPost.visibility == "ALL", ForumPost.visibility.is_(None))
        )

    cls = (current_user.class_name or "").strip()
    if not cls:
        return query.filter(
            or_(ForumPost.visibility == "ALL", ForumPost.visibility.is_(None))
        )

    # SQLite 下 JSON 列以文本存储。注意 json.dumps 默认 ensure_ascii=True，
    # 中文班级名会存成 "\u4e00\u73ed" 这种转义形式，因此两种编码都要匹配。
    raw_pattern = f'%"{cls}"%'
    ascii_pattern = "%" + json.dumps(cls, ensure_ascii=True)[1:-1] + "%"
    classes_text = func.cast(ForumPost.visible_classes, String)
    return query.filter(
        or_(
            ForumPost.visibility == "ALL",
            ForumPost.visibility.is_(None),
            and_(
                ForumPost.visibility == "CLASSES",
                ForumPost.visible_classes.isnot(None),
                or_(
                    classes_text.like(raw_pattern),
                    classes_text.like(ascii_pattern),
                ),
            ),
        )
    )


def _load_favorite_stats(db: Session, post_ids: List[int], user_id: Optional[int] = None):
    """批量取收藏数 + 当前用户是否收藏（避免 N+1）。"""
    if not post_ids:
        return {}, set()

    count_rows = (
        db.query(ForumFavorite.post_id, func.count(ForumFavorite.favorite_id))
        .filter(ForumFavorite.post_id.in_(post_ids))
        .group_by(ForumFavorite.post_id)
        .all()
    )
    counts = {post_id: int(cnt or 0) for post_id, cnt in count_rows}

    mine = set()
    if user_id:
        mine_rows = (
            db.query(ForumFavorite.post_id)
            .filter(
                ForumFavorite.post_id.in_(post_ids),
                ForumFavorite.user_id == user_id,
            )
            .all()
        )
        mine = {row[0] for row in mine_rows}
    return counts, mine


def _serialize_comment(
    comment: ForumComment,
    user: Optional[SysUser] = None,
    liked: bool = False,
    reactions: Optional[Dict[str, int]] = None,
    my_reaction: Optional[str] = None,
    reply_count: int = 0,
) -> Dict[str, Any]:
    """序列化评论为响应字典"""
    return {
        "id": comment.comment_id,
        "content": comment.content,
        "likeCount": comment.like_count or 0,
        "createTime": comment.create_time.isoformat() if comment.create_time else None,
        "parentCommentId": comment.parent_comment_id,
        "isPinned": bool(comment.is_pinned),
        "replyToUserId": comment.reply_to_user_id,
        "attachments": comment.attachments or [],
        "liked": liked or my_reaction is not None,
        "myReaction": my_reaction,
        "reactions": reactions or {},
        "replyCount": reply_count or 0,
        "user": _user_brief(user, comment.user_id),
    }


def _load_reaction_stats(
    db: Session,
    target_ids: List[int],
    *,
    is_comment: bool = False,
    user_id: Optional[int] = None,
):
    """批量聚合表情反应，返回 (按目标的计数, 当前用户对每个目标的选择)。"""
    if not target_ids:
        return {}, {}

    field = ForumLike.comment_id if is_comment else ForumLike.post_id
    rows = db.query(
        field, ForumLike.reaction_code, func.count(ForumLike.like_id)
    ).filter(field.in_(target_ids)).group_by(field, ForumLike.reaction_code).all()

    counts: Dict[int, Dict[str, int]] = {}
    for target_id, code, total in rows:
        counts.setdefault(target_id, {})[code or "like"] = total

    mine: Dict[int, str] = {}
    if user_id is not None:
        mine_rows = db.query(field, ForumLike.reaction_code).filter(
            field.in_(target_ids),
            ForumLike.user_id == user_id,
        ).all()
        for target_id, code in mine_rows:
            mine[target_id] = code or "like"
    return counts, mine


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
    share_type: Optional[str] = Query(None, description="分享类型: EXPERIENCE/RESOURCE/DISCUSSION/FEELING/QUESTION"),
    sort_by: Literal["time", "likes", "comments", "views"] = Query("time", description="排序字段"),
    order: Literal["asc", "desc"] = Query("desc", description="排序方向"),
    keyword: Optional[str] = Query(None, description="标题/正文关键词"),
    sort: Optional[Literal["new", "hot"]] = Query(None, description="快捷排序: new/hot"),
    date_from: Optional[str] = Query(None, description="起始日期 YYYY-MM-DD（含当天）"),
    date_to: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD（含当天）"),
    limit: int = Query(20, ge=1, le=50, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    获取论坛帖子列表(公开访问)
    - 支持按 share_type 筛选
    - 支持按时间/点赞/评论/浏览排序
    - 批量查询 user 信息(避免 N+1)
    - 返回当前用户点赞状态
    """
    query = db.query(ForumPost).filter(ForumPost.status == "NORMAL")
    # P3：可见范围（教师/管理员不过滤；学生仅本校班级或全校；游客仅全校）
    query = _apply_visibility_filter(query, current_user)

    if share_type:
        query = query.filter(ForumPost.share_type == share_type)
    if keyword:
        like = f"%{keyword.strip()}%"
        query = query.filter(
            or_(ForumPost.title.like(like), ForumPost.content.like(like))
        )
    # P3：日期区间（两端都含当天）
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
    if sort == "hot":
        sort_expr = (
            ForumPost.like_count * 2 + ForumPost.comment_count * 3
        ).desc()
    elif sort == "new":
        sort_expr = ForumPost.create_time.desc()
    else:
        sort_field = {
            "time": ForumPost.create_time,
            "likes": ForumPost.like_count,
            "comments": ForumPost.comment_count,
            "views": ForumPost.view_count,
        }[sort_by]
        sort_expr = sort_field.asc() if order == "asc" else sort_field.desc()
    posts = query.order_by(
        ForumPost.is_top.desc(),
        sort_expr,
        ForumPost.create_time.desc()
    ).offset(offset).limit(limit).all()

    if not posts:
        return {"total": total, "limit": limit, "offset": offset, "posts": []}

    # 批量查询 user 信息
    user_ids = list({p.user_id for p in posts})
    users = db.query(SysUser).filter(SysUser.user_id.in_(user_ids)).all()
    user_map = {u.user_id: u for u in users}

    # 批量聚合表情反应 + 当前用户选择
    post_ids = [p.post_id for p in posts]
    reaction_counts, my_reactions = _load_reaction_stats(
        db,
        post_ids,
        user_id=current_user.user_id if current_user else None,
    )
    # P3：批量取收藏统计（避免 N+1）
    fav_counts, my_favs = _load_favorite_stats(
        db,
        post_ids,
        user_id=current_user.user_id if current_user else None,
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "posts": [
            _serialize_post(
                p,
                user_map.get(p.user_id),
                p.post_id in my_reactions,
                reactions=reaction_counts.get(p.post_id, {}),
                my_reaction=my_reactions.get(p.post_id),
                favorite_count=fav_counts.get(p.post_id, 0),
                favorited=p.post_id in my_favs,
            )
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

    # P3：可见范围校验（不可见时按不存在处理，避免泄露"存在但你看不到"）
    visible = _apply_visibility_filter(
        db.query(ForumPost).filter(
            ForumPost.post_id == post_id,
            ForumPost.status == "NORMAL",
        ),
        current_user,
    ).first()
    if not visible:
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
    reaction_counts, my_reactions = _load_reaction_stats(
        db,
        [post_id],
        user_id=current_user.user_id if current_user else None,
    )
    fav_counts, my_favs = _load_favorite_stats(
        db,
        [post_id],
        user_id=current_user.user_id if current_user else None,
    )

    return _serialize_post(
        post,
        user,
        liked=post_id in my_reactions,
        content_full=True,
        reactions=reaction_counts.get(post_id, {}),
        my_reaction=my_reactions.get(post_id),
        favorite_count=fav_counts.get(post_id, 0),
        favorited=post_id in my_favs,
    )


@router.post("/posts", summary="发布新帖")
async def create_post(
    request: Request,
    title: str = Form(..., max_length=200),
    content: str = Form(..., max_length=10000),
    share_type: str = Form("EXPERIENCE"),
    tags: Optional[str] = Form(None),
    attachments: Optional[str] = Form(None, description="附件列表 JSON 字符串"),
    title_color: str = Form("default", description="标题颜色 token"),
    question_id: Optional[int] = Form(None, description="关联题目ID"),
    visibility: Optional[str] = Form(None, description="可见范围: ALL 全校 | CLASSES 本班/指定班级"),
    visible_classes: Optional[str] = Form(None, description="班级名 JSON 数组，visibility=CLASSES 时生效"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    发布新帖
    - 必须登录
    - 关键词过滤:blocked 直接拒绝,masked 自动屏蔽后发布
    - 支持附件(attachments 为 JSON 字符串)
    """
    title = (title or "").strip()
    content = (content or "").strip()
    if not title:
        raise ValidationError("标题不能为空")
    if not content:
        raise ValidationError("正文不能为空")

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

    # 3. 可见范围（P3，决策：学生默认本班、可改全校；教师/管理员默认全校；不设上限）
    is_staff = current_user.user_type in ("teacher", "admin")
    classes = None
    if visible_classes:
        try:
            classes = json.loads(visible_classes)
            if not isinstance(classes, list):
                raise ValueError("visible_classes 必须是数组")
            classes = [str(c).strip() for c in classes if str(c).strip()]
        except (json.JSONDecodeError, ValueError) as e:
            raise ValidationError(f"可见班级格式错误: {e}")

    if visibility not in ("ALL", "CLASSES"):
        visibility = "ALL" if is_staff else "CLASSES"
    if visibility == "CLASSES":
        if not classes:
            own_class = (current_user.class_name or "").strip()
            classes = [own_class] if own_class else []
        if not classes:
            # 没有可指定的班级 → 退回全校，避免帖子谁都看不到
            visibility = "ALL"
    if visibility != "CLASSES":
        classes = None

    # 4. 创建帖子
    if title_color not in TITLE_COLORS:
        title_color = "default"
    post = ForumPost(
        user_id=current_user.user_id,
        title=title.strip(),
        content=final_content,
        share_type=share_type if share_type in ("EXPERIENCE", "RESOURCE", "DISCUSSION", "FEELING", "QUESTION") else "EXPERIENCE",
        tags=tags,
        attachments=parsed_attachments,
        title_color=title_color,
        question_id=question_id,
        last_activity_time=datetime.now(),
        status="NORMAL",
        visibility=visibility,
        visible_classes=classes,
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    logger.info(f"用户 {current_user.user_id} 发布帖子 {post.post_id}")

    # 触发社交成就（按 post id 幂等，只会成功上报一次）
    await _publish_forum_posted(
        db, current_user.user_id, post.post_id, action="created"
    )

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
            reaction_code="like",
        ))
        post.like_count = (post.like_count or 0) + 1
        liked = True

    db.commit()

    # 点赞不是创建行为，不上报 E6 事件（P2-28）

    counts, mine = _load_reaction_stats(
        db, [post_id], user_id=current_user.user_id
    )
    return {
        "liked": liked,
        "likeCount": post.like_count,
        "myReaction": mine.get(post_id),
        "reactions": counts.get(post_id, {}),
    }


# ============================== 收藏 / 我的喜欢（P3） ==============================

@router.post("/posts/{post_id}/favorite", summary="收藏/取消收藏（五角星）")
async def toggle_post_favorite(
    post_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """收藏切换（幂等）：已收藏则取消，未收藏则收藏。

    与 /api/collection（题目/新闻收藏）互不相干；本接口只服务论坛帖子。
    同步维护 forum_post.collect_count 作为展示计数。
    """
    post = db.query(ForumPost).filter(
        ForumPost.post_id == post_id,
        ForumPost.status == "NORMAL",
    ).first()
    if not post:
        raise ResourceNotFoundError("帖子", post_id)

    existing = db.query(ForumFavorite).filter(
        ForumFavorite.post_id == post_id,
        ForumFavorite.user_id == current_user.user_id,
    ).first()

    if existing:
        db.delete(existing)
        post.collect_count = max(0, (post.collect_count or 0) - 1)
        favorited = False
    else:
        db.add(ForumFavorite(post_id=post_id, user_id=current_user.user_id))
        post.collect_count = (post.collect_count or 0) + 1
        favorited = True

    db.commit()
    db.refresh(post)

    counts, _ = _load_favorite_stats(db, [post_id])
    return {
        "favorited": favorited,
        "favoriteCount": counts.get(post_id, post.collect_count or 0),
    }


@router.get("/my-favorites", summary="我的收藏（五角星）")
async def get_my_favorites(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """只返回本人收藏且仍正常的帖子；不可见范围同样生效（单一事实来源）。"""
    base = (
        db.query(ForumPost)
        .join(ForumFavorite, ForumFavorite.post_id == ForumPost.post_id)
        .filter(
            ForumFavorite.user_id == current_user.user_id,
            ForumPost.status == "NORMAL",
        )
    )
    base = _apply_visibility_filter(base, current_user)
    total = base.count()
    posts = (
        base.order_by(ForumFavorite.create_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    post_ids = [p.post_id for p in posts]
    user_map = {}
    if post_ids:
        users = db.query(SysUser).filter(SysUser.user_id.in_({p.user_id for p in posts})).all()
        user_map = {u.user_id: u for u in users}
    fav_counts, my_favs = _load_favorite_stats(
        db, post_ids, user_id=current_user.user_id
    )
    reaction_counts, my_reactions = _load_reaction_stats(
        db, post_ids, user_id=current_user.user_id
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "posts": [
            _serialize_post(
                p,
                user_map.get(p.user_id),
                p.post_id in my_reactions,
                reactions=reaction_counts.get(p.post_id, {}),
                my_reaction=my_reactions.get(p.post_id),
                favorite_count=fav_counts.get(p.post_id, 0),
                favorited=p.post_id in my_favs,
            )
            for p in posts
        ],
    }


@router.get("/my-likes", summary="我的喜欢（爱心）")
async def get_my_likes(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """基于 forum_like.reaction_code='like'，只返回本人点过爱心的帖子。"""
    base = (
        db.query(ForumPost)
        .join(ForumLike, ForumLike.post_id == ForumPost.post_id)
        .filter(
            ForumLike.user_id == current_user.user_id,
            ForumLike.reaction_code == "like",
            ForumPost.status == "NORMAL",
        )
    )
    base = _apply_visibility_filter(base, current_user)
    total = base.count()
    posts = (
        base.order_by(ForumLike.create_time.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    post_ids = [p.post_id for p in posts]
    user_map = {}
    if post_ids:
        users = db.query(SysUser).filter(SysUser.user_id.in_({p.user_id for p in posts})).all()
        user_map = {u.user_id: u for u in users}
    fav_counts, my_favs = _load_favorite_stats(
        db, post_ids, user_id=current_user.user_id
    )
    reaction_counts, my_reactions = _load_reaction_stats(
        db, post_ids, user_id=current_user.user_id
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "posts": [
            _serialize_post(
                p,
                user_map.get(p.user_id),
                p.post_id in my_reactions,
                reactions=reaction_counts.get(p.post_id, {}),
                my_reaction=my_reactions.get(p.post_id),
                favorite_count=fav_counts.get(p.post_id, 0),
                favorited=p.post_id in my_favs,
            )
            for p in posts
        ],
    }


# ============================== 评论接口 ==============================

@router.get("/posts/{post_id}/comments", summary="获取帖子评论列表")
async def get_post_comments(
    post_id: int,
    sort_by: Literal["time", "likes", "replies"] = Query("time", description="排序字段"),
    order: Literal["asc", "desc"] = Query("desc", description="排序方向（默认最新在前）"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取帖子评论列表(分页,仅返回 status=1 的评论,支持时间/点赞/回复数排序)"""
    post = db.query(ForumPost).filter(ForumPost.post_id == post_id).first()
    if not post:
        raise ResourceNotFoundError("帖子", post_id)

    child = aliased(ForumComment)
    reply_count_subq = (
        db.query(func.count(child.comment_id))
        .filter(
            child.parent_comment_id == ForumComment.comment_id,
            child.status == 1,
        )
        .correlate(ForumComment)
        .scalar_subquery()
    )

    base_query = db.query(ForumComment).filter(
        ForumComment.post_id == post_id,
        ForumComment.status == 1
    )
    total = base_query.count()

    sort_field = {
        "time": ForumComment.create_time,
        "likes": ForumComment.like_count,
        "replies": reply_count_subq,
    }[sort_by]
    sort_expr = sort_field.asc() if order == "asc" else sort_field.desc()

    rows = (
        db.query(ForumComment, reply_count_subq.label("reply_count"))
        .filter(
            ForumComment.post_id == post_id,
            ForumComment.status == 1,
        )
        .order_by(
            ForumComment.is_pinned.desc(),
            sort_expr,
            ForumComment.create_time.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    comments = [row[0] for row in rows]
    reply_counts = {row[0].comment_id: int(row[1] or 0) for row in rows}

    if not comments:
        return {"total": total, "limit": limit, "offset": offset, "comments": []}

    # 批量查询 user 信息
    user_ids = list({c.user_id for c in comments})
    users = db.query(SysUser).filter(SysUser.user_id.in_(user_ids)).all()
    user_map = {u.user_id: u for u in users}

    # 批量聚合评论表情反应 + 当前用户选择
    comment_ids = [c.comment_id for c in comments]
    reaction_counts, my_reactions = _load_reaction_stats(
        db,
        comment_ids,
        is_comment=True,
        user_id=current_user.user_id if current_user else None,
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "comments": [
            _serialize_comment(
                c,
                user_map.get(c.user_id),
                c.comment_id in my_reactions,
                reactions=reaction_counts.get(c.comment_id, {}),
                my_reaction=my_reactions.get(c.comment_id),
                reply_count=reply_counts.get(c.comment_id, 0),
            )
            for c in comments
        ]
    }


@router.post("/posts/{post_id}/comments", summary="发表评论")
async def create_comment(
    post_id: int,
    request: Request,
    content: str = Form(..., max_length=2000),
    parent_comment_id: Optional[int] = Form(None),
    reply_to_user_id: Optional[int] = Form(None),
    attachments: Optional[str] = Form(None, description="评论图片 JSON 字符串"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    发表评论
    - 必须登录
    - 关键词过滤(同发帖逻辑)
    - 支持楼中楼回复(parent_comment_id)
    """
    content = (content or "").strip()
    if not content:
        raise ValidationError("评论内容不能为空")

    post = db.query(ForumPost).filter(
        ForumPost.post_id == post_id,
        ForumPost.status == "NORMAL"
    ).first()
    if not post:
        raise ResourceNotFoundError("帖子", post_id)
    if post.is_locked:
        raise BusinessLogicError("该帖子已关闭评论")

    # 校验父评论是否存在且属于同一帖子
    if parent_comment_id:
        parent = db.query(ForumComment).filter(
            ForumComment.comment_id == parent_comment_id,
            ForumComment.post_id == post_id
        ).first()
        if not parent:
            raise ValidationError("父评论不存在或不属于该帖子")
        if not reply_to_user_id:
            reply_to_user_id = parent.user_id

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

    parsed_attachments = None
    if attachments:
        try:
            parsed_attachments = json.loads(attachments)
            if not isinstance(parsed_attachments, list):
                raise ValueError("attachments 必须是数组")
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValidationError(f"评论图片格式错误: {exc}")

    # 创建评论
    comment = ForumComment(
        post_id=post_id,
        user_id=current_user.user_id,
        parent_comment_id=parent_comment_id,
        reply_to_user_id=reply_to_user_id,
        attachments=parsed_attachments,
        content=final_content,
        status=1,
    )
    db.add(comment)

    # 帖子评论数 +1，并刷新最后活跃时间
    post.comment_count = (post.comment_count or 0) + 1
    post.last_activity_time = datetime.now()

    db.commit()
    db.refresh(comment)

    # 回帖同样走 forum.posted；同一帖子只在首次创建时上报一次（P2-28）
    await _publish_forum_posted(
        db, current_user.user_id, post_id, action="commented"
    )

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

    # 点赞不是创建行为，不上报 E6 事件（P2-28）

    return {"liked": liked, "likeCount": comment.like_count}


# ============================== 表情反应 ==============================

def _apply_reaction(
    db: Session,
    user_id: int,
    code: str,
    *,
    post_id: Optional[int] = None,
    comment_id: Optional[int] = None,
) -> Dict[str, Any]:
    """设置/切换/取消表情反应。

    语义：一个用户对同一目标只能有一个反应。
    - 相同表情再次点击 → 取消
    - 不同表情 → 替换，不改变总数
    """
    if code not in REACTION_CODES:
        raise ValidationError(f"不支持的表情: {code}")

    if comment_id is not None:
        target = db.query(ForumComment).filter(
            ForumComment.comment_id == comment_id,
            ForumComment.status == 1,
        ).first()
        if not target:
            raise ResourceNotFoundError("评论", comment_id)
        match = {"comment_id": comment_id}
        is_comment = True
    else:
        target = db.query(ForumPost).filter(
            ForumPost.post_id == post_id,
            ForumPost.status == "NORMAL",
        ).first()
        if not target:
            raise ResourceNotFoundError("帖子", post_id)
        match = {"post_id": post_id}
        is_comment = False

    existing = db.query(ForumLike).filter(
        ForumLike.user_id == user_id,
        *[getattr(ForumLike, k) == v for k, v in match.items()],
    ).first()

    my_reaction: Optional[str] = code
    if existing:
        if (existing.reaction_code or "like") == code:
            db.delete(existing)
            target.like_count = max(0, (target.like_count or 0) - 1)
            my_reaction = None
        else:
            existing.reaction_code = code
    else:
        db.add(ForumLike(user_id=user_id, reaction_code=code, **match))
        target.like_count = (target.like_count or 0) + 1

    db.commit()

    target_id = comment_id if is_comment else post_id
    counts, mine = _load_reaction_stats(
        db, [target_id], is_comment=is_comment, user_id=user_id
    )
    return {
        "myReaction": mine.get(target_id),
        "reactions": counts.get(target_id, {}),
        "reactionCount": target.like_count,
    }


@router.post("/posts/{post_id}/reactions/{reaction_code}", summary="帖子表情反应")
async def set_post_reaction(
    post_id: int,
    reaction_code: str,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _apply_reaction(
        db, current_user.user_id, reaction_code, post_id=post_id
    )


def _clear_reaction(
    db: Session,
    user_id: int,
    *,
    post_id: Optional[int] = None,
    comment_id: Optional[int] = None,
) -> Dict[str, Any]:
    """取消当前用户对目标的任意表情反应。"""
    if comment_id is not None:
        target = db.query(ForumComment).filter(
            ForumComment.comment_id == comment_id,
            ForumComment.status == 1,
        ).first()
        if not target:
            raise ResourceNotFoundError("评论", comment_id)
        match = {"comment_id": comment_id}
        is_comment = True
    else:
        target = db.query(ForumPost).filter(
            ForumPost.post_id == post_id,
            ForumPost.status == "NORMAL",
        ).first()
        if not target:
            raise ResourceNotFoundError("帖子", post_id)
        match = {"post_id": post_id}
        is_comment = False

    existing = db.query(ForumLike).filter(
        ForumLike.user_id == user_id,
        *[getattr(ForumLike, k) == v for k, v in match.items()],
    ).first()

    if existing:
        db.delete(existing)
        target.like_count = max(0, (target.like_count or 0) - 1)
        db.commit()

    target_id = comment_id if is_comment else post_id
    counts, mine = _load_reaction_stats(
        db, [target_id], is_comment=is_comment, user_id=user_id
    )
    return {
        "myReaction": mine.get(target_id),
        "reactions": counts.get(target_id, {}),
        "reactionCount": target.like_count,
    }


@router.delete("/posts/{post_id}/reactions", summary="取消帖子表情反应")
async def clear_post_reaction(
    post_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _clear_reaction(db, current_user.user_id, post_id=post_id)


@router.post("/comments/{comment_id}/reactions/{reaction_code}", summary="评论表情反应")
async def set_comment_reaction(
    comment_id: int,
    reaction_code: str,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _apply_reaction(
        db, current_user.user_id, reaction_code, comment_id=comment_id
    )


@router.delete("/comments/{comment_id}/reactions", summary="取消评论表情反应")
async def clear_comment_reaction(
    comment_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _clear_reaction(db, current_user.user_id, comment_id=comment_id)


# ============================== 表情包 ==============================

STICKER_ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
STICKER_MAX_SIZE = 1024 * 1024
STICKER_USER_LIMIT = 50


def _serialize_sticker(sticker: ForumSticker) -> Dict[str, Any]:
    return {
        "id": sticker.sticker_id,
        "name": sticker.name,
        "url": sticker.url,
        "category": sticker.category,
        "ownerId": sticker.user_id,
    }


@router.get("/stickers", summary="获取表情包列表")
async def list_stickers(
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """返回系统内置表情包 + 当前用户自定义表情包。"""
    query = db.query(ForumSticker).filter(ForumSticker.enabled == 1)
    if current_user:
        query = query.filter(
            or_(ForumSticker.user_id.is_(None), ForumSticker.user_id == current_user.user_id)
        )
    else:
        query = query.filter(ForumSticker.user_id.is_(None))

    stickers = query.order_by(
        ForumSticker.sort_order.asc(), ForumSticker.sticker_id.asc()
    ).all()
    return {"stickers": [_serialize_sticker(s) for s in stickers]}


@router.post("/stickers", summary="上传自定义表情包")
async def upload_sticker(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传自定义表情包（png/jpg/gif/webp，≤1MB）。"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in STICKER_ALLOWED_EXT:
        raise ValidationError(f"表情包仅支持 png/jpg/gif/webp，不允许 {ext or '未知'} 格式")

    contents = await file.read()
    if len(contents) > STICKER_MAX_SIZE:
        raise ValidationError("表情包不能超过 1MB")
    if not contents:
        raise ValidationError("表情包文件为空")

    owned = db.query(func.count(ForumSticker.sticker_id)).filter(
        ForumSticker.user_id == current_user.user_id
    ).scalar() or 0
    if owned >= STICKER_USER_LIMIT:
        raise ValidationError(f"自定义表情包最多 {STICKER_USER_LIMIT} 个")

    filename = f"{uuid.uuid4().hex}{ext}"
    save_dir = os.path.join(settings.UPLOAD_DIR, "stickers")
    os.makedirs(save_dir, exist_ok=True)
    with open(os.path.join(save_dir, filename), "wb") as f:
        f.write(contents)

    sticker = ForumSticker(
        user_id=current_user.user_id,
        name=(name or "自定义表情").strip()[:50] or "自定义表情",
        url=f"/uploads/stickers/{filename}",
        category="sticker",
        sort_order=100,
    )
    db.add(sticker)
    db.commit()
    db.refresh(sticker)
    return _serialize_sticker(sticker)


@router.delete("/stickers/{sticker_id}", summary="删除自定义表情包")
async def delete_sticker(
    sticker_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sticker = db.query(ForumSticker).filter(
        ForumSticker.sticker_id == sticker_id
    ).first()
    if not sticker:
        raise ResourceNotFoundError("表情包", sticker_id)
    if sticker.user_id != current_user.user_id:
        raise BusinessLogicError("只能删除自己上传的表情包", code="PERMISSION_DENIED")

    sticker.enabled = 0
    db.commit()
    return {"success": True, "message": "已删除"}


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
    # 1. 白名单校验(扩展名 + MIME / 文件头)
    ALLOWED_EXT = {
        ".doc", ".docx", ".pdf", ".xls", ".xlsx",
        ".ppt", ".pptx", ".txt", ".csv", ".zip", ".rar", ".7z",
    }
    ALLOWED_MIME = {
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/pdf",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
        "text/csv",
        "application/csv",
        "application/zip",
        "application/x-zip-compressed",
        "application/vnd.rar",
        "application/x-rar-compressed",
        "application/x-7z-compressed",
        "application/octet-stream",
    }
    ARCHIVE_MAGIC = {
        ".zip": (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"),
        ".rar": (b"Rar!\x1a\x07",),
        ".7z": (b"7z\xbc\xaf\x27\x1c",),
    }

    original_name = file.filename or ""
    ext = os.path.splitext(original_name)[1].lower()

    if ext not in ALLOWED_EXT:
        raise ValidationError(f"不支持的文件格式: {ext}")

    # 2. 大小校验(< 20MB)
    MAX_SIZE = 20 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise ValidationError("文件大小不能超过 20MB")

    if ext in ARCHIVE_MAGIC:
        if not any(contents.startswith(sig) for sig in ARCHIVE_MAGIC[ext]):
            raise ValidationError("压缩包文件头校验失败")
    elif file.content_type not in ALLOWED_MIME:
        raise ValidationError(f"文件 MIME 类型不合法: {file.content_type}")

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
        "nickname": user.nickname or user.username,
        "avatar": user.avatar or "",
        "avatarFrame": user.avatar_frame,
        "signature": user.signature,
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

    post_ids = [p.post_id for p in posts]
    reaction_counts, my_reactions = _load_reaction_stats(
        db, post_ids, user_id=current_user.user_id
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "posts": [
            _serialize_post(
                p,
                current_user,
                p.post_id in my_reactions,
                reactions=reaction_counts.get(p.post_id, {}),
                my_reaction=my_reactions.get(p.post_id),
            )
            for p in posts
        ]
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


# ============================== 举报（P0） ==============================

REPORT_TARGET_TYPES = {"POST", "COMMENT", "USER"}
REPORT_REASON_CODES = {"spam", "abuse", "illegal", "other"}


@router.post("/reports", summary="举报帖子/评论/用户")
async def create_forum_report(
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target_type = str(payload.get("target_type") or "").upper()
    if target_type not in REPORT_TARGET_TYPES:
        raise ValidationError("举报目标类型不合法")
    try:
        target_id = int(payload.get("target_id"))
    except (TypeError, ValueError):
        raise ValidationError("举报目标ID不合法")

    reason_code = str(payload.get("reason_code") or "").lower()
    if reason_code not in REPORT_REASON_CODES:
        raise ValidationError("举报原因不合法")
    reason_text = (payload.get("reason_text") or "").strip()[:200] or None

    # 校验目标存在，并禁止举报自己的内容
    if target_type == "POST":
        target = db.query(ForumPost).filter(ForumPost.post_id == target_id).first()
        owner_id = target.user_id if target else None
    elif target_type == "COMMENT":
        target = (
            db.query(ForumComment)
            .filter(ForumComment.comment_id == target_id)
            .first()
        )
        owner_id = target.user_id if target else None
    else:
        target = db.query(SysUser).filter(SysUser.user_id == target_id).first()
        owner_id = target_id if target else None

    if not target:
        raise ResourceNotFoundError("举报目标", target_id)
    if owner_id == current_user.user_id:
        raise BusinessLogicError("不能举报自己")

    exists = (
        db.query(ForumReport)
        .filter(
            ForumReport.reporter_id == current_user.user_id,
            ForumReport.target_type == target_type,
            ForumReport.target_id == target_id,
        )
        .first()
    )
    if exists:
        raise DuplicateResourceError("举报记录")

    report = ForumReport(
        reporter_id=current_user.user_id,
        target_type=target_type,
        target_id=target_id,
        reason_code=reason_code,
        reason_text=reason_text,
        status="PENDING",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"success": True, "report_id": report.report_id}


# ============================== P1 编辑/置顶/删除 ==============================

def _can_moderate_forum(user: SysUser, db: Session) -> bool:
    from ....core.security import Permission, get_effective_permissions

    if user.role_level >= 2:
        return True
    return Permission.FORUM_MODERATE in get_effective_permissions(user, db)


@router.put("/posts/{post_id}", summary="编辑帖子（作者30分钟内）")
async def update_post(
    post_id: int,
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = db.query(ForumPost).filter(
        ForumPost.post_id == post_id,
        ForumPost.status == "NORMAL",
    ).first()
    if not post:
        raise ResourceNotFoundError("帖子", post_id)

    is_author = post.user_id == current_user.user_id
    within_window = (
        post.create_time is not None
        and (datetime.now() - post.create_time).total_seconds() <= 30 * 60
    )
    if not (current_user.role_level >= 2 or (is_author and within_window)):
        raise BusinessLogicError("只能编辑自己 30 分钟内发布的帖子")

    title = (payload.get("title") or post.title or "").strip()
    content = (payload.get("content") or post.content or "").strip()
    if not title or not content:
        raise ValidationError("标题和正文不能为空")

    title_filter = sensitive_filter.detect(title)
    content_filter = sensitive_filter.detect(content)
    if (
        title_filter["level"] == SensitiveLevel.BLOCKED
        or content_filter["level"] == SensitiveLevel.BLOCKED
    ):
        blocked = (
            title_filter
            if title_filter["level"] == SensitiveLevel.BLOCKED
            else content_filter
        )
        _log_violation(db, current_user.user_id, None, blocked, "rejected", title)
        raise BusinessLogicError("内容包含违规词，无法发布")
    if title_filter["level"] == SensitiveLevel.MASKED:
        title = title_filter.get("masked_text") or title
    if content_filter["level"] == SensitiveLevel.MASKED:
        content = content_filter.get("masked_text") or content

    title_color = payload.get("title_color", post.title_color or "default")
    if title_color not in TITLE_COLORS:
        title_color = "default"

    post.title = title
    post.content = content
    post.title_color = title_color
    if payload.get("tags") is not None:
        post.tags = payload.get("tags")
    if payload.get("attachments") is not None:
        if not isinstance(payload["attachments"], list):
            raise ValidationError("attachments 必须是数组")
        post.attachments = payload["attachments"]
    post.last_activity_time = datetime.now()
    db.commit()
    db.refresh(post)
    return _serialize_post(post, current_user, content_full=True)


@router.put("/comments/{comment_id}/pin", summary="置顶/取消置顶评论")
async def pin_comment(
    comment_id: int,
    payload: Dict[str, Any],
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = db.query(ForumComment).filter(
        ForumComment.comment_id == comment_id,
        ForumComment.status == 1,
    ).first()
    if not comment:
        raise ResourceNotFoundError("评论", comment_id)
    post = db.query(ForumPost).filter(ForumPost.post_id == comment.post_id).first()
    if not post:
        raise ResourceNotFoundError("帖子", comment.post_id)

    if post.user_id != current_user.user_id and not _can_moderate_forum(current_user, db):
        raise BusinessLogicError("只有楼主或管理员可以置顶评论")

    comment.is_pinned = 1 if payload.get("pinned") else 0
    db.commit()
    return {"success": True, "isPinned": bool(comment.is_pinned)}


@router.delete("/comments/{comment_id}", summary="删除评论（软删除）")
async def delete_comment(
    comment_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = db.query(ForumComment).filter(
        ForumComment.comment_id == comment_id,
        ForumComment.status == 1,
    ).first()
    if not comment:
        raise ResourceNotFoundError("评论", comment_id)

    if comment.user_id != current_user.user_id and not _can_moderate_forum(current_user, db):
        raise BusinessLogicError("无权删除该评论")

    comment.status = 0
    post = db.query(ForumPost).filter(ForumPost.post_id == comment.post_id).first()
    if post:
        post.comment_count = max(0, (post.comment_count or 0) - 1)
    db.commit()
    return {"success": True}
