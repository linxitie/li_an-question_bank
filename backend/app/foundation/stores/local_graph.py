"""local 图存储：直接读写主库 foundation_graph_node/edge 两张投影表。

图数据是可重建投影，不参与业务事务。每次操作新开 sqlite3 连接并设置
busy_timeout，避免与 FastAPI 的 SQLAlchemy 连接池互相锁死。
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.foundation.stores.graph import (
    GraphEdge,
    GraphHealth,
    GraphNode,
    GraphStoreCorrupt,
    GraphStoreUnavailable,
    canonical_json,
    validate_endpoint,
    validate_label,
    validate_rel,
)

_DIRECTIONS = ("out", "in", "both")
_MAX_DEPTH = 10


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LocalGraphStore:
    backend = "local"

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)

    # ---------- 连接与序列化 ----------

    def _connect(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30)
        except sqlite3.Error as exc:
            raise GraphStoreUnavailable(f"无法打开图数据库 {self.db_path}: {exc}") from exc
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    @staticmethod
    def _props(row: sqlite3.Row) -> dict[str, Any]:
        try:
            value = json.loads(row["props"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise GraphStoreCorrupt(f"图节点属性损坏: {row['props']!r}") from exc
        if not isinstance(value, dict):
            raise GraphStoreCorrupt("图节点属性不是对象")
        return value

    def _get_node_with(self, conn: sqlite3.Connection, label: str, key: str) -> GraphNode | None:
        row = conn.execute(
            "SELECT label, key, props, version FROM foundation_graph_node "
            "WHERE label=? AND key=?",
            (label, key),
        ).fetchone()
        return None if row is None else GraphNode(
            label=row["label"], key=row["key"], props=self._props(row),
            version=int(row["version"]),
        )

    # ---------- 写 ----------

    def upsert_node(self, label: str, key: str, props: dict[str, Any], *, version: int) -> bool:
        label, key = validate_endpoint(label, key)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ValueError(f"version 必须是正整数: {version!r}")
        if not isinstance(props, dict):
            raise ValueError("props 必须是 dict")
        body = canonical_json(props)
        try:
            with closing(self._connect()) as conn, conn:
                cur = conn.execute(
                    """INSERT INTO foundation_graph_node(label, key, props, version, updated_at)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(label, key) DO UPDATE SET
                         props=excluded.props,
                         version=excluded.version,
                         updated_at=excluded.updated_at
                       WHERE excluded.version > foundation_graph_node.version""",
                    (label, key, body, version, _now()),
                )
                return cur.rowcount > 0
        except sqlite3.Error as exc:
            raise GraphStoreUnavailable(f"写入图节点失败: {exc}") from exc

    def upsert_edge(
        self,
        rel: str,
        src: tuple[str, str],
        dst: tuple[str, str],
        props: dict[str, Any],
    ) -> bool:
        rel = validate_rel(rel)
        src_label, src_key = validate_endpoint(*src)
        dst_label, dst_key = validate_endpoint(*dst)
        if not isinstance(props, dict):
            raise ValueError("props 必须是 dict")
        body = canonical_json(props)
        try:
            with closing(self._connect()) as conn, conn:
                if self._get_node_with(conn, src_label, src_key) is None:
                    raise GraphStoreCorrupt(f"边起点不存在: {src_label}/{src_key}")
                if self._get_node_with(conn, dst_label, dst_key) is None:
                    raise GraphStoreCorrupt(f"边终点不存在: {dst_label}/{dst_key}")
                cur = conn.execute(
                    """INSERT INTO foundation_graph_edge(
                           rel, src_label, src_key, dst_label, dst_key, props)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(rel, src_label, src_key, dst_label, dst_key)
                       DO UPDATE SET props=excluded.props""",
                    (rel, src_label, src_key, dst_label, dst_key, body),
                )
                return cur.rowcount > 0
        except sqlite3.Error as exc:
            raise GraphStoreUnavailable(f"写入图边失败: {exc}") from exc

    def delete_node(self, label: str, key: str) -> bool:
        label, key = validate_endpoint(label, key)
        try:
            with closing(self._connect()) as conn, conn:
                conn.execute(
                    """DELETE FROM foundation_graph_edge
                       WHERE (src_label=? AND src_key=?) OR (dst_label=? AND dst_key=?)""",
                    (label, key, label, key),
                )
                cur = conn.execute(
                    "DELETE FROM foundation_graph_node WHERE label=? AND key=?", (label, key)
                )
                return cur.rowcount > 0
        except sqlite3.Error as exc:
            raise GraphStoreUnavailable(f"删除图节点失败: {exc}") from exc

    def delete_edge(self, rel: str, src: tuple[str, str], dst: tuple[str, str]) -> bool:
        rel = validate_rel(rel)
        src_label, src_key = validate_endpoint(*src)
        dst_label, dst_key = validate_endpoint(*dst)
        try:
            with closing(self._connect()) as conn, conn:
                cur = conn.execute(
                    """DELETE FROM foundation_graph_edge
                       WHERE rel=? AND src_label=? AND src_key=? AND dst_label=? AND dst_key=?""",
                    (rel, src_label, src_key, dst_label, dst_key),
                )
                return cur.rowcount > 0
        except sqlite3.Error as exc:
            raise GraphStoreUnavailable(f"删除图边失败: {exc}") from exc

    def clear(self) -> None:
        try:
            with closing(self._connect()) as conn, conn:
                conn.execute("DELETE FROM foundation_graph_edge")
                conn.execute("DELETE FROM foundation_graph_node")
        except sqlite3.Error as exc:
            raise GraphStoreUnavailable(f"清空图投影失败: {exc}") from exc

    # ---------- 读 ----------

    def get_node(self, label: str, key: str) -> GraphNode | None:
        label, key = validate_endpoint(label, key)
        try:
            with closing(self._connect()) as conn:
                return self._get_node_with(conn, label, key)
        except sqlite3.Error as exc:
            raise GraphStoreUnavailable(f"读取图节点失败: {exc}") from exc

    def iter_nodes(self, label: str) -> Iterator[GraphNode]:
        label = validate_label(label)
        try:
            with closing(self._connect()) as conn:
                rows = conn.execute(
                    "SELECT label, key, props, version FROM foundation_graph_node "
                    "WHERE label=? ORDER BY key",
                    (label,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise GraphStoreUnavailable(f"枚举图节点失败: {exc}") from exc
        for row in rows:
            yield GraphNode(
                label=row["label"], key=row["key"], props=self._props(row),
                version=int(row["version"]),
            )

    def iter_edges(self, rel: str) -> Iterator[GraphEdge]:
        rel = validate_rel(rel)
        try:
            with closing(self._connect()) as conn:
                rows = conn.execute(
                    """SELECT rel, src_label, src_key, dst_label, dst_key, props
                       FROM foundation_graph_edge WHERE rel=?
                       ORDER BY src_label, src_key, dst_label, dst_key""",
                    (rel,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise GraphStoreUnavailable(f"枚举图边失败: {exc}") from exc
        for row in rows:
            try:
                props = json.loads(row["props"])
            except (TypeError, json.JSONDecodeError) as exc:
                raise GraphStoreCorrupt(f"图边属性损坏: {row['props']!r}") from exc
            if not isinstance(props, dict):
                raise GraphStoreCorrupt("图边属性不是对象")
            yield GraphEdge(
                rel=row["rel"], src_label=row["src_label"], src_key=row["src_key"],
                dst_label=row["dst_label"], dst_key=row["dst_key"], props=props,
            )

    def _edges_from(
        self, conn: sqlite3.Connection, label: str, key: str, rel: str, direction: str
    ) -> list[sqlite3.Row]:
        if direction == "out":
            sql = ("SELECT * FROM foundation_graph_edge "
                   "WHERE rel=? AND src_label=? AND src_key=?")
            params = (rel, label, key)
        elif direction == "in":
            sql = ("SELECT * FROM foundation_graph_edge "
                   "WHERE rel=? AND dst_label=? AND dst_key=?")
            params = (rel, label, key)
        else:
            sql = ("SELECT * FROM foundation_graph_edge WHERE rel=? AND "
                   "((src_label=? AND src_key=?) OR (dst_label=? AND dst_key=?))")
            params = (rel, label, key, label, key)
        return conn.execute(sql, params).fetchall()

    def neighbors(
        self, label: str, key: str, rel: str, depth: int = 1, direction: str = "out"
    ) -> list[dict[str, Any]]:
        label, key = validate_endpoint(label, key)
        rel = validate_rel(rel)
        if direction not in _DIRECTIONS:
            raise ValueError(f"direction 只支持 {_DIRECTIONS}: {direction!r}")
        if not isinstance(depth, int) or isinstance(depth, bool) or not 1 <= depth <= _MAX_DEPTH:
            raise ValueError(f"depth 必须是 1..{_MAX_DEPTH}: {depth!r}")
        try:
            with closing(self._connect()) as conn:
                visited = {(label, key)}
                frontier = [(label, key)]
                result: list[dict[str, Any]] = []
                for level in range(1, depth + 1):
                    next_frontier: list[tuple[str, str]] = []
                    for current_label, current_key in frontier:
                        for row in self._edges_from(
                            conn, current_label, current_key, rel, direction
                        ):
                            if direction == "out":
                                other = (row["dst_label"], row["dst_key"])
                            elif direction == "in":
                                other = (row["src_label"], row["src_key"])
                            elif row["src_label"] == current_label and row["src_key"] == current_key:
                                other = (row["dst_label"], row["dst_key"])
                            else:
                                other = (row["src_label"], row["src_key"])
                            if other in visited:
                                continue
                            visited.add(other)
                            node = self._get_node_with(conn, other[0], other[1])
                            if node is None:
                                continue
                            result.append({
                                "label": node.label,
                                "key": node.key,
                                "props": node.props,
                                "version": node.version,
                                "rel": row["rel"],
                                "depth": level,
                            })
                            next_frontier.append(other)
                    frontier = next_frontier
                    if not frontier:
                        break
        except sqlite3.Error as exc:
            raise GraphStoreUnavailable(f"遍历图失败: {exc}") from exc
        return result

    def counts(self) -> dict[str, Any]:
        try:
            with closing(self._connect()) as conn:
                nodes = conn.execute("SELECT COUNT(*) FROM foundation_graph_node").fetchone()[0]
                edges = conn.execute("SELECT COUNT(*) FROM foundation_graph_edge").fetchone()[0]
                by_label = {
                    row[0]: int(row[1])
                    for row in conn.execute(
                        "SELECT label, COUNT(*) FROM foundation_graph_node GROUP BY label"
                    )
                }
                by_rel = {
                    row[0]: int(row[1])
                    for row in conn.execute(
                        "SELECT rel, COUNT(*) FROM foundation_graph_edge GROUP BY rel"
                    )
                }
        except sqlite3.Error as exc:
            raise GraphStoreUnavailable(f"统计图投影失败: {exc}") from exc
        return {
            "nodes": int(nodes),
            "edges": int(edges),
            "nodes_by_label": by_label,
            "edges_by_rel": by_rel,
        }

    def health(self) -> GraphHealth:
        try:
            with closing(self._connect()) as conn:
                conn.execute("SELECT 1").fetchone()
                names = {
                    row[0]
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
            missing = [
                t for t in ("foundation_graph_node", "foundation_graph_edge")
                if t not in names
            ]
            if missing:
                return GraphHealth(
                    backend="local", ok=False, degraded=True,
                    detail=f"缺少图投影表: {', '.join(missing)}",
                )
            counts = self.counts()
            return GraphHealth(
                backend="local", ok=True, degraded=False,
                detail=f"nodes={counts['nodes']} edges={counts['edges']}",
            )
        except (sqlite3.Error, GraphStoreUnavailable) as exc:
            return GraphHealth(
                backend="local", ok=False, degraded=True, detail=f"{type(exc).__name__}: {exc}"
            )
