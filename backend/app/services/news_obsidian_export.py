"""R2.2 新闻 Obsidian 审核卡片导出。"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models.models import NewsArticle, NewsImage
from .news_collector import clean_article_text
from .obsidian_export import _safe_path

_BACKEND_DIR = Path(__file__).resolve().parents[2]


def _uid(news: NewsArticle) -> str:
    return f"news_{news.news_id:06d}"


def _copy_images(db: Session, news_list: list[NewsArticle], vault: Path) -> tuple[int, int]:
    """把卡片引用的本地图片复制到 vault 同名路径，保证 Obsidian 能解析 /uploads。"""
    copied = 0
    missing = 0
    for news in news_list:
        images = (
            db.query(NewsImage)
            .filter(NewsImage.news_id == news.news_id)
            .order_by(NewsImage.image_order)
            .all()
        )
        for img in images:
            relative = Path(str(img.image_path or "").lstrip("/\\"))
            if not relative.parts or ".." in relative.parts:
                missing += 1
                continue
            source = _BACKEND_DIR / relative
            target = vault / relative
            if not source.is_file():
                missing += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.is_file() or target.stat().st_size != source.stat().st_size:
                shutil.copy2(source, target)
            copied += 1
    return copied, missing


def _card(db: Session, news: NewsArticle) -> str:
    images = (
        db.query(NewsImage)
        .filter(NewsImage.news_id == news.news_id)
        .order_by(NewsImage.image_order)
        .all()
    )
    exam = json.loads(news.ai_exam_points or "[]")
    entities = json.loads(news.ai_entities or "[]")
    risks = json.loads(news.ai_risk_flags or "[]")
    body = clean_article_text(news.title, news.content or "")
    lines = [
        "---",
        f"news_id: {news.news_id}",
        f"uid: {_uid(news)}",
        "type: news",
        f"status: {news.review_status or 'pending'}",
        f"source: {news.source}",
        f"category: {news.category or ''}",
        f"publish_date: {news.publish_date.date().isoformat() if news.publish_date else ''}",
        f"source_url: {news.url}",
        f"ai_status: {news.ai_status or ''}",
        f"risk_flags: {json.dumps(risks, ensure_ascii=False)}",
        "---",
        "",
        f"# {news.title}",
        "",
        f"- 原文：[{news.url}]({news.url})",
        f"- 来源：{news.source}",
        "",
        "## AI 摘要",
        "",
        news.ai_summary or "（待生成）",
        "",
        *(["## 正文", "", body, ""] if body else []),
        "## 申论考点",
        "",
        *(f"- {item}" for item in exam),
        "",
        "## 实体",
        "",
        *(f"- {item.get('type')}: {item.get('name')}" for item in entities),
        "",
        "## 风险提示",
        "",
        *(f"- {item}" for item in risks),
        "",
        "## 人工审核",
        "",
        "- [ ] 通过",
        "- [ ] 拒绝",
        "- [ ] 退回修改",
        "",
        "- 备注：",
        "",
    ]
    if images:
        lines.extend(
            [
                "## 图片",
                "",
                *(f"- ![{img.image_path}](/{img.image_path.lstrip('/')})" for img in images),
                "",
            ]
        )
    return "\n".join(lines)


def export_news_board(db: Session, vault: Path, dry_run: bool = False) -> dict[str, Any]:
    vault = Path(vault).expanduser()
    if not vault.exists() or not vault.is_dir():
        return {"ok": False, "error": "vault_not_found", "vault": str(vault)}
    news_list = (
        db.query(NewsArticle)
        .filter(NewsArticle.review_status.in_(("pending", "high_risk")))
        .order_by(NewsArticle.publish_date.desc(), NewsArticle.news_id)
        .all()
    )
    images_copied, images_missing = (0, 0)
    if not dry_run:
        images_copied, images_missing = _copy_images(db, news_list, vault)
    root = vault / "01-待审核"
    written = 0
    skipped = 0
    rows = []
    for news in news_list:
        date_dir = news.publish_date.date().isoformat() if news.publish_date else "未分期"
        target = _safe_path(vault, "01-待审核", date_dir, f"{_uid(news)}.md")
        rows.append((date_dir, news))
        if target.exists():
            skipped += 1
            continue
        written += 1
        if dry_run:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(_card(db, news), encoding="utf-8")
        tmp.replace(target)

    lines = [
        "# 新闻时效性看板",
        "",
        f"> 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        f"> 待审 {len(news_list)} 条；高风险 "
        f"{sum(1 for n in news_list if n.review_status == 'high_risk')} 条。",
        "",
        "| 日期 | 标题 | 来源 | 状态 | 风险 |",
        "|---|---|---|---|---|",
    ]
    for date_dir, news in rows:
        risks = json.loads(news.ai_risk_flags or "[]")
        lines.append(
            f"| {date_dir} | [[01-待审核/{date_dir}/{_uid(news)}]] | {news.source} | "
            f"{news.review_status} | {'；'.join(risks) or '低'} |"
        )
    if not dry_run:
        root.mkdir(parents=True, exist_ok=True)
        index = root / "时效性看板.md"
        index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "vault": str(vault.resolve()),
        "candidates": len(news_list),
        "written": written,
        "skipped": skipped,
        "images_copied": images_copied,
        "images_missing": images_missing,
        "dry_run": dry_run,
    }
