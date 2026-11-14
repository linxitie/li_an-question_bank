"""联考小智 - 离线教练（M6）

大模型不可用（未配置密钥 / 超时 / 上游故障）时，联考小智仍需可用。
这里只做两件事，且刻意不做第三件：
  1) 有本地数据 → 用真实统计拼出可执行回答；
  2) 无数据 → 明确说"还没有练习记录"，并给出下一步动作；
  3) 不生成、不编造题目解析——那是大模型的职责，离线模式下必须明说"这一条需要联网 AI"。

为什么不直接返回上游错误：用户看到"大模型返回错误（401）"只会以为系统坏了，
而实际上他能练的题、能看的薄弱点全在本地库里。
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.models import (
    DailyCheckin,
    KnowledgePoint,
    PracticeRecord,
    QuestionBank,
    WrongQuestionPersonal,
)

logger = logging.getLogger(__name__)

# 固定问题池：离线模式下前端直接渲染这 4 个按钮，点击由 /api/llm/offline/answer 作答。
# 选这 4 个的理由：全部能用本地数据回答，不依赖大模型生成。
OFFLINE_QUESTIONS: List[Dict[str, str]] = [
    {"key": "weak_points", "label": "我的薄弱考点是什么"},
    {"key": "plan_today", "label": "今天该练什么"},
    {"key": "progress", "label": "我最近的练习情况"},
    {"key": "exam_info", "label": "考试时间与科目安排"},
]

SUBJECT_NAMES = {1: "行测", 2: "申论", 3: "公安专业科目"}

# 公安联考考情（官方大纲口径，方案 §4.1 已标注置信度）
EXAM_INFO_TEXT = (
    "公安联考笔试三科：\n"
    "• 行测：120 分钟，约 180 题（客观题）\n"
    "• 申论：150 分钟，主观题\n"
    "• 公安专业科目：120 分钟，100 分\n"
    "笔试时间一般安排在次年 1 月的第一个周末；具体日期以当年公告为准。"
)


def _stats(db: Session, user_id: int, days: int) -> Dict[str, Any]:
    """近 N 天的练习统计（按 practice_date 聚合，缺失时按 practice_time 兜底）"""
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    rows = (
        db.query(PracticeRecord.subject_id, PracticeRecord.is_correct)
        .filter(PracticeRecord.user_id == user_id)
        .filter(PracticeRecord.practice_date >= since)
        .all()
    )
    total = len(rows)
    correct = sum(1 for r in rows if r[1])
    by_subject: Dict[int, int] = {}
    for r in rows:
        if r[0]:
            by_subject[r[0]] = by_subject.get(r[0], 0) + 1
    return {
        "days": days,
        "total": total,
        "correct": correct,
        "accuracy": round(correct * 100.0 / total, 1) if total else 0.0,
        "by_subject": by_subject,
    }


# 「其他（未细分）」是收容桶，不是可复习的考点：拿它当"最薄弱考点"会让用户无法行动。
FALLBACK_NAME_PREFIXES = ("其他", "未分类")


def _is_fallback_name(name: str) -> bool:
    return bool(name) and name.startswith(FALLBACK_NAME_PREFIXES)


def _weak_points(db: Session, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """薄弱考点：错题最多的具体考点（排除「其他（未细分）」收容桶）"""
    rows = (
        db.query(KnowledgePoint.point_name, func.count(WrongQuestionPersonal.wrong_id))
        .join(QuestionBank, QuestionBank.question_id == WrongQuestionPersonal.question_id)
        .join(KnowledgePoint, KnowledgePoint.point_id == QuestionBank.point_id)
        .filter(WrongQuestionPersonal.user_id == user_id)
        .filter(WrongQuestionPersonal.status == 1)
        .group_by(KnowledgePoint.point_name)
        .order_by(func.count(WrongQuestionPersonal.wrong_id).desc())
        .limit(limit + 20)  # 多取一些，剔除收容桶后仍能凑满 limit
        .all()
    )
    out = [
        {"point_name": r[0], "count": r[1]}
        for r in rows
        if r[0] and not _is_fallback_name(r[0])
    ]
    return out[:limit]


def _fallback_wrong(db: Session, user_id: int) -> int:
    """错在「其他（未细分）」桶里的题数：用于说明"这些题还没细分到考点"，而不是当成考点推荐"""
    rows = (
        db.query(func.count(WrongQuestionPersonal.wrong_id))
        .join(QuestionBank, QuestionBank.question_id == WrongQuestionPersonal.question_id)
        .join(KnowledgePoint, KnowledgePoint.point_id == QuestionBank.point_id)
        .filter(WrongQuestionPersonal.user_id == user_id)
        .filter(WrongQuestionPersonal.status == 1)
        .filter(KnowledgePoint.point_name.like("其他%"))
        .scalar()
    )
    return int(rows or 0)


def _wrong_total(db: Session, user_id: int) -> int:
    return (
        db.query(func.count(WrongQuestionPersonal.wrong_id))
        .filter(WrongQuestionPersonal.user_id == user_id)
        .filter(WrongQuestionPersonal.status == 1)
        .scalar()
        or 0
    )


def _streak(db: Session, user_id: int) -> int:
    row = (
        db.query(DailyCheckin.continuous_days)
        .filter(DailyCheckin.user_id == user_id)
        .order_by(DailyCheckin.checkin_date.desc())
        .first()
    )
    return int(row[0] or 0) if row else 0


def _fmt_subject_mix(by_subject: Dict[int, int]) -> str:
    if not by_subject:
        return ""
    parts = [
        SUBJECT_NAMES.get(sid, "科目" + str(sid)) + " " + str(n) + " 题"
        for sid, n in sorted(by_subject.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return "、".join(parts)


def answer(db: Session, user_id: int, key: str, message: str = "") -> Dict[str, Any]:
    """按固定问题 key 生成离线回答（全部基于本地数据，不调用大模型）"""
    key = (key or "").strip()
    if key == "exam_info":
        return {"reply": EXAM_INFO_TEXT, "key": key}

    if key == "weak_points":
        points = _weak_points(db, user_id)
        wrong = _wrong_total(db, user_id)
        if not wrong:
            reply = (
                "你在本系统还没有错题记录，所以暂时算不出薄弱考点。\n"
                "建议：先去「快速练习」做 1 组 20 题，交卷后错题会自动进错题集，"
                "下次再问我就能给出具体的薄弱点排名。"
            )
        else:
            lines = [
                "按错题数量排序，你当前最需要补的考点是：",
            ]
            for i, p in enumerate(points, 1):
                lines.append(str(i) + ". " + p["point_name"] + "（错 " + str(p["count"]) + " 题）")
            extra = _fallback_wrong(db, user_id)
            if extra:
                lines.append(
                    "另有 " + str(extra) + " 道错题归在「其他（未细分）」里 —— "
                    "这部分题目还没细分到具体考点，所以不作为薄弱点推荐；"
                    "可以先去「错题集」逐题看解析。"
                )
            lines.append("")
            lines.append("建议先在「错题集」按考点筛出这几组，逐题看解析，再用同考点练习验证。")
            reply = "\n".join(lines)
        return {"reply": reply, "key": key, "data": {"wrong_total": wrong, "points": points}}

    if key == "plan_today":
        s7 = _stats(db, user_id, 7)
        s30 = _stats(db, user_id, 30)
        if s7["total"] == 0:
            reply = (
                "最近 7 天还没有练习记录。今天可以先从这里开始：\n"
                "1. 「快速练习」任选一个子科目做 20 题（约 15 分钟）；\n"
                "2. 交卷后把错的题看一遍解析，错题会自动进入错题集；\n"
                "3. 做完回来再问我一次，我会按你的实际数据安排后面几天。"
            )
        else:
            weak = _weak_points(db, user_id, 3)
            lines = [
                "根据你最近 7 天的数据（" + str(s7["total"]) + " 题，正确率 " + str(s7["accuracy"]) + "%）：",
                "• 今天先补薄弱考点：" + ("、".join(w["point_name"] for w in weak) if weak else "暂无（错题为空）"),
                "• 题量建议：20–30 题，限时 30 分钟，做完立即复盘；",
                "• 科目分配：" + (_fmt_subject_mix(s30["by_subject"]) or "无历史分布，建议行测为主"),
            ]
            reply = "\n".join(lines)
        return {"reply": reply, "key": key, "data": {"last7": s7, "last30": s30}}

    if key == "progress":
        s7 = _stats(db, user_id, 7)
        s30 = _stats(db, user_id, 30)
        streak = _streak(db, user_id)
        wrong = _wrong_total(db, user_id)
        reply = "\n".join([
            "最近 7 天：" + str(s7["total"]) + " 题，正确率 " + str(s7["accuracy"]) + "%",
            "最近 30 天：" + str(s30["total"]) + " 题，正确率 " + str(s30["accuracy"]) + "%",
            "科目分布（30 天）：" + (_fmt_subject_mix(s30["by_subject"]) or "暂无"),
            "连续打卡：" + str(streak) + " 天",
            "待复习错题：" + str(wrong) + " 题",
        ])
        return {"reply": reply, "key": key, "data": {"last7": s7, "last30": s30, "streak": streak}}

    # 自由提问：离线不编造答案，只给可执行的替代路径
    text = (message or "").strip()
    reply = (
        "AI 答疑当前不可用（未配置或暂时连不上大模型），这一条我没法回答。\n"
        "但下面这些不需要 AI 也能马上做："
    )
    if text:
        reply = "你问的是「" + text[:40] + "」。\n" + reply
    reply += (
        "\n1. 点上面的「我的薄弱考点」「今天该练什么」，我用本地数据给你算；"
        "\n2. 去「错题集」按考点筛题，看解析；"
        "\n3. 去「快速练习」直接做题。"
    )
    return {"reply": reply, "key": "fallback", "data": {}}


def build_answer(db: Session, user_id: int, question_key: str, message: str = "") -> Dict[str, Any]:
    """对外入口：任何异常都降级成一句可读提示，绝不把堆栈抛给前端"""
    try:
        return answer(db, user_id, question_key, message)
    except Exception as e:  # noqa: BLE001
        logger.warning("离线教练回答生成失败: %s", e)
        return {
            "reply": "离线教练暂时取不到你的练习数据，请稍后重试，或直接去「快速练习」做题。",
            "key": question_key or "fallback",
            "data": {},
        }
