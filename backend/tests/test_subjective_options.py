"""主观题序列化：options=[] 且 is_subjective=true，不补占位选项。"""
from types import SimpleNamespace

from app.models.models import QuestionBank, QuestionType, SubCategory
from app.services.option_utils import is_subjective_question


def _qtype(is_objective):
    return SimpleNamespace(is_objective=is_objective)


def test_is_subjective_question_helper():
    assert is_subjective_question(SimpleNamespace(), _qtype(0)) is True
    assert is_subjective_question(SimpleNamespace(), _qtype(1)) is False
    assert is_subjective_question(SimpleNamespace()) is False
    assert is_subjective_question(SimpleNamespace(type=None)) is False


def _seed_question(db_session, user, *, subject_id, type_id, content,
                   options, answer, score, sub_category_id):
    question = QuestionBank(
        subject_id=subject_id,
        type_id=type_id,
        question_content=content,
        options=options,
        answer=answer,
        difficulty=1,
        score=score,
        sub_category_id=sub_category_id,
        creator_id=user.user_id,
        status=1,
        audit_status=1,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


def test_subjective_question_serialized_without_options(
    client, db_session, auth_headers, test_user, test_subject, test_question_type
):
    sub_category = SubCategory(
        subject_id=test_subject.subject_id, name="申论写作", status=1, sort_order=1
    )
    subjective_type = QuestionType(
        type_name="写作", type_code="WRITING", subject_id=test_subject.subject_id,
        is_objective=0,
    )
    db_session.add_all([sub_category, subjective_type])
    db_session.commit()
    db_session.refresh(sub_category)
    db_session.refresh(subjective_type)

    subjective = _seed_question(
        db_session, test_user,
        subject_id=test_subject.subject_id,
        type_id=subjective_type.type_id,
        content="请以'基层治理'为题写一篇议论文。",
        options=[{"key": "A", "value": "(待补充)"}],
        answer="范文",
        score=40,
        sub_category_id=sub_category.id,
    )
    objective = _seed_question(
        db_session, test_user,
        subject_id=test_subject.subject_id,
        type_id=test_question_type.type_id,
        content="以下哪项正确？",
        options=[
            {"key": "A", "value": "1"},
            {"key": "B", "value": "2"},
            {"key": "C", "value": "3"},
            {"key": "D", "value": "4"},
        ],
        answer="A",
        score=2,
        sub_category_id=sub_category.id,
    )

    response = client.get(
        f"/api/quick-practice/questions?knowledge_point_ids={sub_category.id}"
        "&bySubCategory=true&limit=10",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    data = response.json()

    items = {item["question_id"]: item for item in data["items"]}
    assert len(items) == 2

    sub_item = items[subjective.question_id]
    assert sub_item["options"] == []
    assert sub_item["is_subjective"] is True
    assert sub_item["score"] == 40.0
    assert "(待补充)" not in str(sub_item["options"])

    obj_item = items[objective.question_id]
    assert obj_item["is_subjective"] is False
    assert len(obj_item["options"]) == 4
    assert [o["key"] for o in obj_item["options"]] == ["A", "B", "C", "D"]
