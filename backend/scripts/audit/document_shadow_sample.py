#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F4 文档双读抽样：随机抽样重算 SoT 与文档库比较，差异写 JSONL。

默认 100 条、固定随机种子（可复现），只读不修复。--write-report 时把
汇总写到 data/reports/foundation/document_shadow_summary.json。
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.foundation import document_shadow as ds  # noqa: E402
from app.foundation.config import BACKEND_DIR, sqlite_path  # noqa: E402
from app.foundation.document_reconcile import COLLECTIONS, iter_sources  # noqa: E402

SUMMARY_PATH = BACKEND_DIR / "data" / "reports" / "foundation" / "document_shadow_summary.json"


def _keys(session: Session, collection: str) -> list[str]:
    return [key for key, _ in iter_sources(session, collection)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F4 文档双读抽样")
    parser.add_argument("--db", default=None)
    parser.add_argument("--sample", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args(argv)

    db = Path(args.db).resolve() if args.db else sqlite_path()
    engine = create_engine(f"sqlite:///{db}")
    try:
        with Session(engine) as session:
            candidates = [
                (collection, key)
                for collection in COLLECTIONS
                for key in _keys(session, collection)
            ]
            picked = random.Random(args.seed).sample(
                candidates, min(args.sample, len(candidates))
            )
            summary = ds.compare_many(session, picked)
    except Exception as exc:  # noqa: BLE001 — 明确失败
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 2

    summary["ok"] = summary["mismatch"] == 0 and summary["error"] == 0
    summary["sample"] = len(picked)
    summary["seed"] = args.seed
    summary["at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    if args.write_report:
        SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY_PATH.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        summary["report"] = str(SUMMARY_PATH.relative_to(BACKEND_DIR))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
