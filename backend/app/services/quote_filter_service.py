"""R1 金句筛选查询（主题 / 关键词）。"""
from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.models import EssayQuote, KgEdge, Topic


def filter_quote_ids(
    db: Session,
    *,
    topic: str | None = None,
    q: str | None = None,
) -> list[int]:
    """返回满足主题/关键词条件的金句 ID；主题不存在时返回空列表。"""
    query = db.query(EssayQuote.quote_id)

    if topic:
        topic_row = (
            db.query(Topic)
            .filter(or_(Topic.slug == topic, Topic.name == topic))
            .first()
        )
        if not topic_row:
            return []
        linked = db.query(KgEdge.src_id).filter(
            KgEdge.src_type == "quote",
            KgEdge.dst_type == "topic",
            KgEdge.dst_id == topic_row.topic_id,
            KgEdge.relation == "has_topic",
        )
        query = query.filter(EssayQuote.quote_id.in_(linked))

    if q:
        query = query.filter(EssayQuote.content.like(f"%{q}%"))

    return [row[0] for row in query.all()]
