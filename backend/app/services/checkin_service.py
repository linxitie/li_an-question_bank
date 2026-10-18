"""每日签到领域服务（P2-46）。

设计约束
--------
- **不新建表、不加字段**：完成记录复用既有 ``daily_checkin`` 表，其
  ``uk_user_date(user_id, checkin_date)`` 唯一约束是「一天一次」的最终防线。
- **并发幂等**：先尝试 ``INSERT OR IGNORE`` 抢占当日记录，只有 rowcount=1
  的请求才继续发放奖励；并发第二个请求在唯一约束上被忽略，不会重复发币。
- **奖励参数复用** ``badge_task`` 的 daily 任务：按 ``task_code`` 查找
  （默认 ``daily_checkin``），读取 ``reward_coins`` / ``reward_growth``。
  历史库尚无该任务时使用与既有签到一致的默认值，不凭空写入新任务行。
- **提交边界**：本服务自行提交事务，调用方必须在 ``commit`` 之后发布
  E10 ``checkin.done``，保证事件只在成功签到（且仅首次）时产生一次。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from ..models.models import CoinRecord, DailyCheckin, SysUser, Task
from .growth_service import add_growth

logger = logging.getLogger(__name__)

#: 复用 ``badge_task`` 的日任务代码；不存在时使用默认奖励。
CHECKIN_TASK_CODE = "daily_checkin"
DEFAULT_CHECKIN_COINS = 5
DEFAULT_CHECKIN_GROWTH = 5


def _today(today: Optional[date] = None) -> date:
    return today or date.today()


def _date_str(value: date) -> str:
    return value.strftime("%Y-%m-%d")


def _get_task(db: Session) -> Optional[Task]:
    return (
        db.query(Task)
        .filter(Task.task_code == CHECKIN_TASK_CODE, Task.t_type == "daily")
        .first()
    )


def _reward_config(task: Optional[Task]) -> tuple[int, int]:
    if task is None:
        return DEFAULT_CHECKIN_COINS, DEFAULT_CHECKIN_GROWTH
    return int(task.reward_coins or 0), int(task.reward_growth or 0)


def _find_record(db: Session, user_id: int, today_str: str) -> Optional[DailyCheckin]:
    return (
        db.query(DailyCheckin)
        .filter(
            DailyCheckin.user_id == user_id,
            DailyCheckin.checkin_date == today_str,
        )
        .first()
    )


def _current_streak(db: Session, user_id: int, today_value: date) -> int:
    """未签到时的当前连续天数：以昨日记录为准，断签即归零。"""
    yesterday_str = _date_str(today_value - timedelta(days=1))
    yesterday = (
        db.query(DailyCheckin)
        .filter(
            DailyCheckin.user_id == user_id,
            DailyCheckin.checkin_date == yesterday_str,
        )
        .first()
    )
    return int(yesterday.continuous_days or 0) if yesterday else 0


def get_today_status(
    db: Session, user_id: int, today: Optional[date] = None
) -> dict:
    """查询今日签到状态（只读，不写库）。"""
    today_value = _today(today)
    today_str = _date_str(today_value)
    task = _get_task(db)
    next_coins, next_growth = _reward_config(task)
    record = _find_record(db, user_id, today_str)

    if record is not None:
        continuous_days = int(record.continuous_days or 0)
        today_reward = int(record.coin_reward or 0)
    else:
        continuous_days = _current_streak(db, user_id, today_value)
        today_reward = 0

    return {
        "date": today_str,
        "checked_in": record is not None,
        "continuous_days": continuous_days,
        "today_reward": today_reward,
        "next_reward": {"coins": next_coins, "growth": next_growth},
    }


def perform_checkin(
    db: Session, user_id: int, today: Optional[date] = None
) -> dict:
    """执行签到（幂等）。

    返回字段：
    - ``is_today_first``：本次是否真正签到成功（False = 今日已签）
    - ``continuous_days``：今日连续天数
    - ``today_reward`` / ``reward_growth``：今日已获得的奖励（重复签到时
      ``reward_growth`` 为 0，表示本次未发放）
    """
    today_value = _today(today)
    today_str = _date_str(today_value)

    # 快速幂等：已签到直接返回，不进入写事务。
    existing = _find_record(db, user_id, today_str)
    if existing is not None:
        return {
            "date": today_str,
            "checked_in": True,
            "is_today_first": False,
            "continuous_days": int(existing.continuous_days or 0),
            "today_reward": int(existing.coin_reward or 0),
            "reward_growth": 0,
            "message": "今日已签到",
        }

    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if user is None:
        raise LookupError(f"user {user_id} not found")

    task = _get_task(db)
    coins, growth = _reward_config(task)

    yesterday_str = _date_str(today_value - timedelta(days=1))
    yesterday = (
        db.query(DailyCheckin)
        .filter(
            DailyCheckin.user_id == user_id,
            DailyCheckin.checkin_date == yesterday_str,
        )
        .first()
    )
    continuous_days = int(yesterday.continuous_days or 0) + 1 if yesterday else 1
    total_days = int(user.total_checkin_days or 0) + 1

    # 并发闸门：唯一约束 uk_user_date 决定唯一赢家；冲突方 rowcount=0。
    claim = (
        sqlite_insert(DailyCheckin)
        .values(
            user_id=user_id,
            checkin_date=today_str,
            checkin_time=datetime.now(),
            continuous_days=continuous_days,
            total_days=total_days,
            has_makeup=0,
            coin_reward=coins,
            streak_bonus=0,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "checkin_date"])
    )
    claimed = db.execute(claim)
    if (claimed.rowcount or 0) != 1:
        db.rollback()
        winner = _find_record(db, user_id, today_str)
        if winner is None:
            raise RuntimeError("签到记录并发冲突但未找到既有记录")
        return {
            "date": today_str,
            "checked_in": True,
            "is_today_first": False,
            "continuous_days": int(winner.continuous_days or 0),
            "today_reward": int(winner.coin_reward or 0),
            "reward_growth": 0,
            "message": "今日已签到",
        }

    user.continuous_checkin_days = continuous_days
    user.total_checkin_days = total_days
    if coins > 0:
        user.total_coins = int(user.total_coins or 0) + coins
        db.add(
            CoinRecord(
                user_id=user_id,
                coin_change=coins,
                current_balance=user.total_coins,
                transaction_type="GAIN",
                source_type="CHECKIN",
                description=f"每日签到奖励（连续{continuous_days}天）",
            )
        )
    add_growth(db, user, growth)

    db.commit()
    logger.info(
        "签到成功 user=%s date=%s streak=%s coins=%s growth=%s",
        user_id,
        today_str,
        continuous_days,
        coins,
        growth,
    )
    return {
        "date": today_str,
        "checked_in": True,
        "is_today_first": True,
        "continuous_days": continuous_days,
        "today_reward": coins,
        "reward_growth": growth,
        "message": f"签到成功，连续{continuous_days}天",
    }
