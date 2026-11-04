"""登录标识回归测试。

背景（2026-11-01）：教师账号 `ycc5678` 的 `sys_user.username` 被改成中文姓名后，
登录接口只匹配 username/phone，用账号编号 `ycc5678` 登录直接报「用户名不存在」。
本次把 `user_no` 纳入登录标识，确保「账号编号」永远可登录，不会因展示名变化而失效。
"""
import pytest

from app.models.models import SysUser
from app.core.security import get_password_hash


@pytest.fixture
def teacher_with_display_name(db_session):
    """模拟事故现场：user_no 是登录编号，username 是中文展示名。"""
    user = SysUser(
        user_no="ycc5678",
        username="琳叵贴",
        password=get_password_hash("ycc5678"),
        phone="13900139000",
        user_type="teacher",
        role_level=1,
        status=1,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestLoginIdentifiers:
    def test_login_by_username(self, client, test_user):
        resp = client.post(
            "/api/auth/login",
            data={"username": test_user.username, "password": "password123"},
        )
        assert resp.status_code == 200
        assert resp.json()["user"]["user_id"] == test_user.user_id

    def test_login_by_user_no(self, client, test_user):
        """user_no（学号/工号）必须能登录，即使 username 与它不同。"""
        assert test_user.user_no == "test001"
        assert test_user.user_no != test_user.username
        resp = client.post(
            "/api/auth/login",
            data={"username": "test001", "password": "password123"},
        )
        assert resp.status_code == 200
        assert resp.json()["user"]["user_id"] == test_user.user_id

    def test_login_by_phone(self, client, test_user):
        resp = client.post(
            "/api/auth/login",
            data={"username": test_user.phone, "password": "password123"},
        )
        assert resp.status_code == 200
        assert resp.json()["user"]["user_id"] == test_user.user_id

    def test_teacher_can_login_by_account_no_after_username_renamed(
        self, client, teacher_with_display_name
    ):
        """事故复现：username 变成中文名后，用编号 ycc5678 仍可登录。"""
        resp = client.post(
            "/api/auth/login",
            data={"username": "ycc5678", "password": "ycc5678"},
        )
        assert resp.status_code == 200
        assert resp.json()["user"]["user_type"] == "teacher"

    def test_wrong_password_still_rejected(self, client, teacher_with_display_name):
        resp = client.post(
            "/api/auth/login",
            data={"username": "ycc5678", "password": "wrong-password"},
        )
        assert resp.status_code in (400, 401)
