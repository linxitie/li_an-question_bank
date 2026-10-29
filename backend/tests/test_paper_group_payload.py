# -*- coding: utf-8 -*-
"""复合题：考试取题必须带组材料，智能组卷必须整组抽取。"""
from app.models.models import (
    ExamPaper,
    PaperQuestionRelation,
    QuestionBank,
    QuestionGroup,
)
from app.services.paper_group_selector import (
    select_questions_with_groups,
    summarize_group_selection,
)


def _question(db_session, subject_id, type_id, creator_id, content, group_id=0, sort_order=0):
    question = QuestionBank(
        subject_id=subject_id,
        type_id=type_id,
        question_content=content,
        options=[{"key": "A", "value": "1"}, {"key": "B", "value": "2"}],
        answer="A",
        difficulty=1,
        score=2,
        creator_id=creator_id,
        status=1,
        audit_status=1,
        group_id=group_id,
        sort_order=sort_order,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


def test_paper_questions_payload_carries_group_material(
    client, db_session, test_subject, test_question_type, test_user
):
    """学生答题页拿不到题组详情接口，组材料必须随试卷题目一起返回。"""
    group = QuestionGroup(
        group_type="material",
        shared_content="<p>资料一：某地 2023 年数据</p>",
        shared_content_images='["/static/question-groups/99/a.jpg"]',
        title="资料分析",
        subject="行测",
    )
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)

    first = _question(db_session, test_subject.subject_id, test_question_type.type_id,
                      test_user.user_id, "组内小题一", group.id, 1)
    second = _question(db_session, test_subject.subject_id, test_question_type.type_id,
                       test_user.user_id, "组内小题二", group.id, 2)
    standalone = _question(db_session, test_subject.subject_id, test_question_type.type_id,
                           test_user.user_id, "独立题")

    paper = ExamPaper(
        paper_name="复合题试卷", paper_code="GROUP-001",
        subject_id=test_subject.subject_id, composition_method="MANUAL",
        creator_id=test_user.user_id, duration=60, total_score=6, difficulty=3,
        exam_type="SIMULATION", paper_type="PUBLISHED", question_count=3,
        max_attempts=1,
    )
    db_session.add(paper)
    db_session.commit()
    db_session.refresh(paper)
    for index, question in enumerate([first, second, standalone], start=1):
        db_session.add(PaperQuestionRelation(
            paper_id=paper.paper_id, question_id=question.question_id,
            question_order=index, question_score=2,
        ))
    db_session.commit()

    response = client.get(f"/api/exams/{paper.paper_id}/questions")
    assert response.status_code == 200, response.text
    rows = {q["question_id"]: q for q in response.json()["questions"]}

    assert rows[first.question_id]["group_id"] == group.id
    assert rows[first.question_id]["shared_content"] == "<p>资料一：某地 2023 年数据</p>"
    assert rows[first.question_id]["shared_content_images"] == ["/static/question-groups/99/a.jpg"]
    assert rows[second.question_id]["group_id"] == group.id
    assert rows[standalone.question_id]["group_id"] == 0
    assert rows[standalone.question_id]["shared_content"] == ""


def test_group_aware_selector_never_returns_partial_group(
    db_session, test_subject, test_question_type, test_user
):
    """命中题组必须整组带入，不能只抽到组内一题。"""
    group = QuestionGroup(group_type="material", shared_content="共享材料", subject="行测")
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)

    members = [
        _question(db_session, test_subject.subject_id, test_question_type.type_id,
                  test_user.user_id, f"组内题 {i}", group.id, i)
        for i in range(1, 4)
    ]
    for i in range(3):
        _question(db_session, test_subject.subject_id, test_question_type.type_id,
                  test_user.user_id, f"独立题 {i}")

    query = db_session.query(QuestionBank).filter(
        QuestionBank.subject_id == test_subject.subject_id,
        QuestionBank.status == 1,
        QuestionBank.audit_status == 1,
    )
    for _ in range(20):
        picked, selected_ids = select_questions_with_groups(db_session, query, 2)
        picked_group = [q for q in picked if q.group_id == group.id]
        if picked_group:
            assert {q.question_id for q in picked_group} == {q.question_id for q in members}
            assert selected_ids >= {q.question_id for q in members}


def test_group_selection_summary_flags_over_quota():
    """整组展开超配必须回传可展示的提示字段。"""
    normal = summarize_group_selection(10, 10)
    assert normal["over_quota"] is False
    assert normal["over_quota_reason"] == ""

    over = summarize_group_selection(10, 12)
    assert over["over_quota"] is True
    assert over["requested_count"] == 10
    assert over["actual_count"] == 12
    assert "整组展开" in over["over_quota_reason"]


def test_missing_material_group_keeps_members_and_marks_review(
    db_session, test_subject, test_question_type, test_user
):
    """P5：复合题缺材料也要建组保留子题关联，但不能拿题干冒充材料。"""
    from app.api.v1.catalog.question_import import _detect_and_link_composite_groups

    contents = [
        "111. 根据以下材料回答111-115题",
        "112. 小题一",
        "113. 小题二",
        "114. 小题三",
        "115. 小题四",
    ]
    questions = [
        _question(db_session, test_subject.subject_id, test_question_type.type_id,
                  test_user.user_id, content)
        for content in contents
    ]
    items = [
        {"question_content": q.question_content, "material_text": ""}
        for q in questions
    ]
    qid_by_index = {i: q.question_id for i, q in enumerate(questions)}

    stats = {"missing_material_groups": 0}
    groups_created, members_linked = _detect_and_link_composite_groups(
        db_session, items, qid_by_index, "行测", "P5 测试", stats=stats,
    )
    db_session.commit()

    assert groups_created == 1
    assert members_linked == 5
    assert stats["missing_material_groups"] == 1

    refreshed = [
        db_session.query(QuestionBank).filter(
            QuestionBank.question_id == q.question_id).first()
        for q in questions
    ]
    group_ids = {q.group_id for q in refreshed}
    assert len(group_ids) == 1 and 0 not in group_ids
    assert all(q.need_review == 1 for q in refreshed)
    group = db_session.query(QuestionGroup).filter(
        QuestionGroup.id == group_ids.pop()).first()
    assert group.shared_content == ""


def test_material_warning_points_to_head_and_range():
    """P5 预览警告：识别到复合题头但材料为空时，必须点名题号并给出处理方式。"""
    from app.api.v1.catalog.question_import import _build_material_warnings

    items = [
        {
            "question_number": 111,
            "question_content": "111. 根据以下材料回答111-115题",
            "material_text": "",
        },
        {"question_number": 112, "question_content": "112. 小题一", "material_text": ""},
        {"question_number": 113, "question_content": "113. 小题二", "material_text": ""},
        {"question_number": 114, "question_content": "114. 小题三", "material_text": ""},
        {"question_number": 115, "question_content": "115. 小题四", "material_text": ""},
    ]

    warnings = _build_material_warnings(items)

    assert len(warnings) == 1
    assert "第111题" in warnings[0]
    assert "112、113、114、115" in warnings[0]
    assert "未解析到材料" in warnings[0]
    assert "重新导入" in warnings[0]

