"""F5 GraphStore：local 持久化、版本守卫、BFS 与健康。"""
from __future__ import annotations

import sqlite3

import pytest

from app.foundation.graph_schema import read_ddl
from app.foundation.stores.graph import (
    GraphStoreCorrupt,
    InvalidGraphTarget,
    LABELS,
    RELS,
)
from app.foundation.stores.local_graph import LocalGraphStore


@pytest.fixture()
def store(tmp_path):
    db = tmp_path / "graph.db"
    conn = sqlite3.connect(db)
    try:
        conn.executescript(read_ddl())
    finally:
        conn.close()
    return LocalGraphStore(db)


def _kp(store, key, status=1, version=1):
    return store.upsert_node("KnowledgePoint", key, {"status": status}, version=version)


def _edge(store, src, dst, rel="PREREQUISITE_OF"):
    return store.upsert_edge(
        rel, ("KnowledgePoint", src), ("KnowledgePoint", dst), {"derivation": "test"}
    )


def test_local_crud_and_version_guard(store):
    assert _kp(store, "1") is True
    assert _kp(store, "1") is False
    assert _kp(store, "1", status=0, version=2) is True
    node = store.get_node("KnowledgePoint", "1")
    assert node.props == {"status": 0}
    assert node.version == 2
    assert store.get_node("KnowledgePoint", "404") is None


def test_edge_requires_both_endpoints(store):
    _kp(store, "1")
    with pytest.raises(GraphStoreCorrupt):
        _edge(store, "1", "2")
    _kp(store, "2")
    assert _edge(store, "1", "2") is True
    assert store.counts()["edges"] == 1


def test_neighbors_bfs_directions_and_delete(store):
    for key in ("A", "B", "C"):
        _kp(store, key)
    _edge(store, "A", "B")
    _edge(store, "B", "C")

    out = store.neighbors("KnowledgePoint", "A", "PREREQUISITE_OF", depth=2)
    assert [(n["key"], n["depth"]) for n in out] == [("B", 1), ("C", 2)]

    incoming = store.neighbors(
        "KnowledgePoint", "C", "PREREQUISITE_OF", depth=2, direction="in"
    )
    assert [n["key"] for n in incoming] == ["B", "A"]

    both = store.neighbors(
        "KnowledgePoint", "B", "PREREQUISITE_OF", depth=1, direction="both"
    )
    assert sorted(n["key"] for n in both) == ["A", "C"]

    assert store.delete_edge(
        "PREREQUISITE_OF", ("KnowledgePoint", "A"), ("KnowledgePoint", "B")
    )
    assert store.delete_node("KnowledgePoint", "B") is True
    assert store.get_node("KnowledgePoint", "B") is None
    assert store.counts()["edges"] == 0
    store.clear()
    assert store.counts()["nodes"] == 0


def test_validators_and_health(store):
    with pytest.raises(InvalidGraphTarget):
        store.upsert_node("Nope", "1", {}, version=1)
    with pytest.raises(InvalidGraphTarget):
        store.neighbors("KnowledgePoint", "1", "NOPE")
    with pytest.raises(InvalidGraphTarget):
        store.upsert_node("KnowledgePoint", "", {}, version=1)
    with pytest.raises(ValueError):
        store.neighbors("KnowledgePoint", "1", RELS[0], depth=0)

    health = store.health()
    assert health.ok is True
    assert health.backend == "local"
    assert "nodes=0" in health.detail


def test_health_reports_missing_tables(tmp_path):
    db = tmp_path / "empty.db"
    LocalGraphStore(db).health()  # 建一个空 sqlite 文件
    health = LocalGraphStore(db).health()
    assert health.ok is False
    assert "缺少图投影表" in health.detail


def test_protocol_constants():
    assert LABELS == ("KnowledgePoint", "Question")
    assert "INSTANCE_OF" in RELS
