#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""F4 文档回填：把 SoT 中的既有数据写入 DocumentStore。

默认 dry-run，只统计不写入；--apply 才真正写。version 固定为 1（与增量
事件的 outbox id 区分），因此重复执行不会覆盖已由事件投影写入的文档。
支持按集合、按条数、断点续跑。文档库不可用时整体失败退出，不假装成功。

用法：
  python backend/scripts/foundation/backfill_documents.py
  python backend/scripts/foundation/backfill_documents.py --apply --collection all
  python backend/scripts/foundation/backfill_documents.py --apply --limit 100
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.foundation.config import DOC_STORE_MAX_BYTES, sqlite_path  # noqa: E402
from app.foundation.document_reconcile import (  # noqa: E402
    COLLECTIONS,
    iter_sources,
)
from app.foundation.stores.document import (  # noqa: E402
    build_document_store,
    canonical_json,
)

BATCH = 200


def _sort_tuple(collection: str, key: str) -> tuple[int, int] | None:
    """把 key 变成可比较断点；import key 形如 table:id。"""
    try:
        if collection == "import_snapshots":
            table, _, raw_id = key.partition(":")
            rank = 0 if table == "question_import_record" else 1
            return rank, int(raw_id)
        return 0, int(key)
    except (TypeError, ValueError):
        return None


def _read_cursor(session: Session, source: str) -> str:
    row = session.execute(
        text("SELECT cursor FROM foundation_backfill_state WHERE source=:source"),
        {"source": source},
    ).first()
    return str(row[0]) if row and row[0] else ""


def _write_state(session: Session, source: str, cursor: str, total: int, done: int) -> None:
    session.execute(
        text(
            """INSERT INTO foundation_backfill_state
                   (source, cursor, total, done, updated_at)
               VALUES (:source, :cursor, :total, :done, :updated_at)
               ON CONFLICT(source) DO UPDATE SET
                   cursor=excluded.cursor, total=excluded.total,
                   done=excluded.done, updated_at=excluded.updated_at"""
        ),
        {
            "source": source,
            "cursor": cursor,
            "total": total,
            "done": done,
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        },
    )
    session.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="F4 文档回填")
    parser.add_argument("--db", default=None)
    parser.add_argument(
        "--collection", default="all", choices=["all", *COLLECTIONS],
        help="all 或单个集合",
    )
    parser.add_argument("--limit", type=int, default=None, help="每个集合最多处理条数")
    parser.add_argument("--apply", action="store_true", help="真正写入；默认 dry-run")
    args = parser.parse_args(argv)

    targets = list(COLLECTIONS) if args.collection == "all" else [args.collection]
    db = Path(args.db).resolve() if args.db else sqlite_path()
    engine = create_engine(f"sqlite:///{db}")
    store = build_document_store()
    health = store.health()
    if not health.ok:
        print(json.dumps({"ok": False, "error": "文档库不可用", "detail": health.detail},
                         ensure_ascii=False))
        return 2

    summary: dict[str, dict[str, int]] = {}
    failures = 0
    try:
        with Session(engine) as session:
            for collection in targets:
                source = f"document:{collection}"
                cursor = _read_cursor(session, source)
                cursor_tuple = _sort_tuple(collection, cursor) if cursor else None
                stats = {"total": 0, "written": 0, "planned": 0, "unchanged": 0,
                         "skipped": 0, "skipped_too_large": 0, "failed": 0}
                last_key = cursor
                done = 0
                for key, builder in iter_sources(session, collection, args.limit):
                    key_tuple = _sort_tuple(collection, key)
                    if cursor_tuple is not None and key_tuple is not None:
                        if key_tuple <= cursor_tuple:
                            continue
                    stats["total"] += 1
                    doc = builder()
                    if doc is None:
                        stats["skipped"] += 1
                        last_key = key
                        continue
                    size = len(canonical_json(doc).encode("utf-8"))
                    if size > DOC_STORE_MAX_BYTES:
                        stats["skipped_too_large"] += 1
                        last_key = key
                        continue
                    if not args.apply:
                        stats["planned"] += 1
                        last_key = key
                        continue
                    try:
                        changed = store.upsert(collection, key, doc, version=1)
                    except Exception as exc:  # noqa: BLE001 — 单条失败继续，最终非零退出
                        stats["failed"] += 1
                        failures += 1
                        print(json.dumps({"collection": collection, "key": key,
                                          "error": f"{type(exc).__name__}: {exc}"},
                                         ensure_ascii=False), file=sys.stderr)
                    else:
                        stats["written" if changed else "unchanged"] += 1
                        last_key = key
                    done += 1
                    if done % BATCH == 0:
                        _write_state(session, source, last_key, stats["total"], done)
                if args.apply:
                    _write_state(session, source, last_key, stats["total"], done)
                summary[collection] = stats
    except Exception as exc:  # noqa: BLE001 — 明确失败
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                         ensure_ascii=False))
        return 2

    print(json.dumps({
        "ok": failures == 0, "apply": bool(args.apply),
        "backend": health.backend, "collections": summary,
    }, ensure_ascii=False, indent=2))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
