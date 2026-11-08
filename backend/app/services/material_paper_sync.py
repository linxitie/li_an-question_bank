# -*- coding: utf-8 -*-
"""资料状态 → 可作答卷状态 的薄接线（P5，2026-11-08）。

分层（为什么放在 `app/services/` 而不是端点里）
----------------------------------------------
```
library/materials.py（端点：唯一能改 status 的地方）
        │  import（同域无关）
        ▼
services/material_paper_sync.py（本文件：只做取键、判可见性、拼审计文案）
        │  import（契约调用）
        ▼
api/v1/exam/contract.py（考试域：拥有 paper_type 的合法值与迁移规则）
        │
        ▼
exam_paper.paper_type
```
`scripts/gates/check_module_boundary.py` 只扫 `app/api/v1/<域>/*.py`，禁止 library 域
import `ExamPaper`（C4 就是这样被拦下并收敛出 `paper_registry` 的）。本文件让
「规则」留在考试域（契约）、「接线」落在服务层（`paper_backfill` 早已在服务层写
`exam_paper.paper_code`，同一先例），「触发」留在端点。

一致性
------
· **同事务**：本文件不 commit，调用方把「资料状态 + 卷状态 + 审计」一次提交；
· **一码多资料**：同一 `paper_code` 被多条资料引用时，任一条 `status=1` 即保持可考，
  全部不为 1 才下架（防御性实现，当前数据无此情况）；
· **ENDED 不复活**：由契约负责，本层不判断。

回滚
----
`settings.MATERIAL_PAPER_SYNC=false` → 本文件全部函数立即变成 no-op（返回 enabled=False），
不需要回滚代码、不需要重启数据库。
"""
from __future__ import annotations

from typing import Iterable, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..api.v1.exam import contract
from ..core.config import settings
from ..models.models import StudyMaterial

#: 只有这个类型的资料关联可作答卷
PAPER_TYPE = "paper"
#: 已上架状态
PUBLISHED_STATUS = 1


def code_of(material: StudyMaterial) -> str:
    """关联键：`paper_code` 优先，空则回落 `badge`（与 paper_registry 同口径）。"""
    return ((getattr(material, "paper_code", "") or "")
            or (getattr(material, "badge", "") or "")).strip()


def _has_other_published(db: Session, code: str, exclude_id: Optional[int]) -> bool:
    """同一编号是否还有**其它**已上架资料（一码多资料时保持可考）。"""
    if not code:
        return False
    query = db.query(StudyMaterial.material_id).filter(
        StudyMaterial.type == PAPER_TYPE,
        StudyMaterial.status == PUBLISHED_STATUS,
        or_(StudyMaterial.paper_code == code, StudyMaterial.badge == code),
    )
    if exclude_id is not None:
        query = query.filter(StudyMaterial.material_id != exclude_id)
    return query.first() is not None


def note_of(result: dict) -> str:
    """把契约结果翻成审计里那一句中文（空串=无话可说）。"""
    skipped = result.get("skipped")
    code = result.get("paper_code") or ""
    if result.get("changed"):
        return f"可作答卷 {code} {result['before']}→{result['after']}"
    if skipped == "no_paper":
        return "无可作答卷（题库里还没有这套卷）"
    if skipped == "ended":
        return "可作答卷已在回收站，未改动"
    return ""


def sync_material(db: Session, material: StudyMaterial) -> dict:
    """资料状态变化后同步其可作答卷（不 commit）。

    调用时机：**已把 `material.status` 改成新值、且还没 commit** 时调用，
    这样会话内的查询（autoflush）能看到新状态，可见性判断才不会用旧值。
    """
    if not settings.MATERIAL_PAPER_SYNC:
        return {"enabled": False, "skipped": "disabled", "paper_code": None,
                "changed": False, "note": ""}
    if (material.type or "") != PAPER_TYPE:
        return {"enabled": True, "skipped": "not_paper", "paper_code": None,
                "changed": False, "note": ""}

    code = code_of(material)
    visible = (material.status == PUBLISHED_STATUS
               or _has_other_published(db, code, material.material_id))
    result = contract.sync_paper_visibility(db, code, visible=visible)
    result["enabled"] = True
    result["note"] = note_of(result)
    return result


def sync_materials(db: Session, materials: Iterable[StudyMaterial]) -> list[dict]:
    """批量版本：逐条同步（数量小，保持 ORM 状态与会话一致，便于逐条写审计）。"""
    return [sync_material(db, m) for m in materials]


def note_of_many(results: list[dict]) -> str:
    """多条结果的合并审计文案（去重、非空、以「；」分隔）。"""
    seen: list[str] = []
    for item in results:
        text = item.get("note") or ""
        if text and text not in seen:
            seen.append(text)
    return "；".join(seen)
