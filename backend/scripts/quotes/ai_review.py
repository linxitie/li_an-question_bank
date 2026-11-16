#!/usr/bin/env python3
"""金句 AI 质量审核 CLI（默认 dry-run）。"""
from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.services.quote_ai_service import review_quotes


def main() -> int:
    parser = argparse.ArgumentParser(description="金句 AI 质量审核")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--apply", action="store_true", help="真正写入审核结果")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = review_quotes(db, limit=args.limit, apply=args.apply)
    finally:
        db.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
