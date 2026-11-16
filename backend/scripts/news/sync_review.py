#!/usr/bin/env python3
"""R2.3 新闻审核勾选回写 CLI。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.news_obsidian_sync import sync_news_review

DEFAULT_VAULT = Path(settings.VAULT_PATH_NEWS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        report = sync_news_review(db, Path(args.vault), dry_run=not args.apply)
    finally:
        db.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
