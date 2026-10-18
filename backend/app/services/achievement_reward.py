"""成就奖励发放单点（P2-52）。

职责边界
--------
- 所有「成就解锁」引发的金币 / 成长值只允许经本模块发放；
- 幂等硬约束：同一用户同一成就只发一次奖。最终防线是
  ``user_achievement.uk_user_achievement(user_id, achievement_id)`` 唯一约束；
  本模块在写入前先查一次，写入时再用 SAVEPOINT 兜住并发冲突；
- 不直接写业务表：金币走 reward 域公开契约 ``grant_coins``，成长值走
  ``growth_service.add_growth``；
- 不 commit：事务边界由调用方（事件消费者 / check_and_grant）决定。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.models import Achievement, SysUser, UserAchievement
from .growth_service import GROWTH_RULES, add_growth

logger = logging.getLogger(__name__)


def _get_user_achievement(
    db: Session, user_id: int, achievement_id: int
) -> Optional[UserAchievement]:
    return (
        db.query(UserAchievement)
        .filter(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement_id,
        )
        .first()
    )


def grant_unlock(
    db: Session,
    user: SysUser,
    achievement: Achievement,
    tier: int = 1,
    upgraded: bool = False,
) -> bool:
    """发放一次成就解锁 / 升档。

    返回 ``True`` 表示状态发生改变（新解锁或升档），``False`` 表示已存在且
    无需变更。新解锁才发金币与成长值；升档只更新档位，不重复发奖。
    """
    achievement_id = int(achievement.achievement_id)
    existing = _get_user_achievement(db, user.user_id, achievement_id)

    if existing is None:
        # 并发下两个消费者可能同时通过上面的查询；SAVEPOINT 保证冲突方
        # 只回滚本次插入，不影响同事务内已算好的任务进度。
        try:
            with db.begin_nested():
                db.add(
                    UserAchievement(
                        user_id=user.user_id,
                        achievement_id=achievement_id,
                        tier=int(tier or 1),
                    )
                )
                db.flush()
        except IntegrityError:
            logger.info(
                "成就并发重复发放已忽略 user=%s achievement=%s",
                user.user_id,
                achievement_id,
            )
            return False

        if int(achievement.reward_coins or 0) > 0:
            # 跨域发币唯一合法入口（reward 域公开契约）
            from ..api.v1.reward.contract import grant_coins

            grant_coins(
                db,
                user,
                int(achievement.reward_coins),
                source_type="SYSTEM",
                related_id=achievement_id,
                description=f"获得成就：{achievement.name}",
            )

        add_growth(db, user, GROWTH_RULES["achievement"])
        logger.info(
            "用户 %s 获得成就「%s」tier=%s，奖励 %s 金币",
            user.user_id,
            achievement.name,
            tier,
            achievement.reward_coins,
        )
        return True

    current_tier = int(existing.tier or 1)
    target_tier = int(tier or 1)
    if target_tier > current_tier:
        existing.tier = target_tier
        logger.info(
            "用户 %s 成就「%s」升级到 tier %s",
            user.user_id,
            achievement.name,
            target_tier,
        )
        return True

    # 已解锁（或档位不升）：不重复发奖，幂等返回 False
    return False


def grant_newly(
    db: Session,
    user: SysUser,
    newly: Iterable[Dict[str, Any]],
) -> int:
    """按判据引擎返回的 ``newly_unlocked`` 列表发放奖励。

    每个元素至少含 ``achievement_id``，可选 ``tier`` / ``upgraded``。
    返回实际发生状态变更的条目数。
    """
    granted = 0
    for item in newly or ():
        try:
            achievement_id = int(item.get("achievement_id"))
        except (TypeError, ValueError):
            continue
        achievement = db.get(Achievement, achievement_id)
        if achievement is None:
            logger.warning("成就奖励跳过：找不到 achievement_id=%s", achievement_id)
            continue
        if grant_unlock(
            db,
            user,
            achievement,
            tier=int(item.get("tier") or 1),
            upgraded=bool(item.get("upgraded")),
        ):
            granted += 1
    return granted
