"""每日签到 API（P2-45 / P2-47）。

- ``POST /api/v1/growth/checkin``：签到（幂等，一天一次）
- ``GET  /api/v1/growth/checkin/status``：查询今日状态

这两个路径为新增端点，不改动任何既有 ``/api/*`` 端点（R11 只增不改）。
E10 ``checkin.done`` 仅在服务成功提交**且为今日首次**后发布一次；
重复签到不会产生事件。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....core.trigger_types import TRIGGER_CHECKIN_DONE
from ....models.models import SysUser
from ....services import checkin_service
from ....services.event_consumer import record_user_action

router = APIRouter(prefix="/api/v1/growth", tags=["每日签到"])
logger = logging.getLogger(__name__)


@router.post("/checkin", summary="每日签到")
async def do_checkin(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """签到；返回今日状态、连续天数与本次奖励。"""
    try:
        result = checkin_service.perform_checkin(db, current_user.user_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="用户不存在") from exc

    # 事务已在服务内提交；仅在今日首次签到后发布 E10，且发布失败不影响签到结果。
    if result["is_today_first"]:
        try:
            await record_user_action(
                db,
                current_user.user_id,
                TRIGGER_CHECKIN_DONE,
                session={
                    "date": result["date"],
                    "continuous_days": result["continuous_days"],
                    "coin_reward": result["today_reward"],
                    "growth_reward": result["reward_growth"],
                },
            )
        except Exception as exc:  # noqa: BLE001 - 事件失败不得回滚已完成的签到
            logger.error(
                "签到事件发布失败 user=%s date=%s: %s",
                current_user.user_id,
                result["date"],
                exc,
            )

    return result


@router.get("/checkin/status", summary="查询今日签到状态")
async def checkin_status(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """只读查询今日是否已签到、连续天数与下次可领奖励。"""
    return checkin_service.get_today_status(db, current_user.user_id)
