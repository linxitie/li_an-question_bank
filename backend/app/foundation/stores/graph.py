"""GraphStore 协议（F5 图投影）。

事实源仍是 SQLite；图库只是可重建投影。图查询只服务内部函数，不暴露 HTTP。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterator, Protocol, runtime_checkable

LABELS = ("KnowledgePoint", "Question")
RELS = ("PREREQUISITE_OF", "PARALLEL_WITH", "INSTANCE_OF")

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class GraphStoreError(Exception):
    """图存储错误基类。"""


class GraphStoreUnavailable(GraphStoreError):
    """配置关闭、依赖缺失、网络或表结构不可用；调用方显式降级。"""


class GraphStoreCorrupt(GraphStoreError):
    """图数据无法解析或端点缺失；不得静默当成空图。"""


class InvalidGraphTarget(GraphStoreError):
    """label/rel/key 不在白名单或格式非法。"""


@dataclass(frozen=True)
class GraphHealth:
    backend: str
    ok: bool
    degraded: bool = False
    detail: str = ""


@dataclass(frozen=True)
class GraphNode:
    label: str
    key: str
    props: dict[str, Any]
    version: int = 1


@dataclass(frozen=True)
class GraphEdge:
    rel: str
    src_label: str
    src_key: str
    dst_label: str
    dst_key: str
    props: dict[str, Any]


@runtime_checkable
class GraphStore(Protocol):
    backend: str

    def upsert_node(self, label: str, key: str, props: dict[str, Any], *, version: int) -> bool: ...

    def upsert_edge(
        self,
        rel: str,
        src: tuple[str, str],
        dst: tuple[str, str],
        props: dict[str, Any],
    ) -> bool: ...

    def delete_node(self, label: str, key: str) -> bool: ...

    def delete_edge(self, rel: str, src: tuple[str, str], dst: tuple[str, str]) -> bool: ...

    def get_node(self, label: str, key: str) -> GraphNode | None: ...

    def iter_nodes(self, label: str) -> Iterator[GraphNode]: ...

    def iter_edges(self, rel: str) -> Iterator[GraphEdge]: ...

    def neighbors(
        self,
        label: str,
        key: str,
        rel: str,
        depth: int = 1,
        direction: str = "out",
    ) -> list[dict[str, Any]]: ...

    def counts(self) -> dict[str, Any]: ...

    def clear(self) -> None: ...

    def health(self) -> GraphHealth: ...


def validate_label(label: str) -> str:
    if label not in LABELS:
        raise InvalidGraphTarget(f"未知图节点 label: {label!r}")
    return label


def validate_rel(rel: str) -> str:
    if rel not in RELS:
        raise InvalidGraphTarget(f"未知图关系 rel: {rel!r}")
    return rel


def validate_key(key: str) -> str:
    if not isinstance(key, str) or not key:
        raise InvalidGraphTarget("图节点 key 不能为空")
    if len(key) > 128:
        raise InvalidGraphTarget("图节点 key 超过 128 字符")
    if _CONTROL_RE.search(key):
        raise InvalidGraphTarget("图节点 key 含控制字符")
    return key


def validate_endpoint(label: str, key: str) -> tuple[str, str]:
    return validate_label(label), validate_key(key)


def canonical_json(payload: Any) -> str:
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise GraphStoreError(f"图属性不是可序列化 JSON: {exc}") from exc


_store: GraphStore | None = None


def build_graph_store(backend: str | None = None) -> GraphStore:
    """按配置构造单例；local 默认，neo4j 可选。"""
    global _store
    from app.foundation import config as cfg

    name = (backend or cfg.GRAPH_BACKEND or "local").strip().lower()
    if name == "off" or not cfg.GRAPH_STORE_ENABLED:
        raise GraphStoreUnavailable("GRAPH_STORE_ENABLED=false 或 GRAPH_BACKEND=off")
    if _store is not None and getattr(_store, "backend", None) == name:
        return _store
    if name == "local":
        from app.foundation.stores.local_graph import LocalGraphStore

        _store = LocalGraphStore(cfg.sqlite_path())
    elif name == "neo4j":
        from app.foundation.stores.neo4j_graph import Neo4jGraphStore

        _store = Neo4jGraphStore(
            uri=cfg.GRAPH_NEO4J_URI,
            user=cfg.GRAPH_NEO4J_USER,
            password=cfg.GRAPH_NEO4J_PASSWORD,
            database=cfg.GRAPH_NEO4J_DATABASE,
        )
    else:
        raise GraphStoreUnavailable(f"未知 GRAPH_BACKEND: {name}（只支持 local/neo4j/off）")
    return _store


def reset_graph_store() -> None:
    global _store
    _store = None
