"""R2.3 新闻审核管理端 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import SysUser
from ....schemas.schemas import NewsReviewRequest
from ....services import news_review_service

router = APIRouter(prefix="/api/admin/news", tags=["管理员端-新闻"])


def _require_admin(user: SysUser) -> None:
    if (user.role_level or 0) < 2:
        raise HTTPException(status_code=403, detail="仅管理员可审核新闻")


@router.get("/pending", summary="待审新闻")
def pending_news(
    limit: int = Query(50, ge=1, le=200),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    items = news_review_service.list_pending(db, limit=limit)
    return {
        "total": len(items),
        "items": [
            {
                "news_id": n.news_id,
                "title": n.title,
                "source": n.source,
                "review_status": n.review_status,
                "ai_status": n.ai_status,
                "ai_summary": n.ai_summary or "",
                "risk_flags": n.ai_risk_flags or "[]",
            }
            for n in items
        ],
    }


@router.post("/{news_id}/review", summary="审核新闻")
def review_news(
    news_id: int,
    body: NewsReviewRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    try:
        news, log = news_review_service.review_news(
            db,
            news_id=news_id,
            action=body.action,
            reason=body.reason,
            reviewer_id=current_user.user_id,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="新闻不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "news_id": news.news_id,
        "review_status": news.review_status,
        "status": news.status,
        "review_id": log.review_id,
        "action": log.action,
    }
