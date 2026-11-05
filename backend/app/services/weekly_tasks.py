"""周任务判定与置顶池（2026-11-05 M2）。

设计要点（对应《金币购体系_设计方案_v1》§3）：
1. 判定只在服务端算，数据源是 exam 域的答题事实（practice_record / exam_record /
   exam_answer_detail），growth 域不写答题数据；
2. 奖励 = 基础值 × 难度系数 × 稀缺系数，单任务封顶 500，单用户每周封顶 900；
3. 置顶是稀缺资源：全站每周 2–3 个，套 1.30/1.45/1.50 三档稀缺系数；
4. 状态机：未开始 → 进行中 → 待判定 → 已发放 / 已失效（+ 已回滚）。

为什么判定要单独成服务而不是写在接口里：
- 运营需要「重算」入口（换算法、补数据），接口里写死就没法重放；
- 判定规则会被单测逐条覆盖，独立函数更易测。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.models import ExamRecord, PracticeRecord, SysUser, Task, UserTaskProgress

logger = logging.getLogger(__name__)

# 周奖励上限（设计文档 §3.2）
WEEKLY_REWARD_CAP = 900
TASK_REWARD_CAP = 500
# 置顶槽位对应的稀缺系数（§3.4）
PINNED_SCARCITY = {1: Decimal("1.30"), 2: Decimal("1.45"), 3: Decimal("1.50")}


def week_key(d: Optional[date] = None) -> str:
    """ISO 周键，如 2026-W45。"""
    d = d or date.today()
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def week_range(d: Optional[date] = None) -> tuple[datetime, datetime]:
    """本周起止：周一 00:00 到下周一 00:00（左闭右开）。"""
    d = d or date.today()
    monday = d - timedelta(days=d.weekday())
    start = datetime.combine(monday, datetime.min.time())
    return start, start + timedelta(days=7)


# ----------------------------- 指标计算 -----------------------------

def _count_practice(user_id: int, start: datetime, end: datetime, db: Session) -> int:
    return (
        db.query(func.count(PracticeRecord.record_id))
        .filter(
            PracticeRecord.user_id == user_id,
            PracticeRecord.practice_time >= start,
            PracticeRecord.practice_time < end,
        )
        .scalar()
        or 0
    )


def _count_kg_node_questions(
    user_id: int, point_id: Optional[int], start: datetime, end: datetime, db: Session
) -> int:
    """个性化任务：本周在指定知识点上的答题数（exam_answer_detail.knowledge_point 为文本）。"""
    from ..models.models import ExamAnswerDetail, KnowledgePoint

    if not point_id:
        return 0
    point = db.query(KnowledgePoint).filter(KnowledgePoint.point_id == point_id).first()
    if not point:
        return 0
    return (
        db.query(func.count(ExamAnswerDetail.detail_id))
        .join(ExamRecord, ExamRecord.record_id == ExamAnswerDetail.record_id)
        .filter(
            ExamRecord.user_id == user_id,
            ExamAnswerDetail.knowledge_point == point.point_name,
            ExamAnswerDetail.create_time >= start,
            ExamAnswerDetail.create_time < end,
        )
        .scalar()
        or 0
    )


def _count_exam_papers(user_id: int, start: datetime, end: datetime, db: Session) -> int:    return (
        db.query(func.count(ExamRecord.record_id))
        .filter(
            ExamRecord.user_id == user_id,
            ExamRecord.is_completed == 1,
            ExamRecord.submit_time >= start,
            ExamRecord.submit_time < end,
        )
        .scalar()
        or 0
    )


def _active_days(user_id: int, start: datetime, end: datetime, db: Session) -> int:
    """本周有刷题记录的天数（去重）。"""
    rows = (
        db.query(PracticeRecord.practice_date)
        .filter(
            PracticeRecord.user_id == user_id,
            PracticeRecord.practice_time >= start,
            PracticeRecord.practice_time < end,
        )
        .distinct()
        .all()
    )
    return len({r[0] for r in rows})


def compute_metric(
    metric: str,
    user_id: int,
    db: Session,
    today: Optional[date] = None,
    param: Optional[int] = None,
) -> float:
    """周任务指标计算入口（全部按本周范围）。

    `param`：个性化任务的知识点 ID（metric = kg_node_questions 时使用）。
    """
    start, end = week_range(today)
    if metric == "kg_node_questions":
        return _count_kg_node_questions(user_id, param, start, end, db)

    if metric == "week_questions":
        return _count_practice(user_id, start, end, db)
    if metric == "week_exam_papers":
        return _count_exam_papers(user_id, start, end, db)
    if metric == "week_active_days":
        return _active_days(user_id, start, end, db)
    if metric == "week_accuracy":
        rows = (
            db.query(PracticeRecord.is_correct)
            .filter(
                PracticeRecord.user_id == user_id,
                PracticeRecord.practice_time >= start,
                PracticeRecord.practice_time < end,
            )
            .all()
        )
        if not rows:
            return 0.0
        correct = sum(1 for r in rows if r[0] == 1)
        return round(correct / len(rows) * 100, 1)
    if metric == "week_daily_practice_days":
        # 连续型：本周每天至少 10 题的天数（用于"连续 7 天每日一练"）
        rows = (
            db.query(PracticeRecord.practice_date, func.count(PracticeRecord.record_id))
            .filter(
                PracticeRecord.user_id == user_id,
                PracticeRecord.practice_time >= start,
                PracticeRecord.practice_time < end,
            )
            .group_by(PracticeRecord.practice_date)
            .all()
        )
        return sum(1 for _, cnt in rows if cnt >= 10)

    # 未知指标：返回 0，避免静默给出错误进度
    logger.warning("未知周任务指标 metric=%s", metric)
    return 0


# ----------------------------- 奖励计算 -----------------------------

def effective_reward(task: Task, scarcity: Optional[Decimal] = None) -> int:
    """奖励 = 基础值 × 难度系数 × 稀缺系数，单任务封顶 500。"""
    base = Decimal(task.reward_coins or 0)
    difficulty = Decimal(str(task.difficulty_factor or 1.0))
    factor = scarcity if scarcity is not None else Decimal(str(task.scarcity_factor or 1.0))
    value = int(round(base * difficulty * factor))
    return min(value, TASK_REWARD_CAP)


def weekly_claimed_total(user_id: int, db: Session, week: Optional[str] = None) -> int:
    """本周已领取的金币合计（用于 900 封顶）。"""
    week = week or week_key()
    rows = (
        db.query(UserTaskProgress, Task)
        .join(Task, Task.task_id == UserTaskProgress.task_id)
        .filter(
            UserTaskProgress.user_id == user_id,
            UserTaskProgress.period_key == week,
            UserTaskProgress.claimed == 1,
        )
        .all()
    )
    total = 0
    for _prog, task in rows:
        total += effective_reward(task)
    return total


def claimable_amount(task: Task, user_id: int, db: Session, scarcity: Optional[Decimal] = None) -> int:
    """本次可领金额（套用周上限）。"""
    remaining = max(0, WEEKLY_REWARD_CAP - weekly_claimed_total(user_id, db))
    return min(effective_reward(task, scarcity), remaining)


# ----------------------------- 置顶池 -----------------------------

def ensure_week_pool(db: Session, week: Optional[str] = None, pinned_count: int = 3) -> list:
    """确保本周池已生成：只从 `pin_eligible=1` 的周任务里挑置顶。

    幂等：同一周已存在合法池（置顶任务都是 pin_eligible）时直接返回；
    若历史池把不可置顶的旧任务选上了，则整池重建。
    """
    from ..models.models import WeeklyTaskPool

    week = week or week_key()
    existing = db.query(WeeklyTaskPool).filter(WeeklyTaskPool.week_key == week).all()

    if existing:
        pinned_rows = [r for r in existing if r.pinned_slot]
        # 管理员手动置顶优先：只要池里有 manual，就完全尊重现状，不做自动重建
        has_manual = any((r.source or "auto") == "manual" for r in pinned_rows)
        if has_manual:
            return existing
        if pinned_rows:
            pinned_ids = [r.task_id for r in pinned_rows]
            eligible = {
                t.task_id
                for t in db.query(Task)
                .filter(Task.task_id.in_(pinned_ids), Task.pin_eligible == 1)
                .all()
            }
            if all(tid in eligible for tid in pinned_ids):
                return existing
        # 池子不合法（旧任务占位）：重建
        db.query(WeeklyTaskPool).filter(WeeklyTaskPool.week_key == week).delete(synchronize_session=False)
        db.flush()

    tasks = (
        db.query(Task)
        .filter(Task.t_type == "weekly", Task.enabled == 1)
        .order_by(Task.sort_order.asc(), Task.task_id.asc())
        .all()
    )
    candidates = [t for t in tasks if (t.pin_eligible or 0) == 1]
    pinned = {t.task_id for t in candidates[:pinned_count]}

    for task in tasks:
        slot = 0
        if task.task_id in pinned:
            slot = candidates.index(task) + 1
        db.add(WeeklyTaskPool(week_key=week, task_id=task.task_id, pinned_slot=slot))
    db.commit()
    return db.query(WeeklyTaskPool).filter(WeeklyTaskPool.week_key == week).all()


def pinned_slots(db: Session, week: Optional[str] = None) -> dict[int, int]:
    """{task_id: pinned_slot}；无池时返回空（任务按普通展示）。"""
    from ..models.models import WeeklyTaskPool

    week = week or week_key()
    rows = db.query(WeeklyTaskPool).filter(WeeklyTaskPool.week_key == week).all()
    return {r.task_id: r.pinned_slot for r in rows}
