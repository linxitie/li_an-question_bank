"""F5 图投影表的唯一 DDL 来源与结构校验。

DDL 在 backend/migrations/20261027_003_graph_projection.sql，本模块只读取与比对，
不复制 SQL 文本，避免迁移/运行时/门禁三份定义漂移。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from app.foundation.config import GRAPH_DDL_FILE

GRAPH_TABLE_SPECS: dict[str, tuple[str, ...]] = {
    "foundation_graph_node": ("label", "key", "props", "version", "updated_at"),
    "foundation_graph_edge": (
        "rel", "src_label", "src_key", "dst_label", "dst_key", "props",
    ),
}
GRAPH_TABLES: tuple[str, ...] = tuple(GRAPH_TABLE_SPECS)
GRAPH_INDEXES: tuple[str, ...] = ("ix_graph_edge_src", "ix_graph_edge_dst")


def read_ddl(path: Path | None = None) -> str:
    target = path or GRAPH_DDL_FILE
    return target.read_text(encoding="utf-8")


def ddl_statements(path: Path | None = None) -> list[str]:
    """把 DDL 拆成单条语句，供测试/临时库直接执行。"""
    statements: list[str] = []
    for chunk in read_ddl(path).split(";"):
        lines = [ln for ln in chunk.splitlines() if ln.strip()]
        body = [ln for ln in lines if not ln.strip().startswith("--")]
        if body:
            statements.append("\n".join(lines))
    return statements


def ensure_graph_schema(conn: sqlite3.Connection, path: Path | None = None) -> list[str]:
    """幂等建表，返回本次真正新建的表名（第二次调用为空）。"""
    existing = _table_names(conn)
    conn.executescript(read_ddl(path))
    conn.commit()
    return [name for name in GRAPH_TABLES if name not in existing]


def verify_graph_schema(conn: sqlite3.Connection) -> list[str]:
    diffs: list[str] = []
    existing = _table_names(conn)
    for table, expected in GRAPH_TABLE_SPECS.items():
        if table not in existing:
            diffs.append(f"missing table: {table}")
            continue
        actual = tuple(row[1] for row in conn.execute(f"PRAGMA table_info({table})"))
        if actual != expected:
            diffs.append(f"column mismatch: {table} expected={expected} actual={actual}")
    for index in GRAPH_INDEXES:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?", (index,)
        ).fetchone()
        if row is None:
            diffs.append(f"missing index: {index}")
    return diffs


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
