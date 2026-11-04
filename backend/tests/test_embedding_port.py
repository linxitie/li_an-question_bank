"""EmbeddingPort 单元测试（F6）。"""
from __future__ import annotations

import httpx
import pytest

from app.foundation.ports.ai import (
    DimensionMismatch,
    EmbeddingError,
    EmbeddingUnavailable,
    HashEmbedding,
    HttpEmbedding,
    OffEmbedding,
    build_embedding_port,
)


class _FakeResponse:
    def __init__(self, status: int, payload=None, text: str = ""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self):
        pass


def test_hash_is_deterministic_normalized_and_degrades():
    port = HashEmbedding(dim=32)
    first = port.embed(["中华人民共和国"])[0]
    second = port.embed(["中华人民共和国"])[0]
    assert first == second
    assert port.provider == "hash"
    assert port.degraded is True
    norm = sum(value * value for value in first) ** 0.5
    assert abs(norm - 1.0) < 1e-9
    assert port.embed(["A", "B"])[0] != first


def test_hash_rejects_empty_and_bad_input():
    port = HashEmbedding(dim=8)
    with pytest.raises(EmbeddingError):
        port.embed([])
    with pytest.raises(EmbeddingError):
        port.embed(["   "])
    with pytest.raises(EmbeddingError):
        port.embed([1])  # type: ignore[list-item]


def test_off_embedding_raises_unavailable():
    port = OffEmbedding(dim=8)
    assert port.provider == "off"
    with pytest.raises(EmbeddingUnavailable):
        port.embed(["文本"])


def test_http_embeddings_batches_and_orders_by_index():
    client = _FakeClient([
        _FakeResponse(200, {"data": [
            {"index": 1, "embedding": [0.0, 2.0]},
            {"index": 0, "embedding": [2.0, 0.0]},
        ]}),
        _FakeResponse(200, {"data": [{"index": 0, "embedding": [0.0, 3.0]}]}),
    ])
    port = HttpEmbedding(
        base_url="http://example.test/v1", model="m", api_key="k",
        dim=2, batch_size=2,
    )
    port._client = client  # type: ignore[assignment]
    vectors = port.embed(["a", "b", "c"])
    assert len(vectors) == 3
    assert vectors[0] == [1.0, 0.0]
    assert vectors[1] == [0.0, 1.0]
    assert vectors[2] == [0.0, 1.0]
    assert len(client.calls) == 2
    assert client.calls[0]["url"] == "http://example.test/v1/embeddings"
    assert client.calls[0]["headers"]["Authorization"] == "Bearer k"
    assert client.calls[0]["json"]["input"] == ["a", "b"]


def test_http_embeddings_endpoint_passthrough_and_error_mapping():
    port = HttpEmbedding(base_url="http://example.test/embeddings", model="m", dim=2)
    assert port.endpoint == "http://example.test/embeddings"

    port._client = _FakeClient([_FakeResponse(429, text="slow")])  # type: ignore[assignment]
    with pytest.raises(EmbeddingUnavailable):
        port.embed(["a"])

    port._client = _FakeClient([_FakeResponse(401, text="bad key")])  # type: ignore[assignment]
    with pytest.raises(EmbeddingError):
        port.embed(["a"])

    port._client = _FakeClient([_FakeResponse(200, {"data": []})])  # type: ignore[assignment]
    with pytest.raises(EmbeddingError):
        port.embed(["a"])

    port._client = _FakeClient([_FakeResponse(200, {"data": [
        {"index": 0, "embedding": [1.0, 2.0, 3.0]}
    ]})])  # type: ignore[assignment]
    with pytest.raises(DimensionMismatch):
        port.embed(["a"])

    port._client = _FakeClient([httpx.ConnectError("boom")])  # type: ignore[assignment]
    with pytest.raises(EmbeddingUnavailable):
        port.embed(["a"])


def test_build_embedding_port_respects_switch(monkeypatch):
    from app.foundation import config as cfg

    monkeypatch.setattr(cfg, "EMBEDDING_ENABLED", False)
    monkeypatch.setattr(cfg, "EMBEDDING_PROVIDER", "off")
    assert build_embedding_port().provider == "off"
    assert build_embedding_port("hash").provider == "hash"
    with pytest.raises(EmbeddingUnavailable):
        build_embedding_port("unknown")
