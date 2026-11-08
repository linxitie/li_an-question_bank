# -*- coding: utf-8 -*-
"""exam 域对外契约：试卷的「可作答性」（P5，2026-11-08）。

背景
----
《试卷管理收敛_单一入口与上架即审批_方案_v1.md》§2.3 规定：`exam_paper` 降为投影，
**唯一真源是 `study_material.status`**；资料上架 → 卷 `PUBLISHED`，资料下架/删除 → 卷 `DRAFT`，
反方向不驱动。

`paper_type` 的合法值集合与迁移规则属于**考试域知识**（PENDING/APPROVED 是审批中间态、
ENDED 是回收站），所以规则写在这里、只写一次；library 域不 import `ExamPaper`
（`scripts/gates/check_module_boundary.py` 的 cross_write 规则），改由
`app/services/material_paper_sync.py` 做薄接线。

本契约**会写** `exam_paper.paper_type`（与 `catalog/contract.py` 那种只读契约不同），
因此刻意做成：
  · 不 commit —— 成败由调用方的事务决定，保证「资料状态 + 卷状态 + 审计」同生共死；
  · 返回值含 before/after/changed/skipped —— 便于调用方写审计与回包；
  · 不碰 ENDED —— 回收站里的卷不因一次上架被复活（题目关系可能已残缺）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ....models.models import ExamPaper

#: 可作答状态（学生考试链路 7 处判据都只看这个值）
VISIBLE_TYPE = "PUBLISHED"
#: 不可作答但可恢复的状态
HIDDEN_TYPE = "DRAFT"
#: 回收站卷：本契约永不改写
TERMINAL_TYPE = "ENDED"
#: 允许被本契约翻转的状态（ENDED 不在其中）
_FLIPPABLE = {"DRAFT", "PENDING", "APPROVED", VISIBLE_TYPE}


def find_paper(db: Session, paper_code: Optional[str]) -> Optional[ExamPaper]:
    """按编号取卷；空编号直接返回 None（不查全表）。"""
    code = (paper_code or "").strip()
    if not code:
        return None
    return db.query(ExamPaper).filter(ExamPaper.paper_code == code).first()


def sync_paper_visibility(db: Session, paper_code: Optional[str], *,
                          visible: bool) -> dict:
    """把一张卷的可作答性对齐到 `visible`（不 commit）。

    Args:
        db: 调用方的事务会话
        paper_code: `study_material.paper_code`（空则调用方应回落 badge）
        visible: True=可作答（PUBLISHED）；False=不可作答（DRAFT）

    返回:
        {
          "paper_id": int | None, "paper_code": str,
          "before": str | None, "after": str | None,
          "changed": bool,
          "skipped": None | "empty_code" | "no_paper" | "ended",
        }

    规则（与方案 §3 的 D-P5-1/2/3 一致）:
        · 上架：DRAFT / PENDING / APPROVED → PUBLISHED（"上架即终审"，避免"已上架但考不到"）
        · 下架：PUBLISHED → DRAFT（PENDING/APPROVED 也回 DRAFT：资料不可见即不可考）
        · ENDED：永不动，返回 skipped="ended"
        · 无卷 / 空编号：不报错，返回 skipped
    """
    code = (paper_code or "").strip()
    result = {"paper_id": None, "paper_code": code, "before": None,
              "after": None, "changed": False, "skipped": None}
    if not code:
        result["skipped"] = "empty_code"
        return result

    paper = find_paper(db, code)
    if paper is None:
        result["skipped"] = "no_paper"
        return result

    before = paper.paper_type
    result["paper_id"] = paper.paper_id
    result["before"] = before
    result["after"] = before

    if before == TERMINAL_TYPE or before not in _FLIPPABLE:
        result["skipped"] = "ended" if before == TERMINAL_TYPE else "not_flippable"
        return result

    target = VISIBLE_TYPE if visible else HIDDEN_TYPE
    if before == target:
        return result

    paper.paper_type = target
    if target == VISIBLE_TYPE:
        paper.publish_time = paper.publish_time or datetime.now()
    # update_time 由 onupdate 自动刷新，这里不手写，避免覆盖他人并发改动的时间戳
    result["after"] = target
    result["changed"] = True
    return result


def paper_is_answerable(db: Session, paper_code: Optional[str]) -> bool:
    """只读判断：该编号的卷当前是否可作答（供巡检/调试复用）。"""
    paper = find_paper(db, paper_code)
    return bool(paper and paper.paper_type == VISIBLE_TYPE)
