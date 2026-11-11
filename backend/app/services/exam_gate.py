# -*- coding: utf-8 -*-
"""P2（2026-11-09）：考试开关注（含定时窗口）——写操作与状态读取的唯一入口。

**为什么单独一个服务**：
  · 写 `exam_paper` 属于考试域，library 域（materials.py）不能直接 import `ExamPaper`
    （门禁 `check_module_boundary` 的 cross_write 规则）；
  · 判定规则（发布/开关/窗口/题量）只应写一次，见 `api/v1/exam/contract.py`；
  · 本文件只做"资料 → 卷"的取键与写字段，规则全部转调契约。

**谁在用**（三个域，口径必须一致）：
  · `library/materials.py`：管理端列表的 `exam` 状态块 + 两个写端点（开关/定时）；
  · `catalog/paper_generation.py`：`/api/papers/list` 学生分支的 SQL 过滤
    （经 `open_conditions()`，避免 catalog → exam 的跨域 import）；
  · `exam/exams.py` + `services/exam_service.py`：开考前**直接**用契约判定（同域，无需绕服务）。

**语义（与方案 §4 一致）**：
  · 开关与「资料上架」独立：上架只决定资料在不在库里；本开关只决定学生能不能**进考试**；
  · 关闭不动 `exam_record`：历史成绩一律保留，只是不能再开新考；
  · 0 题的卷不允许开考（判定在契约里，界面把开关灰掉）。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..api.v1.exam import contract
from ..models.models import StudyMaterial
from .material_paper_link import find_paper, paper_code_of
from .material_paper_sync import EXAM_PLACEMENTS, placement_of


class ExamGateError(ValueError):
    """调用方转 400（资料不是试卷 / 投放位不含考试页 / 还没建卷 …）。"""


def _resolve(db: Session, material: StudyMaterial):
    if (material.type or "") != "paper":
        raise ExamGateError("只有「试卷」类资料才有考试开关")
    if placement_of(material) not in EXAM_PLACEMENTS:
        raise ExamGateError("投放位是「仅资料页」时没有考试开关（学生只能下载原卷）")
    code = paper_code_of(material)
    if not code:
        raise ExamGateError("这条资料还没有试卷编号，无法定位可作答卷；请先补编号/建卷")
    paper = find_paper(db, code)
    if paper is None:
        raise ExamGateError("还没有可作答卷；请先用「建卷」生成（上传时选考试页/都投可自动建）")
    return paper


def state_of(db: Session, material: StudyMaterial,
             now: Optional[datetime] = None) -> dict:
    """只读状态（管理端列表/资料页用）。没有卷时返回 known=False，不抛错。"""
    code = paper_code_of(material)
    paper = find_paper(db, code) if code else None
    state = contract.exam_state(paper, now,
                                questions=contract.question_total(db, paper),
                                answers_missing=contract.answer_gap(db, paper))
    state["paper_code"] = code or None
    state["paper_id"] = paper.paper_id if paper is not None else None
    # 手动总闸原值（前端开关只认这一条）：NULL 视为 1；不能用 `or 1`，否则 0 会被吞成 1
    state["manual_open"] = (1 if getattr(paper, "exam_open", 1) is None
                            else int(getattr(paper, "exam_open", 1))) if paper is not None else 0
    return state


def set_open(db: Session, material: StudyMaterial, *, open_: bool) -> dict:
    """手动总闸。**不 commit**（调用方与审计同一事务）。"""
    paper = _resolve(db, material)
    paper.exam_open = 1 if open_ else 0
    return contract.exam_state(paper, questions=contract.question_total(db, paper),
                               answers_missing=contract.answer_gap(db, paper))


def set_window(db: Session, material: StudyMaterial, *,
               open_at: Optional[datetime], close_at: Optional[datetime]) -> dict:
    """设置/清空定时窗口。空值 = 该侧不限。**不 commit**。"""
    if open_at and close_at and open_at >= close_at:
        raise ExamGateError("开始时间必须早于结束时间")
    paper = _resolve(db, material)
    paper.exam_open_at = open_at
    paper.exam_close_at = close_at
    return contract.exam_state(paper, questions=contract.question_total(db, paper),
                               answers_missing=contract.answer_gap(db, paper))


def parse_dt(value) -> Optional[datetime]:
    """接受 ``YYYY-MM-DD HH:MM`` / ``YYYY-MM-DDTHH:MM`` / 空值。"""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ExamGateError("时间格式不对，请用「YYYY-MM-DD HH:MM」")


# ==================== 跨域只读门面（catalog 的列表查询用） ====================

def open_conditions(now: Optional[datetime] = None) -> list:
    """学生端试卷列表的 SQL 过滤条件（开关 + 窗口 + 有题），转调契约。

    为什么不让 catalog 直接 import `exam/contract.py`：门禁把 catalog → exam 的
    跨域 import 判为违规。服务层是两边都能用的公共层（与 `paper_registry` 同理）。

    **2026-11-09 起 `/api/papers/list` 不再用它做"隐藏"**：产品要求把"暂不可考"的卷
    也显示出来并标注原因（否则学生以为卷丢了）。本函数保留给仍需要"只列可考"的调用方。
    """
    return contract.open_conditions(now)


def paper_state(db: Session, paper, now: Optional[datetime] = None) -> dict:
    """卷的考试状态块（catalog 列表用；与资料页 `paper.exam` 同一份契约）。"""
    return contract.exam_state(paper, now,
                               questions=contract.question_total(db, paper),
                               answers_missing=contract.answer_gap(db, paper))


def paper_hint(db: Session, paper, now: Optional[datetime] = None) -> str:
    """卷"为什么不能考"的一句话（已翻成人话）。可考时返回空串。"""
    return contract.exam_block_message(paper_state(db, paper, now))


def block_message(db: Session, material: StudyMaterial,
                  now: Optional[datetime] = None) -> str:
    """给资料详情页/前端的"为什么不能考"一句话（已把原因码翻成人话）。"""
    state = state_of(db, material, now)
    return contract.exam_block_message(state)
