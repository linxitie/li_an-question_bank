# -*- coding: utf-8 -*-
"""Excel / XLSX 填空横线还原（v8 M3-补）。

背景（实测）：Excel 版题库的填空横线有两种形态：
1. 单元格本身是空的、只带**下边框**（table 边框样式里的 bottom）——
   这是最常见的手工排版方式；
2. 单元格文本是富文本（openpyxl CellRichText），其中某个 run 带
   `u` 字体下划线而内容是空格/空串。

两种都会被 `values_only=True` 读成 `None` 或 `''`，题干于是缺一个空。

判定从严：
· 空单元格 + bottom 边框 → ____，但要求**没有**左右边框：表格内的普通空单元格
  通常四边都有框，四边都有框的空格子是「无内容」而不是「填空位」；
· 富文本里的下划线空白 run → ____，下划线文字 run → <u>文字</u>。
"""
from __future__ import annotations

import logging
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)

BLANK = "____"
_SIDE_NAMES = ('left', 'right', 'top', 'bottom')


def _border_style(edge) -> Optional[str]:
    try:
        style = getattr(edge, 'style', None)
    except Exception:
        return None
    if not style:
        return None
    s = str(style)
    if s.lower() in ('none', 'hair'):
        return None
    return s


def cell_has_bottom_only_border(cell) -> bool:
    """空单元格是否只有下边框（= 手画的填空横线）。"""
    b = getattr(cell, 'border', None)
    if b is None:
        return False
    if not _border_style(getattr(b, 'bottom', None)):
        return False
    # 左/右/上任意一条存在，说明它处在表格网格里，不是独立横线
    for name in ('left', 'right', 'top'):
        if _border_style(getattr(b, name, None)):
            return False
    return True


def rich_text_with_underline(value) -> Optional[str]:
    """富文本单元格 → 还原下划线；不是富文本或没有下划线 run 时返回 None。

    openpyxl >= 3.1 的 `CellRichText` 可迭代出 str / TextBlock；TextBlock 带
    `font`，字体里的 `u` 即下划线。旧版本没有该类型，直接跳过。
    """
    if value is None or isinstance(value, (int, float)):
        return None
    try:
        from openpyxl.cell.rich_text import CellRichText  # noqa: WPS433
    except Exception:
        return None
    if not isinstance(value, CellRichText):
        return None
    buf: List[str] = []
    hit = False
    for part in value:
        if isinstance(part, str):
            buf.append(part)
            continue
        text = getattr(part, 'text', '') or ''
        font = getattr(part, 'font', None)
        underlined = bool(font is not None and getattr(font, 'u', None))
        if not underlined:
            buf.append(text)
        elif text.strip():
            buf.append('<u>' + text + '</u>')
            hit = True
        else:
            buf.append(BLANK)
            hit = True
    if not hit:
        return None
    return ''.join(buf)


def cell_display_text(cell) -> str:
    """单元格文本：富文本先还原下划线；空单元格 + 只有下边框 → ____。"""
    try:
        value = cell.value
    except Exception:
        return ''
    rich = rich_text_with_underline(value)
    if rich is not None:
        return rich
    text = '' if value is None else str(value).strip()
    if text:
        return text
    try:
        if cell_has_bottom_only_border(cell):
            return BLANK
    except Exception:
        pass
    return ''
