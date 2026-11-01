#!/usr/bin/env python3
"""R2.2 导出新闻审核卡片到 Obsidian。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.database import SessionLocal
from app.services.news_obsidian_export import export_news_board

DEFAULT_VAULT = Path(__file__).resolve().parents[2] / "content_hub_vault"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        report = export_news_board(db, Path(args.vault), dry_run=not args.apply)
    finally:
        db.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
