"""练习记录（E2）模块测试（P2-12）。

覆盖：记录创建发布一次 ``practice.record.created``、同一会话重复提交不重复发布、
只读端点不发布事件、``/api/exam-records`` 路由面未变且无硬删除端点。
"""
import pytest
from fastapi.routing import APIRoute

from app.main import app
from app.models.models import PracticeRecord, QuestionBank
from app.services import practice_grading


@pytest.fixture(autouse=True)
def _clear_record_event_sessions():
    practice_grading.reset_record_event_sessions()
    yield
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
def published(monkeypatch):
    events = []

    async def fake_record(db, user_id, trigger_type, session=None):
        events.append({"user_id": user_id, "trigger_type": trigger_type, "session": session})
        return True

    monkeypatch.setattr(practice_grading, "record_user_action", fake_record)
    return events


def _record_events(events):
    return [e for e in events if e["trigger_type"] == "practice.record.created"]


def _submit(client, auth_headers, question, session_id=None, answer="B"):
    payload = {
        "records": [{"question_id": question.question_id, "user_answer": answer}],
    }
    if session_id is not None:
        payload["session_id"] = session_id
    return client.post("/api/practice/batch-record", headers=auth_headers, json=payload)


def test_create_publishes_record_created_once(
    client, auth_headers, db_session, question, published
):
    response = _submit(client, auth_headers, question, session_id="session-e2-1")

    assert response.status_code == 200
    assert db_session.query(PracticeRecord).count() == 1

    record_events = _record_events(published)
    assert len(record_events) == 1
    session = record_events[0]["session"]
    assert session["session_id"] == "session-e2-1"
    assert session["total"] == 1
    assert session["correct"] == 0
    assert len(session["record_ids"]) == 1
    assert session["practice_date"]
    assert session["time_spent"] == 0


def test_same_session_resubmission_does_not_republish(
    client, auth_headers, db_session, question, published
):
    _submit(client, auth_headers, question, session_id="session-e2-dup")
    _submit(client, auth_headers, question, session_id="session-e2-dup")

    assert db_session.query(PracticeRecord).count() == 2
    assert len(_record_events(published)) == 1


def test_distinct_sessions_publish_per_creation(
    client, auth_headers, question, published
):
    _submit(client, auth_headers, question, session_id="session-e2-a")
    _submit(client, auth_headers, question, session_id="session-e2-b")

    assert len(_record_events(published)) == 2


def test_submission_without_session_publishes_per_submit(
    client, auth_headers, question, published
):
    _submit(client, auth_headers, question)
    _submit(client, auth_headers, question)

    assert len(_record_events(published)) == 2


@pytest.mark.parametrize(
    "path",
    [
        "/api/exam-records/self",
        "/api/exam-records/mock",
        "/api/exam-records/stats",
        "/api/exam-records/trend",
        "/api/exam-records/summary",
        "/api/practice/records",
    ],
)
def test_read_endpoints_do_not_publish_events(
    client, auth_headers, published, path
):
    response = client.get(path, headers=auth_headers)

    assert response.status_code == 200
    assert published == []


def test_exam_records_surface_is_read_only():
    routes = {
        (next(iter(route.methods)), route.path)
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/exam-records")
    }

    assert routes == {
        ("GET", "/api/exam-records/self"),
        ("GET", "/api/exam-records/mock"),
        ("GET", "/api/exam-records/stats"),
        ("GET", "/api/exam-records/trend"),
        ("GET", "/api/exam-records/{record_id}/wrong-questions"),
        ("GET", "/api/exam-records/{record_id}/details"),
        ("POST", "/api/exam-records/ai/analyze"),
        ("GET", "/api/exam-records/summary"),
    }
    assert all(method != "DELETE" for method, _ in routes)
