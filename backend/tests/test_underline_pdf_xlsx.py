# -*- coding: utf-8 -*-
"""PDF / XLSX 填空横线还原（v8 M3-补）。

用合成文件锁定行为，不依赖 662MB 原始语料：
· PDF：文字行下方画一条 60pt 的水平线，且该位置文字层只有一个空格；
· XLSX：路径一「空单元格 + 只有下边框」，路径二「富文本里的下划线空白 run」。
"""
import io

import pytest

from app.services.question_ingest.pdf_underline import (
    apply_line_blanks, collect_h_segments, mark_page_blanks,
)
from app.services.question_ingest.xlsx_underline import cell_display_text


# ── PDF ──────────────────────────────────────────────────────────
def _make_pdf(path, text="编译人员在岗位上 的写照。", underline_x=None):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)     # A4
    page.insert_text((72, 120), text, fontname="china-s", fontsize=12)
    if underline_x is not None:
        page.draw_line((underline_x, 124), (underline_x + 60, 124), width=0.8)
    doc.save(path)
    doc.close()


def test_pdf_line_underlaps_text(tmp_path):
    """线与文字基线重合、长度 60pt → 认定为填空横线。"""
    import pdfplumber
    p = tmp_path / "blank.pdf"
    _make_pdf(p, "编译人员在岗位上 的写照。", underline_x=152)
    with pdfplumber.open(str(p)) as pdf:
        page = pdf.pages[0]
        tlines = page.extract_text_lines() or []
        lines, n = mark_page_blanks(page, tlines)
    assert n == 1, f"应只插一个 ____（lines/edges 去重后），实际 {n}"
    assert "____" in lines[0]
    # 原来的空格被替换而不是叠加，避免出现「空格+____」
    assert "  ____" not in lines[0]


def test_pdf_page_frame_line_ignored(tmp_path):
    """横贯整页的线是页框/分隔线，不能当成填空位。"""
    import pdfplumber
    p = tmp_path / "frame.pdf"
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 120), "编译人员在岗位上 的写照。", fontname="china-s", fontsize=12)
    page.draw_line((20, 124), (575, 124), width=0.8)   # 95% 页宽
    doc.save(str(p))
    doc.close()
    with pdfplumber.open(str(p)) as pdf:
        page = pdf.pages[0]
        segs = collect_h_segments(page, page.width, ())
        lines, n = mark_page_blanks(page, page.extract_text_lines() or [], page_width=page.width)
    assert segs == [], "整页宽线未被过滤"
    assert n == 0 and "____" not in lines[0]


def test_pdf_table_grid_ignored():
    """落在表格 bbox 内的线段一律跳过。"""
    class _Page:
        lines = [{"x0": 100, "x1": 200, "top": 300, "bottom": 300.8, "height": 0.8}]
        rects = []
        edges = []
    bbox = [(80, 280, 260, 340)]
    segs = collect_h_segments(_Page(), page_width=595, table_bboxes=bbox)
    assert segs == []


def test_apply_line_blanks_keeps_text_when_already_marked():
    text = "填入____处"
    chars = [{"x0": i * 10, "x1": i * 10 + 9} for i in range(len(text))]
    out, n = apply_line_blanks(text, chars, [{"cx": 45, "cy": 100, "x0": 20, "x1": 70, "top": 100, "bottom": 100.8}])
    assert n == 0 and out == text


# ── XLSX ─────────────────────────────────────────────────────────
def _wb_with_bottom_border(cell):
    from openpyxl import Workbook
    from openpyxl.styles import Border, Side

    wb = Workbook()
    ws = wb.active
    ws.append(["题目内容", "答案"])
    ws.append([None, "A"])
    c = ws.cell(row=2, column=1)
    c.border = Border(bottom=Side(style="thin"))
    return wb, c


def test_xlsx_blank_cell_with_bottom_only_border():
    wb, c = _wb_with_bottom_border(None)
    assert cell_display_text(c) == "____"


def test_xlsx_table_grid_not_treated_as_blank():
    from openpyxl import Workbook
    from openpyxl.styles import Border, Side

    wb = Workbook()
    ws = wb.active
    thin = Side(style="thin")
    ws.append(["题目内容", "答案"])
    ws.append([None, "A"])
    c = ws.cell(row=2, column=1)
    c.border = Border(left=thin, right=thin, top=thin, bottom=thin)  # 普通表格网格
    assert cell_display_text(c) == ""


def test_xlsx_rich_text_underline_run():
    from openpyxl import Workbook
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont

    wb = Workbook()
    ws = wb.active
    ws.append(["题目内容", "答案"])
    ws.append([CellRichText("编译人员在岗位上", TextBlock(InlineFont(u="single"), " "), "的写照。"), "A"])
    assert cell_display_text(ws.cell(row=2, column=1)) == "编译人员在岗位上____的写照。"


def test_parse_excel_buffer_reads_blank_from_border():
    from openpyxl import Workbook
    from openpyxl.styles import Border, Side
    from app.services.question_ingest.excel_reader import parse_excel_buffer

    wb = Workbook()
    ws = wb.active
    ws.append(["题目内容", "答案"])
    # 题干整格都是填空位：空单元格 + 只有下边框
    ws.append([None, "A"])
    ws.cell(row=2, column=1).border = Border(bottom=Side(style="thin"))
    buf = io.BytesIO()
    wb.save(buf)
    rows = parse_excel_buffer(buf.getvalue(), "t.xlsx")
    assert rows and rows[0].get("题目内容") == "____", rows
