# -*- coding: utf-8 -*-
"""catalog 域对外契约：分类法（子类 / 考点）只读访问。

背景
----
备考资料（library 域）需要「子类词表 + 考点表」来做分类校验与考点挂接，
但 `sub_categories` / `knowledge_point` 属 catalog 域。按 P4.1 模块边界约定
（`scripts/gates/check_module_boundary.py`），跨域不得直接 import 他域 ORM 模型，
必须经由该域的契约模块。

本契约**只读**：不新增/修改/删除任何分类法数据，写操作仍由 catalog 域负责。
"""
from typing import Dict, List, Optional, Tuple

from ....models.models import KnowledgePoint, SubCategory

# 科目字符串 ↔ subject_id（question_subject 表里 fallback 名称也叫 auto_<科目>）
SUBJECT_IDS = {"xingce": 1, "shenlun": 2, "gongzhuan": 3}


def category_names(db, subject: str) -> List[str]:
    """某科目的合法子类名（按 sort_order）。"""
    sid = SUBJECT_IDS.get(subject)
    if not sid:
        return []
    rows = (db.query(SubCategory)
            .filter(SubCategory.subject_id == sid, SubCategory.status == 1)
            .order_by(SubCategory.sort_order).all())
    return [(r.name or "").strip() for r in rows]


def category_name_by_id(db, category_id) -> Optional[str]:
    if not category_id:
        return None
    row = db.query(SubCategory).filter(SubCategory.id == category_id).first()
    return (row.name or "").strip() if row else None


def point_rows(db, subject: str) -> List[KnowledgePoint]:
    """某科目的考点行（level 未做过滤：现行 94 条统一是 level=2 的扁平考点）。"""
    sid = SUBJECT_IDS.get(subject)
    if not sid:
        return []
    return (db.query(KnowledgePoint)
            .filter(KnowledgePoint.subject_id == sid,
                    KnowledgePoint.status == 1)
            .order_by(KnowledgePoint.sub_category_id, KnowledgePoint.sort_order)
            .all())


def point_map(db, subject: str) -> Dict[str, Tuple[int, Optional[int]]]:
    """考点名 → (point_id, sub_category_id)。"""
    return {((r.point_name or "").strip()): (r.point_id, r.sub_category_id)
            for r in point_rows(db, subject)}


def point_id_by_name(db, subject: str, name: str) -> Optional[int]:
    name = (name or "").strip()
    if not name:
        return None
    hit = point_map(db, subject).get(name)
    return hit[0] if hit else None


def point_by_id(db, subject: str, point_id) -> Optional[KnowledgePoint]:
    try:
        pid = int(point_id)
    except (TypeError, ValueError):
        return None
    for r in point_rows(db, subject):
        if r.point_id == pid:
            return r
    return None


def point_name(db, subject: str, point_id) -> Optional[str]:
    row = point_by_id(db, subject, point_id)
    return (row.point_name or "").strip() if row else None


def category_of_point(db, subject: str, point_id) -> Optional[str]:
    """考点所属子类名（分类法第三层反推第二层）。"""
    row = point_by_id(db, subject, point_id)
    if not row:
        return None
    return category_name_by_id(db, row.sub_category_id)


def point_belongs_to(db, subject: str, point_id) -> bool:
    return point_by_id(db, subject, point_id) is not None
