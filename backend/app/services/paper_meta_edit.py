# -*- coding: utf-8 -*-
"""试卷元数据的**显式订正**（C2b，2026-11-08）。

背景：文件名解析（C2a）覆盖不了所有情况——「扫描件_001.pdf」解析不出年份、地区，
管理员需要能手工补/改：年份、地区、卷别、题量、总分、时长。

三条设计取舍：

1. **存在资料上（`study_material.paper_meta` JSON），不写 `exam_paper`**。
   理由：`exam_paper` 属于 catalog/exam/platform 域，library 域写它会被 L4 模块边界门禁拦
   （见 C2/C4 交付记录 §5.2）；而"这套卷到底考多少题"在**没关联可作答卷**时也只能存资料这边。
2. **合并优先级**：显式订正 > 文件名解析 > 可作答卷（`exam_paper`）。
   订正是人工判断，必须压过机器解析；可作答卷的题量/总分放最后，是因为它描述的是"在线那份卷"，
   而资料描述的是"纸质/原卷"，两者可能不一致（例如只截取了部分题）。
3. **不自动改编号**：`paper_code` 一旦人工给过或已与可作答卷对上，就不再随年份/地区自动重算，
   否则会把关联打断。要让系统重算，先把 `paper_code` 显式清空。

纯函数集中在这里，路由只做鉴权与落库；`services/paper_registry.paper_block()` 负责展示侧合并。
"""
from __future__ import annotations

import json
from typing import Optional

from .paper_meta_parser import (
    REGION_BY_CODE,
    REGIONS,
    build_paper_code,
    format_meta_label,
    parse_paper_file_name,
    PaperMeta,
)

#: 允许订正的字段 → (类型, 下限, 上限)
EDITABLE_FIELDS = {
    "year": (int, 1990, 2100),
    "volume": (int, 1, 20),
    "question_count": (int, 1, 500),
    "total_score": (float, 0.5, 1000.0),
    "duration": (int, 1, 600),
}
#: 字符串字段（枚举/自由文本）
TEXT_FIELDS = ("region_code", "region_name", "book_kind", "book_kind_label")
BOOK_KINDS = {"T": "题本", "A": "答案", "J": "解析"}


class MetaError(ValueError):
    """订正参数不合法（路由层转 400）。"""


def load_override(material) -> dict:
    """读 `paper_meta` JSON；损坏/空都当没有，不让历史脏数据把预览打挂。"""
    raw = getattr(material, "paper_meta", None)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _as_int(value, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise MetaError(f"{field} 必须是整数")


def _as_float(value, field: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise MetaError(f"{field} 必须是数字")


def resolve_region(payload: dict) -> tuple:
    """地区：优先 code，其次 name；都没给返回 (None, None)。名字不认就报错。"""
    code = (payload.get("region_code") or "").strip().upper()
    name = (payload.get("region_name") or "").strip()
    if code:
        if code not in REGION_BY_CODE:
            raise MetaError(f"未知地区代码：{code}")
        return code, REGION_BY_CODE[code]
    if name:
        for r_code, r_name, _pattern in REGIONS:
            if r_name == name:
                return r_code, r_name
        raise MetaError(f"未知地区：{name}")
    return None, None


def normalize_patch(payload: dict) -> dict:
    """把前端提交的订正字段归一化。

    只接受白名单键；`None` / 空串 = **清除该项**（回到"解析不出就留空"的状态）。
    返回可直接写进 `paper_meta` 的 dict（只含出现过的键）。
    """
    out: dict = {}

    for field, (typ, low, high) in EDITABLE_FIELDS.items():
        if field not in payload:
            continue
        raw = payload[field]
        if raw is None or raw == "":
            out[field] = None
            continue
        value = _as_int(raw, field) if typ is int else _as_float(raw, field)
        if not (low <= value <= high):
            raise MetaError(f"{field} 需在 {low}–{high} 之间，收到 {value}")
        out[field] = int(value) if typ is int else round(float(value), 1)

    if "book_kind" in payload or "book_kind_label" in payload:
        kind = (payload.get("book_kind") or "").strip().upper()
        label = (payload.get("book_kind_label") or "").strip()
        if kind and kind not in BOOK_KINDS:
            raise MetaError(f"卷别只能是 {sorted(BOOK_KINDS)} 之一")
        if not kind and label:
            for k, v in BOOK_KINDS.items():
                if v == label:
                    kind = k
                    break
            else:
                raise MetaError(f"未知卷别：{label}")
        out["book_kind"] = kind or None
        out["book_kind_label"] = BOOK_KINDS.get(kind) if kind else (label or None)

    if "region_code" in payload or "region_name" in payload:
        code, name = resolve_region(payload)
        out["region_code"] = code
        out["region_name"] = name

    return out


def merge_meta(material, override: Optional[dict] = None) -> dict:
    """展示/计算用的合并结果：`override` → 文件名解析 → 空。

    返回扁平 dict（与 `PaperMeta.as_dict()` 同构 + 题量/总分/时长）。
    """
    base = parse_paper_file_name(getattr(material, "title", "") or "").as_dict()
    patch = override if override is not None else load_override(material)
    merged = dict(base)
    for key in ("year", "region_code", "region_name", "book_kind", "book_kind_label", "volume"):
        if key in patch and patch[key] not in (None, ""):
            merged[key] = patch[key]
        elif key in patch and patch[key] in (None, ""):
            merged[key] = None
    for key in ("question_count", "total_score", "duration"):
        if key in patch:
            merged[key] = patch[key]
        else:
            merged.setdefault(key, None)
    # 卷别标签跟着 code 走（前端可能只传 book_kind）
    if merged.get("book_kind") and not merged.get("book_kind_label"):
        merged["book_kind_label"] = BOOK_KINDS.get(merged["book_kind"])
    return merged


def meta_label_of(merged: dict) -> str:
    """`2019 · 北京 · 题本` 形式的一行摘要。"""
    return format_meta_label(PaperMeta(
        year=merged.get("year"),
        region_code=merged.get("region_code"),
        region_name=merged.get("region_name"),
        book_kind=merged.get("book_kind"),
        book_kind_label=merged.get("book_kind_label"),
        volume=merged.get("volume"),
    ))


def suggest_paper_code(merged: dict) -> Optional[str]:
    """按（可能被订正过的）元数据重算人读编号；缺科目/年份/地区则返回 None。"""
    meta = PaperMeta(
        year=merged.get("year"),
        region_code=merged.get("region_code"),
        region_name=merged.get("region_name"),
        subject=merged.get("subject"),
        book_kind=merged.get("book_kind"),
        volume=merged.get("volume"),
    )
    # subject 不在 merged 里时，从编号前缀推回（例如已有 `GZ-...` 或由资料 subject 决定）
    if not meta.subject:
        return None
    return build_paper_code(meta)
