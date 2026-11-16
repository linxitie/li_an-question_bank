#!/usr/bin/env python3
"""R0 Obsidian 投影导出 CLI（三个独立 Vault）。

用法（在 backend 目录）：
    python -m scripts.content_hub.export_obsidian --dry-run
    python -m scripts.content_hub.export_obsidian --apply
"""
from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.services.obsidian_export import export_all


def main() -> int:
    parser = argparse.ArgumentParser(description="Obsidian 投影导出")
    parser.add_argument("--dry-run", action="store_true", help="只计算将写入的文件")
    parser.add_argument("--apply", action="store_true", help="实际写入三个独立 Vault")
    args = parser.parse_args()
    if args.dry_run and args.apply:
        parser.error("--dry-run 与 --apply 不能同时使用")

    db = SessionLocal()
    try:
        # vault=None 时按 VAULT_PATH_QUOTE / VAULT_PATH_NEWS / VAULT_PATH_JOB 分流
        report = export_all(db, None, dry_run=not args.apply)
    finally:
        db.close()

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
