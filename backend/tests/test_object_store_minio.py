"""MinIO 适配器的协议级测试：用假 S3 服务校验签名、读写与故障映射。

不依赖真实 MinIO（D-F3-9：F3 不把 MinIO 加进 compose）。重点验证
SigV4 头齐全、PUT 的 Content-Length/body 哈希一致、404/5xx/断连语义。
"""
from __future__ import annotations

import hashlib
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.foundation.stores import minio_object
from app.foundation.stores.object import ObjectNotFound, ObjectStoreUnavailable
from app.foundation.stores.object import ObjectStoreUnavailable as Unavailable


class _FakeS3(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    objects: dict[str, bytes] = {}
    headers_seen: list[dict[str, str]] = []
    fail_next = False

    def log_message(self, *args):  # 静默
        pass

    def _key(self) -> str:
        return urllib.parse.unquote(self.path.split("?")[0].lstrip("/")).split("/", 1)[1]

    def _record(self):
        self.headers_seen.append({k.lower(): v for k, v in self.headers.items()})

    def do_PUT(self):
        self._record()
        n = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(n)
        if self.headers.get("x-amz-content-sha256") != hashlib.sha256(body).hexdigest():
            self.send_response(400)
            self.end_headers()
            return
        type(self).objects[self._key()] = body
        self.send_response(200)
        self.send_header("ETag", '"x"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self):
        self._record()
        key = self.path.split("?")[0].lstrip("/").split("/", 1)
        if len(key) == 1:
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = type(self).objects.get(urllib.parse.unquote(key[1]))
        if body is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

    def do_GET(self):
        self._record()
        if type(self).fail_next:
            type(self).fail_next = False
            self.send_response(503)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        parsed = urllib.parse.urlparse(self.path)
        if "list-type" in urllib.parse.parse_qs(parsed.query):
            keys = "".join(f"<Contents><Key>{k}</Key></Contents>" for k in type(self).objects)
            xml = f'<?xml version="1.0"?><ListBucketResult><IsTruncated>false</IsTruncated>{keys}</ListBucketResult>'
            raw = xml.encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        key = urllib.parse.unquote(parsed.path.lstrip("/").split("/", 1)[1])
        body = type(self).objects.get(key)
        if body is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        start, end = 0, len(body) - 1
        status = 200
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            a, b = rng[6:].split("-")
            start = int(a)
            end = int(b) if b else len(body) - 1
            end = min(end, len(body) - 1)
            status = 206
        chunk = body[start:end + 1]
        self.send_response(status)
        self.send_header("Content-Length", str(len(chunk)))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(body)}")
        self.end_headers()
        self.wfile.write(chunk)

    def do_DELETE(self):
        self._record()
        key = urllib.parse.unquote(self.path.lstrip("/").split("/", 1)[1])
        existed = type(self).objects.pop(key, None) is not None
        self.send_response(204 if existed else 404)
        self.send_header("Content-Length", "0")
        self.end_headers()


@pytest.fixture()
def store():
    _FakeS3.objects = {}
    _FakeS3.headers_seen = []
    _FakeS3.fail_next = False
    srv = ThreadingHTTPServer(("127.0.0.1", 0), _FakeS3)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    endpoint = f"127.0.0.1:{srv.server_address[1]}"
    s = minio_object.MinioObjectStore(
        endpoint=endpoint, bucket="media", access_key="AK", secret_key="SK",
        secure=False, region="us-east-1", timeout=2.0,
    )
    try:
        yield s
    finally:
        s._client.close()
        srv.shutdown()
        srv.server_close()


def _key(data: bytes) -> str:
    h = hashlib.sha256(data).hexdigest()
    return f"{h[:2]}/{h}"


def test_put_get_stat_delete(store):
    data = b"hello-minio"
    key = _key(data)
    store.put(key, __import__("io").BytesIO(data), "image/png", sha256=key.split("/")[1], size=len(data))
    assert store.stat(key).size == len(data)
    with store.open(key) as fh:
        assert fh.read() == data
    assert store.delete(key) is True
    assert store.stat(key) is None
    assert store.delete(key) is False
    auth = _FakeS3.headers_seen[0]["authorization"]
    assert auth.startswith("AWS4-HMAC-SHA256 Credential=AK/")
    assert "SignedHeaders=" in auth and "Signature=" in auth


def test_stream_range_is_eager(store):
    data = b"0123456789"
    key = _key(data)
    store.put(key, __import__("io").BytesIO(data), "video/mp4", sha256=key.split("/")[1], size=len(data))
    assert b"".join(store.stream(key, 2, 5)) == b"2345"
    with pytest.raises(ObjectNotFound):
        store.stream(key.replace("0", "1"), 0, 1)


def test_list_and_health(store):
    data = b"abc"
    key = _key(data)
    store.put(key, __import__("io").BytesIO(data), "image/png", sha256=key.split("/")[1], size=len(data))
    assert key in list(store.list_keys(""))
    assert store.health().ok is True


def test_http_errors_map_to_unavailable(store):
    _FakeS3.fail_next = True
    with pytest.raises(ObjectStoreUnavailable):
        store.open(_key(b"x"))


def test_connection_error_maps_to_unavailable():
    s = minio_object.MinioObjectStore(
        endpoint="127.0.0.1:9", bucket="media", access_key="AK", secret_key="SK", timeout=0.3
    )
    try:
        with pytest.raises(Unavailable):
            s.stat(_key(b"x"))
    finally:
        s._client.close()
