# -*- coding: utf-8 -*-
"""docx 下划线（填空横线）还原：解析层单测。

背景：Word 里的填空横线是「带下划线格式的空格」，python-docx 的 para.text 只剩
半角空格，落库后横线消失（实测题 3666）。此测试锁定修复行为，防止回归。

v8 M3 把实现收口到 docx_underline.py，并扩面到「段落底边框」与「表格单元格」；
前三个用例仍从 docx_reader 导入，用来钉住 re-export 兼容性。
"""
import pytest

pytest.importorskip("docx")

from docx import Document  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Pt  # noqa: E402

from app.services.question_ingest.docx_reader import (  # noqa: E402
    paragraph_text_with_underline,
)
from app.services.question_ingest.docx_underline import (  # noqa: E402
    BLANK,
    cell_text,
)


def _make_para(runs):
    doc = Document()
    para = doc.add_paragraph()
    for text, underlined in runs:
        run = para.add_run(text)
        run.font.size = Pt(11)
        if underlined:
            run.underline = True
    return para


def test_underlined_blank_becomes_visible_placeholder():
    para = _make_para([("编译人员在岗位上", False), ("  ", True), ("的写照。", False)])
    assert paragraph_text_with_underline(para) == "编译人员在岗位上____的写照。"


def test_underlined_text_keeps_semantic_tag():
    para = _make_para([("关键词是", False), ("重要概念", True)])
    assert paragraph_text_with_underline(para) == "关键词是<u>重要概念</u>"


def test_plain_paragraph_unchanged():
    para = _make_para([("没有任何下划线的普通题干。", False)])
    assert paragraph_text_with_underline(para) == "没有任何下划线的普通题干。"


def test_paragraph_bottom_border_blank_line():
    """整段空白 + 底边框，是另一种常见画线方式（不是 run 级下划线）。"""
    doc = Document()
    p = doc.add_paragraph()
    p.add_run(" ")
    ppr = p._p.get_or_add_pPr()
    pbdr = ppr.makeelement(qn("w:pBdr"), {})
    bottom = ppr.makeelement(qn("w:bottom"), {qn("w:val"): "single", qn("w:sz"): "6"})
    pbdr.append(bottom)
    ppr.append(pbdr)
    assert paragraph_text_with_underline(p) == BLANK


def test_table_cell_keeps_blank():
    """表格里的填空横线：旧实现取 cell.text，横线必丢。"""
    doc = Document()
    table = doc.add_table(rows=1, cols=2)
    cell = table.cell(0, 0)
    p = cell.paragraphs[0]
    p.add_run("姓名：")
    r = p.add_run(" ")
    r.underline = True
    assert BLANK in cell_text(cell)