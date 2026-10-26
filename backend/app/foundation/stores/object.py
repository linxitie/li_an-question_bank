"""对象存储协议（F3 Object 投影）。

设计要点：DB 的 media_assets 是事实源，字节是可重建投影；本协议只描述
字节读写，不参与业务事务。local 默认、MinIO 可选，两者语义一致。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Iterator, Protocol, runtime_checkable


class ObjectStoreError(Exception):
    """对象存储错误基类。"""


class ObjectStoreUnavailable(ObjectStoreError):
    """网络/认证/超时等可重试故障；调用方应返回 503 而不是半条业务数据。"""


class ObjectNotFound(ObjectStoreError):
    """对象不存在。"""


class InvalidObjectKey(ObjectStoreError):
    """key 不是 64 位小写 hex，或不是预期的 <sha[:2]>/<sha> 形态。"""


@dataclass(frozen=True)
class ObjectStat:
    key: str
    size: int
    sha256: str | None = None


@dataclass(frozen=True)
class StoreHealth:
    backend: str
    ok: bool
    degraded: bool = False
    detail: str = ""


@runtime_checkable
class ObjectStore(Protocol):
    backend: str

    def put(
        self,
        key: str,
        source: BinaryIO,
        content_type: str,
        *,
        sha256: str,
        size: int,
    ) -> None: ...

    def open(self, key: str) -> BinaryIO: ...

    def stream(
        self, key: str, start: int = 0, end: int | None = None
    ) -> Iterator[bytes]: ...

    def stat(self, key: str) -> ObjectStat | None: ...

    def delete(self, key: str) -> bool: ...

    def health(self) -> StoreHealth: ...

    def list_keys(self, prefix: str = "") -> Iterator[str]: ...


_store: ObjectStore | None = None


def build_object_store(backend: str | None = None) -> ObjectStore:
    """按配置构造单例；local 与 minio 返回同一协议实现。"""
    global _store
    from app.foundation import config as cfg

    name = (backend or cfg.OBJECT_STORE_BACKEND or "local").strip().lower()
    if _store is not None and getattr(_store, "backend", None) == name:
        return _store
    if name == "local":
        from app.foundation.stores.local_object import LocalObjectStore

        _store = LocalObjectStore(cfg.object_store_root())
    elif name == "minio":
        from app.foundation.stores.minio_object import MinioObjectStore

        _store = MinioObjectStore(
            endpoint=cfg.MINIO_ENDPOINT,
            bucket=cfg.MINIO_BUCKET,
            access_key=cfg.MINIO_ACCESS_KEY,
            secret_key=cfg.MINIO_SECRET_KEY,
            secure=cfg.MINIO_SECURE,
            region=cfg.MINIO_REGION,
        )
    else:
        raise ValueError(f"未知 OBJECT_STORE_BACKEND: {name}（只支持 local/minio）")
    return _store


def reset_object_store() -> None:
    """测试用：丢弃单例，使下一次 build 读取新配置。"""
    global _store
    _store = None


def normalize_key(key: str) -> str:
    """校验并规范化内容寻址 key。

    只接受 64 位小写 hex，或 <sha[:2]>/<64hex> 且前缀必须匹配。
    拒绝绝对路径、反斜杠、..、空段，彻底杜绝路径穿越。
    """
    import re

    if not isinstance(key, str):
        raise InvalidObjectKey("key 必须是字符串")
    candidate = key
    if "/" in candidate:
        parts = candidate.split("/")
        if len(parts) != 2:
            raise InvalidObjectKey(f"非法对象 key: {key!r}")
        prefix, digest = parts
        if prefix != digest[:2]:
            raise InvalidObjectKey(f"key 前缀与 sha256 不匹配: {key!r}")
    else:
        digest = candidate
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise InvalidObjectKey(f"非法对象 key: {key!r}")
    return f"{digest[:2]}/{digest}"
