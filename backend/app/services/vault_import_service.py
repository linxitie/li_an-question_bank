"""R1 原始金句素材库导入（essay_quote upsert）。"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models.models import ContentSource, EssayQuote, KgEdge, Topic
from scripts.content_hub.preview_vault import parse_file
from .kg_service import create_edge, seed_relation_types

_PUNCT_RE = re.compile(r"[\s，。；：！？、“”‘’（）《》〈〉【】,.;:!?\"'()\[\]{}<>·…—\-]+")
_STATUS_MAP = {"已审核": ("published", 1), "待审核": ("pending", 0)}
_STATUS_TRUST = {"published": 70, "pending": 50}


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "")
    return _PUNCT_RE.sub("", value).lower()


def _category_label(relative_parts: tuple[str, ...]) -> str:
    raw = relative_parts[0] if relative_parts else ""
    label = re.sub(r"^\d+-", "", raw)
    return label[:-1] if label.endswith("类") else label


def _topic_slug(name: str) -> str:
    return "auto-" + hashlib.md5(name.encode("utf-8")).hexdigest()[:10]


def _stable_uid(relative_file: str, stem_counts: Counter[str]) -> str:
    """文件名 stem 作为稳定 ID；同名文件跨子目录时追加路径哈希消歧。"""
    stem = Path(relative_file).stem
    if stem_counts.get(stem, 1) <= 1:
        return stem
    suffix = hashlib.sha1(relative_file.encode("utf-8")).hexdigest()[:8]
    return f"{stem}-{suffix}"


def _ensure_topic(db: Session, name: str) -> tuple[Topic, bool]:
    topic = db.query(Topic).filter(Topic.name == name).first()
    if topic:
        return topic, False
    topic = Topic(name=name, slug=_topic_slug(name), kind="theme", aliases=[])
    db.add(topic)
    db.flush()
    return topic, True


def _ensure_source(
    db: Session,
    *,
    quote_id: int,
    relative_file: str,
    publisher: str,
    trust_level: int,
) -> tuple[ContentSource, bool]:
    source = (
        db.query(ContentSource)
        .filter(
            ContentSource.content_type == "quote",
            ContentSource.content_id == quote_id,
            ContentSource.url == relative_file,
        )
        .first()
    )
    if source:
        source.publisher = publisher
        source.trust_level = trust_level
        return source, False
    source = ContentSource(
        content_type="quote",
        content_id=quote_id,
        source_type="obsidian",
        url=relative_file,
        publisher=publisher,
        trust_level=trust_level,
    )
    db.add(source)
    db.flush()
    return source, True


def _edge_exists(db: Session, quote_id: int, relation: str, dst_type: str, dst_id: int) -> bool:
    return (
        db.query(KgEdge.edge_id)
        .filter(
            KgEdge.src_type == "quote",
            KgEdge.src_id == quote_id,
            KgEdge.dst_type == dst_type,
            KgEdge.dst_id == dst_id,
            KgEdge.relation == relation,
        )
        .first()
        is not None
    )


def import_vault(
    db: Session,
    vault: Path,
    *,
    subdir: str = "01-金句素材库",
    limit: int | None = 5,
    apply: bool = False,
) -> dict[str, Any]:
    library = Path(vault) / subdir
    report: dict[str, Any] = {
        "ok": True,
        "apply": apply,
        "library": str(library),
        "scanned": 0,
        "inserted": 0,
        "updated": 0,
        "skipped_status": 0,
        "topics_created": 0,
        "sources_created": 0,
        "edges_created": 0,
        "duplicates": 0,
        "items": [],
        "errors": [],
    }
    if not library.is_dir():
        return {"ok": False, "error": "library_not_found", "library": str(library)}

    if apply:
        seed_relation_types(db)

    files = sorted(library.rglob("*.md"))
    stem_counts = Counter(path.stem for path in files)
    processed = 0
    for path in files:
        if limit is not None and processed >= limit:
            break
        item = parse_file(path, library)
        if not item:
            continue
        report["scanned"] += 1
        raw_status = item["status"]
        mapped = _STATUS_MAP.get(raw_status)
        if not mapped:
            report["skipped_status"] += 1
            continue
        review_status, quote_status = mapped
        quote_text = item["quote"]
        if not quote_text:
            report["errors"].append(f"{item['file']}: empty quote")
            continue

        uid = _stable_uid(item["file"], stem_counts)
        existing = db.query(EssayQuote).filter(EssayQuote.quote_uid == uid).first()
        if existing:
            # 已有人工结果时不让低阶文件状态回退
            if existing.review_status in ("published", "rejected", "archived"):
                review_status = existing.review_status
                quote_status = existing.status
            action = "updated" if apply else "would_update"
        else:
            action = "inserted" if apply else "would_insert"

        category = _category_label(tuple(Path(item["file"]).parts))
        topics = item["topics"] or ([category] if category else [])
        topic_rows: list[Topic] = []
        for name in topics:
            if apply:
                topic, created = _ensure_topic(db, name)
                report["topics_created"] += int(created)
                topic_rows.append(topic)
            else:
                topic_rows.append(db.query(Topic).filter(Topic.name == name).first())

        normalized_hash = hashlib.sha256(normalize_text(quote_text).encode("utf-8")).hexdigest()[:32]
        duplicate_query = db.query(EssayQuote).filter(
            EssayQuote.normalized_hash == normalized_hash
        )
        if existing:
            duplicate_query = duplicate_query.filter(EssayQuote.quote_id != existing.quote_id)
        duplicate_count = duplicate_query.count()
        if duplicate_count:
            report["duplicates"] += 1

        if apply:
            if existing:
                existing.content = quote_text
                existing.source = item["source"]
                existing.author = item["author"]
                existing.category = category
                existing.normalized_hash = normalized_hash
                existing.review_status = review_status
                existing.status = quote_status
                quote = existing
            else:
                quote = EssayQuote(
                    quote_uid=uid,
                    content=quote_text,
                    source=item["source"],
                    author=item["author"],
                    category=category,
                    normalized_hash=normalized_hash,
                    review_status=review_status,
                    status=quote_status,
                )
                db.add(quote)
                db.flush()
                report["inserted"] += 1
            if existing:
                report["updated"] += 1

            source, source_created = _ensure_source(
                db,
                quote_id=quote.quote_id,
                relative_file=item["file"],
                publisher=item["source"],
                trust_level=_STATUS_TRUST.get(review_status, 50),
            )
            report["sources_created"] += int(source_created)
            quote.source_id = source.source_id

            for topic in topic_rows:
                if topic is None:
                    continue
                if not _edge_exists(db, quote.quote_id, "has_topic", "topic", topic.topic_id):
                    create_edge(
                        db,
                        src_type="quote",
                        src_id=quote.quote_id,
                        dst_type="topic",
                        dst_id=topic.topic_id,
                        relation="has_topic",
                    )
                    report["edges_created"] += 1
            if not _edge_exists(db, quote.quote_id, "derived_from", "source", source.source_id):
                create_edge(
                    db,
                    src_type="quote",
                    src_id=quote.quote_id,
                    dst_type="source",
                    dst_id=source.source_id,
                    relation="derived_from",
                )
                report["edges_created"] += 1

        report["items"].append(
            {
                "file": item["file"],
                "uid": uid,
                "action": action,
                "status": review_status,
                "quote": quote_text[:40],
                "topics": topics,
                "duplicate_hash_count": duplicate_count,
            }
        )
        processed += 1

    if apply:
        db.commit()

    return report
