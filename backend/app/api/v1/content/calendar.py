"""
考试日历 API
GET /api/calendar/exams — 获取最新考试信息
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user, get_optional_user
from ....models.models import ExamCalendar as ExamCalendarModel, SysUser

router = APIRouter(prefix="/api/calendar", tags=["考试日历"])
logger = logging.getLogger(__name__)

# 状态标签颜色映射（与招考信息模块一致）
STATUS_COLORS = {
    "报名中": "#10b981",    # 绿色
    "即将报名": "#1a2a6c",  # 藏蓝色
    "已截止": "#c41e3a",    # 中国红
}


def _compute_status(e):
    from datetime import datetime as dt
    now = dt.now()
    if e.registration_end and isinstance(e.registration_end, dt) and e.registration_end < now:
        return "已截止"
    if e.registration_start and isinstance(e.registration_start, dt) and e.registration_start > now:
        return "即将报名"
    if e.registration_start and e.registration_end \
       and isinstance(e.registration_start, dt) and isinstance(e.registration_end, dt) \
       and e.registration_start <= now <= e.registration_end:
        return "报名中"
    # Fallback: based on exam_date
    if e.exam_date and e.exam_date < now:
        return "已截止"
    return "报名中"


def _serialize_exam(e: ExamCalendarModel) -> dict:
    """序列化考试信息"""
    status = _compute_status(e)
    return {
        "id": e.event_id,
        "title": e.title,
        "month": e.month,
        "day": e.day,
        "province": e.province,
        "exam_type": e.exam_type or "",
        "exam_format": e.exam_format or "",
        "exam_date": e.exam_date.isoformat() if e.exam_date else None,
        "registration_start": e.registration_start.isoformat() if e.registration_start else "",
        "registration_end": e.registration_end.isoformat() if e.registration_end else "",
        "url": e.url or "",
        "description": e.description or "",
        "content_html": e.content_html or e.description or "",
        "recruitment_count": getattr(e, 'recruitment_count', '') or "",
        "status": status,
        "status_color": STATUS_COLORS.get(status, "#10b981"),
    }


@router.get("/exams", summary="获取考试日历")
async def get_exams(
    limit: int = Query(20, ge=1, le=50, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量（分页）"),
    province: Optional[str] = Query(None, description="筛选省份"),
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取最新考试日历信息，支持按省份筛选和分页"""
    query = db.query(ExamCalendarModel).filter(ExamCalendarModel.status == 1)
    if province:
        query = query.filter(ExamCalendarModel.province == province)

    # 获取总数
    total = query.count()

    # 报名中优先 → 即将报名 → 已截止, 同状态按 exam_date 升序
    from sqlalchemy import case as sa_case
    now = __import__('datetime').datetime.now()
    status_order = sa_case(
        (ExamCalendarModel.registration_end.isnot(None) & (ExamCalendarModel.registration_end >= now), 0),
        (ExamCalendarModel.registration_start.isnot(None) & (ExamCalendarModel.registration_start > now), 1),
        else_=2
    )
    exams = query.order_by(status_order, ExamCalendarModel.exam_date.asc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [_serialize_exam(e) for e in exams],
        "has_more": (offset + limit) < total
    }


@router.get("/latest", summary="获取最新一条考试信息")
async def get_latest_exam(
    current_user: Optional[SysUser] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """获取最新发布的考试信息（用于判断是否有更新）"""
    latest = db.query(ExamCalendarModel).filter(
        ExamCalendarModel.status == 1
    ).order_by(ExamCalendarModel.create_time.desc()).first()

    if not latest:
        return {"has_update": False, "message": "暂无考试信息", "item": None}

    return {
        "has_update": True,
        "message": "最新",
        "item": _serialize_exam(latest)
    }
