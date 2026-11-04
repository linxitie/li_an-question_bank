"""只读图遍历内部函数（F5）。

不注册 HTTP 路由，不返回给业务页面；调用方必须显式传入 GraphStore。
默认只返回 status=1 的节点，遍历可以经过隐藏节点，避免层级断裂。
"""
from __future__ import annotations

from typing import Any

from app.foundation.stores.graph import GraphStore, GraphStoreUnavailable


def _max_depth(depth: int) -> int:
    from app.foundation import config as cfg

    limit = max(1, int(cfg.GRAPH_QUERY_MAX_DEPTH))
    if not isinstance(depth, int) or isinstance(depth, bool) or depth < 1:
        raise ValueError(f"depth 必须是正整数: {depth!r}")
    return min(depth, limit)


def _visible(node: dict[str, Any], include_hidden: bool) -> bool:
    if include_hidden:
        return True
    props = node.get("props") or {}
    status = props.get("status", 1)
    try:
        return int(status) == 1
    except (TypeError, ValueError):
        return True


def _filter(nodes: list[dict[str, Any]], label: str, include_hidden: bool) -> list[dict[str, Any]]:
    return [
        node for node in nodes
        if node.get("label") == label and _visible(node, include_hidden)
    ]


def prerequisites(
    store: GraphStore, point_id: int | str, depth: int = 3, *, include_hidden: bool = False
) -> list[dict[str, Any]]:
    """沿 PREREQUISITE_OF 反向取祖先（父/祖父），默认最多 5 层。"""
    try:
        nodes = store.neighbors(
            "KnowledgePoint", str(point_id), "PREREQUISITE_OF",
            depth=_max_depth(depth), direction="in",
        )
    except GraphStoreUnavailable:
        return []
    return _filter(nodes, "KnowledgePoint", include_hidden)


def parallel_points(
    store: GraphStore, point_id: int | str, *, include_hidden: bool = False
) -> list[dict[str, Any]]:
    """同父兄弟节点（PARALLEL_WITH 双向）。"""
    try:
        nodes = store.neighbors(
            "KnowledgePoint", str(point_id), "PARALLEL_WITH", depth=1, direction="both",
        )
    except GraphStoreUnavailable:
        return []
    return _filter(nodes, "KnowledgePoint", include_hidden)


def questions_of_point(
    store: GraphStore,
    point_id: int | str,
    limit: int = 50,
    *,
    include_hidden: bool = False,
) -> list[dict[str, Any]]:
    """沿 INSTANCE_OF 反向取该知识点下的题目。"""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError(f"limit 必须是正整数: {limit!r}")
    try:
        nodes = store.neighbors(
            "KnowledgePoint", str(point_id), "INSTANCE_OF", depth=1, direction="in",
        )
    except GraphStoreUnavailable:
        return []
    visible = _filter(nodes, "Question", include_hidden)
    return visible[:limit]


def neighbors(
    store: GraphStore,
    label: str,
    key: str,
    rel: str,
    depth: int = 1,
    *,
    direction: str = "out",
    include_hidden: bool = False,
) -> list[dict[str, Any]]:
    """通用只读遍历；direction 支持 out/in/both。"""
    try:
        nodes = store.neighbors(
            label, key, rel, depth=_max_depth(depth), direction=direction,
        )
    except GraphStoreUnavailable:
        return []
    if include_hidden:
        return nodes
    return [node for node in nodes if _visible(node, include_hidden)]
