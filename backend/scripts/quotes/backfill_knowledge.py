#!/usr/bin/env python3
"""回填金句来源、标签与 FTS 索引（可重复执行）。"""
from __future__ import annotations

import json

from app.core.database import SessionLocal, engine
from app.services.quote_knowledge_service import (
    backfill_quote_knowledge,
    ensure_quote_knowledge_schema,
)


def main() -> int:
    ensure_quote_knowledge_schema(engine)
    db = SessionLocal()
    try:
        report = backfill_quote_knowledge(db)
    finally:
        db.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
