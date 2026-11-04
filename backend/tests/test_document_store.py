"""F4 DocumentStore：local 原子写、版本守卫、路径安全与可选 Mongo 失败映射。"""
from __future__ import annotations

import json

import pytest

from app.foundation.stores.document import (
    DocumentStoreUnavailable,
    DocumentTooLarge,
    InvalidDocumentKey,
    build_document_store,
    reset_document_store,
)
from app.foundation.stores.local_document import LocalDocumentStore
from app.foundation.stores.mongo_document import MongoDocumentStore


def test_local_upsert_get_delete_health(tmp_path):
    store = LocalDocumentStore(tmp_path)
    assert store.health().ok is True
    assert store.get("exam_resources", "38") is None

    assert store.upsert("exam_resources", "38", {"payload": {"paperId": 38}}, version=1)
    assert store.get("exam_resources", "38") == {"payload": {"paperId": 38}}
    assert store.upsert("exam_resources", "38", {"payload": {"paperId": 39}}, version=2)
    assert store.get("exam_resources", "38")["payload"]["paperId"] == 39

    assert store.delete("exam_resources", "38") is True
    assert store.delete("exam_resources", "38") is False
    assert store.get("exam_resources", "38") is None


def test_old_or_same_version_does_not_overwrite(tmp_path):
    store = LocalDocumentStore(tmp_path)
    store.upsert("forum_contents", "5", {"payload": {"v": "new"}}, version=3)

    assert store.upsert("forum_contents", "5", {"payload": {"v": "old"}}, version=2) is False
    assert store.upsert("forum_contents", "5", {"payload": {"v": "same"}}, version=3) is False
    assert store.get("forum_contents", "5")["payload"]["v"] == "new"


def test_invalid_collection_and_key_rejected(tmp_path):
    store = LocalDocumentStore(tmp_path)
    with pytest.raises(InvalidDocumentKey):
        store.upsert("unknown", "1", {}, version=1)
    for key in ("", "../x", "a/b", "a\\b", "a\x00b"):
        with pytest.raises(InvalidDocumentKey):
            store.upsert("exam_resources", key, {}, version=1)


def test_too_large_document_fails_without_truncation(tmp_path):
    store = LocalDocumentStore(tmp_path, max_bytes=1024)
    with pytest.raises(DocumentTooLarge):
        store.upsert("forum_contents", "1", {"payload": "x" * 4096}, version=1)
    assert store.get("forum_contents", "1") is None


def test_corrupt_file_raises_instead_of_empty(tmp_path):
    store = LocalDocumentStore(tmp_path)
    path = store._path("forum_contents", "9")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    from app.foundation.stores.document import DocumentStoreCorrupt

    with pytest.raises(DocumentStoreCorrupt):
        store.get("forum_contents", "9")


def test_iter_keys_returns_stored_keys(tmp_path):
    store = LocalDocumentStore(tmp_path)
    store.upsert("import_snapshots", "question_import_record:1", {"a": 1}, version=1)
    store.upsert("import_snapshots", "question_import_record:2", {"a": 2}, version=1)
    assert sorted(store.iter_keys("import_snapshots")) == [
        "question_import_record:1",
        "question_import_record:2",
    ]


def test_factory_uses_local_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("DOC_STORE_BACKEND", "local")
    monkeypatch.setenv("DOC_STORE_ROOT", str(tmp_path))
    reset_document_store()
    store = build_document_store()
    assert store.backend == "local"
    assert store.health().ok is True
    reset_document_store()


def test_mongo_requires_uri_and_pymongo():
    with pytest.raises(DocumentStoreUnavailable):
        MongoDocumentStore(uri="", database="x")


def test_health_probe_does_not_leave_file(tmp_path):
    store = LocalDocumentStore(tmp_path)
    assert store.health().ok is True
    assert not (tmp_path / ".health-probe").exists()
