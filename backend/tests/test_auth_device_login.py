# -*- coding: utf-8 -*-
"""登录接口的设备准入矩阵（三端登录方案 P1，2026-11-16）——走真实 HTTP 层。

为什么要有这组用例：`test_device_policy.py` 只证明"矩阵函数"对；
本文件证明**登录接口真的按矩阵执行**。拒绝时的契约（三层都要有）：
  1. 状态码 403；
  2. `detail` 仍是**人话字符串**（老前端 `.vtj` 登录页直接渲染 `errData.detail`，不能变字典）；
  3. `error.code == DEVICE_FORBIDDEN` + `error.details.action/pc_login_path`（新前端据此弹「去电脑端登录」）
     + 响应头 `X-Auth-Deny`（仓库全局错误信封对普通 HTTPException 不转发 headers，
     所以这里同时验 body 与 header，防止将来有人把异常类换回 HTTPException）。

用什么账号：conftest 已提供 `test_user / test_teacher / test_admin`
（密码 password123 / teacher123 / admin123），用 `user_no` 登录最稳定
（登录接口按 username / user_no / phone 三选一匹配）。
"""
from __future__ import annotations

import pytest

DEVICES = ("web", "tablet", "mobile")


def _login(client, user_no: str, password: str, client_type: str | None = None):
    data = {"username": user_no, "password": password}
    if client_type is not None:
        data["client_type"] = client_type
    return client.post("/api/auth/login", data=data)


@pytest.mark.parametrize("device", DEVICES)
def test_student_login_ok_on_all_devices(client, test_user, device):
    r = _login(client, test_user.user_no, "password123", device)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["user"]["user_type"] == "student"


@pytest.mark.parametrize("device", DEVICES)
def test_teacher_login_ok_on_all_devices(client, test_teacher, device):
    """本次改造的核心：教师以前在 tablet/mobile 是 403，现在必须 200。"""
    r = _login(client, test_teacher.user_no, "teacher123", device)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["user"]["user_type"] == "teacher"


def test_admin_login_ok_on_web(client, test_admin):
    r = _login(client, test_admin.user_no, "admin123", "web")
    assert r.status_code == 200, r.text
    assert r.json()["user"]["user_type"] == "admin"


@pytest.mark.parametrize("device", ["tablet", "mobile"])
def test_admin_login_rejected_on_device(client, test_admin, device):
    r = _login(client, test_admin.user_no, "admin123", device)
    assert r.status_code == 403, r.text
    body = r.json()

    # ① 老前端兼容：detail 必须是字符串
    assert isinstance(body["detail"], str), body
    assert "电脑端" in body["detail"]
    # ② 新前端可判定：错误码 + 引导信息
    assert body["error"]["code"] == "DEVICE_FORBIDDEN", body
    details = body["error"]["details"]
    assert details["action"] == "use_pc_login"
    assert details["pc_login_path"] == "/#/login"
    assert details["role"] == "admin"
    assert details["client_type"] == device
    # ③ 响应头（只有 BaseAPIException 子类才会被全局处理器转发）
    assert r.headers.get("X-Auth-Deny") == "DEVICE_FORBIDDEN"

    # 不能泄露可用的 token
    assert "access_token" not in r.text


def test_client_type_omitted_defaults_to_web(client, test_admin):
    """不传 client_type（电脑端登录页的实际行为）→ 后端按 web 处理，管理员可登录。"""
    r = _login(client, test_admin.user_no, "admin123")
    assert r.status_code == 200, r.text


def test_env_switch_can_revert_teacher_on_devices(client, test_teacher, monkeypatch):
    """运维回滚开关：MOBILE_TABLET_ROLES=student 时教师设备端恢复旧行为（不改代码）。"""
    monkeypatch.setenv("MOBILE_TABLET_ROLES", "student")
    r = _login(client, test_teacher.user_no, "teacher123", "tablet")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "DEVICE_FORBIDDEN"
    # 电脑端依旧放行
    assert _login(client, test_teacher.user_no, "teacher123", "web").status_code == 200
