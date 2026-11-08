# -*- coding: utf-8 -*-
"""C4：把已存在的可作答卷（`exam_paper`）反向补录成「试卷类资料」（2026-11-08）。

背景（《试卷管理收敛》P4=C、方案 §2.4）：
题库里已经有 2 套**真实公专真题**（100 题/套，`paper_type=PUBLISHED`，学生能考），
但资料库里 `type=paper` 是 0 条 —— 管理员在「资料管理」看不到它们，也就谈不上"上架即审批"的统一入口。
本模块把它们补录成资料，并建立 `study_material.paper_code == exam_paper.paper_code` 的一对一关联。

三条硬约束：
1. **幂等**：已有同 `paper_code` 的资料就跳过，重复执行不产生副本；
2. **默认 dry-run**：`apply=False` 只返回计划，写库必须显式 `apply=True`；
3. **不猜**：文件名解析不出年份/地区时，人读编号留空、退回用 exam_paper 原编号建立关联，
   而不是编一个"看起来像"的编号。
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.models import ExamPaper, StudyMaterial
from .paper_meta_parser import PaperMeta, format_meta_label, parse_paper_file_name

logger = logging.getLogger(__name__)

#: question_subject.subject_name → 资料 subject 枚举
SUBJECT_BY_NAME = {"公专": "gongzhuan", "申论": "shenlun", "行测": "xingce"}
#: 只有这两种状态的卷子值得补录（草稿卷不该出现在资料库）
BACKFILLABLE_PAPER_TYPES = ("PUBLISHED", "APPROVED")


def _subject_of(db: Session, paper: ExamPaper) -> str:
    """按 `exam_paper.subject_id` 查科目名 → 资料枚举；查不到按公专兜底并记日志。"""
    row = db.execute(
        text("SELECT subject_name FROM question_subject WHERE subject_id = :sid"),
        {"sid": paper.subject_id},
    ).first()
    name = (row[0] if row else "") or ""
    subject = SUBJECT_BY_NAME.get(name.strip())
    if not subject:
        logger.warning("[paper-backfill] paper %s 科目 %r 未识别，按公专处理",
                       paper.paper_id, name)
        subject = "gongzhuan"
    return subject


def _existing_material(db: Session, paper: ExamPaper, code: str) -> Optional[StudyMaterial]:
    """幂等判定：先按 paper_code，再按标题（防止早先手工建过同名资料）。"""
    by_code = (db.query(StudyMaterial)
               .filter(StudyMaterial.paper_code == code).first())
    if by_code:
        return by_code
    if code and code != paper.paper_code:
        by_old = (db.query(StudyMaterial)
                  .filter(StudyMaterial.paper_code == paper.paper_code).first())
        if by_old:
            return by_old
    return (db.query(StudyMaterial)
            .filter(StudyMaterial.type == "paper",
                    StudyMaterial.title == (paper.paper_name or "").strip())
            .first())


def plan_backfill(db: Session) -> list[dict]:
    """生成补录计划（不写库）。每项含 paper_id / 解析出的元数据 / 将创建的资料。"""
    papers = (db.query(ExamPaper)
              .filter(ExamPaper.paper_type.in_(BACKFILLABLE_PAPER_TYPES))
              .order_by(ExamPaper.paper_id.asc())
              .all())
    plan: list[dict] = []
    for paper in papers:
        meta: PaperMeta = parse_paper_file_name(paper.paper_name or "")
        # 解析出人读编号就用它，否则沿用 exam_paper 原编号（保证两侧相等、关联得住）
        code = meta.paper_code or paper.paper_code
        existing = _existing_material(db, paper, code)
        plan.append({
            "paper_id": paper.paper_id,
            "paper_name": paper.paper_name,
            "paper_type": paper.paper_type,
            "question_count": int(paper.question_count or 0),
            # SQLite NUMERIC 列取出来是 Decimal，FastAPI 的 json 序列化会 500 → 显式转 float
            "total_score": float(paper.total_score or 0),
            "duration": int(paper.duration or 0),
            "meta": meta.as_dict(),
            "meta_label": format_meta_label(meta),
            "paper_code": code,
            "generated_code": bool(meta.paper_code),
            "existing_material_id": existing.material_id if existing else None,
            "action": "skip" if existing else "create",
            "subject": _subject_of(db, paper),
        })
    return plan


def apply_backfill(db: Session, apply: bool = False,
                   creator_id: Optional[int] = None) -> list[dict]:
    """按计划补录。`apply=False` 时与 `plan_backfill` 等价。

    创建的资料：`type=paper`、`status=1`（卷子本来就是已发布、学生能考，
    资料若置 0 会出现"学生能考但资料显示未上架"的矛盾）、`badge=paper_code`（列表直接显示编号）。
    同时把 `exam_paper.paper_code` 更新成人读编号（仅当解析成功且不与他人冲突），
    这样两侧 `paper_code` 相等即完成关联，不需要第二张关联表。
    """
    plan = plan_backfill(db)
    if not apply:
        return plan

    for item in plan:
        if item["action"] == "skip":
            continue
        paper = db.query(ExamPaper).filter(
            ExamPaper.paper_id == item["paper_id"]).first()
        if not paper:
            item["action"] = "missing"
            continue

        code = item["paper_code"]
        # 人读编号要落到 exam_paper 上（冲突则保持原编号，避免唯一性风险）
        if item["generated_code"] and code != paper.paper_code:
            clash = (db.query(ExamPaper)
                     .filter(ExamPaper.paper_code == code,
                             ExamPaper.paper_id != paper.paper_id).first())
            if clash:
                item["code_conflict_with"] = clash.paper_id
                code = paper.paper_code
                item["paper_code"] = code
            else:
                item["old_paper_code"] = paper.paper_code
                paper.paper_code = code

        material = StudyMaterial(
            subject=item["subject"],
            type="paper",
            title=(paper.paper_name or f"试卷 #{paper.paper_id}").strip()[:200],
            category=None,
            badge=code,
            paper_code=code,
            content="",
            status=1,
            creator_id=creator_id or paper.creator_id,
        )
        db.add(material)
        db.flush()
        item["action"] = "created"
        item["material_id"] = material.material_id
        logger.info("[paper-backfill] paper %s → material %s (%s)",
                    paper.paper_id, material.material_id, code)
    db.commit()
    return plan
