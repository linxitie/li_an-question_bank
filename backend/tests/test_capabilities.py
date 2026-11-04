"""练习管理员能力包与权限测试（P0）。

覆盖：
- 未任命教师没有反馈处理权限；
- 任命后获得反馈与论坛巡版权限；
- 学生骨干获得本班反馈权限，但不含论坛举报处理权限。
"""
from app.core.capabilities import get_effective_permissions
from app.models.models import SysUser, UserCapability


def _permission_values(user, db_session):
    return [p.value for p in get_effective_permissions(user, db_session)]


def test_teacher_without_capability_has_no_feedback_permission(db_session, test_teacher):
    values = _permission_values(test_teacher, db_session)
    assert "feedback:handle" not in values
    assert "forum:report_handle" not in values


def test_teacher_with_capability_gets_feedback_permission(db_session, test_teacher):
    db_session.add(
        UserCapability(
            user_id=test_teacher.user_id,
            capability_code="practice_admin_teacher",
            scope_type="subject",
            scope_id=1,
            status="active",
        )
    )
    db_session.commit()

    values = _permission_values(test_teacher, db_session)
    assert "feedback:handle" in values
    assert "forum:report_handle" in values
    assert "forum:moderate" in values


def test_student_capability_has_no_forum_report_permission(db_session, test_user):
    db_session.add(
        UserCapability(
            user_id=test_user.user_id,
            capability_code="practice_admin_student",
            scope_type="class",
            scope_id=1,
            status="active",
        )
    )
    db_session.commit()

    values = _permission_values(test_user, db_session)
    assert "feedback:handle" in values
    assert "forum:report_handle" not in values
    assert "forum:moderate" not in values


def test_revoked_capability_is_ignored(db_session, test_teacher):
    db_session.add(
        UserCapability(
            user_id=test_teacher.user_id,
            capability_code="practice_admin_teacher",
            scope_type="subject",
            scope_id=1,
            status="revoked",
        )
    )
    db_session.commit()

    values = _permission_values(test_teacher, db_session)
    assert "feedback:handle" not in values


def test_student_cannot_access_admin_practice_admins(client, auth_headers):
    resp = client.get("/api/admin/practice-admins", headers=auth_headers)
    assert resp.status_code == 403


def test_admin_can_access_admin_practice_admins(client, admin_headers):
    resp = client.get("/api/admin/practice-admins", headers=admin_headers)
    assert resp.status_code == 200
    assert "items" in resp.json()


def test_teacher_without_capability_cannot_access_admin_practice_admins(
    client, teacher_headers
):
    resp = client.get("/api/admin/practice-admins", headers=teacher_headers)
    assert resp.status_code == 403


def test_admin_grants_teacher_by_subjects(
    client, admin_headers, db_session, test_teacher
):
    resp = client.post(
        "/api/admin/practice-admins",
        headers=admin_headers,
        json={"user_id": test_teacher.user_id, "subjects": [1, 2]},
    )
    assert resp.status_code == 200
    rows = (
        db_session.query(UserCapability)
        .filter_by(user_id=test_teacher.user_id)
        .all()
    )
    assert len(rows) == 2
    assert {row.scope_id for row in rows} == {1, 2}
    assert all(row.status == "active" for row in rows)


def test_teacher_cannot_grant_teacher(client, teacher_headers, test_admin):
    resp = client.post(
        "/api/admin/practice-admins",
        headers=teacher_headers,
        json={"user_id": test_admin.user_id, "subjects": [1]},
    )
    assert resp.status_code == 403


def test_student_cannot_grant_student(client, auth_headers, test_user, db_session):
    other = SysUser(
        user_no="student002",
        username="学生乙",
        password="x",
        phone="13600136000",
        user_type="student",
        role_level=0,
        status=1,
        class_name="一班",
    )
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)

    resp = client.post(
        "/api/teacher/practice-admins",
        headers=auth_headers,
        json={"user_id": other.user_id, "class_name": "一班"},
    )
    assert resp.status_code == 403


def test_teacher_with_capability_can_grant_own_class_student(
    client, teacher_headers, db_session, test_teacher
):
    db_session.add(
        UserCapability(
            user_id=test_teacher.user_id,
            capability_code="practice_admin_teacher",
            scope_type="subject",
            scope_id=1,
            status="active",
        )
    )
    student = SysUser(
        user_no="student003",
        username="学生丙",
        password="x",
        phone="13500135000",
        user_type="student",
        role_level=0,
        status=1,
        class_name="一班",
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)

    resp = client.post(
        "/api/teacher/practice-admins",
        headers=teacher_headers,
        json={"user_id": student.user_id, "class_name": "一班"},
    )
    assert resp.status_code == 200
    row = (
        db_session.query(UserCapability)
        .filter_by(user_id=student.user_id, capability_code="practice_admin_student")
        .first()
    )
    assert row is not None
    assert row.scope_key == "一班"


def test_teacher_cannot_grant_other_class_student(
    client, teacher_headers, db_session, test_teacher
):
    db_session.add(
        UserCapability(
            user_id=test_teacher.user_id,
            capability_code="practice_admin_teacher",
            scope_type="subject",
            scope_id=1,
            status="active",
        )
    )
    student = SysUser(
        user_no="student004",
        username="学生丁",
        password="x",
        phone="13400134000",
        user_type="student",
        role_level=0,
        status=1,
        class_name="二班",
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)

    resp = client.post(
        "/api/teacher/practice-admins",
        headers=teacher_headers,
        json={"user_id": student.user_id, "class_name": "二班"},
    )
    assert resp.status_code == 403
