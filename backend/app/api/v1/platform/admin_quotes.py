"""金句管理端审核 API。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import (
    ContentSource,
    EssayQuote,
    QuoteReview,
    QuoteTag,
    SysUser,
    Topic,
)

router = APIRouter(prefix="/api/admin/quotes", tags=["管理员端-金句"])


def _require_admin(user: SysUser) -> None:
    if (user.role_level or 0) < 2:
        raise HTTPException(status_code=403, detail="仅管理员可审核金句")


class QuoteReviewRequest(BaseModel):
    action: str
    reason: str = ""


def _tags_for(db: Session, quote_id: int) -> list[str]:
    return [
        row[0]
        for row in db.query(Topic.name)
        .join(QuoteTag, QuoteTag.tag_id == Topic.topic_id)
        .filter(QuoteTag.quote_id == quote_id)
        .all()
    ]


@router.get("/stats", summary="金句管理台统计")
def stats(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    return {
        "total": db.query(EssayQuote).count(),
        "published": db.query(EssayQuote).filter(EssayQuote.status == 1).count(),
        "rejected": db.query(EssayQuote).filter(EssayQuote.status == 0).count(),
        "pending": db.query(EssayQuote).filter(EssayQuote.ai_quality == "pending").count(),
        "sources": db.query(ContentSource).filter(ContentSource.content_type == "quote").count(),
        "tags": db.query(Topic).filter(Topic.slug.like("quote-%")).count(),
    }


@router.get("/review", summary="待审金句")
def list_review(
    status: str = Query("pending", pattern="^(pending|approved|rejected|all)$"),
    keyword: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    query = db.query(EssayQuote)
    if status == "pending":
        query = query.filter(EssayQuote.ai_quality == "pending")
    elif status == "approved":
        query = query.filter(EssayQuote.ai_quality == "approved")
    elif status == "rejected":
        query = query.filter(EssayQuote.ai_quality == "rejected")
    if keyword.strip():
        value = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                EssayQuote.content.like(value),
                EssayQuote.author.like(value),
                EssayQuote.source.like(value),
            )
        )
    total = query.count()
    rows = query.order_by(EssayQuote.quote_id).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "quote_id": q.quote_id,
                "content": q.content,
                "source": q.source or "",
                "author": q.author or "",
                "category": q.category or "",
                "status": q.status,
                "review_status": q.review_status,
                "ai_quality": q.ai_quality,
                "ai_quality_reason": q.ai_quality_reason or "",
                "quality_score": q.quality_score,
                "tags": _tags_for(db, q.quote_id),
            }
            for q in rows
        ],
    }


@router.post("/{quote_id}/review", summary="人工审核金句")
def review_quote(
    quote_id: int,
    body: QuoteReviewRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    quote = db.query(EssayQuote).filter(EssayQuote.quote_id == quote_id).first()
    if quote is None:
        raise HTTPException(status_code=404, detail="金句不存在")
    action = body.action.strip().lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="action 必须是 approve 或 reject")
    before = quote.review_status
    quote.ai_quality = "approved" if action == "approve" else "rejected"
    quote.ai_quality_reason = body.reason.strip() or "人工审核"
    quote.ai_reviewed_at = datetime.now()
    quote.status = 1 if action == "approve" else 0
    quote.review_status = "published" if action == "approve" else "rejected"
    review = QuoteReview(
        quote_id=quote_id,
        reviewer_id=current_user.user_id,
        action=f"manual_{action}",
        reason=quote.ai_quality_reason,
        diff_json=f'{{"from":"{before}","to":"{quote.review_status}"}}',
    )
    db.add(review)
    db.commit()
    return {
        "quote_id": quote_id,
        "status": quote.status,
        "review_status": quote.review_status,
        "review_id": review.review_id,
    }


@router.get("/sources", summary="金句来源")
def sources(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    rows = (
        db.query(ContentSource.publisher, func.count(ContentSource.source_id))
        .filter(ContentSource.content_type == "quote")
        .group_by(ContentSource.publisher)
        .order_by(func.count(ContentSource.source_id).desc())
        .limit(100)
        .all()
    )
    return {"items": [{"source": row[0] or "未知", "count": row[1]} for row in rows]}


@router.get("/tags", summary="金句标签")
def tags(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    rows = (
        db.query(Topic.name, func.count(QuoteTag.quote_id))
        .join(QuoteTag, QuoteTag.tag_id == Topic.topic_id)
        .filter(Topic.slug.like("quote-%"))
        .group_by(Topic.name)
        .order_by(func.count(QuoteTag.quote_id).desc())
        .all()
    )
    return {"items": [{"name": row[0], "count": row[1]} for row in rows]}
