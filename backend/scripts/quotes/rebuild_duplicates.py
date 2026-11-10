#!/usr/bin/env python3
"""重建金句 normalized_hash 与 duplicate_of 关系。"""
from __future__ import annotations

import json

from app.core.database import SessionLocal
from app.services.quote_dedupe_service import rebuild_duplicate_relations


def main() -> int:
    db = SessionLocal()
    try:
        report = rebuild_duplicate_relations(db)
    finally:
        db.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
