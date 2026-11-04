"""EmbeddingPort：off / hash / http 三种提供者。

hash 提供者是确定性的**离线验证**工具，输出被标记为 degraded，不能冒充
语义模型；真实语义索引必须由用户显式配置 OpenAI 兼容 embeddings 服务。
"""
from __future__ import annotations

import hashlib
import math
from typing import Protocol, runtime_checkable

import httpx


class EmbeddingError(Exception):
    """Embedding 调用错误基类。"""


class EmbeddingUnavailable(EmbeddingError):
    """未配置、依赖/网络不可用；调用方显式降级。"""


class DimensionMismatch(EmbeddingError):
    """返回向量维度与配置不一致。"""


@runtime_checkable
class EmbeddingPort(Protocol):
    provider: str
    dim: int
    degraded: bool

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _check_texts(texts: list[str]) -> list[str]:
    if not isinstance(texts, list) or not texts:
        raise EmbeddingError("embed 需要非空文本列表")
    cleaned = []
    for text in texts:
        if not isinstance(text, str):
            raise EmbeddingError("embed 文本必须是 str")
        if not text.strip():
            raise EmbeddingError("embed 文本不能为空")
        cleaned.append(text)
    return cleaned


def _normalize(vector: list[float], dim: int) -> list[float]:
    if len(vector) != dim:
        raise DimensionMismatch(f"向量维度 {len(vector)} != {dim}")
    values: list[float] = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise EmbeddingError("向量元素必须是数字")
        number = float(value)
        if not math.isfinite(number):
            raise EmbeddingError("向量元素必须是有限数")
        values.append(number)
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        raise EmbeddingError("向量不能是零向量")
    return [value / norm for value in values]


class OffEmbedding:
    provider = "off"
    degraded = False

    def __init__(self, dim: int):
        self.dim = int(dim)

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingUnavailable("EMBEDDING_ENABLED=false 或 EMBEDDING_PROVIDER=off")


class HashEmbedding:
    """字符 1/2/3-gram 的有符号 blake2b 哈希；仅用于确定性验证。"""

    provider = "hash"
    degraded = True

    def __init__(self, dim: int):
        if dim <= 0:
            raise ValueError("dim 必须是正整数")
        self.dim = int(dim)

    def _one(self, text: str) -> list[float]:
        body = text.strip().lower()
        vector = [0.0] * self.dim
        grams: list[str] = []
        for size in (1, 2, 3):
            for index in range(max(0, len(body) - size + 1)):
                grams.append(body[index:index + size])
        for gram in grams:
            digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big", signed=False)
            sign = 1.0 if value & 1 else -1.0
            slot = (value >> 1) % self.dim
            vector[slot] += sign
        return _normalize(vector, self.dim)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(text) for text in _check_texts(texts)]


class HttpEmbedding:
    """OpenAI 兼容 /embeddings；批量发送，失败按类型映射异常。"""

    provider = "http"
    degraded = False

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "",
        dim: int,
        timeout: float = 30.0,
        batch_size: int = 32,
    ):
        if not base_url or not model:
            raise EmbeddingUnavailable("EMBEDDING_BASE_URL/EMBEDDING_MODEL 未配置")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.dim = int(dim)
        self.timeout = float(timeout)
        self.batch_size = max(1, int(batch_size))
        self._client: httpx.Client | None = None

    @property
    def endpoint(self) -> str:
        if self.base_url.endswith("/embeddings"):
            return self.base_url
        return self.base_url + "/embeddings"

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.timeout)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        cleaned = _check_texts(texts)
        output: list[list[float]] = []
        for start in range(0, len(cleaned), self.batch_size):
            batch = cleaned[start:start + self.batch_size]
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            payload = {
                "model": self.model,
                "input": batch,
                "encoding_format": "float",
            }
            try:
                response = self._get_client().post(self.endpoint, json=payload, headers=headers)
            except httpx.HTTPError as exc:
                raise EmbeddingUnavailable(f"embeddings 网络错误: {exc}") from exc
            if response.status_code in (429, 500, 502, 503, 504):
                raise EmbeddingUnavailable(
                    f"embeddings 暂时不可用: HTTP {response.status_code}"
                )
            if response.status_code >= 400:
                raise EmbeddingError(
                    f"embeddings 请求被拒绝: HTTP {response.status_code} {response.text[:200]}"
                )
            try:
                data = response.json()
                rows = data["data"]
            except (ValueError, KeyError, TypeError) as exc:
                raise EmbeddingError(f"embeddings 响应结构非法: {exc}") from exc
            if not isinstance(rows, list) or len(rows) != len(batch):
                raise EmbeddingError("embeddings 返回条数与输入不一致")
            ordered = sorted(rows, key=lambda row: int(row.get("index", 0)))
            for row in ordered:
                vector = row.get("embedding") if isinstance(row, dict) else None
                if not isinstance(vector, list):
                    raise EmbeddingError("embeddings 响应缺少 embedding")
                output.append(_normalize(vector, self.dim))
        return output


def build_embedding_port(provider: str | None = None) -> EmbeddingPort:
    from app.foundation import config as cfg

    name = (provider or cfg.EMBEDDING_PROVIDER or "off").strip().lower()
    if name == "off" or (provider is None and not cfg.EMBEDDING_ENABLED):
        return OffEmbedding(cfg.EMBEDDING_DIM)
    if name == "hash":
        return HashEmbedding(cfg.EMBEDDING_DIM)
    if name == "http":
        return HttpEmbedding(
            base_url=cfg.EMBEDDING_BASE_URL,
            model=cfg.EMBEDDING_MODEL,
            api_key=cfg.EMBEDDING_API_KEY or "",
            dim=cfg.EMBEDDING_DIM,
            timeout=cfg.EMBEDDING_TIMEOUT_SECONDS,
            batch_size=cfg.EMBEDDING_BATCH_SIZE,
        )
    raise EmbeddingUnavailable(f"未知 EMBEDDING_PROVIDER: {name}（只支持 off/hash/http）")
