"""Milvus 向量存储（可选后端）。

pymilvus 是可选依赖：未安装时抛 VectorStoreUnavailable，绝不回落到 local。
集合名统一加前缀，避免与用户其它 Milvus 集合冲突。
"""
from __future__ import annotations

import json
from typing import Any, Iterable

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

_BATCH = 500


def _literal(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    return json.dumps(value, ensure_ascii=False)


def _quote_id(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


class MilvusVectorStore:
    backend = "milvus"

    def __init__(
        self,
        *,
        uri: str,
        token: str = "",
        prefix: str = "li_an_",
        dim: int,
        max_top_k: int = 100,
        client: Any | None = None,
    ):
        if dim <= 0:
            raise ValueError("dim 必须是正整数")
        self.uri = uri
        self.token = token
        self.prefix = prefix or ""
        self.dim = int(dim)
        self.max_top_k = max(1, int(max_top_k))
        self._client = client
        self._ready: set[str] = set()

    def _name(self, collection: str) -> str:
        return f"{self.prefix}{validate_collection(collection)}"

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from pymilvus import MilvusClient
        except ImportError as exc:
            raise VectorStoreUnavailable(
                "未安装 pymilvus（可选依赖：pip install 'pymilvus>=2.4,<3'）"
            ) from exc
        try:
            self._client = MilvusClient(uri=self.uri, token=self.token or None)
        except Exception as exc:  # noqa: BLE001 — 连接失败统一映射
            raise VectorStoreUnavailable(f"连接 Milvus 失败: {exc}") from exc
        return self._client

    def _dimension(self, description: Any) -> int | None:
        if not isinstance(description, dict):
            return None
        for field in description.get("fields", []) or []:
            if not isinstance(field, dict):
                continue
            if field.get("field_name") != "vector" and field.get("name") != "vector":
                continue
            params = field.get("params") or {}
            raw = params.get("dim") if isinstance(params, dict) else None
            if raw is None:
                raw = field.get("dim")
            try:
                return int(raw) if raw is not None else None
            except (TypeError, ValueError):
                return None
        return None

    def _ensure_collection(self, collection: str) -> str:
        name = self._name(collection)
        if name in self._ready:
            return name
        client = self._get_client()
        try:
            exists = bool(client.has_collection(collection_name=name))
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreUnavailable(f"检查 Milvus 集合失败: {exc}") from exc
        if exists:
            try:
                description = client.describe_collection(collection_name=name)
            except Exception as exc:  # noqa: BLE001
                raise VectorStoreUnavailable(f"读取 Milvus 集合结构失败: {exc}") from exc
            actual = self._dimension(description)
            if actual is not None and actual != self.dim:
                raise VectorStoreCorrupt(
                    f"Milvus 集合 {name} 维度 {actual} != 配置 {self.dim}"
                )
            self._ready.add(name)
            return name

        try:
            from pymilvus import DataType

            schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
            schema.add_field(
                field_name="id", datatype=DataType.VARCHAR, is_primary=True, max_length=128
            )
            schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=self.dim)
            schema.add_field(field_name="meta", datatype=DataType.JSON)
            index_params = client.prepare_index_params()
            index_params.add_index(
                field_name="vector", index_type="AUTOINDEX", metric_type="COSINE"
            )
            client.create_collection(
                collection_name=name, schema=schema, index_params=index_params
            )
            if hasattr(client, "load_collection"):
                client.load_collection(collection_name=name)
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreUnavailable(f"创建 Milvus 集合失败: {exc}") from exc
        self._ready.add(name)
        return name

    def _where(self, where: dict[str, Any] | None) -> str:
        filters = normalize_where(where)
        clauses: list[str] = []
        for key, values in filters.items():
            field = f'meta[{_quote_id(key)}]'
            if len(values) == 1:
                clauses.append(f"{field} == {_literal(values[0])}")
            else:
                clauses.append(f"{field} in [{', '.join(_literal(v) for v in values)}]")
        return " and ".join(clauses)

    # ---------- 写 ----------

    def upsert(
        self, collection: str, item_id: str, vector: list[float], meta: dict[str, Any]
    ) -> bool:
        return self.upsert_many(collection, [VectorItem(item_id, vector, meta)]) > 0

    def upsert_many(self, collection: str, items: Iterable[VectorItem]) -> int:
        batch = list(items)
        if not batch:
            return 0
        name = self._ensure_collection(collection)
        prepared = [
            {
                "id": validate_id(item.id),
                "vector": normalize_vector(item.vector, self.dim),
                "meta": validate_meta(item.meta),
            }
            for item in batch
        ]
        client = self._get_client()
        written = 0
        for start in range(0, len(prepared), _BATCH):
            chunk = prepared[start:start + _BATCH]
            try:
                result = client.upsert(collection_name=name, data=chunk)
            except Exception as exc:  # noqa: BLE001
                raise VectorStoreUnavailable(f"Milvus upsert 失败: {exc}") from exc
            if isinstance(result, dict):
                written += int(result.get("upsert_count", len(chunk)))
            else:
                written += len(chunk)
        return written

    def delete(self, collection: str, item_id: str) -> bool:
        return self.delete_many(collection, [item_id]) > 0

    def delete_many(self, collection: str, ids: list[str]) -> int:
        targets = [validate_id(item_id) for item_id in ids]
        if not targets:
            return 0
        name = self._ensure_collection(collection)
        client = self._get_client()
        try:
            result = client.delete(collection_name=name, ids=targets)
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreUnavailable(f"Milvus delete 失败: {exc}") from exc
        if isinstance(result, dict):
            return int(result.get("delete_count", len(targets)))
        return len(targets)

    def clear(self, collection: str) -> None:
        name = self._name(collection)
        client = self._get_client()
        try:
            if client.has_collection(collection_name=name):
                client.drop_collection(collection_name=name)
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreUnavailable(f"清空 Milvus 集合失败: {exc}") from exc
        self._ready.discard(name)

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
        query = normalize_vector(vector, self.dim)
        name = self._ensure_collection(collection)
        client = self._get_client()
        kwargs = {
            "collection_name": name,
            "data": [query],
            "anns_field": "vector",
            "limit": top_k,
            "output_fields": ["meta"],
            "search_params": {"metric_type": "COSINE", "params": {}},
        }
        expression = self._where(where)
        if expression:
            kwargs["filter"] = expression
        try:
            result = client.search(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreUnavailable(f"Milvus search 失败: {exc}") from exc
        rows = result[0] if isinstance(result, list) and result else []
        hits: list[VectorHit] = []
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            entity = row.get("entity") if isinstance(row.get("entity"), dict) else {}
            item_id = row.get("id") or entity.get("id")
            meta = entity.get("meta") if isinstance(entity.get("meta"), dict) else row.get("meta")
            score = row.get("distance", row.get("score", 0.0))
            if not isinstance(item_id, str) or not isinstance(meta, dict):
                continue
            try:
                hits.append(VectorHit(id=item_id, score=float(score), meta=meta))
            except (TypeError, ValueError):
                continue
        hits.sort(key=lambda hit: (-hit.score, hit.id))
        return hits

    def fetch(self, collection: str, ids: list[str]) -> dict[str, dict[str, Any]]:
        targets = [validate_id(item_id) for item_id in ids]
        if not targets:
            return {}
        name = self._ensure_collection(collection)
        client = self._get_client()
        expression = "id in [" + ", ".join(_quote_id(item) for item in targets) + "]"
        try:
            rows = client.query(
                collection_name=name, filter=expression, output_fields=["id", "meta"]
            )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreUnavailable(f"Milvus query 失败: {exc}") from exc
        result: dict[str, dict[str, Any]] = {}
        for row in rows or []:
            if isinstance(row, dict) and isinstance(row.get("id"), str):
                meta = row.get("meta")
                if isinstance(meta, dict):
                    result[row["id"]] = meta
        return result

    def list_ids(self, collection: str, limit: int | None = None) -> list[str]:
        if limit is not None and (
            not isinstance(limit, int) or isinstance(limit, bool) or limit < 1
        ):
            raise InvalidVectorTarget(f"limit 必须是正整数或 None: {limit!r}")
        name = self._ensure_collection(collection)
        client = self._get_client()
        ids: list[str] = []
        try:
            if hasattr(client, "query_iterator"):
                iterator = client.query_iterator(
                    collection_name=name, batch_size=1000, filter="", output_fields=["id"]
                )
                while True:
                    batch = next(iterator)
                    if not batch:
                        break
                    ids.extend(
                        row["id"] for row in batch
                        if isinstance(row, dict) and isinstance(row.get("id"), str)
                    )
                    if limit is not None and len(ids) >= limit:
                        break
            else:
                rows = client.query(
                    collection_name=name, filter="", output_fields=["id"], limit=16384
                )
                ids.extend(
                    row["id"] for row in rows or []
                    if isinstance(row, dict) and isinstance(row.get("id"), str)
                )
        except StopIteration:
            # query_iterator 用 StopIteration 表示枚举结束，不是异常吞没。
            batch = None
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreUnavailable(f"Milvus 枚举 id 失败: {exc}") from exc
        ordered = sorted(set(ids))
        return ordered if limit is None else ordered[:limit]

    def count(self, collection: str) -> int:
        name = self._ensure_collection(collection)
        client = self._get_client()
        try:
            rows = client.query(
                collection_name=name, filter="", output_fields=["count(*)"]
            )
        except Exception as exc:  # noqa: BLE001
            raise VectorStoreUnavailable(f"Milvus count 失败: {exc}") from exc
        for row in rows or []:
            if isinstance(row, dict):
                for value in row.values():
                    if isinstance(value, int):
                        return value
        return 0

    def health(self) -> VectorHealth:
        try:
            client = self._get_client()
            client.list_collections()
            return VectorHealth(backend=self.backend, ok=True, detail=self.uri)
        except Exception as exc:  # noqa: BLE001
            return VectorHealth(
                backend=self.backend, ok=False, degraded=True, detail=str(exc)
            )
