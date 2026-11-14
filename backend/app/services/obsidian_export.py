"""R0 Obsidian 单向投影：主题页、金句页、新闻索引、招考索引。

不实现审核回写（R1）；不做正文双向编辑。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.models import EssayQuote, KgEdge, NewsArticle, RecruitmentInfo, Topic

MANIFEST_REL = "99-系统/导出清单.json"


class VaultNotConfigured(RuntimeError):
    """vault 路径不存在或不可写。"""


def _safe_path(vault: Path, *parts: str) -> Path:
    root = vault.resolve()
    target = root.joinpath(*parts).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"path escapes vault: {target}")
    return target


def _render_topic(topic: Topic, count: int) -> str:
    aliases = topic.aliases if isinstance(topic.aliases, list) else []
    return (
        "---\n"
        f"type: topic\n"
        f"topic_id: {topic.topic_id}\n"
        f"slug: {topic.slug}\n"
        f"kind: {topic.kind}\n"
        f"aliases: {json.dumps(aliases, ensure_ascii=False)}\n"
        "---\n\n"
        f"# {topic.name}\n\n"
        f"{topic.description or ''}\n\n"
        f"- 关联内容：{count}\n"
    )


def _quote_topics(db: Session, quote_id: int) -> list[str]:
    rows = (
        db.query(KgEdge)
        .filter(
            KgEdge.src_type == "quote",
            KgEdge.src_id == quote_id,
            KgEdge.relation == "has_topic",
        )
        .all()
    )
    topics = []
    for edge in rows:
        topic = db.query(Topic).filter(Topic.topic_id == edge.dst_id).first()
        if topic:
            topics.append(topic.name)
    return topics


def _render_quote(db: Session, quote: EssayQuote) -> str:
    topics = _quote_topics(db, quote.quote_id)
    uid = quote.quote_uid or f"q_{quote.quote_id:06d}"
    status = quote.review_status or "published"
    return (
        "---\n"
        f"uid: {uid}\n"
        "type: quote\n"
        f"status: {status}\n"
        f"topics: {json.dumps(topics, ensure_ascii=False)}\n"
        f"source: {quote.source or ''}\n"
        f"author: {quote.author or ''}\n"
        "review_note: \"\"\n"
        "---\n\n"
        f"{quote.content}\n"
    )


def _render_news_index(db: Session) -> str:
    lines = ["# 新闻总览", ""]
    articles = db.query(NewsArticle).order_by(NewsArticle.category, NewsArticle.news_id).all()
    current = None
    for article in articles:
        if article.category != current:
            current = article.category
            lines.extend([f"## {current or '未分类'}", ""])
        date = article.publish_date.strftime("%Y-%m-%d") if article.publish_date else ""
        lines.append(f"- [{article.title}]({article.url}) {date}")
    lines.append("")
    return "\n".join(lines)


def _render_recruitment_index(db: Session) -> str:
    lines = ["# 招考总览", ""]
    items = (
        db.query(RecruitmentInfo)
        .filter(RecruitmentInfo.status == 1)
        .order_by(RecruitmentInfo.category, RecruitmentInfo.publish_date.desc())
        .all()
    )
    current = None
    for item in items:
        if item.category != current:
            current = item.category
            lines.extend([f"## {current or '未分类'}", ""])
        deadline = item.registration_end or item.deadline or ""
        suffix = f"（截止 {deadline}）" if deadline else ""
        lines.append(f"- [{item.title}]({item.url or ''}) {suffix}")
    lines.append("")
    return "\n".join(lines)


def _write_if_changed(
    vault: Path,
    rel: str,
    content: str,
    manifest: dict[str, str],
    dry_run: bool,
    stats: dict[str, int],
) -> None:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    target = _safe_path(vault, *rel.split("/"))
    if manifest.get(rel) == digest and target.exists():
        stats["skipped"] += 1
        return
    stats["written"] += 1
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(target)
    manifest[rel] = digest


def _write_inbox_once(
    vault: Path,
    quote: EssayQuote,
    content: str,
    dry_run: bool,
    stats: dict[str, int],
) -> None:
    """待审收件箱只写一次；已存在的文件可能含人工修改，绝不覆盖。"""
    uid = quote.quote_uid or f"q_{quote.quote_id:06d}"
    target = _safe_path(vault, "01-待审核", f"{uid}.md")
    if target.exists():
        stats["skipped"] += 1
        return
    stats["written"] += 1
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(target)


def _load_manifest(vault: Path) -> tuple[Path, dict[str, str]]:
    manifest_path = _safe_path(vault, *MANIFEST_REL.split("/"))
    manifest: dict[str, str] = {}
    if manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest = {str(k): str(v) for k, v in loaded.items()}
        except (OSError, json.JSONDecodeError):
            manifest = {}
    return manifest_path, manifest


def _save_manifest(path: Path, manifest: dict[str, str], dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def export_split(db: Session, dry_run: bool = False) -> dict[str, Any]:
    """按三个独立 Vault 导出：金句、新闻索引、招考索引互不混写。"""
    paths = {
        "quote": Path(settings.VAULT_PATH_QUOTE).expanduser(),
        "news": Path(settings.VAULT_PATH_NEWS).expanduser(),
        "job": Path(settings.VAULT_PATH_JOB).expanduser(),
    }
    if not dry_run:
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
    missing = [name for name, path in paths.items() if not path.is_dir()]
    if missing:
        return {"ok": False, "error": "vault_not_found", "missing": missing}

    stats = {"written": 0, "skipped": 0}
    quote_manifest_path, quote_manifest = _load_manifest(paths["quote"])
    news_manifest_path, news_manifest = _load_manifest(paths["news"])
    job_manifest_path, job_manifest = _load_manifest(paths["job"])

    for topic in db.query(Topic).filter(Topic.status == 1).order_by(Topic.topic_id).all():
        count = (
            db.query(KgEdge)
            .filter(KgEdge.dst_type == "topic", KgEdge.dst_id == topic.topic_id)
            .count()
        )
        _write_if_changed(
            paths["quote"],
            f"04-主题地图/{topic.slug}.md",
            _render_topic(topic, count),
            quote_manifest,
            dry_run,
            stats,
        )

    for quote in db.query(EssayQuote).order_by(EssayQuote.quote_id).all():
        status = quote.review_status or "published"
        if status in ("pending", "draft"):
            _write_inbox_once(paths["quote"], quote, _render_quote(db, quote), dry_run, stats)
            continue
        if status == "rejected" or quote.status != 1:
            uid = quote.quote_uid or f"q_{quote.quote_id:06d}"
            _write_if_changed(
                paths["quote"],
                f"03-已拒绝/{uid}.md",
                _render_quote(db, quote),
                quote_manifest,
                dry_run,
                stats,
            )
            continue
        uid = quote.quote_uid or f"q_{quote.quote_id:06d}"
        _write_if_changed(
            paths["quote"],
            f"02-已发布/{uid}.md",
            _render_quote(db, quote),
            quote_manifest,
            dry_run,
            stats,
        )

    _write_if_changed(
        paths["news"],
        "02-已发布/index.md",
        _render_news_index(db),
        news_manifest,
        dry_run,
        stats,
    )
    _write_if_changed(
        paths["job"],
        "02-已发布/index.md",
        _render_recruitment_index(db),
        job_manifest,
        dry_run,
        stats,
    )
    _save_manifest(quote_manifest_path, quote_manifest, dry_run)
    _save_manifest(news_manifest_path, news_manifest, dry_run)
    _save_manifest(job_manifest_path, job_manifest, dry_run)
    return {
        "ok": True,
        "written": stats["written"],
        "skipped": stats["skipped"],
        "vaults": {name: str(path.resolve()) for name, path in paths.items()},
        "exported_at": datetime.now().isoformat(timespec="seconds"),
    }


def export_all(db: Session, vault: Path | None, dry_run: bool = False) -> dict[str, Any]:
    """兼容旧调用；vault=None 时按三个独立 Vault 导出。"""
    if vault is None:
        return export_split(db, dry_run=dry_run)
    vault = Path(vault).expanduser()
    if not vault.exists() or not vault.is_dir():
        return {"ok": False, "error": "vault_not_found", "vault": str(vault)}

    manifest_path = _safe_path(vault, *MANIFEST_REL.split("/"))
    manifest: dict[str, str] = {}
    if manifest_path.is_file():
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                manifest = {str(k): str(v) for k, v in loaded.items()}
        except (OSError, json.JSONDecodeError):
            manifest = {}

    stats = {"written": 0, "skipped": 0}

    topics = db.query(Topic).filter(Topic.status == 1).order_by(Topic.topic_id).all()
    for topic in topics:
        count = (
            db.query(KgEdge)
            .filter(KgEdge.dst_type == "topic", KgEdge.dst_id == topic.topic_id)
            .count()
        )
        _write_if_changed(
            vault,
            f"04-主题地图/{topic.slug}.md",
            _render_topic(topic, count),
            manifest,
            dry_run,
            stats,
        )

    quotes = db.query(EssayQuote).order_by(EssayQuote.quote_id).all()
    for quote in quotes:
        status = quote.review_status or "published"
        if status in ("pending", "draft"):
            _write_inbox_once(
                vault,
                quote,
                _render_quote(db, quote),
                dry_run,
                stats,
            )
            continue
        if status == "rejected" or quote.status != 1:
            uid = quote.quote_uid or f"q_{quote.quote_id:06d}"
            _write_if_changed(
                vault,
                f"03-已拒绝/{uid}.md",
                _render_quote(db, quote),
                manifest,
                dry_run,
                stats,
            )
            continue
        uid = quote.quote_uid or f"q_{quote.quote_id:06d}"
        _write_if_changed(
            vault,
            f"02-已发布/{uid}.md",
            _render_quote(db, quote),
            manifest,
            dry_run,
            stats,
        )

    _write_if_changed(
        vault,
        "02-新闻/index.md",
        _render_news_index(db),
        manifest,
        dry_run,
        stats,
    )
    _write_if_changed(
        vault,
        "03-招考/index.md",
        _render_recruitment_index(db),
        manifest,
        dry_run,
        stats,
    )

    if not dry_run:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    return {
        "ok": True,
        "written": stats["written"],
        "skipped": stats["skipped"],
        "vault": str(vault.resolve()),
        "exported_at": datetime.now().isoformat(timespec="seconds"),
    }
