#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F6 向量只读盘点：SoT 期望 id/内容哈希 vs VectorStore。

默认抽样 100 条比对元数据；--full 全量比对。--record 才写
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

from app.foundation import config as cfg  # noqa: E402
from app.foundation import vector_reconcile as vr  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F6 向量只读盘点")
    parser.add_argument("--db", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--collection", default=None)
    parser.add_argument("--sample", type=int, default=100, help="抽样条数")
    parser.add_argument("--full", action="store_true", help="全量比较 id/元数据")
    parser.add_argument("--record", action="store_true", help="写入 foundation_reconcile_run")
    args = parser.parse_args(argv)

    db = Path(args.db).resolve() if args.db else cfg.sqlite_path()
    engine = create_engine(f"sqlite:///{db}")
    try:
        with Session(engine) as session:
            run = vr.inspect(
                session, mode="full" if args.full else "sample",
                sample=args.sample, limit=args.limit, collection=args.collection,
            )
            if args.record:
                vr.record(session, run)
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
