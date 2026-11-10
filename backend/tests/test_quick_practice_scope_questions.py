"""快速练习 scope 抽题 + 题组完整展开（设计 D3/D5）。"""
from app.models.models import KnowledgePoint, QuestionBank, SubCategory


def _seed(db_session, user, content, subcategory, *, sub_category_id=None,
          point_id=None, group_id=0, sort_order=0, year=2025, type_id=1,
          difficulty=2, subject_id=1):
    question = QuestionBank(
        subject_id=subject_id, type_id=type_id, question_content=content,
        options=[{"key": "A", "value": "1"}], answer="A",
        difficulty=difficulty, score=2, year=year,
        xingce_subcategory=subcategory, sub_category_id=sub_category_id,
        point_id=point_id, group_id=group_id, sort_order=sort_order,
        creator_id=user.user_id, status=1, audit_status=1,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


def _point(db_session, name, parent_id=0, level=2, sub_category_id=None,
           sort_order=1):
    point = KnowledgePoint(
        point_name=name, subject_id=1, sub_category_id=sub_category_id,
        level=level, parent_id=parent_id, sort_order=sort_order,
    )
    db_session.add(point)
    db_session.commit()
    db_session.refresh(point)
    return point


def _fixture(db_session, user):
    sc = SubCategory(subject_id=1, name="资料分析", status=1, sort_order=1)
    db_session.add(sc)
    db_session.commit()
    db_session.refresh(sc)

    l2 = _point(db_session, "增长", level=2, sub_category_id=sc.id)
    specific = _point(db_session, "增长率", parent_id=l2.point_id, level=3,
                      sub_category_id=sc.id, sort_order=2)
    other = _point(db_session, "其他", parent_id=l2.point_id, level=3,
                   sub_category_id=sc.id, sort_order=99)

    direct = _seed(db_session, user, "L2 直挂", "资料分析",
                   sub_category_id=sc.id, point_id=l2.point_id, year=2025)
    spec = _seed(db_session, user, "具体考点", "资料分析",
                 sub_category_id=sc.id, point_id=specific.point_id, year=2024)
    other_q = _seed(db_session, user, "其他考点", "资料分析",
                    sub_category_id=sc.id, point_id=other.point_id, year=2023)
    orphan = _seed(db_session, user, "未归类", "资料分析",
                   sub_category_id=sc.id, point_id=None, year=2022)
    return sc, l2, specific, other, direct, spec, other_q, orphan


def _ids(response):
    assert response.status_code == 200, response.text
    return {item["question_id"] for item in response.json()["items"]}


def test_scope_l3_and_l2_descendants(
    client, db_session, auth_headers, test_user, test_subject, test_question_type
):
    sc, l2, specific, other, direct, spec, other_q, orphan = _fixture(
        db_session, test_user
    )

    assert _ids(client.get(
        "/api/quick-practice/questions?scope=l3&pointId=%s&limit=20" % specific.point_id,
        headers=auth_headers,
    )) == {spec.question_id}

    l2_ids = _ids(client.get(
        "/api/quick-practice/questions?scope=l2&l2Id=%s&limit=20" % l2.point_id,
        headers=auth_headers,
    ))
    assert l2_ids == {direct.question_id, spec.question_id}

    l2_with_other = _ids(client.get(
        "/api/quick-practice/questions?scope=l2&l2Id=%s&includeOther=true&limit=20"
        % l2.point_id,
        headers=auth_headers,
    ))
    assert l2_with_other == {
        direct.question_id, spec.question_id, other_q.question_id,
    }


def test_scope_other_collects_null_other_and_l2_direct_only(
    client, db_session, auth_headers, test_user, test_subject, test_question_type
):
    sc, l2, specific, other, direct, spec, other_q, orphan = _fixture(
        db_session, test_user
    )
    # 跨科未归类题用于验证 scope=other 必须限定当前科目。
    foreign_orphan = _seed(db_session, test_user, "公专未归类", "常识判断",
                           point_id=None, year=2022, subject_id=3)

    ids = _ids(client.get(
        "/api/quick-practice/questions?scope=other&subCategoryId=%s&limit=20"
        % sc.id,
        headers=auth_headers,
    ))
    # 子科目级「其他（未归类）」只收真正未归类的题；canonical「其他」
    # 挂在 L2 下，不能重复计入。
    assert ids == {orphan.question_id}
    assert spec.question_id not in ids
    assert direct.question_id not in ids
    assert other_q.question_id not in ids
    assert foreign_orphan.question_id not in ids

    l2_other_ids = _ids(client.get(
        "/api/quick-practice/questions?scope=other&l2Id=%s&limit=20" % l2.point_id,
        headers=auth_headers,
    ))
    assert l2_other_ids == {direct.question_id, other_q.question_id}, (
        direct.question_id, spec.question_id, other_q.question_id,
        orphan.question_id, l2.point_id, specific.point_id, other.point_id,
    )


def test_scope_subcategory_returns_all(
    client, db_session, auth_headers, test_user, test_subject, test_question_type
):
    sc, l2, specific, other, direct, spec, other_q, orphan = _fixture(
        db_session, test_user
    )
    ids = _ids(client.get(
        "/api/quick-practice/questions?scope=subcategory&subCategoryId=%s&limit=20"
        % sc.id,
        headers=auth_headers,
    ))
    assert ids == {
        direct.question_id, spec.question_id, other_q.question_id,
        orphan.question_id,
    }


def test_group_expands_even_when_limit_is_one(
    client, db_session, auth_headers, test_user, test_subject, test_question_type
):
    sc = SubCategory(subject_id=1, name="判断推理", status=1, sort_order=1)
    db_session.add(sc)
    db_session.commit()
    db_session.refresh(sc)
    point = _point(db_session, "图形推理", level=3, sub_category_id=sc.id)
    other = _point(db_session, "其他", level=3, sub_category_id=sc.id,
                   parent_id=point.point_id)

    head = _seed(db_session, test_user, "题组第1题", "判断推理",
                 sub_category_id=sc.id, point_id=point.point_id, group_id=77,
                 sort_order=1)
    brother = _seed(db_session, test_user, "题组第2题", "判断推理",
                    sub_category_id=sc.id, point_id=other.point_id, group_id=77,
                    sort_order=2)

    response = client.get(
        "/api/quick-practice/questions?scope=l3&pointId=%s&limit=1"
        % point.point_id,
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["requested_limit"] == 1
    assert data["actual_count"] == 2
    assert data["group_expanded"] is True
    assert [item["question_id"] for item in data["items"]] == [
        head.question_id, brother.question_id,
    ]
