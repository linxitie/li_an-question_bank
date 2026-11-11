#!/usr/bin/env python3
"""招考官方来源采集（默认 dry-run）。"""
from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.services.recruitment_source_collector import collect_all_recruitment_sources


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        reports = collect_all_recruitment_sources(db, limit=args.limit, dry_run=not args.apply)
    finally:
        db.close()
    print(json.dumps({"apply": args.apply, "reports": reports}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
