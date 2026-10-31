"""R1 人工审核看板导出（按分数段分目录）。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..models.models import EssayQuote
from .obsidian_export import _quote_topics, _safe_path

# (目录名, 最低分含, 最高分不含)
BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("01-优先通过", 80.0, 101.0),
    ("02-重点复核", 70.0, 80.0),
    ("03-建议拒绝", 0.0, 70.0),
)


def _bucket(score: float | None) -> str:
    value = score if score is not None else 0.0
    for name, low, high in BUCKETS:
        if low <= value < high:
            return name
    return "03-建议拒绝"


def _uid(quote: EssayQuote) -> str:
    return quote.quote_uid or f"q_{quote.quote_id:06d}"


def _note(quote: EssayQuote, topics: list[str], bucket: str) -> str:
    return (
        "---\n"
        f"uid: {_uid(quote)}\n"
        "type: quote\n"
        "status: needs_human\n"
        f"bucket: {bucket}\n"
        f"review_status: {quote.review_status or ''}\n"
        f"score: {quote.quality_score}\n"
        f"topics: {json.dumps(topics, ensure_ascii=False)}\n"
        f"source: {quote.source or ''}\n"
        f"author: {quote.author or ''}\n"
        'review_note: ""\n'
        "---\n\n"
        f"{quote.content}\n"
    )


def _table_cell(value: str) -> str:
    return (value or "").replace("|", "\\|").replace("\n", " ")


def export_review_board(db: Session, vault: Path, dry_run: bool = False) -> dict[str, Any]:
    vault = Path(vault).expanduser()
    if not vault.exists() or not vault.is_dir():
        return {"ok": False, "error": "vault_not_found", "vault": str(vault)}

    candidates = (
        db.query(EssayQuote)
        .filter(
            or_(
                and_(
                    EssayQuote.quality_score >= 60,
                    EssayQuote.quality_score < 85,
                ),
                EssayQuote.review_status == "pending",
            )
        )
        .order_by(EssayQuote.quality_score.desc(), EssayQuote.quote_id)
        .all()
    )

    board = _safe_path(vault, "00-收件箱", "审核看板")
    buckets: dict[str, int] = {name: 0 for name, _, _ in BUCKETS}
    written = 0
    skipped = 0
    moved = 0
    if not dry_run:
        board.mkdir(parents=True, exist_ok=True)

    # 兼容旧版扁平结构：把根目录笔记迁移到分档目录
    flat_notes = {
        path.stem: path
        for path in board.glob("*.md")
        if path.name != "index.md"
    } if board.is_dir() else {}

    for quote in candidates:
        bucket = _bucket(quote.quality_score)
        buckets[bucket] += 1
        target_dir = _safe_path(vault, "00-收件箱", "审核看板", bucket)
        target = target_dir / f"{_uid(quote)}.md"
        if target.exists():
            skipped += 1
            continue
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
        flat = flat_notes.get(_uid(quote))
        if flat and flat.exists():
            if not dry_run:
                flat.replace(target)
            moved += 1
            continue
        written += 1
        if dry_run:
            continue
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(_note(quote, _quote_topics(db, quote.quote_id), bucket), encoding="utf-8")
        tmp.replace(target)

    lines = [
        "# 金句人工审核看板",
        "",
        f"> 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        f"> 共 {len(candidates)} 条；按分数段拆分到三个子目录。",
        "",
        "## 分档",
        "",
        "| 目录 | 分数 | 数量 |",
        "|---|---:|---:|",
    ]
    for name, low, high in BUCKETS:
        display_low = max(60.0, low)
        display_high = min(85.0, high) - 0.1
        lines.append(f"| {name} | {display_low:.0f}–{display_high:.1f} | {buckets[name]} |")
    lines.append("")

    for name, _low, _high in BUCKETS:
        lines.extend(
            [
                f"## {name}（{buckets[name]}）",
                "",
                "| 分数 | UID | 审核状态 | 来源 | 金句 |",
                "|---:|---|---|---|---|",
            ]
        )
        for quote in candidates:
            if _bucket(quote.quality_score) != name:
                continue
            uid = _uid(quote)
            lines.append(
                f"| {quote.quality_score} | [[{name}/{uid}]] | "
                f"{quote.review_status or ''} | {_table_cell(quote.source or '')} | "
                f"{_table_cell((quote.content or '')[:50])} |"
            )
        lines.append("")

    index_content = "\n".join(lines)
    if not dry_run:
        index = board / "index.md"
        tmp = index.with_name(index.name + ".tmp")
        tmp.write_text(index_content, encoding="utf-8")
        tmp.replace(index)

    return {
        "ok": True,
        "vault": str(vault.resolve()),
        "board": str(board),
        "candidates": len(candidates),
        "buckets": buckets,
        "written": written,
        "moved": moved,
        "skipped": skipped,
        "dry_run": dry_run,
    }
