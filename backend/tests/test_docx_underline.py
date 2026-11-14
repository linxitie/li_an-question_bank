# -*- coding: utf-8 -*-
"""docx 下划线下划线（填空横线）还原：解析层单测。

背景：Word 里的填空横线是「带下划线格式的空格」，python-docx 的 para.text 只剩
半角空格，落库后横线消失（实测题 3666）。此测试锁定修复行为，防止回归。
"""
from docx import Document
from docx.shared import Pt

from app.services.question_ingest.docx_reader import paragraph_text_with_underline


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
