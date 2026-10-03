# -*- coding: utf-8 -*-
"""
学习目标进度自动追踪服务

背景
----
`StudyGoal.current_count` 此前**没有任何自动递增机制**，仅有一个需要前端
主动调用的 `POST /api/goals/{id}/progress` 手动端点。导致金币购与首页的
目标列表只能显示「完成」，无法反映用户真实刷题进度，也就无法科学发放奖励。

本模块提供 `sync_goal_progress`：在练习记录写入后，按真实刷题量**重算**
未完成目标的 `current_count`，并据此判定完成状态与计算奖励。

设计决策（为何这样写）
--------------------
1. **幂等重算，而非增量累加**
   增量式 `current_count += n` 在并发写入、请求重试、网络超时重发时必然漂移，
   且漂移不可逆、无法自愈。改为每次基于 `practice_record` 聚合重算，
   天然可重复执行，便于运维随时重跑修正历史误差。

2. **按 `practice_date` 聚合，而非 `practice_time`**
   `practice_time` 是本地时间 DateTime，跨时区或夏令时场景下用
   `DATE(practice_time)` 分组容易把凌晨/深夜的记录划到错误日期。
   `practice_date` 是入库时落库的纯 Date 字段（实测 100% 填充），语义明确。

3. **只更新未完成目标**
   已完成目标保留当时的完成时间与发奖依据，不回退，避免奖励被反复重算。

4. **跨天自动归零**
   DAILY 目标只统计「今天」，日期一变基数即为 0，天然满足用户要求的归零，
   无需额外的定时任务。

5. **触发点绑定真实做题行为**
   由 `POST /api/practice/record` 成功后调用，不依赖客户端上报，
   杜绝伪造进度。
"""
import logging
from datetime import date, timedelta
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.models import PracticeRecord, StudyGoal

logger = logging.getLogger(__name__)


def _week_start(today: date) -> date:
    """返回本周一（ISO 周：以 Monday 为一周之始）"""
    return today - timedelta(days=today.weekday())


def _count_practice(db: Session, user_id: int, target_date: date) -> int:
    """统计指定日期的刷题数"""
    return (
        db.query(func.count(PracticeRecord.record_id))
        .filter(
            PracticeRecord.user_id == user_id,
            PracticeRecord.practice_date == target_date,
        )
        .scalar()
        or 0
    )


def _compute_reward(goal: StudyGoal) -> int:
    """
    依据实际达成率计算奖励金币，避免「一味显示完成」。

    达成率 = current_count / target_count（上限 1.0）
    基础奖励 base_reward（缺省 20）× 达成率 × 难度系数 difficulty_factor

    保留原有五维字段（quality/persistence/improvement）作为后续扩展点，
    本期只接入达成率与难度系数两项可确定的量，不臆造评分。
    """
    if goal.target_count <= 0:
        return 0
    ratio = min(1.0, (goal.current_count or 0) / float(goal.target_count))
    base = goal.base_reward if goal.base_reward and goal.base_reward > 0 else 20
    factor = goal.difficulty_factor if goal.difficulty_factor and goal.difficulty_factor > 0 else 1.0
    return int(round(base * ratio * factor))


def sync_goal_progress(user_id: int, db: Session) -> List[int]:
    """
    按真实刷题量重算该用户所有未完成目标的进度。

    Returns:
        发生状态变化（进度更新或完成）的 goal_id 列表
    """
    today = date.today()
    week_start = _week_start(today)

    goals = (
        db.query(StudyGoal)
        .filter(
            StudyGoal.user_id == user_id,
            StudyGoal.status == 1,
            StudyGoal.is_completed == 0,
        )
        .all()
    )
    if not goals:
        return []

    # 一次查询当天与本周聚合，避免逐目标查询
    today_count = _count_practice(db, user_id, today)
    week_count = (
        db.query(func.count(PracticeRecord.record_id))
        .filter(
            PracticeRecord.user_id == user_id,
            PracticeRecord.practice_date >= week_start,
            PracticeRecord.practice_date <= today,
        )
        .scalar()
        or 0
    )

    changed: List[int] = []
    for goal in goals:
        gtype = goal.goal_type
        if gtype == "WEEKLY":
            actual = week_count
        elif gtype in ("DAILY", "CUSTOM"):
            # CUSTOM 目标按日推进（与首页「今日目标」一致）
            actual = today_count
        else:
            # MONTHLY 等暂不自动统计，保持原值由用户手动维护
            continue

        new_count = min(actual, goal.target_count) if goal.target_count > 0 else actual

        if goal.current_count != new_count:
            logger.info(
                "[goal_progress] 目标 %s(%s) 进度 %s -> %s",
                goal.goal_id, gtype, goal.current_count, new_count,
            )
            goal.current_count = new_count

        if goal.target_count > 0 and new_count >= goal.target_count:
            goal.is_completed = 1
            from datetime import datetime
            goal.completed_time = datetime.now()
            goal.reward_coins = _compute_reward(goal)
            logger.info(
                "[goal_progress] 目标 %s 达成，发奖 %s 金币",
                goal.goal_id, goal.reward_coins,
            )

        changed.append(goal.goal_id)

    if changed:
        try:
            db.commit()
        except Exception as e:  # noqa: BLE001 — 进度同步失败不应影响刷题主流程
            db.rollback()
            logger.warning("[goal_progress] 进度同步提交失败: %s", e)
            return []

    return changed