"""R1 金句审核状态机。"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ..models.models import EssayQuote, QuoteReview, SysUser

# 当前状态 -> {action: 新状态}
TRANSITIONS: dict[str, dict[str, str]] = {
    "draft": {"approve": "published", "reject": "rejected"},
    "pending": {
        "approve": "published",
        "reject": "rejected",
        "request_changes": "draft",
    },
    "published": {
        "archive": "archived",
        "reject": "rejected",
        "request_changes": "draft",
    },
    "rejected": {"request_changes": "draft"},
    "archived": {},
}

REASON_REQUIRED_ACTIONS = {"reject", "request_changes"}


def get_quote(db: Session, quote_ref: str | int) -> EssayQuote | None:
    ref = str(quote_ref)
    quote = db.query(EssayQuote).filter(EssayQuote.quote_uid == ref).first()
    if quote:
        return quote
    try:
        quote_id = int(ref)
    except ValueError:
        return None
    return db.query(EssayQuote).filter(EssayQuote.quote_id == quote_id).first()


def list_candidates(db: Session, status: str = "pending", limit: int = 20) -> list[EssayQuote]:
    return (
        db.query(EssayQuote)
        .filter(EssayQuote.review_status == status)
        .order_by(EssayQuote.quote_id.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )


def review_quote(
    db: Session,
    *,
    quote_ref: str | int,
    action: str,
    reviewer: SysUser | None = None,
    reason: str = "",
) -> tuple[EssayQuote, QuoteReview]:
    quote = get_quote(db, quote_ref)
    if not quote:
        raise LookupError("quote not found")

    current = quote.review_status or "published"
    target = TRANSITIONS.get(current, {}).get(action)
    if not target:
        raise ValueError(f"invalid transition: {current} -> {action}")
    if action in REASON_REQUIRED_ACTIONS and not reason.strip():
        raise ValueError("reason is required for reject/request_changes")

    quote.review_status = target
    quote.status = 1 if target == "published" else 0

    log = QuoteReview(
        quote_id=quote.quote_id,
        reviewer_id=reviewer.user_id if reviewer else None,
        action=action,
        reason=reason,
        diff_json=json.dumps(
            {"from": current, "to": target, "reason": reason},
            ensure_ascii=False,
        ),
    )
    db.add(log)
    db.commit()
    db.refresh(quote)
    db.refresh(log)
    return quote, log


def serialize_review(quote: EssayQuote, log: QuoteReview) -> dict[str, Any]:
    return {
        "quote_id": quote.quote_id,
        "quote_uid": quote.quote_uid,
        "review_status": quote.review_status,
        "status": quote.status,
        "review_id": log.review_id,
        "action": log.action,
        "reason": log.reason or "",
    }
