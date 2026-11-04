#!/usr/bin/env python3
"""生成单文件人工复核总清单（可点击 Markdown 任务列表）。

用法（在 backend 目录）：
    python -m scripts.content_hub.consolidated_review
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.models import EssayQuote
from app.services.obsidian_export import _quote_topics
from app.services.review_board_export import BUCKETS, _bucket, _uid

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VAULT = BACKEND_ROOT / "content_hub_vault"


def build_document(db: Session) -> tuple[str, dict[str, int]]:
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
    counts = {name: 0 for name, _, _ in BUCKETS}
    lines = [
        "# 金句人工复核总清单",
        "",
        f"> 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        f"> 共 {len(candidates)} 条；每条只勾选一个结论，拒绝/退回请写备注。",
        "> 本文档是汇总清单；逐条可点击复选框，完成后可按此文档统一回写。",
        "",
        "## 统计",
        "",
        "| 分档 | 数量 |",
        "|---|---:|",
    ]
    for name, _, _ in BUCKETS:
        counts[name] = sum(1 for q in candidates if _bucket(q.quality_score) == name)
    for name, _, _ in BUCKETS:
        lines.append(f"| {name} | {counts[name]} |")
    lines.extend(["", "---", ""])

    index = 0
    for bucket, _low, _high in BUCKETS:
        bucket_items = [q for q in candidates if _bucket(q.quality_score) == bucket]
        lines.extend([f"## {bucket}（{len(bucket_items)}）", ""])
        for quote in bucket_items:
            index += 1
            topics = _quote_topics(db, quote.quote_id)
            lines.extend(
                [
                    f"### {index}. {_uid(quote)} — {quote.quality_score} 分 / {quote.review_status or ''}",
                    "",
                    f"- UID：`{_uid(quote)}`",
                    f"- 分档：{bucket}",
                    f"- 来源：{quote.source or '（缺失）'}",
                    f"- 作者：{quote.author or '（缺失）'}",
                    f"- 主题：{'、'.join(topics) or '（未关联）'}",
                    "",
                    f"> {quote.content}",
                    "",
                    "- [ ] 通过",
                    "- [ ] 拒绝",
                    "- [ ] 退回修改",
                    "",
                    "- 备注：",
                    "",
                ]
            )
    return "\n".join(lines), counts


def main() -> int:
    parser = argparse.ArgumentParser(description="生成人工复核总清单")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    args = parser.parse_args()

    db = SessionLocal()
    try:
        content, counts = build_document(db)
    finally:
        db.close()

    board = Path(args.vault) / "00-收件箱" / "审核看板"
    board.mkdir(parents=True, exist_ok=True)
    out = board / "人工复核总清单_391.md"
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(out)
    print(json.dumps({
        "ok": True,
        "path": str(out),
        "total": sum(counts.values()),
        "buckets": counts,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
