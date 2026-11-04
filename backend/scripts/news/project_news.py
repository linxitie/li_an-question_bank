#!/usr/bin/env python3
"""R2.4 新闻图/向量投影 CLI。"""

from __future__ import annotations

import argparse
import json

from app.core.database import SessionLocal
from app.services.news_projection import (
    project_documents,
    project_graph,
    project_media_assets,
    project_objects,
    project_vectors_safe,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", action="store_true")
    parser.add_argument("--vectors", action="store_true")
    parser.add_argument("--documents", action="store_true", help="写 F4 news_contents")
    parser.add_argument("--objects", action="store_true", help="写 F3 新闻图片对象")
    parser.add_argument("--media-assets", action="store_true", help="登记 F3 media_assets")
    parser.add_argument(
        "--provider", default="auto", help="auto/off/hash/http；auto 不可用时降级 FTS"
    )
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    selected = any((args.graph, args.vectors, args.documents, args.objects, args.media_assets))
    if not selected:
        # 默认做基础投影；语义向量必须显式 --vectors。
        args.graph = args.documents = args.objects = args.media_assets = True
    db = SessionLocal()
    try:
        result = {}
        if args.graph:
            result["graph"] = project_graph(db, reset=args.reset)
        if args.objects:
            result["objects"] = project_objects(db)
        if args.media_assets:
            result["media_assets"] = project_media_assets(db)
        if args.documents:
            result["documents"] = project_documents(db)
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
