"""公专（公安专业科目）链路回归用例 —— 计划任务 20（模块 C-1/C-6）

锁定三类问题，防止既有行为被后续改动悄悄回退：

① 选项字母错位：真实公专语料的 `A.\nB.\nC.\nD.`（字母+取值的选项）
   必须产出 4 个选项，**不得**产出错位形态 `[{'key':'A','value':'B.'},
   {'key':'C','value':'D.'}]`（字母被当成值、真实取值丢失）。

   实证依据：`.omo/notepads/xingce-import-optimization/followup-findings.md:17-23`
   —— 行测链路 244 题被该缺陷污染且 100% 落在简答题型；
   公专同类缺陷 **0 / 2583，未污染**。本用例负责守住这个 0。

   注意：错位**只**在「裸字母、无任何取值」的退化输入上出现
   （实测 `_extract_options(['A.','B.','C.','D.'])` 即错位）；
   公专真实语料（含广东 2024 的 `A.13\nB.14\nC.15\nD.16` 跨行取值）
   全部产出 4 个正确选项。修复只允许进行测专用路径，
   **不得**改公专共用的 `_extract_options`，故该退化形态以
   `xfail(strict=True)` 记录在案：一旦有人修好它，strict 会立刻报警提示摘除标记。

② 公专 0 题的 `requirements` 不得被自动填充 —— 守住「缺省留空不伪造」。

③ 铁律 R-5（`solve_problems_files/行测题目导入优化方案.md:70`）：
   省份**只能**来自文件夹名。文件名不含「省」但文件夹名含「省」时，
   省份必须从文件夹名正确取到；无文件夹名时宁缺勿滥，绝不用文件名猜。

本文件只锁定行为，不改任何实现；不构造虚拟文件。
红线（不得触碰）：
- `text_parser.extract_question_blocks` 函数体 —— 字节级红线
- 公专 `_extract_options` 实现 —— 修复只允许进行测专用路径
"""
import os
import sys

import pytest

# 确保 backend 目录在 sys.path 中（与 tests/conftest.py 保持一致）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.v1.question_import import (  # noqa: E402
    _auto_detect_tags,
    _normalize_requirements,
    _resolve_xingce_paper_metadata,
)
from app.services.text_parser import extract_question_blocks  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════
# ① 选项字母错位防御（公专零回归）
# ══════════════════════════════════════════════════════════════════════════

# 错位签名：选项的「值」本身退化成了一个裸选项标记
_BARE_OPTION_MARKERS = {'A.', 'B.', 'C.', 'D.', 'A、', 'B、', 'C、', 'D.',
                        'A．', 'B．', 'C．', 'D．'}


def _is_letter_misaligned(options) -> bool:
    """判断选项是否呈字母错位：某个「值」本身只是裸选项标记。"""
    for opt in options or []:
        val = str(opt.get('value', '')).strip()
        if val in _BARE_OPTION_MARKERS:
            return True
    return False


# 公专真实语料的选项形态（实测 2583 题 0 污染的全部形态）
_GONGZHUAN_OPTION_FORMS = {
    # 最常见：中文取值
    'chinese_values': [
        'A. 预防、制止和侦查违法犯罪活动',
        'B. 维护社会治安秩序',
        'C. 保护公共财产',
        'D. 维护国家安全',
    ],
    # 广东 2024 实测：字母与取值「跨行」的数字取值（findings.md:21-22 同源）
    'digit_values_cross_line': ['A.13', 'B.14', 'C.15', 'D.16'],
    # 顿号分隔
    'dunhao_separator': ['A、第一项', 'B、第二项', 'C、第三项', 'D、第四项'],
    # 中文序号取值
    'chinese_numeral_values': ['A. 一是', 'B. 二是', 'C. 三是', 'D. 四是'],
}


@pytest.mark.parametrize(
    'form_name,option_lines',
    list(_GONGZHUAN_OPTION_FORMS.items()),
    ids=list(_GONGZHUAN_OPTION_FORMS.keys()),
)
def test_gongzhuan_options_yield_four_not_misaligned(form_name, option_lines):
    """公专链路必须产出 4 个选项，且不得出现字母错位 `[{'A':'B.'},{'C':'D.'}]`。"""
    from app.services.text_parser import _extract_options

    options = _extract_options(option_lines)

    assert len(options) == 4, f'期望 4 个选项，实得 {len(options)}: {options}'
    assert [o.get('key') for o in options] == ['A', 'B', 'C', 'D']
    assert not _is_letter_misaligned(options), f'出现字母错位: {options}'
    # 选项的「值」必须保留真实取值，不能被字母标记吞掉
    for opt in options:
        assert str(opt.get('value', '')).strip(), f'选项值丢失: {opt}'


def test_gongzhuan_end_to_end_question_options_not_misaligned():
    """端到端：公专试卷文本解析出的每道题都必须带 4 个完整选项。"""
    text = (
        '1. 公安机关的人民警察依法履行下列哪些职责？\n'
        'A. 预防、制止和侦查违法犯罪活动\n'
        'B. 维护社会治安秩序\n'
        'C. 保护公共财产\n'
        'D. 维护国家安全\n'
        '\n'
        '2. 人民警察的纪律要求包括下列哪些？\n'
        'A. 不得散布有损国家声誉的言论\n'
        'B. 不得泄露国家秘密\n'
        'C. 不得刑讯逼供\n'
        'D. 不得殴打他人\n'
    )
    blocks = extract_question_blocks(text)
    assert len(blocks) == 2, f'期望解析出 2 题，实得 {len(blocks)}'

    for blk in blocks:
        options = blk.get('options') or []
        assert len(options) == 4, f'第 {blk.get("question_number")} 题选项数异常: {options}'
        assert [o.get('key') for o in options] == ['A', 'B', 'C', 'D']
        assert not _is_letter_misaligned(options), f'第 {blk.get("question_number")} 题字母错位: {options}'


@pytest.mark.xfail(
    reason='已知退化形态：裸字母无取值时 _extract_options 退化为错位。'
           '公专真实语料不出现该形态（实证 0/2583）；'
           '修复只允许走「行测专用路径」，不得改公专共用的 _extract_options。'
           '若本用例转 PASSED，说明有人已修复 —— 请删除本 xfail 标记。',
    strict=True,
)
def test_bare_letters_without_values_currently_misaligned():
    """记录在案的已知缺陷：`A.\\nB.\\nC.\\nD.`（裸字母无取值）会错位。

    xfail(strict=True)：当前必定失败；一旦被修好，strict 会报警要求摘除标记。
    本用例**不**改写该行为——修复必须进行测专用路径（红线）。
    """
    from app.services.text_parser import _extract_options

    options = _extract_options(['A.', 'B.', 'C.', 'D.'])

    # 目标行为（尚未达成，故 xfail）
    assert len(options) == 4, f'期望 4 个选项，实得 {len(options)}: {options}'
    assert [o.get('key') for o in options] == ['A', 'B', 'C', 'D']
    assert not _is_letter_misaligned(options)


# ══════════════════════════════════════════════════════════════════════════
# ② 0 题 requirements 不得自动填充（缺省留空不伪造）
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    'label,raw',
    [
        ('none', None),
        ('empty_list', []),
        ('empty_str', ''),
        ('whitespace_str', '   '),
        ('list_all_none', [None, None]),
        ('list_all_empty_str', ['', '  ']),
    ],
    ids=['none', 'empty_list', 'empty_str', 'whitespace_str',
         'list_all_none', 'list_all_empty_str'],
)
def test_normalize_requirements_empty_by_default(label, raw):
    """`_normalize_requirements` 对一切缺省形态一律返回空串，绝不伪造。"""
    assert _normalize_requirements(raw) == ''


@pytest.mark.parametrize(
    'label,text',
    [
        ('empty', ''),
        ('whitespace_only', '   \n\n  '),
        ('plain_prose', '这是一段没有任何题目的说明文字，仅用于确认 0 题场景。'),
    ],
    ids=['empty', 'whitespace_only', 'plain_prose'],
)
def test_zero_question_doc_leaves_requirements_empty(label, text):
    """0 题文档：解析不出任何题块，requirements 绝不被自动填充。"""
    blocks = extract_question_blocks(text)

    assert blocks == [], f'0 题文档不应产出题块，实得 {len(blocks)} 个'
    # 连题块都没有 → 没有任何地方能塞进伪造的 requirements
    assert all(not (b.get('requirements') or []) for b in blocks)


def test_gongzhuan_question_requirements_stay_empty():
    """公专客观题解析出的 requirements 缺省留空（公专题无作答要求概念）。"""
    text = (
        '1. 公安机关的人民警察依法履行下列哪些职责？\n'
        'A. 预防、制止和侦查违法犯罪活动\n'
        'B. 维护社会治安秩序\n'
        'C. 保护公共财产\n'
        'D. 维护国家安全\n'
    )
    blocks = extract_question_blocks(text)
    assert len(blocks) == 1

    for blk in blocks:
        assert not (blk.get('requirements') or []), \
            f'公专题不得自动填充 requirements，实得: {blk.get("requirements")}'
        # 落库口径同样必须为空，不得借 _normalize_requirements 伪造出内容
        assert _normalize_requirements(blk.get('requirements')) == ''


def test_normalize_requirements_preserves_real_content():
    """对照守卫：确有要求时必须原样保留（防止「一律清空」的过度修复）。"""
    listed = ['（1）紧扣资料，内容全面；', '（2）不超过500 字']
    assert _normalize_requirements(listed) == '（1）紧扣资料，内容全面；\n（2）不超过500 字'

    plain = '全面、准确、有条理。不超过250字。'
    assert _normalize_requirements(plain) == plain


# ══════════════════════════════════════════════════════════════════════════
# ③ 省份只从文件夹名取（铁律 R-5）
# ══════════════════════════════════════════════════════════════════════════

# 实测中文件名省份写法不可靠的全部证据（`行测题目导入优化方案.md:70`）：
# 2025 年安徽/河南/山西/陕西/黑龙江全部缺「省」字，甘肃 3 个年份全省缺「省」，
# 广西写「区考」。而 24 个省级文件夹名干净一致 —— 故省份只能来自文件夹名。
#
# 期望值说明：省份取**文件夹名原样**（仅剥离「行测/申论/公专」科目尾巴），
# 不追加臆造的「省」字 —— 尊重文件夹名的实际写法，宁缺勿滥。
_FOLDER_PROVINCE_CASES = [
    # (文件夹名, 文件名, 期望省份)
    ('安徽省行测', '2025年联考公务员.pdf', '安徽省'),
    ('河南省行测', '2025年多省公务员.pdf', '河南省'),
    ('山西省行测', '2025年录用公务员.pdf', '山西省'),
    ('陕西省行测', '2025年公务员.pdf', '陕西省'),
    ('黑龙江省行测', '2025年公务员考试.pdf', '黑龙江省'),
    ('黑龙江行测', '2025年公务员考试.pdf', '黑龙江'),
    ('甘肃省行测', '2025年行测真题.pdf', '甘肃省'),
    ('甘肃行测', '2025年行测真题.pdf', '甘肃'),
    ('江苏省行测', '2025年公务员考试.pdf', '江苏省'),
]


@pytest.mark.parametrize(
    'folder_name,filename,expected',
    _FOLDER_PROVINCE_CASES,
    ids=[f'{c[0]}<-{c[1]}' for c in _FOLDER_PROVINCE_CASES],
)
def test_province_taken_from_folder_name_not_filename(folder_name, filename, expected):
    """文件名不含「省」但文件夹名含「省」时 → 省份必须从文件夹名正确取到。"""
    # 正文同样不含任何省份关键词，确保不可能是正文泄露
    neutral_text = '给定资料：某市开展社区警务改革试点，请根据以下材料回答问题。' * 3

    tags = _resolve_xingce_paper_metadata(
        folder_name=folder_name,
        filename=filename,
        text=neutral_text,
    )

    assert tags.get('exam_province') == expected


def test_province_never_inferred_from_filename():
    """无文件夹名时，文件名里的省份一律不得被猜出来（宁缺勿滥）。"""
    tags = _resolve_xingce_paper_metadata(
        folder_name='',
        filename='2025年河南省公务员考试录用公告.pdf',
        text='给定资料：某省推进公安执法规范化建设。',
    )
    assert tags.get('exam_province') is None


def test_province_never_inferred_from_document_body():
    """正文里出现省份时也不得被采用 —— 省份的唯一来源是文件夹名。"""
    tags = _resolve_xingce_paper_metadata(
        folder_name='安徽省行测',
        filename='2025年联考.pdf',
        text='北京市公安局2025年度考试录用公务员公告',  # 正文含「北京」
    )
    # 文件夹名优先，正文的「北京」不得覆盖
    assert tags.get('exam_province') == '安徽省'


def test_province_marks_national_exam_not_a_province():
    """国考全国卷：显式标注「国考」，绝不用文件名退化成某省。"""
    tags = _resolve_xingce_paper_metadata(
        folder_name='国考行测',
        filename='2025年河南省公务员考试录用公告.pdf',
        text='给定资料：某省推进公安执法规范化建设。',
    )
    assert tags.get('exam_province') == '国考'


def test_folder_subject_suffix_is_stripped():
    """文件夹名的「行测/申论/公专」科目尾巴必须被剥离，只留省份本身。"""
    tags = _resolve_xingce_paper_metadata(
        folder_name='河南省公专',
        filename='2025年联考.pdf',
        text='给定资料：某市推进公安执法规范化建设。',
    )
    assert tags.get('exam_province') == '河南省'


def test_auto_detect_tags_has_no_filename_province_inference():
    """`_auto_detect_tags` 自身不得再从文件名/正文推断省份（R-5 兜底守卫）。

    该函数仅持有 filename / text，没有文件夹名可用；
    省份应由调用方通过文件夹名显式覆盖，而非在此处猜。
    """
    tags = _auto_detect_tags(
        '2025年安徽省公务员考试录用公告.pdf',
        '安徽省2025年度考试录用公务员公告',
    )
    assert 'exam_province' not in tags
    assert tags.get('exam_province') is None
