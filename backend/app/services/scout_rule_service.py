"""R1 Scout 影子打分（规则版，不发布、不改审核状态）。

评分信号：
- 文本长度（过短/过长扣分）
- 来源可信度（content_source.trust_level）
- 作者/出处完整性
- 主题关联（has_topic 边）
- 占位符/乱码/敏感词/疑似 PII（硬风险）
- 重复内容（normalized_hash）
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from ..models.models import ContentSource, EssayQuote, KgEdge

_CORRUPTION_RE = re.compile(r"\?{3,}")
_PLACEHOLDER_RE = re.compile(
    r"(这句话是|引用的内容|你的引用|此处插入|金句内容|示例|测试|placeholder|test|example)",
    re.IGNORECASE,
)
_PHONE_RE = re.compile(r"\b1[3-9]\d{9}\b")
_ID_CARD_RE = re.compile(r"\b\d{17}[\dXx]\b")
_SENSITIVE_TERMS = (
    "赌博", "毒品", "色情", "暴恐", "恐怖主义", "造谣", "谣言",
    "颠覆", "枪支", "自杀", "涉密", "绝密", "机密文件",
)


@dataclass
class ScoutResult:
    quote_id: int
    quote_uid: str
    score: float
    decision: str
    reasons: list[str] = field(default_factory=list)
    signals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "quote_id": self.quote_id,
            "quote_uid": self.quote_uid,
            "score": self.score,
            "decision": self.decision,
            "reasons": self.reasons,
            "signals": self.signals,
        }


def _source_trust(db: Session, quote: EssayQuote) -> int:
    source = None
    if quote.source_id:
        source = db.query(ContentSource).filter(ContentSource.source_id == quote.source_id).first()
    if source is None:
        source = (
            db.query(ContentSource)
            .filter(
                ContentSource.content_type == "quote",
                ContentSource.content_id == quote.quote_id,
            )
            .first()
        )
    return int(source.trust_level) if source and source.trust_level is not None else 40


def _has_topic(db: Session, quote: EssayQuote) -> bool:
    return (
        db.query(KgEdge.edge_id)
        .filter(
            KgEdge.src_type == "quote",
            KgEdge.src_id == quote.quote_id,
            KgEdge.dst_type == "topic",
            KgEdge.relation == "has_topic",
        )
        .first()
        is not None
    )


def _duplicate_count(db: Session, quote: EssayQuote) -> int:
    if not quote.normalized_hash:
        return 1
    return (
        db.query(EssayQuote)
        .filter(
            EssayQuote.normalized_hash == quote.normalized_hash,
            EssayQuote.quote_id != quote.quote_id,
        )
        .count()
        + 1
    )


def score_quote(db: Session, quote: EssayQuote) -> ScoutResult:
    text = (quote.content or "").strip()
    compact = re.sub(r"\s+", "", text)
    length = len(compact)
    reasons: list[str] = []
    signals: dict[str, Any] = {"length": length}

    if length < 8:
        length_score = 10
        reasons.append("too_short")
    elif length < 15:
        length_score = 45
        reasons.append("short")
    elif length <= 60:
        length_score = 100
    elif length <= 100:
        length_score = 70
        reasons.append("long")
    else:
        length_score = 40
        reasons.append("too_long")

    trust = _source_trust(db, quote)
    signals["source_trust"] = trust
    if trust >= 80:
        trust_score = 100
    elif trust >= 60:
        trust_score = 80
    elif trust >= 40:
        trust_score = 55
    else:
        trust_score = 25
        reasons.append("low_source_trust")

    author = (quote.author or "").strip()
    if author:
        author_score = 100
    elif (quote.source or "").strip():
        author_score = 55
        reasons.append("author_missing")
    else:
        author_score = 20
        reasons.append("source_missing")

    topic_score = 100 if _has_topic(db, quote) else 30
    if topic_score < 100:
        reasons.append("topic_missing")

    duplicate_count = _duplicate_count(db, quote)
    signals["duplicate_count"] = duplicate_count
    duplicate_penalty = 0
    if duplicate_count > 1:
        duplicate_penalty = min(30, 10 * (duplicate_count - 1))
        reasons.append("duplicate")

    hard_risk = False
    if _CORRUPTION_RE.search(text):
        hard_risk = True
        reasons.append("corruption")
    if _PLACEHOLDER_RE.search(text):
        hard_risk = True
        reasons.append("placeholder")
    matched_sensitive = [term for term in _SENSITIVE_TERMS if term in text]
    if matched_sensitive:
        hard_risk = True
        signals["sensitive_terms"] = matched_sensitive
        reasons.append("sensitive")
    if _PHONE_RE.search(text) or _ID_CARD_RE.search(text):
        hard_risk = True
        reasons.append("pii")

    score = (
        0.30 * length_score
        + 0.30 * trust_score
        + 0.15 * author_score
        + 0.15 * topic_score
        + 0.10 * 100
        - duplicate_penalty
    )
    if hard_risk:
        score = min(score, 20)
        decision = "reject_candidate"
    elif score >= 85:
        decision = "auto_approve_candidate"
    elif score >= 60:
        decision = "needs_human"
    else:
        decision = "reject_candidate"

    return ScoutResult(
        quote_id=quote.quote_id,
        quote_uid=quote.quote_uid or f"q_{quote.quote_id:06d}",
        score=round(max(0.0, min(100.0, score)), 1),
        decision=decision,
        reasons=reasons,
        signals=signals,
    )


def scout_quotes(
    db: Session,
    *,
    include_all: bool = False,
    limit: int | None = 200,
    apply: bool = False,
) -> dict[str, Any]:
    query = db.query(EssayQuote)
    if not include_all:
        query = query.filter(EssayQuote.review_status.in_(("pending", "draft")))
    query = query.order_by(EssayQuote.quote_id)
    if limit is not None:
        query = query.limit(max(1, min(limit, 5000)))
    quotes = query.all()

    items: list[dict[str, Any]] = []
    decisions: dict[str, int] = {
        "auto_approve_candidate": 0,
        "needs_human": 0,
        "reject_candidate": 0,
    }
    for quote in quotes:
        result = score_quote(db, quote)
        items.append(result.to_dict())
        decisions[result.decision] = decisions.get(result.decision, 0) + 1
        if apply:
            quote.quality_score = result.score
    if apply:
        db.commit()

    return {
        "apply": apply,
        "include_all": include_all,
        "total": len(items),
        "decisions": decisions,
        "items": items,
    }
