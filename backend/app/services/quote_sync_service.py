"""每日金句：从 Obsidian 已审核素材库同步到 essay_quote。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..api.v1.community.quotes import _read_obsidian_quotes
from ..models.models import EssayQuote

_INVALID_AUTHORS = {'"', "'", "“", "”", "-", "—", "佚名", "未知", "无"}


def _clean_author(value: object) -> str:
    """清掉同步/历史数据里的引号、破折号等伪作者。"""
    author = str(value or "").strip()
    return "" if author in _INVALID_AUTHORS else author


def sync_obsidian_quotes(db: Session) -> dict[str, Any]:
    """把 Obsidian 中 status=已审核 的金句幂等写入数据库。"""
    quotes = _read_obsidian_quotes()
    created = 0
    updated = 0
    skipped = 0
    for item in quotes:
        content = (item.get("content") or "").strip()
        if len(content) < 5:
            skipped += 1
            continue
        existing = db.query(EssayQuote).filter(EssayQuote.content == content).first()
        source = (item.get("source") or "").strip()
        author = _clean_author(item.get("author"))
        topics = [str(topic).strip() for topic in (item.get("topics") or []) if topic]
        category = "、".join(topics[:2]) or "金句"
        if existing:
            changed = False
            if source and not existing.source:
                existing.source = source
                changed = True
            current_author = _clean_author(existing.author)
            if current_author != (existing.author or ""):
                existing.author = current_author or None
                changed = True
            if author and not current_author:
                existing.author = author
                changed = True
            if category and not existing.category:
                existing.category = category
                changed = True
            if changed:
                updated += 1
            else:
                skipped += 1
            continue
        db.add(
            EssayQuote(
                content=content,
                source=source or None,
                author=author or None,
                category=category,
                status=1,
            )
        )
        created += 1
    db.commit()
    return {
        "read": len(quotes),
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }
