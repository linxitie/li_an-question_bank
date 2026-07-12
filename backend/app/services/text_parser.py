"""
题目文本智能解析与匹配引擎

功能：
1. 文本标准化（用于相似度比较和去重）
2. 模糊去重检测（相似度 > 80% 视为重复）
3. 统一题号提取器（支持6+种格式）
4. 答案模式提取器（支持10+种模式）
5. 跨格式题号映射
6. 位置兜底匹配
7. 智能匹配主入口（用于分离导入）
"""
import re
import logging
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ============ 常量 ============

# 去重相似度阈值（>= 此值视为重复）
DEDUP_SIMILARITY_THRESHOLD = 0.80

# 题号提取正则模式（按优先级排列）
QUESTION_NUMBER_PATTERNS = [
    # 第N题 / 第 N 题 / 第N、题
    ('cn_di', re.compile(r'第\s*(\d+)\s*[题]')),
    # N. / N． / N、 / N．
    ('num_dot', re.compile(r'(?:^|\n)\s*(\d+)\s*[.、．]')),
    # (N) / （N）
    ('paren', re.compile(r'[（(]\s*(\d+)\s*[）)]')),
    # [N] / 【N】
    ('bracket', re.compile(r'[\[【]\s*(\d+)\s*[\]】]')),
    # N) / N）
    ('num_close_paren', re.compile(r'(?:^|\n)\s*(\d+)\s*[)）]')),
    # 纯数字后跟空格（最宽松，用于纯序列）
    ('bare_num', re.compile(r'(?:^|\n)\s*(\d+)\s+(?=[A-Da-d一-鿿])')),
]

# 答案提取正则模式（按优先级排列）
ANSWER_PATTERNS = [
    # 【答案】C / 《答案》C / <答案>C / 答案:C
    ('chinese_bracket', re.compile(r'[【《<\[]?\s*答\s*案\s*[】》>\]：:：]\s*([A-Da-d对错正确错误是否]+)')),
    # 答案：C / 参考答案：C
    ('chinese_colon', re.compile(r'(?:参考)?答案\s*[：:：]\s*([A-Da-d对错正确错误是否]+)')),
    # 正确选项：C / 正确答案: C
    ('correct_option', re.compile(r'(?:正确选项|正确答案|正确)\s*[：:：]\s*([A-Da-d]+)')),
    # Answer: C / Answer Key: C
    ('english', re.compile(r'Answer\s*(?:Key)?\s*[：:：]\s*([A-Da-d]+)', re.IGNORECASE)),
    # 选C / 选 C
    ('choose', re.compile(r'选\s*([A-Da-d])')),
    # 连续答案序列: 1-5: ABCCD
    ('range', re.compile(r'(\d+)\s*[-～~]\s*(\d+)\s*[：:：]\s*([A-Da-d对错正确错误是否]+)')),
    # 逐题答案: 1.C 2.B 3.A
    ('per_item', re.compile(r'(?:^|\n)\s*(\d+)\s*[.、．)）]\s*([A-Da-d对错正确错误是否])\s*(?=\d|$|\n)')),
]

# ============ 嵌入式答案模式（答案隐藏在详细解析末尾） ============
# 用于解析"故本题答案为D"、"故正确答案为C"等格式
# 优先级高于普通答案模式中的宽松匹配
EMBEDDED_ANSWER_PATTERNS = [
    # 故本题答案为D / 故本题答案选D
    ('gu_ben_ti', re.compile(r'故本题答案(?:为|选)\s*[：:：]?\s*([A-Da-d])')),
    # 故正确答案为C / 故正确答案是C
    ('gu_zheng_que', re.compile(r'故正确(?:的)?答案(?:为|是|选)\s*[：:：]?\s*([A-Da-d])')),
    # 故答案为B / 故答案选B
    ('gu_daan', re.compile(r'故答案(?:为|选)\s*[：:：]?\s*([A-Da-d])')),
    # 因此本题答案为A / 因此本题选A
    ('yin_ci_ben_ti', re.compile(r'因此本题答案(?:为|选)\s*[：:：]?\s*([A-Da-d])')),
    # 因此正确答案为D
    ('yin_ci_zheng_que', re.compile(r'因此正确(?:的)?答案(?:为|是|选)\s*[：:：]?\s*([A-Da-d])')),
    # 因此答案为C / 因此选C
    ('yin_ci_daan', re.compile(r'因此答案(?:为|选)\s*[：:：]?\s*([A-Da-d])')),
    # 本题答案为B / 本题选B
    ('ben_ti_daan', re.compile(r'本题答案(?:为|选)\s*[：:：]?\s*([A-Da-d])')),
    # 正确答案是A / 正确选项为C（无冒号版本）
    ('zheng_que_shi', re.compile(r'正确(?:答案|选项)(?:是|为|选)\s*[：:：]?\s*([A-Da-d])')),
    # 应选D / 应选择D
    ('ying_xuan', re.compile(r'应选(?:择)?\s*[：:：]?\s*([A-Da-d])')),
    # 答案为D。（句号结尾）
    ('daan_wei', re.compile(r'答案(?:为|是)\s*[：:：]?\s*([A-Da-d])\s*[。.]')),
]

# 中文答案映射
CN_ANSWER_MAP = {
    '对': 'A', '正确': 'A', '是': 'A', '√': 'A',
    '错': 'B', '错误': 'B', '否': 'B', '×': 'B',
}

# 科目检测关键词
SUBJECT_KEYWORDS = {
    '公专': ['公安', '警务', '治安', '刑事', '法律', '处罚', '逮捕', '侦查', '警察', '取证',
             '拘留', '犯罪', '刑罚', '诉讼', '证据', '宪法', '消防', '交通', '警械',
             '职业道德', '纪律', '廉洁', '勤务', '巡逻', '盘查', '战术'],
    '申论': ['概括', '归纳', '对策', '议论文', '应用文', '综合分析', '申论', '论证', '论述',
             '评析', '方案', '建议', '措施', '通知', '报告', '请示'],
    '行测': ['数量', '资料分析', '判断推理', '言语理解', '常识判断', '逻辑', '类比',
             '增长率', '百分比', '数学运算', '排列组合', '概率', '数列'],
}


# ============ 文本标准化（去重用） ============

def normalize_text_for_comparison(text: str) -> str:
    """
    标准化文本用于相似度比较。
    - 去除所有空白字符（空格、换行、制表符等）
    - 全角字符转半角（字母、数字、标点）
    - 统一中文标点为半角
    - 转为小写
    """
    if not text:
        return ''

    # 去除所有空白
    text = re.sub(r'\s+', '', text)

    # 全角转半角 + 中文标点统一
    result = []
    for c in text:
        code = ord(c)
        # 全角字母/数字/符号 → 半角
        if 0xFF01 <= code <= 0xFF5E:
            result.append(chr(code - 0xFEE0))
        # 全角空格
        elif code == 0x3000:
            result.append(' ')
        # 中文标点统一化
        elif c in '、．':  # 、 ． → .
            result.append('.')
        elif c in '：':  # ： → :
            result.append(':')
        elif c in '（':  # （ → (
            result.append('(')
        elif c in '）':  # ） → )
            result.append(')')
        elif c in '【':  # 【 → [
            result.append('[')
        elif c in '】':  # 】 → ]
            result.append(']')
        elif c in '“”':  # "" → "
            result.append('"')
        else:
            result.append(c)

    return ''.join(result).lower()


def compute_text_similarity(text_a: str, text_b: str) -> float:
    """
    计算两段文本的相似度（使用 difflib.SequenceMatcher）。
    返回 0.0 ~ 1.0 之间的值。
    """
    if not text_a and not text_b:
        return 1.0
    if not text_a or not text_b:
        return 0.0

    # 对长文本截取前2000字符比较（性能优化）
    a = normalize_text_for_comparison(text_a[:2000])
    b = normalize_text_for_comparison(text_b[:2000])

    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


# ============ 模糊去重 ============

def fuzzy_detect_duplicate(
    db_session,
    content: str,
    answer: str = '',
    subject_id: Optional[int] = None,
    threshold: float = DEDUP_SIMILARITY_THRESHOLD
) -> Tuple[bool, Optional[Any], float]:
    """
    模糊去重检测。

    策略：
    1. 先在数据库中精确匹配（快速路径）
    2. 精确未命中时，按科目过滤候选集
    3. 逐条计算标准化相似度，找到最佳匹配
    4. 相似度 >= threshold 视为重复

    参数：
    - db_session: SQLAlchemy Session
    - content: 题目内容（题干）
    - answer: 答案（可选，用于精确匹配优先）
    - subject_id: 科目ID（可选，用于缩小候选范围）
    - threshold: 相似度阈值，默认 0.80

    返回：
    - (is_duplicate, matched_question, best_similarity)
    """
    from ..models.models import QuestionBank

    if not content:
        return False, None, 0.0

    normalized_input = normalize_text_for_comparison(content)

    # 第1步：精确答案匹配（题干+答案完全相同）— 快速路径
    exact = None
    if answer:
        exact = db_session.query(QuestionBank).filter(
            QuestionBank.question_content == content,
            QuestionBank.answer == answer,
            QuestionBank.status != 0
        ).first()
    if not exact:
        exact = db_session.query(QuestionBank).filter(
            QuestionBank.question_content == content,
            QuestionBank.status != 0
        ).first()
    if exact:
        return True, exact, 1.0

    # 第2步：构建候选集
    query = db_session.query(QuestionBank).filter(QuestionBank.status != 0)
    if subject_id is not None:
        query = query.filter(QuestionBank.subject_id == subject_id)

    # 大库优化：限制候选数量（取最近的500条 + 同科目的500条）
    candidates = query.order_by(QuestionBank.question_id.desc()).limit(1000).all()

    if not candidates:
        return False, None, 0.0

    # 第3步：逐条比对
    best_match = None
    best_score = 0.0

    for q in candidates:
        q_content = q.question_content or ''
        q_normalized = normalize_text_for_comparison(q_content)
        if not q_normalized:
            continue

        # 快速过滤：长度差异过大直接跳过
        if len(normalized_input) > 0 and len(q_normalized) > 0:
            len_ratio = min(len(normalized_input), len(q_normalized)) / \
                        max(len(normalized_input), len(q_normalized))
            if len_ratio < 0.4:  # 长度差超过60%，不太可能是同一题
                continue

        score = SequenceMatcher(None, normalized_input, q_normalized).ratio()
        if score > best_score:
            best_score = score
            best_match = q
            # 提前退出：如果已经 ≥ threshold 且答案也匹配，直接返回
            if score >= threshold and answer and q.answer == answer:
                break

    is_dup = best_score >= threshold
    return is_dup, best_match, best_score


# ============ 题号提取 ============

@dataclass
class QuestionNumber:
    """题号信息"""
    number: int          # 题号数值
    format_type: str     # 格式类型（cn_di, num_dot, paren, bracket, num_close_paren, bare_num）
    position: int        # 在文本中的起始位置
    line_index: int      # 行号（0-based）


def extract_question_numbers(text: str) -> List[QuestionNumber]:
    """
    从文本中提取所有题号。
    每个位置只取第一个命中的格式（按优先级）。
    包含近邻去重逻辑。
    """
    if not text:
        return []

    lines = text.split('\n')
    results: List[QuestionNumber] = []
    recent_numbers: List[Tuple[int, int]] = []  # (number, line_index)

    for line_idx, line in enumerate(lines):
        best_match = None
        best_priority = len(QUESTION_NUMBER_PATTERNS)

        for priority, (fmt_name, pattern) in enumerate(QUESTION_NUMBER_PATTERNS):
            m = pattern.search(line)
            if m:
                num = int(m.group(1))
                # 过滤异常值
                if num <= 0 or num > 5000:
                    continue
                if best_match is None or priority < best_priority:
                    best_match = (num, fmt_name, m.start())
                    best_priority = priority

        if best_match is None:
            continue

        num, fmt_name, pos = best_match

        # 近邻去重：同一题号在附近行重复出现则跳过
        is_dup = False
        for rn, rl in recent_numbers[-5:]:
            if rn == num and (line_idx - rl) <= 2:
                is_dup = True
                break
        if is_dup:
            continue

        results.append(QuestionNumber(
            number=num,
            format_type=fmt_name,
            position=pos,
            line_index=line_idx
        ))
        recent_numbers.append((num, line_idx))

    return results


# ============ 答案提取 ============

def extract_answer_from_lines(lines: List[str]) -> Dict[str, Optional[str]]:
    """
    从文本行中提取答案和解析。
    支持标准答案格式和嵌入式答案格式（如"故本题答案为D"）。
    返回 {'answer': 'A', 'analysis': '...'} 或空字典。
    """
    full_text = '\n'.join(lines)

    # ===== 第一遍：标准答案格式 =====
    for fmt_name, pattern in ANSWER_PATTERNS:
        if fmt_name == 'range' or fmt_name == 'per_item':
            continue  # 这两个由专门的解析函数处理
        m = pattern.search(full_text)
        if m:
            raw_answer = m.group(1).strip().upper() if m.lastindex and m.lastindex >= 1 else m.group(1).strip().upper()

            # 中文答案映射
            if raw_answer in CN_ANSWER_MAP:
                raw_answer = CN_ANSWER_MAP[raw_answer]

            # 提取解析（答案标记之后的文本）
            analysis_parts = []
            answer_end = m.end()
            remaining = full_text[answer_end:].strip()
            if remaining and len(remaining) > 5:
                # 截取到下一个答案标记或题号之前
                next_break = re.search(r'(?:[【《<\[【]?\s*答\s*案|^\s*\d+\s*[.、．])',
                                       remaining, re.MULTILINE)
                if next_break:
                    remaining = remaining[:next_break.start()]
                analysis_parts.append(remaining.strip())

            return {
                'answer': raw_answer,
                'analysis': '\n'.join(analysis_parts) if analysis_parts else None,
                'format': fmt_name,
            }

    # ===== 第二遍：嵌入式答案格式（"故本题答案为D"等） =====
    for fmt_name, pattern in EMBEDDED_ANSWER_PATTERNS:
        # 从末尾开始搜索（嵌入式答案通常在文本块末尾附近）
        matches = list(pattern.finditer(full_text))
        if matches:
            # 取最后一个匹配（最接近末尾的答案）
            m = matches[-1]
            raw_answer = m.group(1).strip().upper()
            if raw_answer in CN_ANSWER_MAP:
                raw_answer = CN_ANSWER_MAP[raw_answer]
            if raw_answer in 'ABCD':
                # 整个文本块作为解析
                return {
                    'answer': raw_answer,
                    'analysis': full_text,
                    'format': f'embedded_{fmt_name}',
                }

    # 兜底：最后一行如果是孤立的大写字母，视为答案
    for line in reversed(lines):
        stripped = line.strip()
        if re.match(r'^[A-Da-d]$', stripped):
            return {'answer': stripped.upper(), 'analysis': None, 'format': 'standalone_letter'}

    return {}


def parse_answer_sequence(text: str) -> Dict[int, Dict[str, Optional[str]]]:
    """
    解析连续答案序列（无题号的纯答案列表）。
    支持3种模式：
    1. 范围模式: 1-5: ABCCD
    2. 逐题模式: 1.C 2.B 3.A
    3. 纯序列模式: A B C D A B C D（按位置从1开始编号）

    返回 {题号: {'answer': 'A', 'analysis': None}}
    """
    result: Dict[int, Dict[str, Optional[str]]] = {}

    # 模式1: 范围模式 1-5: ABCCD
    range_pattern = re.compile(r'(\d+)\s*[-～~]\s*(\d+)\s*[：:：]\s*([A-Da-d对错正确错误是否]+)')
    for m in range_pattern.finditer(text):
        start = int(m.group(1))
        end = int(m.group(2))
        answers = m.group(3)
        for i, ch in enumerate(answers):
            num = start + i
            if num > end:
                break
            ans = ch.upper()
            if ans in CN_ANSWER_MAP:
                ans = CN_ANSWER_MAP[ans]
            if ans in 'ABCD':
                result[num] = {'answer': ans, 'analysis': None}

    if result:
        return result

    # 模式2: 逐题模式 1.C 2.B 3.A
    per_item_pattern = re.compile(
        r'(?:^|\n)\s*(\d+)\s*[.、．)）]\s*([A-Da-d对错正确错误是否])\s*(?=\d|$|\n)'
    )
    for m in per_item_pattern.finditer(text):
        num = int(m.group(1))
        ans = m.group(2).upper()
        if ans in CN_ANSWER_MAP:
            ans = CN_ANSWER_MAP[ans]
        if ans in 'ABCD':
            result[num] = {'answer': ans, 'analysis': None}

    if result:
        return result

    # 模式3: 纯序列 A B C D A B C D（连续字母）
    pure_pattern = re.compile(r'^[\s\n]*([A-Da-d对错正确错误是否]+)[\s\n]*$')
    m = pure_pattern.match(text.strip())
    if m:
        answers = m.group(1)
        for i, ch in enumerate(answers):
            num = i + 1
            ans = ch.upper()
            if ans in CN_ANSWER_MAP:
                ans = CN_ANSWER_MAP[ans]
            if ans in 'ABCD':
                result[num] = {'answer': ans, 'analysis': None}

    return result


def parse_answer_text_to_map(text: str) -> Dict[int, Dict[str, Optional[str]]]:
    """
    将答案文本解析为题号→答案的映射（主要策略）。

    流程：
    1. 提取题号位置
    2. 按题号切分文本块
    3. 从每个文本块中提取答案和解析
    """
    numbers = extract_question_numbers(text)

    if not numbers:
        # 无题号时尝试连续序列解析
        return parse_answer_sequence(text)

    lines = text.split('\n')
    result: Dict[int, Dict[str, Optional[str]]] = {}
    seen = set()

    for i, qn in enumerate(numbers):
        # 确定该题号的文本范围
        start_line = qn.line_index
        if i + 1 < len(numbers):
            end_line = numbers[i + 1].line_index
        else:
            end_line = len(lines)

        # 提取该题号的文本块（去掉题号行首的题号前缀）
        block_lines = lines[start_line:end_line]
        if block_lines:
            # 去掉第一行的题号前缀
            first_line = block_lines[0]
            cleaned = re.sub(r'^(第\s*\d+\s*题|\d+\s*[.、．)）\]】])', '', first_line).strip()
            if cleaned:
                block_lines[0] = cleaned
            else:
                block_lines = block_lines[1:]  # 首行只有题号，去掉整行

        extracted = extract_answer_from_lines(block_lines)
        if extracted and extracted.get('answer'):
            result[qn.number] = {
                'answer': extracted['answer'],
                'analysis': extracted.get('analysis'),
            }
            seen.add(qn.number)

    # 如果按题号分段没提取到答案，尝试宽松正则匹配整个文本
    if not result:
        loose_pattern = re.compile(
            r'(?:^|\n)\s*(\d+)\s*[.、．)）\]】]\s*([A-Da-d对错正确错误是否]+)',
            re.MULTILINE
        )
        for m in loose_pattern.finditer(text):
            num = int(m.group(1))
            ans = m.group(2).strip().upper()
            if ans in CN_ANSWER_MAP:
                ans = CN_ANSWER_MAP[ans]
            if ans in 'ABCD' and num not in seen:
                result[num] = {'answer': ans, 'analysis': None}
                seen.add(num)

    return result


# ============ 题目结构提取 ============

def extract_question_blocks(text: str) -> List[Dict[str, Any]]:
    """
    将文本分割为题目块，每个块包含：
    - question_number: 题号
    - content: 题干文本
    - options: 选项列表
    - answer: 答案（从内联标记提取）
    - analysis: 解析
    - question_type: 题型
    """
    numbers = extract_question_numbers(text)
    if not numbers:
        return []

    lines = text.split('\n')
    blocks = []

    for i, qn in enumerate(numbers):
        start_line = qn.line_index
        if i + 1 < len(numbers):
            end_line = numbers[i + 1].line_index
        else:
            end_line = len(lines)

        block_lines = lines[start_line:end_line]
        block_text = '\n'.join(block_lines)

        # 去掉首行题号前缀
        content_text = block_text
        m = re.match(r'^(?:第\s*\d+\s*题|\d+\s*[.、．)）\]】])\s*', block_text)
        if m:
            content_text = block_text[m.end():]

        # 提取选项
        options = _extract_options(block_lines)

        # 不足4个时从content_text中回退提取
        if len(options) < 4:
            existing_keys = {o['key'] for o in options if isinstance(o, dict)}
            # 匹配A-D开头的行或嵌入式选项
            fallback_re = re.compile(
                r'(?:^|\n)\s*([A-D])\s*[.、．)）]\s*(.+?)(?=\n\s*[A-D]\s*[.、．)）]|\n\n|\n(?:[A-D]\s*[.、．)）])|$)',
                re.DOTALL
            )
            for fm in fallback_re.finditer(content_text):
                k, v = fm.group(1), fm.group(2).strip()
                if k in {'A', 'B', 'C', 'D'} and k not in existing_keys and len(v) > 1:
                    # 清理值中可能混入的下一选项标记
                    v = re.sub(r'\s*[A-D]\s*[.、．)）]\s*.+$', '', v, flags=re.DOTALL).strip()
                    if v:
                        options.append({'key': k, 'value': v})
                        existing_keys.add(k)
                        if len(options) >= 4:
                            break

        # 从content_text中精确移除选项行（使用位置索引避免误删）
        if options and block_lines:
            for line in block_lines:
                stripped = line.strip()
                if re.match(r'^[A-D]\s*[.、．)）]', stripped):
                    idx = content_text.find(line)
                    if idx >= 0:
                        content_text = content_text[:idx] + content_text[idx + len(line):]
        # 移除(单选)/(多选)/[单选]/[多选]等标记
        content_text = re.sub(r'[\[（(]\s*(?:单选|多选|不定项)\s*[\]）)]', '', content_text)
        content_text = re.sub(r'\n{3,}', '\n\n', content_text).strip()

        # 提取内联答案
        extracted = extract_answer_from_lines(block_lines)
        answer = extracted.get('answer') if extracted else None
        analysis = extracted.get('analysis') if extracted else None

        # 检测题型
        qtype = _detect_question_type(content_text, options)

        blocks.append({
            'question_number': qn.number,
            'content': content_text.strip(),
            'options': options,
            'answer': answer,
            'analysis': analysis,
            'question_type': qtype,
            'format': qn.format_type,
        })

    return blocks


def _extract_options(lines: List[str]) -> List[Dict[str, str]]:
    """从文本行中提取选项，返回 [{key:'A',value:'...'}, ...]"""
    options = []
    # 模式1+2合并: 逐行扫描，支持同行多选项和逐行单选项
    for line in lines:
        if len(options) >= 4:
            break  # 保护：最多提取4个选项(A-D)，防止重复提取
        stripped = line.strip()
        if not stripped:
            continue
        # 检测同行是否有多个选项标记 (A.xxx B.xxx)
        markers = re.findall(r'([A-D])\s*[.、．、．)]\s*', stripped)
        if len(markers) >= 2:
            # 按选项标记分割
            parts = re.split(r'(?=[A-D]\s*[.、．、．)])', stripped)
            for part in parts:
                part = part.strip()
                if part:
                    m = re.match(r'([A-D])\s*[.、．、．)]\s*(.+)', part)
                    if m:
                        key = m.group(1)
                        val = re.sub(r'[;；\s]+$', '', m.group(2).strip())
                        if val:
                            options.append({'key': key, 'value': val})
        else:
            # 单行单选项
            m = re.match(r'^\s*([A-D])\s*[.、．、．)]\s*(.+)', stripped)
            if m:
                key = m.group(1)
                val = re.sub(r'[;；\s]+$', '', m.group(2).strip())
                if val:
                    options.append({'key': key, 'value': val})

    # L2 段落回退：L1结果不足2个时，扫描连续段落查找选项
    if len(options) < 2:
        full_text = '\n'.join(lines)
        # 宽松匹配：每行一个选项 A-D
        loose_matches = re.findall(
            r'(?:^|\n)\s*([A-D])\s*[.、．)）]\s*(.+?)(?=\n\s*[A-D]\s*[.、．)）]|\n\n|\Z)',
            full_text, re.DOTALL
        )
        existing_keys = {o.get('key') for o in options}
        for key, val in loose_matches:
            if key not in existing_keys and len(val.strip()) > 0:
                # 清理：截断到下一个选项标记之前
                val = re.sub(r'\s*[A-D]\s*[.、．)）]\s*.+$', '', val, flags=re.DOTALL).strip()
                if val:
                    options.append({'key': key, 'value': val})
                    existing_keys.add(key)
                    if len(options) >= 4:
                        break

    # L3 记录：L1+L2后仍不足2个
    if len(options) < 2:
        logger.warning(f"[options] 仅提取 {len(options)} 个选项，无法自动修复，保留原始结果")
    return options


def _detect_question_type(content: str, options: List[str]) -> str:
    """根据内容和选项自动检测题型（区分单选/多选）"""
    opt_count = len(options)
    content_lower = content.lower() if content else ''

    # 多选题关键词检测
    multi_keywords = ['多选', '不定项', '至少.*个', '两项', '2个以上', '多选题',
                      '哪些', '几种', '包括.*有', '属于.*的有', '正确的有', '错误的有']
    is_multi = any(re.search(kw, content_lower) for kw in multi_keywords) if content else False

    if opt_count >= 3:
        return '多选题' if is_multi else '单选题'
    if opt_count == 2:
        if any(kw in content for kw in ['正确', '错误', '对', '错']):
            return '判断题'
        return '单选题'
    if opt_count == 1 and any(kw in content for kw in ['填空', '______', '___']):
        return '填空题'
    if any(kw in content for kw in ['判断', '对错', '正确', '错误']) and len(content) < 200:
        return '判断题'
    if any(kw in content for kw in ['简答', '简述', '简述题']):
        return '简答题'
    if any(kw in content for kw in ['论述', '论证', '论']):
        return '论述题'

    return '单选题'  # 默认


# ============ 智能匹配主入口（分离导入） ============

@dataclass
class MatchResult:
    """匹配结果"""
    match_rate: float                    # 匹配率 0.0~1.0
    matched_count: int                   # 匹配成功数
    total_questions: int                 # 题目总数
    questions: List[Dict[str, Any]]      # 匹配后的题目列表
    unmatched_question_numbers: List[int]  # 未匹配的题号
    extra_answer_numbers: List[int]      # 多余的答案题号
    analysis_count: int                  # 含解析的题目数
    strategy_used: str                   # 使用的策略描述
    details: Dict[str, Any] = field(default_factory=dict)


def llm_match_questions_answers(
    questions_text: str,
    answers_text: str,
    question_blocks: List[Dict[str, Any]],
    paper_name: str = ''
) -> Dict[int, Dict[str, Optional[str]]]:
    """
    LLM智能匹配兜底方案。
    当传统规则匹配率 < 99% 时调用，使用大模型理解复杂答案格式。

    参数：
    - questions_text: 题目文档原文
    - answers_text: 答案文档原文
    - question_blocks: 已提取的题目块列表
    - paper_name: 试卷名称

    返回：{题号: {'answer': 'A', 'analysis': '...'}}
    """
    import json as _json

    # 构建LLM请求
    question_summaries = []
    for b in question_blocks[:100]:  # 最多处理100题
        qn = b.get('question_number', 0)
        content = b.get('content', '')[:200]
        options = b.get('options', [])
        opt_str = ' '.join(
            f"{o.get('key', '')}. {o if isinstance(o, str) else o.get('value', '')}"[:50]
            for o in (options if isinstance(options, list) else [])
        ) if options else ''
        question_summaries.append(f"第{qn}题: {content} {opt_str}")

    prompt = f"""你是一个公安联考题库的智能答案匹配助手。以下是题目文档和答案文档的内容。

**题目文档关键信息（前100题）：**
{chr(10).join(question_summaries[:50])}

**答案文档（前3000字符）：**
{answers_text[:3000]}

请分析答案文档中每道题的正确答案，输出JSON格式。如果答案文档中有"故本题答案为X"、"故正确答案为X"、"答案为X"等表述，提取对应的选项字母。
对于判断题，"对/正确/是"对应A，"错/错误/否"对应B。

请严格按以下JSON格式输出（只输出JSON，不要其他文字）：
{{"matches": [{{"number": 1, "answer": "D"}}, {{"number": 2, "answer": "C"}}], "notes": "匹配说明"}}

如果无法确定某题的答案，不要包含该题。"""

    try:
        import requests
        from ..core.config import settings

        llm_url = getattr(settings, 'LLM_API_URL', None) or 'http://localhost:8080/api/v1/chat'
        llm_key = getattr(settings, 'LLM_API_KEY', None) or ''

        response = requests.post(
            llm_url,
            headers={
                "Authorization": f"Bearer {llm_key}",
                "Content-Type": "application/json"
            },
            json={
                "messages": [
                    {"role": "system", "content": "你是公安联考题库答案匹配助手，只输出JSON格式的匹配结果。"},
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            content = result.get('content', '') or result.get('reply', '') or result.get('message', {}).get('content', '')
            # 尝试从回复中提取JSON
            json_match = re.search(r'\{[\s\S]*"matches"[\s\S]*\}', str(content))
            if json_match:
                data = _json.loads(json_match.group(0))
                matches = data.get('matches', [])
                result_map = {}
                for m in matches:
                    num = m.get('number')
                    ans = str(m.get('answer', '')).upper().strip()
                    if num and ans and ans in 'ABCD':
                        result_map[num] = {'answer': ans, 'analysis': f'[LLM智能匹配] {answers_text[:500]}'}
                logger.info(f"LLM匹配成功: {len(result_map)} 题")
                return result_map
            else:
                logger.warning(f"LLM响应中未找到JSON: {str(content)[:200]}")
        else:
            logger.warning(f"LLM API返回非200: {response.status_code}")
    except ImportError:
        logger.warning("requests库未安装，LLM匹配不可用")
    except Exception as e:
        logger.warning(f"LLM匹配失败: {e}")

    return {}


def smart_match_questions_answers(
    questions_text: str,
    answers_text: str,
    paper_name: str = ''
) -> MatchResult:
    """
    智能匹配题目和答案（分离导入主入口）。

    策略链（按优先级降级）：
    1. 题号分段解析匹配（主要策略，增强版）
    2. 嵌入式答案提取（"故本题答案为D"等）
    3. 连续答案序列匹配
    4. 内联答案提取
    5. 宽松正则全局匹配
    6. 位置兜底匹配
    7. LLM智能匹配兜底（仅前6级<99%时触发）
    """
    strategies = []

    # ===== 策略1: 题号分段解析（增强版） =====
    question_blocks = extract_question_blocks(questions_text)
    answer_map = parse_answer_text_to_map(answers_text)

    if answer_map:
        strategies.append('题号分段解析')

    # ===== 策略2: 嵌入式答案提取（针对"故本题答案为D"等格式） =====
    embedded_map = _extract_embedded_answers(answers_text)
    if embedded_map:
        strategies.append(f'嵌入式答案提取({len(embedded_map)}题)')
        for num, ans_data in embedded_map.items():
            if num not in answer_map:
                answer_map[num] = ans_data

    # ===== 策略3: 连续答案序列补充 =====
    seq_map = parse_answer_sequence(answers_text)
    if seq_map:
        strategies.append('连续答案序列')
        for num, ans_data in seq_map.items():
            if num not in answer_map:
                answer_map[num] = ans_data

    # ===== 策略4: 从题目文本提取内联答案 =====
    inline_from_q = _extract_inline_answers(questions_text)
    if inline_from_q:
        strategies.append('题目内联答案')
        for num, ans_data in inline_from_q.items():
            if num not in answer_map:
                answer_map[num] = ans_data

    # ===== 策略5: 检测两文本相似度，高相似度时从答案文件提取内联答案 =====
    sim = compute_text_similarity(questions_text, answers_text)
    if sim > 0.6:  # 降低阈值以覆盖更多场景
        inline_from_a = _extract_inline_answers(answers_text)
        if inline_from_a:
            strategies.append('答案文件内联答案')
            for num, ans_data in inline_from_a.items():
                if num not in answer_map:
                    answer_map[num] = ans_data

    # ===== 执行匹配 =====
    matched_count = 0
    analysis_count = 0
    no_answer_nums = []
    answer_keys_used = set()

    for block in question_blocks:
        q_num = block['question_number']
        ans_entry = answer_map.get(q_num)

        if ans_entry and ans_entry.get('answer'):
            ans = ans_entry['answer']
            if ans in CN_ANSWER_MAP:
                ans = CN_ANSWER_MAP[ans]
            if ans in 'ABCD':
                block['answer'] = ans
                matched_count += 1
                answer_keys_used.add(q_num)
            if ans_entry.get('analysis') and len(str(ans_entry['analysis'])) > 10:
                block['analysis'] = ans_entry['analysis']
                analysis_count += 1
        else:
            # 宽松重试：在答案文本中全局搜索该题号的答案
            retry_ans = _loose_answer_search(answers_text, q_num)
            if retry_ans:
                block['answer'] = retry_ans
                matched_count += 1
                answer_keys_used.add(q_num)
            else:
                no_answer_nums.append(q_num)

    # 多余答案
    extra_nums = [n for n in answer_map if n not in answer_keys_used and answer_map[n].get('answer')]

    # ===== 策略6: 位置兜底匹配 =====
    if matched_count == 0 and len(question_blocks) > 0:
        # 从答案文本中提取所有A-D字母
        all_answers = re.findall(r'\b([A-Da-d])\b', answers_text)
        all_answers = [a.upper() for a in all_answers]

        # 如果答案数量与题目数量接近（误差 < 25%）
        if abs(len(all_answers) - len(question_blocks)) <= max(2, len(question_blocks) * 0.25):
            strategies.append('位置兜底匹配')
            for i, block in enumerate(question_blocks):
                if not block.get('answer') and i < len(all_answers):
                    block['answer'] = all_answers[i]
                    matched_count += 1
                    if block['question_number'] in no_answer_nums:
                        no_answer_nums.remove(block['question_number'])

    # 构建初步结果
    total = len(question_blocks)
    match_rate = matched_count / total if total > 0 else 0.0

    # ===== 策略7: LLM智能匹配兜底（仅当前6级匹配率<99%时触发） =====
    llm_used = False
    if match_rate < 0.99 and matched_count < total and answers_text.strip():
        logger.info(f"规则匹配率{round(match_rate*100,1)}%<99%，触发LLM智能匹配...")
        try:
            llm_map = llm_match_questions_answers(
                questions_text, answers_text, question_blocks, paper_name
            )
            if llm_map:
                strategies.append('LLM智能匹配兜底')
                llm_used = True
                for block in question_blocks:
                    q_num = block['question_number']
                    if not block.get('answer') and q_num in llm_map:
                        ans_entry = llm_map[q_num]
                        if ans_entry.get('answer') and ans_entry['answer'] in 'ABCD':
                            block['answer'] = ans_entry['answer']
                            matched_count += 1
                            if q_num in no_answer_nums:
                                no_answer_nums.remove(q_num)
                            if ans_entry.get('analysis'):
                                block['analysis'] = ans_entry['analysis']
                                analysis_count += 1
                match_rate = matched_count / total if total > 0 else 0.0
        except Exception as e:
            logger.warning(f"LLM匹配兜底失败: {e}")

    return MatchResult(
        match_rate=match_rate,
        matched_count=matched_count,
        total_questions=total,
        questions=question_blocks,
        unmatched_question_numbers=no_answer_nums,
        extra_answer_numbers=list(extra_nums),
        analysis_count=analysis_count,
        strategy_used=' → '.join(strategies) if strategies else '无',
        details={
            'similarity': round(sim, 3),
            'answer_keys_total': len(answer_map),
            'answer_keys_used': len(answer_keys_used),
            'inline_from_question': len(inline_from_q) if inline_from_q else 0,
            'inline_from_answer': len(inline_from_a) if sim > 0.6 and inline_from_a else 0,
            'embedded_from_answer': len(embedded_map) if embedded_map else 0,
            'llm_fallback_used': llm_used,
        }
    )


def _extract_embedded_answers(text: str) -> Dict[int, Dict[str, Optional[str]]]:
    """
    从答案文本中提取嵌入式答案（"故本题答案为D"等格式）。
    按题号定位，在每个题号块中搜索嵌入式答案标记。

    关键修正：如果答案出现在块的最开头（前200字符内且紧邻题号行），
    则很可能是上一题的答案，应跳过并继续向后搜索。

    返回: {题号: {'answer': 'A', 'analysis': '...'}}
    """
    if not text:
        return {}

    numbers = extract_question_numbers(text)
    if not numbers:
        # 无题号时：全局搜索嵌入式答案标记，按顺序分配
        all_embedded = []
        for fmt_name, pattern in EMBEDDED_ANSWER_PATTERNS:
            for m in pattern.finditer(text):
                ans = m.group(1).strip().upper()
                if ans in CN_ANSWER_MAP:
                    ans = CN_ANSWER_MAP[ans]
                if ans in 'ABCD':
                    pos = m.start()
                    all_embedded.append({'answer': ans, 'position': pos})
        if all_embedded:
            # 按位置排序
            all_embedded.sort(key=lambda x: x['position'])
            result = {}
            for i, entry in enumerate(all_embedded):
                result[i + 1] = {'answer': entry['answer'], 'analysis': text[:500]}
            return result
        return {}

    lines = text.split('\n')
    result = {}

    for i, qn in enumerate(numbers):
        start_line = qn.line_index
        if i + 1 < len(numbers):
            end_line = numbers[i + 1].line_index
        else:
            end_line = len(lines)
        if end_line < start_line:
            end_line = start_line

        block_lines = lines[start_line:end_line]
        full_block = '\n'.join(block_lines)

        # 收集所有嵌入式答案匹配（含位置信息）
        all_matches = []
        for fmt_name, pattern in EMBEDDED_ANSWER_PATTERNS:
            for m in pattern.finditer(full_block):
                ans = m.group(1).strip().upper()
                if ans in CN_ANSWER_MAP:
                    ans = CN_ANSWER_MAP[ans]
                if ans in 'ABCD':
                    all_matches.append({
                        'answer': ans,
                        'position': m.start(),
                        'format': fmt_name,
                    })

        if not all_matches:
            continue

        # 筛选：如果答案出现在块开头200字符内且紧邻题号开头（可能是上一题答案残留）
        # 则跳过该匹配，优先使用块中间或末尾的答案
        valid_matches = []
        for m in all_matches:
            pos = m['position']
            # 去掉块首题号行后的实际内容起始位置
            first_line = block_lines[0] if block_lines else ''
            # 计算题号行长度
            header_end = 0
            for line in block_lines[:1]:
                header_match = re.match(r'^(?:第\s*\d+\s*题|\d+\s*[.、．)）\]】])\s*', line)
                if header_match:
                    header_end = header_match.end()
            # 如果答案在块开头前200字符且紧随题号行之后
            if pos <= max(200, header_end + 100):
                # 可能是上一题残留，降优先级但保留作为备选
                m['_suspect_previous'] = True
            valid_matches.append(m)

        if not valid_matches:
            continue

        # 优先使用非疑似残留的匹配
        clean_matches = [m for m in valid_matches if not m.get('_suspect_previous')]
        best = (clean_matches or valid_matches)[-1]  # 取最后一个（最接近末尾）

        result[qn.number] = {
            'answer': best['answer'],
            'analysis': full_block,
        }

    return result


def _loose_answer_search(text: str, question_num: int) -> Optional[str]:
    """
    在答案文本中宽松搜索指定题号的答案。
    支持多种格式，包括嵌入式答案。
    """
    if not text:
        return None

    # 尝试找该题号对应的行
    lines = text.split('\n')
    for i, line in enumerate(lines):
        stripped = line.strip()

        # 检查是否以该题号开头
        # 支持: "1．" "1." "1、" "1)" "(1)" "1）" "１．" "【1】"
        num_patterns = [
            rf'^{question_num}\s*[.、．]\s*',
            rf'^{question_num}\s*[)）]\s*',
            rf'^[（(]\s*{question_num}\s*[）)]\s*',
            rf'^[\[【]\s*{question_num}\s*[\]】]\s*',
            rf'^第\s*{question_num}\s*题',
            # 全角数字
            rf'^[{_to_fullwidth(str(question_num))}]\s*[.、．]\s*',
        ]
        is_match = False
        for pat in num_patterns:
            if re.search(pat, stripped):
                is_match = True
                break

        if not is_match:
            continue

        # 找到该题号，从这一行开始扫描后续N行
        scan_lines = lines[i:min(i + 30, len(lines))]
        scan_text = '\n'.join(scan_lines)

        # 先尝试嵌入式答案模式
        for fmt_name, pattern in EMBEDDED_ANSWER_PATTERNS:
            m = pattern.search(scan_text)
            if m:
                ans = m.group(1).strip().upper()
                if ans in CN_ANSWER_MAP:
                    ans = CN_ANSWER_MAP[ans]
                if ans in 'ABCD':
                    return ans

        # 再尝试标准答案模式
        ans_patterns = [
            re.compile(r'[【《<\[]?\s*答\s*案\s*[】》>\]：:：]\s*([A-Da-d])'),
            re.compile(r'(?:参考)?答案\s*[：:：]\s*([A-Da-d])'),
            re.compile(r'正确(?:答案|选项)[：:：]?\s*([A-Da-d])'),
        ]
        for pat in ans_patterns:
            m = pat.search(scan_text)
            if m:
                ans = m.group(1).strip().upper()
                if ans in 'ABCD':
                    return ans

        # 如果该行就是纯答案（如 "1. D"）
        direct = re.search(rf'^{question_num}\s*[.、．)）]\s*([A-Da-d])\s*$', stripped)
        if direct:
            return direct.group(1).upper()

    # 全局宽松搜索
    return _global_loose_answer_search(text, question_num)


def _global_loose_answer_search(text: str, question_num: int) -> Optional[str]:
    """最后的全局宽松搜索，不依赖题号定位"""
    # 搜索 "N. X" 模式（X为A-D）
    # 注意：只在较短的匹配中查找，避免匹配到选项内容
    pattern = re.compile(
        rf'(?:^|\n)\s*{question_num}\s*[.、．)）]\s*([A-Da-d])\s*(?:\s|$)',
        re.MULTILINE
    )
    m = pattern.search(text)
    if m:
        return m.group(1).upper()

    # 最后尝试：在文本中找第N个嵌入式答案模式
    all_embedded = []
    for fmt_name, pat in EMBEDDED_ANSWER_PATTERNS:
        for match in pat.finditer(text):
            all_embedded.append({
                'answer': match.group(1).upper(),
                'position': match.start()
            })
    if all_embedded and question_num <= len(all_embedded):
        # 按位置排序后取第question_num个
        all_embedded.sort(key=lambda x: x['position'])
        idx = question_num - 1
        if idx < len(all_embedded):
            ans = all_embedded[idx]['answer']
            if ans in 'ABCD':
                return ans

    return None


def _to_fullwidth(text: str) -> str:
    """将半角数字字符串转为全角数字字符串"""
    result = []
    for c in text:
        code = ord(c)
        if ord('0') <= code <= ord('9'):
            result.append(chr(code + 0xFEE0))
        else:
            result.append(c)
    return ''.join(result)


def _extract_inline_answers(text: str) -> Dict[int, Dict[str, Optional[str]]]:
    """从完整文本中按题号提取内联答案"""
    numbers = extract_question_numbers(text)
    if not numbers:
        return {}

    lines = text.split('\n')
    result = {}

    for i, qn in enumerate(numbers):
        start_line = qn.line_index
        if i + 1 < len(numbers):
            end_line = numbers[i + 1].line_index
        else:
            end_line = len(lines)

        block_lines = lines[start_line:end_line]
        extracted = extract_answer_from_lines(block_lines)
        if extracted and extracted.get('answer') and extracted['answer'] in 'ABCD':
            result[qn.number] = {
                'answer': extracted['answer'],
                'analysis': extracted.get('analysis'),
            }

    return result


# ============ 科目检测 ============

def detect_subject_category(text: str) -> str:
    """
    从文本内容自动检测科目大类。
    返回: '行测' / '申论' / '公专'
    """
    if not text:
        return '行测'

    scores = {'行测': 0, '申论': 0, '公专': 0}
    text_sample = text[:2000]

    for subject, keywords in SUBJECT_KEYWORDS.items():
        for kw in keywords:
            if kw in text_sample:
                scores[subject] += 1

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else '行测'
