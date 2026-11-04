"""F5 图查询：默认隐藏 status!=1，穿隐藏节点遍历但不返回。"""
from __future__ import annotations

import sqlite3

import pytest

from app.foundation import graph_query as gq
from app.foundation.graph_schema import read_ddl
from app.foundation.stores.graph import GraphStoreUnavailable
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


def _node(store, label, key, status=1):
    store.upsert_node(label, key, {"status": status, "name": key}, version=1)


def _seed(store):
    _node(store, "KnowledgePoint", "A", status=0)
    _node(store, "KnowledgePoint", "B", status=1)
    _node(store, "KnowledgePoint", "C", status=1)
    _node(store, "KnowledgePoint", "D", status=0)
    _node(store, "Question", "Q1", status=1)
    _node(store, "Question", "Q2", status=0)
    store.upsert_edge(
        "PREREQUISITE_OF", ("KnowledgePoint", "A"), ("KnowledgePoint", "B"), {}
    )
    store.upsert_edge(
        "PREREQUISITE_OF", ("KnowledgePoint", "B"), ("KnowledgePoint", "C"), {}
    )
    store.upsert_edge(
        "PARALLEL_WITH", ("KnowledgePoint", "B"), ("KnowledgePoint", "D"), {}
    )
    store.upsert_edge(
        "INSTANCE_OF", ("Question", "Q1"), ("KnowledgePoint", "B"), {}
    )
    store.upsert_edge(
        "INSTANCE_OF", ("Question", "Q2"), ("KnowledgePoint", "B"), {}
    )


def test_prerequisites_filter_hidden_but_traverse(store):
    _seed(store)
    visible = gq.prerequisites(store, "C", depth=2)
    assert [node["key"] for node in visible] == ["B"]
    hidden = gq.prerequisites(store, "C", depth=2, include_hidden=True)
    assert [node["key"] for node in hidden] == ["B", "A"]


def test_parallel_points_and_questions(store):
    _seed(store)
    assert [node["key"] for node in gq.parallel_points(store, "B")] == []
    assert [node["key"] for node in gq.parallel_points(store, "D")] == ["B"]
    assert [node["key"] for node in gq.questions_of_point(store, "B")] == ["Q1"]
    assert gq.questions_of_point(store, "B", limit=1) == gq.questions_of_point(store, "B")[:1]
    assert [node["key"] for node in gq.questions_of_point(
        store, "B", include_hidden=True
    )] == ["Q1", "Q2"]


def test_generic_neighbors_and_depth_validation(store):
    _seed(store)
    out = gq.neighbors(store, "KnowledgePoint", "A", "PREREQUISITE_OF", depth=2)
    assert [node["key"] for node in out] == ["B", "C"]
    with pytest.raises(ValueError):
        gq.prerequisites(store, "C", depth=0)


def test_unavailable_returns_empty(monkeypatch):
    class Down:
        backend = "local"

        def neighbors(self, *args, **kwargs):
            raise GraphStoreUnavailable("down")

    assert gq.prerequisites(Down(), "1") == []
    assert gq.parallel_points(Down(), "1") == []
    assert gq.questions_of_point(Down(), "1") == []
    assert gq.neighbors(Down(), "KnowledgePoint", "1", "INSTANCE_OF") == []
