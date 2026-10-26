"""7 张 foundation 表的唯一 DDL 来源与结构校验。

DDL 存在 backend/migrations/20261027_001_foundation_core.sql，本模块只读取与比对，
不复制 SQL 文本，避免"文档/迁移/运行时"三份定义漂移。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from app.foundation.config import DDL_FILE

# 表 -> 列（顺序即 DDL 顺序，用于结构比对）
TABLE_SPECS: dict[str, tuple[str, ...]] = {
    "foundation_outbox": (
        "id", "event_id", "event_name", "schema_version", "aggregate_type",
        "aggregate_id", "aggregate_ver", "dedupe_key", "payload", "producer",
        "trace_id", "occurred_at", "status", "attempts", "next_retry_at",
        "dispatched_at", "last_error",
    ),
    "foundation_projection_cursor": (
        "projection", "last_outbox_id", "updated_at", "status", "lag_seconds",
    ),
    "foundation_inbox": ("consumer", "event_id", "event_name", "processed_at"),
    "foundation_projection_state": (
        "projection", "aggregate_type", "aggregate_id", "source_version",
        "checksum", "updated_at",
    ),
    "foundation_reconcile_run": (
        "run_id", "scope", "mode", "started_at", "finished_at", "checked",
        "drifted", "repaired", "report_path", "status",
    ),
    "foundation_backfill_state": ("source", "cursor", "total", "done", "updated_at"),
    "foundation_preview_ref": (
        "import_id", "ref_path", "bytes", "sha256", "questions",
        "status_at_purge", "purged_at",
    ),
}
FOUNDATION_TABLES: tuple[str, ...] = tuple(TABLE_SPECS)
FOUNDATION_INDEXES: tuple[str, ...] = (
    "ux_outbox_dedupe", "ix_outbox_status_id", "ix_outbox_aggregate",
    "ix_preview_ref_purged",
)


def read_ddl(path: Path | None = None) -> str:
    target = path or DDL_FILE
    return target.read_text(encoding="utf-8")


def ddl_statements(path: Path | None = None) -> list[str]:
    """把 DDL 文件拆成单条语句（供 SQLAlchemy exec_driver_sql 使用）。"""
    raw = read_ddl(path).split(";")
    statements = []
    for chunk in raw:
        body = [ln for ln in chunk.splitlines() if ln.strip() and not ln.strip().startswith("--")]
        if body:
            statements.append("\n".join(ln for ln in chunk.splitlines() if ln.strip()))
    return statements


def ensure_schema(conn: sqlite3.Connection, path: Path | None = None) -> list[str]:
    """幂等建表，返回本次真正新建的表名（第二次调用应为空列表）。"""
    existing = _table_names(conn)
    conn.executescript(read_ddl(path))
    conn.commit()
    return [name for name in FOUNDATION_TABLES if name not in existing]


def verify_schema(conn: sqlite3.Connection) -> list[str]:
    """返回差异清单；空列表代表结构与 TABLE_SPECS 完全一致。"""
    diffs: list[str] = []
    existing = _table_names(conn)
    for table, expected in TABLE_SPECS.items():
        if table not in existing:
            diffs.append(f"missing table: {table}")
            continue
        actual = tuple(row[1] for row in conn.execute(f"PRAGMA table_info({table})"))
        if actual != expected:
            diffs.append(f"column mismatch: {table} expected={expected} actual={actual}")
    for index in FOUNDATION_INDEXES:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (index,)
        ).fetchone()
        if row is None:
            diffs.append(f"missing index: {index}")
    return diffs


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
