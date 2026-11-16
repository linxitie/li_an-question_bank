"""做题习惯画像（2026-11-05 M3.5）。

M3 用的是"习惯的知识维度"（哪些知识点反复出错/正在生长）。
本模块补"非知识维度"：时段偏好、学科偏好、单次时长、节奏稳定性，
并把它变成采样温度 T 的调制项——习惯稳定 → 温度低（更"锐"、更聚焦）；
习惯波动大 → 温度高（更"散"、多探索）。

为什么用温度调制而不是直接加权节点：
- 直接加权会和 M3 的 heat/growth 打分重复计权，容易把分布压成一条线；
- 温度只改变分布的"陡峭度"，语义上对应"这个人本周的学习节奏有多稳定"，
  与知识维度的打分正交，可解释性更好。
"""
from __future__ import annotations

import logging
import statistics
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.models import PracticeRecord

logger = logging.getLogger(__name__)

# 时段划分（按 practice_time 的小时）
TIME_SLOTS = {
    "morning": (5, 12),     # 05:00–11:59
    "afternoon": (12, 18),  # 12:00–17:59
    "evening": (18, 23),    # 18:00–22:59
    "night": (23, 5),       # 23:00–04:59
}
# 采样温度范围与默认值
BASE_TEMPERATURE = 0.8
MIN_TEMPERATURE = 0.45
MAX_TEMPERATURE = 1.25


def _slot_of(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 23:
        return "evening"
    return "night"


def build_habit_profile(db: Session, user_id: int, days: int = 30) -> dict:
    """聚合近 N 天的做题习惯。

    数据源：practice_record（practice_time / time_spent / subject_id）。
    返回结构直接给前端展示 + 给 temperature_for 用。
    """
    since = datetime.now() - timedelta(days=days)
    rows = (
        db.query(
            PracticeRecord.practice_time,
            PracticeRecord.time_spent,
            PracticeRecord.subject_id,
        )
        .filter(
            PracticeRecord.user_id == user_id,
            PracticeRecord.practice_time >= since,
        )
        .all()
    )

    if not rows:
        return {
            "window_days": days,
            "total_records": 0,
            "preferred_slot": None,
            "slot_distribution": {},
            "preferred_subject": None,
            "subject_distribution": {},
            "avg_time_spent": 0.0,
            "median_time_spent": 0.0,
            "active_days": 0,
            "stability": 0.0,
            "temperature": BASE_TEMPERATURE,
            "habit_summary": "数据不足，先用默认节奏",
        }

    slot_counts: dict[str, int] = {k: 0 for k in TIME_SLOTS}
    subject_counts: dict[int, int] = {}
    daily_counts: dict[str, int] = {}
    durations = []

    for practice_time, time_spent, subject_id in rows:
        if practice_time:
            slot = _slot_of(practice_time.hour)
            slot_counts[slot] += 1
            daily_counts[practice_time.date().isoformat()] = (
                daily_counts.get(practice_time.date().isoformat(), 0) + 1
            )
        # subject_id 历史上出现过脏值（如来源字符串），只接受可转成整数的值
        try:
            sid = int(subject_id) if subject_id is not None else None
        except (TypeError, ValueError):
            sid = None
        if sid is not None:
            subject_counts[sid] = subject_counts.get(sid, 0) + 1
        if time_spent:
            durations.append(int(time_spent))

    preferred_slot = max(slot_counts.items(), key=lambda kv: kv[1])[0] if any(slot_counts.values()) else None
    preferred_subject = (
        max(subject_counts.items(), key=lambda kv: kv[1])[0] if subject_counts else None
    )

    # 稳定性：日刷题量的离散程度（变异系数越小越稳定）
    counts = list(daily_counts.values())
    if len(counts) >= 2 and statistics.mean(counts) > 0:
        cv = statistics.pstdev(counts) / statistics.mean(counts)
        stability = round(max(0.0, 1.0 - min(1.0, cv)), 4)
    elif len(counts) == 1:
        stability = 0.5
    else:
        stability = 0.0

    avg_spent = round(statistics.mean(durations), 1) if durations else 0.0
    median_spent = round(statistics.median(durations), 1) if durations else 0.0

    return {
        "window_days": days,
        "total_records": len(rows),
        "preferred_slot": preferred_slot,
        "slot_distribution": slot_counts,
        "preferred_subject": preferred_subject,
        "subject_distribution": {str(k): v for k, v in subject_counts.items()},
        "avg_time_spent": avg_spent,
        "median_time_spent": median_spent,
        "active_days": len(daily_counts),
        "stability": stability,
        "temperature": temperature_for(stability, len(rows)),
        "habit_summary": _summary(preferred_slot, preferred_subject, stability, avg_spent),
    }


def temperature_for(stability: float, sample_size: int) -> float:
    """习惯稳定性 → 采样温度。

    - 稳定性高（节奏规律）→ 温度低（收敛到已知薄弱点，少探索）；
    - 稳定性低（忽早忽晚、时练时停）→ 温度高（多探索，避免只盯一个点）。
    样本量太少时向默认值回归。
    """
    confidence = min(1.0, sample_size / 50)  # 50 条以上认为画像可信
    target = MAX_TEMPERATURE - (MAX_TEMPERATURE - MIN_TEMPERATURE) * _clamp01(stability)
    value = BASE_TEMPERATURE * (1 - confidence) + target * confidence
    return round(max(MIN_TEMPERATURE, min(MAX_TEMPERATURE, value)), 3)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _summary(slot: Optional[str], subject: Optional[int], stability: float, avg_spent: float) -> str:
    slot_cn = {
        "morning": "上午",
        "afternoon": "下午",
        "evening": "晚上",
        "night": "深夜",
    }.get(slot or "", "不定")
    pace = "节奏稳定" if stability >= 0.6 else ("节奏波动较大" if stability < 0.35 else "节奏一般")
    return f"常在{slot_cn}刷题，{pace}，单次约 {avg_spent:.0f} 秒"


def prefer_subject_boost(db: Session, user_id: int, profile: dict, subject_id: int) -> float:
    """学科偏好加成：命中偏好学科时轻微提升采样分（不改变温度语义）。"""
    preferred = profile.get("preferred_subject")
    if not preferred or int(preferred) != int(subject_id):
        return 0.0
    share = 0.0
    dist = profile.get("subject_distribution") or {}
    total = sum(dist.values()) or 1
    share = dist.get(str(preferred), 0) / total
    return round(0.15 * share, 4)
