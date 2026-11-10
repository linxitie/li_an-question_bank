"""快速练习 display_points：合成「其他」/直练/筛选（设计 D2/D3）。"""
from app.models.models import KnowledgePoint, QuestionBank, SubCategory


def _seed(db_session, user, content, subcategory, *, sub_category_id=None,
          point_id=None, year=2025, type_id=1, difficulty=2):
    question = QuestionBank(
        subject_id=1, type_id=type_id, question_content=content,
        options=[{"key": "A", "value": "1"}], answer="A",
        difficulty=difficulty, score=2, year=year,
        xingce_subcategory=subcategory, sub_category_id=sub_category_id,
        point_id=point_id, creator_id=user.user_id, status=1, audit_status=1,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


def _point(db_session, name, parent_id=0, level=2, sort_order=1):
    point = KnowledgePoint(
        point_name=name, subject_id=1, sub_category_id=None,
        level=level, parent_id=parent_id, sort_order=sort_order,
    )
    db_session.add(point)
    db_session.commit()
    db_session.refresh(point)
    return point


def _display_items(client, auth_headers):
    response = client.get(
        "/api/quick-practice/sub-categories?subjectId=1", headers=auth_headers
    )
    assert response.status_code == 200, response.text
    return {item["name"]: item for item in response.json()["items"]}


def test_display_points_merge_canonical_other_and_orphans(
    client, db_session, auth_headers, test_user, test_subject, test_question_type
):
    sc = SubCategory(subject_id=1, name="判断推理", status=1, sort_order=1)
    db_session.add(sc)
    db_session.commit()
    db_session.refresh(sc)

    l2 = _point(db_session, "逻辑判断", level=2)
    l2.sub_category_id = sc.id
    specific = _point(db_session, "翻译推理", parent_id=l2.point_id, level=3,
                      sort_order=2)
    other = _point(db_session, "其他", parent_id=l2.point_id, level=3,
                   sort_order=99)
    for point in (l2, specific, other):
        point.sub_category_id = sc.id
    db_session.commit()

    _seed(db_session, test_user, "具体考点题", "判断推理",
          sub_category_id=sc.id, point_id=specific.point_id, year=2025)
    _seed(db_session, test_user, "canonical 其他题", "判断推理",
          sub_category_id=sc.id, point_id=other.point_id, year=2024,
          type_id=2, difficulty=3)
    _seed(db_session, test_user, "L2 直挂题", "判断推理",
          sub_category_id=sc.id, point_id=l2.point_id, year=2023)
    _seed(db_session, test_user, "未归类题", "判断推理",
          sub_category_id=sc.id, point_id=None, year=2022)

    items = _display_items(client, auth_headers)
    item = items["判断推理"]

    # 旧 knowledge_points 保持原样，避免破坏旧前端/旧测试。
    assert len(item["knowledge_points"]) == 1
    assert len(item["knowledge_points"][0]["children"]) == 2

    display = {node["point_name"]: node for node in item["display_points"]}
    assert set(display) == {"逻辑判断", "其他（未归类）"}
    l2_node = display["逻辑判断"]
    assert l2_node["is_direct"] is False
    assert l2_node["scope"]["type"] == "l2"
    assert [child["point_name"] for child in l2_node["children"]] == [
        "翻译推理", "其他（未细分）",
    ]
    spec_node, other_node = l2_node["children"]
    assert spec_node["scope"]["type"] == "l3"
    assert spec_node["total_questions"] == 1
    assert other_node["point_id"] == 0
    assert other_node["is_other"] is True
    assert other_node["is_direct"] is True
    assert other_node["total_questions"] == 2  # canonical 其他 + L2 直挂
    assert other_node["scope"] == {
        "type": "other", "id": l2.point_id, "name": "逻辑判断·其他（未细分）",
        "subject_id": 1, "sub_category_id": sc.id, "l2_id": l2.point_id,
    }

    orphan = display["其他（未归类）"]
    assert orphan["total_questions"] == 1
    assert orphan["scope"]["type"] == "other"
    assert orphan["scope"]["sub_category_id"] == sc.id
    assert item["has_specific_points"] is True
    assert item["other_question_count"] == 3
    assert item["unclassified_count"] == 1

    filters = item["filters"]
    assert filters["years"] == [2025, 2024, 2023, 2022]
    assert {entry["type_id"] for entry in filters["types"]} == {1, 2}
    assert {entry["difficulty"] for entry in filters["difficulties"]} == {2, 3}


def test_l2_with_only_other_is_direct_practice(
    client, db_session, auth_headers, test_user, test_subject, test_question_type
):
    sc = SubCategory(subject_id=1, name="常识判断", status=1, sort_order=1)
    db_session.add(sc)
    db_session.commit()
    db_session.refresh(sc)

    l2 = _point(db_session, "文化常识", level=2)
    other = _point(db_session, "其他", parent_id=l2.point_id, level=3)
    for point in (l2, other):
        point.sub_category_id = sc.id
    db_session.commit()
    _seed(db_session, test_user, "其他题", "常识判断",
          sub_category_id=sc.id, point_id=other.point_id)

    item = _display_items(client, auth_headers)["常识判断"]
    assert item["has_specific_points"] is False
    assert len(item["display_points"]) == 1
    node = item["display_points"][0]
    assert node["point_name"] == "文化常识"
    assert node["children"] == []
    assert node["is_direct"] is True
    assert node["is_other"] is True
    assert node["total_questions"] == 1
    assert node["scope"]["type"] == "l2"
    assert node["scope"]["id"] == l2.point_id


def test_global_unclassified_card_has_direct_scope(
    client, db_session, auth_headers, test_user, test_subject, test_question_type
):
    _seed(db_session, test_user, "全局未分类", "无", sub_category_id=None,
          point_id=None)

    item = _display_items(client, auth_headers)["未分类"]
    assert item["has_specific_points"] is False
    assert item["unclassified_count"] == 1
    node = item["display_points"][0]
    assert node["point_name"] == "未分类"
    assert node["is_direct"] is True
    assert node["total_questions"] == 1
    assert node["scope"]["type"] == "other"
    assert node["scope"]["sub_category_id"] is None
