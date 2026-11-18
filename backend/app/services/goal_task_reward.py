"""学习计划每日任务（StudyGoal）金币自动发放（2026-11-15）。

背景：`badge_task`（Task 表）完成任务时会走
`achievement_judge._apply_task_progress → task_reward.auto_claim` 立即发币，
而学习计划每日任务（StudyGoal）只有手动接口 `POST /api/plan/task/{goal_id}/claim`，
学生勾选完成后还要再去点一次「领取」，与 badge_task 的体验不一致。

三个入口复用本模块：

1. `POST /api/plan/task/{goal_id}/toggle`：勾选完成的瞬间立即发；
2. `POST /api/tasks/auto-claim`：页面兜底（商城任务页每次进入都会调）；
3. `GET  /api/tasks/overview`：首页任务卡也会触发兜底。

幂等依据是 `study_goal.coin_claimed`（与手动领取接口同一字段），
因此自动发放与手动领取不会重复发币；发币走 `reward.contract.grant_coins`
（跨域写入必须走公开契约，禁止直接实例化他域表）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from ..models.models import StudyGoal, SysUser

logger = logging.getLogger(__name__)

# 兜底只回溯近期任务：完成很久的历史任务不再自动补发，避免一次性刷出大量金币
DEFAULT_BACKFILL_DAYS = 30


def _grant(db: Session, user: SysUser, goal: StudyGoal, now: datetime) -> int:
    """真正发币并打幂等标记；返回本次发放金额。"""
    coin = int(goal.coin_reward or 0)
    if coin <= 0:
        return 0
    from ..api.v1.reward.contract import grant_coins

    grant_coins(
        db,
        user,
        coin,
        source_type="TASK",
        related_id=goal.goal_id,
        description=f"完成每日任务：{goal.title}",
    )
    goal.coin_claimed = 1
    goal.update_time = now
    return coin


def auto_claim_goal_task(
    db: Session,
    user: SysUser,
    goal: Optional[StudyGoal],
    now: Optional[datetime] = None,
) -> int:
    """单个计划任务「完成即发」；返回本次发放金币（0 = 未发放/无需发放）。

    调用方负责 `db.commit()`；本函数只写会话内对象。
    """
    if goal is None or user is None:
        return 0
    if goal.user_id != user.user_id:
        return 0
    if goal.status != 1 or goal.is_completed != 1 or goal.coin_claimed == 1:
        return 0

    now = now or datetime.now()
    coin = _grant(db, user, goal, now)
    if coin > 0:
        logger.info(
            "用户 %s 完成计划任务 %s，自动发放 %s 金币",
            user.user_id,
            goal.goal_id,
            coin,
        )
    return coin


def auto_claim_completed_goal_tasks(
    db: Session,
    user: SysUser,
    *,
    days: Optional[int] = DEFAULT_BACKFILL_DAYS,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """兜底：把「已完成但没领」的计划任务奖励补齐（幂等）。返回本次发放条目。"""
    now = now or datetime.now()
    query = db.query(StudyGoal).filter(
        StudyGoal.user_id == user.user_id,
        StudyGoal.status == 1,
        StudyGoal.is_completed == 1,
        StudyGoal.coin_claimed == 0,
        StudyGoal.coin_reward > 0,
    )
    if days:
        query = query.filter(StudyGoal.completed_time >= now - timedelta(days=days))

    granted: List[Dict[str, Any]] = []
    for goal in query.all():
        coin = auto_claim_goal_task(db, user, goal, now)
        if coin > 0:
            granted.append(
                {
                    "source": "study_goal",
                    "goal_id": goal.goal_id,
                    "title": goal.title,
                    "reward_coins": coin,
                }
            )
    return granted
