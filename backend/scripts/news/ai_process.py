#!/usr/bin/env python3
"""R2.2 新闻 AI 处理 CLI。"""
from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.models.models import NewsArticle
from app.services.news_ai_service import process_news


def main() -> int:
    parser = argparse.ArgumentParser(description="新闻 AI 摘要/考点/实体/合规")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if not args.apply:
            count = (
                db.query(NewsArticle)
                .filter(NewsArticle.ai_summary.is_(None))
                .filter(NewsArticle.review_status.in_(("pending", "high_risk")))
                .count()
            )
            print(json.dumps({"apply": False, "candidates": count}, ensure_ascii=False))
            return 0
        report = process_news(db, limit=args.limit)
    finally:
        db.close()
    print(json.dumps({"apply": True, **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
