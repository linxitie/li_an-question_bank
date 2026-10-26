"""快速练习子科目计数：canonical L2 节点 + 可见口径 + 未分类桶。"""
from app.models.models import (
    KnowledgePoint,
    QuestionBank,
    QuestionKnowledge,
    SubCategory,
)


def _seed_question(db_session, user, content, subcategory,
                   sub_category_id=None, status=1, audit_status=1,
                   point_id=None):
    question = QuestionBank(
        subject_id=1,
        type_id=1,
        question_content=content,
        options=[{"key": "A", "value": "1"}],
        answer="A",
        difficulty=1,
        score=2,
        xingce_subcategory=subcategory,
        sub_category_id=sub_category_id,
        point_id=point_id,
        creator_id=user.user_id,
        status=status,
        audit_status=audit_status,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


def test_sub_categories_count_visible_and_bucket_unclassified(
    client, db_session, auth_headers, test_user, test_subject, test_question_type
):
    sub_category = SubCategory(
        subject_id=1, name="判断推理", status=1, sort_order=1
    )
    db_session.add(sub_category)
    db_session.commit()
    db_session.refresh(sub_category)

    visible_matched = _seed_question(
        db_session, test_user, "可见判断推理题", "判断推理",
        sub_category_id=sub_category.id,
    )
    _seed_question(db_session, test_user, "未归类题", "无")
    _seed_question(
        db_session, test_user, "隐藏判断推理题", "判断推理",
        sub_category_id=sub_category.id, status=0, audit_status=1,
    )

    knowledge_point = KnowledgePoint(
        point_name="逻辑判断",
        subject_id=1,
        sub_category_id=sub_category.id,
        level=2,
        parent_id=0,
        sort_order=1,
    )
    db_session.add(knowledge_point)
    db_session.commit()
    db_session.refresh(knowledge_point)

    visible_matched.point_id = knowledge_point.point_id
    db_session.commit()

    db_session.add(QuestionKnowledge(
        question_id=visible_matched.question_id,
        knowledge_point_id=knowledge_point.point_id,
    ))
    db_session.commit()

    response = client.get(
        "/api/quick-practice/sub-categories?subjectId=1", headers=auth_headers
    )
    assert response.status_code == 200, response.text

    data = response.json()
    items = {item["name"]: item for item in data["items"]}

    assert items["判断推理"]["total_questions"] == 1
    assert items["判断推理"]["is_unclassified"] is False
    assert items["判断推理"]["unclassified_count"] == 0
    assert items["未分类"]["total_questions"] == 1
    assert items["未分类"]["is_unclassified"] is True
    assert items["未分类"]["unclassified_count"] == 1
    assert items["未分类"]["knowledge_points"] == []
    assert items["未分类"]["children"] == []
    assert sum(item["total_questions"] for item in data["items"]) == 2
    assert data["total"] == 2

    point_items = items["判断推理"]["knowledge_points"]
    assert len(point_items) == 1
    assert point_items[0]["point_id"] == knowledge_point.point_id
    assert point_items[0]["point_name"] == "逻辑判断"
    assert point_items[0]["level"] == 2
    assert point_items[0]["total_questions"] == 1
    assert point_items[0]["done_count"] == 0
    assert point_items[0]["correct_count"] == 0
    assert point_items[0]["accuracy"] == 0
    assert point_items[0]["children"] == []
