"""题目/材料文档投影（F4 的第三类文档集合）。

为什么单独一个模块而不是塞进 document_schema.py：
  document_schema 只覆盖试卷快照 / 导入快照 / 论坛 / 新闻四类业务文档，
  它们的键是"业务主键"，而题库 3750 道题的投影需要**批量**生成与整库校验
  （K6 恒等式：文档条数 = 可投影题数 + 材料组数）。放在这里可以让回填脚本、
  对账与测试共用同一份口径，不必反向往业务 API 里加查询。

口径与 vector_builder 严格一致（status=1 且题干非空），否则 K6/K7 的数量
恒等式会因为"哪边算可见"而互相矛盾。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import text

from app.foundation.vector_builder import content_hash

COLLECTION = "question_documents"
SCHEMA = "question_document/v1"

QUESTION_DOC_PREFIX = "q:"
MATERIAL_DOC_PREFIX = "g:"

FALLBACK_NAME_PREFIXES = ("其他", "未分类", "未归类")

# 与 vector_builder.TEXT_QUESTION_QUERY 的 WHERE 保持一致
QUESTION_SQL = text(
    """SELECT question_id, subject_id, type_id, point_id, sub_category_id, group_id,
              difficulty, year, source, question_content, options, answer,
              answer_analysis, status
       FROM question_bank
       WHERE status = 1
         AND question_content IS NOT NULL
         AND length(trim(question_content)) > 0
       ORDER BY question_id"""
)

GROUP_SQL = text(
    """SELECT id, group_type, title, subject, difficulty, shared_content
       FROM question_groups
       WHERE shared_content IS NOT NULL
         AND length(trim(shared_content)) > 0
       ORDER BY id"""
)

POINT_SQL = text(
    "SELECT point_id, point_name, parent_id, level, subject_id, sub_category_id "
    "FROM knowledge_point ORDER BY point_id"
)

SUBCATEGORY_SQL = text("SELECT id, name, subject_id FROM sub_categories ORDER BY id")


def _limit_clause(limit: Optional[int]) -> str:
    if limit is None:
        return ""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError(f"limit 必须是正整数或 None: {limit!r}")
    return f" LIMIT {int(limit)}"


def is_fallback_name(name: Optional[str]) -> bool:
    return str(name or "").strip().startswith(FALLBACK_NAME_PREFIXES)


def question_key(question_id: Any) -> str:
    return f"{QUESTION_DOC_PREFIX}{int(question_id)}"


def material_key(group_id: Any) -> str:
    return f"{MATERIAL_DOC_PREFIX}{int(group_id)}"


@dataclass
class ProjectionContext:
    """一次投影/校验共用的字典缓存，避免 3750 次逐条查父链。"""

    points: Dict[int, Dict[str, Any]] = field(default_factory=dict)
    subcategories: Dict[int, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def load(cls, session) -> "ProjectionContext":
        ctx = cls()
        for row in session.execute(POINT_SQL).mappings().all():
            ctx.points[int(row["point_id"])] = dict(row)
        for row in session.execute(SUBCATEGORY_SQL).mappings().all():
            ctx.subcategories[int(row["id"])] = dict(row)
        return ctx

    def point_path(self, point_id: Optional[int]) -> List[Dict[str, Any]]:
        """从根到叶的考点链；最多回溯 8 层，遇到断链即停（不抛异常）。"""
        if not point_id:
            return []
        chain: List[Dict[str, Any]] = []
        current = int(point_id)
        seen = set()
        while current and current not in seen and len(chain) < 8:
            seen.add(current)
            row = self.points.get(current)
            if row is None:
                break
            chain.append({
                "pointId": current,
                "name": row.get("point_name"),
                "level": row.get("level"),
            })
            parent = row.get("parent_id")
            current = int(parent) if parent else 0
        chain.reverse()
        return chain

    def point_name(self, point_id: Optional[int]) -> Optional[str]:
        if not point_id:
            return None
        row = self.points.get(int(point_id))
        return str(row["point_name"]) if row else None

    def subcategory_name(self, sub_category_id: Optional[int]) -> Optional[str]:
        if not sub_category_id:
            return None
        row = self.subcategories.get(int(sub_category_id))
        return str(row["name"]) if row else None


def _parse_options(raw: Any) -> Any:
    """options 列有 JSON 字符串、也有纯文本；解析失败就原样保留，不丢数据。"""
    if raw is None or raw == "":
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except (ValueError, TypeError):
        return str(raw)


def _images(*texts: Optional[str], question_id: Optional[int] = None, db=None) -> List[Dict[str, Any]]:
    if not any(t and "[IMAGE:" in str(t) for t in texts):
        return []
    from app.services import image_markers

    return image_markers.describe_images(*texts, question_id=question_id, db=db)


def build_question_document(row: Dict[str, Any], ctx: ProjectionContext,
                            db=None) -> Dict[str, Any]:
    point_id = row.get("point_id")
    point_name = ctx.point_name(point_id)
    stem = str(row.get("question_content") or "")
    analysis = str(row.get("answer_analysis") or "")
    options = _parse_options(row.get("options"))
    options_text = json.dumps(options, ensure_ascii=False) if isinstance(options, (dict, list)) else (options or "")
    return {
        "schema": SCHEMA,
        "kind": "question",
        "questionId": int(row["question_id"]),
        "subjectId": row.get("subject_id"),
        "subCategoryId": row.get("sub_category_id"),
        "subCategoryName": ctx.subcategory_name(row.get("sub_category_id")),
        "typeId": row.get("type_id"),
        "difficulty": row.get("difficulty"),
        "year": row.get("year"),
        "source": row.get("source"),
        "pointId": point_id,
        "pointName": point_name,
        "pointPath": ctx.point_path(point_id),
        "isFallback": is_fallback_name(point_name),
        "groupId": row.get("group_id"),
        "materialDocument": material_key(row["group_id"]) if row.get("group_id") else None,
        "stem": stem,
        "options": options,
        "answer": row.get("answer"),
        "analysis": analysis,
        "images": _images(stem, analysis, options_text, question_id=int(row["question_id"]), db=db),
        "contentHash": content_hash(stem),
    }


def build_material_document(row: Dict[str, Any], db=None) -> Dict[str, Any]:
    content = str(row.get("shared_content") or "")
    return {
        "schema": SCHEMA,
        "kind": "material",
        "groupId": int(row["id"]),
        "title": row.get("title"),
        "groupType": row.get("group_type"),
        "subject": row.get("subject"),
        "difficulty": row.get("difficulty"),
        "content": content,
        "images": _images(content, db=db),
        "contentHash": content_hash(content),
    }


def expected_keys(session, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """只读 SoT，算出应当存在的文档键与内容哈希（K6 的期望侧）。"""
    out: List[Dict[str, Any]] = []
    for row in session.execute(text(str(QUESTION_SQL) + _limit_clause(limit))).mappings().all():
        out.append({
            "collection": COLLECTION,
            "key": question_key(row["question_id"]),
            "kind": "question",
            "contentHash": content_hash(str(row["question_content"] or "")),
        })
    for row in session.execute(GROUP_SQL).mappings().all():
        out.append({
            "collection": COLLECTION,
            "key": material_key(row["id"]),
            "kind": "material",
            "contentHash": content_hash(str(row["shared_content"] or "")),
        })
    return out


def project(session, store, *, limit: Optional[int] = None, reset: bool = False,
            version: Optional[int] = None, db=None) -> Dict[str, int]:
    """全量投影题目与材料文档；reset=True 先删同集合已有键。"""
    ctx = ProjectionContext.load(session)
    written = 0
    skipped = 0
    deleted = 0
    if reset:
        for key in list(store.iter_keys(COLLECTION)):
            if store.delete(COLLECTION, key):
                deleted += 1

    base_version = int(version) if version is not None else 1
    for row in session.execute(QUESTION_SQL).mappings().all():
        doc = build_question_document(dict(row), ctx, db=db)
        if store.upsert(COLLECTION, question_key(doc["questionId"]), doc, version=base_version):
            written += 1
        else:
            skipped += 1
    for row in session.execute(GROUP_SQL).mappings().all():
        doc = build_material_document(dict(row), db=db)
        if store.upsert(COLLECTION, material_key(doc["groupId"]), doc, version=base_version):
            written += 1
        else:
            skipped += 1
    return {"written": written, "skipped": skipped, "deleted": deleted}


def verify(session, store, *, limit: Optional[int] = None) -> Dict[str, Any]:
    """K6：文档条数 = 可投影题数 + 材料组数，且内容哈希一致。"""
    expected = expected_keys(session, limit=limit)
    expected_keyset = {item["key"] for item in expected}
    actual: List[str] = list(store.iter_keys(COLLECTION))
    actual_set = set(actual)

    missing = sorted(expected_keyset - actual_set)
    extra = sorted(actual_set - expected_keyset)
    drifted: List[str] = []
    for key in sorted(expected_keyset & actual_set):
        envelope = store.get(COLLECTION, key) or {}
        doc = envelope.get("document", envelope)
        want = next(item["contentHash"] for item in expected if item["key"] == key)
        if doc.get("contentHash") != want:
            drifted.append(key)

    questions = sum(1 for item in expected if item["kind"] == "question")
    materials = sum(1 for item in expected if item["kind"] == "material")
    ok = not missing and not extra and not drifted
    return {
        "identity": "K6",
        "ok": ok,
        "expected": len(expected),
        "expectedQuestions": questions,
        "expectedMaterials": materials,
        "actual": len(actual_set),
        "missing": missing[:20],
        "extra": extra[:20],
        "drifted": drifted[:20],
        "missingTotal": len(missing),
        "extraTotal": len(extra),
        "driftedTotal": len(drifted),
    }
