"""内部向量检索入口（F6）。

不新增 HTTP API；只有后端内部函数可调用。开关关闭或后端不可用时显式抛错，
不静默返回空列表。
"""
from __future__ import annotations

from typing import Any

from app.foundation import config as cfg
from app.foundation.ports.ai import EmbeddingPort, build_embedding_port
from app.foundation.stores.vector import VectorStore, build_vector_store


def search_questions(
    query: str,
    *,
    top_k: int = 10,
    where: dict[str, Any] | None = None,
    store: VectorStore | None = None,
    embedding: EmbeddingPort | None = None,
    collection: str | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query 不能为空")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise ValueError(f"top_k 必须是正整数: {top_k!r}")
    port = embedding or build_embedding_port()
    target = store or build_vector_store()
    name = collection or cfg.VECTOR_COLLECTION
    vector = port.embed([query])[0]
    hits = target.search(name, vector, top_k=top_k, where=where)
    return [
        {"id": hit.id, "score": hit.score, "meta": dict(hit.meta)}
        for hit in hits
    ]
