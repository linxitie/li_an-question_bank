"""金句精确去重：normalized_hash + duplicate_of 关系。"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from ..models.models import EssayQuote, QuoteRelation

_PUNCT_RE = re.compile(r"[^\u4e00-\u9fffA-Za-z0-9]")


def normalized_hash(content: str) -> str:
    normalized = _PUNCT_RE.sub("", content or "").lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def rebuild_duplicate_relations(db: Session) -> dict[str, Any]:
    """回填哈希并建立重复关系；不自动下线，交给管理端确认。"""
    quotes = db.query(EssayQuote).order_by(EssayQuote.quote_id).all()
    groups: dict[str, list[EssayQuote]] = defaultdict(list)
    for quote in quotes:
        digest = normalized_hash(quote.content)
        quote.normalized_hash = digest
        groups[digest].append(quote)

    created = 0
    groups_with_duplicates = 0
    for rows in groups.values():
        if len(rows) < 2:
            continue
        groups_with_duplicates += 1
        # 优先保留已通过、status=1 且 ID 最小的金句。
        canonical = sorted(
            rows,
            key=lambda q: (0 if q.status == 1 and q.ai_quality == "approved" else 1, q.quote_id),
        )[0]
        for row in rows:
            if row.quote_id == canonical.quote_id:
                continue
            exists = (
                db.query(QuoteRelation)
                .filter(
                    QuoteRelation.from_quote_id == row.quote_id,
                    QuoteRelation.to_quote_id == canonical.quote_id,
                    QuoteRelation.relation_type == "duplicate_of",
                )
                .first()
            )
            if exists is None:
                db.add(
                    QuoteRelation(
                        from_quote_id=row.quote_id,
                        to_quote_id=canonical.quote_id,
                        relation_type="duplicate_of",
                        score=1.0,
                        created_by="system",
                    )
                )
                created += 1
    db.commit()
    return {
        "quotes": len(quotes),
        "groups_with_duplicates": groups_with_duplicates,
        "relations_created": created,
    }


def duplicate_groups(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    rows = (
        db.query(QuoteRelation)
        .filter(QuoteRelation.relation_type == "duplicate_of")
        .order_by(QuoteRelation.to_quote_id, QuoteRelation.from_quote_id)
        .limit(limit)
        .all()
    )
    grouped: dict[int, list[QuoteRelation]] = defaultdict(list)
    for row in rows:
        grouped[row.to_quote_id].append(row)
    result = []
    for canonical_id, links in grouped.items():
        canonical = db.get(EssayQuote, canonical_id)
        if canonical is None:
            continue
        items = []
        for link in links:
            duplicate = db.get(EssayQuote, link.from_quote_id)
            if duplicate is not None:
                items.append(
                    {
                        "quote_id": duplicate.quote_id,
                        "content": duplicate.content,
                        "author": duplicate.author or "",
                        "source": duplicate.source or "",
                        "status": duplicate.status,
                    }
                )
        result.append(
            {
                "canonical_id": canonical.quote_id,
                "canonical_content": canonical.content,
                "duplicates": items,
            }
        )
    return result
