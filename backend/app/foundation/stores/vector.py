"""VectorStore 协议（F6 向量投影）。

事实源仍是 SQLite；向量库只是可重建投影。向量检索只服务内部函数，
不暴露 HTTP，也不作为第二事实源。

集合名、id、向量与 where 条件都在进入实现前统一校验，避免 local 与
Milvus 两个后端对坏输入给出不一致的行为。
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any, Iterable, Protocol, runtime_checkable

_COLLECTION_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class VectorStoreError(Exception):
    """向量存储错误基类。"""


class VectorStoreUnavailable(VectorStoreError):
    """配置关闭、依赖缺失、网络或端点不可用；调用方显式降级。"""


class VectorStoreCorrupt(VectorStoreError):
    """向量文件/集合结构损坏；不得静默当成空索引。"""


class InvalidVectorTarget(VectorStoreError):
    """集合、id、向量、元数据或过滤条件非法。"""


@dataclass(frozen=True)
class VectorHealth:
    backend: str
    ok: bool
    degraded: bool = False
    detail: str = ""


@dataclass(frozen=True)
class VectorHit:
    id: str
    score: float
    meta: dict[str, Any]


@dataclass(frozen=True)
class VectorItem:
    id: str
    vector: list[float]
    meta: dict[str, Any]


@runtime_checkable
class VectorStore(Protocol):
    backend: str
    dim: int

    def upsert(
        self, collection: str, item_id: str, vector: list[float], meta: dict[str, Any]
    ) -> bool: ...

    def upsert_many(self, collection: str, items: Iterable[VectorItem]) -> int: ...

    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[VectorHit]: ...

    def fetch(self, collection: str, ids: list[str]) -> dict[str, dict[str, Any]]: ...

    def list_ids(self, collection: str, limit: int | None = None) -> list[str]: ...

    def delete(self, collection: str, item_id: str) -> bool: ...

    def delete_many(self, collection: str, ids: list[str]) -> int: ...

    def count(self, collection: str) -> int: ...

    def clear(self, collection: str) -> None: ...

    def health(self) -> VectorHealth: ...


def validate_collection(collection: str) -> str:
    if not isinstance(collection, str) or not _COLLECTION_RE.fullmatch(collection):
        raise InvalidVectorTarget(f"非法向量集合名: {collection!r}")
    return collection


def validate_id(item_id: str) -> str:
    if not isinstance(item_id, str) or not item_id:
        raise InvalidVectorTarget("向量 id 不能为空")
    if len(item_id) > 128:
        raise InvalidVectorTarget("向量 id 超过 128 字符")
    if _CONTROL_RE.search(item_id):
        raise InvalidVectorTarget("向量 id 含控制字符")
    return item_id


def validate_meta(meta: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(meta, dict):
        raise InvalidVectorTarget("向量 meta 必须是 dict")
    try:
        json.dumps(meta, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise InvalidVectorTarget(f"向量 meta 不是可序列化 JSON: {exc}") from exc
    return meta


def normalize_vector(vector: list[float], dim: int) -> list[float]:
    if not isinstance(vector, (list, tuple)):
        raise InvalidVectorTarget("向量必须是 float 列表")
    if len(vector) != dim:
        raise InvalidVectorTarget(f"向量维度 {len(vector)} != {dim}")
    values: list[float] = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise InvalidVectorTarget("向量元素必须是数字")
        number = float(value)
        if not math.isfinite(number):
            raise InvalidVectorTarget("向量元素必须是有限数")
        values.append(number)
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        raise InvalidVectorTarget("向量不能是零向量")
    return [value / norm for value in values]


def normalize_where(where: dict[str, Any] | None) -> dict[str, list[Any]]:
    """把等值/IN 条件规范化为 {字段: [候选值...]}；多个字段之间是 AND。"""
    if where is None:
        return {}
    if not isinstance(where, dict):
        raise InvalidVectorTarget("where 必须是 dict")
    result: dict[str, list[Any]] = {}
    for key, raw in where.items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", key):
            raise InvalidVectorTarget(f"非法 where 字段: {key!r}")
        values = list(raw) if isinstance(raw, (list, tuple, set)) else [raw]
        if not values:
            raise InvalidVectorTarget(f"where 字段 {key} 的候选值不能为空")
        cleaned: list[Any] = []
        for value in values:
            if isinstance(value, bool) or isinstance(value, (int, float, str)) or value is None:
                cleaned.append(value)
            else:
                raise InvalidVectorTarget(f"where 字段 {key} 的值类型不支持: {type(value).__name__}")
        result[key] = cleaned
    return result


_store: VectorStore | None = None


def build_vector_store(backend: str | None = None) -> VectorStore:
    """按配置构造单例；off 表示显式关闭。"""
    global _store
    from app.foundation import config as cfg

    name = (backend or cfg.VECTOR_BACKEND or "off").strip().lower()
    if name == "off" or not cfg.VECTOR_STORE_ENABLED:
        raise VectorStoreUnavailable("VECTOR_STORE_ENABLED=false 或 VECTOR_BACKEND=off")
    if _store is not None and getattr(_store, "backend", None) == name:
        return _store
    if name == "local":
        from app.foundation.stores.local_vector import LocalVectorStore

        _store = LocalVectorStore(
            cfg.vector_store_root(), dim=cfg.VECTOR_DIM, max_top_k=cfg.VECTOR_SEARCH_TOP_K_MAX
        )
    elif name == "milvus":
        from app.foundation.stores.milvus_vector import MilvusVectorStore

        _store = MilvusVectorStore(
            uri=cfg.VECTOR_MILVUS_URI,
            token=cfg.VECTOR_MILVUS_TOKEN or "",
            prefix=cfg.VECTOR_MILVUS_PREFIX,
            dim=cfg.VECTOR_DIM,
            max_top_k=cfg.VECTOR_SEARCH_TOP_K_MAX,
        )
    else:
        raise VectorStoreUnavailable(f"未知 VECTOR_BACKEND: {name}（只支持 local/milvus/off）")
    return _store


def reset_vector_store() -> None:
    global _store
    _store = None
