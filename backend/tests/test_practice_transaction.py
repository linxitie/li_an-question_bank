"""答题练习判分事务测试（P2-06）。

覆盖：判分正确性、回滚、错题同事务幂等、事件在提交后只发一次。
"""
import asyncio

import pytest

from app.models.models import (
    PracticeRecord,
    QuestionBank,
    WrongQuestionPersonal,
)
from app.services import practice_grading
from app.services.practice_grading import normalize_answer, submit_answers


@pytest.fixture
def question(db_session, test_subject, test_question_type, test_user):
    row = QuestionBank(
        subject_id=test_subject.subject_id,
        type_id=test_question_type.type_id,
        question_content="下列选项正确的是？",
        options=["A. 甲", "B. 乙", "C. 丙", "D. 丁"],
        answer="AC",
        creator_id=test_user.user_id,
        status=1,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _run(coro):
    return asyncio.run(coro)


def test_answer_normalization_handles_multi_choice():
    assert normalize_answer("c, a") == "AC"
    assert normalize_answer(["A", "C"]) == "AC"
    assert normalize_answer("AC") == "AC"


def test_submit_grades_and_writes_same_transaction(
    db_session, test_user, question, monkeypatch
):
    events = []

    async def fake_record(db, user_id, trigger_type, session=None):
        events.append((user_id, trigger_type, session))
        return True

    monkeypatch.setattr(practice_grading, "record_user_action", fake_record)

    result = _run(submit_answers(
        db_session,
        test_user.user_id,
        [
            {"question_id": question.question_id, "user_answer": "AC", "time_spent": 12},
            {"question_id": question.question_id, "user_answer": "B", "time_spent": 8},
        ],
        source_type="快速练习",
    ))

    assert result["total"] == 2
    assert result["correct"] == 1
    assert result["wrong_question_stats"] == {"new": 1, "updated": 0, "skipped": 0}
    assert result["has_new_wrong"] is True

    records = db_session.query(PracticeRecord).all()
    assert len(records) == 2
    assert {r.is_correct for r in records} == {0, 1}

    wrong = db_session.query(WrongQuestionPersonal).one()
    assert wrong.error_count == 1
    assert wrong.user_answer == "B"

    assert len(events) == 1
    assert events[0][1] == "practice.submit"
    assert events[0][2]["total"] == 2
    assert events[0][2]["correct"] == 1


def test_rollback_leaves_no_writes_and_no_event(
    db_session, test_user, question, monkeypatch
):
    published = []

    async def fake_record(*args, **kwargs):
        published.append(1)
        return True

    def boom(*args, **kwargs):
        raise RuntimeError("错题写入失败")

    monkeypatch.setattr(practice_grading, "record_user_action", fake_record)
    monkeypatch.setattr(practice_grading, "upsert_wrong_question", boom)

    with pytest.raises(RuntimeError):
        _run(submit_answers(
            db_session,
            test_user.user_id,
            [{"question_id": question.question_id, "user_answer": "B"}],
            source_type="快速练习",
        ))

    assert db_session.query(PracticeRecord).count() == 0
    assert db_session.query(WrongQuestionPersonal).count() == 0
    assert published == []


def test_same_wrong_question_increments_once_per_attempt(
    db_session, test_user, question, monkeypatch
):
    async def fake_record(*args, **kwargs):
        return True

    monkeypatch.setattr(practice_grading, "record_user_action", fake_record)

    payload = [{"question_id": question.question_id, "user_answer": "B"}]
    _run(submit_answers(db_session, test_user.user_id, payload, "快速练习"))
    result = _run(submit_answers(db_session, test_user.user_id, payload, "快速练习"))

    assert result["wrong_question_stats"] == {"new": 0, "updated": 1, "skipped": 0}
    assert db_session.query(PracticeRecord).count() == 2
    wrong = db_session.query(WrongQuestionPersonal).one()
    assert wrong.error_count == 2
    assert wrong.review_count == 2


def test_correct_answer_does_not_touch_wrong_book(
    db_session, test_user, question, monkeypatch
):
    async def fake_record(*args, **kwargs):
        return True

    monkeypatch.setattr(practice_grading, "record_user_action", fake_record)

    _run(submit_answers(
        db_session,
        test_user.user_id,
        [{"question_id": question.question_id, "user_answer": "A,C"}],
        "快速练习",
    ))

    assert db_session.query(WrongQuestionPersonal).count() == 0


def test_batch_record_endpoint_exposes_new_wrong_flag(
    client, auth_headers, db_session, question
):
    response = client.post(
        "/api/practice/batch-record",
        headers=auth_headers,
        json={
            "records": [
                {"question_id": question.question_id, "user_answer": "AC"},
                {"question_id": question.question_id, "user_answer": "B"},
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["has_new_wrong"] is True
    assert body["wrong_question_stats"]["new"] == 1


def test_quick_practice_submit_endpoint_uses_grading(
    client, auth_headers, db_session, question
):
    response = client.post(
        "/api/quick-practice/submit",
        headers=auth_headers,
        json={
            "subject_id": question.subject_id,
            "records": [
                {"question_id": question.question_id, "user_answer": "AC", "is_correct": False},
                {"question_id": question.question_id, "user_answer": "D", "is_correct": True},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["correct"] == 1
    assert body["wrong_question_stats"]["new"] == 1

    db_session.expire_all()
    assert db_session.query(PracticeRecord).count() == 2
    assert db_session.query(WrongQuestionPersonal).count() == 1
