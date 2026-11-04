"""答题练习判分事务服务（E1 / E11 / E12）。

一次提交在同一事务内完成：判分 -> 写作答记录（PracticeRecord）->
写个人错题集（WrongQuestionPersonal）-> 提交。任一环节异常整体回滚。
行为事件与业务写同一事务（Outbox 默认开启）；关闭 Outbox 时在提交后发布，发布失败不回滚已落库数据。
"""
from __future__ import annotations

import logging
import re
from collections import OrderedDict
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from ..core.database import commit_with_retry
from ..core.trigger_types import (
    TRIGGER_PRACTICE_RECORD_CREATED,
    TRIGGER_PRACTICE_SUBMIT,
)
from ..models.models import PracticeRecord, QuestionBank, WrongQuestionPersonal
from .event_consumer import outbox_mode_enabled, record_user_action

logger = logging.getLogger(__name__)

_ANSWER_SPLIT_RE = re.compile(r"[,，、;；\s]+")
_LETTERS_RE = re.compile(r"^[A-Za-z]+$")

#: 已发布 E2 的练习会话（进程内去重，仅作事件加速器的幂等护栏）。
#: 成就判据本身按 session 幂等，进程重启后重复发布不会造成重复发放。
_RECORD_EVENT_SESSIONS: "OrderedDict[Tuple[int, str], None]" = OrderedDict()
_RECORD_EVENT_SESSION_LIMIT = 4096


def reset_record_event_sessions() -> None:
    """清空 E2 会话去重表（仅测试使用）。"""
    _RECORD_EVENT_SESSIONS.clear()


def _claim_record_session(user_id: int, session_id: str) -> bool:
    """抢占一个练习会话的 E2 发布权；同一会话重复提交返回 False。"""
    key = (user_id, str(session_id))
    if key in _RECORD_EVENT_SESSIONS:
        return False
    _RECORD_EVENT_SESSIONS[key] = None
    while len(_RECORD_EVENT_SESSIONS) > _RECORD_EVENT_SESSION_LIMIT:
        _RECORD_EVENT_SESSIONS.popitem(last=False)
    return True


def _record_session_published(user_id: int, session_id: str) -> bool:
    return (user_id, str(session_id)) in _RECORD_EVENT_SESSIONS

def normalize_answer(value: Any) -> str:
    """归一化客观题答案：字母答案去分隔符后排序，文本答案仅去首尾空白。"""
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        parts = [str(v).strip() for v in value if str(v).strip()]
        text = "".join(parts)
    else:
        text = str(value).strip()
    if not text:
        return ""
    parts = [p for p in _ANSWER_SPLIT_RE.split(text) if p]
    if len(parts) > 1:
        text = "".join(parts)
    if _LETTERS_RE.match(text):
        return "".join(sorted(text.upper()))
    return text


def grade_answer(correct_answer: Any, user_answer: Any) -> bool:
    """按标准答案判分；空作答一律判错。"""
    expected = normalize_answer(correct_answer)
    actual = normalize_answer(user_answer)
    return bool(expected) and expected == actual


def upsert_wrong_question(
    db: Session,
    user_id: int,
    question_id: int,
    subject_id: Optional[int] = None,
    user_answer: str = "",
) -> str:
    """同事务内写入/累加个人错题，返回 ``new`` / ``updated`` / ``skipped``。"""
    db.flush()
    if not subject_id:
        question = db.query(QuestionBank).filter(
            QuestionBank.question_id == question_id
        ).first()
        if not question:
            return "skipped"
        subject_id = question.subject_id

    now = datetime.now()
    existing = db.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.user_id == user_id,
        WrongQuestionPersonal.question_id == question_id,
        WrongQuestionPersonal.collection_type == "WRONG",
    ).first()
    if existing:
        existing.error_count = (existing.error_count or 0) + 1
        existing.review_count = (existing.review_count or 0) + 1
        existing.last_review_time = now
        if user_answer:
            existing.user_answer = user_answer
        return "updated"

    db.add(WrongQuestionPersonal(
        user_id=user_id,
        question_id=question_id,
        subject_id=subject_id,
        collection_type="WRONG",
        error_count=1,
        accuracy_rate=0.0,
        user_answer=user_answer or "",
        add_time=now,
        last_review_time=now,
        review_count=1,
    ))
    return "new"


def _load_questions(db: Session, question_ids: Iterable[int]) -> Dict[int, QuestionBank]:
    ids = list({qid for qid in question_ids if qid})
    if not ids:
        return {}
    rows = db.query(QuestionBank).filter(QuestionBank.question_id.in_(ids)).all()
    return {row.question_id: row for row in rows}


def _grade_item(db: Session, user_id: int, item: Dict[str, Any],
                questions: Dict[int, QuestionBank], source_type: str,
                subject_id: Optional[int]) -> Dict[str, Any]:
    question_id = item.get("question_id")
    if question_id is None:
        raise ValueError("records 中存在缺少 question_id 的条目")
    question_id = int(question_id)
    question = questions.get(question_id)
    if question is None:
        raise ValueError(f"题目不存在: {question_id}")

    user_answer = item.get("user_answer", item.get("answer", ""))
    if user_answer in (None, ""):
        is_correct = bool(item.get("is_correct", False))
    else:
        is_correct = grade_answer(question.answer, user_answer)

    record_subject = item.get("subject_id") or subject_id or question.subject_id
    record = PracticeRecord(
        user_id=user_id,
        question_id=question_id,
        subject_id=record_subject,
        type_id=question.type_id,
        is_correct=1 if is_correct else 0,
        time_spent=int(item.get("time_spent") or 0),
        answer=str(user_answer or ""),
        practice_date=date.today(),
        practice_time=datetime.now(),
        source_type=item.get("source") or source_type,
    )
    db.add(record)
    db.flush()

    wrong_result = "skipped"
    if not is_correct:
        wrong_result = upsert_wrong_question(
            db, user_id, question_id, record_subject, str(user_answer or "")
        )

    return {
        "record_id": record.record_id,
        "question_id": question_id,
        "is_correct": bool(is_correct),
        "correct_answer": question.answer,
        "wrong_result": wrong_result,
    }


async def submit_answers(
    db: Session,
    user_id: int,
    records: List[Dict[str, Any]],
    source_type: str,
    subject_id: Optional[int] = None,
    session_id: Optional[str] = None,
    publish_event: bool = True,
) -> Dict[str, Any]:
    """判分 + 记录 + 错题入库（单事务），提交后发布一次 E1 事件。"""
    if not records:
        return {
            "status": "ok",
            "count": 0,
            "correct": 0,
            "total": 0,
            "accuracy": 0.0,
            "wrong_question_stats": {"new": 0, "updated": 0, "skipped": 0},
            "has_new_wrong": False,
            "results": [],
            "event_published": False,
        }

    wrong_stats = {"new": 0, "updated": 0, "skipped": 0}
    results: List[Dict[str, Any]] = []
    try:
        questions = _load_questions(db, (item.get("question_id") for item in records))
        for item in records:
            result = _grade_item(db, user_id, item, questions,
                                 source_type, subject_id)
            results.append(result)
            if not result["is_correct"] and result["wrong_result"] in wrong_stats:
                wrong_stats[result["wrong_result"]] += 1
    except Exception:
        db.rollback()
        raise

    total = len(results)
    correct = sum(1 for r in results if r["is_correct"])
    event_session = {
        "session_id": session_id,
        "source": source_type,
        "total": total,
        "correct": correct,
    }
    published = False
    # F2b：判分数据与两个行为事件同一事务提交。
    try:
        if publish_event:
            try:
                published = await record_user_action(
                    db, user_id, TRIGGER_PRACTICE_SUBMIT, session=event_session
                )
            except Exception as exc:  # noqa: BLE001 — 关闭 Outbox 时事件不阻断判分
                if outbox_mode_enabled():
                    raise
                logger.warning(f"练习判分事件发布失败(非阻断): {exc}")

        record_event_published = await _publish_record_created(
            db,
            user_id,
            records=results,
            total=total,
            correct=correct,
            time_spent=sum(int(item.get("time_spent") or 0) for item in records),
            session_id=session_id,
            source_type=source_type,
            publish_event=publish_event,
        )
        commit_with_retry(db)
    except Exception:
        db.rollback()
        raise

    return {
        "status": "ok",
        "count": total,
        "correct": correct,
        "total": total,
        "accuracy": round(correct * 100 / max(total, 1), 1),
        "wrong_question_stats": wrong_stats,
        "has_new_wrong": bool(wrong_stats["new"] or wrong_stats["updated"]),
        "results": results,
        "event_published": published,
        "record_event_published": record_event_published,
        "session": event_session,
    }


async def _publish_record_created(
    db: Session,
    user_id: int,
    records: List[Dict[str, Any]],
    total: int,
    correct: int,
    time_spent: int,
    session_id: Optional[str],
    source_type: str,
    publish_event: bool,
) -> bool:
    """E2：练习记录创建后发布一次；同一会话重复提交不再发布。"""
    if not publish_event or total <= 0:
        return False
    if session_id and _record_session_published(user_id, session_id):
        logger.info(f"练习记录事件已发布过，跳过重复会话: {session_id}")
        return False

    payload = {
        "session_id": session_id,
        "source": source_type,
        "total": total,
        "correct": correct,
        "record_ids": [r["record_id"] for r in records],
        "time_spent": time_spent,
        "practice_date": date.today().isoformat(),
    }
    try:
        published = await record_user_action(
            db, user_id, TRIGGER_PRACTICE_RECORD_CREATED, session=payload
        )
    except Exception as exc:  # noqa: BLE001 — 关闭 Outbox 时事件不阻断判分
        if outbox_mode_enabled():
            raise
        logger.warning(f"练习记录事件发布失败(非阻断): {exc}")
        return False
    if session_id:
        _claim_record_session(user_id, session_id)
    return published
