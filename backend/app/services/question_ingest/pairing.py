"""分离导入文件名配对信号：归一化 + 相似度 + 诊断提示。

背景：分离导入时用户分别上传题目/答案两个文件，文件名是廉价且强力的配对信号。
历史缺陷是前端从未上传文件名，全仓也没有任何文件名配对机制（2026-10-12 实测）。
本模块只作**信号与诊断**，不强制覆盖内容匹配结果（手选优先）。
"""
import re
from difflib import SequenceMatcher
from typing import Optional

# 扩展名（doc/docx/pdf/txt/xlsx/xls/csv）
_EXT_RE = re.compile(r'\.(docx?|pdf|txt|xlsx?|csv)$', re.IGNORECASE)
# 答案文件后缀噪音词：答案及解析 / 答案与解析 / 答案解析 / 参考答案 / 答案 / 解析
_ANS_SUFFIX_RE = re.compile(
    r'[\s_\-—]*(?:答案及解析|答案与解析|答案解析|参考答案|答案|解析)\s*$')
# 括号标记（（部分）（打印）等）
_PAREN_RE = re.compile(r'[（(][^（）()]{0,6}[）)]')


def normalize_filename(name: str) -> str:
    """文件名归一化：去扩展名、去括号标记、去答案后缀、去空白。"""
    if not name:
        return ''
    base = _EXT_RE.sub('', name.strip())
    base = _PAREN_RE.sub('', base)
    base = _ANS_SUFFIX_RE.sub('', base)
    return re.sub(r'\s+', '', base)


def filename_similarity(questions_filename: str, answers_filename: str) -> float:
    """文件名相似度：归一化后 SequenceMatcher 与公共前缀占比取大者（0~1）。"""
    q = normalize_filename(questions_filename)
    a = normalize_filename(answers_filename)
    if not q or not a:
        return 0.0
    ratio = SequenceMatcher(None, q, a).ratio()
    i = 0
    while i < len(q) and i < len(a) and q[i] == a[i]:
        i += 1
    longest = max(len(q), len(a))
    prefix_ratio = i / longest if longest else 0.0
    return round(max(ratio, prefix_ratio), 4)


def diagnose_filename_pair(
    questions_filename: str, answers_filename: str, match_rate: float
) -> Optional[str]:
    """返回诊断提示文本；无需提示时返回 None。

    - 相似度高（>=0.5）但匹配率低（<60%）→ 疑似同一套卷、内容匹配失败；
    - 相似度低（<0.3）→ 提示核对文件。
    """
    if not questions_filename or not answers_filename:
        return None
    sim = filename_similarity(questions_filename, answers_filename)
    if sim >= 0.5 and match_rate < 60:
        return (
            f'题目与答案文件名高度相似（{round(sim * 100)}%），疑似同一套卷，'
            f'但内容匹配失败（匹配率 {round(match_rate, 1)}%）。'
            f'请检查答案文档格式，或改用人工匹配。'
        )
    if sim < 0.3:
        return (
            f'题目与答案文件名相似度低（{round(sim * 100)}%），'
            f'请核对是否选择了对应的两份文件。'
        )
    return None
