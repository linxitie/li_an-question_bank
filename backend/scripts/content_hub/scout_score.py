#!/usr/bin/env python3
"""R1 Scout 影子打分 CLI（规则版）。

用法（在 backend 目录）：
    python -m scripts.content_hub.scout_score --dry-run
    python -m scripts.content_hub.scout_score --all --dry-run
    python -m scripts.content_hub.scout_score --apply
"""
from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.services.scout_rule_service import scout_quotes


def main() -> int:
    parser = argparse.ArgumentParser(description="Scout 影子打分")
    parser.add_argument("--dry-run", action="store_true", help="只打分，不写 quality_score（默认）")
    parser.add_argument("--apply", action="store_true", help="把分数写入 essay_quote.quality_score")
    parser.add_argument("--all", action="store_true", help="包含已发布金句（默认只看 pending/draft）")
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    limit = None if args.all else args.limit
    db = SessionLocal()
    try:
        report = scout_quotes(
            db,
            include_all=args.all,
            limit=limit,
            apply=bool(args.apply),
        )
    finally:
        db.close()

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
