"""真实世界格式回归测试 —— 2016江西招警《人民警察基础知识》答案解析场景。

文档特征（源自真实PDF诊断）:
    - 题号行首格式: ``N、【考查XX】`` / ``N、本题考查XX。``
    - 答案唯一标记: 块内散文句 ``故正确答案为B。`` / ``本题正确答案为C``
    - 噪声源: 正文出现独立年份 ``2016`` / ``2015年11月`` —— 曾被
      extract_question_numbers 误判为题号（106个假题号）导致分块腰斩，
      匹配率跌至 52.6%（51/97）
    - 解析价值: 每块的选项分析（A项正确…D项错误…）即解析正文

验收基线: 该结构下匹配率必须 ≥95%，且解析字段不得大面积缺失。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from app.services.text_parser import (
    smart_match_questions_answers,
    extract_question_numbers,
    _extract_embedded_answers,
)

# 极简仿真样本：保留四类关键结构——顿号题号、年份噪声、内嵌答案句、逐项解析
SAMPLE_ANSWERS = (
    "2016 江西招警考试《人民警察基础知识》真题（部分）答案解析\n"
    "-1-\n"
    "1、本题考查法理学。\n"
    "法的渊源是指能作为法律决定的前提的法律资料。\n"
    "A项正确，宪法是国家最高权力机关制定的根本大法。\n"
    "B项错误，行政法规不是根本大法。\n"
    "C项错误，地方性法规效力低于宪法。\n"
    "D项错误，条约属于渊源但非最高。\n"
    "故正确答案为A。\n"
    "2、本题考查宪法学。\n"
    "2015 年我国修正了《立法法》。\n"
    "A项正确，立法法是全国性法律。\n"
    "B项错误，行政法规效力低于法律。\n"
    "故正确答案为A。\n"
    "3、本题考查刑法。\n"
    "刑法是规定犯罪与刑罚的法律规范总称。\n"
    "A项错误，民法调整平等主体关系。\n"
    "B项正确，刑法的任务是惩罚犯罪保护人民。\n"
    "故正确答案为B。\n"
    "4、本题考查行政法。\n"
    "行政许可遵循合法与效率原则。\n"
    "A项正确，许可设定须有法律依据。\n"
    "B项错误，规章不得擅自增设许可。\n"
    "C项正确，许可程序应当公开透明。\n"
    "D项错误，许可并非一律收费。\n"
    "故本题正确答案为AC。\n"
    "5、本题考查人民警察法。\n"
    "公安机关的人民警察按照职责分工依法执行职务。\n"
    "A项正确，警械使用须符合法定情形。\n"
    "B项错误，传唤不属于刑事强制措施。\n"
    "故正确答案为A。\n"
)

QUESTIONS_TEMPLATE = (
    "{n}、下列关于{topic}的说法，正确的是（\u3000\u3000）。\n"
    "A.说法一\nB.说法二\nC.说法三\nD.说法四\n"
)
TOPICS = ['法理学', '立法法', '刑法概念', '行政许可', '警察职权']


def _build_questions_text():
    parts = []
    for i, topic in enumerate(TOPICS, start=1):
        parts.append(QUESTIONS_TEMPLATE.format(n=i, topic=topic))
    return '\n'.join(parts)


class TestRealWorldJiangxi2016:
    def test_year_tokens_not_treated_as_question_numbers(self):
        """年份噪声(2016/2015年)不得进入题号表——52.6%根因的单元级验证。"""
        nums = extract_question_numbers(SAMPLE_ANSWERS)
        vals = [n.number for n in nums]
        assert 2016 not in vals, f'年份2016被误判为题号: {vals}'
        assert 2015 not in vals, f'年份2015被误判为题号: {vals}'
        assert vals[:5] == [1, 2, 3, 4, 5], f'真题号应完整有序: {vals}'

    def test_embedded_extraction_covers_all_blocks_with_analysis(self):
        """嵌入式策略必须覆盖全部5块并携带解析文本。"""
        m = _extract_embedded_answers(SAMPLE_ANSWERS)
        assert set(m.keys()) == {1, 2, 3, 4, 5}, f'缺块: {sorted(m.keys())}'
        assert m[1]['answer'] == 'A'
        assert m[3]['answer'] == 'B'
        assert m[4]['answer'] == 'AC', '多选字母组合不得丢失'
        # 解析字段：至少包含逐项分析内容
        analysis = m[1].get('analysis') or ''
        assert 'A项正确' in analysis

    def test_end_to_end_match_rate_ge_95(self):
        """端到端：该结构下匹配率≥95%且解析非空占比≥60%。"""
        r = smart_match_questions_answers(_build_questions_text(), SAMPLE_ANSWERS)
        assert r.total_questions == 5
        assert r.match_rate >= 0.95, (
            f'匹配率 {r.match_rate:.1%} 不达标 '
            f'(matched={r.matched_count}, unmatched={r.unmatched_question_numbers})')
        with_analysis = sum(
            1 for q in r.questions if q.get('analysis'))
        assert with_analysis >= 3, f'解析覆盖不足: {with_analysis}/5'

    def test_multichoice_letters_sorted(self):
        """多选答案 AC 归一化为升序（复用 canonical 规则）。"""
        m = _extract_embedded_answers(SAMPLE_ANSWERS)
        assert m[4]['answer'] == ''.join(sorted('AC'))
