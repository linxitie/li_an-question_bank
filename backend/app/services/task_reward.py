"""任务奖励自动发放（2026-11-10）。

背景：学生完成任务后必须进入「商城 → 任务」手动点「领取」，奖励不会自动到账。
本模块把「完成即发放」这件事收敛成一个**幂等**函数，供两个入口复用：

1. `achievement_judge._apply_task_progress()`：行为事件触发进度推进、任务刚达成时立即发；
2. `POST /api/tasks/auto-claim`：页面兜底，把历史上「已完成但没领」的任务补齐。

幂等依据是 `user_task_progress.claimed` 标志位（与手动领取接口同一套字段），
因此自动发放和手动领取不会重复发币。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..models.models import SysUser, Task, UserTaskProgress
from . import weekly_tasks as weekly
from .coin_ledger import grant as grant_coins
from .growth_service import add_growth

logger = logging.getLogger(__name__)

# 周任务单任务封顶 / 每周封顶在 weekly 服务内计算，这里只负责调用


def resolve_reward(db: Session, user_id: int, task: Task) -> int:
    """任务当前可发放的金币数（周任务套难度/稀缺系数并受封顶约束）。"""
    if task.t_type == "weekly":
        slot = weekly.pinned_slots(db).get(task.task_id, 0)
        return int(weekly.claimable_amount(
            task, user_id, db, weekly.PINNED_SCARCITY.get(slot)
        ) or 0)
    return int(task.reward_coins or 0)


def auto_claim(
    db: Session,
    user: SysUser,
    task: Task,
    progress: UserTaskProgress,
    now: Optional[datetime] = None,
) -> int:
    """已完成任务立即发奖；返回本次发放的金币（0 = 未发放/无需发放）。

    调用方负责 `db.commit()`；本函数只写会话内对象。
    """
    if progress is None or progress.claimed == 1 or progress.expired == 1:
        return 0

    reward = resolve_reward(db, user.user_id, task)
    if reward <= 0:
        # 周任务达到封顶或无奖励时不发，保留「待领取」状态，避免吞掉任务
        return 0

    now = now or datetime.now()
    source_type = "RANDOM_TASK" if task.t_type == "random" else "TASK"
    grant_coins(
        db,
        user,
        reward,
        source_type=source_type,
        related_id=task.task_id,
        description=f"完成任务：{task.title}",
    )

    # 周任务 C 类场景奖励券：与手动领取保持同一口径
    coupon_code = getattr(task, "coupon_code", None)
    if task.t_type == "weekly" and coupon_code:
        try:
            from ..api.v1.reward.coupons import grant_coupon

            grant_coupon(db, user, coupon_code, source="TASK")
        except Exception as exc:  # noqa: BLE001 — 发券失败不影响金币与任务状态
            logger.warning("任务 %s 自动发券失败: %s", task.task_id, exc)

    if task.reward_growth and task.reward_growth > 0:
        add_growth(db, user, task.reward_growth)

    progress.completed = 1
    if not getattr(progress, "completed_at", None):
        progress.completed_at = now
    progress.claimed = 1
    progress.claimed_at = now
    progress.pending_verify = 0

    logger.info(
        "用户 %s 完成任务 %s，自动发放 %s 金币",
        user.user_id,
        task.title,
        reward,
    )
    return reward
