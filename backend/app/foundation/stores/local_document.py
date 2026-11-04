"""local 文档存储：按 key 哈希分桶 + 临时文件原子替换。

路径：<root>/<collection>/<sha256(key)[:2]>/<sha256(key)>.json。
用哈希而不是原始 key 命名，避免中文、冒号与 Windows 保留名带来的路径问题。
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Iterator

from app.foundation.stores.document import (
    DocumentHealth,
    DocumentStoreCorrupt,
    DocumentStoreUnavailable,
    DocumentTooLarge,
    canonical_json,
    document_digest,
    validate_target,
)

logger = logging.getLogger(__name__)


class LocalDocumentStore:
    backend = "local"

    def __init__(self, root: Path | str, *, max_bytes: int = 8 * 1024 * 1024):
        self.root = Path(root)
        self.max_bytes = max(1024, int(max_bytes))
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def upsert(
        self, collection: str, key: str, doc: dict[str, Any], *, version: int
    ) -> bool:
        collection, key = validate_target(collection, key)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ValueError(f"version 必须是正整数: {version!r}")
        payload = canonical_json(doc)
        size = len(payload.encode("utf-8"))
        if size > self.max_bytes:
            raise DocumentTooLarge(f"文档 {collection}/{key} 超过 {self.max_bytes} 字节")
        path = self._path(collection, key)
        with self._lock_for(path):
            current = self._read_version(path)
            if current is not None and current >= version:
                return False
            envelope = {
                "collection": collection,
                "key": key,
                "version": version,
                "document": doc,
            }
            body = canonical_json(envelope)
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(body)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, path)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError as cleanup_exc:
                    logger.debug("本地文档临时文件清理失败: %s", cleanup_exc)
                raise
        return True

    def get(self, collection: str, key: str) -> dict[str, Any] | None:
        collection, key = validate_target(collection, key)
        path = self._path(collection, key)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DocumentStoreCorrupt(f"文档损坏 {collection}/{key}: {exc}") from exc
        if not isinstance(envelope, dict) or not isinstance(envelope.get("document"), dict):
            raise DocumentStoreCorrupt(f"文档结构非法 {collection}/{key}")
        if envelope.get("key") != key or envelope.get("collection") != collection:
            raise DocumentStoreCorrupt(f"文档 key 不匹配 {collection}/{key}")
        return envelope["document"]

    def delete(self, collection: str, key: str) -> bool:
        collection, key = validate_target(collection, key)
        try:
            self._path(collection, key).unlink()
            return True
        except FileNotFoundError:
            return False

    def iter_keys(self, collection: str) -> Iterator[str]:
        if collection not in ("exam_resources", "import_snapshots", "forum_contents"):
            raise ValueError(f"未知文档集合: {collection!r}")
        base = self.root / collection
        if not base.exists():
            return
        for path in base.rglob("*.json"):
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("跳过不可读文档 %s: %s", path, exc)
                continue
            key = envelope.get("key")
            if isinstance(key, str):
                yield key

    def health(self) -> DocumentHealth:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            probe = self.root / ".health-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return DocumentHealth(backend=self.backend, ok=True, detail=str(self.root))
        except OSError as exc:
            return DocumentHealth(
                backend=self.backend, ok=False, degraded=True, detail=str(exc)
            )

    def _read_version(self, path: Path) -> int | None:
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise DocumentStoreUnavailable(f"读取文档失败 {path}: {exc}") from exc
        try:
            envelope = json.loads(raw)
            version = envelope.get("version")
        except (json.JSONDecodeError, AttributeError) as exc:
            raise DocumentStoreCorrupt(f"文档损坏 {path}: {exc}") from exc
        return version if isinstance(version, int) else None

    def _path(self, collection: str, key: str) -> Path:
        digest = document_digest(collection, key)
        return self.root / collection / digest[:2] / f"{digest}.json"

    def _lock_for(self, path: Path) -> threading.Lock:
        name = str(path)
        with self._locks_guard:
            lock = self._locks.get(name)
            if lock is None:
                lock = threading.Lock()
                self._locks[name] = lock
            return lock
