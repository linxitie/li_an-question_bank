"""D-37 回归：解析期字符串状态必须归一化成库内整数枚举。

背景（2026-11-16 逐项测试实测）：真实真题 docx 解析出 90 题，`preview_data` 里
每条的 `status` 都是字符串 `'NEW'`；而通用校验器只接受整数 {0,1}，
于是 90/90 全部被判 `R-ENUM: status 必须是 [0, 1]`，批量导入 100% 不可用。

修法在导入层归一化（`normalize_parse_status`），校验器语义保持不变。
本文件钉住：
  1. 业务字符串能映射成 0/1；
  2. 认不出的字符串被剔除（不让它误杀正常题目）；
  3. 非法整数值仍会被校验器拒绝 —— 归一化没有把校验改宽。
"""
import pytest

from app.api.v1.catalog.question_import import normalize_parse_status
from app.foundation.validation import ReferenceCache, validate_question


def _base():
    return {
        'question_content': '测试题干：下列说法正确的是（ ）。',
        'options': ['A. 甲', 'B. 乙', 'C. 丙', 'D. 丁'],
        'answer': 'A',
        'difficulty': 3,
        'score': 1,
    }


@pytest.mark.parametrize('raw,expected', [
    ('NEW', 0),
    ('DRAFT', 0),
    ('unpublished', 0),
    (' new ', 0),
    ('PUBLISHED', 1),
    ('online', 1),
    ('0', 0),
    ('1', 1),
])
def test_string_status_normalized(raw, expected):
    item = _base()
    item['status'] = raw
    assert normalize_parse_status(item)['status'] == expected


@pytest.mark.parametrize('raw', ['ANSWER_ONLY', 'weird-state', ''])
def test_unknown_string_status_removed(raw):
    item = _base()
    item['status'] = raw
    assert 'status' not in normalize_parse_status(item)


def test_int_status_untouched():
    for value in (0, 1, 9):
        item = _base()
        item['status'] = value
        assert normalize_parse_status(item)['status'] == value


def test_normalized_item_passes_validator():
    """归一化后 'NEW' 不再触发 R-ENUM（这正是 90 题被拒的原因）。"""
    item = _base()
    item['status'] = 'NEW'
    normalize_parse_status(item)
    issues = validate_question(item, ReferenceCache(), partial=True, require_ids=False)
    assert not any(i.rule == 'R-ENUM' and getattr(i, 'field', '') == 'status' for i in issues), issues


def test_invalid_int_still_rejected_by_validator():
    """防改宽：归一化不处理 int，非法整数仍必须被校验器拒绝。"""
    item = _base()
    item['status'] = 9
    normalize_parse_status(item)
    issues = validate_question(item, ReferenceCache(), partial=True, require_ids=False)
    assert any(i.rule == 'R-ENUM' and getattr(i, 'field', '') == 'status' for i in issues), issues
