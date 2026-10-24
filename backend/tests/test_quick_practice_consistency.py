"""快速练习题目列表：bySubCategory 直查 question_bank 与返回字段一致性。"""
from app.models.models import (
    KnowledgePoint,
    QuestionBank,
    QuestionGroup,
    QuestionKnowledge,
    QuestionType,
    SubCategory,
)


def _seed_question(db_session, user, content, *, type_id, sub_category_id,
                   group_id=0, score=2, requirements=None):
    question = QuestionBank(
        subject_id=1,
        type_id=type_id,
        question_content=content,
        answer="A",
        sub_category_id=sub_category_id,
        group_id=group_id,
        score=score,
        requirements=requirements,
        status=1,
        audit_status=1,
        creator_id=user.user_id,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


def test_by_sub_category_queries_question_bank_directly(
    client, db_session, auth_headers, test_user
):
    sub_category = SubCategory(subject_id=1, name="判断推理", status=1)
    subjective_type = QuestionType(
        type_name="写作", type_code="WRITING_TEST", is_objective=0
    )
    group = QuestionGroup(
        group_type="material",
        shared_content="共享材料",
        shared_content_images='["/static/test.png"]',
    )
    db_session.add_all([sub_category, subjective_type, group])
    db_session.commit()
    for obj in (sub_category, subjective_type, group):
        db_session.refresh(obj)

    question_a = _seed_question(
        db_session, test_user, "未挂知识点的写作题",
        type_id=subjective_type.type_id,
        sub_category_id=sub_category.id,
        group_id=group.id,
        score=40,
        requirements="1000字",
    )
    _seed_question(
        db_session, test_user, "不应出现的未分类题",
        type_id=subjective_type.type_id,
        sub_category_id=None,
    )

    assert db_session.query(QuestionKnowledge).count() == 0

    response = client.get(
        f"/api/quick-practice/questions?knowledge_point_ids={sub_category.id}"
        "&bySubCategory=true&limit=10",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["total"] == 1
    assert data["limit"] == 10
    assert len(data["items"]) == 1

    item = data["items"][0]
    assert item["question_id"] == question_a.question_id
    assert item["group_id"] == group.id
    assert item["shared_content"] == "共享材料"
    assert item["shared_content_images"] == '["/static/test.png"]'
    assert item["is_subjective"] is True
    assert item["question_type_name"] == "写作"
    assert item["score"] == 40.0
    assert item["requirements"] == "1000字"
    assert "question_type_detail" in item
    assert "options" in item
    assert "images" in item


def test_by_sub_category_empty_returns_message(
    client, db_session, auth_headers, test_user
):
    sub_category = SubCategory(subject_id=1, name="资料分析", status=1)
    db_session.add(sub_category)
    db_session.commit()
    db_session.refresh(sub_category)

    response = client.get(
        f"/api/quick-practice/questions?knowledge_point_ids={sub_category.id}"
        "&bySubCategory=true&limit=10",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "total": 0,
        "items": [],
        "message": "该子科目下暂无题目",
    }


def test_without_by_sub_category_keeps_knowledge_relation_path(
    client, db_session, auth_headers, test_user, test_question_type
):
    point = KnowledgePoint(
        point_name="逻辑判断",
        subject_id=1,
        level=2,
        parent_id=0,
        sort_order=1,
    )
    db_session.add(point)
    db_session.commit()
    db_session.refresh(point)

    question = _seed_question(
        db_session, test_user, "通过关系表关联的客观题",
        type_id=test_question_type.type_id,
        sub_category_id=None,
    )
    db_session.add(QuestionKnowledge(
        question_id=question.question_id,
        knowledge_point_id=point.point_id,
    ))
    db_session.commit()

    response = client.get(
        f"/api/quick-practice/questions?knowledge_point_ids={point.point_id}&limit=10",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["question_id"] == question.question_id
    assert data["items"][0]["is_subjective"] is False
