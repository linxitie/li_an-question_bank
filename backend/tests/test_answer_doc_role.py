"""答案文档角色判定与答案条目解析（2026-10-25 导入配对事故回归）。

事故：答案 PDF 被当成题目文档切块，题本 125 块 / 答案 95 块，
教师看到"答案对不上"。本组用例锁定两个纯函数的行为：
  - looks_like_answer_document：文件名/正文信号判定答案卷
  - extract_answer_entries：答案卷 → 题号/答案/解析条目
"""
from app.services.text_parser import (
    extract_answer_entries,
    looks_like_answer_document,
)

ANSWER_TEXT = """2025年某省公务员录用考试《行测》答案解析

1．C
【解析】本题考查政治常识，故选 C。

2．A
【解析】由材料可知，答案为 A。

3．D
【解析】计算可得 D 项正确。

4．B
【解析】B 项符合题意。

5．A
【解析】A 项当选。
"""

QUESTION_TEXT = """2025年某省公务员录用考试《行测》题本

1．下列表述正确的是（ ）
A．甲
B．乙
C．丙
D．丁

2．由上题可知（ ）
A．1
B．2
C．3
D．4
"""


def test_filename_marks_answer_document():
    assert looks_like_answer_document('', '2025年安徽行测答案解析.pdf') is True
    assert looks_like_answer_document('', '2025年安徽行测题本.pdf') is False


def test_content_marks_answer_document():
    assert looks_like_answer_document(ANSWER_TEXT) is True


def test_question_text_is_not_answer_document():
    assert looks_like_answer_document(QUESTION_TEXT) is False


def test_extract_answer_entries_keeps_numbers_and_answers():
    entries = extract_answer_entries(ANSWER_TEXT)
    numbers = [e['number'] for e in entries]
    assert numbers == [1, 2, 3, 4, 5]
    assert [e['answer'] for e in entries] == ['C', 'A', 'D', 'B', 'A']
    # 解析必须跟着题号走，不能串到下一题
    assert '政治常识' in entries[0]['analysis']
    assert '材料' in entries[1]['analysis']
    assert '计算' in entries[2]['analysis']


def test_extract_answer_entries_matches_question_count():
    """同题号的题目卷与答案卷，条目数必须一致（配对可比对）。"""
    entries = extract_answer_entries(ANSWER_TEXT)
    assert len(entries) == 5
    assert len({e['number'] for e in entries}) == 5
