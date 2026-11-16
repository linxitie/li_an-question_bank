#!/usr/bin/env python3
"""外部授权金句源采集（默认 dry-run）。"""
from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.services.quote_external_collector import collect_external_quotes


def main() -> int:
    parser = argparse.ArgumentParser(description="外部金句源采集")
    parser.add_argument("--limit-articles", type=int, default=0, help="每个来源最多文章数，0 用配置")
    parser.add_argument("--apply", action="store_true", help="写入数据库")
    args = parser.parse_args()
    limit = args.limit_articles or None
    db = SessionLocal()
    try:
        reports = collect_external_quotes(db, dry_run=not args.apply, max_articles=limit)
    finally:
        db.close()
    print(json.dumps({"apply": args.apply, "reports": reports}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
