"""local 向量存储：<root>/<collection>.npy + ids/meta JSON。

向量是 float32 且写入前已 L2 归一化，点积即余弦。写文件用临时文件 +
fsync + os.replace，npy 最后替换；进程内 RLock 保证单进程单写者。
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from app.foundation.stores.vector import (
    InvalidVectorTarget,
    VectorHealth,
    VectorHit,
    VectorItem,
    VectorStoreCorrupt,
    VectorStoreUnavailable,
    normalize_vector,
    normalize_where,
    validate_collection,
    validate_id,
    validate_meta,
)

logger = logging.getLogger(__name__)


class LocalVectorStore:
    backend = "local"

    def __init__(self, root: Path | str, *, dim: int, max_top_k: int = 100):
        if dim <= 0:
            raise ValueError("dim 必须是正整数")
        self.root = Path(root)
        self.dim = int(dim)
        self.max_top_k = max(1, int(max_top_k))
        self._lock = threading.RLock()
        self.root.mkdir(parents=True, exist_ok=True)

    # ---------- 路径与序列化 ----------

    def _paths(self, collection: str) -> tuple[Path, Path, Path]:
        collection = validate_collection(collection)
        return (
            self.root / f"{collection}.npy",
            self.root / f"{collection}.ids.json",
            self.root / f"{collection}.meta.json",
        )

    def _load(self, collection: str) -> tuple[list[str], np.ndarray, dict[str, dict[str, Any]]]:
        npy_path, ids_path, meta_path = self._paths(collection)
        exists = [npy_path.exists(), ids_path.exists(), meta_path.exists()]
        if not any(exists):
            return [], np.zeros((0, self.dim), dtype=np.float32), {}
        if not all(exists):
            raise VectorStoreCorrupt(f"向量文件不完整: {collection} {exists}")
        try:
            ids_raw = json.loads(ids_path.read_text(encoding="utf-8"))
            meta_raw = json.loads(meta_path.read_text(encoding="utf-8"))
            matrix = np.load(npy_path, allow_pickle=False)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise VectorStoreCorrupt(f"读取向量集合失败 {collection}: {exc}") from exc
        if not isinstance(ids_raw, list) or not all(isinstance(x, str) for x in ids_raw):
            raise VectorStoreCorrupt(f"ids.json 不是字符串数组: {collection}")
        if not isinstance(meta_raw, dict):
            raise VectorStoreCorrupt(f"meta.json 不是对象: {collection}")
        if matrix.ndim != 2 or matrix.shape != (len(ids_raw), self.dim):
            raise VectorStoreCorrupt(
                f"向量矩阵形状 {matrix.shape} 与 ids={len(ids_raw)}/dim={self.dim} 不符"
            )
        if len(set(ids_raw)) != len(ids_raw):
            raise VectorStoreCorrupt(f"ids 重复: {collection}")
        if set(meta_raw) != set(ids_raw):
            raise VectorStoreCorrupt(f"ids 与 meta key 不一致: {collection}")
        return ids_raw, matrix.astype(np.float32, copy=False), meta_raw

    def _atomic_write_json(self, path: Path, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
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
                logger.debug("本地向量临时文件清理失败: %s", cleanup_exc)
            raise

    def _atomic_write_npy(self, path: Path, matrix: np.ndarray) -> None:
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as fh:
                np.save(fh, matrix, allow_pickle=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError as cleanup_exc:
                logger.debug("本地向量临时文件清理失败: %s", cleanup_exc)
            raise

    def _save(
        self, collection: str, ids: list[str], matrix: np.ndarray, meta: dict[str, dict[str, Any]]
    ) -> None:
        npy_path, ids_path, meta_path = self._paths(collection)
        npy_path.parent.mkdir(parents=True, exist_ok=True)
        # npy 最后替换：读者最坏看到旧矩阵 + 新 ids/meta，_load 会报 Corrupt 而不是静默错配。
        self._atomic_write_json(ids_path, ids)
        self._atomic_write_json(meta_path, meta)
        self._atomic_write_npy(npy_path, matrix)

    # ---------- 写 ----------

    def upsert(
        self, collection: str, item_id: str, vector: list[float], meta: dict[str, Any]
    ) -> bool:
        return self.upsert_many(collection, [VectorItem(item_id, vector, meta)]) > 0

    def upsert_many(self, collection: str, items: Iterable[VectorItem]) -> int:
        batch = list(items)
        if not batch:
            return 0
        prepared: list[VectorItem] = []
        for item in batch:
            item_id = validate_id(item.id)
            vector = normalize_vector(item.vector, self.dim)
            meta = validate_meta(item.meta)
            prepared.append(VectorItem(item_id, vector, meta))
        with self._lock:
            ids, matrix, meta = self._load(collection)
            index = {key: pos for pos, key in enumerate(ids)}
            rows = matrix.tolist()
            for item in prepared:
                if item.id in index:
                    rows[index[item.id]] = item.vector
                else:
                    index[item.id] = len(ids)
                    ids.append(item.id)
                    rows.append(item.vector)
                meta[item.id] = item.meta
            self._save(
                collection, ids,
                np.asarray(rows, dtype=np.float32).reshape((len(ids), self.dim)),
                meta,
            )
        return len(prepared)

    def delete(self, collection: str, item_id: str) -> bool:
        return self.delete_many(collection, [item_id]) > 0

    def delete_many(self, collection: str, ids: list[str]) -> int:
        targets = {validate_id(item_id) for item_id in ids}
        if not targets:
            return 0
        with self._lock:
            current_ids, matrix, meta = self._load(collection)
            keep = [i for i, item_id in enumerate(current_ids) if item_id not in targets]
            removed = len(current_ids) - len(keep)
            if not removed:
                return 0
            new_ids = [current_ids[i] for i in keep]
            new_matrix = matrix[keep] if len(keep) else np.zeros((0, self.dim), dtype=np.float32)
            for item_id in targets:
                meta.pop(item_id, None)
            self._save(collection, new_ids, new_matrix, meta)
        return removed

    def clear(self, collection: str) -> None:
        with self._lock:
            for path in self._paths(collection):
                try:
                    path.unlink()
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    raise VectorStoreUnavailable(f"清空向量集合失败 {path}: {exc}") from exc

    # ---------- 读 ----------

    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= self.max_top_k:
            raise InvalidVectorTarget(f"top_k 必须是 1..{self.max_top_k}: {top_k!r}")
        query = np.asarray(normalize_vector(vector, self.dim), dtype=np.float32)
        filters = normalize_where(where)
        with self._lock:
            ids, matrix, meta = self._load(collection)
        if not ids:
            return []
        scores = matrix @ query
        candidates: list[tuple[str, float]] = []
        for pos, item_id in enumerate(ids):
            props = meta[item_id]
            if all(props.get(key) in values for key, values in filters.items()):
                candidates.append((item_id, float(scores[pos])))
        candidates.sort(key=lambda pair: (-pair[1], pair[0]))
        return [
            VectorHit(id=item_id, score=score, meta=dict(meta[item_id]))
            for item_id, score in candidates[:top_k]
        ]

    def fetch(self, collection: str, ids: list[str]) -> dict[str, dict[str, Any]]:
        targets = [validate_id(item_id) for item_id in ids]
        with self._lock:
            _, _, meta = self._load(collection)
        return {item_id: dict(meta[item_id]) for item_id in targets if item_id in meta}

    def list_ids(self, collection: str, limit: int | None = None) -> list[str]:
        if limit is not None and (
            not isinstance(limit, int) or isinstance(limit, bool) or limit < 1
        ):
            raise InvalidVectorTarget(f"limit 必须是正整数或 None: {limit!r}")
        with self._lock:
            ids, _, _ = self._load(collection)
        ordered = sorted(ids)
        return ordered if limit is None else ordered[:limit]

    def count(self, collection: str) -> int:
        with self._lock:
            ids, _, _ = self._load(collection)
        return len(ids)

    def health(self) -> VectorHealth:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".health-", dir=str(self.root))
            os.close(fd)
            os.unlink(tmp)
            return VectorHealth(backend=self.backend, ok=True, detail=str(self.root))
        except OSError as exc:
            return VectorHealth(
                backend=self.backend, ok=False, degraded=True, detail=str(exc)
            )
