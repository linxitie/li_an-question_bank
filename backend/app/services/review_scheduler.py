"""艾宾浩斯复习排程（M3）

把「错题」变成「记忆卡片」，按记忆稳定度推算下次该复习的时间。

为什么不用固定的 1/2/4/7/15/30 天序列：
固定序列假设「所有题一样难」，但一道蒙对的资料分析和一个背反了的法条，
保持率衰减速度差一个数量级。所以这里用「难度 D → 初始稳定度 S0 → 按答题结果成长」的
可复算模型（方案 §4.3），固定序列只作为 UI 上的参考刻度。

三条硬约束（全部来自用户要求"可落地、有提醒效果"）：
  1) 复习强度随考试日收缩——越接近笔试，越只复习高危题（§4.4）；
  2) 单日有配额上限——排不完就顺延，疲劳复习等于无效复习；
  3) 提醒分层且可关——逾期 3 天升级，连续 3 天不做降级为"先做 10 题找回节奏"。
"""

from __future__ import annotations

import datetime as dt
import logging
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.models import (
    KnowledgePoint,
    PracticeRecord,
    QuestionBank,
    ReviewLog,
    ReviewSchedule,
    SubCategory,
    UserNotification,
    WrongQuestionPersonal,
)

logger = logging.getLogger(__name__)

# 科目修正系数：信息量越大保持越差 → 间隔越短（方案 §4.3 ④）
SUBJECT_FACTOR: Dict[int, float] = {1: 1.00, 2: 0.75, 3: 0.90}
# 科目权重：由题量 × 分值混合估得（方案 §4.3 ⑦）
SUBJECT_WEIGHT: Dict[int, float] = {1: 0.45, 2: 0.20, 3: 0.35}
# 考纲权重 w_topic（按子科目名匹配，匹配不到取 0.5 中位值）
TOPIC_WEIGHT: Dict[str, float] = {
    "知觉速度与准确性": 0.10,
    "言语理解与表达": 0.20,
    "判断推理": 0.25,
    "资料分析": 0.20,
    "数量关系": 0.10,
    "常识判断": 0.15,
    "政治理论": 0.15,
    "科学推理": 0.10,
    "职业素养": 0.20,
    "基础知识": 0.45,
    "基本警务能力": 0.35,
    "归纳概括": 0.30,
    "综合分析": 0.25,
    "提出对策": 0.20,
    "应用文写作": 0.20,
    "议论文写作": 0.25,
}
DEFAULT_TOPIC_WEIGHT = 0.50
# 每种题型的基础答题时长（秒）：用于算"用时比"，申论主观题远慢于客观题
BASE_SECONDS: Dict[int, int] = {1: 60, 2: 90, 3: 120, 4: 90, 5: 60, 14: 150, 15: 90, 19: 240}
DEFAULT_BASE_SECONDS = 75
# 复习参考刻度（仅用于 UI 展示"第 N 次复习"，真实间隔以公式为准）
REFERENCE_INTERVALS = (1, 2, 4, 7, 15, 30, 60, 90)


# ==================== 时间与考情 ====================


def exam_date() -> dt.date:
    try:
        return dt.date.fromisoformat(settings.EXAM_DATE)
    except (TypeError, ValueError):
        logger.warning("EXAM_DATE 配置无法解析: %s，回退 2027-01-02", settings.EXAM_DATE)
        return dt.date(2027, 1, 2)


def days_until_exam(today: Optional[dt.date] = None) -> int:
    today = today or dt.date.today()
    return (exam_date() - today).days


def phase_of(days_left: int) -> Dict[str, Any]:
    """考试日锚定的阶段策略（方案 §4.4）"""
    if days_left <= 0:
        return {"key": "after", "name": "考后", "quota_ratio": 0.0, "min_priority": 1.1, "note": "队列归档"}
    if days_left <= 7:
        return {
            "key": "sprint",
            "name": "冲刺期",
            "quota_ratio": 1.0,
            "min_priority": 0.0,
            "note": "只排高危题（lapses≥2 或 D≥0.6），每日 ≤20 题",
        }
    if days_left <= 14:
        return {"key": "mock", "name": "模拟期", "quota_ratio": 0.3, "min_priority": 0.0, "note": "复习量降到 30%，让位全真模拟"}
    if days_left <= 30:
        return {"key": "converge", "name": "收敛期", "quota_ratio": 1.0, "min_priority": 0.5, "note": "只排优先级 ≥0.5 的题"}
    if days_left <= 60:
        return {"key": "build", "name": "强化期", "quota_ratio": 1.0, "min_priority": 0.3, "note": "已牢固（P<0.3）的题暂停"}
    return {"key": "normal", "name": "常态期", "quota_ratio": 1.0, "min_priority": 0.0, "note": "全量复习 + 新增练习"}


# ==================== 记忆模型 ====================


def compute_difficulty(accuracy: Optional[float], level: Optional[int], time_ratio: Optional[float]) -> float:
    """D = 0.45*(1-acc) + 0.35*lvl + 0.20*tr，全部裁剪到 [0,1]"""
    acc = 0.5 if accuracy is None else max(0.0, min(1.0, accuracy))
    lvl = max(0.0, min(1.0, ((level or 3) - 1) / 4.0))
    tr = 0.5 if time_ratio is None else max(0.0, min(1.0, time_ratio))
    return round(0.45 * (1 - acc) + 0.35 * lvl + 0.20 * tr, 4)


def initial_stability(difficulty: float) -> float:
    """S0 = 2.2*(1-0.6*D)：D=0 → 2.2 天，D=1 → 0.88 天"""
    return round(2.2 * (1 - 0.6 * difficulty), 4)


def grow_stability(stability: float, difficulty: float, correct: bool) -> float:
    if correct:
        return round(stability * (1.5 + 0.9 * (1 - difficulty)), 4)
    return round(max(0.6, stability * 0.35), 4)


def interval_days(stability: float, subject_id: Optional[int], days_left: Optional[int] = None) -> int:
    """I = clamp(round(S*f), 1, days_until_exam-1)"""
    factor = SUBJECT_FACTOR.get(subject_id or 0, 1.0)
    raw = int(round(stability * factor))
    upper = 90 if days_left is None else max(1, days_left - 1)
    return max(1, min(raw, upper))


def retention(stability: float, last_review_at: Optional[dt.datetime], now: Optional[dt.datetime] = None) -> float:
    """R(t) = exp(-Δ/S)"""
    if not stability or stability <= 0:
        return 0.0
    now = now or dt.datetime.now()
    if not last_review_at:
        return 0.0
    delta_days = max(0.0, (now - last_review_at).total_seconds() / 86400.0)
    return round(math.exp(-delta_days / stability), 4)


def priority(retain: float, subject_id: Optional[int], lapses: int, topic_weight: float) -> float:
    """P = (1-R) * W_subject * (1+0.5*lapses) * w_topic"""
    w_subject = SUBJECT_WEIGHT.get(subject_id or 0, 0.3)
    return round(max(0.0, 1 - retain) * w_subject * (1 + 0.5 * lapses) * topic_weight, 4)


# ==================== 数据准备 ====================


def _history_stats(db: Session, user_id: int, question_ids: Sequence[int]) -> Dict[int, Dict[str, Any]]:
    """一次查出这批题的历史正确率与平均用时（避免逐题 N+1）"""
    if not question_ids:
        return {}
    rows = (
        db.query(
            PracticeRecord.question_id,
            func.count(PracticeRecord.record_id),
            func.sum(PracticeRecord.is_correct),
            func.avg(PracticeRecord.time_spent),
        )
        .filter(PracticeRecord.user_id == user_id, PracticeRecord.question_id.in_(list(question_ids)))
        .group_by(PracticeRecord.question_id)
        .all()
    )
    out: Dict[int, Dict[str, Any]] = {}
    for qid, total, correct, avg_time in rows:
        out[qid] = {
            "total": int(total or 0),
            "accuracy": (float(correct or 0) / total) if total else None,
            "avg_seconds": float(avg_time) if avg_time else None,
        }
    return out


def _topic_weight_map(db: Session) -> Dict[int, str]:
    """sub_category_id → 子科目名（用于查考纲权重）"""
    rows = db.query(SubCategory.id, SubCategory.name).all()
    return {int(r[0]): (r[1] or "") for r in rows}


def _time_ratio(avg_seconds: Optional[float], type_id: Optional[int]) -> Optional[float]:
    if not avg_seconds:
        return None
    base = BASE_SECONDS.get(type_id or 0, DEFAULT_BASE_SECONDS)
    return min(1.0, avg_seconds / float(base))


def _build_row(
    db: Session,
    user_id: int,
    question: QuestionBank,
    stats: Dict[int, Dict[str, Any]],
    topic_names: Dict[int, str],
    now: dt.datetime,
) -> ReviewSchedule:
    s = stats.get(question.question_id, {})
    difficulty = compute_difficulty(
        s.get("accuracy"),
        question.difficulty,
        _time_ratio(s.get("avg_seconds"), question.type_id),
    )
    stability = initial_stability(difficulty)
    return ReviewSchedule(
        user_id=user_id,
        question_id=question.question_id,
        subject_id=question.subject_id,
        point_id=question.point_id,
        stability=stability,
        difficulty=difficulty,
        reps=0,
        lapses=0,
        last_review_at=None,
        next_due_at=now,  # 冷启动全部进首日队列，配额之外的顺延（见 due）
        last_result=None,
        rescue_mode=0,
        create_time=now,
        update_time=now,
    )


def collect_review_question_ids(db: Session, user_id: int) -> List[int]:
    """复习单元 = 错题 ∪ 历史错答过的题（方案 §4.2/§4.8）"""
    wrong_ids = [
        int(r[0])
        for r in db.query(WrongQuestionPersonal.question_id)
        .filter(WrongQuestionPersonal.user_id == user_id, WrongQuestionPersonal.status == 1)
        .all()
    ]
    failed_ids = [
        int(r[0])
        for r in db.query(PracticeRecord.question_id)
        .filter(PracticeRecord.user_id == user_id, PracticeRecord.is_correct == 0)
        .distinct()
        .all()
    ]
    return sorted(set(wrong_ids) | set(failed_ids))


def rebuild(db: Session, user_id: int, limit: Optional[int] = None) -> Dict[str, Any]:
    """冷启动/补建排程（幂等）：只为缺排程的题建行，已存在的不动"""
    ids = collect_review_question_ids(db, user_id)
    if limit:
        ids = ids[:limit]
    if not ids:
        return {"created": 0, "skipped": 0, "total": 0}
    existing = {
        int(r[0])
        for r in db.query(ReviewSchedule.question_id)
        .filter(ReviewSchedule.user_id == user_id, ReviewSchedule.question_id.in_(ids))
        .all()
    }
    missing = [qid for qid in ids if qid not in existing]
    if not missing:
        return {"created": 0, "skipped": len(ids), "total": len(ids)}

    questions = db.query(QuestionBank).filter(QuestionBank.question_id.in_(missing)).all()
    stats = _history_stats(db, user_id, [q.question_id for q in questions])
    topic_names = _topic_weight_map(db)
    now = dt.datetime.now()
    for q in questions:
        db.add(_build_row(db, user_id, q, stats, topic_names, now))
    db.commit()
    logger.info("复习排程补建: user=%s created=%s", user_id, len(questions))
    return {"created": len(questions), "skipped": len(ids) - len(missing), "total": len(ids)}


# ==================== 今日队列 ====================


def _quota(db: Session, user_id: int) -> int:
    """每日配额：有可用时长就按 60 分钟折算，否则取配置上限（10–60 题）"""
    cap = max(10, min(60, int(settings.REVIEW_DAILY_MAX or 60)))
    return cap


def due(
    db: Session,
    user_id: int,
    limit: int = 20,
    subject_id: Optional[int] = None,
    mode: str = "today",
) -> Dict[str, Any]:
    """今日待复习：按优先级 P 排序，带保持率 R 与材料标记"""
    now = dt.datetime.now()
    days_left = days_until_exam()
    phase = phase_of(days_left)
    if phase["key"] == "after":
        return {"items": [], "total": 0, "phase": phase, "days_left": days_left, "quota": 0, "note": phase["note"]}

    q = (
        db.query(ReviewSchedule, QuestionBank)
        .join(QuestionBank, QuestionBank.question_id == ReviewSchedule.question_id)
        .filter(ReviewSchedule.user_id == user_id)
    )
    if subject_id:
        q = q.filter(ReviewSchedule.subject_id == subject_id)
    rows = q.all()

    topic_names = _topic_weight_map(db)
    scored: List[Tuple[float, ReviewSchedule, QuestionBank, float]] = []
    for schedule, question in rows:
        retain = retention(schedule.stability, schedule.last_review_at, now)
        w_topic = TOPIC_WEIGHT.get(topic_names.get(question.sub_category_id or 0, ""), DEFAULT_TOPIC_WEIGHT)
        score = priority(retain, schedule.subject_id, schedule.lapses, w_topic)
        scored.append((score, schedule, question, retain))

    overdue = [s for _, s, _, _ in scored if s.next_due_at and s.next_due_at <= now]
    # 阶段过滤。
    # 注意：从未复习过（last_review_at 为空）的题必须放行——它们是冷启动队列，
    # 保持率还没开始衰减，用 min_priority 卡它们会让新用户永远看不到今日队列。
    never_reviewed = lambda s: s.last_review_at is None  # noqa: E731
    if phase["key"] == "sprint":
        scored = [
            (p, s, qq, r) for p, s, qq, r in scored
            if never_reviewed(s) or s.lapses >= 2 or s.difficulty >= 0.6
        ]
    elif phase["key"] in ("converge", "build"):
        scored = [
            (p, s, qq, r) for p, s, qq, r in scored
            if never_reviewed(s) or p >= phase["min_priority"]
        ]

    scored.sort(key=lambda item: (-item[0], item[1].next_due_at or now))
    quota = _quota(db, user_id)
    if phase["key"] == "mock":
        quota = max(5, int(round(quota * phase["quota_ratio"])))
    if phase["key"] == "sprint":
        quota = min(quota, 20)
    effective = max(1, min(limit or quota, quota))

    picked = scored[:effective]
    items = []
    for score, schedule, question, retain in picked:
        items.append({
            "question_id": question.question_id,
            "subject_id": question.subject_id,
            "question_type": question.type_id,
            "point_id": question.point_id,
            "point_name": _point_name(db, question.point_id),
            "group_id": question.group_id,
            "has_material": bool(question.group_id),
            "difficulty": schedule.difficulty,
            "stability": schedule.stability,
            "retention": retain,
            "priority": score,
            "reps": schedule.reps,
            "lapses": schedule.lapses,
            "next_due_at": schedule.next_due_at.isoformat() if schedule.next_due_at else None,
            "overdue_days": max(0, (now - schedule.next_due_at).days) if schedule.next_due_at else 0,
            "rescue_mode": bool(schedule.rescue_mode),
        })

    overdue_max = max([it["overdue_days"] for it in items], default=0)
    note = phase["note"]
    if overdue_max >= 3:
        note += "；有题已逾期 " + str(overdue_max) + " 天"
    return {
        "items": items,
        "total": len(scored),
        "due_now": len(overdue),
        "phase": phase,
        "days_left": days_left,
        "quota": quota,
        "overdue_level": 2 if overdue_max >= 3 else (1 if overdue_max >= 1 else 0),
        "note": note,
    }


def _point_name(db: Session, point_id: Optional[int]) -> Optional[str]:
    if not point_id:
        return None
    row = db.query(KnowledgePoint.point_name).filter(KnowledgePoint.point_id == point_id).first()
    return row[0] if row else None


# ==================== 作答与更新 ====================


def grade(db: Session, user_id: int, question_id: int, result: int, elapsed_ms: Optional[int] = None) -> Dict[str, Any]:
    """提交一次复习结果，返回新间隔与下次到期"""
    schedule = (
        db.query(ReviewSchedule)
        .filter(ReviewSchedule.user_id == user_id, ReviewSchedule.question_id == question_id)
        .first()
    )
    if not schedule:
        question = db.query(QuestionBank).filter(QuestionBank.question_id == question_id).first()
        if not question:
            raise ValueError("题目不存在: " + str(question_id))
        stats = _history_stats(db, user_id, [question_id])
        schedule = _build_row(db, user_id, question, stats, _topic_weight_map(db), dt.datetime.now())
        db.add(schedule)
        db.flush()

    correct = 1 if int(result) == 1 else 0
    before = float(schedule.stability or 2.2)
    after = grow_stability(before, float(schedule.difficulty or 0.5), bool(correct))
    days_left = days_until_exam()
    interval = 1 if not correct else interval_days(after, schedule.subject_id, days_left)
    now = dt.datetime.now()

    schedule.stability = after
    schedule.reps = int(schedule.reps or 0) + (1 if correct else 0)
    schedule.lapses = int(schedule.lapses or 0) + (0 if correct else 1)
    schedule.last_review_at = now
    schedule.next_due_at = now + dt.timedelta(days=interval)
    schedule.last_result = correct
    schedule.rescue_mode = 0
    schedule.update_time = now
    db.add(ReviewLog(
        user_id=user_id,
        question_id=question_id,
        result=correct,
        elapsed_ms=elapsed_ms,
        stability_before=before,
        stability_after=after,
        interval_days=interval,
        reviewed_at=now,
    ))
    db.commit()
    rep_index = min(len(REFERENCE_INTERVALS) - 1, int(schedule.reps or 0))
    return {
        "question_id": question_id,
        "result": correct,
        "stability": after,
        "interval_days": interval,
        "next_due_at": schedule.next_due_at.isoformat(),
        "reps": schedule.reps,
        "lapses": schedule.lapses,
        "reference_interval": REFERENCE_INTERVALS[rep_index],
    }


# ==================== 统计与日历 ====================


def stats(db: Session, user_id: int, days: int = 30) -> Dict[str, Any]:
    since = dt.datetime.now() - dt.timedelta(days=days)
    logs = (
        db.query(ReviewLog)
        .filter(ReviewLog.user_id == user_id, ReviewLog.reviewed_at >= since)
        .all()
    )
    total = len(logs)
    correct = sum(1 for r in logs if r.result == 1)
    schedules = db.query(ReviewSchedule).filter(ReviewSchedule.user_id == user_id).all()
    now = dt.datetime.now()
    retains = [retention(s.stability, s.last_review_at, now) for s in schedules if s.last_review_at]
    overdue = sum(1 for s in schedules if s.next_due_at and s.next_due_at <= now)
    return {
        "days": days,
        "reviewed": total,
        "correct_rate": round(correct * 100.0 / total, 1) if total else 0.0,
        "avg_retention": round(sum(retains) / len(retains), 3) if retains else 0.0,
        "tracked": len(schedules),
        "overdue": overdue,
        "phase": phase_of(days_until_exam()),
        "days_left": days_until_exam(),
    }


def calendar(db: Session, user_id: int, month: str = "") -> Dict[str, Any]:
    """学习日历用：本月每日复习量与考试节点"""
    if month:
        try:
            first = dt.date.fromisoformat(month + "-01")
        except ValueError:
            first = dt.date.today().replace(day=1)
    else:
        first = dt.date.today().replace(day=1)
    if first.month == 12:
        nxt = first.replace(year=first.year + 1, month=1)
    else:
        nxt = first.replace(month=first.month + 1)

    logs = (
        db.query(ReviewLog.reviewed_at)
        .filter(
            ReviewLog.user_id == user_id,
            ReviewLog.reviewed_at >= dt.datetime.combine(first, dt.time.min),
            ReviewLog.reviewed_at < dt.datetime.combine(nxt, dt.time.min),
        )
        .all()
    )
    done: Dict[str, int] = {}
    for (ts,) in logs:
        key = ts.date().isoformat()
        done[key] = done.get(key, 0) + 1

    schedules = db.query(ReviewSchedule).filter(ReviewSchedule.user_id == user_id).all()
    due_map: Dict[str, int] = {}
    for s in schedules:
        if s.next_due_at and first <= s.next_due_at.date() < nxt:
            key = s.next_due_at.date().isoformat()
            due_map[key] = due_map.get(key, 0) + 1

    return {
        "month": first.strftime("%Y-%m"),
        "done": done,
        "due": due_map,
        "exam_date": exam_date().isoformat(),
        "days_left": days_until_exam(),
    }


# ==================== 提醒 ====================


def remind(db: Session, user_id: int) -> Dict[str, Any]:
    """给单个用户发站内复习提醒（幂等：当天同类型只发一条）"""
    if not settings.REVIEW_REMINDER_ENABLED:
        return {"sent": False, "reason": "disabled"}
    now = dt.datetime.now()
    today_start = dt.datetime.combine(now.date(), dt.time.min)
    exists = (
        db.query(UserNotification)
        .filter(
            UserNotification.user_id == user_id,
            UserNotification.type == "review_due",
            UserNotification.created_at >= today_start,
        )
        .first()
    )
    if exists:
        return {"sent": False, "reason": "already_sent"}

    payload = due(db, user_id, limit=1, mode="today")
    count = payload.get("due_now") or 0
    if not count:
        return {"sent": False, "reason": "nothing_due"}
    level = payload.get("overdue_level") or 0
    title = "今天有 " + str(count) + " 道错题该复习了"
    content = payload.get("note") or ""
    if level >= 2:
        title = "复习已逾期：" + str(count) + " 道错题在等你"
    db.add(UserNotification(
        user_id=user_id,
        type="review_due",
        title=title,
        content=content,
        link="#/wrong-questions?tab=review",
        related_type="review",
    ))
    db.commit()

    # 站内信之外再走短信（默认关闭；开启后受每日配额约束）。旁路失败不影响站内信。
    sms_result: Dict[str, Any] = {"sent": False, "reason": "skipped"}
    try:
        from .notify import sms_adapter
        from ..models.models import SysUser

        user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
        sms_result = sms_adapter.send(
            getattr(user, "phone", None) if user else None,
            title,
            "打开砺安题库 → 错题集 → 错题复习，按顺序过一遍即可。",
            user_id=user_id,
        )
    except Exception as e:  # noqa: BLE001 - 短信是旁路，不影响站内信
        logger.warning("复习短信提醒失败 user=%s: %s", user_id, e)

    return {"sent": True, "count": count, "overdue_level": level, "sms": sms_result}


def remind_all(db: Session) -> Dict[str, Any]:
    """定时任务入口：给所有有排程的用户发提醒"""
    user_ids = [int(r[0]) for r in db.query(ReviewSchedule.user_id).distinct().all()]
    sent = 0
    for uid in user_ids:
        try:
            if remind(db, uid).get("sent"):
                sent += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("复习提醒失败 user=%s: %s", uid, e)
    return {"users": len(user_ids), "sent": sent}
