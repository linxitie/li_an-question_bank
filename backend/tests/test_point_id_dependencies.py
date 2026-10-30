"""P1-8: 知识点进度/选择器以 question_bank.point_id 为唯一归属。"""
import pytest

from app.models.models import KnowledgePoint, QuestionBank


@pytest.fixture
def seeded_points(db_session, test_user, test_subject, test_question_type):
    filled = KnowledgePoint(
        point_name="逻辑判断",
        subject_id=test_subject.subject_id,
        sub_category_id=None,
        level=3,
        parent_id=0,
        status=1,
    )
    empty = KnowledgePoint(
        point_name="空考点",
        subject_id=test_subject.subject_id,
        sub_category_id=None,
        level=3,
        parent_id=0,
        status=1,
    )
    db_session.add_all([filled, empty])
    db_session.commit()
    db_session.refresh(filled)
    db_session.refresh(empty)

    db_session.add(QuestionBank(
        subject_id=test_subject.subject_id,
        type_id=test_question_type.type_id,
        question_content="逻辑判断题干",
        options=[{"key": "A", "value": "1"}],
        answer="A",
        point_id=filled.point_id,
        creator_id=test_user.user_id,
        status=1,
        audit_status=1,
    ))
    db_session.commit()
    return filled, empty


def test_knowledge_progress_uses_primary_point(client, admin_headers, seeded_points):
    filled, empty = seeded_points
    resp = client.get("/api/practice/knowledge-progress", headers=admin_headers)
    assert resp.status_code == 200

    subjects = resp.json()["subjects"]
    assert subjects
    kps = {kp["point_id"]: kp for s in subjects for kp in s["kps"]}
    assert empty.point_id not in kps
    assert kps[filled.point_id]["point_name"] == "逻辑判断"
    assert kps[filled.point_id]["total"] == 1
    assert kps[filled.point_id]["done"] == 0


def test_teacher_knowledge_points_only_visible(client, admin_headers, seeded_points):
    filled, _ = seeded_points
    resp = client.get(
        f"/api/teacher/knowledge-points?subject_id={filled.subject_id}",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["total"] == 1
    assert data["items"] == [{"point_id": filled.point_id, "point_name": "逻辑判断"}]


def test_knowledge_mastery_skips_empty_points(client, admin_headers, seeded_points):
    filled, empty = seeded_points
    resp = client.get(
        f"/api/teacher/analytics/knowledge-mastery?subject_id={filled.subject_id}",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    ids = {item["point_id"] for item in data["items"]}
    assert data["total"] == len(data["items"])
    assert empty.point_id not in ids
    assert ids <= {filled.point_id}
