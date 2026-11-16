# 学习周报接口（模块4 · 4-6）
#
# GET /api/v1/growth/report/weekly?weeks_ago=0
#   聚合最近一周：专注时长/次数、任务完成、签到、错题变化、最强时段
# 新增端点，不改既有契约（R11 只增不改）。题库为空时相关字段给 null，不编造。
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import (
    FocusRecord,
    StudyGoal,
    SysUser,
    WrongQuestionPersonal,
)

router = APIRouter(prefix="/api/v1/growth/report", tags=["学习周报"])
logger = logging.getLogger(__name__)


def _week_range(weeks_ago: int) -> tuple[datetime, datetime]:
    """返回 [start, end)：以今天为终点向前推 weeks_ago 周，按 7 天窗口。"""
    now = datetime.now()
    end = now - timedelta(weeks=weeks_ago)
    start = end - timedelta(days=7)
    return start, end


@router.get("/weekly", summary="学习周报（一周聚合）")
async def weekly_report(
    weeks_ago: int = Query(0, ge=0, le=51, description="0=本周，1=上一周"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    uid = current_user.user_id
    start, end = _week_range(weeks_ago)

    # 专注
    focus_rows = (
        db.query(FocusRecord.started_at, FocusRecord.minutes)
        .filter(
            FocusRecord.user_id == uid,
            FocusRecord.mode == "focus",
            FocusRecord.started_at >= start,
            FocusRecord.started_at < end,
        )
        .all()
    )
    focus_minutes = sum(int(m or 0) for _, m in focus_rows)
    focus_sessions = len(focus_rows)

    # 最强时段与最活跃的一天
    hour_bucket: dict[int, int] = {}
    day_bucket: dict[str, int] = {}
    for started, minutes in focus_rows:
        if not started:
            continue
        hour_bucket[started.hour] = hour_bucket.get(started.hour, 0) + int(minutes or 0)
        key = started.strftime("%Y-%m-%d")
        day_bucket[key] = day_bucket.get(key, 0) + int(minutes or 0)
    best_hour = max(hour_bucket.items(), key=lambda kv: kv[1])[0] if hour_bucket else None
    best_day = max(day_bucket.items(), key=lambda kv: kv[1])[0] if day_bucket else None

    # 任务
    tasks_total = (
        db.query(func.count(StudyGoal.goal_id))
        .filter(StudyGoal.user_id == uid, StudyGoal.task_date >= start.strftime("%Y-%m-%d"),
                StudyGoal.task_date <= end.strftime("%Y-%m-%d"))
        .scalar()
        or 0
    )
    tasks_done = (
        db.query(func.count(StudyGoal.goal_id))
        .filter(StudyGoal.user_id == uid, StudyGoal.is_completed == 1,
                StudyGoal.task_date >= start.strftime("%Y-%m-%d"),
                StudyGoal.task_date <= end.strftime("%Y-%m-%d"))
        .scalar()
        or 0
    )

    # 错题：本周新增 / 本周复习过
    wrong_new = (
        db.query(func.count(WrongQuestionPersonal.wrong_id))
        .filter(WrongQuestionPersonal.user_id == uid,
                WrongQuestionPersonal.add_time >= start,
                WrongQuestionPersonal.add_time < end)
        .scalar()
        or 0
    )
    wrong_reviewed = (
        db.query(func.count(WrongQuestionPersonal.wrong_id))
        .filter(WrongQuestionPersonal.user_id == uid,
                WrongQuestionPersonal.last_review_time >= start,
                WrongQuestionPersonal.last_review_time < end)
        .scalar()
        or 0
    )

    completion = round(tasks_done / tasks_total * 100) if tasks_total else 0

    return {
        "week_start": start.strftime("%Y-%m-%d"),
        "week_end": end.strftime("%Y-%m-%d"),
        "range_note": "统计窗口为 [开始日, 结束日) 不含结束日",
        "weeks_ago": weeks_ago,
        "focus": {
            "minutes": focus_minutes,
            "hours": round(focus_minutes / 60, 1),
            "sessions": focus_sessions,
            "best_hour": best_hour,
            "best_day": best_day,
        },
        "tasks": {
            "total": tasks_total,
            "done": tasks_done,
            "completion": completion,
        },
        "wrong": {
            "new": wrong_new,
            "reviewed": wrong_reviewed,
        },
        "comment": _comment(focus_minutes, completion, wrong_new, tasks_total),
        "has_data": bool(focus_sessions or tasks_total or wrong_new or wrong_reviewed),
    }


def _comment(focus_minutes: int, completion: int, wrong_new: int, tasks_total: int) -> str:
    """按数据给一句人话点评；没有数据就说没有，不编。"""
    if not focus_minutes and not tasks_total:
        return "这周还没有记录，点一下番茄钟，数据就从第一格开始攒。"
    if completion >= 80 and focus_minutes >= 300:
        return "执行力很稳：任务基本清完，专注时长也在线，保持这个节奏。"
    if completion >= 50:
        return "节奏还行，任务完成过半，专注时长可以再加一点。"
    if wrong_new >= 10:
        return "这周新错题偏多，先把错题过一遍再刷新的。"
    return "起步阶段，先把每日专注拉起来，比多刷题更重要。"
