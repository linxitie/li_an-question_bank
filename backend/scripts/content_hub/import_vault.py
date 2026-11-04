#!/usr/bin/env python3
"""原始金句素材库导入 CLI（默认 dry-run，最多 5 条）。

用法（在 backend 目录）：
    python -m scripts.content_hub.import_vault --limit 5
    python -m scripts.content_hub.import_vault --limit 5 --apply
    python -m scripts.content_hub.import_vault --all --apply
"""
from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.services.vault_import_service import import_vault

DEFAULT_VAULT = r"D:\砺安题库\li_an-question_bank\每日金句知识库"


def main() -> int:
    parser = argparse.ArgumentParser(description="金句素材库导入")
    parser.add_argument("--vault", default=DEFAULT_VAULT)
    parser.add_argument("--subdir", default="01-金句素材库")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--all", action="store_true", help="不限制条数")
    parser.add_argument("--apply", action="store_true", help="真正写库；默认 dry-run")
    args = parser.parse_args()

    limit = None if args.all else args.limit
    db = SessionLocal()
    try:
        report = import_vault(
            db,
            args.vault,
            subdir=args.subdir,
            limit=limit,
            apply=bool(args.apply),
        )
    finally:
        db.close()

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
