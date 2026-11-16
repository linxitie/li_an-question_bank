# -*- coding: utf-8 -*-
"""考试评分口径（唯一写点）。

**口径 A（2026-11-09 用户拍板）**

    is_scored = 1  <=>  已交卷（is_completed=1）且**没有待人工评分的明细**
                        （即不存在 `exam_answer_detail.is_correct IS NULL`）

为什么改：统一前三个写点三种口径 —— 老交卷端点是恒真式（恒 1）、
`smart_exam` 建记录即写 1、`exam_service.submit_exam` 无条件 1（且该方法无调用方）。
`is_scored` 因此不表达任何信息。详见
`docs/plans/考试评分口径_is_scored统一_方案_v1.md`。

三个派生字段（只增不改）：

    manual_pending_count  待人工评分题数（is_correct 为 NULL）
    answered_count        已作答题数（student_answer 非空）
    question_total        本卷题数（分数/正确率的分母）

用法（交卷时，`is_completed` 由调用方置 1）：

    from ....services.exam_scoring import finalize_record
    finalize_record(exam_record, details, paper.question_count)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional


@dataclass(frozen=True)
class ScoringFlags:
    """一次作答的评分口径结果（纯数据，便于单测）。"""

    is_scored: bool
    manual_pending_count: int
    answered_count: int
    question_total: int


def _is_pending(detail: Any) -> bool:
    """该明细是否待人工评分：is_correct 为 None（主观题未人工评）。

    注意区分 `is_correct=0`（答错，已评分）与 `None`（还没评）。
    """
    return getattr(detail, "is_correct", None) is None


def _is_answered(detail: Any) -> bool:
    return bool((getattr(detail, "student_answer", "") or "").strip())


def scoring_flags(
    details: Iterable[Any],
    question_total: Optional[int] = None,
    is_completed: bool = True,
) -> ScoringFlags:
    """按口径 A 计算 is_scored 与三个派生字段（纯函数，无副作用）。"""
    details = list(details or [])
    manual_pending = sum(1 for d in details if _is_pending(d))
    answered = sum(1 for d in details if _is_answered(d))
    # 分母优先用卷面题量；卷面题量缺失（0/None）时退化为明细条数
    total = int(question_total or 0) or len(details)
    return ScoringFlags(
        is_scored=bool(is_completed) and manual_pending == 0,
        manual_pending_count=manual_pending,
        answered_count=answered,
        question_total=total,
    )


def finalize_record(
    record: Any,
    details: Iterable[Any],
    question_total: Optional[int] = None,
    is_completed: bool = True,
) -> ScoringFlags:
    """把口径 A 写到 `exam_record` 上（唯一写点，三处交卷都调用它）。

    只写 4 个字段：`is_scored` / `manual_pending_count` / `answered_count` /
    `question_total`；其余字段（总分、用时、提交时间等）仍由调用方负责。
    """
    flags = scoring_flags(details, question_total, is_completed)
    record.is_scored = 1 if flags.is_scored else 0
    record.manual_pending_count = flags.manual_pending_count
    record.answered_count = flags.answered_count
    record.question_total = flags.question_total
    return flags


# 存量库补列后的回填（D5-b，2026-11-16）。
#
# 为什么需要：`exam_record` 的这 4 列是 2026-11-09 口径 A 落地时新增的，
# 老库补列后 4 列全是默认值 0 —— 于是"已交卷"的老记录会被读成"未评分"
# （`agent_router` 里 `ExamRecord.is_scored == 1` 的统计会漏掉它们）。
#
# 为什么只扫描 `question_total = 0` 的行：那正是"从未按口径 A 算过"的特征。
# 新记录在交卷写点已写好 4 个列（值必然 ≥0；有明细时 >0），因此不会被重复改写，
# 天然幂等；没有明细的空记录每次启动会算一次同样的值，写入等价、无副作用。
#
# 分母取明细条数（与 `scoring_flags(question_total=0)` 的退化规则一致）：
# 老记录没有地方能取到"卷面题量"，用卷面题量反而会与当时页面显示的分母不一致。
_BACKFILL_STALE_SQL = """
UPDATE exam_record SET
       manual_pending_count = (
           SELECT COUNT(*) FROM exam_answer_detail d
            WHERE d.record_id = exam_record.record_id AND d.is_correct IS NULL),
       answered_count = (
           SELECT COUNT(*) FROM exam_answer_detail d
            WHERE d.record_id = exam_record.record_id
              AND TRIM(COALESCE(d.student_answer, '')) <> ''),
       question_total = (
           SELECT COUNT(*) FROM exam_answer_detail d
            WHERE d.record_id = exam_record.record_id),
       is_scored = CASE
           WHEN COALESCE(is_completed, 0) = 1 AND (
               SELECT COUNT(*) FROM exam_answer_detail d
                WHERE d.record_id = exam_record.record_id
                  AND d.is_correct IS NULL) = 0
           THEN 1 ELSE 0 END
 WHERE COALESCE(question_total, 0) = 0
"""


def backfill_stale_records(engine) -> int:
    """把"从未算过"的历史记录按口径 A 回填一次，返回受影响行数。

    `engine` 为 SQLAlchemy 的 Engine 或 Connection。
    缺 `exam_answer_detail` 表（极老库）时返回 0 并打印告警，不抛异常 ——
    启动自愈不能因为回填失败把整个应用拦住。
    """
    from sqlalchemy import text

    try:
        with engine.begin() as conn:
            result = conn.execute(text(_BACKFILL_STALE_SQL))
            return int(result.rowcount or 0)
    except Exception as exc:  # noqa: BLE001 - 回填失败不阻塞启动
        print(f"[WARN] exam_record 评分字段回填跳过: {exc}")
        return 0


__all__ = ["ScoringFlags", "scoring_flags", "finalize_record", "backfill_stale_records"]

