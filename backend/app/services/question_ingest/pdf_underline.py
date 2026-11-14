# -*- coding: utf-8 -*-
"""PDF 填空横线还原（v8 M3-补）。

背景（实测）：PDF 题库里的「填空横线」几乎都不是文字，而是：
  · 一条细水平线（`page.lines` / `page.edges`，常见 0.5~1pt 高），
  · 或一条填充矩形（`page.rects`，height <= 2pt）。
文字层里对应位置往往是**一个空格甚至什么都没有**，因此 extract_text()
拿到的题干就是「编译人员在岗位上 的写照」这种断句。

判定规则（保守优先，宁可少插也不插错）：
1. 只取水平线段：长 18~60% 页宽（更宽的是页眉分隔线/整页边框，不是填空）；
2. 线段必须紧贴某条文字行的**下沿**（|线顶 - 行底| <= GAP_MAX 且不高于行内文字中部），
   否则是表格网格线或装饰线；
3. 位置落在表格 bbox 内的线段一律跳过（表格边框会成片误判）；
4. 该行已有 `____` 时不再插入；
5. 插入位置按线段中心 x 与「该行字符中心 x」排序确定，命中空格则替换该空格，
   避免出现「空格 + ____」的双空格。

只做文本形态还原，不猜测横线长度（统一四个下划线），与 docx 侧保持同一约定。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

BLANK = "____"

SEG_MIN_W = 18.0        # 短于 18pt 的多为标点下划线/误检碎片
SEG_MAX_RATIO = 0.6     # 宽于 60% 页宽的是分隔线/边框
GAP_MAX = 6.0           # 线与文字基线的最大垂直距离（pt）
GAP_MIN = -3.0          # 线不得明显压在文字中部（否则是删除线区域）
RECT_MAX_H = 2.5        # 视为「横线」的矩形最大高度


def _bbox_contains_any(seg_cx: float, seg_cy: float, bboxes: Sequence[Tuple]) -> bool:
    for b in bboxes:
        try:
            x0, top, x1, bottom = float(b[0]), float(b[1]), float(b[2]), float(b[3])
        except Exception:
            continue
        if x0 - 2 <= seg_cx <= x1 + 2 and top - 2 <= seg_cy <= bottom + 2:
            return True
    return False


def collect_h_segments(page, page_width: float,
                       table_bboxes: Sequence[Tuple] = ()) -> List[Dict[str, float]]:
    """收集本页可能是填空横线的水平线段（已按宽度/表格/页框过滤）。"""
    segs: List[Dict[str, float]] = []
    seen: set = set()   # pdfplumber 同一条线会同时出现在 lines 与 edges 里，必须去重

    def _push(x0: float, x1: float, top: float, bottom: float) -> None:
        w = x1 - x0
        if w < SEG_MIN_W:
            return
        if page_width and w > page_width * SEG_MAX_RATIO:
            return
        cy = (top + bottom) / 2.0
        cx = (x0 + x1) / 2.0
        if table_bboxes and _bbox_contains_any(cx, cy, table_bboxes):
            return
        key = (round(x0, 1), round(top, 1), round(x1, 1))
        if key in seen:
            return
        seen.add(key)
        segs.append({'x0': x0, 'x1': x1, 'top': top, 'bottom': bottom,
                     'cx': cx, 'cy': cy})

    for attr in ('lines', 'rects', 'edges'):
        for obj in (getattr(page, attr, None) or []):
            try:
                if attr == 'edges':
                    # pdfplumber 的 edge 用 orientation 区分
                    if obj.get('orientation') != 'h':
                        continue
                elif attr == 'rects':
                    if float(obj.get('height', 0) or 0) > RECT_MAX_H:
                        continue
                else:
                    if float(obj.get('height', 0) or 0) > RECT_MAX_H:
                        continue
                _push(float(obj['x0']), float(obj['x1']),
                      float(obj['top']), float(obj.get('bottom', obj['top'])))
            except Exception:
                continue
    return segs


def _chars_of(line: Dict[str, Any]) -> List[Dict[str, Any]]:
    chars = line.get('chars') or []
    try:
        return sorted(chars, key=lambda c: (float(c.get('x0', 0)), float(c.get('top', 0))))
    except Exception:
        return list(chars)


def _char_text_positions(text: str, chars: Sequence[Dict[str, Any]]) -> Optional[List[int]]:
    """把 pdfplumber 的 chars 逐个对齐到 text 下标。

    `extract_text()` 会在字符间距过大处**合成空格**，而 `extract_text_lines()`
    的 chars 里没有这些空格，因此 len(chars) 与 len(text) 往往不等（实测
    27 vs 30）。直接按字符数比例估算会把 ____ 插到行尾，必须按「字符本身」
    顺序查找下标：逐个字符在 text 中向后 find，天然跨过合成空格。
    任一步找不到（连字/替换字符）则返回 None，调用方放弃该行。
    """
    out: List[int] = []
    cursor = 0
    for c in chars:
        ch = str(c.get('text') or '')
        if not ch:
            out.append(cursor)
            continue
        idx = text.find(ch, cursor)
        if idx < 0:
            return None
        out.append(idx)
        cursor = idx + len(ch)
    return out


def apply_line_blanks(text: str, chars: Sequence[Dict[str, Any]],
                      segs: Sequence[Dict[str, float]]) -> Tuple[str, int]:
    """在单行文本里按线段位置插入 ____，返回 (新文本, 插入数)。"""
    if not text or not segs:
        return text, 0
    if BLANK in text:
        return text, 0
    positions = _char_text_positions(text, chars)
    if not positions:
        return text, 0
    char_cx: List[float] = []
    for c in chars:
        try:
            char_cx.append((float(c.get('x0', 0)) + float(c.get('x1', 0))) / 2.0)
        except Exception:
            char_cx.append(0.0)
    inserts: List[int] = []
    for seg in segs:
        pos = len(text)
        for i, cx in enumerate(char_cx):
            if cx > seg['cx']:
                pos = positions[i]
                break
        if pos not in inserts:
            inserts.append(pos)
    # 从右往左改，前面的下标才不会失效
    out = text
    for pos in sorted(inserts, reverse=True):
        # 落点前恰好是空格（origin 里横线常被解析成一个空格）→ 用 ____ 顶替该空格
        if pos > 0 and out[pos - 1] == ' ':
            out = out[:pos - 1] + BLANK + out[pos:]
        else:
            out = out[:pos] + BLANK + out[pos:]
    return out, len(inserts)


def mark_page_blanks(page, tlines: Sequence[Dict[str, Any]],
                     page_width: Optional[float] = None,
                     table_bboxes: Sequence[Tuple] = ()) -> Tuple[List[str], int]:
    """把一页的文字行转成「含 ____ 的行文本」，返回 (行文本列表, 插入总数)。

    tlines 为 `page.extract_text_lines()` 的结果；必须带 chars 才能定位插入点，
    缺 chars 时原样返回（宁可不还原，也不乱插）。
    """
    lines: List[str] = [str(l.get('text', '')) for l in tlines]
    if not tlines:
        return lines, 0
    try:
        pw = float(page_width or page.width or 0)
    except Exception:
        pw = 0.0
    if not table_bboxes:
        # 调用方没给才自行探测（pdf_reader 已探测过，避免重复 find_tables）
        try:
            for t in (page.find_tables() or []):
                b = getattr(t, 'bbox', None)
                if b:
                    table_bboxes = list(table_bboxes) + [b]
        except Exception:
            table_bboxes = []
    try:
        segs = collect_h_segments(page, pw, table_bboxes)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[pdf-underline] 线段收集失败：{e}")
        return lines, 0
    if not segs:
        return lines, 0

    total = 0
    for i, line in enumerate(tlines):
        chars = _chars_of(line)
        if not chars:
            continue
        try:
            l_top = float(line.get('top', 0.0))
            l_bottom = float(line.get('bottom', 0.0))
        except Exception:
            continue
        if l_bottom - l_top < 1.0:
            continue
        hit: List[Dict[str, float]] = []
        for seg in segs:
            gap = seg['top'] - l_bottom
            if GAP_MIN <= gap <= GAP_MAX:
                hit.append(seg)
            elif l_top - 1.0 <= seg['cy'] <= l_bottom + GAP_MAX and gap <= GAP_MAX:
                # 线画在文字基线略上方、字框内部的情形
                if seg['top'] >= l_bottom - 4.0:
                    hit.append(seg)
        if not hit:
            continue
        new_text, n = apply_line_blanks(lines[i], chars, hit)
        if n:
            lines[i] = new_text
            total += n
    return lines, total
