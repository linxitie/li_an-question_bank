"""MilvusVectorStore 单元测试（F6，使用 fake client，不依赖真实 Milvus）。"""
from __future__ import annotations

import json
import re
import sys
import types

import pytest

from app.foundation.stores.milvus_vector import MilvusVectorStore
from app.foundation.stores.vector import (
    InvalidVectorTarget,
    VectorItem,
    VectorStoreCorrupt,
    VectorStoreUnavailable,
)


class _Schema:
    def __init__(self):
        self.fields = []

    def add_field(self, **kwargs):
        self.fields.append(kwargs)


class _Index:
    def __init__(self):
        self.items = []

    def add_index(self, **kwargs):
        self.items.append(kwargs)


class _FakeMilvus:
    def __init__(self):
        self.collections = {}
        self.rows = {}
        self.query_calls = []
        self.deleted = []

    def has_collection(self, collection_name):
        return collection_name in self.collections

    def describe_collection(self, collection_name):
        return self.collections[collection_name]

    def create_schema(self, **_kwargs):
        return _Schema()

    def prepare_index_params(self):
        return _Index()

    def create_collection(self, collection_name, schema=None, index_params=None):
        self.collections[collection_name] = {
            "fields": [
                {"field_name": f["field_name"], "params": f.get("params", {})}
                for f in (schema.fields if schema else [])
            ],
            "index": index_params.items if index_params else [],
        }
        self.rows.setdefault(collection_name, {})

    def load_collection(self, collection_name):
        self.collections[collection_name]["loaded"] = True

    def upsert(self, collection_name, data):
        for row in data:
            self.rows.setdefault(collection_name, {})[row["id"]] = {
                "id": row["id"], "meta": row["meta"], "vector": row["vector"],
            }
        return {"upsert_count": len(data)}

    def search(self, collection_name, data, anns_field, limit, output_fields, search_params, **kwargs):
        rows = list(self.rows.get(collection_name, {}).values())[:limit]
        return [[
            {"id": row["id"], "distance": 1.0 - index * 0.1,
             "entity": {"meta": row["meta"]}}
            for index, row in enumerate(rows)
        ]]

    def query(self, collection_name, filter, output_fields, **kwargs):
        self.query_calls.append({"filter": filter, "fields": output_fields})
        rows = list(self.rows.get(collection_name, {}).values())
        if "count(*)" in output_fields:
            return [{"count(*)": len(rows)}]
        if filter and "id in" in filter:
            wanted = set(re.findall(r'"([^"]+)"', filter))
            rows = [row for row in rows if row["id"] in wanted]
        if output_fields == ["id"]:
            return [{"id": row["id"]} for row in rows]
        return [{"id": row["id"], "meta": row["meta"]} for row in rows]

    def delete(self, collection_name, ids):
        for item_id in ids:
            self.rows.get(collection_name, {}).pop(item_id, None)
            self.deleted.append(item_id)
        return {"delete_count": len(ids)}

    def drop_collection(self, collection_name):
        self.collections.pop(collection_name, None)
        self.rows.pop(collection_name, None)

    def list_collections(self):
        return list(self.collections)


def _store(client, dim=4):
    store = MilvusVectorStore(uri="http://milvus:19530", dim=dim, client=client)
    store._ready.add("li_an_text_questions")
    return store


def test_upsert_search_fetch_and_count():
    client = _FakeMilvus()
    client.collections["li_an_text_questions"] = {"fields": []}
    client.rows["li_an_text_questions"] = {}
    store = _store(client)
    assert store.backend == "milvus"
    assert store.upsert_many("text_questions", [
        VectorItem("q1", [1, 0, 0, 0], {"subjectId": 1}),
        VectorItem("q2", [0, 1, 0, 0], {"subjectId": 2}),
    ]) == 2
    hits = store.search("text_questions", [1, 0, 0, 0], top_k=2)
    assert [hit.id for hit in hits] == ["q1", "q2"]
    assert hits[0].score == 1.0
    assert store.fetch("text_questions", ["q1", "missing"]) == {
        "q1": {"subjectId": 1}
    }
    assert store.list_ids("text_questions") == ["q1", "q2"]
    assert store.count("text_questions") == 2
    assert store.delete("text_questions", "q1") is True
    assert store.list_ids("text_questions") == ["q2"]
    store.clear("text_questions")
    assert "li_an_text_questions" not in client.collections


def test_where_expression_and_top_k_bounds():
    store = _store(_FakeMilvus())
    assert store._where(None) == ""
    assert store._where({"difficulty": 3}) == 'meta["difficulty"] == 3'
    assert store._where({"subjectId": [1, 2]}) == 'meta["subjectId"] in [1, 2]'
    assert store._where({"a": "x", "b": True}) == (
        'meta["a"] == "x" and meta["b"] == true'
    )
    with pytest.raises(InvalidVectorTarget):
        store.search("text_questions", [1, 0, 0, 0], top_k=0)
    with pytest.raises(InvalidVectorTarget):
        store.search("text_questions", [1, 0, 0, 0], top_k=101)


def test_create_collection_uses_schema_and_index(monkeypatch):
    client = _FakeMilvus()
    monkeypatch.setitem(sys.modules, "pymilvus", types.SimpleNamespace(
        DataType=types.SimpleNamespace(VARCHAR="VARCHAR", FLOAT_VECTOR="FLOAT_VECTOR", JSON="JSON")
    ))
    store = MilvusVectorStore(uri="http://milvus:19530", dim=4, client=client)
    assert store.upsert("text_questions", "q1", [1, 0, 0, 0], {"a": 1}) is True
    description = client.collections["li_an_text_questions"]
    assert description["loaded"] is True
    assert description["index"][0]["metric_type"] == "COSINE"
    assert [field["field_name"] for field in description["fields"]] == ["id", "vector", "meta"]


def test_existing_collection_dimension_mismatch_is_corrupt():
    client = _FakeMilvus()
    client.collections["li_an_text_questions"] = {"fields": [
        {"field_name": "vector", "params": {"dim": 8}}
    ]}
    client.rows["li_an_text_questions"] = {}
    store = MilvusVectorStore(uri="http://milvus:19530", dim=4, client=client)
    with pytest.raises(VectorStoreCorrupt):
        store.list_ids("text_questions")


def test_missing_pymilvus_is_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "pymilvus", None)
    store = MilvusVectorStore(uri="http://milvus:19530", dim=4)
    with pytest.raises(VectorStoreUnavailable):
        store.list_ids("text_questions")
    assert store.health().ok is False


def test_health_lists_collections():
    client = _FakeMilvus()
    store = MilvusVectorStore(uri="http://milvus:19530", dim=4, client=client)
    health = store.health()
    assert health.backend == "milvus"
    assert health.ok is True