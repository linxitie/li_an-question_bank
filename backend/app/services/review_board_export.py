"""R1 人工审核看板导出（60–84.9 分 + 仍 pending）。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..models.models import EssayQuote
from .obsidian_export import _quote_topics, _safe_path


def _uid(quote: EssayQuote) -> str:
    return quote.quote_uid or f"q_{quote.quote_id:06d}"


def _note(quote: EssayQuote, topics: list[str]) -> str:
    return (
        "---\n"
        f"uid: {_uid(quote)}\n"
        "type: quote\n"
        "status: needs_human\n"
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
    written = 0
    skipped = 0
    if not dry_run:
        board.mkdir(parents=True, exist_ok=True)

    for quote in candidates:
        target = board / f"{_uid(quote)}.md"
        if target.exists():
            skipped += 1
            continue
        written += 1
        if dry_run:
            continue
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(_note(quote, _quote_topics(db, quote.quote_id)), encoding="utf-8")
        tmp.replace(target)

    lines = [
        "# 金句人工审核看板",
        "",
        f"> 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        f"> 共 {len(candidates)} 条：Scout 分 60–84.9，或仍为 pending。",
        "",
        "| 分数 | UID | 审核状态 | 来源 | 金句 |",
        "|---:|---|---|---|---|",
    ]
    for quote in candidates:
        uid = _uid(quote)
        lines.append(
            f"| {quote.quality_score} | [[{uid}]] | {quote.review_status or ''} | "
            f"{_table_cell(quote.source or '')} | {_table_cell((quote.content or '')[:50])} |"
        )
    index_content = "\n".join(lines) + "\n"
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
        "written": written,
        "skipped": skipped,
        "dry_run": dry_run,
    }
