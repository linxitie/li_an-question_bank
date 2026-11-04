"""从 SoT 生成 text_questions 向量计划。

只投影 status=1 且题干非空的题目；meta 保留定位字段和内容哈希。
回填脚本、对账、检索共用同一份题目筛选口径。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text

from app.foundation import config as cfg
from app.foundation.ports.ai import EmbeddingPort
from app.foundation.stores.vector import VectorItem, VectorStore

TEXT_QUESTION_QUERY = text(
    """SELECT question_id, subject_id, type_id, point_id, difficulty, status,
              question_content
       FROM question_bank
       WHERE status = 1
         AND question_content IS NOT NULL
         AND length(trim(question_content)) > 0
       ORDER BY question_id"""
)


def _limit_clause(limit: int | None) -> str:
    if limit is None:
        return ""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError(f"limit 必须是正整数或 None: {limit!r}")
    return f" LIMIT {int(limit)}"


@dataclass(frozen=True)
class QuestionRecord:
    id: str
    text: str
    meta: dict[str, Any]


@dataclass
class VectorBuildPlan:
    collection: str
    records: list[QuestionRecord] = field(default_factory=list)
    items: list[VectorItem] = field(default_factory=list)

    @property
    def planned(self) -> int:
        return len(self.records)


def content_hash(text_value: str) -> str:
    return hashlib.sha256(text_value.encode("utf-8")).hexdigest()[:16]


def expected_records(session, *, limit: int | None = None) -> list[QuestionRecord]:
    """只查 SoT，不调用 embedding；对账用它比对 id 与内容哈希。"""
    rows = session.execute(
        text(str(TEXT_QUESTION_QUERY) + _limit_clause(limit))
    ).mappings().all()
    records: list[QuestionRecord] = []
    for row in rows:
        body = str(row["question_content"])
        records.append(QuestionRecord(
            id=str(int(row["question_id"])),
            text=body,
            meta={
                "subjectId": row["subject_id"],
                "typeId": row["type_id"],
                "pointId": row["point_id"],
                "difficulty": row["difficulty"],
                "status": row["status"],
                "contentHash": content_hash(body),
            },
        ))
    return records


def build_vector_plan(
    session,
    embedding: EmbeddingPort,
    *,
    collection: str | None = None,
    limit: int | None = None,
) -> VectorBuildPlan:
    name = collection or cfg.VECTOR_COLLECTION
    records = expected_records(session, limit=limit)
    plan = VectorBuildPlan(collection=name, records=records)
    if not records:
        return plan
    vectors = embedding.embed([record.text for record in records])
    if len(vectors) != len(records):
        raise ValueError(f"embedding 返回 {len(vectors)} 条，期望 {len(records)} 条")
    for record, vector in zip(records, vectors):
        if len(vector) != int(embedding.dim):
            raise ValueError(
                f"embedding 维度 {len(vector)} != 端口维度 {embedding.dim}"
            )
        plan.items.append(VectorItem(id=record.id, vector=list(vector), meta=dict(record.meta)))
    return plan


def apply_plan(
    store: VectorStore,
    plan: VectorBuildPlan,
    *,
    reset: bool = False,
    batch_size: int = 200,
) -> dict[str, int]:
    if reset:
        store.clear(plan.collection)
    written = 0
    for start in range(0, len(plan.items), max(1, int(batch_size))):
        written += store.upsert_many(plan.collection, plan.items[start:start + max(1, int(batch_size))])
    return {
        "planned": plan.planned,
        "written": written,
        "skipped": max(0, plan.planned - written),
    }
