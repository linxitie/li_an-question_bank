"""错题集（E4）模块测试（P2-16）。

覆盖：掌握状态流转发布一次 ``wrong.reviewed``、同一错题幂等重放不发、非掌握流转不发、
只读端点不发、斩题与掌握流转共用去重口径，以及 E12「练习答错自动入库」在错题列表可见。
"""
from datetime import datetime

import pytest

from app.api.v1.catalog import wrong_questions
from app.models.models import QuestionBank, WrongQuestionPersonal
from app.services import practice_grading


@pytest.fixture(autouse=True)
def _reset_event_state():
    wrong_questions.reset_reviewed_events()
    practice_grading.reset_record_event_sessions()
    yield
    wrong_questions.reset_reviewed_events()
    practice_grading.reset_record_event_sessions()


@pytest.fixture
def question(db_session, test_subject, test_question_type, test_user):
    row = QuestionBank(
        subject_id=test_subject.subject_id,
        type_id=test_question_type.type_id,
        question_content="下列关于治安管理处罚的说法正确的是？",
        options=["A. 甲", "B. 乙", "C. 丙", "D. 丁"],
        answer="A",
        creator_id=test_user.user_id,
        status=1,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


@pytest.fixture
def wrong_row(db_session, test_user, question):
    row = WrongQuestionPersonal(
        user_id=test_user.user_id,
        question_id=question.question_id,
        subject_id=question.subject_id,
        collection_type="WRONG",
        error_count=2,
        mastery_level="UNMASTERED",
        is_cut=0,
        accuracy_rate=0,
        review_count=2,
        add_time=datetime.now(),
        last_review_time=datetime.now(),
        status=1,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


@pytest.fixture
def published(monkeypatch):
    events = []

    async def fake_record(db, user_id, trigger_type, session=None):
        events.append(
            {"user_id": user_id, "trigger_type": trigger_type, "session": session}
        )
        return True

    monkeypatch.setattr(wrong_questions, "record_user_action", fake_record)
    return events


def _reviewed_events(events):
    return [e for e in events if e["trigger_type"] == "wrong.reviewed"]


def _set_mastery(client, auth_headers, wrong_id, level="MASTERED"):
    return client.put(
        f"/api/wrong-questions/{wrong_id}/mastery",
        headers=auth_headers,
        json={"mastery_level": level},
    )


def test_mastery_transition_publishes_once(
    client, auth_headers, db_session, wrong_row, published
):
    response = _set_mastery(client, auth_headers, wrong_row.wrong_id)

    assert response.status_code == 200
    db_session.refresh(wrong_row)
    assert wrong_row.mastery_level == "MASTERED"
    assert wrong_row.is_cut == 1

    events = _reviewed_events(published)
    assert len(events) == 1
    session = events[0]["session"]
    assert session["wrong_id"] == wrong_row.wrong_id
    assert session["question_id"] == wrong_row.question_id
    assert session["mastery_level"] == "MASTERED"
    assert session["action"] == "mastered"


def test_mastery_replay_does_not_republish(
    client, auth_headers, db_session, wrong_row, published
):
    _set_mastery(client, auth_headers, wrong_row.wrong_id)
    _set_mastery(client, auth_headers, wrong_row.wrong_id)

    assert len(_reviewed_events(published)) == 1


def test_non_mastered_transition_does_not_publish(
    client, auth_headers, db_session, wrong_row, published
):
    response = _set_mastery(client, auth_headers, wrong_row.wrong_id, "PARTIAL")

    assert response.status_code == 200
    db_session.refresh(wrong_row)
    assert wrong_row.mastery_level == "PARTIAL"
    assert _reviewed_events(published) == []


def test_chop_shares_reviewed_dedupe(
    client, auth_headers, db_session, wrong_row, published
):
    first = client.put(
        f"/api/wrong-questions/{wrong_row.wrong_id}/chop", headers=auth_headers
    )
    second = client.put(
        f"/api/wrong-questions/{wrong_row.wrong_id}/chop", headers=auth_headers
    )

    assert first.status_code == 200
    assert second.status_code == 200
    db_session.refresh(wrong_row)
    assert wrong_row.is_cut == 1
    assert len(_reviewed_events(published)) == 1


def test_mastery_after_chop_does_not_republish(
    client, auth_headers, db_session, wrong_row, published
):
    client.put(f"/api/wrong-questions/{wrong_row.wrong_id}/chop", headers=auth_headers)
    _set_mastery(client, auth_headers, wrong_row.wrong_id)

    assert len(_reviewed_events(published)) == 1


@pytest.mark.parametrize(
    "path",
    [
        "/api/wrong-questions",
        "/api/wrong-questions/subcategories",
        "/api/wrong-questions/review/queue",
        "/api/wrong-questions/zhanti/list",
        "/api/wrong-questions/zhanti/expiring",
    ],
)
def test_read_endpoints_do_not_publish_reviewed(
    client, auth_headers, wrong_row, published, path
):
    response = client.get(path, headers=auth_headers)

    assert response.status_code == 200
    assert _reviewed_events(published) == []


def test_wrong_question_detail_is_read_only(
    client, auth_headers, wrong_row, published
):
    response = client.get(
        f"/api/wrong-questions/{wrong_row.wrong_id}/detail", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["wrong_id"] == wrong_row.wrong_id
    assert _reviewed_events(published) == []


def test_practice_wrong_answer_lands_in_wrongbook(
    client, auth_headers, db_session, question
):
    response = client.post(
        "/api/practice/batch-record",
        headers=auth_headers,
        json={"records": [{"question_id": question.question_id, "user_answer": "B"}]},
    )

    assert response.status_code == 200
    stored = db_session.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.question_id == question.question_id
    ).one()
    assert stored.error_count == 1

    listing = client.get("/api/wrong-questions", headers=auth_headers)
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert [item["wrong_id"] for item in items] == [stored.wrong_id]


def test_error_count_still_accumulates_via_collect(
    client, auth_headers, db_session, question, wrong_row
):
    response = client.post(
        "/api/wrong-questions/collect",
        headers=auth_headers,
        json={
            "question_id": question.question_id,
            "subject_id": question.subject_id,
            "is_correct": False,
        },
    )

    assert response.status_code == 200
    db_session.refresh(wrong_row)
    assert wrong_row.error_count == 3
    assert wrong_row.review_count == 3
