"""LocalVectorStore 单元测试（F6）。"""
from __future__ import annotations

import json

import pytest

from app.foundation.stores.local_vector import LocalVectorStore
from app.foundation.stores.vector import InvalidVectorTarget, VectorItem, VectorStoreCorrupt


def _store(tmp_path, dim=4):
    return LocalVectorStore(tmp_path / "vectors", dim=dim, max_top_k=5)


def test_upsert_search_where_and_persist(tmp_path):
    store = _store(tmp_path)
    assert store.upsert_many("text_questions", [
        VectorItem("q1", [1.0, 0.0, 0.0, 0.0], {"subjectId": 1, "contentHash": "a"}),
        VectorItem("q2", [0.0, 1.0, 0.0, 0.0], {"subjectId": 2, "contentHash": "b"}),
        VectorItem("q3", [0.9, 0.1, 0.0, 0.0], {"subjectId": 1, "contentHash": "c"}),
    ]) == 3
    assert store.count("text_questions") == 3
    assert set(store.list_ids("text_questions")) == {"q1", "q2", "q3"}

    hits = store.search("text_questions", [1.0, 0.0, 0.0, 0.0], top_k=2)
    assert [hit.id for hit in hits] == ["q1", "q3"]
    assert hits[0].score == pytest.approx(1.0)
    assert hits[1].score == pytest.approx(0.9 / (0.82 ** 0.5))

    only_one = store.search(
        "text_questions", [1.0, 0.0, 0.0, 0.0], top_k=5, where={"subjectId": 1}
    )
    assert {hit.id for hit in only_one} == {"q1", "q3"}
    either = store.search(
        "text_questions", [1.0, 0.0, 0.0, 0.0], top_k=5,
        where={"subjectId": [1, 2], "contentHash": ["a", "b"]},
    )
    assert {hit.id for hit in either} == {"q1", "q2"}

    assert store.fetch("text_questions", ["q1", "missing"]) == {
        "q1": {"subjectId": 1, "contentHash": "a"}
    }
    assert store.upsert("text_questions", "q1", [0.0, 0.0, 1.0, 0.0],
                        {"subjectId": 3, "contentHash": "z"}) is True
    assert store.count("text_questions") == 3

    reopened = _store(tmp_path)
    assert reopened.count("text_questions") == 3
    assert reopened.fetch("text_questions", ["q1"])["q1"]["subjectId"] == 3


def test_delete_and_clear(tmp_path):
    store = _store(tmp_path)
    store.upsert_many("c1", [
        VectorItem("a", [1, 0, 0, 0], {}),
        VectorItem("b", [0, 1, 0, 0], {}),
    ])
    assert store.delete("c1", "a") is True
    assert store.delete("c1", "missing") is False
    assert store.list_ids("c1") == ["b"]
    assert store.delete_many("c1", ["b", "missing"]) == 1
    assert store.count("c1") == 0
    store.upsert_many("c1", [VectorItem("c", [1, 0, 0, 0], {})])
    store.clear("c1")
    assert store.list_ids("c1") == []


def test_invalid_vectors_and_top_k(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(InvalidVectorTarget):
        store.upsert("c", "a", [1.0, 0.0], {})
    with pytest.raises(InvalidVectorTarget):
        store.upsert("c", "a", [0.0, 0.0, 0.0, 0.0], {})
    with pytest.raises(InvalidVectorTarget):
        store.upsert("c", "a", [1.0, float("nan"), 0.0, 0.0], {})
    with pytest.raises(InvalidVectorTarget):
        store.search("c", [1.0, 0.0, 0.0, 0.0], top_k=0)
    with pytest.raises(InvalidVectorTarget):
        store.search("c", [1.0, 0.0, 0.0, 0.0], top_k=6)
    with pytest.raises(InvalidVectorTarget):
        store.upsert("Bad-Name", "a", [1, 0, 0, 0], {})


def test_corrupt_index_is_reported(tmp_path):
    root = tmp_path / "vectors"
    root.mkdir()
    (root / "c.npy").write_bytes(b"not a numpy file")
    (root / "c.ids.json").write_text(json.dumps(["a"]), encoding="utf-8")
    (root / "c.meta.json").write_text(json.dumps({"a": {}}), encoding="utf-8")
    store = _store(tmp_path)
    with pytest.raises(VectorStoreCorrupt):
        store.list_ids("c")


def test_health_creates_root(tmp_path):
    store = _store(tmp_path)
    health = store.health()
    assert health.backend == "local"
    assert health.ok is True
    assert (tmp_path / "vectors").is_dir()
