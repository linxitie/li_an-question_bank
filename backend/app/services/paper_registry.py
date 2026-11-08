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

    - 元数据：**从资料标题解析**（年份/地区/题本或答案），解析不出返回 None，前端显示 `—`；
    - 关联：`study_material.paper_code`（没有则退回 `badge`）== `exam_paper.paper_code`；
    - `answerable`：`paper_type == 'PUBLISHED'`（学生考试链路只看这个值，见 `exams.py`）。
    """
    code = (material.paper_code or material.badge or "").strip()
    meta = parse_paper_file_name(material.title or "")
    exam = find_exam_by_code(db, code)
    return {
        "paper_code": code or None,
        "year": meta.year,
        "region_name": meta.region_name,
        "book_kind_label": meta.book_kind_label,
        "meta_label": format_meta_label(meta),
        "exam_paper_id": exam.paper_id if exam else None,
        "question_count": (int(exam.question_count or 0) if exam else None),
        # `exam_paper.total_score` 是 NUMERIC → Decimal，不转 float 会让 JSON 序列化 500
        "total_score": (float(exam.total_score) if exam and exam.total_score is not None else None),
        "duration": (int(exam.duration or 0) if exam else None),
        "paper_type": exam.paper_type if exam else None,
        "answerable": bool(exam and exam.paper_type == "PUBLISHED"),
    }
