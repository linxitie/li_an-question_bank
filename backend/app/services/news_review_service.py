"""R2.3 新闻审核状态机。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.models import NewsArticle, NewsReview

TRANSITIONS = {
    "pending": {"publish": "published", "reject": "rejected", "needs_changes": "needs_changes"},
    "high_risk": {"publish": "published", "reject": "rejected", "needs_changes": "needs_changes"},
    "needs_changes": {"publish": "published", "reject": "rejected", "resubmit": "pending"},
    "published": {"archive": "archived"},
}


class NewsReviewError(ValueError):
    pass


def review_news(
    db: Session,
    *,
    news_id: int,
    action: str,
    reason: str = "",
    reviewer_id: int | None = None,
) -> tuple[NewsArticle, NewsReview]:
    news = db.query(NewsArticle).filter(NewsArticle.news_id == news_id).first()
    if not news:
        raise LookupError("news not found")
    current = news.review_status or "pending"
    target = TRANSITIONS.get(current, {}).get(action)
    if not target:
        raise NewsReviewError(f"invalid transition: {current} -> {action}")
    if action in ("reject", "needs_changes") and not reason.strip():
        raise NewsReviewError("reason is required")
    news.review_status = target
    if target == "published":
        news.status = 1
    elif target in ("rejected", "needs_changes"):
        news.status = 0
    log = NewsReview(
        news_id=news.news_id,
        action=action,
        from_status=current,
        to_status=target,
        reviewer_id=reviewer_id,
        reason=reason,
    )
    db.add(log)
    db.commit()
    db.refresh(news)
    db.refresh(log)
    return news, log


def list_pending(db: Session, limit: int = 50):
    return (
        db.query(NewsArticle)
        .filter(NewsArticle.review_status.in_(("pending", "high_risk", "needs_changes")))
        .order_by(NewsArticle.publish_date.desc(), NewsArticle.news_id)
        .limit(max(1, min(limit, 200)))
        .all()
    )
