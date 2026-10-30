"""快速练习考点树：canonical L2/L3 过滤、0 题隐藏、去重与可见计数。"""
import pytest

from app.models.models import (
    KnowledgePoint,
    PracticeRecord,
    QuestionBank,
    QuestionKnowledge,
    SubCategory,
)


def _seed_question(db, user, content, sub_category_id=None, status=1,
                   point_id=None):
    question = QuestionBank(
        subject_id=1,
        type_id=1,
        question_content=content,
        options=[{"key": "A", "value": "1"}],
        answer="A",
        difficulty=1,
        score=2,
        sub_category_id=sub_category_id,
        point_id=point_id,
        creator_id=user.user_id,
        status=status,
        audit_status=1,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def _seed_point(db, name, level, parent_id, sub_category_id, sort_order, status=1):
    point = KnowledgePoint(
        point_name=name,
        subject_id=1,
        sub_category_id=sub_category_id,
        level=level,
        parent_id=parent_id,
        sort_order=sort_order,
        status=status,
    )
    db.add(point)
    db.commit()
    db.refresh(point)
    return point


def _link(db, question, point):
    db.add(QuestionKnowledge(
        question_id=question.question_id,
        knowledge_point_id=point.point_id,
    ))
    db.commit()


def _record(db, user, question, is_correct):
    db.add(PracticeRecord(
        user_id=user.user_id,
        question_id=question.question_id,
        subject_id=1,
        type_id=1,
        is_correct=is_correct,
    ))
    db.commit()


@pytest.fixture
def tree(db_session, test_user, test_question_type):
    sub_category = SubCategory(
        subject_id=1, name="判断推理", status=1, sort_order=1
    )
    db_session.add(sub_category)
    db_session.commit()
    db_session.refresh(sub_category)

    l2_a = _seed_point(db_session, "逻辑判断", 2, 0, sub_category.id, 1)
    l2_zero = _seed_point(db_session, "零题L2", 2, 0, sub_category.id, 2)
    l2_hidden = _seed_point(
        db_session, "隐藏L2", 2, 0, sub_category.id, 3, status=0
    )

    l3_translate = _seed_point(
        db_session, "翻译推理", 3, l2_a.point_id, sub_category.id, 1
    )
    l3_other = _seed_point(
        db_session, "其他", 3, l2_a.point_id, sub_category.id, 2
    )
    l3_zero = _seed_point(
        db_session, "零题L3", 3, l2_a.point_id, sub_category.id, 3
    )

    q_l3 = _seed_question(
        db_session, test_user, "翻译推理题", sub_category_id=sub_category.id,
        point_id=l3_translate.point_id,
    )
    q_other = _seed_question(
        db_session, test_user, "其他题", sub_category_id=sub_category.id,
        point_id=l3_other.point_id,
    )
    q_direct = _seed_question(
        db_session, test_user, "直挂L2题", sub_category_id=sub_category.id,
        point_id=l2_a.point_id,
    )
    q_unlinked = _seed_question(
        db_session, test_user, "无关系题", sub_category_id=sub_category.id,
        point_id=None,
    )
    q_global = _seed_question(
        db_session, test_user, "全局未分类题", sub_category_id=None,
        point_id=None,
    )
    q_hidden = _seed_question(
        db_session, test_user, "下架题", sub_category_id=sub_category.id,
        status=0, point_id=l3_translate.point_id,
    )

    _link(db_session, q_l3, l3_translate)
    _link(db_session, q_other, l3_other)
    # 关系表多挂一个 L3：计数必须以 point_id 为准，不能被关系表带偏
    _link(db_session, q_other, l3_translate)
    _link(db_session, q_direct, l2_a)
    _link(db_session, q_hidden, l3_translate)

    _record(db_session, test_user, q_l3, 1)
    _record(db_session, test_user, q_l3, 0)
    _record(db_session, test_user, q_other, 0)
    _record(db_session, test_user, q_global, 1)

    return {
        "sub_category": sub_category,
        "l2_a": l2_a,
        "l2_zero": l2_zero,
        "l2_hidden": l2_hidden,
        "l3_translate": l3_translate,
        "l3_other": l3_other,
        "l3_zero": l3_zero,
        "q_unlinked": q_unlinked,
    }


def test_sub_categories_return_canonical_tree(client, auth_headers, tree):
    response = client.get(
        "/api/quick-practice/sub-categories?subjectId=1", headers=auth_headers
    )
    assert response.status_code == 200, response.text

    data = response.json()
    items = {item["name"]: item for item in data["items"]}
    assert data["total"] == 2
    assert set(items) == {"判断推理", "未分类"}

    card = items["判断推理"]
    assert card["is_unclassified"] is False
    assert card["total_questions"] == 4
    assert card["done_count"] == 2
    assert card["correct_count"] == 1
    assert card["accuracy"] == 50.0
    assert card["unclassified_count"] == 1

    kps = card["knowledge_points"]
    assert [node["point_name"] for node in kps] == ["逻辑判断"]
    l2 = kps[0]
    assert l2["point_id"] == tree["l2_a"].point_id
    assert l2["level"] == 2
    assert l2["total_questions"] == 3
    assert l2["done_count"] == 2
    assert l2["correct_count"] == 1
    assert l2["accuracy"] == 50.0

    children = l2["children"]
    assert [child["point_name"] for child in children] == ["翻译推理", "其他"]
    assert [child["level"] for child in children] == [3, 3]
    assert all(child["children"] == [] for child in children)
    assert sum(child["total_questions"] for child in children) == 2
    assert l2["total_questions"] == sum(
        child["total_questions"] for child in children
    ) + 1

    child_map = {child["point_name"]: child for child in children}
    assert child_map["翻译推理"]["total_questions"] == 1
    assert child_map["翻译推理"]["done_count"] == 1
    assert child_map["翻译推理"]["correct_count"] == 1
    assert child_map["翻译推理"]["accuracy"] == 100.0
    assert child_map["其他"]["total_questions"] == 1
    assert child_map["其他"]["done_count"] == 1
    assert child_map["其他"]["correct_count"] == 0
    assert child_map["其他"]["accuracy"] == 0

    assert l2["total_questions"] + card["unclassified_count"] == card["total_questions"]

    returned_ids = {l2["point_id"]} | {child["point_id"] for child in children}
    assert tree["l2_zero"].point_id not in returned_ids
    assert tree["l2_hidden"].point_id not in returned_ids
    assert tree["l3_zero"].point_id not in returned_ids
    assert len([node["point_name"] for node in children]) == len(
        {node["point_name"] for node in children}
    )

    unc = items["未分类"]
    assert unc["id"] == 0
    assert unc["sort_order"] == 999
    assert unc["is_unclassified"] is True
    assert unc["total_questions"] == 1
    assert unc["done_count"] == 1
    assert unc["correct_count"] == 1
    assert unc["accuracy"] == 100.0
    assert unc["unclassified_count"] == 1
    assert unc["knowledge_points"] == []
    assert unc["children"] == []


def test_knowledge_points_returns_only_nonzero_l3(client, auth_headers, tree):
    response = client.get(
        "/api/quick-practice/knowledge-points"
        f"?subCategoryId={tree['sub_category'].id}",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    data = response.json()
    assert data["total"] == 2
    names = [item["point_name"] for item in data["items"]]
    assert names == ["翻译推理", "其他"]
    assert tree["l2_a"].point_name not in names
    assert tree["l3_zero"].point_name not in names

    item_map = {item["point_name"]: item for item in data["items"]}
    assert item_map["翻译推理"]["total_questions"] == 1
    assert item_map["翻译推理"]["done_count"] == 1
    assert item_map["翻译推理"]["correct_count"] == 1
    assert item_map["翻译推理"]["accuracy"] == 100.0
    assert item_map["其他"]["total_questions"] == 1
    assert item_map["其他"]["correct_count"] == 0


def test_primary_point_wins_over_multiple_relations(
    client, auth_headers, db_session, test_user, tree
):
    q_multi = _seed_question(
        db_session, test_user, "双关系题",
        sub_category_id=tree["sub_category"].id,
        point_id=tree["l3_translate"].point_id,
    )
    _link(db_session, q_multi, tree["l3_translate"])
    _link(db_session, q_multi, tree["l3_other"])

    response = client.get(
        "/api/quick-practice/sub-categories?subjectId=1", headers=auth_headers
    )
    assert response.status_code == 200, response.text

    data = response.json()
    items = {item["name"]: item for item in data["items"]}
    card = items["判断推理"]

    assert card["total_questions"] == 5
    assert card["unclassified_count"] == 1

    l2 = card["knowledge_points"][0]
    children = {child["point_name"]: child for child in l2["children"]}
    assert children["翻译推理"]["total_questions"] == 2
    assert children["其他"]["total_questions"] == 1
    assert l2["total_questions"] == 4
    assert l2["total_questions"] + card["unclassified_count"] == card["total_questions"]
