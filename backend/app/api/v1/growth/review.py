# 错题遗忘曲线复习 API（模块4 · P4）
#
# - GET  /api/v1/growth/review/due          今日待复习错题
# - GET  /api/v1/growth/review/summary      复习总览
# - POST /api/v1/growth/review/{id}/grade   提交复习评分并重排下次时间
#
# 三个均为新增端点，不改动任何既有端点（R11 只增不改）。
# 算法为 SM-2 简化版：间隔 1 / 3 / 依次 x ease；答错回退 1 天并降低 ease。
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import SysUser, WrongQuestionPersonal

router = APIRouter(prefix="/api/v1/growth/review", tags=["错题复习"])
logger = logging.getLogger(__name__)

GRADE_AGAIN = "again"
GRADE_GOOD = "good"
GRADE_EASY = "easy"
VALID_GRADES = {GRADE_AGAIN, GRADE_GOOD, GRADE_EASY}


def _next_interval(grade: str, interval: int, ease: float, reps: int) -> Tuple[int, float, int]:
    # 返回 (新间隔天数, 新 ease, 新 reps)
    if grade == GRADE_AGAIN:
        return 1, max(1.3, round(ease - 0.2, 2)), 0
    reps = reps + 1
    if grade == GRADE_GOOD:
        if reps == 1:
            new_interval = 1
        elif reps == 2:
            new_interval = 3
        else:
            new_interval = max(1, round(interval * ease))
        return new_interval, ease, reps
    base = interval if interval and interval > 0 else 1
    return max(1, round(base * ease * 1.3)), min(3.0, round(ease + 0.15, 2)), reps


@router.get("/due", summary="今日待复习错题")
async def due_reviews(
    limit: int = 20,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now()
    rows = (
        db.query(WrongQuestionPersonal)
        .filter(
            WrongQuestionPersonal.user_id == current_user.user_id,
            WrongQuestionPersonal.status == 1,
            WrongQuestionPersonal.collection_type == "WRONG",
            WrongQuestionPersonal.next_review_at.isnot(None),
            WrongQuestionPersonal.next_review_at <= now,
        )
        .order_by(WrongQuestionPersonal.next_review_at.asc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    items = []
    for r in rows:
        due = r.next_review_at or now
        items.append({
            "wrong_id": r.wrong_id,
            "question_id": r.question_id,
            "subject_id": r.subject_id,
            "error_count": r.error_count,
            "review_count": r.review_count,
            "interval_days": r.review_interval_days or 1,
            "overdue_days": max(0, (now - due).days),
        })
    return {"total": len(items), "items": items}


@router.get("/summary", summary="复习总览")
async def review_summary(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now()
    week_later = now + timedelta(days=7)

    def base():
        return db.query(func.count(WrongQuestionPersonal.wrong_id)).filter(
            WrongQuestionPersonal.user_id == current_user.user_id,
            WrongQuestionPersonal.status == 1,
            WrongQuestionPersonal.collection_type == "WRONG",
        )

    total = base().scalar() or 0
    due_today = base().filter(
        WrongQuestionPersonal.next_review_at.isnot(None),
        WrongQuestionPersonal.next_review_at <= now,
    ).scalar() or 0
    due_week = base().filter(
        WrongQuestionPersonal.next_review_at.isnot(None),
        WrongQuestionPersonal.next_review_at <= week_later,
    ).scalar() or 0
    unscheduled = base().filter(WrongQuestionPersonal.next_review_at.is_(None)).scalar() or 0
    return {
        "total": total,
        "due_today": due_today,
        "due_7d": due_week,
        "unscheduled": unscheduled,
    }


class GradeRequest(BaseModel):
    grade: str = Field(..., description="again / good / easy")


@router.post("/{wrong_id}/grade", summary="提交复习评分并重排下次复习")
async def grade_review(
    wrong_id: int,
    payload: GradeRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    grade = (payload.grade or "").strip().lower()
    if grade not in VALID_GRADES:
        raise HTTPException(status_code=422, detail="grade 只能是 again / good / easy")

    row: Optional[WrongQuestionPersonal] = (
        db.query(WrongQuestionPersonal)
        .filter(
            WrongQuestionPersonal.wrong_id == wrong_id,
            WrongQuestionPersonal.user_id == current_user.user_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="错题不存在或不属于当前用户")

    interval = row.review_interval_days or 1
    ease = float(row.review_ease or 2.5)
    reps = int(row.review_reps or 0)
    new_interval, new_ease, new_reps = _next_interval(grade, interval, ease, reps)

    now = datetime.now()
    row.review_interval_days = new_interval
    row.review_ease = new_ease
    row.review_reps = new_reps
    row.next_review_at = now + timedelta(days=new_interval)
    row.last_review_time = now
    row.review_count = int(row.review_count or 0) + 1
    if grade == GRADE_GOOD:
        row.correct_count = int(row.correct_count or 0) + 1

    db.commit()
    db.refresh(row)
    return {
        "wrong_id": row.wrong_id,
        "interval_days": row.review_interval_days,
        "ease": float(row.review_ease),
        "reps": row.review_reps,
        "next_review_at": row.next_review_at.isoformat() if row.next_review_at else None,
    }
