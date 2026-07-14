"""
论坛 API
GET /api/forum/posts — 获取论坛帖子列表
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.security import get_optional_user
from ...models.models import ForumPost, SysUser

router = APIRouter(prefix="/api/forum", tags=["论坛"])
logger = logging.getLogger(__name__)


@router.get("/posts", summary="获取论坛帖子列表")
async def get_forum_posts(
    share_type: Optional[str] = Query(None, description="分享类型: EXPERIENCE/RESOURCE/DISCUSSION/FEELING"),
    limit: int = Query(20, ge=1, le=50, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取论坛帖子列表（公开访问），支持按分享类型筛选"""
    query = db.query(ForumPost).filter(ForumPost.status == 1)

    if share_type:
        query = query.filter(ForumPost.share_type == share_type)

    total = query.count()
    posts = query.order_by(
        ForumPost.is_top.desc(),
        ForumPost.create_time.desc()
    ).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "posts": [
            {
                "id": p.post_id,
                "title": p.title,
                "content": p.content[:200] + "..." if len(p.content or "") > 200 else p.content,
                "shareType": p.share_type,
                "tags": p.tags.split(",") if p.tags else [],
                "isTop": bool(p.is_top),
                "isEssence": bool(p.is_essence),
                "likeCount": p.like_count or 0,
                "commentCount": p.comment_count or 0,
                "viewCount": p.view_count or 0,
                "userId": p.user_id,
                "createTime": p.create_time.isoformat() if p.create_time else None
            }
            for p in posts
        ]
    }
