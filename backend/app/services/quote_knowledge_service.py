"""金句来源、标签与 FTS5 检索基础设施。"""

from __future__ import annotations

import hashlib
from datetime import datetime

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from ..models.models import ContentSource, EssayQuote, QuoteTag, Topic

_FTS_DDL = """
CREATE VIRTUAL TABLE IF NOT EXISTS quote_fts USING fts5(
    quote_id UNINDEXED,
    content,
    author,
    source,
    tokenize='unicode61'
)
"""

_TRIGGER_DDL = (
    """
    CREATE TRIGGER IF NOT EXISTS quote_fts_ai AFTER INSERT ON essay_quote BEGIN
      INSERT INTO quote_fts(rowid, quote_id, content, author, source)
      VALUES (new.quote_id, new.quote_id, new.content, coalesce(new.author, ''), coalesce(new.source, ''));
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS quote_fts_ad AFTER DELETE ON essay_quote BEGIN
      DELETE FROM quote_fts WHERE rowid = old.quote_id;
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS quote_fts_au AFTER UPDATE ON essay_quote BEGIN
      DELETE FROM quote_fts WHERE rowid = old.quote_id;
      INSERT INTO quote_fts(rowid, quote_id, content, author, source)
      VALUES (new.quote_id, new.quote_id, new.content, coalesce(new.author, ''), coalesce(new.source, ''));
    END
    """,
)


def ensure_quote_knowledge_schema(engine) -> None:
    """创建 FTS5 表与同步触发器；可重复执行。"""
    with engine.begin() as conn:
        conn.execute(text(_FTS_DDL))
        for ddl in _TRIGGER_DDL:
            conn.execute(text(ddl))


def _topic_slug(category: str) -> str:
    digest = hashlib.sha1(category.encode("utf-8")).hexdigest()[:8]
    return f"quote-{digest}"


def backfill_quote_knowledge(db: Session) -> dict[str, int]:
    """给存量金句补来源、分类标签，并重建 FTS 索引。"""
    sources = 0
    tags = 0
    for quote in db.query(EssayQuote).all():
        source_text = (quote.source or "").strip()
        if source_text:
            source = (
                db.query(ContentSource)
                .filter(
                    ContentSource.content_type == "quote",
                    ContentSource.content_id == quote.quote_id,
                )
                .first()
            )
            if source is None:
                source = ContentSource(
                    content_type="quote",
                    content_id=quote.quote_id,
                    source_type="obsidian",
                    url="",
                    publisher=source_text,
                    author=quote.author or None,
                    fetched_at=datetime.now(),
                    trust_level=70,
                )
                db.add(source)
                db.flush()
                sources += 1
            quote.source_id = source.source_id

        category = (quote.category or "").strip()
        if category:
            slug = _topic_slug(category)
            topic = db.query(Topic).filter(or_(Topic.slug == slug, Topic.name == category)).first()
            if topic is None:
                topic = Topic(
                    name=category,
                    slug=slug,
                    kind="theme",
                    description="金句分类",
                    status=1,
                )
                db.add(topic)
                db.flush()
            link = (
                db.query(QuoteTag)
                .filter(QuoteTag.quote_id == quote.quote_id, QuoteTag.tag_id == topic.topic_id)
                .first()
            )
            if link is None:
                db.add(
                    QuoteTag(
                        quote_id=quote.quote_id,
                        tag_id=topic.topic_id,
                        confidence=1.0,
                        source="category",
                    )
                )
                tags += 1
    db.commit()
    with db.get_bind().begin() as conn:
        conn.execute(text("DELETE FROM quote_fts"))
        conn.execute(text("""
                INSERT INTO quote_fts(rowid, quote_id, content, author, source)
                SELECT quote_id, quote_id, content, coalesce(author, ''), coalesce(source, '')
                FROM essay_quote
                WHERE status = 1
                """))
    return {"sources": sources, "tags": tags}
