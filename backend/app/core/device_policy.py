# -*- coding: utf-8 -*-
"""设备准入策略（三端登录 · 唯一真源，2026-11-16 P1）。

**需求**：学生与教师可在电脑 / 平板 / 手机三端登录；**管理员仅电脑端**。

**为什么要单独成模块**：原判定写死在登录接口里一行
（`client_type in ("mobile","tablet") and user.user_type != "student"`），
需求一变（教师放行、将来可能加"平板只读"等）就要改接口代码，且无单测覆盖点。
集中到本模块后：
  · 矩阵只写一遍，登录接口/前端/文档都引用同一口径；
  · 纯函数、无 IO，可被单测穷举（3 角色 × 3 端）；
  · 运维可用环境变量调整设备端允许的角色，**不必改代码、不必发版**。

**两条硬约束**
1. `admin` 永远只能 `web`：即使环境变量写了 `admin` 也会被过滤掉（防误配把管理员放到手机端）。
2. `web` 端维持历史行为：任何角色都放行（老代码就是这么做的，避免引入回归）。

**为什么 client_type 不可信**：它由客户端自报（登录表单字段），可被脚本伪造。
所以本模块只承担**产品准入**，不是安全边界；真正的安全边界是各接口上的
`require_teacher_or_admin` / `require_admin` 等角色守卫（本方案未放宽任何接口权限）。
"""
from __future__ import annotations

import os
from typing import Dict, FrozenSet, Set

# 设备标识（与前端 device.ts 的三端命名保持一致）
DEVICES: tuple[str, ...] = ("web", "tablet", "mobile")

# 角色 → 默认可登录的设备（web 允许任何角色，见 is_role_allowed_on_device）
DEFAULT_DEVICE_ROLES: Dict[str, FrozenSet[str]] = {
    "tablet": frozenset({"student", "teacher"}),
    "mobile": frozenset({"student", "teacher"}),
}

# 永久只允许电脑端的角色（硬约束，环境变量无法放开）
ALWAYS_PC_ONLY_ROLES: FrozenSet[str] = frozenset({"admin"})

# 环境变量：设备端允许的非 admin 角色（逗号分隔），默认 student,teacher
ENV_DEVICE_ROLES = "MOBILE_TABLET_ROLES"
DEFAULT_DEVICE_ROLE_NAMES = "student,teacher"

# 拒绝时给前端的机器可读标识（body.detail 仍是人话字符串，保持老前端兼容）
DENY_CODE_DEVICE_FORBIDDEN = "DEVICE_FORBIDDEN"
DENY_ACTION_USE_PC = "use_pc_login"
PC_LOGIN_PATH = "/#/login"


def normalize_device(client_type: str | None) -> str:
    """把客户端上报的 client_type 归一化；未知值按 web 处理（与旧行为一致）。"""
    device = (client_type or "web").strip().lower()
    return device if device in DEVICES else "web"


def _env_device_roles() -> Set[str]:
    raw = os.environ.get(ENV_DEVICE_ROLES)
    if raw is None or not raw.strip():
        names = DEFAULT_DEVICE_ROLE_NAMES
    else:
        names = raw
    roles = {item.strip().lower() for item in names.split(",") if item.strip()}
    # 硬约束：admin 不在设备端；学生必须始终可用（避免误配把学生也关掉）
    roles -= ALWAYS_PC_ONLY_ROLES
    roles.add("student")
    return roles


def device_roles(client_type: str | None) -> Set[str]:
    """该设备端允许的角色集合（web 端返回空集，语义是"不限角色"）。"""
    device = normalize_device(client_type)
    if device == "web":
        return set()
    return _env_device_roles()


def is_role_allowed_on_device(role: str | None, client_type: str | None) -> bool:
    """角色能否在该设备端登录（登录接口的唯一判定入口）。"""
    device = normalize_device(client_type)
    role_name = (role or "").strip().lower()
    if device == "web":
        return True  # 电脑端维持历史行为：任何角色都可登录
    if role_name in ALWAYS_PC_ONLY_ROLES:
        return False  # 管理员恒仅电脑端
    return role_name in device_roles(device)


def denial(role: str | None, client_type: str | None) -> dict:
    """拒绝时返回的结构（message 给人看，其余给前端做引导/埋点）。"""
    device = normalize_device(client_type)
    role_name = (role or "").strip().lower()
    if role_name in ALWAYS_PC_ONLY_ROLES:
        message = "管理员仅支持电脑端登录，请改用电脑访问"
    else:
        message = "该角色暂不支持在平板/手机端登录，请改用电脑端"
    return {
        "code": DENY_CODE_DEVICE_FORBIDDEN,
        "role": role_name,
        "client_type": device,
        "message": message,
        "action": DENY_ACTION_USE_PC,
        "pc_login_path": PC_LOGIN_PATH,
    }


def policy_snapshot() -> dict:
    """当前生效矩阵（只读快照，供自检脚本、验收与文档对齐用）。"""
    roles = sorted(_env_device_roles())
    return {
        "web": "any",
        "tablet": roles,
        "mobile": roles,
        "always_pc_only": sorted(ALWAYS_PC_ONLY_ROLES),
        "env_var": ENV_DEVICE_ROLES,
        "pc_login_path": PC_LOGIN_PATH,
    }


__all__ = [
    "DEVICES",
    "ALWAYS_PC_ONLY_ROLES",
    "ENV_DEVICE_ROLES",
    "DENY_CODE_DEVICE_FORBIDDEN",
    "DENY_ACTION_USE_PC",
    "PC_LOGIN_PATH",
    "normalize_device",
    "device_roles",
    "is_role_allowed_on_device",
    "denial",
    "policy_snapshot",
]
