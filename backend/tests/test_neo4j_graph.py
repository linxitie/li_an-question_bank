"""Neo4j 图存储适配器的 fake HTTP 契约测试。"""
from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.foundation.stores.graph import (
    GraphStoreCorrupt,
    GraphStoreError,
    GraphStoreUnavailable,
)
from app.foundation.stores.neo4j_graph import Neo4jGraphStore


class _FakeNeo4j:
    def __init__(self):
        self.requests: list[dict] = []
        self.responder = lambda statement, params: (200, _rows())

    def handle(self, statement, params, auth):
        self.requests.append({"statement": statement, "params": params, "auth": auth})
        return self.responder(statement, params)


def _rows(columns=None, rows=None):
    return {
        "results": [{
            "columns": columns or [],
            "data": [{"row": row} for row in (rows or [])],
        }],
        "errors": [],
    }


def _make_handler(fake: _FakeNeo4j):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):  # noqa: N802 - http.server 约定
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            statement = body["statements"][0]["statement"]
            params = body["statements"][0].get("parameters") or {}
            status, payload = fake.handle(statement, params, self.headers.get("Authorization"))
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            return

    return Handler


@pytest.fixture()
def fake():
    fake = _FakeNeo4j()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(fake))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    fake.uri = f"http://{host}:{port}"
    yield fake
    server.shutdown()
    server.server_close()


def _store(fake, **kwargs):
    return Neo4jGraphStore(
        uri=fake.uri, user="neo4j", password="secret", database="neo4j", **kwargs
    )


def test_requires_uri_and_password():
    with pytest.raises(GraphStoreUnavailable):
        Neo4jGraphStore(uri="", user="neo4j", password="secret")
    with pytest.raises(GraphStoreUnavailable):
        Neo4jGraphStore(uri="http://localhost:7474", user="neo4j", password="")


def test_upsert_node_sends_basic_auth_and_cypher(fake):
    fake.responder = lambda statement, params: (
        200, _rows(["current", "version"], [[0, 1]])
    )
    store = _store(fake)
    assert store.upsert_node("KnowledgePoint", "7", {"name": "x"}, version=1) is True

    request = fake.requests[0]
    assert "MERGE (n:LiAnNode:`KnowledgePoint` {key: $key})" in request["statement"]
    assert "$version > current" in request["statement"]
    assert request["params"]["key"] == "7"
    assert request["params"]["label"] == "KnowledgePoint"
    assert request["params"]["props"] == {"name": "x"}
    scheme, encoded = request["auth"].split(" ", 1)
    assert scheme == "Basic"
    assert base64.b64decode(encoded).decode() == "neo4j:secret"


def test_upsert_node_version_guard_returns_false(fake):
    fake.responder = lambda statement, params: (
        200, _rows(["current", "version"], [[2, 2]])
    )
    assert _store(fake).upsert_node("KnowledgePoint", "7", {}, version=2) is False


def test_upsert_edge_missing_endpoint_is_corrupt(fake):
    fake.responder = lambda statement, params: (200, _rows(["c"], [[0]]))
    with pytest.raises(GraphStoreCorrupt):
        _store(fake).upsert_edge(
            "INSTANCE_OF", ("Question", "1"), ("KnowledgePoint", "7"), {}
        )
    assert "MATCH (a:LiAnNode:`Question` {key: $src_key})" in fake.requests[0]["statement"]


def test_auth_failure_maps_to_unavailable(fake):
    fake.responder = lambda statement, params: (401, {"errors": []})
    with pytest.raises(GraphStoreUnavailable, match="认证失败"):
        _store(fake).clear()


def test_server_error_maps_to_unavailable(fake):
    fake.responder = lambda statement, params: (503, {"errors": []})
    with pytest.raises(GraphStoreUnavailable, match="HTTP 503"):
        _store(fake).clear()


def test_cypher_error_maps_to_store_error(fake):
    fake.responder = lambda statement, params: (
        200, {"results": [], "errors": [{"message": "bad cypher"}]}
    )
    with pytest.raises(GraphStoreError, match="bad cypher"):
        _store(fake).clear()


def test_health_reports_degraded_without_raising(fake):
    fake.responder = lambda statement, params: (500, {"errors": []})
    health = _store(fake).health()
    assert health.backend == "neo4j"
    assert health.ok is False
    assert health.degraded is True


def test_counts_aggregates_node_and_edge_rows(fake):
    def responder(statement, params):
        if "count(n) AS c" in statement:
            return 200, _rows(["c"], [[3]])
        if "type(r) AS rel" in statement:
            return 200, _rows(["rel", "c"], [["INSTANCE_OF", 2]])
        return 200, _rows(["label", "c"], [["KnowledgePoint", 3]])

    fake.responder = responder
    counts = _store(fake).counts()
    assert counts["nodes"] == 3
    assert counts["edges"] == 2
    assert counts["nodes_by_label"] == {"KnowledgePoint": 3}
    assert counts["edges_by_rel"] == {"INSTANCE_OF": 2}
