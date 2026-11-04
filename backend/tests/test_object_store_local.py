"""F3 Step 2：local 内容寻址对象存储。"""
from __future__ import annotations

import hashlib
import io

import pytest

from app.foundation.stores.local_object import LocalObjectStore
from app.foundation.stores.object import InvalidObjectKey


def _key(data: bytes) -> tuple[str, str]:
    sha = hashlib.sha256(data).hexdigest()
    return f"{sha[:2]}/{sha}", sha


def test_put_stat_and_idempotent(tmp_path):
    data = b"hello media" * 100
    key, sha = _key(data)
    store = LocalObjectStore(tmp_path)

    store.put(key, io.BytesIO(data), "application/octet-stream", sha256=sha, size=len(data))
    st = store.stat(key)
    assert st is not None and st.size == len(data) and st.sha256 == sha
    path = tmp_path / sha[:2] / sha
    mtime = path.stat().st_mtime_ns

    store.put(key, io.BytesIO(data), "application/octet-stream", sha256=sha, size=len(data))
    assert path.stat().st_mtime_ns == mtime, "同 key 二次 put 不得重写"
    assert [p for p in (tmp_path / sha[:2]).iterdir() if p.name.startswith(".tmp-")] == []


def test_stream_open_and_ranges(tmp_path):
    data = bytes(range(256)) * 40
    key, sha = _key(data)
    store = LocalObjectStore(tmp_path)
    store.put(key, io.BytesIO(data), "application/octet-stream", sha256=sha, size=len(data))

    assert b"".join(store.stream(key)) == data
    assert b"".join(store.stream(key, 10, 19)) == data[10:20]
    assert b"".join(store.stream(key, len(data) - 5)) == data[-5:]
    assert b"".join(store.stream(key, len(data))) == b""
    with store.open(key) as fh:
        assert hashlib.sha256(fh.read()).hexdigest() == sha


def test_delete_existing_and_missing(tmp_path):
    data = b"x"
    key, sha = _key(data)
    store = LocalObjectStore(tmp_path)
    store.put(key, io.BytesIO(data), "text/plain", sha256=sha, size=1)
    assert store.delete(key) is True
    assert store.delete(key) is False
    assert store.stat(key) is None


@pytest.mark.parametrize(
    "bad",
    ["../etc/passwd", "/abs/path", "abc", "AB" * 32, "aa/" + "bb" * 32, "aa/../" + "cc" * 32],
)
def test_invalid_keys_rejected(tmp_path, bad):
    store = LocalObjectStore(tmp_path)
    with pytest.raises(InvalidObjectKey):
        store.stat(bad)


def test_concurrent_put_same_key_leaves_one_file(tmp_path):
    import threading

    data = b"concurrent" * 10000
    key, sha = _key(data)
    store = LocalObjectStore(tmp_path)
    errors: list[BaseException] = []

    def worker():
        try:
            store.put(key, io.BytesIO(data), "application/octet-stream", sha256=sha, size=len(data))
        except BaseException as e:  # noqa: BLE001 - 测试收集线程异常
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert (tmp_path / sha[:2] / sha).read_bytes() == data
    assert len(list((tmp_path / sha[:2]).glob("*"))) == 1


def test_list_keys_and_health(tmp_path):
    store = LocalObjectStore(tmp_path)
    for data in (b"a", b"b"):
        key, sha = _key(data)
        store.put(key, io.BytesIO(data), "text/plain", sha256=sha, size=1)
    assert len(list(store.list_keys())) == 2
    health = store.health()
    assert health.backend == "local" and health.ok is True
