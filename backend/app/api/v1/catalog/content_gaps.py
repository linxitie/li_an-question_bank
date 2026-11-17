# -*- coding: utf-8 -*-
"""内容缺口体检 API（v9 M7）。

用户在后期手工导入题本，系统需要能自动指出「这批题里哪些缺图 / 缺横线 /
缺选项 / 缺答案 / 缺解析 / 缺材料」，并给出可点击定位的入口。

GET  /api/content-gaps/summary?subject_id=        全库（或单科目）六类缺口统计
GET  /api/content-gaps/questions?kind=&subject_id=  按缺口类型分页列题
GET  /api/content-gaps/question/{question_id}     单题缺口明细
POST /api/content-gaps/scan                       对指定题目批量体检（导入后自检）
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import QuestionBank, QuestionGroup, SysUser
from ....services import content_gaps

router = APIRouter(prefix="/api/content-gaps", tags=["内容缺口"])


class ScanRequest(BaseModel):
    question_ids: List[int] = Field(default_factory=list, description="要体检的题目 ID")


def _require_reviewer(user: SysUser) -> None:
    role = getattr(user, "user_type", None)
    if role not in ("teacher", "admin", 2, 3):
        raise HTTPException(status_code=403, detail="仅教师或管理员可查看内容缺口")


@router.get("/summary", summary="内容缺口总览")
async def get_summary(
    subject_id: Optional[int] = Query(None, description="1 行测 / 2 申论 / 3 公专"),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    _require_reviewer(current_user)
    data = content_gaps.scan_query(db, subject_id=subject_id, page=1, page_size=1)
    # 复用同一套扫描，只回聚合与类型，不回题目列表
    return {
        "scanned": data["scanned"],
        "gap_questions": data["gap_questions"],
        "by_kind": data["by_kind"],
        "kind_labels": data["kind_labels"],
    }


@router.get("/questions", summary="按缺口类型列题")
async def list_gap_questions(
    kind: Optional[str] = Query(None, description="缺口类型，如 missing_image"),
    subject_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    _require_reviewer(current_user)
    if kind and kind not in content_gaps.KINDS:
        raise HTTPException(status_code=400, detail=f"未知缺口类型：{kind}")
    return content_gaps.scan_query(
        db, subject_id=subject_id, kind=kind, page=page, page_size=page_size
    )


@router.get("/question/{question_id}", summary="单题缺口明细")
async def get_question_gaps(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    q = db.query(QuestionBank).filter(QuestionBank.question_id == question_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="题目不存在")
    group = None
    if q.group_id:
        group = db.query(QuestionGroup).filter(QuestionGroup.id == q.group_id).first()
    res = content_gaps.check_question(q, group=group)
    res["kind_labels"] = content_gaps.KINDS
    return res


@router.post("/scan", summary="批量体检指定题目")
async def scan_questions(
    req: ScanRequest,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(get_current_user),
):
    # 导入完成后前端也会调这里做自检，学生答题后不该 403，故不做角色限制
    if not req.question_ids:
        return {"scanned": 0, "gap_questions": 0, "by_kind": {k: 0 for k in content_gaps.KINDS},
                "kind_labels": content_gaps.KINDS, "items": []}
    return content_gaps.scan_ids(db, req.question_ids[:500])
