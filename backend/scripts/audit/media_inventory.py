#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""媒体只读盘点：DB active 行 -> 对象存储，报告缺字节/大小不符/可选孤儿。

默认不写库、不删任何字节。需要让 L7-16 看到对账新鲜度时显式加 --record。

用法：
  python backend/scripts/audit/media_inventory.py
  python backend/scripts/audit/media_inventory.py --full --orphans --record
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.foundation import media_reconcile as mr  # noqa: E402
from app.foundation.config import MEDIA_ORPHAN_GRACE_DAYS, sqlite_path  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="媒体资产只读盘点")
    parser.add_argument("--db", default=None)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--full", action="store_true", help="不限制行数")
    parser.add_argument("--orphans", action="store_true", help="扫描对象存储孤儿")
    parser.add_argument("--record", action="store_true", help="写入 foundation_reconcile_run")
    args = parser.parse_args(argv)

    db = Path(args.db).resolve() if args.db else sqlite_path()
    engine = create_engine(f"sqlite:///{db}")
    try:
        with Session(engine) as session:
            run = mr.inventory(
                session, limit=None if args.full else args.limit,
                include_orphans=args.orphans, mode="full" if args.full else "sample",
            )
            if args.record:
                mr.record(session, run)
    except Exception as exc:  # 明确失败，不假装成功
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 2
    print(json.dumps({
        "ok": run.status != "drift", "run_id": run.run_id, "status": run.status,
        "checked": run.checked, "missing_blob": run.missing_blob,
        "size_mismatch": run.size_mismatch, "orphans": run.orphans,
        "orphan_bytes": run.orphan_bytes, "orphan_error": run.orphan_error,
        "report": run.report_path, "recorded": bool(args.record),
        "orphan_grace_days": MEDIA_ORPHAN_GRACE_DAYS,
    }, ensure_ascii=False, indent=2))
    return 0 if run.status != "drift" else 1


if __name__ == "__main__":
    raise SystemExit(main())
