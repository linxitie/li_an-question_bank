"""R1 金句审核管理端 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import SysUser
from ....schemas.schemas import QuoteReviewRequest
from ....services import quote_review_service

router = APIRouter(prefix="/api/admin/quotes", tags=["管理员端-金句"])


def _require_admin(user: SysUser) -> None:
    if (user.role_level or 0) < 2:
        raise HTTPException(status_code=403, detail="仅管理员可审核金句")


@router.get("/candidates", summary="待审金句列表")
def list_candidates(
    status: str = Query("pending", description="pending/draft/rejected/published/archived"),
    limit: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    quotes = quote_review_service.list_candidates(db, status=status, limit=limit)
    return {
        "items": [
            {
                "quote_id": quote.quote_id,
                "quote_uid": quote.quote_uid,
                "content": quote.content,
                "source": quote.source or "",
                "author": quote.author or "",
                "review_status": quote.review_status,
                "status": quote.status,
            }
            for quote in quotes
        ],
        "total": len(quotes),
    }


@router.post("/{quote_ref}/review", summary="审核金句")
def review_quote(
    quote_ref: str,
    body: QuoteReviewRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    try:
        quote, log = quote_review_service.review_quote(
            db,
            quote_ref=quote_ref,
            action=body.action,
            reviewer=current_user,
            reason=body.reason,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="金句不存在")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return quote_review_service.serialize_review(quote, log)
