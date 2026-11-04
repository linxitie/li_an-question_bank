#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F6 向量回填。

默认 dry-run，只统计 SoT 期望条数，不写生产索引。
--apply 才写；生产语义索引要求 EMBEDDING_PROVIDER=http，防止哈希向量冒充语义索引。
--verify 使用临时目录 + HashEmbedding 做端到端验证，不触碰生产向量根。

用法：
  python backend/scripts/foundation/backfill_vectors.py
  python backend/scripts/foundation/backfill_vectors.py --apply --reset
  python backend/scripts/foundation/backfill_vectors.py --verify
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.foundation import config as cfg  # noqa: E402
from app.foundation.ports.ai import HashEmbedding, build_embedding_port  # noqa: E402
from app.foundation.stores.local_vector import LocalVectorStore  # noqa: E402
from app.foundation.stores.vector import build_vector_store  # noqa: E402
from app.foundation.vector_builder import (  # noqa: E402
    apply_plan,
    build_vector_plan,
    expected_records,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F6 向量回填")
    parser.add_argument("--db", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--collection", default=None)
    parser.add_argument("--apply", action="store_true", help="真正写入；默认 dry-run")
    parser.add_argument("--reset", action="store_true", help="先清空集合")
    parser.add_argument("--verify", action="store_true", help="临时根 + hash 端到端验证")
    args = parser.parse_args(argv)
    if args.reset and not args.apply:
        print(json.dumps({"ok": False, "error": "--reset 必须与 --apply 同时使用"},
                         ensure_ascii=False))
        return 2

    db = Path(args.db).resolve() if args.db else cfg.sqlite_path()
    engine = create_engine(f"sqlite:///{db}")
    collection = args.collection or cfg.VECTOR_COLLECTION
    try:
        with Session(engine) as session:
            if args.verify:
                root = Path(tempfile.mkdtemp(prefix="li-an-vector-verify-"))
                try:
                    store = LocalVectorStore(root, dim=cfg.VECTOR_DIM,
                                             max_top_k=cfg.VECTOR_SEARCH_TOP_K_MAX)
                    embedding = HashEmbedding(cfg.EMBEDDING_DIM)
                    plan = build_vector_plan(
                        session, embedding, collection=collection, limit=args.limit
                    )
                    stats = apply_plan(store, plan, reset=True)
                    payload = {
                        "ok": True, "verify": True, "degraded": True,
                        "embedding": "hash", "collection": collection,
                        "planned": stats["planned"], "written": stats["written"],
                        "count": store.count(collection), "root": str(root),
                    }
                    print(json.dumps(payload, ensure_ascii=False, indent=2))
                    return 0 if stats["planned"] == stats["written"] else 1
                finally:
                    shutil.rmtree(root, ignore_errors=True)

            if not args.apply:
                records = expected_records(session, limit=args.limit)
                print(json.dumps({
                    "ok": True, "apply": False, "collection": collection,
                    "planned": len(records), "backend": cfg.VECTOR_BACKEND,
                }, ensure_ascii=False, indent=2))
                return 0

            embedding = build_embedding_port()
            if embedding.provider != "http":
                print(json.dumps({
                    "ok": False,
                    "error": "生产语义索引要求 EMBEDDING_PROVIDER=http；"
                             "没有模型时请用 --verify 做临时 hash 验证",
                    "provider": embedding.provider,
                }, ensure_ascii=False))
                return 2
            store = build_vector_store()
            health = store.health()
            if not health.ok:
                print(json.dumps({"ok": False, "error": "向量存储不可用",
                                  "detail": health.detail}, ensure_ascii=False))
                return 2
            plan = build_vector_plan(
                session, embedding, collection=collection, limit=args.limit
            )
            stats = apply_plan(store, plan, reset=args.reset)
            payload = {
                "ok": True, "apply": True, "reset": bool(args.reset),
                "backend": health.backend, "collection": collection,
                "planned": stats["planned"], "written": stats["written"],
                "count": store.count(collection),
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
    except Exception as exc:  # noqa: BLE001 — 明确失败
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
