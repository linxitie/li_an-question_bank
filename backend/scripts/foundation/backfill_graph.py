#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F5 图回填：从 SoT 重新生成节点/边并写入 GraphStore。

默认 dry-run，只统计不写入；--apply 才真正写；--reset 先清空图投影表。
图可重建，因此每次 apply 都把 version 写成 1（重复执行结果一致）。
GraphStore 不可用时整体失败退出，不假装成功。

用法：
  python backend/scripts/foundation/backfill_graph.py
  python backend/scripts/foundation/backfill_graph.py --apply
  python backend/scripts/foundation/backfill_graph.py --apply --reset
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

from app.foundation.config import sqlite_path  # noqa: E402
from app.foundation.graph_builder import apply_plan, build_graph  # noqa: E402
from app.foundation.stores.graph import build_graph_store  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F5 图回填")
    parser.add_argument("--db", default=None)
    parser.add_argument("--limit", type=int, default=None, help="最多处理多少个知识点")
    parser.add_argument("--apply", action="store_true", help="真正写入；默认 dry-run")
    parser.add_argument("--reset", action="store_true", help="先清空图投影再写入")
    args = parser.parse_args(argv)

    db = Path(args.db).resolve() if args.db else sqlite_path()
    engine = create_engine(f"sqlite:///{db}")
    try:
        store = build_graph_store()
        health = store.health()
        if not health.ok:
            print(json.dumps({"ok": False, "error": "图存储不可用", "detail": health.detail},
                             ensure_ascii=False))
            return 2
        with Session(engine) as session:
            plan = build_graph(session, limit=args.limit)
            result = {"nodes": plan.node_counts(), "edges": plan.edge_counts()}
            if not args.apply:
                print(json.dumps({"ok": True, "apply": False, "backend": health.backend,
                                  "planned": result}, ensure_ascii=False, indent=2))
                return 0
            stats = apply_plan(store, plan, reset=args.reset)
    except Exception as exc:  # noqa: BLE001 — 明确失败
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 2

    print(json.dumps({"ok": True, "apply": True, "reset": bool(args.reset),
                      "backend": health.backend, "planned": result, "written": stats},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
