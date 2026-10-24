"""P1-9: 三端题量口径一致性守门（学生 / 教师 / 管理员）。"""
import pytest

from app.models.models import QuestionBank, SubCategory

VISIBLE_SUBCATEGORY = "判断推理"
UNCLASSIFIED_BUCKET = "未分类"
NO_SUBCATEGORY = "无"


def _seed_question(db, user, content, sub_category_id, xingce_subcategory,
                   status=1, audit_status=1):
    question = QuestionBank(
        subject_id=1,
        type_id=1,
        question_content=content,
        options=[{"key": "A", "value": "1"}],
        answer="A",
        difficulty=1,
        score=2,
        sub_category_id=sub_category_id,
        xingce_subcategory=xingce_subcategory,
        creator_id=user.user_id,
        status=status,
        audit_status=audit_status,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@pytest.fixture
def seeded_counts(db_session, test_user, test_subject, test_question_type):
    sub_category = SubCategory(
        subject_id=test_subject.subject_id,
        name=VISIBLE_SUBCATEGORY,
        status=1,
        sort_order=1,
    )
    db_session.add(sub_category)
    db_session.commit()
    db_session.refresh(sub_category)

    visible = [
        _seed_question(
            db_session, test_user, "可见-判断推理-1", sub_category.id,
            VISIBLE_SUBCATEGORY,
        ),
        _seed_question(
            db_session, test_user, "可见-判断推理-2", sub_category.id,
            VISIBLE_SUBCATEGORY,
        ),
        _seed_question(
            db_session, test_user, "可见-未分类", None, NO_SUBCATEGORY,
        ),
    ]
    pending = _seed_question(
        db_session, test_user, "待审-判断推理", sub_category.id,
        VISIBLE_SUBCATEGORY, status=1, audit_status=0,
    )
    offline = _seed_question(
        db_session, test_user, "下线-判断推理", sub_category.id,
        VISIBLE_SUBCATEGORY, status=0, audit_status=1,
    )
    return {
        "subject_id": test_subject.subject_id,
        "sub_category_id": sub_category.id,
        "visible": [q.question_id for q in visible],
        "pending": pending.question_id,
        "offline": offline.question_id,
    }


def _l2_total_sum(item):
    return sum(
        int(point["total_questions"]) for point in item["knowledge_points"]
    )


def _visible_total(items):
    return sum(int(item["total_questions"]) for item in items)


def test_student_sub_categories_counts(client, auth_headers, seeded_counts):
    resp = client.get(
        "/api/quick-practice/sub-categories",
        params={"subjectId": seeded_counts["subject_id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    by_name = {item["name"]: item for item in items}

    assert len(seeded_counts["visible"]) == 3
    assert _visible_total(items) == 3

    for item in items:
        if item["is_unclassified"]:
            continue
        assert (
            _l2_total_sum(item) + int(item["unclassified_count"])
            == int(item["total_questions"])
        ), item

    sub_item = by_name[VISIBLE_SUBCATEGORY]
    assert sub_item["total_questions"] == 2
    assert sub_item["is_unclassified"] is False
    assert sub_item["unclassified_count"] == 2
    assert _l2_total_sum(sub_item) == 0

    unc_item = by_name[UNCLASSIFIED_BUCKET]
    assert unc_item["is_unclassified"] is True
    assert unc_item["total_questions"] == 1


def test_teacher_list_counts(client, admin_headers, seeded_counts):
    resp = client.get(
        "/api/teacher/questions",
        params={"page": 1, "page_size": 10},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 3
    assert {item["question_id"] for item in data["items"]} == set(
        seeded_counts["visible"]
    )

    filtered = client.get(
        "/api/teacher/questions",
        params={
            "xingce_subcategory": VISIBLE_SUBCATEGORY,
            "page": 1,
            "page_size": 10,
        },
        headers=admin_headers,
    )
    assert filtered.status_code == 200, filtered.text
    assert filtered.json()["total"] == 2


def test_admin_list_counts(client, admin_headers, seeded_counts):
    resp = client.get(
        "/api/admin/questions",
        params={
            "page": 1,
            "page_size": 10,
            "subject_id": seeded_counts["subject_id"],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 3
    assert {item["question_id"] for item in data["items"]} == set(
        seeded_counts["visible"]
    )
