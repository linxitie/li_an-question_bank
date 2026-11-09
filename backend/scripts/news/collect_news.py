#!/usr/bin/env python3
"""R2.1 新闻采集 CLI（默认 dry-run，只解析不入库）。

用法（backend 目录）：
    python -m scripts.news.collect_news --source beijing --limit 1
    python -m scripts.news.collect_news --source beijing --limit 1 --apply
"""

from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.services.news_collector import collect_all_sources, collect_source, source_by_code


def main() -> int:
    parser = argparse.ArgumentParser(description="新闻源采集")
    parser.add_argument("--source", default="", help="来源 code；留空表示全部")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument(
        "--scan-limit",
        type=int,
        default=0,
        help="列表扫描条数；0 表示 limit*3，用于跳过重复后继续找新新闻",
    )
    parser.add_argument("--apply", action="store_true", help="真正写库；默认 dry-run")
    args = parser.parse_args()
    scan_limit = args.scan_limit or max(args.limit * 3, args.limit)

    db = SessionLocal()
    try:
        if args.source:
            source = source_by_code(args.source)
            if not source:
                print(
                    json.dumps(
                        {"ok": False, "error": f"unknown source: {args.source}"}, ensure_ascii=False
                    )
                )
                return 2
            reports = [
                collect_source(
                    db,
                    source,
                    limit=args.limit,
                    scan_limit=scan_limit,
                    dry_run=not args.apply,
                )
            ]
        else:
            reports = collect_all_sources(
                db,
                limit=args.limit,
                scan_limit=scan_limit,
                dry_run=not args.apply,
            )
    finally:
        db.close()
    print(json.dumps({"apply": bool(args.apply), "reports": reports}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
