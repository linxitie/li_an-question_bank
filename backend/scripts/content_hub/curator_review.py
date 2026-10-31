#!/usr/bin/env python3
"""R1 Curator LLM 复核（默认 dry-run，只读看板笔记）。

用法（在 backend 目录）：
    python -m scripts.content_hub.curator_review --limit 3 --dry-run
    python -m scripts.content_hub.curator_review --limit 3 --apply

LLM 配置（由用户本人填写，不要把密钥写进仓库）：
    LLM_API_URL=http://...
    LLM_API_KEY=...
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.database import SessionLocal
from app.services.curator_service import review_notes

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VAULT = BACKEND_ROOT / "content_hub_vault"


def main() -> int:
    parser = argparse.ArgumentParser(description="Curator LLM 审核看板复核")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--bucket", default="02-重点复核")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="只预览，不写回笔记（默认）")
    parser.add_argument("--apply", action="store_true", help="把结果写回笔记 frontmatter；不改 DB 状态")
    args = parser.parse_args()
    if args.apply and args.dry_run:
        parser.error("--apply and --dry-run cannot be used together")

    db = SessionLocal()
    try:
        report = review_notes(
            db,
            Path(args.vault),
            bucket=args.bucket,
            limit=None if args.all else args.limit,
            apply=bool(args.apply),
        )
    finally:
        db.close()

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
