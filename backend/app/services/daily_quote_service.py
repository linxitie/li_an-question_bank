"""R1 每日金句预生成服务。"""
from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.models import DailyQuote, EssayQuote

ALGORITHM_VERSION = "datehash-v1"


def _hash(day: date, quote: EssayQuote) -> str:
    key = quote.quote_uid or str(quote.quote_id)
    return hashlib.sha256(f"{day.isoformat()}:{key}".encode("utf-8")).hexdigest()


def get_or_create_daily(
    db: Session,
    target_date: date | None = None,
) -> tuple[DailyQuote, EssayQuote] | None:
    """获取/生成当天金句；同一天幂等，跨进程一致。"""
    day = target_date or date.today()
    day_key = day.isoformat()

    row = db.query(DailyQuote).filter(DailyQuote.quote_date == day_key).first()
    if row:
        quote = (
            db.query(EssayQuote)
            .filter(EssayQuote.quote_id == row.quote_id, EssayQuote.status == 1)
            .first()
        )
        if quote:
            return row, quote
        db.delete(row)
        db.commit()

    recent_cutoff = (day - timedelta(days=30)).isoformat()
    recent_ids = {
        quote_id
        for (quote_id,) in db.query(DailyQuote.quote_id)
        .filter(DailyQuote.quote_date >= recent_cutoff)
        .all()
    }

    pool = (
        db.query(EssayQuote)
        .filter(
            EssayQuote.status == 1,
            or_(
                EssayQuote.review_status == "published",
                EssayQuote.review_status.is_(None),
            ),
        )
        .all()
    )
    candidates = [quote for quote in pool if quote.quote_id not in recent_ids]
    fallback_used = 0
    if not candidates:
        candidates = pool
        fallback_used = 1
    if not candidates:
        return None

    chosen = min(candidates, key=lambda quote: _hash(day, quote))
    row = DailyQuote(
        quote_date=day_key,
        quote_id=chosen.quote_id,
        algorithm_version=ALGORITHM_VERSION,
        fallback_used=fallback_used,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, chosen


def serialize_daily(row: DailyQuote, quote: EssayQuote) -> dict[str, Any]:
    return {
        "quote_id": quote.quote_id,
        "content": quote.content,
        "source": quote.source or "",
        "category": quote.category or "",
        "author": quote.author or "",
        "favorited": False,
        "source_type": "database",
        "date": row.quote_date,
    }
