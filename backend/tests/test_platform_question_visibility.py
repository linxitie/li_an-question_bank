"""P1-4: 教师/管理员题目列表与统计默认口径与学生端一致。"""
import pytest

from app.models.models import QuestionBank

CASES = [
    ("visible", 1, 1),
    ("offline", 0, 1),
    ("pending", 1, 0),
    ("hidden", 0, 0),
]


@pytest.fixture
def seeded_questions(db_session, test_user, test_subject, test_question_type):
    created = {}
    for name, status, audit_status in CASES:
        question = QuestionBank(
            subject_id=test_subject.subject_id,
            type_id=test_question_type.type_id,
            question_content=name,
            options=[{"key": "A", "value": "1"}],
            answer="A",
            difficulty=1,
            score=2,
            creator_id=test_user.user_id,
            status=status,
            audit_status=audit_status,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)
        created[name] = question.question_id
    return created


def _item_ids(payload):
    return {item["question_id"] for item in payload["items"]}


def test_admin_list_default_visible_only(client, admin_headers, seeded_questions):
    resp = client.get(
        "/api/admin/questions?page=1&page_size=10", headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert _item_ids(data) == {seeded_questions["visible"]}


def test_admin_list_include_offline(client, admin_headers, seeded_questions):
    resp = client.get(
        "/api/admin/questions?page=1&page_size=10&include_offline=true",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert _item_ids(data) == {
        seeded_questions["visible"],
        seeded_questions["offline"],
    }


def test_admin_list_include_pending(client, admin_headers, seeded_questions):
    resp = client.get(
        "/api/admin/questions?page=1&page_size=10&include_pending=true",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert _item_ids(data) == {
        seeded_questions["visible"],
        seeded_questions["pending"],
    }


def test_admin_list_both_switches(client, admin_headers, seeded_questions):
    resp = client.get(
        "/api/admin/questions?page=1&page_size=10"
        "&include_offline=true&include_pending=true",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4
    assert _item_ids(data) == set(seeded_questions.values())


def test_admin_stats_default_visible_only(client, admin_headers, seeded_questions):
    resp = client.get("/api/admin/questions/stats", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["xingce"] == 1


def test_admin_stats_both_switches(client, admin_headers, seeded_questions):
    resp = client.get(
        "/api/admin/questions/stats"
        "?include_offline=true&include_pending=true",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4
    assert data["xingce"] == 4


def test_teacher_list_default_visible_only(
    client, admin_headers, seeded_questions
):
    resp = client.get(
        "/api/teacher/questions?page=1&page_size=10", headers=admin_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert _item_ids(data) == {seeded_questions["visible"]}


def test_teacher_list_both_switches(client, admin_headers, seeded_questions):
    resp = client.get(
        "/api/teacher/questions?page=1&page_size=10"
        "&include_offline=true&include_pending=true",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4
    assert _item_ids(data) == set(seeded_questions.values())
