#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F5 图只读盘点：SoT 重算期望图 -> GraphStore，报告 drift。

默认抽样 100 个知识点；--full 全量比较节点/边 key；--record 才写
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

from app.foundation import graph_reconcile as gr  # noqa: E402
from app.foundation.config import sqlite_path  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F5 图只读盘点")
    parser.add_argument("--db", default=None)
    parser.add_argument("--limit", type=int, default=None, help="最多处理多少个知识点")
    parser.add_argument("--sample", type=int, default=100, help="抽样知识点数")
    parser.add_argument("--full", action="store_true", help="全量比较节点/边")
    parser.add_argument("--record", action="store_true", help="写入 foundation_reconcile_run")
    args = parser.parse_args(argv)

    db = Path(args.db).resolve() if args.db else sqlite_path()
    engine = create_engine(f"sqlite:///{db}")
    try:
        with Session(engine) as session:
            run = gr.inspect(
                session, mode="full" if args.full else "sample",
                sample=args.sample, limit=args.limit,
            )
            if args.record:
                gr.record(session, run)
    except Exception as exc:  # noqa: BLE001 — 明确失败
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 2
    print(json.dumps({
        "ok": run.status != "drift", "run_id": run.run_id, "status": run.status,
        "mode": run.mode, "checked": run.checked, "missing": run.missing,
        "mismatched": run.mismatched, "orphan": run.orphan,
        "sampled": run.sampled, "sample_mismatch": run.sample_mismatch,
        "report": run.report_path, "recorded": bool(args.record),
    }, ensure_ascii=False, indent=2))
    return 0 if run.status != "drift" else 1


if __name__ == "__main__":
    raise SystemExit(main())
