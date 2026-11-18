"""艾宾浩斯复习 API（M3）

GET  /api/review/due?limit=&subject=&mode=today   今日待复习（按优先级 P 排序）
POST /api/review/{question_id}/grade              提交复习结果 → 新间隔与下次到期
GET  /api/review/stats?days=30                    复习量/正确率/平均保持率/逾期数
POST /api/review/rebuild                          冷启动：从错题 + 历史错答生成排程（幂等）
GET  /api/review/calendar?month=2026-11           学习日历：每日 done/due + 考试节点
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import SysUser
from ....services import review_scheduler

router = APIRouter(prefix="/api/review", tags=["复习提醒"])
logger = logging.getLogger(__name__)


class GradeRequest(BaseModel):
    result: int = Field(..., ge=0, le=1, description="1 对 / 0 错")
    elapsed_ms: Optional[int] = Field(None, ge=0, description="作答耗时（毫秒）")


@router.get("/due", summary="今日待复习")
async def review_due(
    limit: int = Query(20, ge=1, le=100),
    subject: Optional[int] = Query(None, description="科目 ID：1 行测 / 2 申论 / 3 公专"),
    mode: str = Query("today"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """首屏就把排程补齐：用户从没进过这个接口时也应该看到今天的队列。"""
    try:
        review_scheduler.rebuild(db, current_user.user_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("复习排程补建失败: %s", e)
    return review_scheduler.due(db, current_user.user_id, limit=limit, subject_id=subject, mode=mode)


@router.post("/{question_id}/grade", summary="提交复习结果")
async def review_grade(
    question_id: int,
    req: GradeRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return review_scheduler.grade(
            db,
            current_user.user_id,
            question_id,
            req.result,
            req.elapsed_ms,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/stats", summary="复习统计")
async def review_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return review_scheduler.stats(db, current_user.user_id, days=days)


@router.post("/rebuild", summary="冷启动：生成复习排程（幂等）")
async def review_rebuild(
    limit: Optional[int] = Query(None, ge=1, le=5000),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return review_scheduler.rebuild(db, current_user.user_id, limit=limit)


@router.get("/calendar", summary="学习日历：每日复习量与考试节点")
async def review_calendar(
    month: str = Query("", description="YYYY-MM；留空取当月"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return review_scheduler.calendar(db, current_user.user_id, month=month)
