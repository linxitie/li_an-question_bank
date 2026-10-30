"""F4 文档对账/回填/双读测试。"""
from __future__ import annotations

import os
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.foundation import document_reconcile as dr
from app.foundation import document_shadow as ds
from app.foundation import schema as fs
from app.foundation.stores.document import reset_document_store
from app.foundation.stores.local_document import LocalDocumentStore


@pytest.fixture()
def env(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db}")
    raw = engine.raw_connection().driver_connection
    fs.ensure_schema(raw)
    store = LocalDocumentStore(tmp_path / "docs")
    from app.foundation import config as cfg

    monkeypatch.setattr(cfg, "DOC_STORE_BACKEND", "local")
    monkeypatch.setattr(cfg, "DOC_STORE_ROOT", str(tmp_path / "docs"))
    reset_document_store()
    with Session(engine) as session:
        yield session, store, db, tmp_path
    reset_document_store()
    engine.dispose()


def _doc(name: str, *, version: int = 1) -> dict:
    return {"@type": "ExamPaper", "paperId": name, "name": name, "version": version}


def _sources(docs):
    def _iter(_session, collection, limit=None):
        rows = [(key, doc) for key, doc in docs.items()]
        if limit:
            rows = rows[:limit]
        for key, doc in rows:
            yield key, (lambda value=doc: value)

    return _iter


def test_inspect_detects_missing_mismatch_orphan(env, monkeypatch):
    session, store, _db, _tmp = env
    store.upsert("exam_resources", "1", _doc("同"), version=7)  # version 不参与比较
    store.upsert("exam_resources", "2", _doc("旧"), version=3)
    store.upsert("exam_resources", "9", _doc("孤儿"), version=1)
    monkeypatch.setattr(
        dr, "iter_sources", _sources({"1": _doc("同"), "2": _doc("新"), "3": _doc("缺")})
    )
    run = dr.inspect(session, store, collection="exam_resources")
    assert run.checked == 3
    assert run.missing == 1
    assert run.mismatched == 1
    assert run.orphan == 1
    assert run.drifted == 3
    assert run.status == "drift"
    assert run.report_path


def test_inspect_limit_skips_orphan_scan(env, monkeypatch):
    session, store, _db, _tmp = env
    store.upsert("exam_resources", "9", _doc("孤儿"), version=1)
    monkeypatch.setattr(dr, "iter_sources", _sources({"1": _doc("一")}))
    run = dr.inspect(session, store, collection="exam_resources", limit=1)
    assert run.missing == 1
    assert run.orphan == 0


def test_record_and_freshness(env, monkeypatch):
    session, store, _db, _tmp = env
    monkeypatch.setattr(dr, "iter_sources", _sources({}))
    run = dr.inspect(session, store, collection="exam_resources")
    dr.record(session, run)
    latest = dr.latest_run(session)
    assert latest and latest["run_id"] == run.run_id
    assert dr.freshness_days(latest) is not None


def test_shadow_compare_ok_and_mismatch(env, monkeypatch):
    session, store, _tmp, root = env
    monkeypatch.setattr(ds, "build_document_store", lambda: store)
    monkeypatch.setattr(
        ds, "_build_expected", lambda _s, _c, key: _doc("目标" if key == "1" else "新")
    )
    store.upsert("exam_resources", "1", _doc("目标"), version=4)
    store.upsert("exam_resources", "2", _doc("旧"), version=4)
    assert ds.compare(session, "exam_resources", "1")["status"] == "ok"
    result = ds.compare(session, "exam_resources", "2")
    assert result["status"] == "mismatch"
    assert result["reason"] == "content_changed"
    assert ds.REPORT_PATH.exists()


def test_shadow_error_does_not_raise(env, monkeypatch):
    session, _store, _tmp, _root = env

    def boom():
        raise RuntimeError("down")

    monkeypatch.setattr(ds, "build_document_store", boom)
    monkeypatch.setattr(ds, "_build_expected", lambda _s, _c, _k: _doc("x"))
    result = ds.compare(session, "exam_resources", "1")
    assert result["status"] == "error"
    assert "down" in result["error"]


def test_backfill_dry_run_and_apply(env, monkeypatch):
    session, store, db, _tmp = env
    sys.path.insert(0, os.path.join(os.getcwd(), "scripts", "foundation"))
    import backfill_documents as bf

    docs = {"1": _doc("一"), "2": _doc("二")}
    monkeypatch.setattr(bf, "iter_sources", _sources(docs))
    monkeypatch.setattr(bf, "build_document_store", lambda: store)

    assert bf.main(["--db", str(db)]) == 0
    assert store.get("exam_resources", "1") is None

    assert bf.main(["--db", str(db), "--apply", "--collection", "exam_resources"]) == 0
    assert store.get("exam_resources", "1") is not None
    assert store.get("exam_resources", "2") is not None
    row = session.execute(
        text("SELECT cursor, done FROM foundation_backfill_state WHERE source=:s"),
        {"s": "document:exam_resources"},
    ).first()
    assert row is not None and row[0] == "2" and row[1] == 2


def test_backfill_skips_too_large(env, monkeypatch):
    session, store, db, _tmp = env
    sys.path.insert(0, os.path.join(os.getcwd(), "scripts", "foundation"))
    import backfill_documents as bf

    monkeypatch.setattr(bf, "iter_sources", _sources({"1": _doc("大")}))
    monkeypatch.setattr(bf, "build_document_store", lambda: store)
    monkeypatch.setattr(bf, "DOC_STORE_MAX_BYTES", 10)
    assert bf.main(["--db", str(db), "--apply", "--collection", "exam_resources"]) == 0
    assert store.get("exam_resources", "1") is None
