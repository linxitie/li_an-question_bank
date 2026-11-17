# 专注力数据接口（模块4 · 4-1 热力图）
#
# - POST /api/v1/growth/focus/record   写入一次专注记录
# - GET  /api/v1/growth/focus/heatmap  星期 × 小时 热力矩阵
#
# 均为新增端点，不改既有契约（R11 只增不改）。
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import FocusRecord, SysUser

router = APIRouter(prefix="/api/v1/growth/focus", tags=["专注力"])
logger = logging.getLogger(__name__)


class FocusRecordIn(BaseModel):
    minutes: int = Field(..., ge=1, le=600, description="本次专注分钟数")
    mode: str = Field("focus", description="focus / break")
    source: str = Field("widget", max_length=20)
    started_at: Optional[datetime] = None


@router.post("/record", summary="写入一次专注记录")
async def add_record(
    payload: FocusRecordIn,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ended = datetime.now()
    started = payload.started_at or (ended - timedelta(minutes=payload.minutes))
    # 前端可能传带时区的 ISO 串；统一转成本地 naive 时间，否则热力图会整体偏 8 小时
    if started.tzinfo is not None:
        started = started.astimezone().replace(tzinfo=None)
    row = FocusRecord(
        user_id=current_user.user_id,
        started_at=started,
        ended_at=ended,
        minutes=int(payload.minutes),
        mode=(payload.mode or "focus")[:10],
        source=(payload.source or "widget")[:20],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"record_id": row.record_id, "minutes": row.minutes, "started_at": row.started_at.isoformat()}


@router.get("/heatmap", summary="星期 × 小时 专注热力矩阵")
async def heatmap(
    weeks: int = Query(4, ge=1, le=26, description="统计最近多少周"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    since = datetime.now() - timedelta(weeks=weeks)
    rows = (
        db.query(FocusRecord.started_at, FocusRecord.minutes)
        .filter(
            FocusRecord.user_id == current_user.user_id,
            FocusRecord.mode == "focus",
            FocusRecord.started_at >= since,
        )
        .all()
    )

    matrix = [[0 for _ in range(24)] for _ in range(7)]
    daily = {}
    total = 0
    for started, minutes in rows:
        if not started:
            continue
        wd = started.weekday()
        hr = started.hour
        m = int(minutes or 0)
        if 0 <= wd < 7 and 0 <= hr < 24:
            matrix[wd][hr] += m
        total += m
        key = started.strftime("%Y-%m-%d")
        daily[key] = daily.get(key, 0) + m

    best = {"weekday": None, "hour": None, "minutes": 0}
    for wd in range(7):
        for hr in range(24):
            if matrix[wd][hr] > best["minutes"]:
                best = {"weekday": wd, "hour": hr, "minutes": matrix[wd][hr]}

    return {
        "weeks": weeks,
        "matrix": matrix,
        "total_minutes": total,
        "session_count": len(rows),
        "best_slot": best,
        "daily": daily,
    }
