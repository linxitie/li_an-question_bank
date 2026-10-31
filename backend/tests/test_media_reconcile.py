"""媒体对账/GC 测试：缺字节、大小不符、孤儿、宽限期与 dry-run/execute。"""
from __future__ import annotations

import hashlib
import io
import os
import sys
import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.foundation import media_reconcile as mr
from app.foundation import media_schema as ms
from app.foundation import schema as fs
from app.foundation.stores.local_object import LocalObjectStore
from app.models.media_asset import MediaAsset


def _put(store: LocalObjectStore, data: bytes) -> tuple[str, str]:
    sha = hashlib.sha256(data).hexdigest()
    key = f"{sha[:2]}/{sha}"
    store.put(key, io.BytesIO(data), "image/png", sha256=sha, size=len(data))
    return sha, key


def _asset(asset_id: str, data: bytes, *, size: int | None = None) -> MediaAsset:
    sha = hashlib.sha256(data).hexdigest()
    return MediaAsset(
        asset_id=asset_id, sha256=sha, object_key=f"{sha[:2]}/{sha}",
        size_bytes=len(data) if size is None else size, content_type="image/png",
        kind="avatar", original_name="a.png", status="active",
        created_at="2026-10-27T10:00:00+08:00",
    )


@pytest.fixture()
def env(tmp_path):
    db = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db}")
    raw = engine.raw_connection().driver_connection
    fs.ensure_schema(raw)
    ms.ensure_media_schema(raw)
    root = tmp_path / "objects"
    store = LocalObjectStore(root)
    with Session(engine) as session:
        yield session, store, root, db
    engine.dispose()


def test_inventory_missing_and_size_mismatch(env):
    session, store, _root, _db = env
    a_data, b_data = b"aaaa", b"bbbb"
    _, a_key = _put(store, a_data)
    _, b_key = _put(store, b_data)
    session.add_all([
        _asset("a" * 32, a_data),
        _asset("b" * 32, b_data),
        _asset("c" * 32, a_data, size=len(a_data) + 9),
    ])
    session.commit()
    store.delete(b_key)
    run = mr.inventory(session, store, include_orphans=False)
    assert run.checked == 3
    assert run.missing_blob == 1
    assert run.size_mismatch == 1
    assert run.drifted == 2
    assert run.status == "drift"
    assert run.report_path and run.report_path.endswith(".json")


def test_orphans_and_gc_grace(env):
    session, store, root, db = env
    data = b"referenced"
    _, key = _put(store, data)
    _, orphan_key = _put(store, b"orphan-bytes")
    session.add(_asset("a" * 32, data))
    session.commit()
    run = mr.inventory(session, store, include_orphans=True)
    assert run.orphan_scan is True
    assert run.orphans == 1
    assert any(d["object_key"] == orphan_key for d in run.details)

    # 导入脚本（scripts/audit 不是包）
    sys.path.insert(0, os.path.join(os.getcwd(), "scripts", "audit"))
    import gc_media_orphans as gc

    picks, total, recent = gc._candidates(session, root, grace_days=7, batch=500)
    assert total == 1 and picks == [] and recent == 1
    picks, _total, _recent = gc._candidates(session, root, grace_days=0, batch=500)
    assert [p["key"] for p in picks] == [orphan_key]

    rc = gc.main(["--db", str(db), "--root", str(root), "--grace-days", "0", "--execute"])
    assert rc == 0
    assert store.stat(orphan_key) is None
    assert store.stat(key) is not None


def test_record_and_freshness(env):
    session, store, _root, _db = env
    data = b"x"
    _put(store, data)
    session.add(_asset("a" * 32, data))
    session.commit()
    run = mr.inventory(session, store)
    mr.record(session, run)
    latest = mr.latest_run(session)
    assert latest and latest["run_id"] == run.run_id
    assert mr.freshness_days(latest) is not None
    assert mr.freshness_days(latest) < 1
