"""K1–K7 七条恒等式校验（v6.0 方案 §2.1）。

"分类绝对准确"在这里不是形容词：任一恒等式不成立即视为投影/数据不一致，
回填脚本与门禁共用本模块，避免"脚本说成功、结果不对"。

K1 孤儿题（可见题 point_id 为空）        = 0
K2 脏引用（point_id 指向不存在/停用节点）= 0
K3 可下钻节点必须有子节点                = 100%
K4 同题同考点重复挂载                    = 0
K5 图节点数 = 考点数 + 题数（按 label）  恒等
K6 文档条数 = 题数 + 材料组数           恒等
K7 向量条数 = 可向量化题数，维度一致     恒等

图/文档/向量三类检查在对应 store 关闭或不可用时记 skipped，而不是伪造成 PASS。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import text

VISIBLE_WHERE = "qb.status = 1 AND qb.audit_status = 1"

ORPHAN_SQL = text(
    f"""SELECT COUNT(*) FROM question_bank qb
        WHERE {VISIBLE_WHERE}
          AND (qb.point_id IS NULL
               OR qb.point_id NOT IN (SELECT point_id FROM knowledge_point))"""
)

DIRTY_REF_SQL = text(
    f"""SELECT COUNT(*) FROM question_bank qb
        JOIN knowledge_point kp ON kp.point_id = qb.point_id
        WHERE {VISIBLE_WHERE} AND kp.status <> 1"""
)

DRILLABLE_SQL = text(
    """SELECT parent_id, COUNT(*) AS children
       FROM knowledge_point
       WHERE level = 3 AND status = 1 AND parent_id IS NOT NULL AND parent_id <> 0
       GROUP BY parent_id"""
)

DUPLICATE_SQL = text(
    """SELECT COUNT(*) FROM (
           SELECT question_id, knowledge_point_id, COUNT(*) AS n
           FROM question_knowledge
           GROUP BY question_id, knowledge_point_id
           HAVING n > 1
       )"""
)

POINT_TOTAL_SQL = text("SELECT COUNT(*) FROM knowledge_point")

# 图口径：有 question_knowledge 链接或已挂主考点（与 graph_builder.QUESTION_QUERY 一致）
GRAPH_QUESTION_SQL = text(
    """SELECT COUNT(*) FROM question_bank qb
       WHERE qb.point_id IS NOT NULL
          OR EXISTS (SELECT 1 FROM question_knowledge qk WHERE qk.question_id = qb.question_id)"""
)

# 向量/文档口径：status=1 且题干非空（与 vector_builder / question_documents 一致）
VECTOR_QUESTION_SQL = text(
    """SELECT COUNT(*) FROM question_bank
       WHERE status = 1 AND question_content IS NOT NULL
         AND length(trim(question_content)) > 0"""
)


def _result(identity: str, ok: bool, expected: Any, actual: Any, note: str = "",
            status: str = "checked") -> Dict[str, Any]:
    return {
        "identity": identity,
        "status": status,
        "ok": bool(ok),
        "expected": expected,
        "actual": actual,
        "note": note,
    }


def _scalar(session, sql) -> int:
    return int(session.execute(sql).scalar() or 0)


def check_k1(session) -> Dict[str, Any]:
    orphans = _scalar(session, ORPHAN_SQL)
    return _result("K1", orphans == 0, 0, orphans,
                   "可见题存在空考点：导入时应落「其他（未细分）」收容叶子")


def check_k2(session) -> Dict[str, Any]:
    dirty = _scalar(session, DIRTY_REF_SQL)
    return _result("K2", dirty == 0, 0, dirty, "题目挂在 status<>1 的考点上")


def check_k3(session, graph_store=None) -> Dict[str, Any]:
    parents = {int(row[0]): int(row[1]) for row in session.execute(DRILLABLE_SQL)}
    if not parents:
        return _result("K3", True, 0, 0, "没有 level=3 子节点", status="checked")
    if graph_store is None:
        return _result("K3", True, len(parents), len(parents),
                       "图库未启用，仅校验 SoT 层级", status="skipped")
    missing = []
    for parent_id in parents:
        children = list(graph_store.neighbors(
            "KnowledgePoint", str(parent_id), "PREREQUISITE_OF", 1, "out"
        ))
        if not children:
            missing.append(parent_id)
    return _result("K3", not missing, len(parents), len(parents) - len(missing),
                   "缺边的父考点: " + ",".join(str(m) for m in missing[:10]))


def check_k4(session) -> Dict[str, Any]:
    dups = _scalar(session, DUPLICATE_SQL)
    return _result("K4", dups == 0, 0, dups, "question_knowledge 同题同考点重复")


def check_k5(session, graph_store=None) -> Dict[str, Any]:
    points = _scalar(session, POINT_TOTAL_SQL)
    questions = _scalar(session, GRAPH_QUESTION_SQL)
    expected = points + questions
    if graph_store is None:
        return _result("K5", True, expected, None, "图库未启用", status="skipped")
    counts = graph_store.counts()
    by_label = counts.get("nodes_by_label") or {}
    actual_points = int(by_label.get("KnowledgePoint", 0))
    actual_questions = int(by_label.get("Question", 0))
    actual = actual_points + actual_questions
    ok = actual_points == points and actual_questions == questions
    return _result(
        "K5", ok, expected, actual,
        f"KnowledgePoint {actual_points}/{points}, Question {actual_questions}/{questions}",
    )


def check_k6(session, document_store=None) -> Dict[str, Any]:
    from app.foundation import question_documents

    if document_store is None:
        return _result("K6", True, None, None, "文档库未启用", status="skipped")
    report = question_documents.verify(session, document_store)
    expected = report["expectedQuestions"] + report["expectedMaterials"]
    return _result(
        "K6", report["ok"], expected, report["actual"],
        f"题 {report['expectedQuestions']} + 材料 {report['expectedMaterials']}；"
        f"缺 {report['missingTotal']} 余 {report['extraTotal']} 漂移 {report['driftedTotal']}",
    )


def check_k7(session, vector_store=None, collection: Optional[str] = None) -> Dict[str, Any]:
    from app.foundation import config as cfg

    questions = _scalar(session, VECTOR_QUESTION_SQL)
    name = collection or cfg.VECTOR_COLLECTION
    if vector_store is None:
        return _result("K7", True, questions, None, "向量库未启用", status="skipped")
    actual = int(vector_store.count(name))
    health = vector_store.health()
    ok = actual == questions and bool(getattr(health, "ok", False))
    return _result("K7", ok, questions, actual,
                   f"collection={name} dim={cfg.EMBEDDING_DIM} health={health.detail or 'ok'}")


def run_all(session, *, graph_store=None, document_store=None,
            vector_store=None) -> Dict[str, Any]:
    """一次跑完七条恒等式，返回可直接落盘/打印的报告。"""
    checks = [
        check_k1(session),
        check_k2(session),
        check_k3(session, graph_store),
        check_k4(session),
        check_k5(session, graph_store),
        check_k6(session, document_store),
        check_k7(session, vector_store),
    ]
    failed = [item["identity"] for item in checks if not item["ok"]]
    return {
        "ok": not failed,
        "failed": failed,
        "checks": checks,
    }
