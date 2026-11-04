#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F4 文档只读盘点：SoT 重算文档 -> DocumentStore，报告 drift。

默认抽样 500 条且不扫孤儿；--full 全量并扫描孤儿；--record 才写
foundation_reconcile_run。drift 退出码 1，便于门禁/巡检识别。
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

from app.foundation import document_reconcile as dr  # noqa: E402
from app.foundation.config import sqlite_path  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F4 文档只读盘点")
    parser.add_argument("--db", default=None)
    parser.add_argument("--collection", default=None, choices=list(dr.COLLECTIONS))
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--full", action="store_true", help="不限制行数并扫描孤儿")
    parser.add_argument("--record", action="store_true", help="写入 foundation_reconcile_run")
    args = parser.parse_args(argv)

    db = Path(args.db).resolve() if args.db else sqlite_path()
    engine = create_engine(f"sqlite:///{db}")
    try:
        with Session(engine) as session:
            run = dr.inspect(
                session, collection=args.collection,
                limit=None if args.full else args.limit,
                mode="full" if args.full else "sample",
            )
            if args.record:
                dr.record(session, run)
    except Exception as exc:  # noqa: BLE001 — 明确失败
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 2
    print(json.dumps({
        "ok": run.status != "drift", "run_id": run.run_id, "status": run.status,
        "mode": run.mode, "checked": run.checked, "missing": run.missing,
        "mismatched": run.mismatched, "orphan": run.orphan,
        "skipped": run.skipped, "report": run.report_path,
        "recorded": bool(args.record),
    }, ensure_ascii=False, indent=2))
    return 0 if run.status != "drift" else 1


if __name__ == "__main__":
    raise SystemExit(main())
