# -*- coding: utf-8 -*-
"""管理员端权限引擎、用户生命周期与批量撤销回归。"""
import json
from datetime import datetime, timedelta

from app.core.security import (
    Permission,
    create_access_token,
    get_effective_permissions,
    get_password_hash,
    permission_catalog,
)
from app.models.models import (
    PermissionChangeBatch,
    SysUser,
    UserPermissionOverride,
)


def _override(db_session, user_id, code, effect, expires_at=None, status="active"):
    row = UserPermissionOverride(
        user_id=user_id,
        permission_code=code,
        effect=effect,
        scope_type="global",
        scope_id=0,
        scope_key="",
        status=status,
        reason="测试",
        granted_at=datetime.now(),
        expires_at=expires_at,
    )
    db_session.add(row)
    db_session.commit()
    return row


def _grant_single_permission(client, headers, user_id, code="system:monitor"):
    response = client.put(
        f"/api/admin/users/{user_id}/permissions",
        headers=headers,
        json={
            "reason": "单用户撤销回归",
            "changes": [{"permission_code": code, "effect": "grant"}],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["batch_id"]


def test_permission_catalog_covers_every_permission():
    catalog = permission_catalog()
    assert len(catalog) == len(Permission) == 33
    codes = {item["code"] for item in catalog}
    assert codes == {p.value for p in Permission}
    assert all(item["label"] and item["group"] for item in catalog)


def test_effective_permissions_apply_grant_and_deny(db_session, test_teacher):
    baseline = set(get_effective_permissions(test_teacher, db_session))
    assert Permission.SYSTEM_MONITOR not in baseline
    _override(db_session, test_teacher.user_id, Permission.SYSTEM_MONITOR.value, "grant")
    assert Permission.SYSTEM_MONITOR in get_effective_permissions(test_teacher, db_session)

    if baseline:
        denied = sorted(p.value for p in baseline)[0]
        _override(db_session, test_teacher.user_id, denied, "deny")
        assert Permission(denied) not in get_effective_permissions(test_teacher, db_session)


def test_expired_override_is_ignored(db_session, test_teacher):
    _override(
        db_session,
        test_teacher.user_id,
        Permission.SYSTEM_MONITOR.value,
        "grant",
        expires_at=datetime.now() - timedelta(minutes=1),
    )
    assert Permission.SYSTEM_MONITOR not in get_effective_permissions(test_teacher, db_session)


def test_super_admin_protected_permissions_ignore_deny(db_session, test_admin):
    _override(
        db_session,
        test_admin.user_id,
        Permission.USER_MANAGE.value,
        "deny",
    )
    assert Permission.USER_MANAGE in get_effective_permissions(test_admin, db_session)


def test_single_user_permission_tristate_and_batch(
    client, db_session, admin_headers, test_teacher
):
    url = f"/api/admin/users/{test_teacher.user_id}/permissions"
    granted = client.put(
        url,
        headers=admin_headers,
        json={
            "reason": "三态回归",
            "changes": [{"permission_code": "system:monitor", "effect": "grant"}],
        },
    )
    assert granted.status_code == 200, granted.text
    assert granted.json()["batch_id"]

    detail = client.get(url, headers=admin_headers)
    assert detail.status_code == 200, detail.text
    item = next(
        i for i in detail.json()["items"] if i["permission_code"] == "system:monitor"
    )
    assert item["state"] == "grant" and item["effective"] is True

    inherited = client.put(
        url,
        headers=admin_headers,
        json={
            "reason": "恢复继承",
            "changes": [{"permission_code": "system:monitor", "effect": "inherit"}],
        },
    )
    assert inherited.status_code == 200, inherited.text
    detail = client.get(url, headers=admin_headers)
    item = next(
        i for i in detail.json()["items"] if i["permission_code"] == "system:monitor"
    )
    assert item["state"] == "inherit" and item["effective"] is False


def test_non_super_cannot_grant_permission_it_lacks(
    client, db_session, test_teacher
):
    from app.core.security import create_access_token

    operator = SysUser(
        user_no="admin002", username="普通管理员", password="x",
        phone="13900139001", user_type="admin", role_level=2, status=1,
    )
    db_session.add(operator)
    db_session.commit()
    token = create_access_token(data={"user_id": operator.user_id, "user_no": operator.user_no})
    response = client.put(
        f"/api/admin/users/{test_teacher.user_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "reason": "越权测试",
            "changes": [{"permission_code": "data:backup", "effect": "grant"}],
        },
    )
    assert response.status_code == 403, response.text


def test_self_and_last_super_cannot_be_disabled(
    client, db_session, admin_headers, test_admin
):
    response = client.put(
        f"/api/admin/users/{test_admin.user_id}/disable",
        headers=admin_headers,
        json={"is_disabled": 1, "reason": "误操作"},
    )
    assert response.status_code == 403, response.text


def test_soft_deleted_user_cannot_login(client, db_session, test_user):
    test_user.is_deleted = 1
    db_session.commit()
    response = client.post("/api/auth/login", data={
        "username": test_user.user_no,
        "password": "password123",
    })
    assert response.status_code == 403, response.text


def test_permission_batch_preview_apply_and_undo(
    client, db_session, admin_headers, test_teacher
):
    payload = {
        "target": {"mode": "ids", "user_ids": [test_teacher.user_id], "expected_count": 1},
        "operation": "grant",
        "permissions": ["system:monitor"],
        "reason": "期中阅卷临时授权",
        "dry_run": True,
    }
    preview = client.post(
        "/api/admin/users/permissions/preview", headers=admin_headers, json=payload
    )
    assert preview.status_code == 200, preview.text
    preview_body = preview.json()
    assert preview_body["dry_run"] is True
    assert preview_body["conflicts"] == []
    assert preview_body["items"][0]["after"] == "grant"

    applied = client.post(
        "/api/admin/users/permissions/apply", headers=admin_headers, json=payload
    )
    assert applied.status_code == 200, applied.text
    batch_id = applied.json()["batch_id"]
    assert batch_id
    assert Permission.SYSTEM_MONITOR in get_effective_permissions(test_teacher, db_session)

    audit = client.get("/api/admin/permission-audit", headers=admin_headers)
    assert audit.status_code == 200, audit.text
    record = next(i for i in audit.json()["items"] if i["batch_id"] == batch_id)
    assert record["can_undo"] is True

    undone = client.post(
        f"/api/admin/permission-batches/{batch_id}/undo",
        headers=admin_headers,
        json={"reason": "授权填错"},
    )
    assert undone.status_code == 200, undone.text
    db_session.expire_all()
    assert Permission.SYSTEM_MONITOR not in get_effective_permissions(test_teacher, db_session)


def test_single_user_permission_batch_can_be_undone(
    client, db_session, admin_headers, test_teacher
):
    batch_id = _grant_single_permission(client, admin_headers, test_teacher.user_id)
    db_session.expire_all()
    assert Permission.SYSTEM_MONITOR in get_effective_permissions(test_teacher, db_session)

    undone = client.post(
        f"/api/admin/permission-batches/{batch_id}/undo",
        headers=admin_headers,
        json={"reason": "撤销单用户授权"},
    )
    assert undone.status_code == 200, undone.text
    db_session.expire_all()
    assert Permission.SYSTEM_MONITOR not in get_effective_permissions(test_teacher, db_session)


def test_single_user_undo_supports_legacy_snapshot_without_user_id(
    client, db_session, admin_headers, test_teacher
):
    batch_id = _grant_single_permission(client, admin_headers, test_teacher.user_id)
    batch = db_session.query(PermissionChangeBatch).filter(
        PermissionChangeBatch.batch_id == batch_id
    ).first()
    before = json.loads(batch.before_json)
    after = json.loads(batch.after_json)
    before.pop("user_id", None)
    after.pop("user_id", None)
    batch.before_json = json.dumps(before)
    batch.after_json = json.dumps(after)
    db_session.commit()

    undone = client.post(
        f"/api/admin/permission-batches/{batch_id}/undo",
        headers=admin_headers,
        json={"reason": "兼容旧批次撤销"},
    )
    assert undone.status_code == 200, undone.text
    db_session.expire_all()
    assert Permission.SYSTEM_MONITOR not in get_effective_permissions(test_teacher, db_session)

def test_role_template_update_can_be_undone(client, db_session, admin_headers):
    roles = client.get("/api/admin/permissions", headers=admin_headers)
    assert roles.status_code == 200, roles.text
    teacher = roles.json()["roles"]["teacher"]["permissions"]
    removed = "question:create" if "question:create" in teacher else teacher[0]
    target = [code for code in teacher if code != removed]

    saved = client.put(
        "/api/admin/permissions",
        headers=admin_headers,
        json={"role": "teacher", "permissions": target, "reason": "模板撤销回归"},
    )
    assert saved.status_code == 200, saved.text
    batch_id = saved.json()["batch_id"]
    after_save = client.get("/api/admin/permissions", headers=admin_headers)
    assert removed not in after_save.json()["roles"]["teacher"]["permissions"], (saved.json(), after_save.json()["roles"]["teacher"]["permissions"], db_session.query(__import__("app.models.models", fromlist=["SysConfig"]).SysConfig).filter_by(config_key="role_permissions_teacher").first().config_value)

    undone = client.post(
        f"/api/admin/permission-batches/{batch_id}/undo",
        headers=admin_headers,
        json={"reason": "恢复模板"},
    )
    assert undone.status_code == 200, undone.text
    restored = client.get("/api/admin/permissions", headers=admin_headers)
    assert removed in restored.json()["roles"]["teacher"]["permissions"]

def test_user_list_exposes_avatar(client, db_session, admin_headers, test_user):
    test_user.avatar = "/uploads/avatars/avatar_test.png"
    db_session.commit()
    response = client.get("/api/admin/users", headers=admin_headers)
    assert response.status_code == 200, response.text
    item = next(i for i in response.json()["items"] if i["user_id"] == test_user.user_id)
    assert item["avatar"] == "/uploads/avatars/avatar_test.png"


def test_batch_purge_anonymizes_recycle_bin_user(
    client, db_session, admin_headers, test_user
):
    test_user.is_deleted = 1
    test_user.deleted_at = datetime.now()
    test_user.avatar = "/uploads/avatars/avatar_test.png"
    test_user.email = "pii@example.com"
    db_session.commit()

    response = client.post(
        "/api/admin/users/batch",
        headers=admin_headers,
        json={
            "action": "purge",
            "target": {
                "mode": "ids",
                "user_ids": [test_user.user_id],
                "expected_count": 1,
            },
            "payload": {"reason": "批量注销回归"},
            "expected_count": 1,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["affected"] == 1

    db_session.refresh(test_user)
    assert test_user.is_deleted == 2
    assert test_user.username == f"deleted_{test_user.user_id}"
    assert test_user.user_no == f"deleted_{test_user.user_id}"
    assert test_user.phone == ""
    assert test_user.email is None
    assert test_user.avatar is None
    assert test_user.role_level == 0


def test_batch_purge_requires_super_admin(
    client, db_session, test_teacher, test_user
):
    test_user.is_deleted = 1
    db_session.commit()
    low_admin = SysUser(
        user_no="admin002",
        username="普通管理员",
        password=get_password_hash("admin123"),
        phone="13900139001",
        user_type="admin",
        role_level=2,
        status=1,
    )
    db_session.add(low_admin)
    db_session.commit()
    token = create_access_token(
        data={"user_id": low_admin.user_id, "user_no": low_admin.user_no}
    )
    response = client.post(
        "/api/admin/users/batch",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "action": "purge",
            "target": {
                "mode": "ids",
                "user_ids": [test_user.user_id],
                "expected_count": 1,
            },
            "payload": {"reason": "越权注销"},
            "expected_count": 1,
        },
    )
    assert response.status_code == 403, response.text


def test_batch_purge_rejects_user_outside_recycle_bin(
    client, db_session, admin_headers, test_user
):
    assert (test_user.is_deleted or 0) == 0
    response = client.post(
        "/api/admin/users/batch",
        headers=admin_headers,
        json={
            "action": "purge",
            "target": {
                "mode": "ids",
                "user_ids": [test_user.user_id],
                "expected_count": 1,
            },
            "payload": {"reason": "非回收站注销"},
            "expected_count": 1,
        },
    )
    assert response.status_code == 422, response.text
