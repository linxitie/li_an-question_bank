"""目标完成判定（2026-11-05）。

问题背景：`/api/goals/{id}/complete` 原实现直接把 `current_count` 补到 `target_count`
就发币，`/progress` 也接受客户端自报增量 → 用户可以凭空刷金币。

本模块把"目标是否完成"的判定从客户端移到服务端，数据源是 exam 域的答题事实：
- DAILY   ：今天 00:00 起
- WEEKLY  ：本周一 00:00 起
- MONTHLY ：本月 1 日 00:00 起
- CUSTOM  ：从目标创建时间起（并扣除创建时的基线计数，只算新增）

计数口径：practice_record（练习/快速练习/智能刷题）+ exam_answer_detail（套卷答题）。
`goal.subject_mode > 0` 时只统计该学科。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.models import ExamAnswerDetail, ExamRecord, PracticeRecord, StudyGoal

logger = logging.getLogger(__name__)


def goal_window(goal: StudyGoal) -> tuple[datetime, datetime]:
    """目标统计窗口（左闭右开）。"""
    now = datetime.now()
    gtype = (goal.goal_type or "DAILY").upper()

    if gtype == "DAILY":
        start = datetime.combine(date.today(), datetime.min.time())
    elif gtype == "WEEKLY":
        monday = date.today() - timedelta(days=date.today().weekday())
        start = datetime.combine(monday, datetime.min.time())
    elif gtype == "MONTHLY":
        start = datetime.combine(date.today().replace(day=1), datetime.min.time())
    else:  # CUSTOM
        start = goal.create_time or (now - timedelta(days=30))

    return start, now


def count_real_progress(db: Session, goal: StudyGoal) -> dict:
    """按答题事实统计目标实际进度。"""
    start, end = goal_window(goal)
    subject_mode = goal.subject_mode or 0

    practice_q = db.query(func.count(PracticeRecord.record_id)).filter(
        PracticeRecord.user_id == goal.user_id,
        PracticeRecord.practice_time >= start,
        PracticeRecord.practice_time < end,
    )
    if subject_mode > 0:
        practice_q = practice_q.filter(PracticeRecord.subject_id == subject_mode)
    practice_count = practice_q.scalar() or 0

    exam_q = (
        db.query(func.count(ExamAnswerDetail.detail_id))
        .join(ExamRecord, ExamRecord.record_id == ExamAnswerDetail.record_id)
        .filter(
            ExamRecord.user_id == goal.user_id,
            ExamRecord.is_completed == 1,
            ExamRecord.submit_time >= start,
            ExamRecord.submit_time < end,
        )
    )
    exam_count = exam_q.scalar() or 0

    total = int(practice_count) + int(exam_count)

    # CUSTOM 目标：扣除创建时的基线，只算"为目标新增"的量
    baseline = 0
    if (goal.goal_type or "").upper() == "CUSTOM" and goal.baseline_count:
        baseline = int(goal.baseline_count)
        total = max(0, total - baseline)

    required = int(goal.target_count or 0)
    return {
        "actual": total,
        "required": required,
        "practice_count": int(practice_count),
        "exam_count": int(exam_count),
        "baseline": baseline,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "passed": total >= required,
    }


def verify_or_raise(db: Session, goal: StudyGoal) -> dict:
    """未达标则抛 ValueError（由接口层转 400），达标返回统计详情。"""
    detail = count_real_progress(db, goal)
    if not detail["passed"]:
        raise ValueError(
            f"目标未完成：实际 {detail['actual']}/{detail['required']}，"
            f"统计区间 {detail['window_start'][:16]} 起"
        )
    return detail
