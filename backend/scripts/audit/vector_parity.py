#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F6 local / Milvus 检索一致性抽样。

同一批题目用同一 EmbeddingPort 编码，分别查 local 与 Milvus 的 top-10，
计算逐条重合率；Milvus 不可用时明确报错，不把未执行写成通过。
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
from app.foundation.ports.ai import build_embedding_port  # noqa: E402
from app.foundation.stores.local_vector import LocalVectorStore  # noqa: E402
from app.foundation.stores.milvus_vector import MilvusVectorStore  # noqa: E402
from app.foundation.vector_builder import expected_records  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F6 向量检索一致性抽样")
    parser.add_argument("--db", default=None)
    parser.add_argument("--collection", default=None)
    parser.add_argument("--sample", type=int, default=100)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--embedding-provider", default=None,
                        choices=("off", "hash", "http"))
    args = parser.parse_args(argv)
    if args.sample < 1 or args.top_k < 1:
        print(json.dumps({"ok": False, "error": "sample/top-k 必须为正整数"},
                         ensure_ascii=False))
        return 2

    db = Path(args.db).resolve() if args.db else cfg.sqlite_path()
    engine = create_engine(f"sqlite:///{db}")
    collection = args.collection or cfg.VECTOR_COLLECTION
    local = LocalVectorStore(cfg.vector_store_root(), dim=cfg.VECTOR_DIM,
                             max_top_k=cfg.VECTOR_SEARCH_TOP_K_MAX)
    milvus = MilvusVectorStore(
        uri=cfg.VECTOR_MILVUS_URI, token=cfg.VECTOR_MILVUS_TOKEN or "",
        prefix=cfg.VECTOR_MILVUS_PREFIX, dim=cfg.VECTOR_DIM,
        max_top_k=cfg.VECTOR_SEARCH_TOP_K_MAX,
    )
    try:
        embedding = build_embedding_port(args.embedding_provider)
        if embedding.provider == "off":
            print(json.dumps({"ok": False,
                              "error": "Embedding 未启用；请用 --embedding-provider hash 做离线一致性验证"},
                             ensure_ascii=False))
            return 2
        with Session(engine) as session:
            records = expected_records(session)
        if not records:
            print(json.dumps({"ok": False, "error": "SoT 没有可抽样题目"},
                             ensure_ascii=False))
            return 2
        step = max(1, len(records) // args.sample)
        sample = records[::step][:args.sample]
        ratios: list[float] = []
        missing_local = 0
        missing_milvus = 0
        for record in sample:
            vector = embedding.embed([record.text])[0]
            left = local.search(collection, vector, top_k=args.top_k)
            right = milvus.search(collection, vector, top_k=args.top_k)
            left_ids = {hit.id for hit in left}
            right_ids = {hit.id for hit in right}
            if not left_ids:
                missing_local += 1
            if not right_ids:
                missing_milvus += 1
            if left_ids or right_ids:
                ratios.append(len(left_ids & right_ids) / len(left_ids | right_ids))
        average = sum(ratios) / len(ratios) if ratios else 0.0
        payload = {
            "ok": average >= 0.95 and missing_local == 0 and missing_milvus == 0,
            "collection": collection, "sample": len(sample), "top_k": args.top_k,
            "embedding": embedding.provider, "average_jaccard": round(average, 4),
            "threshold": 0.95, "missing_local": missing_local,
            "missing_milvus": missing_milvus,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1
    except Exception as exc:  # noqa: BLE001 — 明确失败
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
