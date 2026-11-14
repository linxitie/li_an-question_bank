# -*- coding: utf-8 -*-
"""下划线/填空横线还原（v8 M3）。

背景（实测）：Word 里的填空横线绝大多数是「带下划线格式的空格或制表位」，
甚至只是一条段落底边框；python-docx 的 paragraph.text 只返回字符，
空白被丢弃后题干就只剩一个空格——题 3666「编译工作是寂寞的…」即此类。

本模块统一三件事：
1. 段落内 run 级下划线：空白 → 四个下划线，文字 → <u>文字</u>；
2. 段落底边框（w:pBdr/w:bottom）：整段只有空白但带底边框时，视作一条横线；
3. 表格单元格、页眉页脚、文本框里的段落：同样按上面两条处理，
   否则整张表格里的填空题仍然会丢横线（旧实现直接取 cell.text）。

约定：只做「文本形态还原」，不猜测横线长度，避免生成超长占位符。
"""
from __future__ import annotations

import logging
from typing import Iterable, List

logger = logging.getLogger(__name__)

# Word 里常见的三种「横线容器」，统一映射成四个下划线
BLANK = "____"

_NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _run_is_underlined(run) -> bool:
    """run 是否带下划线。

    python-docx 对「样式继承」的下划线返回 None 而不是 False，
    因此先判显式下划线，再兜底看 rPr/w:u。
    """
    try:
        if run.underline is True:
            return True
        if run.underline is None:
            rpr = run._r.find(f"{_NS_W}rPr")
            if rpr is not None:
                u = rpr.find(f"{_NS_W}u")
                if u is not None and u.get(f"{_NS_W}val") not in (None, "none"):
                    return True
    except Exception:
        return False
    return False


def paragraph_has_bottom_border(para) -> bool:
    """段落是否带底边框（排版里常用它画填空横线）。"""
    try:
        ppr = para._p.find(f"{_NS_W}pPr")
        if ppr is None:
            return False
        pbdr = ppr.find(f"{_NS_W}pBdr")
        if pbdr is None:
            return False
        bottom = pbdr.find(f"{_NS_W}bottom")
        if bottom is None:
            return False
        return bottom.get(f"{_NS_W}val") not in (None, "none")
    except Exception:
        return False


def paragraph_text_with_underline(para) -> str:
    """按 run 还原下划线，返回段落文本。"""
    try:
        runs = para.runs
    except Exception:
        return para.text or ""
    buf: List[str] = []
    for run in runs:
        text = run.text or ""
        if not _run_is_underlined(run):
            buf.append(text)
        elif text.strip():
            buf.append("<u>" + text + "</u>")
        else:
            buf.append(BLANK)
    merged = "".join(buf)
    if merged.strip():
        return merged
    # 整段空白但有底边框：这条线本身就是填空位置
    if paragraph_has_bottom_border(para):
        return BLANK
    return para.text or ""


def cell_text(cell) -> str:
    """表格单元格文本：逐段落还原下划线（旧实现 cell.text 会丢横线）。"""
    try:
        texts = [paragraph_text_with_underline(p) for p in cell.paragraphs]
    except Exception:
        return (cell.text or "").strip()
    return "\n".join(t for t in texts if t and t.strip()).strip()


def textbox_texts(doc) -> Iterable[str]:
    """文本框（w:txbxContent）里的段落文本。

    python-docx 不暴露文本框，只能走 XML；题干/材料被放进文本框的卷子并不少见，
    漏掉会表现为「题目内容缺失」。
    """
    try:
        root = doc.element.body
    except Exception:
        return []
    out: List[str] = []
    for box in root.iter(f"{_NS_W}txbxContent"):
        for p in box.iter(f"{_NS_W}p"):
            buf: List[str] = []
            for r in p.iter(f"{_NS_W}r"):
                text = "".join(t.text or "" for t in r.iter(f"{_NS_W}t"))
                if not text:
                    continue
                underlined = False
                rpr = r.find(f"{_NS_W}rPr")
                if rpr is not None:
                    u = rpr.find(f"{_NS_W}u")
                    underlined = u is not None and u.get(f"{_NS_W}val") not in (None, "none")
                if not underlined:
                    buf.append(text)
                elif text.strip():
                    buf.append("<u>" + text + "</u>")
                else:
                    buf.append(BLANK)
            merged = "".join(buf).strip()
            if merged:
                out.append(merged)
    return out


def header_footer_texts(doc) -> Iterable[str]:
    """页眉页脚里含横线的段落。

    只取「含横线或下划线」的段落：页眉里通常还有页码、试卷名等噪声，
    全量拼进题干会污染内容。
    """
    out: List[str] = []
    try:
        sections = doc.sections
    except Exception:
        return out
    for sec in sections:
        for part in (sec.header, sec.footer):
            try:
                paras = part.paragraphs
            except Exception:
                continue
            for p in paras:
                text = paragraph_text_with_underline(p)
                if BLANK in text or "<u>" in text:
                    out.append(text.strip())
    return out
