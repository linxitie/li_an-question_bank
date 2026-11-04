# -*- coding: utf-8 -*-
"""教师班级范围（共享服务）

为什么单独抽出来（2026-10-26）：
    community/forum_moderation 原先直接 `from ....models.models import Banji`，
    触发 check_module_boundary 的 cross_write 违规（Banji 属 platform 域独占表，
    由提交 5f32fdc 引入）。把班级查询下沉到 services 后，api 域不再直接持有
    他域模型的引用，边界检查通过；同时 forum / 其它域都能复用同一口径。

口径：
    教师可管理的班级 = SysUser.class_name（本人所在班）
                     ∪ Banji.teacher_id == 教师 的关联班
"""

from typing import Optional, Set

from sqlalchemy.orm import Session

from ..models.models import Banji, SysUser


def teacher_class_names(db: Session, teacher: SysUser) -> Set[str]:
    """教师可管理的班级名集合（去重、去空）。"""
    names: Set[str] = set()
    if teacher.class_name:
        names.add(teacher.class_name)
    rows = (
        db.query(Banji.class_name)
        .filter(Banji.teacher_id == teacher.user_id)
        .all()
    )
    for (name,) in rows:
        if name:
            names.add(name)
    return names


def is_my_student(db: Session, teacher: SysUser, author: Optional[SysUser]) -> bool:
    """作者是否为该教师管辖范围内的学生。"""
    if not author or author.user_type != "student" or not author.class_name:
        return False
    return author.class_name in teacher_class_names(db, teacher)
