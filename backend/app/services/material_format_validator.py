# -*- coding: utf-8 -*-
"""备考资料上传的**文件级格式校验器**（P2-B，需求 3 的"严格的文档内容格式"）。

设计原则
--------
1. **纯函数、零 IO**：只吃 `headers + rows`，好测、可复用、可给学生端和管理员端共用。
2. **错误码可定位**：每条错误都带 `code / row / column / message`，前端能直接标红单元格。
3. **先全检再落库**：调用方拿到 `ok=False` 就不入库，避免"导了一半才发现第 87 行超长"。
4. **不猜**：分类/考点只做"是否在词表内"的判定，不做模糊纠正（纠正交给自动分类）。

错误码
------
E001 缺必需列（正面/背面）        E002 必填单元格为空
E003 超长（正面>120 / 背面>600）  E004 行数超上限
E005 文件内重复行                 E006 分类不在子类词表
E007 考点不在考点表               E008 含危险标签（script/iframe 等）
E009 扩展名不支持                 E010 文件超过体积上限
"""
from __future__ import annotations

import os
from typing import Dict, Iterable, List, Optional, Sequence

# 与 materials.py 的卡片上限保持一致（改一处要两处同改，故此处引用常量名并加断言测试）
FRONT_MAX = 120
BACK_MAX = 600
ROW_LIMIT = 200
FILE_MAX_MB = 10
SUPPORTED_EXT = (".xlsx", ".csv")

DANGEROUS = ("<script", "<iframe", "<object", "<embed", "<style")

# 表头别名：同一含义允许多种写法（教师旧模板不改也能用）
COLUMN_ALIASES = {
    "front": ("正面", "卡片正面", "题目", "问题", "front"),
    "back": ("背面", "卡片背面", "答案", "解析", "内容", "back"),
    "category": ("分类", "子类", "类别", "category"),
    "point": ("考点", "知识点", "point"),
    "difficulty": ("难度", "difficulty"),
    "cover": ("封面", "配图", "cover"),
}
REQUIRED = ("front", "back")

# 整表拒绝类错误：文件本身不可用，逐行跳过没有意义
BLOCKING_CODES = ("E001", "E004", "E009", "E010")
# 行级错误：跳过该行并回报（与既有 D5「invalid_rows / skipped」语义一致）
ROW_CODES = ("E002", "E003", "E005", "E008")

ERROR_TEXT = {
    "E001": "缺少必需列",
    "E002": "必填单元格为空",
    "E003": "内容超长",
    "E004": "行数超过上限",
    "E005": "文件内重复行",
    "E006": "分类不在子类词表内",
    "E007": "考点不在考点表内",
    "E008": "含不允许的标签",
    "E009": "扩展名不支持",
    "E010": "文件超过体积上限",
}


def resolve_columns(headers: Sequence[str]) -> Dict[str, int]:
    """表头 → 列下标（按别名表匹配，后出现的同名列不覆盖先出现的）。"""
    norm = [(h or "").strip().lower() for h in headers]
    out: Dict[str, int] = {}
    for key, aliases in COLUMN_ALIASES.items():
        for idx, h in enumerate(norm):
            if h in [a.lower() for a in aliases]:
                out[key] = idx
                break
    return out


def check_file(name: str, size_bytes: int) -> List[dict]:
    """文件级检查（扩展名 / 体积），返回错误列表。"""
    errs: List[dict] = []
    ext = os.path.splitext(name or "")[1].lower()
    if ext not in SUPPORTED_EXT:
        errs.append({"code": "E009", "row": 0, "column": "文件",
                     "message": f"仅支持 {'/'.join(SUPPORTED_EXT)}，当前 {ext or '无扩展名'}"})
    if size_bytes and size_bytes > FILE_MAX_MB * 1024 * 1024:
        errs.append({"code": "E010", "row": 0, "column": "文件",
                     "message": f"文件 {size_bytes / 1048576:.1f}MB，超过 {FILE_MAX_MB}MB 上限"})
    return errs


def validate_rows(headers: Sequence[str], rows: Iterable[Sequence[str]], *,
                  category_names: Optional[Sequence[str]] = None,
                  point_names: Optional[Sequence[str]] = None,
                  row_limit: int = ROW_LIMIT,
                  max_errors: int = 50,
                  category_as_warning: bool = False) -> dict:
    """校验表格结构 + 逐行内容。

    返回 {ok, errors, warnings, stats, columns}；errors 最多 max_errors 条，
    但 stats.error_count 是真实总数（前端可显示"共 N 处问题，仅展示前 50"）。
    """
    cols = resolve_columns(headers)
    errors: List[dict] = []
    warnings: List[dict] = []
    stats = {"rows": 0, "valid": 0, "error_count": 0, "warning_count": 0}

    def add(code: str, row: int, column: str, message: str) -> None:
        stats["error_count"] += 1
        if len(errors) < max_errors:
            errors.append({"code": code, "row": row, "column": column,
                           "message": message})

    missing = [c for c in REQUIRED if c not in cols]
    if missing:
        for c in missing:
            add("E001", 0, COLUMN_ALIASES[c][0],
                f"{ERROR_TEXT['E001']}：需要在表头写入「{COLUMN_ALIASES[c][0]}」")
        return {"ok": False, "errors": errors, "warnings": warnings,
                "stats": stats, "columns": cols}

    rows = list(rows)
    stats["rows"] = len(rows)
    if len(rows) > row_limit:
        add("E004", 0, "-", f"共 {len(rows)} 行，超过单次上限 {row_limit} 行，请拆分文件")

    cats = set(category_names or [])
    points = set(point_names or [])
    seen = set()

    for i, r in enumerate(rows, start=1):
        def cell(key: str) -> str:
            idx = cols.get(key)
            if idx is None or idx >= len(r):
                return ""
            return (r[idx] or "").strip()

        front, back = cell("front"), cell("back")
        if not front:
            add("E002", i, COLUMN_ALIASES["front"][0], "正面不能为空")
            continue
        if not back:
            add("E002", i, COLUMN_ALIASES["back"][0], "背面不能为空")
            continue
        if len(front) > FRONT_MAX:
            add("E003", i, COLUMN_ALIASES["front"][0],
                f"正面 {len(front)} 字，超过 {FRONT_MAX} 字上限")
        if len(back) > BACK_MAX:
            add("E003", i, COLUMN_ALIASES["back"][0],
                f"背面 {len(back)} 字，超过 {BACK_MAX} 字上限")
        low = (front + back).lower()
        if any(t in low for t in DANGEROUS):
            add("E008", i, "-", "含不允许的标签（script/iframe/object/embed/style）")

        key = (front, back)
        if key in seen:
            add("E005", i, "-", "与前面某行正/背面完全相同")
        seen.add(key)

        cat = cell("category")
        if cat and cats and cat not in cats:
            msg = f"分类「{cat}」不在本子类词表内；可留空由系统自动分类"
            if category_as_warning:
                stats["warning_count"] += 1
                if len(warnings) < max_errors:
                    warnings.append({"code": "E006", "row": i,
                                     "column": COLUMN_ALIASES["category"][0],
                                     "message": msg})
            else:
                add("E006", i, COLUMN_ALIASES["category"][0], msg)
        pt = cell("point")
        if pt and points and pt not in points:
            # 考点写错不阻断（自动分类会兜底），按警告处理
            stats["warning_count"] += 1
            if len(warnings) < max_errors:
                warnings.append({"code": "E007", "row": i,
                                 "column": COLUMN_ALIASES["point"][0],
                                 "message": f"考点「{pt}」不在考点表内，将由系统自动分类"})

        if len(front) <= FRONT_MAX and len(back) <= BACK_MAX:
            stats["valid"] += 1

    return {"ok": stats["error_count"] == 0, "errors": errors,
            "warnings": warnings, "stats": stats, "columns": cols}
