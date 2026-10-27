"""MongoDB 文档存储（可选依赖，默认不启用）。

版本守卫与 local 一致：旧版本不覆盖新版本；pymongo 缺失时明确抛
DocumentStoreUnavailable，由 Outbox 重试，绝不静默丢文档。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterator

from app.foundation.stores.document import (
    DocumentHealth,
    DocumentStoreCorrupt,
    DocumentStoreUnavailable,
    DocumentTooLarge,
    canonical_json,
    validate_target,
)

logger = logging.getLogger(__name__)


class MongoDocumentStore:
    backend = "mongo"

    def __init__(
        self,
        *,
        uri: str,
        database: str,
        prefix: str = "",
        max_bytes: int = 8 * 1024 * 1024,
        timeout_ms: int = 3000,
    ):
        if not uri:
            raise DocumentStoreUnavailable("DOC_STORE_MONGO_URI 未配置")
        try:
            from pymongo import MongoClient
        except ImportError as exc:
            raise DocumentStoreUnavailable("pymongo 未安装") from exc
        self.max_bytes = max(1024, int(max_bytes))
        self._prefix = prefix or ""
        self._client = MongoClient(uri, serverSelectionTimeoutMS=timeout_ms)
        self._db = self._client[database]

    def upsert(
        self, collection: str, key: str, doc: dict[str, Any], *, version: int
    ) -> bool:
        collection, key = validate_target(collection, key)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ValueError(f"version 必须是正整数: {version!r}")
        body = canonical_json(doc)
        if len(body.encode("utf-8")) > self.max_bytes:
            raise DocumentTooLarge(f"文档 {collection}/{key} 超过 {self.max_bytes} 字节")
        coll = self._collection(collection)
        envelope = {
            "_id": key,
            "version": version,
            "document": doc,
            "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        try:
            result = coll.update_one(
                {"_id": key, "version": {"$lt": version}},
                {"$set": envelope},
                upsert=False,
            )
            if result.matched_count:
                return True
            if coll.find_one({"_id": key}, {"_id": 1}) is not None:
                return False
            coll.insert_one(envelope)
            return True
        except Exception as exc:  # noqa: BLE001 - 统一映射为可重试故障
            raise DocumentStoreUnavailable(f"Mongo 写入失败: {exc}") from exc

    def get(self, collection: str, key: str) -> dict[str, Any] | None:
        collection, key = validate_target(collection, key)
        try:
            row = self._collection(collection).find_one({"_id": key})
        except Exception as exc:  # noqa: BLE001
            raise DocumentStoreUnavailable(f"Mongo 读取失败: {exc}") from exc
        if row is None:
            return None
        doc = row.get("document")
        if not isinstance(doc, dict):
            raise DocumentStoreCorrupt(f"文档结构非法 {collection}/{key}")
        return doc

    def delete(self, collection: str, key: str) -> bool:
        collection, key = validate_target(collection, key)
        try:
            result = self._collection(collection).delete_one({"_id": key})
        except Exception as exc:  # noqa: BLE001
            raise DocumentStoreUnavailable(f"Mongo 删除失败: {exc}") from exc
        return bool(result.deleted_count)

    def iter_keys(self, collection: str) -> Iterator[str]:
        if collection not in ("exam_resources", "import_snapshots", "forum_contents"):
            raise ValueError(f"未知文档集合: {collection!r}")
        try:
            cursor = self._collection(collection).find({}, {"_id": 1})
            for row in cursor:
                key = row.get("_id")
                if isinstance(key, str):
                    yield key
        except Exception as exc:  # noqa: BLE001
            raise DocumentStoreUnavailable(f"Mongo 枚举失败: {exc}") from exc

    def health(self) -> DocumentHealth:
        try:
            self._client.admin.command("ping")
            return DocumentHealth(backend=self.backend, ok=True, detail=self._db.name)
        except Exception as exc:  # noqa: BLE001
            return DocumentHealth(
                backend=self.backend, ok=False, degraded=True, detail=str(exc)
            )

    def _collection(self, collection: str):
        return self._db[f"{self._prefix}{collection}"]
