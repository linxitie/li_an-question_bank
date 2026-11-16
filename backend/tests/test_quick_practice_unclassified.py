"""快速练习：0 号「未分类」虚拟子科目出题范围。"""
from app.models.models import QuestionBank


def _seed(db_session, user, content, *, subject_id, sub_category_id,
          type_id, status=1):
    question = QuestionBank(
        subject_id=subject_id,
        type_id=type_id,
        question_content=content,
        answer="A",
        options='[{"key":"A","value":"甲"},{"key":"B","value":"乙"}]',
        sub_category_id=sub_category_id,
        score=2,
        status=status,
        audit_status=1,
        creator_id=user.user_id,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


def test_unclassified_scope_filters_by_subject(
    client, db_session, auth_headers, test_user, test_question_type
):
    xc_null = _seed(
        db_session, test_user, "行测未分类题",
        subject_id=1, sub_category_id=None, type_id=test_question_type.type_id,
    )
    ga_null = _seed(
        db_session, test_user, "公专未分类题",
        subject_id=3, sub_category_id=None, type_id=test_question_type.type_id,
    )
    classified = _seed(
        db_session, test_user, "行测已分类题",
        subject_id=1, sub_category_id=5, type_id=test_question_type.type_id,
    )
    hidden = _seed(
        db_session, test_user, "行测未分类隐藏题",
        subject_id=1, sub_category_id=None, type_id=test_question_type.type_id,
        status=0,
    )

    response = client.get(
        "/api/quick-practice/questions?knowledge_point_ids=0"
        "&bySubCategory=true&subjectId=1&limit=10",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    ids = {item["question_id"] for item in data["items"]}

    assert data["total"] == 1
    assert xc_null.question_id in ids
    assert ga_null.question_id not in ids
    assert classified.question_id not in ids
    assert hidden.question_id not in ids

    rows = db_session.query(QuestionBank).filter(
        QuestionBank.question_id.in_(ids)
    ).all()
    assert rows and all(row.sub_category_id is None for row in rows)


def test_unclassified_scope_requires_subject(client, auth_headers):
    response = client.get(
        "/api/quick-practice/questions?knowledge_point_ids=0"
        "&bySubCategory=true&limit=10",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 0
    assert "subjectId" in data["message"]


def test_positive_sub_category_still_works(
    client, db_session, auth_headers, test_user, test_question_type
):
    question = _seed(
        db_session, test_user, "正数子科目题",
        subject_id=1, sub_category_id=5, type_id=test_question_type.type_id,
    )
    response = client.get(
        "/api/quick-practice/questions?knowledge_point_ids=5"
        "&bySubCategory=true&subjectId=1&limit=10",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["question_id"] == question.question_id
