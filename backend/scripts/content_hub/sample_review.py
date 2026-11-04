#!/usr/bin/env python3
"""从审核看板抽取人工校准样本，生成 Obsidian Markdown（只读，不改状态）。

用法（在 backend 目录）：
    python -m scripts.content_hub.sample_review
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.models import EssayQuote
from app.services.obsidian_export import _quote_topics
from app.services.scout_rule_service import score_quote

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VAULT = BACKEND_ROOT / "content_hub_vault"


def _take(db: Session, lo: float, hi: float, n: int, rng: random.Random) -> list[EssayQuote]:
    quotes = (
        db.query(EssayQuote)
        .filter(EssayQuote.quality_score >= lo, EssayQuote.quality_score < hi)
        .all()
    )
    pending = [q for q in quotes if q.review_status == "pending"]
    published = [q for q in quotes if q.review_status == "published"]
    half = n // 2
    n_pending = min(len(pending), half)
    n_pub = min(len(published), n - n_pending)
    if n_pub < n - n_pending:
        n_pending = min(len(pending), n - n_pub)
    picked = rng.sample(pending, n_pending) + rng.sample(published, n_pub)
    used = {q.quote_id for q in picked}
    rest = [q for q in quotes if q.quote_id not in used]
    if len(picked) < n:
        picked += rng.sample(rest, min(len(rest), n - len(picked)))
    return picked


def _block(db: Session, quote: EssayQuote, bucket: str, index: int) -> str:
    result = score_quote(db, quote)
    topics = _quote_topics(db, quote.quote_id)
    signals = result.signals
    reasons = "、".join(result.reasons) or "无"
    lines = [
        f"### {index}. [[{bucket}/{quote.quote_uid}]] — {quote.quality_score} 分 / {quote.review_status}",
        "",
        f"- UID：`{quote.quote_uid}`",
        f"- 来源：{quote.source or '（缺失）'}",
        f"- 作者：{quote.author or '（缺失）'}",
        f"- 主题：{'、'.join(topics) or '（未关联）'}",
        f"- Scout 信号：长度 {signals.get('length')}，来源可信度 {signals.get('source_trust')}，"
        f"重复组 {signals.get('duplicate_count')}，扣分原因：{reasons}",
        "",
        f"> {quote.content}",
        "",
        "**人工结论（只勾一项）**",
        "",
        "- [ ] 通过",
        "- [ ] 拒绝",
        "- [ ] 退回修改",
        "",
        "- 备注：",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="抽取人工校准样本")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--seed", type=int, default=20261031)
    parser.add_argument("--n2", type=int, default=20)
    parser.add_argument("--n3", type=int, default=10)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    db = SessionLocal()
    try:
        sample2 = _take(db, 70, 80, args.n2, rng)
        sample3 = _take(db, 60, 70, args.n3, rng)
        for quote in sample2 + sample3:
            db.expire(quote)
        blocks2 = [_block(db, q, "02-重点复核", i + 1) for i, q in enumerate(sample2)]
        blocks3 = [_block(db, q, "03-建议拒绝", i + 1) for i, q in enumerate(sample3)]
    finally:
        db.close()

    today = date.today().strftime("%Y%m%d")
    out_dir = Path(args.vault) / "00-收件箱" / "审核看板" / "抽样校准"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"抽样审核包_{today}.md"
    header = [
        f"# 抽样审核包（{date.today().isoformat()}）",
        "",
        f"> 02-重点复核：{len(sample2)} 条；03-建议拒绝：{len(sample3)} 条。",
        "> 目的：校准人工标准，不修改 DB 状态；确认后再批量处理。",
        "",
        "## 判定标准草案（可先填这里）",
        "",
        "- 通过：",
        "- 拒绝：",
        "- 退回修改：",
        "",
        "---",
        "",
        "## 02-重点复核 抽样",
        "",
        *blocks2,
        "---",
        "",
        "## 03-建议拒绝 抽样",
        "",
        *blocks3,
    ]
    out.write_text("\n".join(header), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "path": str(out),
        "total": len(sample2) + len(sample3),
        "02": len(sample2),
        "03": len(sample3),
        "seed": args.seed,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
