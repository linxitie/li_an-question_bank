"""
个人目标完成度四维加权判定服务

四维：完成率(40%) + 质量分(25%) + 坚持分(20%) + 进步分(15%)，再乘难度系数(封顶3.0)。
- 完成率 = current_count / target_count
- 质量分 = 目标周期内正确率分档
- 坚持分 = 目标创建后连续学习天数分档
- 进步分 = (当前正确率 - 基线正确率) / 基线正确率，截断 [0,1]
- reward = max(base_reward × overall × difficulty, 10)  保底 10 币
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import func, Date
from sqlalchemy.orm import Session

from ..models.models import StudyGoal, SysUser, PracticeRecord

logger = logging.getLogger(__name__)

# 权重
W_COMPLETION = 0.40
W_QUALITY = 0.25
W_PERSISTENCE = 0.20
W_IMPROVEMENT = 0.15


def evaluate(goal: StudyGoal, user: SysUser, db: Session) -> dict:
    """计算四维加权完成度，返回各维分数与最终奖励（不写库、不 commit）。"""
    completion_rate = _completion_rate(goal)
    accuracy = _goal_accuracy(goal, user.user_id, db)
    quality_score = _quality_score(accuracy)
    persistence_score = _persistence_score(_consecutive_days(goal, user.user_id, db))
    improvement_score = _improvement_score(goal, accuracy)
    difficulty_factor = _difficulty_factor(goal)

    overall = (
        completion_rate * W_COMPLETION
        + quality_score * W_QUALITY
        + persistence_score * W_PERSISTENCE
        + improvement_score * W_IMPROVEMENT
    )

    base_reward = goal.base_reward if (goal.base_reward or 0) > 0 else 20
    reward = max(int(base_reward * overall * difficulty_factor), 10)

    return {
        "completion_rate": round(completion_rate, 4),
        "quality_score": quality_score,
        "persistence_score": persistence_score,
        "improvement_score": round(improvement_score, 4),
        "overall_completion": round(overall, 4),
        "difficulty_factor": difficulty_factor,
        "reward_coins": reward,
    }


# ------------------------- 四维计算 -------------------------

def _completion_rate(goal: StudyGoal) -> float:
    if not goal.target_count or goal.target_count <= 0:
        return 0.0
    return min(goal.current_count / goal.target_count, 1.0)


def _quality_score(accuracy: float) -> float:
    if accuracy >= 0.85:
        return 1.0
    if accuracy >= 0.70:
        return 0.7
    if accuracy >= 0.60:
        return 0.5
    return 0.3


def _persistence_score(days: int) -> float:
    if days >= 30:
        return 1.0
    if days >= 21:
        return 0.9
    if days >= 14:
        return 0.75
    if days >= 7:
        return 0.6
    if days >= 3:
        return 0.4
    return 0.2


def _improvement_score(goal: StudyGoal, accuracy: float) -> float:
    baseline = goal.baseline_accuracy if (goal.baseline_accuracy or 0) > 0 else 0.0
    if baseline <= 0:
        # 无基线（老目标），进步分按 0.5 中性处理
        return 0.5
    improvement = (accuracy - baseline) / baseline
    return min(max(improvement, 0.0), 1.0)


def _difficulty_factor(goal: StudyGoal) -> float:
    tv = goal.target_count or 0
    gt = (goal.goal_type or "DAILY").upper()
    if gt == "DAILY":
        factor = 1.0 + (tv / 100) * 0.5
    elif gt == "WEEKLY":
        factor = 1.0 + (tv / 500) * 0.5
    elif gt == "MONTHLY":
        factor = 1.0 + (tv / 2000) * 0.5
    else:  # CUSTOM
        factor = 1.2 + (tv / 100) * 0.3
    return min(round(factor, 2), 3.0)


# ------------------------- 统计辅助 -------------------------

def _goal_accuracy(goal: StudyGoal, user_id: int, db: Session) -> float:
    """目标创建后范围内的正确率"""
    start = goal.create_time or datetime.now()
    rows = db.query(PracticeRecord.is_correct).filter(
        PracticeRecord.user_id == user_id,
        PracticeRecord.practice_time >= start,
    ).all()
    total = len(rows)
    if total == 0:
        return 0.0
    correct = sum(1 for (c,) in rows if c == 1)
    return correct / total


def _consecutive_days(goal: StudyGoal, user_id: int, db: Session) -> int:
    """目标创建后的连续学习自然日天数"""
    start = goal.create_time or datetime.now()
    rows = db.query(func.DATE(PracticeRecord.practice_time)).filter(
        PracticeRecord.user_id == user_id,
        PracticeRecord.practice_time >= start,
    ).distinct().all()
    study_dates = {r[0] for r in rows if r[0]}

    today = datetime.now().date()
    day = today
    if day not in study_dates:
        day = day - timedelta(days=1)  # 允许今天尚未开始

    streak = 0
    while day in study_dates:
        streak += 1
        day = day - timedelta(days=1)
    return streak
