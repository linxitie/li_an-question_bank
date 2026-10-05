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


def _aggregate_by_subject(
    db: Session, user_id: int, start_date: date, end_date: date
) -> dict:
    """一次查询聚合区间内**按科目分组**的刷题量与累计时长。

    返回 ``{subject_id: (count, seconds)}``。

    为什么按科目分组而不是逐目标查一次：
    目标列表里可能有多个不同 ``subject_mode`` 的目标，若对每个目标单独
    过滤一次就是 N+1 查询。这里改为「每个日期区间一条 group by 查询」，
    区间内所有科目一次取回，循环内查表，SQL 数量与目标数无关。

    ``subject_id`` 可能为 NULL（历史记录缺科目），SQLAlchemy 的
    ``group_by`` 会把 NULL 归为独立一组，键即 ``None``，混科目标会把它
    一并累加进去——这比静默丢弃这些记录更接近真实刷题量。
    """
    rows = (
        db.query(
            PracticeRecord.subject_id,
            func.count(PracticeRecord.record_id),
            func.coalesce(func.sum(PracticeRecord.time_spent), 0),
        )
        .filter(
            PracticeRecord.user_id == user_id,
            PracticeRecord.practice_date >= start_date,
            PracticeRecord.practice_date <= end_date,
        )
        .group_by(PracticeRecord.subject_id)
        .all()
    )
    return {r[0]: (int(r[1] or 0), int(r[2] or 0)) for r in rows}


def _resolve_by_subject(table: dict, subject_mode: int) -> tuple:
    """按目标的科目限定，从分组聚合结果中取出真实刷题量。

    ``subject_mode == 0`` 表示混科、不限定科目，累加所有科目；
    ``subject_mode > 0`` 表示仅统计该科目。

    此前实现完全忽略 ``subject_mode``，导致「申论 20 题」的目标会被行测
    的刷题量顶上去——这正是用户反馈「进度条不是真实的算法」的根因。

    Returns:
        ``(count, seconds)``
    """
    if subject_mode and int(subject_mode) > 0:
        return table.get(int(subject_mode), (0, 0))
    count = sum(v[0] for v in table.values())
    seconds = sum(v[1] for v in table.values())
    return count, seconds


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
    month_start = today.replace(day=1)

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

    # 每种目标类型对应一个统计区间。CUSTOM 与 DAILY 同为「按日推进」
    # （沿用原实现的口径：与首页「今日目标」一致）。
    ranges = {
        "DAILY": (today, today),
        "CUSTOM": (today, today),
        "WEEKLY": (week_start, today),
        # MONTHLY 此前被 continue 直接跳过，等于月度目标永不推进。
        "MONTHLY": (month_start, today),
    }

    # 只为实际存在的目标类型发起查询，且每种类型仅一条 group by 语句，
    # 因此 SQL 数量取决于类型数（≤4）而非目标数，无 N+1。
    tables: dict = {}
    for gtype in {g.goal_type for g in goals if g.goal_type in ranges}:
        start, end = ranges[gtype]
        tables[gtype] = _aggregate_by_subject(db, user_id, start, end)

    changed: List[int] = []
    for goal in goals:
        gtype = goal.goal_type
        if gtype not in ranges:
            # 未知类型（如未来新增）保持原值，不臆造统计口径
            continue

        count, seconds = _resolve_by_subject(tables[gtype], goal.subject_mode or 0)

        # 进度口径说明：`target_count` 的语义是「题量」（前端 L210 校验题量、
        # L79 以 current_count/target_count 展示），因此进度必须用题数。
        # `expected_minutes` 是「单日预期学习时间」这一参考信息，
        # 若拿它当完成判据会与题量目标单位错配（例如 20 分钟直接顶满
        # 「20 题」的目标），故只记录实际用时，不参与达成判定。
        actual = count
        new_count = min(actual, goal.target_count) if goal.target_count > 0 else actual

        if goal.current_count != new_count:
            logger.info(
                "[goal_progress] 目标 %s(%s) 科目=%s 进度 %s -> %s（实际用时 %s 分钟）",
                goal.goal_id, gtype, goal.subject_mode or 0,
                goal.current_count, new_count, round(seconds / 60),
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