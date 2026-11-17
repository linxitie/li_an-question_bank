#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""四库（关系/图/文档/向量）重建与 K1–K7 校验（v6.0 M1）。

关系库（SQLite）是唯一事实源；图/文档/向量都是**可重建投影**。本脚本只读 SoT
并写三类投影，不修改任何业务表；校验失败即非零退出，供门禁与人工复核共用。

用法（在 backend/ 下执行）：
  python scripts/qbdm/rebuild_foundation.py --store all --verify
  python scripts/qbdm/rebuild_foundation.py --store graph --reset
  python scripts/qbdm/rebuild_foundation.py --store vector --limit 200      # 小批试跑
  python scripts/qbdm/rebuild_foundation.py --verify-only                   # 只校验

向量库默认 EMBEDDING_PROVIDER=off（不产生向量）。本脚本在 provider=off 时
自动切到 hash（离线确定性 n-gram），保证"零外部调用也能灌满向量库"。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.foundation import config as cfg  # noqa: E402
from app.foundation import invariants, question_documents  # noqa: E402
from app.foundation.graph_builder import apply_plan as apply_graph_plan  # noqa: E402
from app.foundation.graph_builder import build_graph  # noqa: E402
from app.foundation.ports.ai import build_embedding_port  # noqa: E402
from app.foundation.stores.document import build_document_store  # noqa: E402
from app.foundation.stores.graph import build_graph_store  # noqa: E402
from app.foundation.stores.vector import build_vector_store  # noqa: E402
from app.foundation.vector_builder import (  # noqa: E402
    apply_plan as apply_vector_plan,
    build_vector_plan,
)

AUDIT_DIR = BACKEND_DIR / "data" / "audit"


def _open_graph():
    if cfg.GRAPH_BACKEND == "off":
        print("! GRAPH_BACKEND=off，跳过图库")
        return None
    try:
        return build_graph_store()
    except Exception as exc:  # noqa: BLE001 - 依赖缺失时如实降级
        print(f"! 图库不可用：{exc}")
        return None


def _open_document():
    if cfg.DOC_STORE_BACKEND == "off":
        print("! DOC_STORE_BACKEND=off，跳过文档库")
        return None
    try:
        return build_document_store()
    except Exception as exc:  # noqa: BLE001
        print(f"! 文档库不可用：{exc}")
        return None


def _open_vector():
    if cfg.VECTOR_BACKEND == "off":
        print("! VECTOR_BACKEND=off，跳过向量库")
        return None
    try:
        return build_vector_store()
    except Exception as exc:  # noqa: BLE001
        print(f"! 向量库不可用：{exc}")
        return None


def _embedding_port():
    """provider=off 时用 hash（离线确定性）——仍然零外部调用。"""
    provider = (cfg.EMBEDDING_PROVIDER or "off").strip().lower()
    if provider == "off" or not cfg.EMBEDDING_ENABLED:
        # 显式传 "hash"：config 在 EMBEDDING_ENABLED=false 时会把"不传参"解释成 off
        print("· EMBEDDING_PROVIDER=off/degraded → 本次用 hash（离线 n-gram，可重建）")
        return build_embedding_port("hash"), "hash"
    return build_embedding_port(provider), provider


def rebuild_graph(session, *, limit, reset: bool) -> dict:
    store = _open_graph()
    if store is None:
        return {"store": "graph", "skipped": True}
    plan = build_graph(session, limit=limit)
    print(f"· 图计划：节点 {len(plan.nodes)}（{plan.node_counts()}），边 {len(plan.edges)}（{plan.edge_counts()}）")
    result = apply_graph_plan(store, plan, reset=reset)
    result.update({"store": "graph", "collection": "foundation_graph", "skipped": False})
    print(f"· 图写入：{result}")
    return result


def rebuild_document(session, *, limit, reset: bool) -> dict:
    store = _open_document()
    if store is None:
        return {"store": "document", "skipped": True}
    version = int(time.time() * 1000)
    result = question_documents.project(session, store, limit=limit, reset=reset, version=version)
    result.update({"store": "document", "collection": question_documents.COLLECTION,
                   "version": version, "skipped": False})
    print(f"· 文档写入：{result}")
    return result


def rebuild_vector(session, *, limit, reset: bool) -> dict:
    store = _open_vector()
    if store is None:
        return {"store": "vector", "skipped": True}
    port, provider = _embedding_port()
    plan = build_vector_plan(session, port, limit=limit)
    print(f"· 向量计划：{plan.planned} 条（provider={provider}, dim={cfg.EMBEDDING_DIM}）")
    result = apply_vector_plan(store, plan, reset=reset)
    result.update({"store": "vector", "collection": plan.collection,
                   "provider": provider, "skipped": False})
    print(f"· 向量写入：{result}")
    return result


def verify(session, *, graph, document, vector) -> dict:
    report = invariants.run_all(
        session,
        graph_store=graph,
        document_store=document,
        vector_store=vector,
    )
    print()
    print("== K1–K7 ==")
    for item in report["checks"]:
        flag = "PASS" if item["ok"] else "FAIL"
        if item["status"] == "skipped":
            flag = "SKIP"
        print(f"[{flag}] {item['identity']} 期望={item['expected']} 实际={item['actual']} {item['note']}")
    return report


def write_report(payload: dict) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / f"foundation_rebuild_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="四库重建 + K1–K7 校验")
    parser.add_argument("--store", choices=["graph", "document", "vector", "all"], default="all")
    parser.add_argument("--reset", action="store_true", help="先清空目标投影（可重建）")
    parser.add_argument("--limit", type=int, default=None, help="只处理前 N 条（小批试跑）")
    parser.add_argument("--verify", action="store_true", help="重建后校验")
    parser.add_argument("--verify-only", action="store_true", help="只校验，不重建")
    args = parser.parse_args()

    print(f"· 开关：GRAPH_BACKEND={cfg.GRAPH_BACKEND} DOC_STORE_BACKEND={cfg.DOC_STORE_BACKEND} "
          f"VECTOR_BACKEND={cfg.VECTOR_BACKEND} EMBEDDING_PROVIDER={cfg.EMBEDDING_PROVIDER}")

    graph = _open_graph()
    document = _open_document()
    vector = _open_vector()

    session = SessionLocal()
    payload: dict = {"stores": [], "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        if not args.verify_only:
            if args.store in ("graph", "all"):
                payload["stores"].append(rebuild_graph(session, limit=args.limit, reset=args.reset))
            if args.store in ("document", "all"):
                payload["stores"].append(rebuild_document(session, limit=args.limit, reset=args.reset))
            if args.store in ("vector", "all"):
                payload["stores"].append(rebuild_vector(session, limit=args.limit, reset=args.reset))

        if args.verify or args.verify_only:
            report = verify(session, graph=graph, document=document, vector=vector)
            payload["invariants"] = report
            path = write_report(payload)
            print()
            print(f"报告：{path}")
            if not report["ok"]:
                raise SystemExit(1)
        else:
            path = write_report(payload)
            print()
            print(f"报告：{path}")
    finally:
        session.close()


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    main()
