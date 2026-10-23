"""按用户授予的能力包（练习管理员）。

设计要点：
- 不新增 user_type，避免牵动登录、路由与历史数据；
- 角色权限是基础，能力包是额外授权；
- 教师练习管理员按科目授权，学生骨干练习管理员按班级授权；
- 学生骨干不包含论坛举报处理权限（最小权限）。

本模块只定义能力码与权限映射，不导入 security，避免循环依赖。
"""

from typing import Dict, List

from sqlalchemy.orm import Session

from ..models.models import UserCapability

CAPABILITY_TEACHER_PRACTICE_ADMIN = "practice_admin_teacher"
CAPABILITY_STUDENT_PRACTICE_ADMIN = "practice_admin_student"

VALID_CAPABILITY_CODES = {
    CAPABILITY_TEACHER_PRACTICE_ADMIN,
    CAPABILITY_STUDENT_PRACTICE_ADMIN,
}

# 能力码 -> 权限值（字符串，由 security 统一转成 Permission 枚举）
CAPABILITY_PERMISSION_VALUES: Dict[str, List[str]] = {
    CAPABILITY_TEACHER_PRACTICE_ADMIN: [
        "feedback:read",
        "feedback:handle",
        "feedback:stats",
        "forum:moderate",
        "forum:report_handle",
        "practice_admin:grant_student",
    ],
    CAPABILITY_STUDENT_PRACTICE_ADMIN: [
        "feedback:read",
        "feedback:handle",
        "feedback:stats",
    ],
}


def get_active_capabilities(user_id: int, db: Session) -> List[UserCapability]:
    """返回用户当前生效的能力包授权。"""
    if not user_id:
        return []
    return (
        db.query(UserCapability)
        .filter(
            UserCapability.user_id == user_id,
            UserCapability.status == "active",
        )
        .all()
    )


def get_capability_permission_values(user_id: int, db: Session) -> List[str]:
    """返回用户通过能力包获得的权限值（去重）。"""
    values: List[str] = []
    for capability in get_active_capabilities(user_id, db):
        for value in CAPABILITY_PERMISSION_VALUES.get(capability.capability_code, []):
            if value not in values:
                values.append(value)
    return values


def get_effective_permissions(user, db: Session):
    """用户最终权限 = 角色权限 ∪ 能力包权限。

    延迟导入 security，避免 security -> capabilities -> security 的循环依赖。
    """
    from .security import get_user_permissions_with_db

    return get_user_permissions_with_db(user, db)
