#!/usr/bin/env python3
"""R0 Obsidian 投影导出 CLI。

用法（在 backend 目录）：
    python -m scripts.content_hub.export_obsidian --dry-run
    python -m scripts.content_hub.export_obsidian --vault "<仓库>/backend/content_hub_vault"
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.core.database import SessionLocal
from app.services.obsidian_export import export_all

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VAULT = os.environ.get("OBSIDIAN_VAULT_PATH") or str(BACKEND_ROOT / "content_hub_vault")


def main() -> int:
    parser = argparse.ArgumentParser(description="Obsidian 投影导出")
    parser.add_argument("--vault", default=DEFAULT_VAULT, help="Obsidian vault 根目录")
    parser.add_argument("--dry-run", action="store_true", help="只计算将写入的文件")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = export_all(db, Path(args.vault), dry_run=args.dry_run)
    finally:
        db.close()

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
