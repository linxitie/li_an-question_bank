# -*- coding: utf-8 -*-
"""任务 21（模块 C-5）测试：分离与合并导入路径**共用同一套**三方交叉校验。

覆盖计划 QA Scenarios:
  Scenario 1  计数相等但内容错配必须被阻断（核心防线）
              — 构造 3 题题目文档 + 3 段答案文档，但答案顺序被打乱
                （第1题答案对应第3题），断言 blocked=True 且
                block_reasons 含 stem_fingerprint_mismatch
  Scenario 2  公专/行测链路零影响
              — 非申论文档必须被统一校验入口显式跳过（返回 None），
                由 gate_l1_parser.py --subject gongzhuan / gate_l2_matching.py
                另行覆盖字节级基线。

反向用例是本次改动的**主防线**：过去合并导入只校验「答案段数==题目数」，
一旦相等便整卷放行 → A 卷答案贴到 B 卷题目上，且入库后不可逆。
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.text_parser import extract_question_blocks
from app.api.v1.question_import import (
    _essay_cross_validate,
    _essay_split_combined_text,
    _essay_cross_validate_import,
)

# ─────────────────────────────────────────────────────────────────────
# 真实语料（安徽 2023 / 2024 A 卷）—— 两套卷题号、题量、分值分布完全相同，
# 只有题干措辞不同。这正是「计数相等但错配」的教科书样本。
# ─────────────────────────────────────────────────────────────────────
_SL_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), '题库', '申论', '安徽申论')

_SL_CORPUS = {
    'q2023': '2023年公务员多省联考《申论》题（安徽A、普通选调卷）.pdf',
    'a2023': '2023年公务员多省联考《申论》题（安徽A、普通选调卷）答案.pdf',
    'q2024': '2024年公务员多省联考《申论》题（安徽A、普通选调卷）.pdf',
    'a2024': '2024年公务员多省联考《申论》题（安徽A、普通选调卷）答案.pdf',
}


def _has_corpus():
    return all(os.path.exists(os.path.join(_SL_ROOT, v)) for v in _SL_CORPUS.values())


def _load_corpus():
    from app.api.v1.question_import import _extract_text_from_pdf
    out = {}
    for key, name in _SL_CORPUS.items():
        with open(os.path.join(_SL_ROOT, name), 'rb') as f:
            out[key] = _extract_text_from_pdf(f.read())
    return out


# ── 3 题合成样本（无语料环境也能跑）────────────────────────────────
# 题目侧与答案侧的题号/分值完全相同，仅题干措辞不同 —— 纯计数校验抓不住。
_Q_COMBINED = """给定资料
（一）材料正文，围绕城市基层治理展开论述，篇幅若干。

1. 根据给定资料1，请概括当前城市社区治理面临的主要问题（15分）
要求：全面、准确、有条理；不超过200字。

2. 请结合给定资料2，谈谈你对新局蕴新机这句话的理解（20分）
要求：观点明确，分析透彻，不超过300字。

3. 假设你是C市老龄办工作人员，请根据给定资料3提出对策建议（25分）
要求：针对性强、具体可行、分条列出，不超过400字。
"""


def _answer_block(qno, stem, score, body):
    """答案区的一个题块：自带完整题干（安徽/国考答案卷的真实版式）。"""
    return f"{qno}. {stem}（{score}分）\n要求：略。\n参考答案：{body}\n"


def _shuffled_answers(stems_scores, bodies):
    """按题号槽位 1/2/3 排布，但槽位里装的**题干与答案**互换：

        槽位1 → 第3题的题干 + 第3题的答案
        槽位2 → 第1题的题干 + 第1题的答案
        槽位3 → 第2题的题干 + 第2题的答案

    即「第1题槽位对应的是第3题」。两边的题号、题数、分值分布完全相同，
    纯计数校验必然漏放 —— 这正是要拦住的目标。
    """
    order = [2, 0, 1]
    parts = []
    for slot, k in enumerate(order, start=1):
        _qno, stem, score = stems_scores[k]
        parts.append(_answer_block(slot, stem, score, bodies[k]))
    return ''.join(parts)


_STEMS = [
    (1, "根据给定资料1，请概括当前城市社区治理面临的主要问题", 15),
    (2, "请结合给定资料2，谈谈你对新局蕴新机这句话的理解", 20),
    (3, "假设你是C市老龄办工作人员，请根据给定资料3提出对策建议", 25),
]
_BODIES = ["答案甲：人手不足、制度不健全、权责不清。",
           "答案乙：投入不足、专业力量缺乏、数据壁垒。",
           "答案丙：加强顶层设计、补齐设施、培养专干。"]


# ═════════════════════════════════════════════════════════════════════
# Scenario 1：计数相等但内容错配必须被阻断（核心防线）
# ═════════════════════════════════════════════════════════════════════

def test_reverse_count_equal_but_mismatched_is_blocked():
    """3 题题目文档 + 3 段答案文档，答案顺序被打乱 → 必须 blocked 且带
    stem_fingerprint_mismatch。

    反向用例：若放行，用户的每条答案都会贴到别人的题目上（第1题拿第3题答案），
    而这正是用户硬约束 2 明令禁止的「计数相等但错配」。
    """
    shuffled = _shuffled_answers(_STEMS, _BODIES)
    q_blocks = extract_question_blocks(_Q_COMBINED)
    a_blocks = extract_question_blocks(shuffled)

    # 前置条件：两侧题数相等、题号集合相同 —— 说明纯计数校验拦不住
    assert len(q_blocks) == len(a_blocks) == 3
    assert {b['question_number'] for b in q_blocks} == \
           {b['question_number'] for b in a_blocks}

    merged = _essay_cross_validate(q_blocks, a_blocks)

    # 核心断言：一律 blocked，绝不按序硬配
    blocked = [q for q in merged['questions'] if q['blocked']]
    assert blocked, "计数相等但错配被放行 —— 错配将不可逆地入库"
    assert merged['report']['blocked_count'] >= 1

    reasons = {r for q in merged['questions'] for r in q['block_reasons']}
    assert 'stem_fingerprint_mismatch' in reasons


def test_reverse_mismatch_on_merged_import_path_is_blocked():
    """合并导入（合订本）走 `_essay_cross_validate_import`，同一判据同样阻断。"""
    shuffled_answer_area = _shuffled_answers(_STEMS, _BODIES)
    combined = _Q_COMBINED + "\n" + shuffled_answer_area

    merged = _essay_cross_validate_import(combined)
    assert merged is not None, "合并导入的申论文档未被统一校验入口接住"

    assert merged['report']['blocked_count'] >= 1
    reasons = {r for q in merged['questions'] for r in q['block_reasons']}
    assert 'stem_fingerprint_mismatch' in reasons


@pytest.mark.skipif(not _has_corpus(), reason='安徽申论语料不在磁盘上')
def test_reverse_real_corpus_cross_year_mismatch_is_blocked():
    """真实语料：安徽 2023 题本 + 2024 答案卷。

    两套卷题量/题号/分值分布完全相同（4 题，15/20/25/40 分），
    纯计数校验 blocked_count=0；题干指纹必须把它拦住。
    """
    corpus = _load_corpus()
    q_blocks = extract_question_blocks(corpus['q2023'])
    a_blocks = extract_question_blocks(corpus['a2024'])

    # 计数相等的铁证
    assert len(q_blocks) == len(a_blocks) == 4
    assert [b['score'] for b in q_blocks] == [b['score'] for b in a_blocks]

    merged = _essay_cross_validate(q_blocks, a_blocks)
    assert merged['report']['blocked_count'] == 4
    reasons = {r for q in merged['questions'] for r in q['block_reasons']}
    assert reasons == {'stem_fingerprint_mismatch'}


@pytest.mark.skipif(not _has_corpus(),
                    reason='安徽申论语料不在磁盘上')
def test_real_corpus_correct_pairing_still_passes():
    """反向配对的对照组：同一年份的正确配对必须 0 阻断。
    防止三方校验被无意间收紧成「一律阻断」。
    """
    corpus = _load_corpus()
    merged = _essay_cross_validate(
        extract_question_blocks(corpus['q2023']),
        extract_question_blocks(corpus['a2023']))
    assert merged['report']['blocked_count'] == 0


def test_combined_import_correct_pairing_still_passes():
    """合并导入的正确配对同样必须 0 阻断（防止收紧过度）。"""
    combined = _Q_COMBINED + "\n" + ''.join(
        _answer_block(*s, b) for s, b in zip(_STEMS, _BODIES))
    merged = _essay_cross_validate_import(combined)
    assert merged is not None
    assert merged['report']['blocked_count'] == 0


# ═════════════════════════════════════════════════════════════════════
# Scenario 2：公专/行测链路零影响
# ═════════════════════════════════════════════════════════════════════

def test_gongzhuan_doc_is_bypassed_by_unified_validator():
    """公专体例文档 → 统一校验入口必须返回 None（跳过申论判据）。"""
    gongzhuan = """1. 依据《治安管理处罚法》的规定，下列行为中应当给予治安管理处罚的是（ ）。
A. 甲在公共场所故意裸露身体
B. 乙在家中独自饮酒
C. 丙主动参加社区志愿服务
D. 丁按时上下班遵守交通规则
【答案】A
【解析】本题考查治安管理处罚的适用范围。
2. 公安机关办理行政案件时，对违法嫌疑人的询问查证时间不得超过（ ）。
A. 4小时
B. 8小时
C. 12小时
D. 24小时
【答案】B
【解析】询问查证时间不得超过8小时。
"""
    assert _essay_cross_validate_import(gongzhuan) is None


def test_xingce_doc_is_bypassed_by_unified_validator():
    """行测体例文档 → 统一校验入口必须返回 None。"""
    xingce = """一、常识判断
1. 下列属于我国宪法基本原则的是（ ）。
A. 人民主权原则
B. 三权分立原则
C. 君主立宪原则
D. 联邦制原则
答案：A
2. 我国现行的宪法是哪一年颁布的（ ）。
A. 1949年
B. 1982年
C. 1993年
D. 2004年
答案：B
"""
    assert _essay_cross_validate_import(xingce) is None


def test_empty_text_is_bypassed():
    assert _essay_cross_validate_import('') is None
    assert _essay_cross_validate_import('   \n  \n') is None


# ═════════════════════════════════════════════════════════════════════
# 分离与合并共用同一实现（不是两份）
# ═════════════════════════════════════════════════════════════════════

def test_merged_and_separate_paths_share_one_validator():
    """合并入口必须最终落到同一个 `_essay_cross_validate` 上。

    做法：对同一份题目文本与同一份答案文本，比较
      ① 分离路径  _essay_cross_validate(q_blocks, a_blocks)
      ② 合并路径  _essay_cross_validate_import(q_text + a_text)
    两次报告必须逐字段一致 —— 证据上排除「两份实现漂移」。
    """
    answer_area = ''.join(_answer_block(*s, b) for s, b in zip(_STEMS, _BODIES))
    combined = _Q_COMBINED + "\n" + answer_area

    q_blocks = extract_question_blocks(_Q_COMBINED)
    a_blocks = extract_question_blocks(answer_area)
    separate = _essay_cross_validate(q_blocks, a_blocks)
    merged = _essay_cross_validate_import(combined)

    assert merged is not None
    for key in ('question_count', 'answer_count', 'matched', 'blocked_count'):
        assert merged['report'][key] == separate['report'][key], (
            f'{key} 两条路径不一致 → 说明存在两份实现')

    # 阻断原因也应逐题一致（顺序一致）
    assert [q['block_reasons'] for q in merged['questions']] == \
           [q['block_reasons'] for q in separate['questions']]


def test_inline_answer_essay_doc_falls_back():
    """形态②③（答案紧随每题、就地配对）没有文末统一答案区，
    统一入口必须返回 None，交回既有解析逻辑，绝不强行拆分。"""
    inline = """1. 请根据给定资料，概括当前城市社区治理面临的主要问题。（15分）
要求：全面、准确、有条理。
参考答案：人手不足；制度不健全。
2. 请结合给定资料，分析上述问题的成因。（20分）
要求：观点明确，分析透彻。
参考答案：投入不足；专业力量缺乏。
"""
    assert _essay_cross_validate_import(inline) is None


def test_split_combined_text_boundary_is_after_last_question():
    """切分边界必须落在最后一道真题之后 —— 绝不允许把题区末尾划进答案侧。"""
    answer_area = ''.join(_answer_block(*s, b) for s, b in zip(_STEMS, _BODIES))
    combined = _Q_COMBINED + "\n" + answer_area

    q_text, a_text = _essay_split_combined_text(combined)
    assert q_text is not None and a_text is not None

    # 题目侧应仍含 3 道题，答案侧应含 3 个自带题干的答案块
    assert len(extract_question_blocks(q_text)) == 3
    assert len(extract_question_blocks(a_text)) == 3
    # 题目侧不应出现任何答案锚点
    assert '参考答案' not in q_text
