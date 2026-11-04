# -*- coding: utf-8 -*-
"""申论章节标题识别与多题切分回归。

真实故障（2026-10-31 实测）：2024 年北京市公考《申论》题 PDF 实际 4 题
（20/15/25/40 分），旧 _ESSAY_SECTION_HEAD_RE 把第 2 题行
「2. 给定材料2中提到……（15分）」误判为章节标题并 continue，
随后连续性剪枝把第 3/4 题一并丢掉，最终只入库 1 题。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.text_parser import (  # noqa: E402
    _ESSAY_SECTION_HEAD_RE,
    extract_question_blocks,
)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_BJ_2024 = os.path.join(
    _ROOT, '题库', '申论', '北京申论', '2024年北京市公考《申论》题.pdf')


def test_question_line_starting_with_material_is_not_section_heading():
    """真题行不能因为以「2. 给定材料2」开头就被当成章节标题。"""
    assert not _ESSAY_SECTION_HEAD_RE.match(
        '2. 给定材料2中提到“想要做好服务，就要‘眼高手低’，小题大做”，'
        '谈谈你对这句话的理解。（15分）')
    assert not _ESSAY_SECTION_HEAD_RE.match(
        '4. 阅读给定材料，结合你对材料中划线部分的思考，自拟题目，'
        '自选角度，写一篇议论文。（40分）')


def test_real_section_headings_still_match():
    """真正的章节标题必须继续命中，避免修过头。"""
    assert _ESSAY_SECTION_HEAD_RE.match('三、作答要求')
    assert _ESSAY_SECTION_HEAD_RE.match('一、给定材料')
    assert _ESSAY_SECTION_HEAD_RE.match('四、参考答案')


@pytest.mark.skipif(not os.path.exists(_BJ_2024),
                    reason='2024 北京申论语料不在磁盘上')
def test_real_2024_beijing_essay_has_four_questions():
    """真实 PDF：必须切出 4 题，分值 20/15/25/40，且每题都有要求。"""
    from app.api.v1.catalog.question_import import _extract_text_from_pdf

    with open(_BJ_2024, 'rb') as f:
        text = _extract_text_from_pdf(f.read())
    blocks = extract_question_blocks(text)

    assert len(blocks) == 4
    assert [b['question_number'] for b in blocks] == [1, 2, 3, 4]
    assert [b['score'] for b in blocks] == [20, 15, 25, 40]
    assert all(b.get('requirements') for b in blocks)
