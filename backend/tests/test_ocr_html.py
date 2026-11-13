# -*- coding: utf-8 -*-
"""OCR 文本 → 段落 HTML 的单测（P2，2026-11-12）。

覆盖三类规则 + 边界：去噪 / 断行合并 / 新块断段 / 超长切分 / HTML 转义 / 空输入。
"""
from __future__ import annotations

from app.services import ocr_html


def test_drop_noise_headers_and_page_numbers():
    lines = [
        "获取试卷更新，请关注公众号：gwyeasy（公务员考试挺简单）",
        "1、本题考查公安时政。",
        "第 3 页",
        "12/24",
        "来源：F整理：杨柳（微信：gwy288）",
    ]
    assert ocr_html.drop_noise(lines) == ["1、本题考查公安时政。"]


def test_merge_line_broken_by_column():
    # 上一行没有句末标点 → 与下一行直接拼接，中文不加空格
    lines = ["社会主义法治理念是中国特色社会主义理论在法治建设上的体现。其深刻内涵可以概括为",
             "依法治国、执法为民、公平正义、服务大局、党的领导五大方面的内容。"]
    paras = ocr_html.reflow(lines)
    assert len(paras) == 1
    assert "概括为依法治国" in paras[0]


def test_new_block_starts_paragraph():
    lines = [
        "解析：某段说明文字",
        "2、本题考查宪法。",
        "《宪法》第四十五条规定……",
    ]
    paras = ocr_html.reflow(lines)
    assert paras[0].startswith("解析：某段说明文字")
    assert any(p.startswith("2、本题考查宪法。") for p in paras), paras


def test_sentence_end_breaks_paragraph():
    paras = ocr_html.reflow(["第一句结束。", "第二句开始并结束。"])
    assert paras == ["第一句结束。", "第二句开始并结束。"]


def test_title_line_is_not_merged_with_question_no():
    paras = ocr_html.reflow([
        "2016年河南省公务员考试《公安基础知识》专业考试真题（解析）",
        "1、本题考查公安基础知识。",
    ])
    assert paras[0].startswith("2016年河南省")
    assert paras[1].startswith("1、本题考查")


def test_long_paragraph_is_split():
    body = "这是很长的一段话。" * 200          # 1800 字，超过 1000
    paras = ocr_html.reflow([body])
    assert len(paras) >= 2
    assert all(len(p) <= ocr_html.MAX_PARA_CHARS + 5 for p in paras)


def test_html_is_escaped():
    html_out, stats = ocr_html.text_to_html("3、比较 a<b 且 c>d & e。")
    assert "&lt;b" in html_out and "&gt;d" in html_out and "&amp; e" in html_out
    assert "<script" not in html_out
    assert stats["paragraphs"] == 1


def test_empty_input():
    html_out, stats = ocr_html.text_to_html("")
    assert html_out == ""
    assert stats == {"paragraphs": 0, "chars": 0, "avg_para": 0}


def test_stats_counts_plain_chars_not_tags():
    text = "1、第一题。\n2、第二题。"
    html_out, stats = ocr_html.text_to_html(text)
    assert stats["paragraphs"] == 2
    assert stats["chars"] == len("1、第一题。") + len("2、第二题。")
    assert html_out.count("<p>") == 2


def test_drop_switch_can_keep_noise_lines():
    lines = ["公众号：x", "1、正文。"]
    assert ocr_html.reflow(lines, drop=False)[0].startswith("公众号")
    assert ocr_html.reflow(lines)[0].startswith("1、")
