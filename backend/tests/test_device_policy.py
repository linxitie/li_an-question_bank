# -*- coding: utf-8 -*-
"""设备准入矩阵的纯函数单测（三端登录方案 P1，2026-11-16）。

为什么单独测矩阵：它是登录接口的唯一判定入口，需求为
「学生 / 教师三端可用、管理员仅电脑端」。矩阵写错的后果是
"管理员能从手机登录"（违反需求）或"教师被误拦"（就是本次要修的 bug）。

覆盖点：
  1. 3 角色 × 3 端的完整矩阵；
  2. web 端对任何角色都放行（含未知角色，保证历史行为不回归）；
  3. admin 硬约束：环境变量写了 admin 也放不开；
  4. MOBILE_TABLET_ROLES 可调整教师是否放行，且学生不会被误关；
  5. 未知 client_type 归一化为 web；
  6. denial() 的形状（前端引导依赖 code/action/pc_login_path）。
"""
from __future__ import annotations

import pytest

from app.core import device_policy as dp


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv(dp.ENV_DEVICE_ROLES, raising=False)


@pytest.mark.parametrize("device", ["web", "tablet", "mobile"])
def test_student_can_login_everywhere(device):
    assert dp.is_role_allowed_on_device("student", device) is True


@pytest.mark.parametrize("device", ["web", "tablet", "mobile"])
def test_teacher_can_login_everywhere(device):
    assert dp.is_role_allowed_on_device("teacher", device) is True


def test_admin_only_on_web():
    assert dp.is_role_allowed_on_device("admin", "web") is True
    assert dp.is_role_allowed_on_device("admin", "tablet") is False
    assert dp.is_role_allowed_on_device("admin", "mobile") is False


def test_web_allows_unknown_roles(monkeypatch):
    # 历史行为：电脑端不做角色过滤，将来新增角色也不会被这段代码挡住
    assert dp.is_role_allowed_on_device("auditor", "web") is True


def test_unknown_client_type_falls_back_to_web():
    assert dp.normalize_device(None) == "web"
    assert dp.normalize_device("") == "web"
    assert dp.normalize_device("WATCH") == "web"
    # 归一化后按 web 放行 admin
    assert dp.is_role_allowed_on_device("admin", "watch") is True


def test_env_can_revoke_teacher_on_devices(monkeypatch):
    monkeypatch.setenv(dp.ENV_DEVICE_ROLES, "student")
    assert dp.is_role_allowed_on_device("teacher", "tablet") is False
    assert dp.is_role_allowed_on_device("teacher", "web") is True  # 电脑端不受影响


def test_student_never_lost_even_if_env_misses_it(monkeypatch):
    monkeypatch.setenv(dp.ENV_DEVICE_ROLES, "teacher")
    assert dp.is_role_allowed_on_device("student", "mobile") is True


def test_admin_stays_pc_only_even_if_env_says_admin(monkeypatch):
    monkeypatch.setenv(dp.ENV_DEVICE_ROLES, "student,teacher,admin")
    assert dp.device_roles("tablet") == {"student", "teacher"}
    assert dp.is_role_allowed_on_device("admin", "tablet") is False


def test_denial_payload_shape():
    info = dp.denial("admin", "mobile")
    assert info["code"] == dp.DENY_CODE_DEVICE_FORBIDDEN
    assert info["action"] == dp.DENY_ACTION_USE_PC
    assert info["client_type"] == "mobile"
    assert info["role"] == "admin"
    assert "电脑端" in info["message"]
    assert info["pc_login_path"] == dp.PC_LOGIN_PATH


def test_policy_snapshot_reflects_env(monkeypatch):
    monkeypatch.setenv(dp.ENV_DEVICE_ROLES, "student")
    snap = dp.policy_snapshot()
    assert snap["web"] == "any"
    assert snap["tablet"] == ["student"]
    assert snap["always_pc_only"] == ["admin"]
