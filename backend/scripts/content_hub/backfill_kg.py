#!/usr/bin/env python3
"""R0 三类内容回填：主题边 + 统一来源。

用法（在 backend 目录）：
    python -m scripts.content_hub.backfill_kg --dry-run
    python -m scripts.content_hub.backfill_kg --apply

dry-run 只统计、不写库；apply 幂等，可重复执行。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.models import ContentSource, EssayQuote, KgEdge, NewsArticle, RecruitmentInfo, Topic
from app.services.kg_seed import TOPIC_SEED, seed_topics
from app.services.kg_service import create_edge, seed_relation_types

QUOTE_CATEGORY_TO_TOPIC = {
    "哲理": "哲理思辨",
    "治国": "治国理政",
    "民生": "民生保障",
    "民心": "民生保障",
    "法治": "法治思维",
    "品德": "品德修养",
}

NEWS_CATEGORY_TO_TOPIC = {
    "理论": "政治理论",
    "党史": "党史学习",
    "公安报": "公安要闻",
}

RECRUITMENT_CATEGORY_TO_TOPIC = {
    "国考省考": "国考省考",
    "教师招聘": "教师招聘",
    "事业单位": "事业单位",
    "国企招聘": "国企招聘",
    "医疗卫生": "医疗卫生",
    "三支一扶": "三支一扶",
}

_PUNCT_RE = re.compile(r"[\s，。；：！？、“”‘’（）《》〈〉【】,.;:!?\"'()\[\]{}<>·…—\-]+")


def normalize_text(text: str) -> str:
    """与去重口径保持一致的轻量归一化。"""
    value = unicodedata.normalize("NFKC", text or "")
    return _PUNCT_RE.sub("", value).lower()


def _ensure_source(
    db: Session,
    *,
    content_type: str,
    content_id: int,
    source_type: str,
    url: str,
    publisher: str | None = None,
    trust_level: int = 50,
) -> tuple[ContentSource, bool]:
    url = url or ""
    existing = (
        db.query(ContentSource)
        .filter(
            ContentSource.content_type == content_type,
            ContentSource.content_id == content_id,
            ContentSource.url == url,
        )
        .first()
    )
    if existing:
        return existing, False
    source = ContentSource(
        content_type=content_type,
        content_id=content_id,
        source_type=source_type,
        url=url,
        publisher=publisher or "",
        trust_level=trust_level,
    )
    db.add(source)
    db.flush()
    return source, True


def _link_topic(
    db: Session,
    *,
    topic: Topic,
    content_type: str,
    content_id: int,
) -> bool:
    existing = (
        db.query(KgEdge)
        .filter(
            KgEdge.src_type == content_type,
            KgEdge.src_id == content_id,
            KgEdge.dst_type == "topic",
            KgEdge.dst_id == topic.topic_id,
            KgEdge.relation == "has_topic",
        )
        .first()
    )
    create_edge(
        db,
        src_type=content_type,
        src_id=content_id,
        dst_type="topic",
        dst_id=topic.topic_id,
        relation="has_topic",
    )
    return existing is None


def _link_source(
    db: Session,
    *,
    source: ContentSource,
    content_type: str,
    content_id: int,
) -> bool:
    existing = (
        db.query(KgEdge)
        .filter(
            KgEdge.src_type == content_type,
            KgEdge.src_id == content_id,
            KgEdge.dst_type == "source",
            KgEdge.dst_id == source.source_id,
            KgEdge.relation == "derived_from",
        )
        .first()
    )
    create_edge(
        db,
        src_type=content_type,
        src_id=content_id,
        dst_type="source",
        dst_id=source.source_id,
        relation="derived_from",
    )
    return existing is None


def backfill(db: Session, apply: bool = False) -> dict:
    """回填三类内容的主题边与来源；apply=False 时只统计。"""
    report: dict = {
        "apply": apply,
        "topics_created": 0,
        "sources_created": 0,
        "edges_created": 0,
        "quotes": {"total": 0, "linked": 0, "skipped": 0},
        "news": {"total": 0, "linked": 0, "skipped": 0},
        "recruitment": {"total": 0, "linked": 0, "skipped": 0},
        "coverage": {},
        "missing_topics": [],
        "unmapped": [],
    }

    if apply:
        report["topics_created"] = seed_topics(db) + seed_relation_types(db)

    topic_by_name = {topic.name: topic for topic in db.query(Topic).all()}
    seed_names = {name for name, _slug, _kind in TOPIC_SEED}
    missing_topics: set[str] = set()

    quotes = db.query(EssayQuote).all()
    report["quotes"]["total"] = len(quotes)
    for quote in quotes:
        topic_name = QUOTE_CATEGORY_TO_TOPIC.get((quote.category or "").strip())
        if not topic_name:
            report["quotes"]["skipped"] += 1
            report["unmapped"].append(f"quote:{quote.quote_id}:{(quote.category or '').strip()}")
            continue
        topic = topic_by_name.get(topic_name)
        if apply and topic is None:
            missing_topics.add(topic_name)
            report["quotes"]["skipped"] += 1
            continue
        report["quotes"]["linked"] += 1
        if not apply:
            continue

        if quote.normalized_hash is None:
            quote.normalized_hash = hashlib.sha256(
                normalize_text(quote.content).encode("utf-8")
            ).hexdigest()[:32]
        if not quote.quote_uid:
            quote.quote_uid = f"q_{quote.quote_id:06d}"

        source, created = _ensure_source(
            db,
            content_type="quote",
            content_id=quote.quote_id,
            source_type="manual",
            url="",
            publisher=quote.source or quote.author or "",
            trust_level=40,
        )
        report["sources_created"] += int(created)
        if _link_topic(db, topic=topic, content_type="quote", content_id=quote.quote_id):
            report["edges_created"] += 1
        if _link_source(db, source=source, content_type="quote", content_id=quote.quote_id):
            report["edges_created"] += 1
        if quote.source_id is None:
            quote.source_id = source.source_id

    news_items = db.query(NewsArticle).all()
    report["news"]["total"] = len(news_items)
    for item in news_items:
        topic_name = NEWS_CATEGORY_TO_TOPIC.get((item.category or "").strip())
        if not topic_name:
            report["news"]["skipped"] += 1
            report["unmapped"].append(f"news:{item.news_id}:{(item.category or '').strip()}")
            continue
        topic = topic_by_name.get(topic_name)
        if apply and topic is None:
            missing_topics.add(topic_name)
            report["news"]["skipped"] += 1
            continue
        report["news"]["linked"] += 1
        if not apply:
            continue

        source, created = _ensure_source(
            db,
            content_type="news",
            content_id=item.news_id,
            source_type="web",
            url=item.url or "",
            publisher=item.source or "",
            trust_level=60,
        )
        report["sources_created"] += int(created)
        if _link_topic(db, topic=topic, content_type="news", content_id=item.news_id):
            report["edges_created"] += 1
        if _link_source(db, source=source, content_type="news", content_id=item.news_id):
            report["edges_created"] += 1

    recruitments = db.query(RecruitmentInfo).all()
    report["recruitment"]["total"] = len(recruitments)
    for item in recruitments:
        topic_name = RECRUITMENT_CATEGORY_TO_TOPIC.get((item.category or "").strip())
        if not topic_name:
            report["recruitment"]["skipped"] += 1
            report["unmapped"].append(
                f"recruitment:{item.recruitment_id}:{(item.category or '').strip()}"
            )
            continue
        topic = topic_by_name.get(topic_name)
        if apply and topic is None:
            missing_topics.add(topic_name)
            report["recruitment"]["skipped"] += 1
            continue
        report["recruitment"]["linked"] += 1
        if not apply:
            continue

        source, created = _ensure_source(
            db,
            content_type="recruitment",
            content_id=item.recruitment_id,
            source_type="web",
            url=item.url or "",
            publisher=item.organization or "",
            trust_level=60,
        )
        report["sources_created"] += int(created)
        if _link_topic(db, topic=topic, content_type="recruitment", content_id=item.recruitment_id):
            report["edges_created"] += 1
        if _link_source(db, source=source, content_type="recruitment", content_id=item.recruitment_id):
            report["edges_created"] += 1

    if apply:
        db.commit()

    for bucket, key in (("quotes", "quote"), ("news", "news"), ("recruitment", "recruitment")):
        total = report[bucket]["total"]
        report["coverage"][key] = round(report[bucket]["linked"] / total, 4) if total else 1.0
    report["missing_topics"] = sorted(missing_topics)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="R0 内容图谱回填")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="只统计，不写库（默认）")
    group.add_argument("--apply", action="store_true", help="写入主题边与来源")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = backfill(db, apply=bool(args.apply))
    finally:
        db.close()

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
