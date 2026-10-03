# -*- coding: utf-8 -*-
"""
composite_matcher.py — 复合题（题组）识别引擎（方案 v1.0 层1 + 层2）

职责：仅做"识别与题号范围判定"，返回结构化结果，**不操作数据库**。
由 question_import._detect_and_link_composite_groups 调用落库。

层1 规则集（确定性识别，无模型，O(n)）：
  1. 题号范围（range） ：根据以下材料/情境/文章/图表…回答X-Y题（明确题号范围）
  2. 材料标识（material）：材料一/资料1/材料：…（后续连续题号归属）
  3. 情境标识（scenario）：根据以下情境…（后续连续题号归属）
  4. 文章标识（passage）：阅读以下文章/阅读下面/给定资料…（后续连续题号归属）

层2 语义增强兜底（无模型，O(n log n)，不存向量）：
  A. 上下文继承检测：小题题干含"该材料/据此/根据上文"等引用词 → 向上追溯材料头
  B. 序列模式挖掘：材料头后连续题号 + 客观题一致性
  D. 文本相似度：字符 n-gram 重叠辅助判定（不落向量）
  E. 共享内容推测：无选项长题干（≥60字）或含材料关键词 → 候选材料头

设计原则：
  - 复用 text_parser.extract_question_numbers 统一题号提取，禁止另写解析
  - 不存向量、不落盘，仅返回结构化分组建议（整数索引）
  - 判定失败不抛异常，返回 None 由调用方跳过
  - 保守优先：层2 宁可漏识别（入人工审核），不误合并（题组仅为展示聚合视图）
"""
import re
import logging
from typing import List, Optional, Tuple, Dict

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


# ============ 层2 语义增强兜底（方案 v1.0 §4.1，无模型） ============

# A. 上下文继承指示词：小题题干命中即认为依赖前文（材料/情境/图表）
_CONTEXT_INDICATORS = [
    '该材料', '该情境', '该资料', '该图表', '该案例', '上述材料', '上述情境',
    '上述资料', '据此', '根据上文', '根据以上', '结合材料', '结合上述',
    '根据材料', '材料中', '情境中', '图中', '表中所列', '根据上述',
]

# E. 共享内容推测关键词：题干含这些词且无选项 → 强材料头信号
_MATERIAL_KEYWORDS = ['材料', '情境', '资料', '文章', '图表', '案例', '背景', '阅读以下', '给定资料']

# 客观题型集合（小题须为客观题才参与序列挖掘）
_OBJECTIVE_TYPES = {'单选题', '多选题', '选择题', '判断题', '不定项', '单选', '多选', '判断'}


def _char_ngrams(text: str, n: int = 2) -> set:
    """字符级 n-gram 集合（轻量相似度，无外部依赖，不落向量）"""
    t = re.sub(r'\s+', '', text or '')
    if len(t) < n:
        return {t} if t else set()
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def _overlap_ratio(a: str, b: str) -> float:
    """两个文本的字符 n-gram 重叠度（Jaccard，0~1）"""
    sa, sb = _char_ngrams(a), _char_ngrams(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def semantic_grouping(questions: List[dict]) -> List[dict]:
    """层2 语义增强兜底：对层1 未命中的题目做分组建议。

    输入 questions：每项含 question_content / options / question_type_detail / answer 等。
    返回分组建议列表，每项：
      {head_index, member_indices, group_type, confidence, reason}

    算法（保守优先，O(n log n)）：
      1. 预处理：每题提取题号/选项数/题型/是否客观题/是否含上下文指示词
      2. E 共享内容推测：无选项长题干（≥60字）或含材料关键词 → 候选材料头
      3. B 序列挖掘：材料头后连续题号（gap=1）且为客观题 → 候选小题
      4. A 上下文继承：含指示词的小题，向上追溯最近材料头
      5. D 相似度：材料头与候选小题关键词重叠度辅助加置信
      6. 置信度 < 阈值仍返回但标 reason（调用方决定是否入人工审核）
    """
    if not questions or len(questions) < 2:
        return []

    # 1. 预处理
    qinfo = []  # {idx, qnum, opt_count, is_objective, has_context, content}
    for i, q in enumerate(questions):
        content = q.get('question_content') or ''
        qn = None
        try:
            from .text_parser import extract_question_numbers
            nums = extract_question_numbers(content or '')
            qn = nums[0].number if nums else None
        except Exception:
            qn = None
        opts = q.get('options') or []
        opt_count = len(opts) if isinstance(opts, (list, tuple)) else 0
        qtype = str(q.get('question_type_detail') or q.get('question_type') or '')
        is_objective = any(t in qtype for t in _OBJECTIVE_TYPES) or opt_count >= 2
        has_context = any(kw in content for kw in _CONTEXT_INDICATORS)
        qinfo.append({
            'idx': i, 'qnum': qn, 'opt_count': opt_count,
            'is_objective': is_objective, 'has_context': has_context,
            'content': content,
        })

    # 2. 候选材料头：无选项长题干 或 含材料关键词且非客观题
    heads = []
    for qi in qinfo:
        content = qi['content']
        long_no_opt = (len(content) >= 60 and qi['opt_count'] == 0)
        material_kw = any(kw in content for kw in _MATERIAL_KEYWORDS) and not qi['is_objective']
        if long_no_opt or material_kw:
            heads.append(qi)

    suggestions = []
    used = set()
    for head in heads:
        if head['idx'] in used:
            continue
        member_indices = []

        # 3. B 序列挖掘：材料头后连续题号 + 客观题
        #   - 材料头有题号：从 head_qnum+1 连续递增收集
        #   - 材料头无题号（纯材料段落）：从其后第一个有题号的客观题锚点开始连续收集
        if head['qnum'] is not None:
            expect = head['qnum'] + 1
            for qi in qinfo:
                if qi['idx'] == head['idx'] or qi['idx'] in used:
                    continue
                if qi['qnum'] == expect and qi['is_objective']:
                    member_indices.append(qi['idx'])
                    expect += 1
                    if len(member_indices) >= _MAX_MEMBERS:
                        break
                elif qi['qnum'] is not None and qi['qnum'] > expect:
                    break  # 断档
        else:
            # 无题号材料头：从其后第一个客观题锚点开始，收集连续递增题号序列
            expect = None
            for qi in qinfo:
                if qi['idx'] <= head['idx'] or qi['idx'] in used:
                    continue
                if not qi['is_objective'] or qi['qnum'] is None:
                    if expect is not None:
                        break  # 遇到非连续客观题 → 断档
                    continue
                if expect is None:
                    expect = qi['qnum'] + 1
                    member_indices.append(qi['idx'])
                elif qi['qnum'] == expect:
                    member_indices.append(qi['idx'])
                    expect += 1
                    if len(member_indices) >= _MAX_MEMBERS:
                        break
                elif qi['qnum'] > expect:
                    break  # 断档

        # 4. A 上下文继承：含指示词的小题向上追溯（若序列挖掘未覆盖）
        for qi in qinfo:
            if qi['idx'] == head['idx'] or qi['idx'] in used:
                continue
            if qi['idx'] in member_indices:
                continue
            if qi['has_context'] and qi['is_objective']:
                # 该小题依赖前文 → 归属最近的这个材料头
                member_indices.append(qi['idx'])

        member_indices = sorted(set(member_indices))
        if not member_indices:
            continue

        # 5. D 相似度：材料头与小题关键词重叠度辅助置信
        sim = _overlap_ratio(head['content'], ' '.join(
            qinfo[m]['content'] for m in member_indices if m < len(qinfo)
        ))
        confidence = 0.6 + min(sim, 0.3)  # 0.6~0.9

        group_type = 'material'
        for kw, gt in [('情境', 'scenario'), ('图表', 'data_analysis'), ('文章', 'passage'), ('资料', 'material')]:
            if kw in head['content']:
                group_type = gt
                break

        for m in member_indices:
            used.add(m)
        used.add(head['idx'])

        suggestions.append({
            'head_index': head['idx'],
            'member_indices': member_indices,
            'group_type': group_type,
            'confidence': round(confidence, 2),
            'reason': 'semantic: 无标识材料头+连续题号/上下文继承',
        })

    return suggestions


# ============================================================================
# 行测材料块归组（任务 9 新增，纯增量）
# ============================================================================
#
# 与既有层1 规则集的关系
# ----------------------
# 既有 4 条规则（material / scenario / passage / range）的触发词是
# 「材料一」「根据以下情境」「阅读以下文章」「根据以下…回答X-Y题」，
# **完全不命中行测**。行测的材料头是**全角括号独占行** `（一）（二）…`
# （实测 85/85 覆盖、364 块，分布见下表），且其形态是**跨分节通用**的：
#
#   资料分析 299 / 言语理解与表达 39 / 判断推理 19 / 常识判断 7 = 364
#
# 为什么不新写材料正则：text_parser.route_xingce_sections（任务 7）已把
# 材料块定位到 100% 准确率并**自带所属分节**。此处直接复用，
# 符合本文件既定原则「复用 text_parser，禁止另写解析」。
#
# 隔离性
# ------
# 本函数只在 route_xingce_sections 返回非 None（即已通过 ≥2 分节锚点门槛）时
# 才有输出，故公专/申论链路**不可能**触发。既有 4 条规则与 _MATERIAL_KEYWORDS
# 一律未改动。

# 行测分区 → question_groups.group_type（沿用既有语义；group_type 列注释已含这4 值）
XINGCE_SECTION_GROUP_TYPE = {
    '资料分析': 'data_analysis',      # 统计图表 + 4~5 小题
    '言语理解与表达': 'passage',       # 多篇文章 + 阅读理解题
    '判断推理': 'scenario',           # 情景材料 + 逻辑题
    '常识判断': 'material',           # 材料 + 常识题
}


def match_xingce_material_groups(materials, qno_positions, sections=None):
    """把行测材料块与小题题号关联，返回题组建议。

    **纯识别，不碰数据库**（与本文件其余函数契约一致）；落库由调用方负责。

    Args:
        materials: :func:`text_parser.route_xingce_sections` 返回的 ``materials``，
            每项含 ``ordinal`` / ``start`` / ``end`` / ``section``。
        qno_positions: ``[(题号, 字符位置, 所属分节名), ...]``，需按位置升序。
            位置取自 :func:`text_parser.split_xingce_answer_blocks` 的 ``start``
            （锚点位置，权威）。
        sections: route_xingce_sections 的 ``sections``，用于把每个材料块的上界
            限制在**本分节末尾**，防止「常识判断」的材料吃掉后续分节的题。

    Returns:
        ``[{'ordinal', 'section', 'group_type', 'start', 'end',
           'member_qnums': [...], 'member_count': int,
           'confidence': float, 'reason': str}, ...]``

        无材料块时返回 ``[]``（不抛异常）。
    """
    if not materials:
        return []

    sec_end: dict = {}
    if sections:
        for i, s in enumerate(sections):
            sec_end[s['name']] = s['end'] if i + 1 < len(sections) else None

    INF = float('inf')
    out = []
    for i, m in enumerate(materials):
        section = m.get('section') or ''
        gtype = XINGCE_SECTION_GROUP_TYPE.get(section, 'material')
        upper = materials[i + 1]['start'] if i + 1 < len(materials) else INF
        # 上界同时受「下一个材料块」与「本分节末尾」约束
        se = sec_end.get(section)
        if se is not None:
            upper = min(upper, se)

        members = [
            qno for qno, pos, sec in qno_positions
            if sec == section and m['start'] < pos < upper
        ]
        if not members:
            continue

        out.append({
            'ordinal': m.get('ordinal'),
            'section': section,
            'group_type': gtype,
            'start': m['start'],
            'end': upper if upper != INF else -1,
            'member_qnums': sorted(members),
            'member_count': len(members),
            # 材料块由 ≥2 分节锚点门槛 + 100% 可解析的分节头定位，
            # 且成员是**位置区间内**的题（不是关键词猜测），故置信度给满
            'confidence': 1.0,
            'reason': 'xingce: （一）（二）材料锚点 + 分节边界限定位置区间',
        })

    return out
