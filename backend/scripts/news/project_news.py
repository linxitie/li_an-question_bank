#!/usr/bin/env python3
"""R2.4 新闻图/向量投影 CLI。"""
from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.services.news_projection import project_graph, project_vectors_safe


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", action="store_true")
    parser.add_argument("--vectors", action="store_true")
    parser.add_argument("--provider", default="auto", help="auto/off/hash/http；auto 不可用时降级 FTS")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    if not args.graph and not args.vectors:
        args.graph = args.vectors = True
    db = SessionLocal()
    try:
        result = {}
        if args.graph:
            result["graph"] = project_graph(db, reset=args.reset)
        if args.vectors:
            result["vectors"] = project_vectors_safe(
                db,
                provider=args.provider,
                reset=args.reset,
            )
    finally:
        db.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
