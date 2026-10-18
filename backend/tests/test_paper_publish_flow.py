"""P2-17..P2-23 组卷/历年试卷域：状态机、E3 事件、发布推送与幂等。"""
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import create_access_token, get_password_hash
from app.models.models import ExamPaper, QuestionBank, SmartExamRecord, SysUser


@pytest.fixture
def teacher(db_session):
    user = SysUser(
        user_no="teacher001",
        username="教师",
        password=get_password_hash("password123"),
        phone="13700137000",
        user_type="teacher",
        role_level=2,
        status=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def teacher_headers(teacher):
    token = create_access_token(
        data={"user_id": teacher.user_id, "user_no": teacher.user_no}
    )
    return {"Authorization": f"Bearer {token}"}


def _create_paper(client, headers, code="PAPER-FLOW-001"):
    response = client.post(
        "/api/papers/",
        headers=headers,
        json={
            "paper_name": "状态机测试卷",
            "paper_code": code,
            "subject_id": 1,
            "composition_method": "MANUAL",
            "duration": 60,
            "total_score": 100,
            "difficulty": 3,
            "exam_type": "SIMULATION",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _seed_question(db_session, teacher, subject_id=1, type_id=1):
    question = QuestionBank(
        subject_id=subject_id,
        type_id=type_id,
        question_content="1+1 等于几？",
        options=[{"key": "A", "value": "1"}, {"key": "B", "value": "2"}],
        answer="B",
        answer_analysis="基础算术",
        difficulty=1,
        score=2,
        creator_id=teacher.user_id,
        status=1,
        audit_status=1,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


def _add_question(client, headers, paper_id, question_id):
    response = client.post(
        f"/api/papers/{paper_id}/questions",
        headers=headers,
        json=[question_id],
    )
    assert response.status_code == 200, response.text


def test_paper_state_machine_student_sees_only_published(
    client, db_session, test_user, test_admin, teacher, teacher_headers,
    auth_headers, admin_headers,
):
    paper = _create_paper(client, teacher_headers)
    paper_id = paper["paper_id"]
    assert paper["paper_type"] == "DRAFT"

    question = _seed_question(db_session, teacher)
    _add_question(client, teacher_headers, paper_id, question.question_id)

    draft_list = client.get("/api/papers/list?paper_type=PUBLISHED", headers=auth_headers)
    assert draft_list.status_code == 200
    assert all(item["paper_id"] != paper_id for item in draft_list.json()["items"])
    assert client.get(f"/api/papers/{paper_id}", headers=auth_headers).status_code in (403, 404)

    submit = client.post(f"/api/papers/{paper_id}/submit", headers=teacher_headers)
    assert submit.status_code == 200, submit.text
    assert _paper(db_session, paper_id).paper_type == "PENDING"

    assert client.post(f"/api/papers/{paper_id}/submit", headers=teacher_headers).status_code == 409
    assert client.post(f"/api/papers/{paper_id}/publish", headers=teacher_headers).status_code == 403

    approve = client.post(
        f"/api/papers/{paper_id}/approve?approval_result=APPROVED",
        headers=admin_headers,
    )
    assert approve.status_code == 200, approve.text
    assert _paper(db_session, paper_id).paper_type == "APPROVED"

    with patch(
        "app.api.v1.platform.websocket.publish_data_changed",
        new=AsyncMock(return_value=1),
    ) as mocked_push:
        publish = client.post(f"/api/papers/{paper_id}/publish", headers=admin_headers)
        assert publish.status_code == 200, publish.text
        mocked_push.assert_awaited_once()
        _args, kwargs = mocked_push.await_args[0], mocked_push.await_args[1]
        assert kwargs["domain"] == "exam"
        assert kwargs["type"] == "paper.published"
        assert kwargs["id"] == paper_id

    assert _paper(db_session, paper_id).paper_type == "PUBLISHED"

    published_list = client.get("/api/papers/list?paper_type=PUBLISHED", headers=auth_headers)
    assert published_list.status_code == 200
    assert any(item["paper_id"] == paper_id for item in published_list.json()["items"])
    assert client.get(f"/api/papers/{paper_id}", headers=auth_headers).status_code == 200


def test_invalid_transitions_return_409_and_no_push(
    client, db_session, test_user, test_admin, teacher, teacher_headers, admin_headers
):
    paper = _create_paper(client, teacher_headers, code="PAPER-FLOW-002")
    paper_id = paper["paper_id"]
    question = _seed_question(db_session, teacher)
    _add_question(client, teacher_headers, paper_id, question.question_id)

    approve = client.post(
        f"/api/papers/{paper_id}/approve?approval_result=APPROVED",
        headers=admin_headers,
    )
    assert approve.status_code == 409
    assert "DRAFT" in approve.json()["error"]["message"]

    with patch(
        "app.api.v1.platform.websocket.publish_data_changed",
        new=AsyncMock(return_value=1),
    ) as mocked_push:
        publish = client.post(f"/api/papers/{paper_id}/publish", headers=admin_headers)
        assert publish.status_code == 409
        mocked_push.assert_not_awaited()

    student_create = client.post(
        "/api/papers/",
        headers={"Authorization": "Bearer " + _token_for(db_session, "student")},
        json={
            "paper_name": "越权卷",
            "paper_code": "PAPER-FLOW-003",
            "subject_id": 1,
            "composition_method": "MANUAL",
            "duration": 60,
            "total_score": 100,
        },
    )
    assert student_create.status_code == 403


def test_smart_exam_submit_emits_paper_completed_once(
    client, db_session, test_user, teacher, teacher_headers, auth_headers,
    test_admin, admin_headers,
):
    paper = _create_paper(client, teacher_headers, code="PAPER-FLOW-004")
    paper_id = paper["paper_id"]
    question = _seed_question(db_session, teacher)
    _add_question(client, teacher_headers, paper_id, question.question_id)
    client.post(f"/api/papers/{paper_id}/submit", headers=teacher_headers)
    client.post(f"/api/papers/{paper_id}/approve?approval_result=APPROVED", headers=admin_headers)
    with patch(
        "app.api.v1.platform.websocket.publish_data_changed",
        new=AsyncMock(return_value=1),
    ):
        client.post(f"/api/papers/{paper_id}/publish", headers=admin_headers)

    start = client.post(f"/api/smart-exam/{paper_id}/start", headers=auth_headers)
    assert start.status_code == 200, start.text

    with patch(
        "app.api.v1.exam.smart_exam.record_user_action",
        new=AsyncMock(return_value=True),
    ) as mocked_record:
        first = client.post(
            f"/api/smart-exam/{paper_id}/submit",
            headers=auth_headers,
            json={"answers": {str(question.question_id): "B"}},
        )
        assert first.status_code == 200, first.text
        assert mocked_record.await_count == 1
        call_args = mocked_record.await_args[0]
        assert call_args[1] == test_user.user_id
        assert call_args[2] == "paper.completed"

        second = client.post(
            f"/api/smart-exam/{paper_id}/submit",
            headers=auth_headers,
            json={"answers": {str(question.question_id): "B"}},
        )
        assert second.status_code == 200, second.text
        assert second.json()["duplicate"] is True
        assert mocked_record.await_count == 1

    records = db_session.query(SmartExamRecord).filter_by(paper_id=paper_id).all()
    assert len(records) == 1


def _paper(db_session, paper_id):
    return db_session.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).first()


def _token_for(db_session, user_type):
    user = db_session.query(SysUser).filter(SysUser.user_type == user_type).first()
    return create_access_token(data={"user_id": user.user_id, "user_no": user.user_no})
