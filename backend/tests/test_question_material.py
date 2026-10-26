import json

import pytest

from app.core.security import get_password_hash
from app.models.models import QuestionBank, QuestionGroup, SysUser
from app.services.question_ingest.groups import upsert_question_material


def _seed_question(db, test_user, test_subject, test_question_type):
    question = QuestionBank(
        subject_id=test_subject.subject_id,
        type_id=test_question_type.type_id,
        question_content="给定材料题题干",
        answer="参考答案",
        answer_analysis="解析",
        creator_id=test_user.user_id,
        audit_status=1,
        status=1,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def _refetch(db, question_id):
    db.expire_all()
    return db.query(QuestionBank).filter(
        QuestionBank.question_id == question_id).first()


def test_create_material_creates_group_and_links_question(
        db_session, test_user, test_subject, test_question_type):
    question = _seed_question(db_session, test_user, test_subject, test_question_type)

    group = upsert_question_material(
        db_session, question, shared_content="材料正文A",
        current_user=test_user)
    db_session.commit()

    assert group is not None
    assert group.id is not None
    assert group.group_type == "material"
    assert group.shared_content == "材料正文A"
    assert group.subject == test_subject.subject_name
    assert question.group_id == group.id
    assert _refetch(db_session, question.question_id).group_id == group.id


def test_update_existing_group_keeps_same_id(
        db_session, test_user, test_subject, test_question_type):
    question = _seed_question(db_session, test_user, test_subject, test_question_type)
    group = upsert_question_material(
        db_session, question, shared_content="旧材料", current_user=test_user)
    db_session.commit()
    group_id = group.id

    updated = upsert_question_material(
        db_session, question, group_id=group_id,
        shared_content="新材料", shared_content_images=["/static/a.png"],
        current_user=test_user)
    db_session.commit()

    assert updated.id == group_id
    assert updated.shared_content == "新材料"
    assert json.loads(updated.shared_content_images) == ["/static/a.png"]
    assert _refetch(db_session, question.question_id).group_id == group_id


def test_clear_material_unlinks_question_but_keeps_group(
        db_session, test_user, test_subject, test_question_type):
    question = _seed_question(db_session, test_user, test_subject, test_question_type)
    group = upsert_question_material(
        db_session, question, shared_content="待清空材料", current_user=test_user)
    db_session.commit()
    group_id = group.id

    result = upsert_question_material(
        db_session, question, group_id=0, shared_content="",
        current_user=test_user)
    db_session.commit()

    assert result is None
    assert _refetch(db_session, question.question_id).group_id == 0
    assert db_session.query(QuestionGroup).filter(
        QuestionGroup.id == group_id).first() is not None


def test_permission_enforced_for_group_update(
        db_session, test_user, test_admin, test_subject, test_question_type):
    outsider = SysUser(
        user_no="stu999",
        username="无关学生",
        password=get_password_hash("password123"),
        phone="13700137000",
        user_type="student",
        role_level=1,
        status=1,
    )
    db_session.add(outsider)
    db_session.commit()
    db_session.refresh(outsider)

    question = _seed_question(db_session, test_user, test_subject, test_question_type)
    group = upsert_question_material(
        db_session, question, shared_content="原始材料", current_user=test_user)
    db_session.commit()

    with pytest.raises(PermissionError):
        upsert_question_material(
            db_session, question, group_id=group.id,
            shared_content="越权修改", current_user=outsider)

    creator_result = upsert_question_material(
        db_session, question, group_id=group.id,
        shared_content="创建者修改", current_user=test_user)
    assert creator_result.shared_content == "创建者修改"

    admin_result = upsert_question_material(
        db_session, question, group_id=group.id,
        shared_content="管理员修改", current_user=test_admin)
    assert admin_result.shared_content == "管理员修改"


def test_teacher_endpoint_updates_material(
        db_session, client, admin_headers, test_user,
        test_subject, test_question_type):
    question = _seed_question(db_session, test_user, test_subject, test_question_type)

    response = client.put(
        f"/api/teacher/questions/{question.question_id}",
        json={
            "shared_content": "教师补录材料",
            "shared_content_images": '["/static/teacher_1.png"]',
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    detail = client.get(f"/api/questions/{question.question_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["group_id"] > 0
    assert data["shared_content"] == "教师补录材料"
    assert json.loads(data["shared_content_images"]) == ["/static/teacher_1.png"]


def test_admin_endpoint_updates_existing_group_material(
        db_session, client, admin_headers, test_user,
        test_subject, test_question_type):
    question = _seed_question(db_session, test_user, test_subject, test_question_type)
    group = upsert_question_material(
        db_session, question, shared_content="管理员旧材料", current_user=test_user)
    db_session.commit()
    group_id = group.id

    response = client.put(
        f"/api/admin/questions/{question.question_id}",
        json={
            "group_id": group_id,
            "shared_content": "管理员新材料",
            "shared_content_images": '["/static/admin_1.png"]',
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    detail = client.get(f"/api/questions/{question.question_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["group_id"] == group_id
    assert data["shared_content"] == "管理员新材料"
    assert json.loads(data["shared_content_images"]) == ["/static/admin_1.png"]
