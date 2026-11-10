"""知识点进度：L3 汇总回 L2，未归类「其他」每科只留一条。"""
from app.models.models import KnowledgePoint, QuestionBank


def _point(db_session, subject_id, name, *, parent_id=0, level=3, sort_order=1):
    point = KnowledgePoint(
        point_name=name, subject_id=subject_id, level=level,
        parent_id=parent_id, sort_order=sort_order, status=1,
    )
    db_session.add(point)
    db_session.commit()
    db_session.refresh(point)
    return point


def _question(db_session, user, subject_id, type_id, content, point_id):
    question = QuestionBank(
        subject_id=subject_id, type_id=type_id, question_content=content,
        options=[{"key": "A", "value": "1"}], answer="A",
        point_id=point_id, creator_id=user.user_id, status=1, audit_status=1,
    )
    db_session.add(question)
    db_session.commit()
    return question


def test_progress_rolls_l3_up_to_l2_and_merges_orphan_other(
    client, db_session, auth_headers, test_user, test_subject, test_question_type
):
    sid = test_subject.subject_id
    l2 = _point(db_session, sid, "言语理解", level=2)
    specific = _point(db_session, sid, "逻辑填空", parent_id=l2.point_id)
    nested_other = _point(db_session, sid, "其他", parent_id=l2.point_id,
                          sort_order=99)
    orphan_other = _point(db_session, sid, "其他", parent_id=0, sort_order=98)

    _question(db_session, test_user, sid, test_question_type.type_id,
              "具体考点题", specific.point_id)
    _question(db_session, test_user, sid, test_question_type.type_id,
              "L2 下其他题", nested_other.point_id)
    _question(db_session, test_user, sid, test_question_type.type_id,
              "无父级其他题", orphan_other.point_id)

    response = client.get("/api/practice/knowledge-progress", headers=auth_headers)
    assert response.status_code == 200, response.text
    subjects = response.json()["subjects"]
    assert len(subjects) == 1
    rows = {row["point_name"]: row for row in subjects[0]["kps"]}

    # 具体 L3 与 canonical「其他」都汇总到父级 L2，不再单独出现。
    assert set(rows) == {"言语理解", "其他（未归类）"}
    assert rows["言语理解"]["level"] == 2
    assert rows["言语理解"]["total"] == 2
    assert rows["言语理解"]["scope"] == {
        "type": "l2", "id": l2.point_id,
        "include_descendants": True, "include_other": True,
    }
    assert rows["其他（未归类）"]["total"] == 1
    assert rows["其他（未归类）"]["scope"] == {
        "type": "other", "id": 0, "sub_category_id": None,
    }
