"""R1 Scout 决策落库（高分发布 / 低分拒绝）。"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from ..models.models import EssayQuote, QuoteReview


def apply_scout_decisions(
    db: Session,
    *,
    high: float = 85.0,
    low: float = 60.0,
) -> dict[str, Any]:
    """把规则分落到审核状态；只处理有 quality_score 的金句。"""
    high_quotes = (
        db.query(EssayQuote)
        .filter(EssayQuote.quality_score >= high)
        .all()
    )
    low_quotes = (
        db.query(EssayQuote)
        .filter(EssayQuote.quality_score < low)
        .all()
    )

    approved = 0
    rejected = 0
    for quote in high_quotes:
        before = quote.review_status or ""
        quote.review_status = "published"
        quote.status = 1
        db.add(
            QuoteReview(
                quote_id=quote.quote_id,
                reviewer_id=None,
                action="auto_approve",
                reason=f"Scout score {quote.quality_score} >= {high}",
                diff_json=json.dumps(
                    {"from": before, "to": "published", "score": quote.quality_score},
                    ensure_ascii=False,
                ),
            )
        )
        approved += 1

    for quote in low_quotes:
        before = quote.review_status or ""
        quote.review_status = "rejected"
        quote.status = 0
        db.add(
            QuoteReview(
                quote_id=quote.quote_id,
                reviewer_id=None,
                action="auto_reject",
                reason=f"Scout score {quote.quality_score} < {low}",
                diff_json=json.dumps(
                    {"from": before, "to": "rejected", "score": quote.quality_score},
                    ensure_ascii=False,
                ),
            )
        )
        rejected += 1

    db.commit()
    remaining = {
        "published": db.query(EssayQuote).filter(EssayQuote.review_status == "published").count(),
        "pending": db.query(EssayQuote).filter(EssayQuote.review_status == "pending").count(),
        "rejected": db.query(EssayQuote).filter(EssayQuote.review_status == "rejected").count(),
    }
    return {
        "high_threshold": high,
        "low_threshold": low,
        "approved": approved,
        "rejected": rejected,
        "audit_logs": approved + rejected,
        "remaining": remaining,
    }
