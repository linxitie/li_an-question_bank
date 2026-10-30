"""F4 双读校验：重算 SoT 文档与文档库副本比较，只写 JSONL 日志，不修复。

业务读路径不接这个模块；抽样脚本与人工排查使用。文档库不可用、损坏或
内容不一致都只返回结果并记日志，避免校验动作反过来影响业务。
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.foundation.config import BACKEND_DIR
from app.foundation.document_reconcile import document_hash
from app.foundation.document_schema import (
    build_exam_resource,
    build_forum_content,
    build_import_snapshot,
)
from app.foundation.stores.document import COLLECTIONS, build_document_store

REPORT_PATH = BACKEND_DIR / "data" / "reports" / "foundation" / "document_shadow.jsonl"
_LOCK = threading.Lock()


def _build_expected(session: Session, collection: str, key: str) -> dict[str, Any] | None:
    if collection == "exam_resources":
        return build_exam_resource(session, int(key))
    if collection == "forum_contents":
        return build_forum_content(session, int(key))
    if collection == "import_snapshots":
        source_table, _, raw_id = key.partition(":")
        if not raw_id.isdigit():
            raise ValueError(f"非法导入文档 key: {key}")
        return build_import_snapshot(session, source_table, int(raw_id))
    raise ValueError(f"未知文档集合: {collection}")


def compare(session: Session, collection: str, key: str) -> dict[str, Any]:
    """返回比较结果；任何异常都转成 status=error，不向调用方抛。"""
    result: dict[str, Any] = {
        "collection": collection,
        "key": key,
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    try:
        if collection not in COLLECTIONS:
            raise ValueError(f"未知文档集合: {collection}")
        expected = _build_expected(session, collection, key)
        if expected is None:
            result.update({"status": "skipped", "reason": "source_missing"})
            return result
        expected_hash = document_hash(expected)
        result["soT_hash"] = expected_hash
        stored = build_document_store().get(collection, key)
        if stored is None:
            result.update({"status": "mismatch", "reason": "missing_in_store"})
            _append(result)
            return result
        store_hash = document_hash(stored)
        result["store_hash"] = store_hash
        if store_hash == expected_hash:
            result["status"] = "ok"
        else:
            result.update({"status": "mismatch", "reason": "content_changed"})
            _append(result)
    except Exception as exc:  # noqa: BLE001 — 校验失败只记录，不打断业务
        result.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
        _append(result)
    return result


def compare_many(session: Session, items: list[tuple[str, str]]) -> dict[str, int]:
    summary = {"checked": 0, "ok": 0, "mismatch": 0, "skipped": 0, "error": 0}
    for collection, key in items:
        result = compare(session, collection, key)
        summary["checked"] += 1
        status = result["status"]
        if status in summary:
            summary[status] += 1
    return summary


def _append(result: dict[str, Any]) -> None:
    try:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "collection": result.get("collection"),
                "key": result.get("key"),
                "soT_hash": result.get("soT_hash"),
                "store_hash": result.get("store_hash"),
                "status": result.get("status"),
                "reason": result.get("reason"),
                "error": result.get("error"),
                "at": result.get("at"),
            },
            ensure_ascii=False,
        )
        with _LOCK, REPORT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        # 日志盘满/只读时也不影响调用方；控制台由脚本自行报告。
        return
