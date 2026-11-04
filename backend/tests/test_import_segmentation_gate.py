"""P1-6 切分闸门：题号对账必须只拦“成片漏切”，不误伤删题/片段卷。"""
from app.api.v1.catalog.question_import import _detect_numbering_gap


ESSAY_TEXT = """1. 根据给定材料，概括北京经验。（20分）
要求：准确全面。

2. 给定材料2中提到“想要做好服务”，谈谈理解。（15分）
要求：分析合理。

3. 阅读给定材料5，提出对策建议。（25分）
要求：建议合理可行。

4. 结合材料，自拟题目写文章。（40分）
要求：观点鲜明。
"""


def _essay_items(*numbers):
    return [
        {'question_number': n, 'subject_name': '申论', 'question_content': f'第{n}题'}
        for n in numbers
    ]


def test_essay_four_questions_collapsed_to_one_is_blocked():
    gap = _detect_numbering_gap(_essay_items(1), ESSAY_TEXT, '申论')
    assert gap is not None
    assert gap['expected'] == 4
    assert gap['actual'] == 1
    assert gap['missing'] == [2, 3, 4]


def test_complete_essay_has_no_gap():
    assert _detect_numbering_gap(_essay_items(1, 2, 3, 4), ESSAY_TEXT, '申论') is None


def test_single_missing_question_is_not_blocked():
    """只缺 1 题可能是原卷删题，不能阻断整批。"""
    assert _detect_numbering_gap(_essay_items(1, 2, 4), ESSAY_TEXT, '申论') is None


def test_fragment_paper_starting_at_101_is_not_blocked():
    """只有 101-125 题的片段卷，不能被误判成缺 1-100 题。"""
    text = '\n'.join(f'{n}. 片段题题干' for n in range(101, 126))
    items = [{'question_number': n, 'subject_name': '行测'} for n in range(101, 126)]
    assert _detect_numbering_gap(items, text, '行测') is None
