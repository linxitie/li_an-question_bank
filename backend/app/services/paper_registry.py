# -*- coding: utf-8 -*-
"""试卷资料 ↔ 可作答卷（`exam_paper`）的只读桥（C2/C4，2026-11-08）。

**为什么单独一个服务文件**：
`backend/scripts/gates/check_module_boundary.py` 会拦截「library 域的模块直接 import 他域 ORM」
（`ExamPaper` 的表只被 catalog/exam/platform 域用）。资料预览需要读这套卷的题量/总分/是否可考，
于是把这段跨域读取收敛到服务层一处：`library/materials.py` 只调 `paper_block()`，不再 import ExamPaper。
基线 `boundary_baseline.json` 只有一条历史违规（catalog 分类法契约），本文件保证不新增第二条。

**只读**：这里不写 `exam_paper`。上架联动（`paper_type` 同步，方案 §2.3）属于 C3/P5，
届时同样走这个文件，并按需要评估是否改成 `exam/contract.py` + 基线登记（需用户批准）。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from ..api.v1.exam import contract  # 服务层可读跨域契约（与 material_paper_link 读 catalog.contract 同理）
from ..models.models import ExamPaper, StudyMaterial
from .paper_meta_parser import format_meta_label, parse_paper_file_name


def find_exam_by_code(db: Session, code: Optional[str]) -> Optional[ExamPaper]:
    """按 `paper_code` 找可作答卷；空 code 直接返回 None（不查全表）。"""
    code = (code or "").strip()
    if not code:
        return None
    return (db.query(ExamPaper)
            .filter(ExamPaper.paper_code == code).first())


def paper_block(db: Session, material: StudyMaterial) -> dict:
    """预览接口的 `paper` 区块。

    合并优先级（C2b 起）：**管理员显式订正**（`paper_meta`）> 文件名解析 > 可作答卷（`exam_paper`）。
    题量/总分/时长这三项若资料里没订正、而可作答卷有值，就用卷上的（并标 `source` 便于界面解释）。
    `answerable`：`paper_type == 'PUBLISHED'`（学生考试链路只看这个值，见 `exams.py`）。
    """
    from .paper_meta_edit import load_override, merge_meta, meta_label_of

    code = (material.paper_code or material.badge or "").strip()
    override = load_override(material)
    merged = merge_meta(material, override)
    exam = find_exam_by_code(db, code)

    question_count = merged.get("question_count")
    total_score = merged.get("total_score")
    duration = merged.get("duration")
    source = {
        "question_count": "edit" if question_count is not None else None,
        "total_score": "edit" if total_score is not None else None,
        "duration": "edit" if duration is not None else None,
    }
    if exam:
        if question_count is None:
            # P2：`question_count` 是缓存值，用 `question_total()` 兜底成实数，
            # 保证预览里的题量与「能否开考」的判定不会自相矛盾。
            question_count = contract.question_total(db, exam)
            source["question_count"] = "exam"
        if total_score is None:
            total_score = float(exam.total_score) if exam.total_score is not None else None
            source["total_score"] = "exam"
        if duration is None:
            duration = int(exam.duration or 0)
            source["duration"] = "exam"

    meta = parse_paper_file_name(material.title or "")
    # ★ P2（2026-11-09）：`answerable` 从「只看 PUBLISHED」升级为「考试开关 + 定时窗口 + 有题」
    #   的完整判据（`contract.exam_ready`）。原因：P2 之后 PUBLISHED 只是必要条件 ——
    #   管理员可能已关闭这场考试，或卷里还是 0 题；前端若仍显示「开始考试」，
    #   学生点进去只会拿到 400。同时把完整 `exam` 状态块给出，前端不必自己拼文案。
    state = contract.exam_state(exam, questions=contract.question_total(db, exam),
                                answers_missing=contract.answer_gap(db, exam))
    return {
        "paper_code": code or None,
        "year": merged.get("year"),
        "region_name": merged.get("region_name"),
        "region_code": merged.get("region_code"),
        "book_kind_label": merged.get("book_kind_label"),
        "volume": merged.get("volume"),
        "meta_label": meta_label_of(merged) or format_meta_label(meta),
        "exam_paper_id": exam.paper_id if exam else None,
        "question_count": question_count,
        # `exam_paper.total_score` 是 NUMERIC → Decimal，不转 float 会让 JSON 序列化 500
        "total_score": total_score,
        "duration": duration,
        "source": source,
        # 人工订正过的原始键值（只有这些值该回填进"改信息"表单；
        # 解析出来的值不回填，否则保存一次就把解析结果固化成了订正）
        "override": override,
        "paper_type": exam.paper_type if exam else None,
        "answerable": bool(state.get("ready")),
        # P2：完整考试状态（known/published/open/ready/reason/open_at/close_at/question_count）
        "exam": state,
        "exam_hint": contract.exam_block_message(state),
    }
