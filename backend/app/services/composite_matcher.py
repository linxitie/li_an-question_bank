# -*- coding: utf-8 -*-
"""
composite_matcher.py — 复合题（题组）规则引擎识别（方案 v1.0 层1）

职责：仅做"识别与题号范围判定"，返回结构化结果，**不操作数据库**。
由 question_import._detect_and_link_composite_groups 调用落库。

层1 规则集（确定性识别，无模型，O(n)）：
  1. 题号范围（range） ：根据以下材料/情境/文章/图表…回答X-Y题（明确题号范围）
  2. 材料标识（material）：材料一/资料1/材料：…（后续连续题号归属）
  3. 情境标识（scenario）：根据以下情境…（后续连续题号归属）
  4. 文章标识（passage）：阅读以下文章/阅读下面/给定资料…（后续连续题号归属）

设计原则：
  - 复用 text_parser.extract_question_numbers 统一题号提取，禁止另写解析
  - 不存向量、不落盘，仅返回 (group_type, title, member_qnums)
  - 判定失败不抛异常，返回 None 由调用方跳过
"""
import re
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# 规则集：(规则名, 正则, 静态 group_type)
#   - range 规则的 group_type 需按内容动态判定（含"情境"→scenario，否则→material）
#   - material/scenario/passage 规则的 group_type 静态确定
_GROUP_HEAD_RULES = [
    (
        'range',
        re.compile(
            r'根据以[下此][^\n]{0,40}?(?:材料|情境|文章|图表)'
            r'[^\n]{0,30}?回答\s*(\d+)\s*[-～~—－]\s*(\d+)\s*题?'
        ),
        None,
    ),
    ('material', re.compile(r'^(?:材料|资料)\s*[一二三四五六七八九十\d]+[：:．.]'), 'material'),
    ('scenario', re.compile(r'^根据以下情境'), 'scenario'),
    ('passage', re.compile(r'^(?:阅读以下文章|阅读下面|给定资料)'), 'passage'),
]

# 材料头无明确范围时，连续题号推断的最大跨度（防御异常，超过则判定断裂）
_MAX_GAP = 1
# 单个题组最多挂题数（防御异常，超过视为切分异常）
_MAX_MEMBERS = 30


def match_group_head(content: str):
    """匹配题组头规则。

    返回 (group_type, qnum_range) 或 None：
      - group_type: 'material' | 'scenario' | 'passage' | 'data_analysis'
      - qnum_range: (start, end) 明确题号范围；无明确范围时为 None（需后续连续题号推断）
    """
    if not content or not isinstance(content, str):
        return None
    text = content.strip()
    for name, pattern, static_type in _GROUP_HEAD_RULES:
        m = pattern.search(text)
        if not m:
            continue
        if name == 'range':
            x, y = int(m.group(1)), int(m.group(2))
            if y < x or y - x > 20:  # 防御异常范围（复用既有校验）
                return None
            gtype = 'scenario' if '情境' in m.group(0) else 'material'
            return gtype, (x, y)
        # material/scenario/passage：无明确题号范围
        return static_type, None
    return None


def infer_member_qnums(
    head_qnum: Optional[int],
    candidate_qnums: List[int],
    qnum_range: Optional[Tuple[int, int]],
) -> List[int]:
    """给定头题题号、批内候选小题题号、明确范围，返回应挂组的小题题号列表（升序）。

    - 有明确 qnum_range：返回 range 内（含边界）的候选题号。
    - 无 qnum_range：从头题题号之后，按连续递增（gap==1）收集候选，
      遇到断档（gap>1）或达到 _MAX_MEMBERS 即停止。
    """
    cands = sorted([qn for qn in candidate_qnums if qn is not None])
    if not cands:
        return []

    if qnum_range is not None:
        x, y = qnum_range
        return [qn for qn in cands if x <= qn <= y]

    # 无明确范围：从 head_qnum 之后连续递增收集
    if head_qnum is None:
        # 头题无题号（纯材料段落）→ 从候选中的第一个题号开始连续收集
        members = []
        prev = None
        for qn in cands:
            if prev is None:
                members.append(qn)
                prev = qn
            elif qn - prev == _MAX_GAP:
                members.append(qn)
                prev = qn
            else:
                break
            if len(members) >= _MAX_MEMBERS:
                break
        return members

    members = []
    expect = head_qnum + 1
    for qn in cands:
        if qn == expect:
            members.append(qn)
            expect += 1
            if len(members) >= _MAX_MEMBERS:
                break
        elif qn > expect:
            break  # 断档
        # qn < expect 说明重复/乱序，跳过
    return members
