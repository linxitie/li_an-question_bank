# -*- coding: utf-8 -*-
"""A2（2026-11-08）：把一份「试卷类资料」变成题库里的可作答卷。

**解决什么问题**：上传试卷只落 `study_material(status=0)` + 原件 + `paper_code`
（`paper_code` 是 C2a 从文件名解析出来的人读编号，如 `GZ-2024-GK-T`），
**不会建 `exam_paper`**。于是学生端永远看不到上传的真题（#127 就是活样本）。
本服务补上"资料 → 卷"这一步，其余链路（导题挂关系 → 上架 → P5 自动 PUBLISHED）复用现有能力。

**幂等**：以 `paper_code` 为唯一键——已存在就原样返回（`created=false`），
绝不覆盖已有卷的状态/题目（避免把已发布的卷改成草稿）。

**为什么不自动建**：每份试卷资料都凭空多一张 0 题草稿卷会把"题库"塞满空卷；
所以由管理员在列表里点「建卷」显式触发（D-A2-1 的推荐默认）。

**分层**：本文件属服务层，可以直接 import `ExamPaper`（门禁只扫 `api/v1/<域>`）；
库里已有 `paper_backfill`（卷→资料）与 `material_paper_sync`（资料状态→卷状态）两个先例。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from ..api.v1.catalog.contract import SUBJECT_IDS
from ..models.models import ExamPaper, StudyMaterial
from .paper_meta_edit import load_override, merge_meta

#: 只有这个类型能建可作答卷
PAPER_TYPE = "paper"
#: 资料没有元数据时的兜底（与既有卷保持一致：120 分钟 / 100 分）
DEFAULT_DURATION = 120
DEFAULT_TOTAL_SCORE = 100.0


def paper_code_of(material: StudyMaterial) -> str:
    """关联键：`paper_code` 优先，空则回落 `badge`（与 paper_registry / P5 同口径）。"""
    return ((getattr(material, "paper_code", "") or "")
            or (getattr(material, "badge", "") or "")).strip()


def find_paper(db: Session, code: str) -> Optional[ExamPaper]:
    code = (code or "").strip()
    if not code:
        return None
    return db.query(ExamPaper).filter(ExamPaper.paper_code == code).first()


def ensure_paper_for_material(db: Session, material: StudyMaterial, *,
                              actor_id: Optional[int] = None,
                              paper_name: Optional[str] = None) -> dict:
    """建卷（或复用同编号的卷）。**不 commit**，由调用方决定事务。

    Args:
        paper_name: 只影响**新建**时的卷名。P1 上传即建卷按用户决策 ② 传「文件名去扩展名」，
            避免管理端填的展示标题（可能带「（含答案）」等修饰）被卷名继承；
            传 None 时沿用旧口径（资料标题）。

    返回::

        {"created": bool, "paper": ExamPaper, "paper_code": str}

    Raises:
        ValueError: 资料不是试卷类型 / 没有编号（调用方转 400）。
    """
    if (material.type or "") != PAPER_TYPE:
        raise ValueError("只有「试卷」类资料才能生成可作答卷")
    code = paper_code_of(material)
    if not code:
        raise ValueError("这条资料没有试卷编号（paper_code），无法生成可作答卷；"
                         "请先在「改信息」里补编号")

    existing = find_paper(db, code)
    if existing is not None:
        return {"created": False, "paper": existing, "paper_code": code}

    # 元数据合并优先级（与预览抽屉同口径）：人工订正 > 文件名解析
    merged = merge_meta(material, load_override(material))
    duration = merged.get("duration") or DEFAULT_DURATION
    total_score = merged.get("total_score") or DEFAULT_TOTAL_SCORE
    subject_id = SUBJECT_IDS.get((material.subject or "").strip(), 3)

    paper = ExamPaper(
        paper_name=((paper_name or "").strip()
                    or material.title or f"试卷 {code}")[:200],
        paper_code=code,
        subject_id=subject_id,
        composition_method="IMPORT",
        creator_id=material.creator_id or actor_id,
        duration=int(duration),
        total_score=float(total_score),
        difficulty=3,
        exam_type="SIMULATION",
        # 一律草稿：是否可考由「资料上架」经 P5 联动决定（方案 §2.3 唯一真源）
        paper_type="DRAFT",
        question_count=0,
        max_attempts=5,
    )
    db.add(paper)
    db.flush()   # 取 paper_id（不 commit）
    return {"created": True, "paper": paper, "paper_code": code}


def paper_brief(result: dict) -> dict:
    """把服务结果裁成接口回包（避免把 ORM 对象丢给前端）。"""
    paper = result["paper"]
    return {
        "created": result["created"],
        "paper_id": paper.paper_id,
        "paper_code": paper.paper_code,
        "paper_name": paper.paper_name,
        "paper_type": paper.paper_type,
        "question_count": paper.question_count or 0,
    }
