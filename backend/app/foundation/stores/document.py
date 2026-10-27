"""DocumentStore 协议（F4 文档投影）。

事实源仍是 SQLite；文档库只是可重建投影。本模块只描述文档读写与键规范，
不参与业务事务，也不提供 HTTP 读接口。
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterator, Protocol, runtime_checkable

COLLECTIONS = ("exam_resources", "import_snapshots", "forum_contents")

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class DocumentStoreError(Exception):
    """文档存储错误基类。"""


class DocumentStoreUnavailable(DocumentStoreError):
    """网络/依赖/磁盘等可重试故障；调用方交给 Outbox 重试。"""


class DocumentStoreCorrupt(DocumentStoreError):
    """已有文档无法解析；不得当成空文档覆盖。"""


class InvalidDocumentKey(DocumentStoreError):
    """集合未知，或 key 含控制字符/超长。"""


class DocumentTooLarge(DocumentStoreError):
    """序列化后超过单文档上限；必须显式失败，不截断。"""


@dataclass(frozen=True)
class DocumentHealth:
    backend: str
    ok: bool
    degraded: bool = False
    detail: str = ""


@runtime_checkable
class DocumentStore(Protocol):
    backend: str

    def upsert(
        self, collection: str, key: str, doc: dict[str, Any], *, version: int
    ) -> bool: ...

    def get(self, collection: str, key: str) -> dict[str, Any] | None: ...

    def delete(self, collection: str, key: str) -> bool: ...

    def iter_keys(self, collection: str) -> Iterator[str]: ...

    def health(self) -> DocumentHealth: ...


def validate_target(collection: str, key: str) -> tuple[str, str]:
    if collection not in COLLECTIONS:
        raise InvalidDocumentKey(f"未知文档集合: {collection!r}")
    if not isinstance(key, str) or not key:
        raise InvalidDocumentKey("文档 key 不能为空")
    if len(key) > 512:
        raise InvalidDocumentKey("文档 key 超过 512 字符")
    if _CONTROL_RE.search(key):
        raise InvalidDocumentKey("文档 key 含控制字符")
    if "/" in key or "\\" in key or key in {".", ".."}:
        raise InvalidDocumentKey("文档 key 不允许路径分隔符")
    return collection, key


def canonical_json(payload: Any) -> str:
    """稳定序列化：同内容同字节，便于版本比较与对账哈希。"""
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise DocumentStoreError(f"文档不是可序列化 JSON: {exc}") from exc


def document_digest(collection: str, key: str) -> str:
    return hashlib.sha256(f"{collection}\0{key}".encode("utf-8")).hexdigest()


_store: DocumentStore | None = None


def build_document_store(backend: str | None = None) -> DocumentStore:
    """按配置构造单例；local 默认，mongo 可选。"""
    global _store
    from app.foundation import config as cfg

    name = (backend or cfg.DOC_STORE_BACKEND or "local").strip().lower()
    if name == "off":
        raise DocumentStoreUnavailable("DOC_STORE_BACKEND=off")
    if _store is not None and getattr(_store, "backend", None) == name:
        return _store
    if name == "local":
        from app.foundation.stores.local_document import LocalDocumentStore

        _store = LocalDocumentStore(cfg.document_store_root(), max_bytes=cfg.DOC_STORE_MAX_BYTES)
    elif name == "mongo":
        from app.foundation.stores.mongo_document import MongoDocumentStore

        _store = MongoDocumentStore(
            uri=cfg.DOC_STORE_MONGO_URI,
            database=cfg.DOC_STORE_MONGO_DB,
            prefix=cfg.DOC_STORE_MONGO_PREFIX,
            max_bytes=cfg.DOC_STORE_MAX_BYTES,
        )
    else:
        raise DocumentStoreUnavailable(
            f"未知 DOC_STORE_BACKEND: {name}（只支持 local/mongo）"
        )
    return _store


def reset_document_store() -> None:
    """测试/切换配置用：清空单例。"""
    global _store
    _store = None
