"""媒体资产表（media_assets）的唯一 DDL 来源与结构校验。

DDL 在 backend/migrations/20261027_002_media_assets.sql；本模块只读取比对，
不复制 SQL，避免迁移与运行时两份定义漂移。F3 的媒体表独立于 F1 的 7 张
foundation 表（foundation/schema.py 保持原样）。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.foundation.config import MEDIA_DDL_FILE

MEDIA_TABLE_SPECS: dict[str, tuple[str, ...]] = {
    "media_assets": (
        "asset_id", "sha256", "object_key", "size_bytes", "content_type",
        "kind", "original_name", "created_by", "status", "created_at", "deleted_at",
    ),
}
MEDIA_TABLES: tuple[str, ...] = tuple(MEDIA_TABLE_SPECS)
MEDIA_INDEXES: tuple[str, ...] = (
    "ix_media_assets_sha256",
    "ix_media_assets_status",
    "ix_media_assets_created_by",
)


def read_ddl(path: Path | None = None) -> str:
    return (path or MEDIA_DDL_FILE).read_text(encoding="utf-8")


def ensure_media_schema(conn: sqlite3.Connection, path: Path | None = None) -> list[str]:
    """幂等建表；返回本次真正新建的表名（第二次调用为空）。"""
    existing = _table_names(conn)
    conn.executescript(read_ddl(path))
    conn.commit()
    return [name for name in MEDIA_TABLES if name not in existing]


def verify_media_schema(conn: sqlite3.Connection) -> list[str]:
    """返回差异清单；空列表代表表与 3 个索引齐全且列顺序一致。"""
    diffs: list[str] = []
    existing = _table_names(conn)
    for table, expected in MEDIA_TABLE_SPECS.items():
        if table not in existing:
            diffs.append(f"missing table: {table}")
            continue
        actual = tuple(row[1] for row in conn.execute(f"PRAGMA table_info({table})"))
        if actual != expected:
            diffs.append(f"column mismatch: {table} expected={expected} actual={actual}")
    for index in MEDIA_INDEXES:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (index,)
        ).fetchone()
        if row is None:
            diffs.append(f"missing index: {index}")
    return diffs


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
