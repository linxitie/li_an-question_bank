#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""媒体孤儿 GC：只删「无任何 active 行引用 + 超过宽限期」的本地对象。

安全边界：
- 默认 dry-run，必须显式 --execute；
- 只处理 OBJECT_STORE_BACKEND=local；MinIO 无 LastModified 时拒绝删除；
- 只扫描对象存储根目录，不碰 static/、uploads/、data/*.bak（R7/R8）；
- 单次最多 batch 条（默认 500），先算后删，删除失败逐条报告。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.foundation.config import (  # noqa: E402
    MEDIA_ORPHAN_GRACE_DAYS,
    OBJECT_STORE_ROOT,
    object_store_root,
    sqlite_path,
)
from app.foundation.stores.local_object import LocalObjectStore  # noqa: E402
from app.foundation.stores.object import normalize_key  # noqa: E402


def _candidates(session: Session, root: Path, grace_days: float, batch: int):
    refs = {
        row[0]
        for row in session.execute(
            text("SELECT object_key FROM media_assets WHERE status='active'")
        )
    }
    store = LocalObjectStore(root)
    now = time.time()
    picks, skipped_recent, orphan_total = [], 0, 0
    for key in store.list_keys(""):
        if key in refs:
            continue
        orphan_total += 1
        try:
            norm = normalize_key(key)
            path = root / norm
            age_days = (now - path.stat().st_mtime) / 86400.0
        except (OSError, ValueError):
            continue
        if age_days < grace_days:
            skipped_recent += 1
            continue
        picks.append({"key": norm, "age_days": round(age_days, 2),
                      "size": path.stat().st_size})
        if len(picks) >= batch:
            break
    return picks, orphan_total, skipped_recent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="媒体孤儿 GC（默认 dry-run）")
    parser.add_argument("--db", default=None)
    parser.add_argument("--root", default=None, help="local 对象根，默认 OBJECT_STORE_ROOT")
    parser.add_argument("--grace-days", type=float, default=MEDIA_ORPHAN_GRACE_DAYS)
    parser.add_argument("--batch", type=int, default=500)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    from app.foundation import config as cfg

    if (cfg.OBJECT_STORE_BACKEND or "local").lower() != "local":
        print(json.dumps({"ok": False, "error": "MinIO 孤儿缺 LastModified，F3 不自动删；"
                          "请人工核对 ListObjectsV2 后再处理"}, ensure_ascii=False))
        return 2
    root = Path(args.root).resolve() if args.root else object_store_root()
    if not root.exists():
        print(json.dumps({"ok": True, "dry_run": not args.execute, "deleted": 0,
                          "candidates": 0, "note": "对象根不存在"}, ensure_ascii=False))
        return 0
    db = Path(args.db).resolve() if args.db else sqlite_path()
    engine = create_engine(f"sqlite:///{db}")
    with Session(engine) as session:
        picks, orphan_total, skipped_recent = _candidates(
            session, root, max(0.0, args.grace_days), max(1, args.batch)
        )
    deleted, failed = [], []
    if args.execute:
        store = LocalObjectStore(root)
        for item in picks:
            try:
                if store.delete(item["key"]):
                    deleted.append(item["key"])
            except Exception as exc:
                failed.append({"key": item["key"], "error": f"{type(exc).__name__}: {exc}"})
    print(json.dumps({
        "ok": not failed, "dry_run": not args.execute, "root": str(root),
        "grace_days": args.grace_days, "batch": args.batch,
        "orphan_total": orphan_total, "candidates": len(picks),
        "skipped_recent": skipped_recent, "deleted": len(deleted),
        "failed": failed,
        "preview": [] if args.execute else picks[:20],
    }, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
