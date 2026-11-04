#!/usr/bin/env python3
"""把旧规则误拒、但新 Scout 分已过线的金句恢复为 pending。

用法（在 backend 目录）：
    python -m scripts.content_hub.reopen_rejected --dry-run
    python -m scripts.content_hub.reopen_rejected --apply
"""
from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.models.models import EssayQuote, QuoteReview


def reopen_rejected(db, min_score: float = 60.0, apply: bool = False) -> dict:
    quotes = (
        db.query(EssayQuote)
        .filter(
            EssayQuote.review_status == "rejected",
            EssayQuote.quality_score >= min_score,
        )
        .all()
    )
    if apply:
        for quote in quotes:
            quote.review_status = "pending"
            quote.status = 0
            db.add(
                QuoteReview(
                    quote_id=quote.quote_id,
                    reviewer_id=None,
                    action="reopen_by_recalibration",
                    reason=f"Scout recalibration: score {quote.quality_score} >= {min_score}",
                    diff_json=json.dumps(
                        {"from": "rejected", "to": "pending", "score": quote.quality_score},
                        ensure_ascii=False,
                    ),
                )
            )
        db.commit()

    return {
        "apply": apply,
        "min_score": min_score,
        "reopened": len(quotes),
        "remaining_rejected": db.query(EssayQuote)
        .filter(EssayQuote.review_status == "rejected")
        .count(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="恢复被旧规则误拒的金句")
    parser.add_argument("--min-score", type=float, default=60.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply and args.dry_run:
        parser.error("--apply and --dry-run cannot be used together")

    db = SessionLocal()
    try:
        report = reopen_rejected(db, min_score=args.min_score, apply=bool(args.apply))
    finally:
        db.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
