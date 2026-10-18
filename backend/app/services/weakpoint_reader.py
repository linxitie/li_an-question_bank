"""薄弱知识点只读服务（P2-57，E13 供给方）。

职责边界：
- **只读**：只查询 `practice_record` 与题型/知识点维表，不写任何业务表；
- **不依赖 API 层**：不 import 任何 `app.api.*` 模块，供成绩分析端点（⑧）
  与试卷推荐位（⑤）共同复用；
- **结构稳定**：对外固定返回 ``knowledge_point`` / ``accuracy`` / ``total``
  / ``correct`` 四个字段，调用方无需感知底层表结构。
"""
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.models import KnowledgePoint, PracticeRecord, QuestionBank, QuestionType

# 判定阈值：题量达到该值才参与薄弱点排序，避免 1~2 题的偶然错误被放大。
DEFAULT_MIN_ATTEMPTS = 5
# 正确率不高于该值视为薄弱（百分比）。
DEFAULT_MAX_ACCURACY = 60.0
DEFAULT_LIMIT = 5


def _weakpoint_query(
    db: Session,
    user_id: int,
    min_attempts: int,
    max_accuracy: float,
):
    """构造用户维度的考点聚合查询（内部使用）。"""
    attempts = func.count(PracticeRecord.record_id)
    correct = func.coalesce(func.sum(PracticeRecord.is_correct), 0)
    accuracy = correct * 100.0 / attempts

    point_name = func.coalesce(KnowledgePoint.point_name, QuestionType.type_name)

    return (
        db.query(
            point_name.label("knowledge_point"),
            attempts.label("total"),
            correct.label("correct"),
            accuracy.label("accuracy"),
        )
        .select_from(PracticeRecord)
        .outerjoin(QuestionBank, PracticeRecord.question_id == QuestionBank.question_id)
        .outerjoin(KnowledgePoint, QuestionBank.point_id == KnowledgePoint.point_id)
        .outerjoin(QuestionType, PracticeRecord.type_id == QuestionType.type_id)
        .filter(
            PracticeRecord.user_id == user_id,
            PracticeRecord.is_correct.isnot(None),
        )
        .group_by(point_name)
        .having(attempts >= min_attempts)
        .having(accuracy <= max_accuracy)
        .order_by(accuracy.asc(), attempts.desc())
    )


def get_weakpoints(
    db: Session,
    user_id: Optional[int],
    *,
    min_attempts: int = DEFAULT_MIN_ATTEMPTS,
    max_accuracy: float = DEFAULT_MAX_ACCURACY,
    limit: int = DEFAULT_LIMIT,
) -> List[Dict[str, Any]]:
    """返回用户薄弱考点集合，按正确率升序、题量降序排列。

    返回项固定为::

        {
            "knowledge_point": str,
            "accuracy": float,   # 百分比，保留 1 位小数
            "total": int,
            "correct": int,
        }

    未登录 / 无足够练习记录时返回空列表，不抛异常。
    """
    if not user_id:
        return []

    rows = (
        _weakpoint_query(db, user_id, min_attempts, max_accuracy)
        .limit(limit)
        .all()
    )

    result: List[Dict[str, Any]] = []
    for row in rows:
        total = int(row.total or 0)
        if total <= 0:
            continue
        result.append(
            {
                "knowledge_point": row.knowledge_point or "未分类考点",
                "accuracy": round(float(row.accuracy or 0), 1),
                "total": total,
                "correct": int(row.correct or 0),
            }
        )
    return result


def get_weakpoint_type_ids(
    db: Session,
    user_id: Optional[int],
    *,
    min_attempts: int = DEFAULT_MIN_ATTEMPTS,
    max_accuracy: float = DEFAULT_MAX_ACCURACY,
) -> List[int]:
    """返回薄弱考点对应的题型 ID 集合，供试卷推荐位做筛选。

    与 :func:`get_weakpoints` 使用完全相同的阈值口径；没有薄弱点时返回 ``[]``，
    调用方须把空列表视为「不筛选」而不是「筛选出空结果」。
    """
    if not user_id:
        return []

    attempts = func.count(PracticeRecord.record_id)
    correct = func.coalesce(func.sum(PracticeRecord.is_correct), 0)
    accuracy = correct * 100.0 / attempts

    rows = (
        db.query(PracticeRecord.type_id)
        .select_from(PracticeRecord)
        .filter(
            PracticeRecord.user_id == user_id,
            PracticeRecord.type_id.isnot(None),
            PracticeRecord.is_correct.isnot(None),
        )
        .group_by(PracticeRecord.type_id)
        .having(attempts >= min_attempts)
        .having(accuracy <= max_accuracy)
        .all()
    )
    return [int(row[0]) for row in rows if row[0] is not None]
