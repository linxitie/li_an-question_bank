"""R2 新闻检索：FTS5 trigram 优先，LIKE 回退。"""
from __future__ import annotations

from sqlalchemy import func, inspect, or_, text
from sqlalchemy.orm import Query, Session

from ..core.news_schema import CATEGORY_ALIASES
from ..models.models import NewsArticle


def _fts_available(db: Session) -> bool:
    try:
        return "news_fts" in set(inspect(db.get_bind()).get_table_names())
    except Exception:
        return False


def _like_filter(query: Query, keyword: str) -> Query:
    like = f"%{keyword}%"
    return query.filter(
        or_(
            NewsArticle.title.like(like),
            NewsArticle.summary.like(like),
            NewsArticle.content.like(like),
        )
    )


def apply_keyword(query: Query, db: Session, keyword: str | None) -> Query:
    """优先 FTS；短词/特殊语法/无 FTS 时回退 LIKE。"""
    value = (keyword or "").strip()
    if not value:
        return query
    if len(value) < 3 or not _fts_available(db):
        return _like_filter(query, value)
    try:
        ids = [
            row[0]
            for row in db.execute(
                text("SELECT news_id FROM news_fts WHERE news_fts MATCH :q"),
                {"q": value},
            ).all()
        ]
        return query.filter(NewsArticle.news_id.in_(ids))
    except Exception:
        db.rollback()
        return _like_filter(query, value)


def category_counts(db: Session) -> dict:
    rows = (
        db.query(NewsArticle.category, NewsArticle.category_code, func.count(NewsArticle.news_id))
        .filter(NewsArticle.status == 1)
        .group_by(NewsArticle.category, NewsArticle.category_code)
        .all()
    )
    items = []
    for category, code, count in rows:
        name = category or "未分类"
        items.append({
            "category": name,
            "category_code": code or CATEGORY_ALIASES.get(name),
            "count": count,
        })
    items.sort(key=lambda item: (-item["count"], item["category"]))
    return {"total": sum(item["count"] for item in items), "items": items}
