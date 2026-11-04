"""Neo4j 图存储适配器（可选后端）。

通过 Neo4j 的 HTTP transactional endpoint 执行 Cypher，不新增 neo4j 驱动依赖。
所有节点额外带 LiAnNode 公共标签，clear 只删本投影，不碰用户库里的其他数据。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterator

import httpx

from app.foundation.stores.graph import (
    GraphEdge,
    GraphHealth,
    GraphNode,
    GraphStoreCorrupt,
    GraphStoreError,
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


class Neo4jGraphStore:
    backend = "neo4j"

    def __init__(
        self,
        *,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
        timeout: float = 3.0,
    ):
        self.uri = (uri or "").strip().rstrip("/")
        self.user = (user or "").strip()
        self.password = password or ""
        self.database = (database or "neo4j").strip()
        self.timeout = float(timeout)
        if not self.uri:
            raise GraphStoreUnavailable("GRAPH_NEO4J_URI 为空")
        if not self.password:
            raise GraphStoreUnavailable("GRAPH_NEO4J_PASSWORD 为空（Neo4j 需要认证）")

    # ---------- HTTP ----------

    def _endpoint(self) -> str:
        return f"{self.uri}/db/{self.database}/tx/commit"

    def _run(self, statement: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        payload = {
            "statements": [{
                "statement": statement,
                "parameters": parameters or {},
                "resultDataContents": ["row"],
            }]
        }
        try:
            response = httpx.post(
                self._endpoint(),
                json=payload,
                auth=(self.user, self.password),
                timeout=self.timeout,
            )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            raise GraphStoreUnavailable(f"Neo4j 不可达: {type(exc).__name__}: {exc}") from exc
        if response.status_code in (401, 403):
            raise GraphStoreUnavailable("Neo4j 认证失败（检查 GRAPH_NEO4J_USER/PASSWORD）")
        if response.status_code >= 500:
            raise GraphStoreUnavailable(f"Neo4j 服务错误: HTTP {response.status_code}")
        if response.status_code >= 400:
            raise GraphStoreError(f"Neo4j 请求失败: HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise GraphStoreError("Neo4j 返回不是合法 JSON") from exc
        errors = data.get("errors") or []
        if errors:
            message = "; ".join(
                str(item.get("message") or item.get("code") or item) for item in errors
            )
            raise GraphStoreError(f"Neo4j Cypher 错误: {message}")
        results = data.get("results") or []
        if not results:
            return []
        result = results[0]
        columns = result.get("columns") or []
        rows = result.get("data") or []
        parsed: list[dict[str, Any]] = []
        for item in rows:
            row = item.get("row") if isinstance(item, dict) else None
            if isinstance(row, list):
                parsed.append(dict(zip(columns, row)))
        return parsed

    @staticmethod
    def _clean_props(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            return {}
        props = dict(raw)
        for key in ("label", "key", "version", "updatedAt"):
            props.pop(key, None)
        return props

    # ---------- 写 ----------

    def upsert_node(self, label: str, key: str, props: dict[str, Any], *, version: int) -> bool:
        label, key = validate_endpoint(label, key)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ValueError(f"version 必须是正整数: {version!r}")
        if not isinstance(props, dict):
            raise ValueError("props 必须是 dict")
        canonical_json(props)  # 提前校验可序列化
        rows = self._run(
            f"""MERGE (n:LiAnNode:`{label}` {{key: $key}})
                WITH n, coalesce(n.version, 0) AS current
                FOREACH (_ IN CASE WHEN $version > current THEN [1] ELSE [] END |
                  SET n += $props, n.label = $label, n.version = $version,
                      n.updatedAt = $updated_at
                )
                RETURN current, n.version AS version""",
            {
                "key": key, "label": label, "props": props, "version": version,
                "updated_at": _now(),
            },
        )
        if not rows:
            raise GraphStoreCorrupt(f"Neo4j upsert 节点没有返回结果: {label}/{key}")
        return int(rows[0].get("version") or 0) > int(rows[0].get("current") or 0)

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
        canonical_json(props)
        rows = self._run(
            f"""MATCH (a:LiAnNode:`{src_label}` {{key: $src_key}}),
                      (b:LiAnNode:`{dst_label}` {{key: $dst_key}})
                MERGE (a)-[r:`{rel}`]->(b)
                SET r += $props
                RETURN count(r) AS c""",
            {
                "src_key": src_key, "dst_key": dst_key, "props": props,
            },
        )
        if not rows or int(rows[0].get("c") or 0) == 0:
            raise GraphStoreCorrupt(
                f"Neo4j 边端点不存在: {src_label}/{src_key} -> {dst_label}/{dst_key}"
            )
        return True

    def delete_node(self, label: str, key: str) -> bool:
        label, key = validate_endpoint(label, key)
        rows = self._run(
            f"MATCH (n:LiAnNode:`{label}` {{key: $key}}) "
            "DETACH DELETE n RETURN count(n) AS c",
            {"key": key},
        )
        return bool(rows and int(rows[0].get("c") or 0) > 0)

    def delete_edge(self, rel: str, src: tuple[str, str], dst: tuple[str, str]) -> bool:
        rel = validate_rel(rel)
        src_label, src_key = validate_endpoint(*src)
        dst_label, dst_key = validate_endpoint(*dst)
        rows = self._run(
            f"""MATCH (a:LiAnNode:`{src_label}` {{key: $src_key}})
                      -[r:`{rel}`]->
                      (b:LiAnNode:`{dst_label}` {{key: $dst_key}})
                DELETE r RETURN count(r) AS c""",
            {"src_key": src_key, "dst_key": dst_key},
        )
        return bool(rows and int(rows[0].get("c") or 0) > 0)

    def clear(self) -> None:
        self._run("MATCH (n:LiAnNode) DETACH DELETE n RETURN count(n) AS c")

    # ---------- 读 ----------

    def get_node(self, label: str, key: str) -> GraphNode | None:
        label, key = validate_endpoint(label, key)
        rows = self._run(
            f"""MATCH (n:LiAnNode:`{label}` {{key: $key}})
                RETURN n.label AS label, n.key AS key, properties(n) AS props,
                       n.version AS version LIMIT 1""",
            {"key": key},
        )
        if not rows:
            return None
        row = rows[0]
        return GraphNode(
            label=str(row.get("label") or label),
            key=str(row.get("key") or key),
            props=self._clean_props(row.get("props")),
            version=int(row.get("version") or 1),
        )

    def iter_nodes(self, label: str) -> Iterator[GraphNode]:
        label = validate_label(label)
        rows = self._run(
            f"""MATCH (n:LiAnNode:`{label}`)
                RETURN n.label AS label, n.key AS key, properties(n) AS props,
                       n.version AS version ORDER BY n.key"""
        )
        for row in rows:
            yield GraphNode(
                label=str(row.get("label") or label),
                key=str(row.get("key") or ""),
                props=self._clean_props(row.get("props")),
                version=int(row.get("version") or 1),
            )

    def iter_edges(self, rel: str) -> Iterator[GraphEdge]:
        rel = validate_rel(rel)
        rows = self._run(
            f"""MATCH (a:LiAnNode)-[r:`{rel}`]->(b:LiAnNode)
                RETURN a.label AS src_label, a.key AS src_key,
                       b.label AS dst_label, b.key AS dst_key, properties(r) AS props
                ORDER BY src_label, src_key, dst_label, dst_key"""
        )
        for row in rows:
            yield GraphEdge(
                rel=rel,
                src_label=str(row.get("src_label") or ""),
                src_key=str(row.get("src_key") or ""),
                dst_label=str(row.get("dst_label") or ""),
                dst_key=str(row.get("dst_key") or ""),
                props=dict(row.get("props") or {}),
            )

    def neighbors(
        self, label: str, key: str, rel: str, depth: int = 1, direction: str = "out"
    ) -> list[dict[str, Any]]:
        label, key = validate_endpoint(label, key)
        rel = validate_rel(rel)
        if direction not in _DIRECTIONS:
            raise ValueError(f"direction 只支持 {_DIRECTIONS}: {direction!r}")
        if not isinstance(depth, int) or isinstance(depth, bool) or not 1 <= depth <= _MAX_DEPTH:
            raise ValueError(f"depth 必须是 1..{_MAX_DEPTH}: {depth!r}")
        if direction == "out":
            pattern = f"(start)-[r:`{rel}`*1..{depth}]->(n:LiAnNode)"
        elif direction == "in":
            pattern = f"(start)<-[r:`{rel}`*1..{depth}]-(n:LiAnNode)"
        else:
            pattern = f"(start)-[r:`{rel}`*1..{depth}]-(n:LiAnNode)"
        rows = self._run(
            f"""MATCH (start:LiAnNode:`{label}` {{key: $key}}){pattern}
                WITH n, min(length(r)) AS depth
                RETURN n.label AS label, n.key AS key, properties(n) AS props,
                       n.version AS version, depth
                ORDER BY depth, key""",
            {"key": key},
        )
        return [{
            "label": str(row.get("label") or ""),
            "key": str(row.get("key") or ""),
            "props": self._clean_props(row.get("props")),
            "version": int(row.get("version") or 1),
            "rel": rel,
            "depth": int(row.get("depth") or 1),
        } for row in rows]

    def counts(self) -> dict[str, Any]:
        node_rows = self._run("MATCH (n:LiAnNode) RETURN count(n) AS c")
        edge_rows = self._run(
            """MATCH ()-[r]->() WHERE type(r) IN
               ['PREREQUISITE_OF','PARALLEL_WITH','INSTANCE_OF']
               RETURN type(r) AS rel, count(r) AS c"""
        )
        label_rows = self._run(
            "MATCH (n:LiAnNode) RETURN n.label AS label, count(*) AS c"
        )
        by_rel = {str(row.get("rel")): int(row.get("c") or 0) for row in edge_rows}
        by_label = {str(row.get("label")): int(row.get("c") or 0) for row in label_rows}
        return {
            "nodes": int(node_rows[0].get("c") or 0) if node_rows else 0,
            "edges": sum(by_rel.values()),
            "nodes_by_label": by_label,
            "edges_by_rel": by_rel,
        }

    def health(self) -> GraphHealth:
        try:
            rows = self._run("RETURN 1 AS ok")
            if not rows:
                return GraphHealth(backend="neo4j", ok=False, degraded=True, detail="空响应")
            counts = self.counts()
            return GraphHealth(
                backend="neo4j", ok=True, degraded=False,
                detail=f"nodes={counts['nodes']} edges={counts['edges']}",
            )
        except (GraphStoreError, httpx.HTTPError) as exc:
            return GraphHealth(
                backend="neo4j", ok=False, degraded=True,
                detail=f"{type(exc).__name__}: {exc}",
            )
