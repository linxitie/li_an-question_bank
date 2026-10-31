#!/usr/bin/env python3
"""R1 Obsidian 审核收件箱回写 CLI。

用法（在 backend 目录）：
    python -m scripts.content_hub.sync_review --dry-run
    python -m scripts.content_hub.sync_review
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.core.database import SessionLocal
from app.services.obsidian_sync import sync_review_inbox

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VAULT = os.environ.get("OBSIDIAN_VAULT_PATH") or str(BACKEND_ROOT / "content_hub_vault")


def main() -> int:
    parser = argparse.ArgumentParser(description="Obsidian 审核收件箱回写")
    parser.add_argument("--vault", default=DEFAULT_VAULT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = sync_review_inbox(db, Path(args.vault), dry_run=args.dry_run)
    finally:
        db.close()

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
