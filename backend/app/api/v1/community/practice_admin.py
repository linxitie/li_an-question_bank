"""练习管理员授权接口（P0）。

授权链：
- 管理员 -> 教师：按科目授予 practice_admin_teacher；
- 教师练习管理员 -> 本班学生骨干：按班级授予 practice_admin_student；
- 学生骨干不能再向下授权。

P0 只实现查询与授权/撤销的骨架，反馈与论坛处理接口在 P2 接入。
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.capabilities import (
    CAPABILITY_STUDENT_PRACTICE_ADMIN,
    CAPABILITY_TEACHER_PRACTICE_ADMIN,
    get_active_capabilities,
)
from ....core.security import (
    Permission,
    assert_scope_covers,
    get_effective_permissions,
    require_permission,
)
from ....models.models import SysUser, UserCapability

router = APIRouter(prefix="/api/practice-admin", tags=["练习管理员"])
admin_router = APIRouter(prefix="/api/admin/practice-admins", tags=["练习管理员"])
teacher_router = APIRouter(prefix="/api/teacher/practice-admins", tags=["练习管理员"])


class TeacherGrantPayload(BaseModel):
    user_id: int
    subjects: List[int] = Field(default_factory=list, description="科目ID列表")
    note: Optional[str] = None


class StudentGrantPayload(BaseModel):
    user_id: int
    class_name: str
    note: Optional[str] = None


def _serialize_capability(row: UserCapability, user: Optional[SysUser]) -> Dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "username": user.nickname or user.username if user else None,
        "capability_code": row.capability_code,
        "scope_type": row.scope_type,
        "scope_id": row.scope_id,
        "scope_key": row.scope_key,
        "status": row.status,
        "granted_by": row.granted_by,
        "granted_at": row.granted_at.isoformat() if row.granted_at else None,
        "note": row.note,
    }


@admin_router.get("", summary="练习管理员列表（管理员）")
async def list_practice_admins(
    current_user: SysUser = Depends(
        require_permission(Permission.PRACTICE_ADMIN_GRANT_TEACHER)
    ),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(UserCapability)
        .filter(
            UserCapability.capability_code == CAPABILITY_TEACHER_PRACTICE_ADMIN,
            UserCapability.status == "active",
        )
        .order_by(UserCapability.granted_at.desc())
        .all()
    )
    user_ids = {row.user_id for row in rows}
    users = (
        db.query(SysUser).filter(SysUser.user_id.in_(user_ids)).all()
        if user_ids
        else []
    )
    user_map = {u.user_id: u for u in users}
    return {
        "items": [_serialize_capability(row, user_map.get(row.user_id)) for row in rows]
    }


@admin_router.post("", summary="任命教师为练习管理员（按科目）")
async def grant_teacher(
    payload: TeacherGrantPayload,
    current_user: SysUser = Depends(
        require_permission(Permission.PRACTICE_ADMIN_GRANT_TEACHER)
    ),
    db: Session = Depends(get_db),
):
    teacher = db.query(SysUser).filter(SysUser.user_id == payload.user_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="用户不存在")
    if teacher.user_type != "teacher":
        raise HTTPException(status_code=400, detail="只能任命教师")
    if not payload.subjects:
        raise HTTPException(status_code=400, detail="至少选择一个科目")

    created = 0
    for subject_id in payload.subjects:
        exists = (
            db.query(UserCapability)
            .filter(
                UserCapability.user_id == payload.user_id,
                UserCapability.capability_code == CAPABILITY_TEACHER_PRACTICE_ADMIN,
                UserCapability.scope_type == "subject",
                UserCapability.scope_id == subject_id,
            )
            .first()
        )
        if exists:
            exists.status = "active"
            exists.revoked_at = None
            continue
        db.add(
            UserCapability(
                user_id=payload.user_id,
                capability_code=CAPABILITY_TEACHER_PRACTICE_ADMIN,
                scope_type="subject",
                scope_id=subject_id,
                status="active",
                granted_by=current_user.user_id,
                note=payload.note,
            )
        )
        created += 1
    db.commit()
    return {"success": True, "created": created}


@admin_router.delete("/{user_id}", summary="撤销教师练习管理员")
async def revoke_teacher(
    user_id: int,
    current_user: SysUser = Depends(
        require_permission(Permission.PRACTICE_ADMIN_GRANT_TEACHER)
    ),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(UserCapability)
        .filter(
            UserCapability.user_id == user_id,
            UserCapability.capability_code == CAPABILITY_TEACHER_PRACTICE_ADMIN,
            UserCapability.status == "active",
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="未找到有效授权")
    from datetime import datetime

    for row in rows:
        row.status = "revoked"
        row.revoked_at = datetime.now()
    db.commit()
    return {"success": True, "revoked": len(rows)}


@teacher_router.get("", summary="本班学生骨干练习管理员列表")
async def list_student_practice_admins(
    current_user: SysUser = Depends(
        require_permission(Permission.PRACTICE_ADMIN_GRANT_STUDENT)
    ),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(UserCapability)
        .filter(
            UserCapability.capability_code == CAPABILITY_STUDENT_PRACTICE_ADMIN,
            UserCapability.status == "active",
            UserCapability.granted_by == current_user.user_id,
        )
        .order_by(UserCapability.granted_at.desc())
        .all()
    )
    return {"items": [_serialize_capability(row, None) for row in rows]}


@teacher_router.post("", summary="任命本班学生骨干为练习管理员")
async def grant_student(
    payload: StudentGrantPayload,
    current_user: SysUser = Depends(
        require_permission(Permission.PRACTICE_ADMIN_GRANT_STUDENT)
    ),
    db: Session = Depends(get_db),
):
    student = db.query(SysUser).filter(SysUser.user_id == payload.user_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="用户不存在")
    if student.user_type != "student":
        raise HTTPException(status_code=400, detail="只能任命学生")
    if not current_user.class_name:
        raise HTTPException(status_code=403, detail="当前教师未绑定班级")
    if payload.class_name != current_user.class_name:
        raise HTTPException(status_code=403, detail="只能任命本班学生")
    if student.class_name != current_user.class_name:
        raise HTTPException(status_code=403, detail="学生不属于本班")

    exists = (
        db.query(UserCapability)
        .filter(
            UserCapability.user_id == payload.user_id,
            UserCapability.capability_code == CAPABILITY_STUDENT_PRACTICE_ADMIN,
            UserCapability.scope_type == "class",
            UserCapability.scope_key == payload.class_name,
        )
        .first()
    )
    if exists:
        exists.status = "active"
        exists.revoked_at = None
    else:
        db.add(
            UserCapability(
                user_id=payload.user_id,
                capability_code=CAPABILITY_STUDENT_PRACTICE_ADMIN,
                scope_type="class",
                scope_key=current_user.class_name,
                status="active",
                granted_by=current_user.user_id,
                note=payload.note or current_user.class_name,
            )
        )
    db.commit()
    return {"success": True}


@teacher_router.delete("/{user_id}", summary="撤销本班学生骨干练习管理员")
async def revoke_student(
    user_id: int,
    current_user: SysUser = Depends(
        require_permission(Permission.PRACTICE_ADMIN_GRANT_STUDENT)
    ),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(UserCapability)
        .filter(
            UserCapability.user_id == user_id,
            UserCapability.capability_code == CAPABILITY_STUDENT_PRACTICE_ADMIN,
            UserCapability.granted_by == current_user.user_id,
            UserCapability.status == "active",
        )
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="未找到有效授权")
    from datetime import datetime

    for row in rows:
        row.status = "revoked"
        row.revoked_at = datetime.now()
    db.commit()
    return {"success": True, "revoked": len(rows)}
