"""每日金句预生成：daily_quote 表是每日下发的唯一快照。"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from ..models.models import DailyQuote, EssayQuote

_ALGORITHM = "datehash-v2"


def _date_index(day: date, size: int) -> int:
    return (day.year * 366 + day.month * 31 + day.day) % max(1, size)


def _pick_quote(db: Session, day: date) -> EssayQuote | None:
    ids = [
        row[0]
        for row in db.query(EssayQuote.quote_id)
        .filter(EssayQuote.status == 1)
        .order_by(EssayQuote.quote_id)
        .all()
    ]
    if not ids:
        return None
    quote = db.get(EssayQuote, ids[_date_index(day, len(ids))])
    if quote is None or quote.status != 1:
        return None
    return quote


def ensure_daily_quote(
    db: Session, day: date | None = None
) -> tuple[EssayQuote | None, DailyQuote | None, bool]:
    """读取或生成当天快照；返回 (quote, record, created)。"""
    target = day or date.today()
    key = target.isoformat()
    record = db.get(DailyQuote, key)
    if record is not None:
        quote = db.get(EssayQuote, record.quote_id)
        if quote is not None and quote.status == 1:
            return quote, record, False
    quote = _pick_quote(db, target)
    if quote is None:
        return None, None, False
    if record is None:
        record = DailyQuote(
            quote_date=key,
            quote_id=quote.quote_id,
            algorithm_version=_ALGORITHM,
            fallback_used=0,
        )
        db.add(record)
    else:
        record.quote_id = quote.quote_id
        record.algorithm_version = _ALGORITHM
        record.fallback_used = 0
    db.commit()
    return quote, record, True
