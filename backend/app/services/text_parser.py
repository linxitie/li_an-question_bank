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
import os
import logging
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ============ UTB ID 清洗 ============

# UTB ID 正则：UTB + 8位以上十六进制 + 可选的 -选项X-N 后缀
UTB_PATTERN = re.compile(r'UTB[a-f0-9]{8,}(?:[-－]\s*选项[A-D]\s*\d*)?', re.IGNORECASE)
# 题号前缀正则：第X题：/第X题 /
QNUM_PREFIX_PATTERN = re.compile(r'^第\s*\d+\s*题[：:]\s*')
# 选项中的UTB ID变体：UTB7df857a7-选项A-5 / UTB7df857a7-选项B
UTB_OPTION_PATTERN = re.compile(r'UTB[a-f0-9]{8,}[-－]\s*选项[A-D][-－]?\d*', re.IGNORECASE)
# 独立选项标签清理（如 "A.\nUTB7df857a7-选项A-5" 保留A.但清理UTB部分）
UTB_LINE_PATTERN = re.compile(r'(?:^|\n)\s*[A-H]\s*[.、．）\]]\s*UTB[a-f0-9]{8,}[-－]?\s*选项?[A-H]?[-－]?\d*\s*', re.IGNORECASE)

def clean_question_text(text: str) -> str:
    """
    统一清洗题目文本：移除 UTB ID、题号前缀、多余空白
    适用场景：导入入库前、校验前、显示前（三重保险）
    """
    if not text:
        return text
    # 1. 移除 UTBxxxxxxxx 及其变体 (UTB7df857a7-选项A-5)
    text = UTB_PATTERN.sub('', text)
    # 2. 移除选项中的UTB ID变体
    text = UTB_OPTION_PATTERN.sub('', text)
    # 3. 移除"第X题："前缀
    text = QNUM_PREFIX_PATTERN.sub('', text)
    # 3.5 P3.1 剥离尾部粘连的分节头（解析切分残留）：
    #     形如 "...应：（ ） 六、根据以下情境材料，回答71-73题" ——
    #     下一节的材料头被粘连到上一题题干尾部。仅剥离"位于文本末尾"的
    #     分节头（锚定$），保护材料头题自身的开头材料句（B2 识别依赖）。
    text = re.sub(
        r'\s*[一二三四五六七八九十]{1,3}\s*、\s*根据以下[^。]*?回答\s*\d+\s*[-～~—－]\s*\d+\s*题?[。.]?\s*$',
        ' ', text)
    # 4. 合并连续空白行（保留单个换行）
    text = re.sub(r'\n\s*\n', '\n', text)
    # 5. 合并多余空白（保留换行结构）
    text = re.sub(r'[^\S\n]+', ' ', text)
    # 6. 清理每行首尾空白
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(line for line in lines if line)
    # 7. 最终合并为单行（去除换行）
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# ============ 常量 ============

# 去重相似度阈值（>= 此值视为重复）
#
# 历史: 此常量曾在本文件**两处重复定义**（此处 0.75 / "模糊去重"段 0.70），
#       后者静默覆盖前者，是易踩坑的重复定义。现统一为单一声明。
#
# 取值 0.70。阈值越低 -> 越激进地判定为重复。之所以敢取比早先 0.75 更激进的值，
#       是因为 fuzzy_detect_duplicate 额外要求答案标准化后相等（硬约束）：
#       内容相似度只负责"召回"候选，误判由答案硬约束挡掉，两者配合提高准确率。
#
# 注: 早先此处"降低阈值 = 更严格的去重"的注释是反的 —— 降低阈值放宽的是判定门，
#     真正提高准确率的是答案硬约束，而不是阈值本身。
DEDUP_SIMILARITY_THRESHOLD = 0.70

# ============ TextPreprocessor: 文本预处理器 ============

class TextPreprocessor:
    """
    文本预处理器：清理空白、去除干扰、统一题号格式
    """

    # 中文数字映射
    CN_NUM_MAP = {
        '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
        '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
        '十一': '11', '十二': '12', '十三': '13', '十四': '14', '十五': '15',
        '十六': '16', '十七': '17', '十八': '18', '十九': '19', '二十': '20',
    }

    def clean_text(self, text: str) -> str:
        """
        文本预处理流程：
        1. 统一编码：UTF-8
        2. 统一字符：全角→半角，中文标点→英文标点
        3. 清理空白：多余空格、换行、制表符
        4. 去除干扰：页眉、页脚、水印、页码
        5. 统一题号格式：所有题号统一为"数字."格式
        """
        if not text:
            return ""

        # 1. 清理空白：移除行内空白（空格、制表符），保留换行符
        text = re.sub(r'[^\S\n]+', '', text)

        # 2. 去除页码
        text = re.sub(r'第\s*\d+\s*页', '', text)
        text = re.sub(r'\d+\s*页', '', text)

        # 3. 去除页眉页脚（常见格式）
        text = re.sub(r'^(.*?)(?:页眉|页脚|水印).*?$', '', text, flags=re.MULTILINE)

        return text

    def normalize_question_numbers(self, text: str) -> str:
        """
        统一题号格式：
        - "一、" → "1."
        - "（1）" → "1."
        - "第1题" → "1."
        - "Q1:" → "1."
        """
        if not text:
            return ""

        # 替换中文数字题号
        for cn, num in self.CN_NUM_MAP.items():
            text = re.sub(re.escape(cn) + r'、', f'{num}.', text)

        # 替换其他格式
        text = re.sub(r'（(\d+)）', r'\1.', text)
        text = re.sub(r'第(\d+)题', r'\1.', text)
        text = re.sub(r'Q(\d+):', r'\1.', text)

        return text


# ============ QuestionNumberRecognizer: 题号识别器 ============

class QuestionNumberRecognizer:
    """
    带置信度的题号识别器，支持多种题号格式。
    """

    # 中文数字映射（长词优先，避免"十"误匹配"十一"）
    CN_NUM_MAP = {
        '二十': 20, '十九': 19, '十八': 18, '十七': 17, '十六': 16,
        '十五': 15, '十四': 14, '十三': 13, '十二': 12, '十一': 11,
        '十': 10, '九': 9, '八': 8, '七': 7, '六': 6,
        '五': 5, '四': 4, '三': 3, '二': 2, '一': 1,
    }

    # 数字题号正则（锚定行首，避免匹配正文中的数字）
    PATTERNS = [
        re.compile(r'^\s*(\d+)\.\s*'),           # 1.
        re.compile(r'^\s*(\d+)、\s*'),           # 1、
        re.compile(r'^\s*(\d+)．\s*'),           # 1．
        re.compile(r'^\s*(\d+)\s*[)）]\s*'),     # 1) / 1）
        re.compile(r'^\s*[\(（](\d+)[)）]\s*'),   # (1) / （1）
        re.compile(r'^\s*\[(\d+)\]\s*'),         # [1]
        re.compile(r'^\s*第(\d+)题\s*'),          # 第1题
        re.compile(r'^\s*Q(\d+)[:：]\s*'),        # Q1: / Q1：
        re.compile(r'^\s*问题(\d+)\s*'),          # 问题1
        re.compile(r'^\s*题(\d+)\s*'),            # 题1
    ]

    def recognize_with_confidence(self, text: str) -> list:
        """
        带置信度的题号识别。
        返回：[{number, position, format, confidence, context}]
        """
        if not text:
            return []

        results = []
        lines = text.split('\n')

        for line_num, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # 1. 尝试数字题号模式（优先）
            matched = False
            for pattern in self.PATTERNS:
                match = pattern.match(stripped)
                if match:
                    number = int(match.group(1))
                    confidence = 0.8
                    # 连续题号提高置信度
                    if results and number == results[-1]['number'] + 1:
                        confidence = 0.95
                    results.append({
                        'number': number,
                        'position': line_num,
                        'format': pattern.pattern,
                        'confidence': confidence,
                        'context': stripped[:60],
                    })
                    matched = True
                    break

            # 2. 尝试中文数字题号（"一、"、"二、"等）
            if not matched:
                cn_match = re.match(r'^\s*([一二三四五六七八九十]+)、\s*', stripped)
                if cn_match:
                    cn_text = cn_match.group(1)
                    number = self._cn_to_number(cn_text)
                    if number is not None:
                        confidence = 0.8
                        if results and number == results[-1]['number'] + 1:
                            confidence = 0.95
                        results.append({
                            'number': number,
                            'position': line_num,
                            'format': 'cn_number',
                            'confidence': confidence,
                            'context': stripped[:60],
                        })

        return results

    def _cn_to_number(self, cn_text: str) -> Optional[int]:
        """将中文数字转换为阿拉伯数字（长词优先）"""
        for cn, num in self.CN_NUM_MAP.items():
            if cn_text == cn:
                return num
        return None

    def resolve_conflicts(self, candidates: list) -> list:
        """
        解决题号识别冲突。
        使用连续性判断选择最长的连续序列。
        """
        if not candidates:
            return []

        # 按位置排序
        sorted_candidates = sorted(candidates, key=lambda x: x['position'])

        # 选择连续性最好的序列
        best_sequence = []
        current_sequence = [sorted_candidates[0]]

        for i in range(1, len(sorted_candidates)):
            if sorted_candidates[i]['number'] == current_sequence[-1]['number'] + 1:
                current_sequence.append(sorted_candidates[i])
            else:
                if len(current_sequence) > len(best_sequence):
                    best_sequence = current_sequence
                current_sequence = [sorted_candidates[i]]

        if len(current_sequence) > len(best_sequence):
            best_sequence = current_sequence

        return best_sequence


# ============ AnswerExtractor: 答案提取器 ============

class AnswerExtractor:
    """
    从答案文本中提取结构化答案信息，支持多种答案格式。
    """

    # 支持的答案格式
    ANSWER_PATTERNS = [
        r'答案[：:]\s*([A-Da-d]+)',           # 答案：A
        r'参考答案[：:]\s*([A-Da-d]+)',       # 参考答案：AB
        r'正确答案[：:]\s*([A-Da-d]+)',       # 正确答案：ABC
        r'标准答案[：:]\s*([A-Da-d]+)',       # 标准答案：ABCD
        r'Answer[：:]\s*([A-Da-d]+)',         # Answer: A
        r'故本题答案为([A-Da-d]+)',           # 故本题答案为D
        r'本题选([A-Da-d]+)',                 # 本题选AB
        r'应选([A-Da-d]+)',                   # 应选C
    ]

    def extract_with_context(self, text: str, question_block: dict) -> dict:
        """
        带上下文的答案提取。
        输入：答案文本和题目块信息（含 question_type）
        输出：{answer, confidence, format, raw_text}
        """
        if not text:
            return {'answer': '', 'confidence': 0.0, 'format': '', 'raw_text': ''}

        question_type = question_block.get('question_type', '单选题')

        # 尝试所有标准答案格式
        for pattern in self.ANSWER_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                answer = match.group(1).upper()
                if self.validate_answer(answer, question_type):
                    return {
                        'answer': answer,
                        'confidence': 0.9,
                        'format': pattern,
                        'raw_text': match.group(0),
                    }

        # 回退：尝试提取单个字母
        single_letter_match = re.search(r'\b([A-Da-d])\b', text)
        if single_letter_match:
            answer = single_letter_match.group(1).upper()
            if self.validate_answer(answer, question_type):
                return {
                    'answer': answer,
                    'confidence': 0.7,
                    'format': 'single_letter',
                    'raw_text': single_letter_match.group(0),
                }

        # 论述题/写作题回退：整段文本即为答案
        if question_type in ('论述题', '写作题'):
            cleaned = text.strip()
            if cleaned and self.validate_answer(cleaned, question_type):
                return {
                    'answer': cleaned,
                    'confidence': 0.8,
                    'format': 'full_text',
                    'raw_text': cleaned[:200],
                }

        return {'answer': '', 'confidence': 0.0, 'format': '', 'raw_text': ''}

    def validate_answer(self, answer: str, question_type: str) -> bool:
        """
        验证答案是否合理。
        根据题目类型验证答案格式。
        """
        if question_type in ('单选题', '多选题'):
            return self._validate_choice_answer(answer, question_type)
        elif question_type in ('论述题', '写作题'):
            return len(answer.strip()) >= 50
        else:
            return bool(answer.strip())

    def _validate_choice_answer(self, answer: str, question_type: str) -> bool:
        """
        验证选择题答案格式。
        - 单选题：单个字母 A-D
        - 多选题：多个字母 A-D，按字母顺序排列
        """
        clean_answer = re.sub(r'[\s、,，]', '', answer.upper())

        if question_type == '单选题':
            return bool(re.match(r'^[A-D]$', clean_answer))
        elif question_type == '多选题':
            if not re.match(r'^[A-D]+$', clean_answer):
                return False
            return clean_answer == ''.join(sorted(clean_answer))
        return False


# ============ IntelligentMatcher: 智能匹配引擎 ============

class IntelligentMatcher:
    """
    智能匹配题目和答案，支持多策略降级。
    """

    def __init__(self):
        self.text_preprocessor = TextPreprocessor()
        self.question_recognizer = QuestionNumberRecognizer()
        self.answer_extractor = AnswerExtractor()
        self._similarity_calculator = None
        self._structure_matcher = None

    def _get_similarity_calculator(self):
        if self._similarity_calculator is None:
            from .similarity import SimilarityCalculator
            self._similarity_calculator = SimilarityCalculator()
        return self._similarity_calculator

    def _get_structure_matcher(self):
        if self._structure_matcher is None:
            from .structure_matcher import StructureMatcher
            self._structure_matcher = StructureMatcher()
        return self._structure_matcher

    def match_questions_answers(self, questions_text: str, answers_text: str,
                                paper_name: str = '') -> 'MatchResult':
        """
        智能匹配题目和答案。
        策略：题号分段解析匹配（主要策略）
        """
        if not questions_text or not answers_text:
            return MatchResult(
                match_rate=0.0, matched_count=0, total_questions=0,
                questions=[], unmatched_question_numbers=[], extra_answer_numbers=[],
                analysis_count=0, strategy_used='无数据', details={},
            )

        # 预处理文本
        q_text = self.text_preprocessor.clean_text(questions_text)
        a_text = self.text_preprocessor.clean_text(answers_text)

        # 识别题号
        question_numbers = self.question_recognizer.recognize_with_confidence(q_text)
        question_numbers = self.question_recognizer.resolve_conflicts(question_numbers)

        # 提取题目块
        question_blocks = self._extract_question_blocks(q_text, question_numbers)

        # 提取答案映射
        answer_map = self._extract_answer_map(a_text)

        # 执行匹配
        matched_count = 0
        analysis_count = 0
        no_answer_nums = []

        for block in question_blocks:
            q_num = block['question_number']
            ans_entry = answer_map.get(q_num)

            if ans_entry and ans_entry.get('answer'):
                ans = ans_entry['answer']
                block['answer'] = ans
                matched_count += 1
                if ans_entry.get('analysis') and len(str(ans_entry['analysis'])) > 0:
                    block['analysis'] = ans_entry['analysis']
                    analysis_count += 1
            else:
                no_answer_nums.append(q_num)

        # 计算匹配率
        total = len(question_blocks)
        match_rate = matched_count / total if total > 0 else 0.0

        return MatchResult(
            match_rate=match_rate,
            matched_count=matched_count,
            total_questions=total,
            questions=question_blocks,
            unmatched_question_numbers=no_answer_nums,
            extra_answer_numbers=[],
            analysis_count=analysis_count,
            strategy_used='题号分段解析',
            details={'answer_map_keys': list(answer_map.keys())},
        )

    def _extract_question_blocks(self, text: str, question_numbers: list) -> list:
        """从文本中提取题目块"""
        blocks = []
        lines = text.split('\n')

        current_block = None
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # 检查是否是新的题号
            matched_new = False
            for q_info in question_numbers:
                num = q_info['number']
                if stripped.startswith(f"{num}.") or stripped.startswith(f"{num}、"):
                    if current_block:
                        blocks.append(current_block)
                    current_block = {
                        'question_number': num,
                        'content': stripped,
                        'options': [],
                        'answer': '',
                        'analysis': '',
                        'question_type': '单选题',
                    }
                    matched_new = True
                    break

            if not matched_new and current_block:
                # 检查是否是选项
                option_match = re.match(r'^([A-D])\.\s*(.*)', stripped)
                if option_match:
                    current_block['options'].append({
                        'key': option_match.group(1),
                        'value': option_match.group(2),
                    })

        if current_block:
            blocks.append(current_block)

        return blocks

    def _extract_answer_map(self, text: str) -> dict:
        """从答案文本中提取答案映射 {题号: {answer, analysis}}"""
        answer_map = {}

        # 策略1：标准答案格式（"答案：A"、"参考答案：AB" 等）
        for pattern in AnswerExtractor.ANSWER_PATTERNS:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            for match in matches:
                context = text[max(0, match.start() - 80):match.start()]
                num_match = re.search(r'(\d+)', context)
                if num_match:
                    q_num = int(num_match.group(1))
                    answer = match.group(1).upper()
                    # 尝试提取解析
                    analysis = self._extract_analysis(text, match.end())
                    answer_map[q_num] = {'answer': answer, 'analysis': analysis}

        # 策略2：题号.字母 格式（"1.A"、"2.B" 等，预处理后常见格式）
        num_answer_pattern = re.compile(r'(\d+)\.\s*([A-Da-d]+)')
        for match in num_answer_pattern.finditer(text):
            q_num = int(match.group(1))
            if q_num not in answer_map:
                answer = match.group(2).upper()
                analysis = self._extract_analysis(text, match.end())
                answer_map[q_num] = {'answer': answer, 'analysis': analysis}

        # 策略3：题号 + 单独字母（"1 A"、"2 B" 等空格分隔格式）
        num_space_pattern = re.compile(r'(\d+)\s+([A-Da-d])\b')
        for match in num_space_pattern.finditer(text):
            q_num = int(match.group(1))
            if q_num not in answer_map:
                answer = match.group(2).upper()
                analysis = self._extract_analysis(text, match.end())
                answer_map[q_num] = {'answer': answer, 'analysis': analysis}

        return answer_map

    def _extract_analysis(self, text: str, start_pos: int) -> str:
        """从答案后方提取解析文本"""
        remaining = text[start_pos:start_pos + 500]
        # 匹配"解析："后的内容，直到行尾或下一题号
        analysis_match = re.search(r'解析[：:]\s*(.+?)(?:\n|$)', remaining)
        if analysis_match:
            return analysis_match.group(1).strip()
        return ''

    def evaluate_match_quality(self, result: 'MatchResult') -> dict:
        """
        评估匹配结果质量。
        返回：{match_rate, confidence, consistency, quality_score}
        """
        match_rate = result.match_rate
        confidence = min(match_rate * 1.1, 1.0)
        consistency = 1.0 - (len(result.unmatched_question_numbers) / result.total_questions if result.total_questions > 0 else 0)
        quality_score = match_rate * 0.5 + confidence * 0.3 + consistency * 0.2

        return {
            'match_rate': match_rate,
            'confidence': confidence,
            'consistency': consistency,
            'quality_score': quality_score,
        }


# ============ ContentCleaner: 噪声过滤器 ============

class ContentCleaner:
    """
    过滤文档中的无关内容（页眉、页脚、页码、日期、目录标记等）。
    采用两阶段过滤：行级模式匹配 → 重复行检测。
    """

    # 行级噪声模式 (pattern, label)
    NOISE_PATTERNS = [
        (re.compile(r'^\s*\d{1,4}\s*$'), 'page_number'),            # 纯数字 → 页码
        (re.compile(r'^\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\s*$'), 'date'),  # 日期
        (re.compile(r'^第\s*\d+\s*页\s*(?:共\s*\d+\s*页)?$'), 'page_label'),  # 第N页
        (re.compile(r'^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]'), 'toc_marker'),   # 目录标记
        (re.compile(r'^\s*(?:版权所有|翻印必究|内部资料|机密|绝密|秘密)\s*$'), 'classification'),  # 密级标记
        (re.compile(r'^\s*(?:·\s*\d+\s*·|-\s*\d+\s*-)\s*$'), 'separator'),  # 分隔符 · 1 · / - 1 -
        (re.compile(r'^\s*_{3,}\s*$'), 'hr'),                      # 下划线分隔
        (re.compile(r'^\s*-{3,}\s*$'), 'hr_dash'),                 # 短横线分隔
        (re.compile(r'^\s*\*{3,}\s*$'), 'hr_star'),                # 星号分隔
        (re.compile(r'^https?://\S+$'), 'url'),                    # URL
        (re.compile(r'^(?:扫描|扫一扫|二维码|关注|公众号|微信|QQ)\S*$'), 'social'),  # 社交推广
        # === 第3波：推广/营销/联系方式过滤 ===
        (re.compile(r'(?:来源|整理|编辑|制作|供稿|文\s*[／/]|作者)\s*[：:：]\s*.+'), 'credit_line'),
        (re.compile(r'(?:微信|QQ|手机|电话|联系方式|咨询)\s*[：:：]\s*[\d\w]+'), 'contact'),
        (re.compile(r'关注\s*(?:公众号|微信|微博|抖音|小红书)\s*[：:：]?\s*\S+'), 'social_promo'),
        (re.compile(r'(?:扫码|扫一扫|二维码)\S*'), 'qr_promo'),
        (re.compile(r'(?:上岸|保过|报班|课程咨询|免费领取|加微信|加QQ|联系客服|获取.*更新|一个上岸)\S*'), 'ad'),
        (re.compile(r'(?:gwy\d+|gwyeasy|gk\d+|ht\d+)'), 'account_id'),
        (re.compile(r'(?:淘宝|taobao|拼多多|京东|闲鱼)\S*'), 'ecommerce'),
        (re.compile(r'^\s*(?:更多|全部|查看全文|阅读原文)\s*[：:：]?\s*$'), 'more_link'),
        (re.compile(r'http[s]?://\S+'), 'url_inline'),
    ]

    # 页眉页脚检测：在文档中重复出现 ≥ HEADER_FOOTER_THRESHOLD 次的短行
    HEADER_FOOTER_THRESHOLD = 3
    HEADER_FOOTER_MAX_LENGTH = 60  # 页眉页脚通常较短

    # 内容行豁免：命中这些标记的短行属于"答案/解析"正文数据，
    # 即使重复出现也绝不是页眉页脚。
    # 真实案例1：2016江西答案解析PDF中 "故正确答案为A。" 恰好出现3次
    # （≥阈值且末次位置>0.9）→ 被本机制整组误杀 → 匹配率从100%跌至52.6%，
    # 且幸存的仅是字母组合稀有（<3次）的答案行——症状极具迷惑性。
    # 真实案例2：2019深圳辅警卷判断题的结论写作 "故表述正确。"/"故表述错误。"，
    # 既短又成组重复（10 道判断题），同样被整组误删；随后答案段缺失，
    # 宽松重试从邻近解析文字里抓了 C/D/D/B 当答案。
    # 判断题结论行必须一并豁免，否则重演案例1。
    _ANSWER_LINE_HINT = re.compile(
        r'(?:正确答案|参考答案|标准答案|本题答案|答案\s*[为是:：]|故选|应选|本题选)'
        r'|(?:故|因此|所以|综上)?\s*(?:上述|该|此项|此|本)?\s*(?:表述|说法)\s*(?:是)?\s*'
        r'(?:正确|错误|错|对)\s*[。．.！!]?\s*$'
        r'|本题为判断题'
        r'|(?:正确)?答案\s*(?:为|是)\s*(?:正确|错误|错|对)\s*[。．.！!]?\s*$'
    )

    # === 2026-09-29 新增：页脚/水印专项规则 ===
    # 真实案例：2023年1月7日国考公安专业科目 PDF（16页）
    #   ① 页脚「第 17 页，共 18 页」：NOISE_PATTERNS 的 page_label 模式中间只允许 \s*，
    #      匹配不到中文逗号「，」，真实 PDF 全部使用「，」→ 16页×2处 全部漏网；
    #   ② 水印「小绵羊上岸店 小绵羊上岸店」：Phase2 以「整行完全相同」计数，
    #      而该水印每页重复次数不一（2连/3连/4连…各有变体），每种变体单独计数后
    #      多数不足 HEADER_FOOTER_THRESHOLD → 集体漏网（实测残留 80 处）。

    # 页脚：允许「，,、」分隔（真实 PDF 常见「第 17 页，共 18 页」）
    _PAGE_FOOTER = re.compile(
        r'^第\s*\d+\s*页\s*[，,、]?\s*(?:共\s*\d+\s*页)?\s*$'
    )
    # 页脚变体：「— 17 —」「17 / 18」「17-18」
    _PAGE_FOOTER_ALT = re.compile(
        r'^[—\-–]\s*\d+\s*[—\-–]?\s*$'
        r'|^\d{1,3}\s*[/／\-–]\s*\d{1,3}\s*$'
    )

    # 内容行豁免：命中即视为题目正文，绝不可当噪声删除
    _OPTION_MARK = re.compile(r'(?:^|\s)[A-DＡ-Ｄ][.．、)）]')
    _QNUM_PREFIX = re.compile(r'^\s*\d{1,3}\s*[．.、]')

    @staticmethod
    def _strip_punct(t: str) -> str:
        """取 token 的字词核心（去标点/空白），用于水印同一性比对"""
        return re.sub(r'[^\w\u4e00-\u9fff]', '', t)

    @classmethod
    def _is_page_footer(cls, stripped: str) -> bool:
        """整行是否只是「第N页，共M页」页脚。

        含题号前缀或选项标记时一律返回 False —— 「参见第3页」这类正文表述
        以及「第3页第4题」必须保留，误删会直接损坏题干。
        """
        if cls._OPTION_MARK.search(stripped) or cls._QNUM_PREFIX.match(stripped):
            return False
        return bool(cls._PAGE_FOOTER.match(stripped)
                    or cls._PAGE_FOOTER_ALT.match(stripped))

    @classmethod
    def _is_watermark_line(cls, stripped: str) -> bool:
        """整行是否由同一短词重复 2 次以上构成（水印/推广行）。

        真实案例「小绵羊上岸店 小绵羊上岸店」在不同页重复次数不一，
        Phase2 精确字符串计数无法覆盖，必须按「同一性」而非「字符串相等」判定。
        含题号、选项标记或答案结论标记时一律豁免。
        """
        if cls._OPTION_MARK.search(stripped) or cls._QNUM_PREFIX.match(stripped):
            return False
        if cls._ANSWER_LINE_HINT.search(stripped):
            return False
        tokens = stripped.split()
        if len(tokens) < 2:
            return False
        base = cls._strip_punct(tokens[0])
        if len(base) < 2:          # 过短的 token（如单个数字）不判定，避免误伤
            return False
        return all(cls._strip_punct(t) == base for t in tokens)

    @classmethod
    def clean(cls, lines: List[str]) -> List[str]:
        """
        过滤文本行中的噪声。
        返回过滤后的行列表。
        """
        if not lines:
            return []

        # Phase 1: 行级模式过滤
        # 顺序要点：专项规则先于 NOISE_PATTERNS 判定。页脚/水印若留到后面，
        # 页面文本里紧邻的题号行可能先被拼接，污染「题号在行首」的假设。
        filtered = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue  # 跳过完全空行
            is_noise = False
            # ① 页脚专项（含中文逗号变体）
            if cls._is_page_footer(stripped):
                logger.debug(f"[ContentCleaner] 过滤页脚: {stripped[:50]}")
                is_noise = True
            # ② 水印专项（同一短词重复变体）
            elif cls._is_watermark_line(stripped):
                logger.debug(f"[ContentCleaner] 过滤水印行: {stripped[:50]}")
                is_noise = True
            else:
                for pattern, label in cls.NOISE_PATTERNS:
                    if pattern.match(stripped):
                        logger.debug(f"[ContentCleaner] 过滤噪声({label}): {stripped[:50]}")
                        is_noise = True
                        break
            if not is_noise:
                filtered.append(line)

        if not filtered:
            return filtered

        # Phase 2: 重复短行检测（页眉/页脚特征）
        line_counts: Dict[str, List[int]] = {}
        for i, line in enumerate(filtered):
            stripped = line.strip()
            if len(stripped) <= cls.HEADER_FOOTER_MAX_LENGTH and len(stripped) > 1:
                # 内容行豁免：答案标记行是解析核心数据（见 _ANSWER_LINE_HINT 注释）
                if cls._ANSWER_LINE_HINT.search(stripped):
                    continue
                # 选项行豁免：「A.说法一」这类行是**题目内容**，绝不可当页眉整组删除。
                # 真实事故（tests/test_realworld_formats 江西2016 端到端用例）：
                # 该卷每题选项文本相同，「A.说法一」重复 5 次 ≥ HEADER_FOOTER_THRESHOLD(3)
                # 且 len(indices)>=5，被 Phase2 重复短行检测整组误删 →
                # 题块 options 变 0 → 无选项题门控 block_accepts_letter_answer 拒绝
                # 字母答案 → 匹配率由 100% 跌至 0%。
                # 选项行与页眉页脚形态完全不同（页眉不会长成「A.xxx」），豁免是安全的。
                if cls._OPTION_MARK.search(stripped):
                    continue
                line_counts.setdefault(stripped, []).append(i)

        repeated_indices = set()
        for text, indices in line_counts.items():
            if len(indices) >= cls.HEADER_FOOTER_THRESHOLD:
                # 检查是否均匀分布（页眉页脚的特征：出现在文档开头或结尾附近）
                first_pos = indices[0] / max(len(filtered), 1)
                last_pos = indices[-1] / max(len(filtered), 1)
                if first_pos < 0.1 or last_pos > 0.9 or len(indices) >= 5:
                    logger.debug(f"[ContentCleaner] 过滤重复行(×{len(indices)}): {text[:50]}")
                    repeated_indices.update(indices)

        if repeated_indices:
            filtered = [line for i, line in enumerate(filtered) if i not in repeated_indices]

        return filtered

    @classmethod
    def clean_text(cls, text: str) -> str:
        """对完整文本进行噪声过滤，返回清理后的文本"""
        if not text:
            return ''
        lines = text.split('\n')
        cleaned = cls.clean(lines)
        return '\n'.join(cleaned)

    # 无关图片文件名黑名单
    IRRELEVANT_IMAGE_PATTERNS = [
        re.compile(r'(?:qr|qrcode|二维码|erweima)', re.IGNORECASE),
        re.compile(r'(?:wechat|weixin|微信)', re.IGNORECASE),
        re.compile(r'(?:taobao|淘宝|拼多多|京东|闲鱼|天猫)', re.IGNORECASE),
        re.compile(r'(?:广告|ad|promo|推广)', re.IGNORECASE),
        re.compile(r'(?:logo|图标|头像|avatar)', re.IGNORECASE),
        re.compile(r'(?:公众号|订阅号|gzh)', re.IGNORECASE),
    ]

    @classmethod
    def is_irrelevant_image(cls, filename: str, position_ratio: float = 0.0) -> bool:
        """
        判断图片是否与题目内容无关（二维码、推广图、尾部广告等）。

        Args:
            filename: 图片文件名或路径
            position_ratio: 图片在文档中的位置比例（0.0~1.0），末尾>0.85的图片大概率是广告
        """
        if not filename:
            return False
        # 文档末尾的图片（最后15%）→ 大概率是广告/二维码
        if position_ratio > 0.85:
            return True
        # 文件名匹配黑名单
        basename = os.path.basename(filename) if os.path else filename
        for pattern in cls.IRRELEVANT_IMAGE_PATTERNS:
            if pattern.search(basename):
                return True
        return False

    @classmethod
    def clean_question_content(cls, text: str) -> str:
        """
        对单条题目内容进行深度清洗。

        在 clean_text 基础上额外处理：
        1. 移除尾随的行内 URL
        2. 移除末尾来源/整理行（倒数 3 行内匹配 credit_line）
        3. 移除文档末尾纯推广段落
        4. 移除行内推广关键词（保留题干正文）
        """
        if not text:
            return ''

        # 先执行标准行级清洗
        cleaned = cls.clean_text(text)
        if not cleaned:
            return cleaned

        lines = cleaned.split('\n')
        if not lines:
            return cleaned

        # 逐行处理：移除行内 URL（保留前面的正文）
        url_inline_pattern = re.compile(r'http[s]?://\S+')
        processed = []
        for line in lines:
            stripped = line.strip()
            # 如果整行就是 URL，跳过
            if url_inline_pattern.fullmatch(stripped):
                continue
            # 如果行以 URL 开头，跳过
            if url_inline_pattern.match(stripped):
                continue
            # 移除行尾 URL（保留正文）
            line = url_inline_pattern.sub('', line).strip()
            if line:
                processed.append(line)

        if not processed:
            return ''

        # 从末尾开始检查：移除来源/整理行
        credit_pattern = re.compile(
            r'(?:来源|整理|编辑|制作|供稿|文\s*[／/]|作者)\s*[：:：]'
        )
        tail_remove_count = 0
        for i in range(len(processed) - 1, max(len(processed) - 4, -1), -1):
            line = processed[i].strip()
            if credit_pattern.search(line):
                tail_remove_count += 1
            elif re.search(r'(?:gwy\d+|gwyeasy|gk\d+|微信|公众号|关注|上岸)',
                          line, re.IGNORECASE):
                tail_remove_count += 1
            else:
                break

        if tail_remove_count > 0:
            processed = processed[:len(processed) - tail_remove_count]

        # 移除首尾空行
        while processed and not processed[0].strip():
            processed.pop(0)
        while processed and not processed[-1].strip():
            processed.pop()

        return '\n'.join(processed)


# ============ 增强纯序列匹配 ============

def _match_pure_sequence_enhanced(answer_text: str, question_count: int) -> Dict[int, Dict[str, Optional[str]]]:
    """
    增强版纯序列匹配——处理无题号的纯答案序列。
    支持格式：
    - 空格分隔: "A B C D A B C D"
    - 换行分隔: "A\\nB\\nC\\nD"
    - 逗号分隔: "A,B,C,D"
    - 中文答案: "对 错 对 错"
    - 混合格式: "1A 2B 3C 4D"
    - 连续无分隔: "ABCDABCD"

    校验规则：
    - 提取的答案数 ≈ 题目数(误差<20%) → 高置信度按位置映射
    - 答案数明显少于题目 → 标记为低置信度
    - 答案数为0 → 返回空
    """
    if not answer_text or not answer_text.strip():
        return {}

    text = answer_text.strip()

    # 策略1: 混合格式 "1A 2B 3C 4D" 或 "1.A 2.B 3.C 4.D"
    mixed_pattern = re.compile(r'(?:^|\s)(\d+)\s*[.、．)）]?\s*([A-Da-d对错正确错误是否])(?=\s|$)')
    mixed_matches = mixed_pattern.findall(text)
    if mixed_matches and len(mixed_matches) >= 2:
        result = {}
        for num_str, ans_str in mixed_matches:
            num = int(num_str)
            ans = ans_str.upper()
            if ans in CN_ANSWER_MAP:
                ans = CN_ANSWER_MAP[ans]
            if ans and all(c in "ABCD" for c in str(ans)) and num not in result:
                result[num] = {'answer': ans, 'analysis': None}
        if len(result) >= min(2, question_count * 0.5):
            return result

    # 策略2: 提取所有单独的A-D字母（处理空格/逗号/换行分隔）
    # 先规范化：将所有分隔符替换为空格
    normalized = re.sub(r'[\s,;，；、\n\r]+', ' ', text)
    # 提取所有独立的A-D字母或中文答案
    tokens = normalized.split()
    answers = []
    for token in tokens:
        token_upper = token.strip().upper()
        if len(token_upper) == 1 and token_upper in 'ABCD':
            answers.append(token_upper)
        elif token_upper in CN_ANSWER_MAP:
            answers.append(CN_ANSWER_MAP[token_upper])
        # 也处理中文答案
        elif token in ('对', '正确', '是', '√'):
            answers.append('A')
        elif token in ('错', '错误', '否', '×'):
            answers.append('B')

    if answers:
        # 校验：答案数应与题目数接近
        tolerance = max(2, int(question_count * 0.2))
        if abs(len(answers) - question_count) <= tolerance:
            result = {}
            for i, ans in enumerate(answers):
                result[i + 1] = {'answer': ans, 'analysis': None}
            return result
        elif len(answers) >= question_count * 0.5:
            # 答案偏少但仍有参考价值，标记为低置信度
            result = {}
            for i, ans in enumerate(answers):
                result[i + 1] = {'answer': ans, 'analysis': None}
            return result

    # 策略3: 连续无分隔字符串 "ABCDABCD"（回退已有逻辑）
    # 检查文本是否为纯字母+中文答案序列
    pure = re.sub(r'[\s,;，；、\n\r]+', '', text)
    all_answers = []
    for ch in pure:
        ch_upper = ch.upper()
        if ch_upper in 'ABCD':
            all_answers.append(ch_upper)
        elif ch in ('对', '正', '是', '√'):
            all_answers.append('A')
        elif ch in ('错', '误', '否', '×'):
            all_answers.append('B')

    if all_answers and abs(len(all_answers) - question_count) <= max(3, int(question_count * 0.25)):
        result = {}
        for i, ans in enumerate(all_answers):
            result[i + 1] = {'answer': ans, 'analysis': None}
        return result

    return {}

# 题号提取正则模式（按优先级排列）
# 行首前缀容忍 Markdown 标题标记（"## 1、正确答案是：D"）：部分答案解析 PDF
# 由 Markdown 源生成，题号行带 "# " 前缀，导致行首锚定 \s* 失配、题号整段漏识别
# （真实案例：2017多省联考答案解析 100 题只认出 5 个，匹配率跌至 74%）。
_LINE_START = r'(?:^|\n)[ \t]*(?:#{1,6}[ \t]+)?'
QUESTION_NUMBER_PATTERNS = [
    # 第N题 / 第 N 题 / 第N、题
    ('cn_di', re.compile(r'第\s*(\d+)\s*[题]')),
    # N. / N． / N、 / N．
    ('num_dot', re.compile(_LINE_START + r'(\d+)\s*[.、．]')),
    # (N) / （N）
    ('paren', re.compile(r'[（(]\s*(\d+)\s*[）)]')),
    # [N] / 【N】
    ('bracket', re.compile(r'[\[【]\s*(\d+)\s*[\]】]')),
    # N) / N）
    ('num_close_paren', re.compile(_LINE_START + r'(\d+)\s*[)）]')),
    # 纯数字后跟空格（最宽松，用于纯序列）
    ('bare_num', re.compile(_LINE_START + r'(\d+)\s+(?=[A-Da-d一-鿿])')),
]

# 答案提取正则模式（按优先级排列）
# 捕获组拓宽为含分隔符（、，,;；空白·），修复"A、B、C"只被截取为"A"的多选答案丢失问题。
# range/per_item 仍保持连续字母，交由 parse_answer_sequence 按题号逐题处理（非多选场景）。
ANSWER_PATTERNS = [
    # 【答案】C / 《答案》C / <答案>C / 答案:C
    ('chinese_bracket', re.compile(r'[【《<\[]?\s*答\s*案\s*[】》>\]：:：]\s*([A-Da-d对错正确错误是否、，,;；\s·]+)')),
    # 答案：C / 参考答案：C
    ('chinese_colon', re.compile(r'(?:参考)?答案\s*[：:：]\s*([A-Da-d对错正确错误是否、，,;；\s·]+)')),
    # 正确选项：C / 正确答案: C
    ('correct_option', re.compile(r'(?:正确选项|正确答案|正确)\s*[：:：]\s*([A-Da-d、，,;；\s·]+)')),
    # Answer: C / Answer Key: C
    ('english', re.compile(r'Answer\s*(?:Key)?\s*[：:：]\s*([A-Da-d、，,;；\s·]+)', re.IGNORECASE)),
    # 选C / 选 C
    ('choose', re.compile(r'选\s*([A-Da-d、，,;；\s·]+)')),
    # 连续答案序列: 1-5: ABCCD
    ('range', re.compile(r'(\d+)\s*[-～~]\s*(\d+)\s*[：:：]\s*([A-Da-d对错正确错误是否]+)')),
    # 逐题答案: 1.C 2.B 3.A
    ('per_item', re.compile(r'(?:^|\n)\s*(\d+)\s*[.、．)）]\s*([A-Da-d对错正确错误是否]+)\s*(?=\d|$|\n)')),
]

# ============ 嵌入式答案模式（答案隐藏在详细解析末尾） ============
# 用于解析"故本题答案为D"、"故正确答案为C"等格式
# 优先级高于普通答案模式中的宽松匹配
EMBEDDED_ANSWER_PATTERNS = [
    # ---------- 判断题结论（最高优先级）----------
    # 真实事故：2019 深圳辅警《公安素质测试》判断题 81–90 的答案写作
    # 「故表述正确。」「故表述错误。」——既不含"答案"二字，也没有冒号，
    # 下面 12 条模式一个都匹配不上，于是退化成单字母兜底，
    # 从上一题遗留的「A项、B项错误，C项正确」里抓了 C/D/D/B 写进库里。
    # 必须放在最前：它们要求结论词位于**行尾**，避免把选择题解析中的
    # 中间描述（如"A项表述正确"）误当成整题答案。
    # 捕获组是必需的：抽取侧统一取 m.group(1) 作为答案。
    ('pan_jiao_wu', re.compile(
        r'(?:故|因此|所以|综上)?\s*(?:上述|该|此项|此|本)?\s*(?:表述|说法)\s*(?:是)?\s*'
        r'(错误|错)\s*[。．.！!]?\s*$', re.MULTILINE)),
    ('pan_jiao_dui', re.compile(
        r'(?:故|因此|所以|综上)?\s*(?:上述|该|此项|此|本)?\s*(?:表述|说法)\s*(?:是)?\s*'
        r'(正确|对)\s*[。．.！!]?\s*$', re.MULTILINE)),
    # 整行只有一个判定词（"正确。"/"错误"/"本题为判断题，正确"）
    ('pan_jiao_bare_wu', re.compile(
        r'^\s*(?:故|因此|所以|综上)?\s*(?:上述|该|此项|此|本)?\s*(?:表述|说法)?\s*(?:是)?\s*'
        r'(错误|错)\s*[。．.！!]?\s*$', re.MULTILINE)),
    ('pan_jiao_bare_dui', re.compile(
        r'^\s*(?:故|因此|所以|综上)?\s*(?:上述|该|此项|此|本)?\s*(?:表述|说法)?\s*(?:是)?\s*'
        r'(正确|对)\s*[。．.！!]?\s*$', re.MULTILINE)),
    # 故本题答案为D / 故本题答案选D
    ('gu_ben_ti', re.compile(r'故本题答案(?:为|选)\s*[：:：]?\s*([A-Da-d、，,;；\s·]+)')),
    # 故正确答案为C / 故正确答案是C
    ('gu_zheng_que', re.compile(r'故正确(?:的)?答案(?:为|是|选)\s*[：:：]?\s*([A-Da-d、，,;；\s·]+)')),
    # 故答案为B / 故答案选B
    ('gu_daan', re.compile(r'故答案(?:为|选)\s*[：:：]?\s*([A-Da-d、，,;；\s·]+)')),
    # 因此本题答案为A / 因此本题选A
    ('yin_ci_ben_ti', re.compile(r'因此本题答案(?:为|选)\s*[：:：]?\s*([A-Da-d、，,;；\s·]+)')),
    # 因此正确答案为D
    ('yin_ci_zheng_que', re.compile(r'因此正确(?:的)?答案(?:为|是|选)\s*[：:：]?\s*([A-Da-d、，,;；\s·]+)')),
    # 因此答案为C / 因此选C
    ('yin_ci_daan', re.compile(r'因此答案(?:为|选)\s*[：:：]?\s*([A-Da-d、，,;；\s·]+)')),
    # 本题答案为B / 本题选B
    ('ben_ti_daan', re.compile(r'本题答案(?:为|选)\s*[：:：]?\s*([A-Da-d、，,;；\s·]+)')),
    # 正确答案是A / 正确选项为C（无冒号版本）
    ('zheng_que_shi', re.compile(r'正确(?:答案|选项)(?:是|为|选)\s*[：:：]?\s*([A-Da-d、，,;；\s·]+)')),
    # 应选D / 应选择D
    ('ying_xuan', re.compile(r'应选(?:择)?\s*[：:：]?\s*([A-Da-d、，,;；\s·]+)')),
    # 答案为D。（句号结尾）
    ('daan_wei', re.compile(r'答案(?:为|是)\s*[：:：]?\s*([A-Da-d、，,;；\s·]+)\s*[。.]')),
]

# 判断题判定词（从解析结论直读"正确/错误"，用于无选项题）
# 真实事故：2019 深圳辅警卷判断题 81–90 没有任何选项，答案却被写成
# A/B/C/D —— 上游 CN_ANSWER_MAP 把"正确/错误"映射成 A/B，
# 下游又只接受纯字母，于是无选项题被塞进一个不可判分的假答案。
_JUDGE_VERDICT_PATTERNS = (
    (re.compile(r'(?:故|因此|所以|综上)[^。\n]{0,12}表述\s*(?:是)?\s*(错误|错)\s*[。．.！!]?\s*$',
                re.MULTILINE), '错误'),
    (re.compile(r'(?:故|因此|所以|综上)[^。\n]{0,12}表述\s*(?:是)?\s*(正确|对)\s*[。．.！!]?\s*$',
                re.MULTILINE), '正确'),
    (re.compile(r'(?:故|因此|所以|综上)[^。\n]{0,12}说法\s*(?:是)?\s*(错误|错)\s*[。．.！!]?\s*$',
                re.MULTILINE), '错误'),
    (re.compile(r'(?:故|因此|所以|综上)[^。\n]{0,12}说法\s*(?:是)?\s*(正确|对)\s*[。．.！!]?\s*$',
                re.MULTILINE), '正确'),
    # 整行只有判定词
    (re.compile(r'^\s*(?:故|因此|所以|综上)?\s*(?:上述|该|此项|此|本)?\s*'
                r'(?:表述|说法)?\s*(?:是)?\s*(错误|错)\s*[。．.！!]?\s*$',
                re.MULTILINE), '错误'),
    (re.compile(r'^\s*(?:故|因此|所以|综上)?\s*(?:上述|该|此项|此|本)?\s*'
                r'(?:表述|说法)?\s*(?:是)?\s*(正确|对)\s*[。．.！!]?\s*$',
                re.MULTILINE), '正确'),
    # "故正确答案为错误。" / "答案为正确" —— 同一份答案卷里两种写法并存
    # （2019 深圳辅警卷 81–84 用"故表述错误"，85–89 用"本题为判断题，故正确答案为错误"）
    (re.compile(r'(?:故|因此|所以|综上)?\s*(?:本题为判断题[，,]\s*)?'
                r'(?:本题)?\s*(?:正确)?答案\s*(?:为|是)\s*(错误|错)\s*[。．.！!]?\s*$',
                re.MULTILINE), '错误'),
    (re.compile(r'(?:故|因此|所以|综上)?\s*(?:本题为判断题[，,]\s*)?'
                r'(?:本题)?\s*(?:正确)?答案\s*(?:为|是)\s*(正确|对)\s*[。．.！!]?\s*$',
                re.MULTILINE), '正确'),
    # "本题为判断题，正确"（逗号直接跟判定词，无"答案"二字）
    (re.compile(r'本题为判断题\s*[，,]\s*(错误|错)\s*[。．.！!]?\s*$',
                re.MULTILINE), '错误'),
    (re.compile(r'本题为判断题\s*[，,]\s*(正确|对)\s*[。．.！!]?\s*$',
                re.MULTILINE), '正确'),
)


def judge_verdict_from_text(text: Any) -> str:
    """从解析正文提取判断题结论，返回 '正确' / '错误' / ''。

    必须取**最后一个**结论：解析里常先否定部分选项（如"A项错误"）再给总结论。
    """
    if not text:
        return ''
    s = str(text)
    verdict = ''
    for pat, v in _JUDGE_VERDICT_PATTERNS:
        for _m in pat.finditer(s):
            verdict = v
    return verdict


def block_accepts_letter_answer(block: Dict[str, Any]) -> bool:
    """该题块是否允许落 A/B/C/D 形式的答案。

    真实事故（2019 深圳辅警卷 81–90）：判断题没有 A/B 选项，却因
    「宽松重试」「增强纯序列匹配」「位置兜底匹配」三道兜底策略把字母灌了进去，
    产出 C/D/D/B 这类与题干无关的假答案 —— 不可判分，也会误导教师。

    判据只看**有没有选项**，不看题型名：
    - 有选项（>=2）→ 字母有意义。即便题型判成"判断题"（如
      "（ ）A.正确 B.错误 C.正确 D.错误"），答案也应当是字母。
    - 无选项 → 字母无意义。判断题只能落"正确/错误"，
      主观题只能留空交 need_review 复核，绝不允许猜字母。
    """
    return len(block.get('options') or []) >= 2


_ANSWER_REGION_HEAD_RE = re.compile(r'^[ \t]*(\d{1,3})\s*[、.．)）]')


def answer_region_for(text: str, q_num: int) -> str:
    """从答案文本中截取题号 q_num 所属的整段（到下一个题号标题为止）。

    用于无选项题（判断题）从解析结论直读"正确/错误" —— 这类题在答案
    文件里既没有"答案：C"也没有 A/B 选项，只有自然语言结论。
    """
    if not text:
        return ''
    lines = str(text).split('\n')
    start = None
    for i, ln in enumerate(lines):
        m = _ANSWER_REGION_HEAD_RE.match(ln)
        if m and int(m.group(1)) == q_num:
            start = i
            break
    if start is None:
        return ''
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = _ANSWER_REGION_HEAD_RE.match(lines[j])
        if m and int(m.group(1)) == q_num + 1:
            end = j
            break
    return '\n'.join(lines[start:end])


# 中文答案映射
CN_ANSWER_MAP = {
    '对': 'A', '正确': 'A', '是': 'A', '√': 'A',
    '错': 'B', '错误': 'B', '否': 'B', '×': 'B',
}

# 科目检测关键词（三级权重：core=5, high=3, normal=1）
# 设计原则：公专科目必须能从行测关键词中"突围"——核心词权重显著高于普通词
SUBJECT_KEYWORDS = {
    '公专': {
        'core': ['公安专业', '公安基础知识', '警务实务', '公安专业知识', '警察执法',
                 '治安管理', '刑事侦查', '行政执法', '公安机关', '人民警察',
                 '公安专业考试', '人民警察基本素养', '警务技能', '公安业务',
                 '刑事犯罪', '治安处罚', '公安法学', '警察法', '人民警察法',
                 '公安基础', '基本警务能力', '职业素养'],
        'high': ['公安', '警务', '警察', '执法', '侦查', '治安', '刑事',
                 '犯罪', '刑罚', '拘留', '逮捕', '搜查', '盘查',
                 '警械', '武器', '巡逻', '交警', '消防', '户籍'],
        'normal': ['职业道德', '纪律', '廉洁', '勤务', '交通', '诉讼',
                   '证据', '宪法', '行政处罚', '刑事诉讼', '民事诉讼',
                   '治安管理处罚', '公安机关组织', '人民警察使用']
    },
    '申论': {
        'core': ['申论', '归纳概括', '综合分析', '提出对策', '应用文写作', '议论文写作',
                 '申论写作', '大作文', '小作文', '公文写作'],
        'high': ['概括', '分析', '对策', '建议', '方案', '措施', '公文', '公务员',
                 '材料', '给定资料', '根据材料', '结合材料'],
        'normal': ['论证', '论述', '评析', '通知', '报告', '请示',
                   '阐述', '说明', '评价', '评述', '为什么', '如何理解', '试述', '试析']
    },
    '行测': {
        'core': ['行测', '行政职业能力测验', '数量关系', '资料分析', '判断推理',
                 '言语理解', '常识判断', '逻辑填空', '片段阅读', '行测真题'],
        'high': ['数量', '资料', '判断', '推理', '言语', '常识', '类比', '定义',
                 '增长率', '百分比', '数学运算', '排列组合', '概率', '数列',
                 '图形推理', '逻辑判断'],
        'normal': ['逻辑', '类比', '增长率', '百分比', '数学运算', '排列组合', '概率', '数列',
                   '中心理解', '词语理解', '语句表达']
    },
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

# 去重阈值统一由文件顶部常量 DEDUP_SIMILARITY_THRESHOLD(0.70) 定义，此处不再重复声明。

# 选项结构相似度权重（占综合得分的30%）
OPTION_STRUCTURE_WEIGHT = 0.30
# 内容相似度权重（占70%）
CONTENT_SIMILARITY_WEIGHT = 0.70


def _normalize_answer(answer: str) -> str:
    """标准化答案格式：去空格、去标点、统一大写、全角→半角"""
    if not answer:
        return ''
    # 全角字母 → 半角
    result = []
    for c in str(answer):
        code = ord(c)
        if 0xFF21 <= code <= 0xFF3A:  # 全角大写 A-Z
            result.append(chr(code - 0xFEE0))
        elif 0xFF41 <= code <= 0xFF5A:  # 全角小写 a-z
            result.append(chr(code - 0xFEE0))
        else:
            result.append(c)
    answer = ''.join(result)
    # 去空格、标点
    answer = re.sub(r'[\s,，、;；.\-—/|\\]', '', answer)
    # 去中文修饰词
    answer = re.sub(r'[对正确错误是否√×①②③④⑤⑥⑦⑧⑨⑩]', '', answer)
    # 只保留字母和数字
    letters = re.sub(r'[^A-Za-z0-9]', '', answer)
    return letters.upper()


def canonical_answer(answer: str) -> str:
    """
    答案归一化（单一事实来源，供答案提取/题型判定/读路径兜底共用）。

    - 全角字母/数字/符号 → 半角
    - 中文判断词映射：对/正确/是/√ → A，错/错误/否/× → B（按长度降序替换，避免子串误命中）
    - 去分隔符/空白/标点，统一大写，仅保留 [A-Z0-9]

    例：'A、B、C' → 'ABC'；'A B' → 'AB'；'对' → 'A'；'错误' → 'B'；'正确' → 'A'。

    注意：本函数面向客观题（单选/多选/判断）的字母答案归一化；
    论述/写作题的自由文本答案不应经此处理（会丢失正文）。
    """
    if not answer:
        return ''
    s = str(answer)
    # 1. 全角 → 半角
    s = ''.join(chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c for c in s)
    # 2. 中文判断词 → 字母（长词优先，避免 '错' 先于 '错误' 命中）
    cn_map_sorted = sorted(CN_ANSWER_MAP.items(), key=lambda kv: len(kv[0]), reverse=True)
    for cn, letter in cn_map_sorted:
        s = s.replace(cn, letter)
    # 3. 仅保留字母与数字（同时去除分隔符/空白/标点/残余中文）
    s = re.sub(r'[^A-Za-z0-9]', '', s)
    return s.upper()


def _extract_options_structure(text: str) -> str:
    """
    从题目内容中提取选项结构指纹。
    返回标准化选项字符串，用于结构相似度比较。
    """
    if not text:
        return ''
    # 提取 A/B/C/D 选项标记和选项首字
    option_pattern = re.compile(r'(?:^|\n)\s*([A-D])\s*[.、．)）]\s*(.{0,20})', re.MULTILINE)
    matches = option_pattern.findall(text)
    if not matches:
        return ''
    # 构建结构指纹：A:xxx|B:xxx|C:xxx|D:xxx
    structure_parts = []
    for key, val in matches:
        # 标准化：去空白、取前10字符
        clean_val = re.sub(r'\s+', '', val)[:10]
        structure_parts.append(f"{key}:{clean_val}")
    return '|'.join(structure_parts)


def _compute_option_similarity(text_a: str, text_b: str) -> float:
    """计算两段文本的选项结构相似度"""
    struct_a = _extract_options_structure(text_a)
    struct_b = _extract_options_structure(text_b)
    if not struct_a and not struct_b:
        return 0.0  # 都没有选项，结构上无差别
    if not struct_a or not struct_b:
        return 0.0  # 一个有选项一个没有，结构不同
    return SequenceMatcher(None, struct_a, struct_b).ratio()


def fuzzy_detect_duplicate(
    db_session,
    content: str,
    answer: str = '',
    subject_id: Optional[int] = None,
    threshold: float = DEDUP_SIMILARITY_THRESHOLD
) -> Tuple[bool, Optional[Any], float]:
    """
    增强版模糊去重检测。

    增强策略（v2）：
    1. 精确答案匹配（快速路径）
    2. 跨科目候选集构建（不限 subject_id，全局去重）
    3. 复合相似度计算：内容70% + 选项结构30%
    4. 答案归一化硬约束：相似度达标 + 答案必须匹配 → 才算重复
    5. 答案匹配时降低阈值到0.65（答案相同则更可能是同一题的不同版本）

    参数：
    - db_session: SQLAlchemy Session
    - content: 题目内容（题干）
    - answer: 答案（可选，用于精确匹配和硬约束）
    - subject_id: 科目ID（可选，设为None则跨科目检查）
    - threshold: 相似度阈值，默认 0.70

    返回：
    - (is_duplicate, matched_question, best_similarity)
    """
    from ..models.models import QuestionBank

    if not content:
        return False, None, 0.0

    normalized_input = normalize_text_for_comparison(content)
    normalized_answer = _normalize_answer(answer)

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

    # 第2步：构建候选集（跨科目检查）
    query = db_session.query(QuestionBank).filter(QuestionBank.status != 0)

    # 前缀匹配缩小候选范围
    content_prefix = content[:20] if len(content) > 20 else content
    candidates = query.filter(
        QuestionBank.question_content.like(content_prefix[:10] + '%')
    ).limit(800).all()

    # 补充：答案匹配但前缀不同的候选（捕获改写后的同一题目）
    if normalized_answer and len(candidates) < 200:
        more = query.filter(
            ~QuestionBank.question_id.in_(
                [c.question_id for c in candidates]
            ) if candidates else True
        ).limit(500).all()
        # 答案预筛选：匹配才加入
        for q in more:
            if _normalize_answer(q.answer or '') == normalized_answer:
                candidates.append(q)

    if len(candidates) < 50 and not normalized_answer:
        more = query.filter(
            ~QuestionBank.question_id.in_(
                [c.question_id for c in candidates]
            ) if candidates else True
        ).limit(500).all()
        candidates.extend(more)

    if not candidates:
        return False, None, 0.0

    # 第3步：逐条比对（复合相似度 + 答案硬约束）
    best_match = None
    best_composite_score = 0.0

    for q in candidates:
        q_content = q.question_content or ''
        q_normalized = normalize_text_for_comparison(q_content)
        if not q_normalized:
            continue

        # 快速过滤：长度差异过大直接跳过
        if len(normalized_input) > 0 and len(q_normalized) > 0:
            len_ratio = min(len(normalized_input), len(q_normalized)) / \
                        max(len(normalized_input), len(q_normalized))
            if len_ratio < 0.35:  # 长度差超过65%
                continue

        # 计算内容相似度
        content_score = SequenceMatcher(None, normalized_input, q_normalized).ratio()

        # 计算选项结构相似度（仅当双方都有选项时）
        option_score = _compute_option_similarity(content, q_content)

        # 复合得分：内容70% + 选项结构30%
        composite = content_score * CONTENT_SIMILARITY_WEIGHT + \
                    option_score * OPTION_STRUCTURE_WEIGHT

        if composite > best_composite_score:
            best_composite_score = composite
            best_match = q

            # 答案硬约束检查
            q_answer_normalized = _normalize_answer(q.answer or '')

            # 情况A：双方都有答案 → 答案必须匹配 + 复合得分≥threshold
            if normalized_answer and q_answer_normalized:
                if normalized_answer == q_answer_normalized:
                    # 答案相同 → 降低阈值到0.65
                    effective_threshold = min(threshold, 0.65)
                    if composite >= effective_threshold:
                        break
                # 答案不同 → 不算重复，继续寻找
                else:
                    best_match = None
                    best_composite_score = 0.0
                    continue

            # 情况B：仅一方有答案 → 使用原始阈值（无答案硬约束）
            elif composite >= threshold:
                break

    # 最终判定
    if best_match is None:
        return False, None, 0.0

    # 有答案时：答案必须匹配才算重复
    if normalized_answer and best_match.answer:
        q_ans = _normalize_answer(best_match.answer)
        if q_ans and normalized_answer != q_ans:
            return False, None, best_composite_score

    # 答案相同 → 更宽松的阈值（0.65）
    effective_threshold = threshold
    if normalized_answer and _normalize_answer(best_match.answer or '') == normalized_answer:
        effective_threshold = min(threshold, 0.65)

    is_dup = best_composite_score >= effective_threshold
    return is_dup, best_match, best_composite_score


# ============ 题号提取 ============

@dataclass
class QuestionNumber:
    """题号信息"""
    number: int          # 题号数值
    format_type: str     # 格式类型（cn_di, num_dot, paren, bracket, num_close_paren, bare_num）
    position: int        # 在文本中的起始位置
    line_index: int      # 行号（0-based）


def extract_question_numbers(text: str, exclude_paren_bracket: bool = False,
                             monotonic: bool = False) -> List[QuestionNumber]:
    """
    从文本中提取所有题号。
    每个位置只取第一个命中的格式（按优先级）。
    包含近邻去重逻辑。

    exclude_paren_bracket=True 时禁用 paren/bracket 两种"括号题号"格式。
    用途：答案解析文档中，真实题号是行首"1、"（num_dot）格式，而解析正文里的
    "（1）指引作用（2）评价作用…"子项序号会被 paren 模式误判为题号，
    导致答案块切分错乱、解析串题丢失（真实案例：2016多省联考答案解析 119个题号
    中 19 个是误判的子项序号，导致 7 题解析缺失）。

    monotonic=True 时，题号须严格单调递增（后一个 > 前一个）。用于答案解析：
    解析正文里的枚举序号（如"5.丢失枪支不报"出现在第 27 题正文中）会被 num_dot
    误判为题号 5，破坏第 27 题的块边界（"故正确答案为D"被截断归入错误块）。
    标准试卷答案的题号必然单调递增，正文枚举必然违反单调性，据此可精准过滤。
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
            if exclude_paren_bracket and fmt_name in ('paren', 'bracket'):
                continue
            m = pattern.search(line)
            if m:
                num = int(m.group(1))
                # 过滤异常值（现实试卷题号≤999；同时排除1900-2100等年份噪声，
                # 否则正文"2016 江西招警…"会被误判为题号导致分块腰斩——
                # 真实案例：2016江西答案解析PDF因此从100%跌至52.6%）
                if num <= 0 or num > 999:
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

        # monotonic 模式：题号须严格递增（后一个 > 前一个）。
        # 答案解析正文里的枚举序号（如"5.丢失枪支不报"出现在第27题中）违反递增性，过滤。
        if monotonic and results and num <= results[-1].number:
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

# ---- 高置信度答案声明（权威性优先，而非"位置最靠后优先"）----
#
# 背景（20 份真实语料实测出 17 处静默错答，3 类根因收敛于此）：
#   旧实现对所有答案模式一律取 matches[-1]（全文最后一个匹配）。
#   当 PDF 抽取把下一题的答案粘连进本块末尾时，末位恰好是"下一题的答案"；
#   当解析逐项点评 A/B/C/D 时，末位恰好是"最后一个干扰项字母"。
#
#   实例A（块边界滑动）2017多省联考题79：
#     块首 "## 79、正确答案是：C"   ← 本题权威声明
#     块尾 "…两抢犯罪数为12、正确答案是：B" ← 实为第80题（题号80在抽取中丢失）
#     旧逻辑取末位 → B（错）    新逻辑取块首 → C（对）
#
#   实例B（干扰项泄漏）2017国考题14：
#     "此题看似选D，因为…"（干扰项示范）… "故本题正确答案为C"（真答案）
#     旧逻辑取末位仍可能命中"看似选D" → D（错）
#
# 设计原则：**声明的权威性由"它是谁的声明"决定，不由"它出现在哪"决定。**
#   1) 题头声明（块首行，声明的就是本块这道题）—— 最高
#   2) 结论声明（"故正确答案为X"）—— 高，取最后一个且排除干扰项前缀
#   3) 其余原有模式 —— 保持原行为作为兜底，不改变既有解析结果
_BLOCK_HEADER_ANSWER_RE = re.compile(
    r'^\s*(?:#{1,6}\s*)?'
    r'(?:第\s*\d+\s*题|\d+\s*[、.．)）\]]\s*)?'   # 题号前缀可缺（题号可能已被上游剥离）
    r'(?:本题)?\s*(?:参考)?\s*(?:正确)?\s*答案'
    r'(?:是|为|选)?\s*[：:：]?\s*'
    r'([A-Da-d]{1,4})(?![A-Za-z])'
)

# 结论声明："故正确答案为C" / "因此本题选A"
_CONCLUSION_ANSWER_RE = re.compile(
    r'(?:故|因此|所以)\s*(?:本题|本问|该题)?\s*'
    r'(?:正确)?\s*(?:答案|选项)'
    r'(?:是|为|选)?\s*[：:：]?\s*'
    r'([A-Da-d]{1,4})(?![A-Za-z])'
)

# 干扰项提示前缀：紧贴答案字母前出现这些词时，该字母是"错误选项示范"而非答案
_DISTRACTOR_PREFIX_RE = re.compile(
    r'(?:看似|似选|似为|易选|易错|易误|误选|干扰|注意|而非|不是)\s*(?:选|为|是)?\s*$'
)


def _pick_conclusion_answer(full_text: str) -> Optional[str]:
    """从块内取最后一个"结论声明"作为答案，跳过干扰项前缀的假声明。

    返回归一化后的答案字母串；无有效结论声明时返回 None。
    """
    best = None
    for m in _CONCLUSION_ANSWER_RE.finditer(full_text):
        prefix = full_text[max(0, m.start() - 12):m.start()]
        if _DISTRACTOR_PREFIX_RE.search(prefix):
            continue  # "看似选D" 这类干扰项示范，跳过
        best = m
    if best is None:
        return None
    ans = canonical_answer(best.group(1))
    if ans and all(c in 'ABCD' for c in ans) and len(ans) <= 4:
        return ans
    return None


def extract_answer_from_lines(lines: List[str]) -> Dict[str, Optional[str]]:
    """
    从文本行中提取答案和解析。
    支持标准答案格式和嵌入式答案格式（如"故本题答案为D"）。

    答案优先级：题头权威声明 > 结论声明（排除干扰项） > 原有模式兜底。
    """
    full_text = '\n'.join(lines)

    # ===== 第零遍：题头权威声明（本块这道题的答案，优先级最高） =====
    # 只在块首行匹配。长度护栏：题头声明是一行短声明；
    # 若首行是长句（正文里顺带提到"答案是A"），则不算题头声明，交由后续结论判定。
    if lines:
        head = lines[0]
        if len(head.strip()) <= 40:
            mh = _BLOCK_HEADER_ANSWER_RE.match(head)
            if mh:
                raw = canonical_answer(mh.group(1))
                if raw and all(c in 'ABCD' for c in raw) and len(raw) <= 4:
                    # 解析 = 题头声明之后的剩余文本
                    rest = '\n'.join(lines[1:]).strip()
                    tail = head[mh.end():].strip()
                    if tail and len(tail) > 5:
                        rest = (tail + '\n' + rest).strip()
                    return {
                        'answer': raw,
                        'analysis': rest or None,
                        'format': 'block_header',
                    }

    # ===== 第零遍之二：结论声明（排除干扰项前缀） =====
    # 放在原有模式之前：逐项点评型解析里，"故正确答案为X"才是权威结论。
    concl = _pick_conclusion_answer(full_text)
    if concl:
        return {
            'answer': concl,
            'analysis': full_text,
            'format': 'conclusion',
        }

    # ===== 第一遍：标准答案格式 =====
    for fmt_name, pattern in ANSWER_PATTERNS:
        if fmt_name == 'range' or fmt_name == 'per_item':
            continue  # 这两个由专门的解析函数处理
        # 修复：取最后一个匹配，避免题干中"答案：A"干扰
        matches = list(pattern.finditer(full_text))
        if matches:
            m = matches[-1]
            # 归一化答案：A、B、C → ABC；对/正确 → A；错/错误 → B
            raw_answer = canonical_answer(m.group(1))

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
            raw_answer = canonical_answer(m.group(1))
            # 修复：支持多字母答案（如 ABCD），不再仅限单字母
            if raw_answer and all(c in 'ABCD' for c in raw_answer) and len(raw_answer) <= 4:
                # 整个文本块作为解析
                return {
                    'answer': raw_answer,
                    'analysis': full_text,
                    'format': f'embedded_{fmt_name}',
                }

    # 兜底：最后一行如果是孤立的大写字母串，视为答案
    for line in reversed(lines):
        stripped = line.strip()
        # 修复：加 + 量词，支持多字母答案（如 ABCD）
        if re.match(r'^[A-Da-d]+$', stripped):
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
            if all(c in "ABCD" for c in str(ans)):
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
        if all(c in "ABCD" for c in str(ans)):
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
            if all(c in "ABCD" for c in str(ans)):
                result[num] = {'answer': ans, 'analysis': None}

    # 模式4: 增强纯序列匹配（处理空格/逗号/换行/中文答案等分隔格式）
    if not result:
        # 传入题目数=0让函数不校验数量（纯序列模式不需要数量校验）
        result = _match_pure_sequence_enhanced(text, 0)
        # 如果按数量校验增强版没匹配到，放宽条件再试
        if not result:
            result = _match_pure_sequence_enhanced(text, 999)

    return result


def parse_answer_text_to_map(text: str) -> Dict[int, Dict[str, Optional[str]]]:
    """
    将答案文本解析为题号→答案的映射（主要策略）。

    流程：
    1. 提取题号位置（排除括号题号，避免解析正文"（1）（2）"子项序号误判）
    2. 按题号切分文本块
    3. 从每个文本块中提取答案和解析
    """
    numbers = extract_question_numbers(text, exclude_paren_bracket=True, monotonic=True)

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
            if ans and all(c in "ABCD" for c in str(ans)) and num not in seen:
                result[num] = {'answer': ans, 'analysis': None}
                seen.add(num)

    return result


# ============ 题目结构提取 ============

# 材料头行正则：X、请根据以下[情境/情景材料、资料、文章、图表]，回答Y-Z题
# 变体覆盖（18 份真实语料实测）：
#   "五、根据以下情境材料，回答86-89题。"     情境材料（原生支持）
#   "三、根据以下情景材料，回答78-81题。"     情景材料（首版遗漏 -> 4 题污染）
#   "八、请根据以下情景材料，回答90-93题。"  "请"前缀（首版遗漏）
#   "根据以下情境资料，回答71-73题。"         无中文数字章节号
# 关键：不用 $ 锚定 —— 实际语料中材料头常与材料正文挤在同一行
#（"...正确的有（ ）⏎三、根据以下情景材料，回答78-81题。2015年10月4日，某铁路局…"），
# 首版 $ 锚定要求独占一行，导致同行形态 100% 漏剥离。
_MATERIAL_HEAD_RE = re.compile(
    r'(?:^|\n)[ \t]*(?:[一二三四五六七八九十]+[ \t]*[、，．][ \t]*)?'
    r'(?:请)?(?:根据|阅读)(?:以下|下面)'
    r'(?:情境|情景)?(?:材料|资料|文章|图表|内容|案例)?'
    r'[^\n]{0,20}?回答[ \t]*(\d+)[ \t]*[-～~—－至][ \t]*(\d+)[ \t]*题'
)

# 题号行 / 选项行 / 图片标记行（用于判定材料正文边界）
_BOUNDARY_RE = re.compile(
    r'^(?:\d+\s*[.、．)）\]】]|[A-D]\s*[.、．)）]|\[IMAGE:)')

# ============ P2：分节指令段（题型说明段）识别 ============
# 真实语料实测（30 份 docx / 2899 题块，污染 20 道 = 0.7%）：
#   "二、多项选择题。请从每题的四个备选答案中，选出两个或两个以上的正确答案，多选、少选、错选均不得分。"
#   "三、情景分析题，根据给出的情境材料做出分析，按照提问要求选择正确答案。每题所设选项中至少有一个正确答案…"
#   "三、判断题。判断下列说法的正误。"
#   "二、多项选择题。按照提问选择正确答案，多选、少选、错选或不选均不得分。"
# 分节指令段与 _MATERIAL_HEAD_RE 认的"材料头"是两种东西：
#   材料头     → 后面接"回答 N-M 题"，指向具体题号区间
#   分节指令段 → 后面接"答题说明"，只是换题型的过渡语
# 历史实现只认前者，导致分节指令段整体粘连到上一题题干尾部，
# 并把下一节的首题材料一起吞掉（判断题整节消失由此而来）。
# 关键：同样不用 $ 锚定 —— 实际语料常与上一题的题干/图片挤在同一行。
_SECTION_TYPE_WORDS = (
    r'单项选择题|多项选择题|不定项选择题|不定项选择|单项选择|多项选择|'
    r'案例分析题|情景分析题|选择题|判断题|简述题|简答题|论述题|写作题|材料题'
)
_SECTION_DIRECTIVE_RE = re.compile(
    r'[一二三四五六七八九十]{1,3}\s*[、，．.]\s*'
    r'(?:' + _SECTION_TYPE_WORDS + r')'
    r'\s*[。．.、，]'
    r'[^\n]{0,150}?'
    r'(?:不得分|不评分|不扣分|判断下列|请选择|回答下列|按要求|最恰当|中选择|选择填)'
)


# 题号前缀（第N题 / 12. / 12、/ 12））——供 extract_question_blocks 去首行题号用
_QNUM_PREFIX_RE = re.compile(r'^(?:第\s*\d+\s*题|\d+\s*[.、．)）\]】])\s*')


def _find_section_directive(line: str):
    """在一行文本中定位分节指令段。返回 (起始下标, 结束下标, 匹配文本) 或 None。

    只认「中文数字序号 + 题型名 + 答题说明」的完整形态，避免把题干里
    正常出现的"一、""二、"列举误判成分节标记。

    必须同时给出**结束下标**：分节指令独占一行时，整行都该丢弃；
    与材料同行时，只有 end 之后的部分才是节首材料。用起始下标切会把
    指令本身回吐给下一题（等于污染搬家，没解决）。
    """
    m = _SECTION_DIRECTIVE_RE.search(line)
    if m:
        return m.start(), m.end(), m.group(0)
    return None


# 分节声明题型 → 标准题型名。
# 用于给"无选项题"提供题型依据：判断题在真题里常以"陈述句 +（  ）"呈现，
# 本身没有任何选项，若只看题块结构必然落到"简答题"兜底分支。
# 真实事故：2019 深圳辅警《公安素质测试》卷三、每题所设选项中至少有两个正确答案…／三、判断题。判断下列说法的正误。
# 第 81–90 题是标准判断题，却因 0 选项被判成"简答题"，随后答案抽取抓不到
# "故表述正确/错误"这种文字结论，退化成单字母兜底，被填入 C/D/D/B 假答案。
_SECTION_TYPE_MAP = (
    ('单项选择题', '单选题'),
    ('单项选择', '单选题'),
    ('多项选择题', '多选题'),
    ('不定项选择题', '多选题'),
    ('不定项选择', '多选题'),
    ('多项选择', '多选题'),
    ('判断题', '判断题'),
    ('案例分析题', '案例分析题'),
    ('情景分析题', '情景分析题'),
    ('简述题', '简答题'),
    ('简答题', '简答题'),
    ('论述题', '论述题'),
    ('写作题', '写作题'),
    ('材料题', '材料题'),
)


def _section_type_of(text: str) -> str:
    """从分节指令文本解析其声明的题型；未声明任何题型返回 ''。"""
    if not text:
        return ''
    for kw, ty in _SECTION_TYPE_MAP:
        if kw in text:
            return ty
    return ''


def _build_section_index(lines: List[str]) -> List[Tuple[int, str]]:
    """预扫描全部分节指令，返回按行号升序的 [(行号, 题型)]。

    必须在题块循环**之前**建好：分节标题行本身会被 P2 的
    _strip_trailing_material 从上一题尾部剥离掉，循环内已无从取到。
    """
    marks: List[Tuple[int, str]] = []
    for i, ln in enumerate(lines):
        hit = _find_section_directive(ln)
        if not hit:
            continue
        ty = _section_type_of(hit[2])
        if ty:
            marks.append((i, ty))
    return marks


def _section_type_at(marks: List[Tuple[int, str]], line_idx: int) -> str:
    """取行号 line_idx 之前最近一次分节声明的题型；无则返回 ''。"""
    ty = ''
    for idx, t in marks:
        if idx < line_idx:
            ty = t
        else:
            break
    return ty


def _strip_trailing_material(lines: List[str]) -> Tuple[List[str], List[str]]:
    """剥离题干块尾部粘连的「材料头」与「分节指令段」（分节残留）。

    返回 (保留的行, 溢出到下一题块的首行)：
    - 保留的行：属于本题的行
    - 溢出行：分节指令段之后、下一个题号行之前的"节首材料"（如情景分析的图表说明），
      它属于**下一节的第一题**，必须回吐给下一题块，否则下一题题干残缺。
      这正是"判断题整节消失"与"下一节首题只剩选项没有题干"的成因。

    真实案例 1（材料头）：第85题尾部混入"五、根据以下情境材料，回答86-89题。新生派出所位于老城区…"
    真实案例 2（分节指令）：第70题尾部混入"三、情景分析题，…（一）下图为甲县公安局的机构设置图。[IMAGE]"

    注意：仅剥离"位于块中后部"的分节标记（其前已有本题题干内容），
    保护复合题/题组题自身的开头材料句。
    """
    if not lines:
        return lines, []

    # ---- 定位首个分节标记（材料头 或 分节指令段），跳过首行（首行是题号行）----
    cut_idx = None      # 该行从 cut_char 起全部剥离
    cut_char = None
    cut_end = None      # 指令行保留 [cut_end:] 部分（同行材料）
    for i in range(1, len(lines)):
        m = _MATERIAL_HEAD_RE.search(lines[i])
        if m:
            cut_idx = i
            cut_char = m.start() + (1 if m.group(0).startswith('\n') else 0)
            # 材料头：整行剩余部分视为材料正文
            cut_end = cut_char
            break
        hit = _find_section_directive(lines[i])
        if hit:
            cut_idx, cut_char, cut_end = i, hit[0], hit[1]
            break
    if cut_idx is None:
        return lines, []

    keep = list(lines[:cut_idx])
    prefix = lines[cut_idx][:cut_char].rstrip()
    if prefix:
        keep.append(prefix)

    # ---- 从分节标记之后收集"节首材料" ----
    # 注意：块的右边界已由「下一题题号所在行」限定，因此分节指令之后的**所有**
    # 内容（含 [IMAGE:...] 与选项行）都属于下一节的首题，全部回吐。
    # 早期版本在 [IMAGE: 处 break，会把下一节首题的共享材料图直接丢掉。
    spill: List[str] = []
    tail = lines[cut_idx][cut_end:].strip()
    # 指令正则的 [^\n]{0,150}? 会在最后一个关键词处收尾，行尾常剩一个句号
    # 之类的孤立标点，它是指令的一部分而非节首材料，去掉。
    if tail and not re.fullmatch(r'[\s。，、；：,.;:!?！？]+', tail):
        spill.append(tail)
    spill.extend(lines[cut_idx + 1:])

    # 去掉溢出行首尾空行
    while spill and not spill[0].strip():
        spill.pop(0)
    while spill and not spill[-1].strip():
        spill.pop()
    return keep, spill


# ==================== 申论（Essay / 主观题）解析 ====================
# 设计约束（2026-10-01）：
#  1) 本段只做"增量"：新增函数 + 在 extract_question_blocks 入口加一个分支。
#     原有选择题切分逻辑（extract_question_numbers / monotonic / P2 回吐等）
#     一行都不改，确保公专/行测回归不受影响。
#  2) 非申论文档一律返回 None，走原路径 —— 这是行测/公测零影响的保证。
#  3) 申论文法实测要点（详见 .omo/plans/shenlun-import-precision-v4.md §2.5）：
#     · 安徽/多省联考卷：题号 = 半角 "1."；要求子项 = 全角 "（1）"
#     · 国考卷：题号 = 全角 "（1）"；要求子项同为全角，靠"含分值"区分
#     所以必须先判定题号样式，再决定切题正则。
#  4) 答案文档（分离型）自带完整题干 + 要求，可与题目文档做三方交叉校验；
#     校验不通过时 blocked=True，绝不"就近填充"，避免配对错位。

_ESSAY_SCORE_RE = re.compile(r'[（(]\s*(\d{1,3})\s*分\s*[）)]')
_ESSAY_REQ_LINE_RE = re.compile(r'^[ \t　]*[（(]\s*\d{1,2}\s*[）)]')
_ESSAY_REQ_MARK = '要求'
_ESSAY_ANS_ALONE_RE = re.compile(r'^[ \t　]*(?:[一二三四五六七八九十]+\s*、\s*)?参考答案[ \t　]*[:：]?[ \t　]*$', re.M)
_ESSAY_ANS_INLINE_RE = re.compile(r'参考答案[ \t　]*[:：](?!说明)')
# 答案区「段头」：一、（15 分）—— 2022 国考行政执法卷等用「中文序号 + 分值」标出每题答案起点。
# 必须与「参考答案」锚点区分：前者只切分段（cur=[]），后者才把整段正文纳入答案。
_ESSAY_ANS_SEG_RE = re.compile(
    r'^[ \t　]*[一二三四五六七八九十]{1,3}[ \t　]*[、.．]?[ \t　]*[（(][ \t　]*\d{1,3}[ \t　]*分[ \t　]*[）)]'
)


# 解析标记（同一段内「答案」与「解析」的分界，**不是**段起点）
# 全语料实测：127 份有答案区的文档中，94% 靠 `参考答案说明` 分隔，6% 无分隔。
_ESSAY_ANALYSIS_MARK_RE = re.compile(
    r'^[ \t　]*[【\[]?\s*(?:参考答案说明|答案说明|答案解析|试题解析|解析|思路方面|总体思路|'
    r'答题思路|思路分析)\s*[】\]]?\s*[：:]?'
)
# 「审题及答题思路」在双段式版式里属于**答案区开头的审题分析**，
# 后面紧跟的【参考答案】才是答案主体 —— 它不是段级解析标记，
# 若当解析分界会把答案主体整段落进 analysis（实测 Q3/Q4/Q5 串题即由此而来）。
_ESSAY_AUDIT_MARK_RE = re.compile(
    r'^[ \t　]*[【\[]?\s*(?:审题及答题思路|审题思路|审题分析)\s*[】\]]?\s*[：:]?')


def _essay_is_analysis_mark(ls: str) -> bool:
    """该行是否「解析起始标记」—— 归入 analysis，且**绝不能**当作段起点。

    ⚠️ 真实回归（实测 2019 国考省级卷 line 203/328/353）：`参考答案说明：…`
    被误当成新的答案段起点 → 一段答案被切成多段 → 尾段数与题目数不等 →
    整份卷误报 `answer_block_count_mismatch`，同时造成答案/解析内容互相吞并。
    """
    return bool(_ESSAY_ANALYSIS_MARK_RE.match(ls))


# 段起点：必须容忍 `【参考答案】` 的方括号包装。
# 实测 2019 国考省级卷 line 303 是 `2、【参考答案】`，line 328/353 是 `【参考答案】`，
# 旧正则只认裸 `参考答案` → 第 2 段起点漏识别 → 尾段 5 段只切出 4 段 →
# 第 2 题答案被并进第 1 段尾，进而在块级产出「Q1 含下一题分值/题干措辞」的串题。
_ESSAY_ANS_START_RE = re.compile(
    r'^[ \t　]*(?:[（(]?\s*(?:\d{1,2}|[一二三四五六七八九十]{1,3})\s*[）)]?\s*[、.．]?\s*)?'
    r'[【\[]?\s*(?:参考答案|答案)\s*[】\]]?\s*[：:]?'
    # 允许段起点行**带正文**：实测 2019 国考省级卷 line 303 的
    # `2、【参考答案】发展经济挖掘文化美化环境弘扬正气建设好新农村`
    # 段标记与答案正文同行，若要求行尾必须为空（`\s*$`）就会漏识别段起点，
    # 导致第 2 题答案并进第 1 段尾 → Q1/Q2 answer 含下一题分值与题干措辞 → 串题。
    r'\S'
)
# 带分值的纯段头：2022 行政执法卷 `一、（15 分）`
_ESSAY_ANS_SEG_BRACKET_RE = re.compile(
    r'^[ \t　]*[一二三四五六七八九十]{1,3}\s*[、.．]?\s*[（(]\s*\d{1,3}\s*分\s*[）)]'
)


def _essay_is_ans_anchor(ls: str) -> bool:
    """该行是否是答案区**段起点**（用于切分答案段）。

    覆盖全语料实测到的全部形态：
      · `参考答案` / `参考答案：` / `【参考答案】`（独立行）
      · `1、参考答案：` / `一、参考答案（F）`（编号）
      · `一、（15 分）`（纯分值段头）

    排除项（易错点）：
      · 解析标记（`参考答案说明` 等）是段内分界，不是段起点
      · 行中有实际正文内容的（如 `参考答案从"…`开头）不是段起点
    """
    if _essay_is_analysis_mark(ls):
        return False
    # ★ 无编号的 `【参考答案】` **不是**段起点。
    #   实测 2019 国考省级卷是「审题及答题思路 + 参考答案」双段式版式，
    #   答案区 5 题共出现 7 处"参考答案"字样：
    #     197 `1、参考答案：`      ← 段起点（题号1）
    #     303 `2、【参考答案】`    ← 段起点（题号2）
    #     319 `3、参考答案：`      ← 段起点（题号3）
    #     328 `【参考答案】`      ← **同题内**的答案主体，不是新题
    #     346 `4、参考答案：`      ← 段起点（题号4）
    #     353 `【参考答案】`      ← 同题内的答案主体
    #     361 `5、参考答案：`      ← 段起点（题号5）
    #   若把裸 `【参考答案】` 当段起点，7 段去配 5 题，按序配对整体错位
    #   → 后续题答案被贴到前面题上 → 串题。
    #   段起点必须带**题号或分值**；裸括号形式只作同段内标记。
    if re.match(r'^[ \t　]*[（(]?\s*(?:\d{1,2}|[一二三四五六七八九十]{1,3})\s*[）)]?\s*[、.．]?\s*'
                r'[【\[]?\s*(?:参考答案|答案)\s*[】\]]?\s*[（(]\s*[A-Za-z]\s*[）)]', ls):
        # ★ 带卷别后缀的「一、参考答案（H）」「参考答案（F）」**不是**段起点。
        #   实测 2021 国考副省级/地市级是「H/F 两套答案」版式：
        #     240 一、参考答案（H）  250 参考答案（F）
        #     259 二、参考答案（H）  267 参考答案（F）
        #     275 三、参考答案（H）  287 参考答案（F） ……
        #   5 道题共 10 处答案锚点。若每处都切段，10 段去配 5 题 → 段数不等 →
        #   5 题全部误报 `answer_block_count_mismatch`（阻断 30→35 的退步来源）。
        #   H/F 是同一题的两套参考答案，不是新题。
        #   判据：段起点必须带**中文/阿拉伯题号**，且不得带 (H)/(F) 这类卷别后缀。
        return False
    if re.match(r'^[ \t　]*[【\[]\s*(?:参考答案|答案)\s*[】\]]', ls):
        return False
    if _ESSAY_ANS_START_RE.match(ls) or _ESSAY_ANS_SEG_BRACKET_RE.match(ls):
        return True
    return bool(_ESSAY_ANS_ALONE_RE.match(ls) or _ESSAY_ANS_INLINE_RE.search(ls)
                or _ESSAY_ANS_NUMBERED_RE.match(ls) or _ESSAY_ANS_SEG_RE.match(ls))


def _essay_looks_like_question_number(line: str, style: str) -> bool:
    """该行是否是真题号行（用于答案段的段尾兜底）。

    复用 `_essay_split_questions` 的同一套判据：体例正则 + 「题号+分值同行」严格判据。
    ⚠️ 必须要求分值：答案正文里大量 `1.经济价值。 2.生态能力。` 这类分点，
    若只靠题号正则会把它们当成新题号，导致答案被切碎。
    """
    s = (line or '').strip()
    if not s or _essay_is_analysis_mark(s) or _essay_is_ans_anchor(s):
        return False
    m = _ESSAY_NUM_RES.get(style, _ESSAY_HALF_NUM_RE).match(s)
    if not m:
        return False
    return bool(_ESSAY_SCORE_RE.search(s))


def _essay_split_answer_analysis(seg_lines: List[str]) -> Tuple[List[str], List[str]]:
    """把一个答案段切成 (答案行, 解析行)。

    全语料实测的规则（优先级从高到低）：
      1. `参考答案说明` / `【参考答案说明】` / `思路方面` 等**解析标记**出现即切换到解析，
         该行**归入解析**（用户原话：答案为参考答案，答案解析为参考答案说明）。
      2. 解析标记之前的内容全部归入答案。
      3. 段内无解析标记时，解析留空 —— 绝不把答案当解析（6% 的文档本就无分界）。

    返回 ([答案行], [解析行])，两者都不含解析标记行本身。
    """
    ans_lines: List[str] = []
    ana_lines: List[str] = []
    seen_mark = False
    for l in seg_lines:
        if _essay_is_analysis_mark(l):
            if not seen_mark:
                seen_mark = True
            # 解析标记行的正文（如"本参考答案从…五个方面"）归入解析
            body = _ESSAY_ANALYSIS_MARK_RE.sub('', l).strip()
            if body:
                ana_lines.append(body)
            continue
        (ana_lines if seen_mark else ans_lines).append(l)
    # ===== 去重校验：答案与解析不得包含对方=====
    # 用户原话：「不能区分答案和答案解析，导致答案解析为空」
    # 以及实测截图里 `参考答案说明` 同时出现在 answer 与 analysis 两处。
    # 根因是按解析标记切分时，若标记行之后又出现答案正文（或标记本身被
    # 两侧同时收下），同一段文字会落进两个字段。
    # 规则：以**先切出的部分**为准，另一侧若是其子串则置空，绝不两边都留。
    if ans_lines and ana_lines:
        _a_norm = re.sub(r'\s+', '', '\n'.join(ans_lines))
        _n_norm = re.sub(r'\s+', '', '\n'.join(ana_lines))
        # 解析是答案的子串 → 说明文字被重复收下，以答案为准
        if _n_norm and _n_norm in _a_norm:
            ana_lines = []
        # 答案是解析的子串 → 答案被误并入解析，以解析为准
        elif _a_norm and _a_norm in _n_norm:
            ans_lines = []
    return ans_lines, ana_lines
_ESSAY_ANS_NUMBERED_RE = re.compile(r'^[一二三四五六七八九十]+\s*、\s*参考答案\s*[（(]?\s*([HFhf])?\s*[）)]?', re.M)
_ESSAY_ANSNOTE_RE = re.compile(r'参考答案说明\s*[:：]?')
_ESSAY_MATERIAL_ANCHOR_RE = re.compile(
    r'^[ \t　]*(?:[一二三四五六七八九十]+\s*、\s*)?给定(?:材料|资料)[ \t　]*$')
_ESSAY_NOISE_RE = re.compile(r'^[ \t　]*(?:[一二三四五六七八九十]+\s*、\s*)?注意事项[ \t　]*$')
_ESSAY_MATERIAL_BLOCK_RE = re.compile(r'^[ \t　]*材料\s*(\d+)[ \t　]*$')
# 半角题号：安徽/多省联考体
_ESSAY_HALF_NUM_RE = re.compile(r'^[ \t　]*(\d{1,2})\s*[.．、](?![\d])[ \t　]*\S')
# 全角阿拉伯题号：国考体
_ESSAY_FULL_NUM_RE = re.compile(r'^[ \t　]*[（(]\s*(\d{1,2})\s*[）)][ \t　]*\S')
# 全角中文数字题号：2018 地市级等卷的「（一）（二）」体例
_ESSAY_CN_NUM_RE = re.compile(r'^[ \t　]*[（(]\s*([一二三四五六七八九十]+)\s*[）)][ \t　]*\S')
# 「问题一：」体例：2022 国考行政执法卷等
_ESSAY_WORD_NUM_RE = re.compile(r'^[ \t　]*问\s*题\s*([一二三四五六七八九十]+)\s*[：:][ \t　]*\S')
_CN_DIGITS = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
# 要求特征词（用于全角体下把"要求子项"从"题号"里排除）
_ESSAY_REQ_WORDS = (
    '准确全面', '准确、全面', '恰当提炼', '不超过', '紧扣资料', '条理清晰',
    '内容具体', '语言流畅', '逻辑清晰', '观点明确', '自选角度', '字数',
    '全面、准确', '分析全面', '对策得当', '针对性强', '言之有理', '不超过',
)
_ESSAY_VALID_TYPES = ('简答题', '论述题', '写作题', '简述题', '议论文/写作')


def _essay_norm_fp(s: str) -> str:
    """题干指纹：去所有空白与标点，仅留文字与数字，用于跨文档比对同一题。"""
    return re.sub(r'[\s　·．.、,，;；:：!！?？\'"“”‘’()（）《》<>\[\]【】—\-]', '', s or '')


def _essay_find_score(seg: str):
    """取一段文本里的分值；同一题内分值可能重复出现（题干 + 要求各一次），
    取首个即可 —— 不做求和，避免 2022 行政执法卷那类"10 个锚点/5 题"的误算。"""
    m = _ESSAY_SCORE_RE.search(seg or '')
    return int(m.group(1)) if m else None


def _essay_cn_to_int(s: str) -> int:
    """中文数字转阿拉伯（仅需 1..10，申论题号不会更大）。"""
    s = (s or '').strip()
    if not s:
        return 0
    if s == '十':
        return 10
    if len(s) == 1:
        return _CN_DIGITS.get(s, 0)
    if len(s) == 2 and s[0] == '十':
        return 10 + _CN_DIGITS.get(s[1], 0)
    if len(s) == 2 and s[1] == '十':
        return _CN_DIGITS.get(s[0], 0) * 10
    if len(s) == 3 and s[1] == '十':
        return _CN_DIGITS.get(s[0], 0) * 10 + _CN_DIGITS.get(s[2], 0)
    return 0


_ESSAY_NUM_RES = {
    'half': _ESSAY_HALF_NUM_RE,
    'full': _ESSAY_FULL_NUM_RE,
    'cn': _ESSAY_CN_NUM_RE,
    'word': _ESSAY_WORD_NUM_RE,
}


def _essay_questions_floor(lines: List[str]) -> int:
    """返回「作答要求区」起始行号；题号候选必须落在该行之后。

    合订本开头是「一、注意事项」，其中的 "1. 2. 3." 会被半角正则命中。
    实测（2022 国考地市级卷）：注意事项占 line 3-11，真题在 line 239 之后，
    不设下界就会把 6 条注意事项当成前 6 题。用作答要求锚点/材料锚点做下界即可隔离。
    """
    for i, ln in enumerate(lines):
        s = ln.strip()
        if re.match(r'^[一二三四五六七八九十]+\s*、\s*作答要求', s):
            return i
        if s.startswith('作答要求'):
            return i
    # 无「作答要求」标题时，退回用材料锚点（材料区之后的才是题目）
    for i, ln in enumerate(lines):
        if _ESSAY_MATERIAL_ANCHOR_RE.match(ln.strip()):
            # 从材料区往后找第一道题（材料块标题行不算），这里直接返回锚点行，
            # 由分值窗口进一步过滤
            return i
    return 0


def _detect_essay_numbering(lines: List[str]) -> Optional[str]:
    """判定题号样式：'half'（1.）/ 'full'（（1））/ 'cn'（（一））/ None。

    判据分两级，**严格级优先**：
      严格级：题号与分值标记在**同一行**。这是最精确的信号 ——
        安徽卷 "1. 根据“给定资料1”，请谈谈E县…（15分）"
        国考卷 "（1）根据“给定资料1”，对调研组的调研材料…（15 分）"
        而要求子项 "（1）准确全面；" 与答案分点 "1. 创新项目落地机制。"
        所在行都不含分值，故不会被误判。
      宽松级：题号行下方 5 行窗口内出现分值。仅当严格级一个都没命中时才启用，
        用于兜住那些分值被 PDF 换行拆到下一行的卷。

    ⚠️ 宽松级单独使用会造成严重误判（实测 2023 安徽B卷）：
      要求子项 "（1）准确全面；"（line 149）下方 5 行内含下一题的 "（25分）"（line 152），
      会被当成题号 → 3 道真题只切出 3 个"要求子项"块，真题全丢。
    """
    floor = _essay_questions_floor(lines)
    res = _ESSAY_NUM_RES

    def _scan(strict: bool) -> Dict[str, int]:
        tally = {style: 0 for style in res}
        for idx in range(floor, len(lines)):
            s = lines[idx].strip()
            if not s:
                continue
            if strict:
                scope = lines[idx]          # 仅本行
            else:
                scope = '\n'.join(lines[idx:idx + 5])
            if not _ESSAY_SCORE_RE.search(scope):
                continue
            for style, rx in res.items():
                m = rx.match(s)
                if not m:
                    continue
                if style == 'cn' and not _essay_cn_to_int(m.group(1)):
                    break
                tally[style] += 1
                break
        return tally

    tally = _scan(True)
    if max(tally.values()) > 0:
        return max(tally.items(), key=lambda kv: kv[1])[0]
    tally = _scan(False)
    return max(tally.items(), key=lambda kv: kv[1])[0] if max(tally.values()) > 0 else None


def _essay_split_questions(lines: List[str], style: str):
    """按判定出的题号样式切出 (题号, 行号, 卷别标记) 列表。

    两道硬约束：
      1) 分值校验（严格级：题号同行含分值；本函数沿用宽松窗口，
         但由于体例已由严格级确定，误判概率大幅降低）
      2) 题号必须严格递增（monotonic）—— 申论题号天然 1..N 递增，
         任何重复或回退都说明该候选不是真题号
    """
    num_re = _ESSAY_NUM_RES.get(style, _ESSAY_HALF_NUM_RE)
    floor = _essay_questions_floor(lines)
    raw = []
    for i in range(floor, len(lines)):
        m = num_re.match(lines[i])
        if not m:
            continue
        window = '\n'.join(lines[i:i + 5])
        if not _ESSAY_SCORE_RE.search(window):
            continue
        if style in ('cn', 'word'):
            qno = _essay_cn_to_int(m.group(1))
        else:
            qno = int(m.group(1))
        if qno <= 0:
            continue
        variant = ''
        mv = re.search(r'[（(]\s*([HFhf])\s*[）)]', lines[i])
        if mv:
            variant = mv.group(1).upper()
        raw.append((qno, i, variant))

    pruned: List[Tuple[int, int, str]] = []
    last = 0
    for qno, idx, variant in raw:
        if qno > last:
            pruned.append((qno, idx, variant))
            last = qno
    return pruned


def _essay_collect_materials(lines: List[str], q_start: int):
    """抽取材料正文（给定材料锚点 ~ 第一个题号行）与材料小标题列表。"""
    anchor = None
    for i in range(min(q_start, len(lines))):
        if _ESSAY_MATERIAL_ANCHOR_RE.match(lines[i].strip()):
            anchor = i
            break
    if anchor is None:
        return None, []
    blocks = []
    for i in range(anchor, q_start):
        m = _ESSAY_MATERIAL_BLOCK_RE.match(lines[i].strip())
        if m:
            blocks.append((int(m.group(1)), i))
    body = '\n'.join(lines[anchor:q_start]).strip()
    # 去掉锚点行本身
    body = re.sub(r'^[ \t　]*(?:[一二三四五六七八九十]+\s*、\s*)?给定(?:材料|资料)[ \t　]*\n', '', body)
    titles = ['材料%d' % n for n, _ in blocks]
    return (body or None), titles


def _essay_is_requirement_run(block_lines: List[str], start: int, style: str) -> bool:
    """判断 start 行起是否为"要求子项序列"。硬判据：整段无分值标记。"""
    seg = '\n'.join(block_lines[start:])
    return not _ESSAY_SCORE_RE.search(seg)


def _parse_essay_document(text: str) -> Optional[List[Dict[str, Any]]]:
    """申论文档 → 题目块列表；非申论体例返回 None。

    返回的块在原有键之外新增：
      requirements    要求清单（list[str]）
      material_text   共享材料全文（仅第一块携带，避免重复占用内存）
      material_titles 材料小标题列表（仅第一块）
      low_confidence  题干指纹是否未能对齐
      blocked         是否存在阻断性问题（映射不可信）
      block_reasons   阻断原因列表
    """
    lines = text.split('\n')
    style = _detect_essay_numbering(lines)
    if style is None:
        return None

    # 锚点门槛：至少命中 2 个申论特征才认定为申论（材料锚点 / 题号 / 答案锚点）
    hits = 0
    if any(_ESSAY_MATERIAL_ANCHOR_RE.match(l.strip()) for l in lines):
        hits += 1
    if _essay_split_questions(lines, style):
        hits += 1
    if (_ESSAY_ANS_ALONE_RE.search(text) or _ESSAY_ANS_INLINE_RE.search(text)
            or _ESSAY_ANS_NUMBERED_RE.search(text)):
        hits += 1
    if hits < 2:
        return None

    numbers = _essay_split_questions(lines, style)
    if not numbers:
        return None

    material_text, material_titles = _essay_collect_materials(lines, numbers[0][1])

    # ---- 形态①判定：全部答案锚点都落在「最后一个题号之后」→ 文末统一答案区 ----
    # 合订本（2018/2019/2020/2022 国考真题卷及答案）把 5 份参考答案集中放在
    # 文末，此时「就地配对」找不到每题的答案，必须改为按序切分答案区再顺序配对。
    # 形态②③（分离型答案 PDF）答案紧随各题，就地配对即可。
    last_q_line = numbers[-1][1]

    def _first_anchor_pos(from_line: int) -> Optional[int]:
        for i in range(from_line, len(lines)):
            if _essay_is_ans_anchor(lines[i].strip()):
                return i
        return None

    tail_anchor = _first_anchor_pos(last_q_line)
    # 最后一个题号之前完全没有答案锚点 → 认定为形态①
    head_anchor = _first_anchor_pos(0)
    head_has_answer = head_anchor is not None and head_anchor < last_q_line
    trailing_block = (tail_anchor is not None) and not head_has_answer

    # 形态①：把文末答案区按答案锚点切成 N 段，与题目按序一一对应
    trailing_segments: List[List[str]] = []
    if trailing_block:
        tail_lines = lines[tail_anchor:]
        cur: List[str] = []
        started = False
        for l in tail_lines:
            is_anchor = _essay_is_ans_anchor(l.strip())
            # ★ 段尾兜底：答案段内若出现**下一个题号行**，立即截断。
            #   这是串题的最终保险 —— 无论段起点正则是否漏识别形态，
            #   都不允许一个答案段跨越到下一题。
            #   实测 2019 国考省级卷 line 303 是 `2、【参考答案】`：
            #   段起点漏识别 → 第2题答案并进第1段尾 → Q1/Q2/Q3 的 answer 里
            #   出现下一题的分值与题干措辞 → 串题。
            #   有题号兜底后，即使段起点漏了，内容也不会越界到下一题。
            if started and cur and _essay_looks_like_question_number(l, style):
                trailing_segments.append(cur)
                cur = [l]
                continue
            if is_anchor:
                if started and cur:
                    trailing_segments.append(cur)
                cur = []
                started = True
                continue
            if started:
                cur.append(l)
        if started and cur:
            trailing_segments.append(cur)

    blocks: List[Dict[str, Any]] = []
    for k, (qno, sline, _variant) in enumerate(numbers):
        eline = numbers[k + 1][1] if k + 1 < len(numbers) else len(lines)
        raw = lines[sline:eline]
        seg = '\n'.join(raw)

        answer_txt = analysis_txt = ''
        if trailing_block:
            # 按序配对：第 k 题取第 k 段；段数不足则留空并阻断，绝不越界取用
            if k < len(trailing_segments):
                    # 统一走权威切分：解析标记归解析，且不再误命中正文里的"参考答案"
                    _ans_l, _ana_l = _essay_split_answer_analysis(trailing_segments[k])
                    answer_txt = '\n'.join(_ans_l).strip()
                    analysis_txt = '\n'.join(_ana_l).strip()
            stem_and_req = seg
        else:
            # 形态②③：就地配对（题号之后、下一个题号之前找答案锚点）
            ans_pos = None
            for off, l in enumerate(raw):
                if _essay_is_ans_anchor(l.strip()):
                    ans_pos = off
                    break
            stem_and_req = seg
            if ans_pos is not None:
                stem_and_req = '\n'.join(raw[:ans_pos])
                ans_body = raw[ans_pos + 1:]
                # 统一走权威切分：解析标记归解析（用户原话：答案为参考答案，
                # 答案解析为参考答案说明），且不会把答案正文里的"该条参考答案为：…"
                # 误当成解析起点（旧 `_ESSAY_ANSNOTE_RE.search` 就会误命中）。
                _ans_l, _ana_l = _essay_split_answer_analysis(ans_body)
                answer_txt = '\n'.join(_ans_l).strip()
                analysis_txt = '\n'.join(_ana_l).strip()

        # --- 题干 / 要求 拆分 ---
        req_at = None
        req_inline = ''
        for j, l in enumerate(stem_and_req.split('\n')):
            if l.strip().startswith(_ESSAY_REQ_MARK):
                req_at = j
                # 要求内容可能与「要求：」同行（实测 2022 国考行政执法卷：
                #   "　　要求：全面、准确、有条理。不超过250 字。"），必须先摘掉前缀取正文，
                # 否则只取后续行会把内容整段丢掉，导致 requirements 为空。
                req_inline = re.sub(
                    r'^[ \t　]*' + re.escape(_ESSAY_REQ_MARK) + r'[ \t　]*[：:]?[ \t　]*',
                    '', l).strip()
                break
        if req_at is None:
            stem = stem_and_req.strip()
            requirements: List[str] = []
        else:
            sl = stem_and_req.split('\n')
            stem = '\n'.join(sl[:req_at]).strip()
            collected: List[str] = []
            if req_inline:
                collected.append(req_inline)
            for l in sl[req_at + 1:]:
                t = l.strip()
                if _ESSAY_REQ_LINE_RE.match(t):
                    collected.append(t)
            # 纯文本要求（无「（1）」编号）没有子项行，整段作为一条要求保留，
            # 绝不能因为缺少编号就把要求丢掉——要求是申论题的采分点依据。
            requirements = collected
        # 去掉题干里的题号前缀
        stem = re.sub(r'^[ \t　]*(?:\d{1,2}\s*[.．、]|[（(]\s*\d{1,2}\s*[）)])[ \t　]*', '', stem).strip()

        score = _essay_find_score(stem_and_req)
        reasons: List[str] = []
        low_conf = False
        if not score:
            reasons.append('missing_score')
        # 形态①按序配对时，答案段数必须与题目数一致，否则说明有一段答案缺失或多出，
        # 此时不能靠"顺序第 k 段"盲取，必须阻断交人工核对。
        if trailing_block and len(trailing_segments) != len(numbers):
            reasons.append('answer_block_count_mismatch')
        blk: Dict[str, Any] = {
            'question_number': str(qno),
            'content': stem,
            'options': [],
            'answer': answer_txt,
            'analysis': analysis_txt,
            'requirements': requirements,
            'question_type': '简答题',
            'type_confidence': 0.9,
            'format': 'essay',
            'low_confidence': low_conf,
            'blocked': bool(reasons),
            'block_reasons': reasons,
            'score': score if score else 1,
            'suspicious': False,
        }
        blocks.append(blk)

    if blocks:
        blocks[0]['material_text'] = material_text
        blocks[0]['material_titles'] = material_titles
        for i, b in enumerate(blocks):
            b['group_id'] = 0
            b['question_level'] = 2 if len(blocks) > 1 else 1
            b['sort_order'] = i + 1
    return blocks


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
    # ---- 申论分支（2026-10-01）：非申论文档返回 None，此处行为与改动前完全一致 ----
    _essay_blocks = _parse_essay_document(text)
    if _essay_blocks is not None:
        return _essay_blocks
    # monotonic=True：题目文档题号同样必须严格递增。
    # 真实案例（2017国考第100题）："（1）附近居民（2）维持现场秩序的民警（3）媒体报道的人
    # （4）参与应急的消防人员"是"安全撤离顺序"题的**被打乱子项编号**（A-D 选项引用
    # 这四个序号），却被 paren 模式误判为第1~4题，凭空造出 4 道幽灵题，
    # 同时把真题 1~4 挤成重题号。子项序号（1~4）必然小于当前题号（100），
    # 违反单调性，据此精准过滤。
    numbers = extract_question_numbers(text, monotonic=True)
    if not numbers:
        return []

    lines = text.split('\n')
    blocks = []
    # P2 回吐缓冲区：上一题剥离出的"节首材料"暂存于此，下一轮作为本题前缀
    pending_spill: List[str] = []
    # 分节题型索引：必须在循环外预扫描。分节标题行会被 P2 从上一题尾部剥离，
    # 循环内取不到；而"无选项题"的题型判定又恰恰只能依赖它。
    section_marks = _build_section_index(lines)

    for i, qn in enumerate(numbers):
        start_line = qn.line_index
        if i + 1 < len(numbers):
            end_line = numbers[i + 1].line_index
        else:
            end_line = len(lines)

        raw_block = lines[start_line:end_line]

        # ---- 步骤 1：去掉首行题号前缀（只改首行，其余行原样）----
        # 注意 first_nl 是在 block_text 上取的偏移，因此切片也必须在 block_text 上做。
        # 早期版本拿 block_text 的偏移去切 block_text[m.end():] 得到的子串，
        # 偏移错位 m.end() 个字符，首行末尾会多出 "\n[I" 之类的垃圾。
        block_text = '\n'.join(raw_block)
        m = _QNUM_PREFIX_RE.match(block_text)
        if m:
            first_nl = block_text.find('\n')
            if first_nl < 0:
                block_lines = [block_text[m.end():]]
            else:
                head = block_text[m.end():first_nl]
                block_lines = ([head] if head.strip() else []) \
                    + block_text[first_nl + 1:].split('\n')
        else:
            block_lines = list(raw_block)

        # ---- 步骤 2：剥离题干尾部粘连的分节标记（材料头 + 分节指令段）----
        # 返回 (保留行, 溢出行)。溢出的节首材料留给下一题。
        block_lines, pending_spill = _strip_trailing_material(block_lines)

        # ---- 步骤 3：由剥离后的行**重算**题干，再前置回吐内容 ----
        # ★ 必须在剥离之后重算 content_text。早期版本在步骤 1 就把 content_text
        #   定死，步骤 2 剥离后没有重算，导致 content_text 仍是未剥离的原文 ——
        #   分节指令段照样留在题干里，污染"看起来一点没变"。
        content_text = '\n'.join(block_lines)
        spill_text = '\n'.join(pending_spill).strip()
        pending_spill = []
        if spill_text:
            content_text = f'{spill_text}\n{content_text}'.strip()
        block_text = '\n'.join(block_lines)

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

        # P0-fix: 图片选择题（选项是图片本身，文字无 A/B/C/D）。
        # 题干含图片指向词 + 含 IMAGE 占位 + 无文字选项 → 生成占位选项"见图"，
        # 保留图片，避免前端显示"选项缺失"。
        # 关键词覆盖实测语料：图标/示意图/下图/如图/图中/图表/看图（图示）/标志/标识/图形/图片。
        # 真实案例：2017国考题45"下列图示中，不属于法定特种车辆的是"、2018多省题69
        # "在下列交通标志的区域中…可以停车的有"——"图示""标志"是最高频的两种表述，
        # 首版关键词表遗漏导致 20 道图片选择题被判为"选项缺失"。
        if (not options or len(options) < 2) and re.search(r'\[IMAGE:', content_text):
            if re.search(
                r'图标|示意图|下图|如图|图中|图表|看图|图示|标志|标识|图形|图片|'
                r'如上图|如下图所示|所示',
                content_text,
            ):
                options = [
                    {'key': 'A', 'value': '（见图）'},
                    {'key': 'B', 'value': '（见图）'},
                    {'key': 'C', 'value': '（见图）'},
                    {'key': 'D', 'value': '（见图）'},
                ]

        # 提取内联答案
        extracted = extract_answer_from_lines(block_lines)
        answer = extracted.get('answer') if extracted else None
        analysis = extracted.get('analysis') if extracted else None

        # 检测题型（传入 answer 支持多字母答案检测；section_hint 提供分节声明的题型）
        section_hint = _section_type_at(section_marks, start_line)
        qtype, type_confidence = _detect_question_type(content_text, options, answer or '', section_hint)

        # ============ P4：剥离文末推广图/二维码 ============
        # 真实事故（2019 新疆兵团卷第 90 题，末题）：
        #   [IMAGE:72648561_90_0] [IMAGE:72648561_90_1]
        # 挂在最后一题尾部，是文档末尾的推广二维码。它们过不了二维码解码
        # （印刷模糊/带 logo），image_filters 的 block 级规则漏过。
        # 位置规则与内容规则正交：**文末区间的图片无论能否解码一律丢弃**。
        if i == len(numbers) - 1:
            content_text = _strip_trailing_images(content_text)

        blocks.append({
            'question_number': qn.number,
            'content': content_text.strip(),
            'options': options,
            'answer': answer,
            'analysis': analysis,
            'question_type': qtype,
            'type_confidence': type_confidence,
            'format': qn.format_type,
        })

    return _mark_and_split_suspected(blocks)


# 行首题号（用于检测题块内部是否混入其他题号）
# 必须带 MULTILINE：findall 逐块扫描正文时，^ 需匹配每一行行首而非仅整段开头
_INNER_QN_LINE = re.compile(r'^\s*(\d{1,3})\s*[．.、]', re.M)


def _mark_and_split_suspected(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """串题检测：标记可疑（主）+ 自动二次切分（辅）。

    背景
    ----
    PDF 曾因 ``extract_tables()`` 与 ``extract_text()`` 重复拼接导致全文翻倍，
    单调性过滤丢弃了重复题号却把重复文本留在题块内 → 一道题吞掉后续多道题。
    该根因已在上游修复，但历史脏数据、以及其他成因（如答案段混入正文）
    仍可能产生「块内含多个题号」的题块，必须在切分层兜底。

    策略（按用户决策：以标记可疑为主）
    ----------------------------------
    1. **主**：任何块内出现除自身以外的题号，一律打 ``suspicious=True`` 并写明原因，
       交由教师在预览页用「逐题删除」处理 —— 宁可标记，也不错切。
    2. **辅**：仅当内部题号**严格递增且互不重复**、且首行恰为本块自身题号时，
       才自动二次切分。条件不满足则只标记、不动内容。

    为什么不放宽 monotonic
    ----------------------
    ``extract_question_numbers(monotonic=True)`` 的单调性是防止「答案段题号被
    误当作新题」的关键（曾有 2017 国考第 100 题幽灵题的教训）。放宽会重引入该缺陷。

    Returns
    -------
    切分后的题块列表（顺序与输入一致，可能因二次切分而变长）
    """
    if not blocks:
        return blocks

    out: List[Dict[str, Any]] = []
    for b in blocks:
        content = b.get('content') or ''
        qn = b.get('question_number')
        qn_txt = str(qn) if qn is not None else None
        inner = _INNER_QN_LINE.findall(content)
        others = [q for q in inner if q != qn_txt]
        if not others:
            b.setdefault('suspicious', False)
            out.append(b)
            continue

        uniq_others = sorted({int(q) for q in others})
        b['suspicious'] = True
        b['suspicious_reason'] = (
            f"块内混入 {len(uniq_others)} 个其他题号: {uniq_others[:8]}"
        )

        # --- 辅策略：安全条件下自动二次切分 ---
        nums = [int(q) for q in inner]
        qn_int: Optional[int] = None
        if qn is not None:
            try:
                qn_int = int(qn)
            except (TypeError, ValueError):
                qn_int = None
        safe = (
            qn_int is not None
            and len(set(nums)) == len(nums)
            and all(nums[i] < nums[i + 1] for i in range(len(nums) - 1))
            and bool(nums)
            and nums[0] == qn_int
        )
        if not safe:
            out.append(b)
            continue

        lines_c = content.split('\n')
        positions: List[tuple] = []
        for i, ln in enumerate(lines_c):
            m = _INNER_QN_LINE.match(ln)
            if m:
                positions.append((i, int(m.group(1))))
        subs: List[Dict[str, Any]] = []
        for k, (li, sq) in enumerate(positions):
            end = positions[k + 1][0] if k + 1 < len(positions) else len(lines_c)
            seg = '\n'.join(lines_c[li:end]).strip()
            if not seg:
                continue
            sub_opts = _extract_options([str(x) for x in seg.split('\n')])
            subs.append({
                'question_number': sq,
                'content': seg,
                'options': sub_opts,
                'answer': None,          # 答案/解析需在匹配阶段重新归属
                'analysis': None,
                'question_type': None,
                'type_confidence': 0.0,
                'format': b.get('format'),
                'suspicious': False,
                'recovered_from': qn,     # 记录来源题块，便于回溯
            })
        if len(subs) >= 2:
            b['suspicious'] = True
            b['suspicious_reason'] += f"；已自动二次切分为 {len(subs)} 个子题"
            b['split_into'] = [s['question_number'] for s in subs]
            out.extend(subs)
        else:
            out.append(b)

    return out


# [IMAGE:xxx] 占位符
_IMAGE_MARKER_RE = re.compile(r'\[IMAGE:[^\]\s]+\]')
# A/B/C/D 选项行（行首）
_OPTION_LINE_RE = re.compile(r'^\s*[A-H]\s*[.、．)）]')


def _strip_trailing_images(content: str) -> str:
    """剥离**最后一道题**题干中、位于最后一个选项行之后的图片占位符。

    判定依据（结构性而非猜测）：
      - 该题是全文最后一块，其后不再有任何题号
      - 图片标记出现在最后一个 A-H 选项行之后
    → 说明这些图不属于题目本身，而是文档页尾的推广位/二维码。

    正常题目的图片都在选项行**之前**（题干图），不受影响。
    真实案例："[IMAGE:72648561_90_0] [IMAGE:72648561_90_1]"
    """
    if not content or '[IMAGE:' not in content:
        return content
    lines = content.split('\n')
    last_opt = -1
    for i, ln in enumerate(lines):
        if _OPTION_LINE_RE.match(ln):
            last_opt = i
    if last_opt < 0:
        # 没有可识别的选项行 → 无法用结构判断，保守不动
        return content
    for i in range(len(lines) - 1, last_opt, -1):
        if _IMAGE_MARKER_RE.search(lines[i]):
            lines[i] = _IMAGE_MARKER_RE.sub('', lines[i]).rstrip()
    return '\n'.join(lines)


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


# ============ 题型归一化映射 ============

# 仅保留4种标准类型：单选题、多选题、论述题、写作题
VALID_QUESTION_TYPES = ['单选题', '多选题', '论述题', '写作题']

# 旧类型 → 新标准类型映射
TYPE_NORMALIZE_MAP = {
    '单选题': '单选题', '选择题': '单选题', '单选': '单选题',
    '多选题': '多选题', '不定项': '多选题', '多选': '多选题',
    '论述题': '论述题', '简答题': '论述题', '案例分析题': '论述题',
    '无': '论述题', '填空题': '论述题',
    '写作题': '写作题', '作文': '写作题', '应用文': '写作题',
    # 判断题保持独立，不再映射为单选题
}

# 题型徽章颜色映射（供前端使用）
TYPE_BADGE_COLORS = {
    '单选题': '#409EFF',   # 蓝色
    '多选题': '#67C23A',   # 绿色
    '判断题': '#8B5CF6',   # 紫色
    '论述题': '#E6A23C',   # 橙色
    '写作题': '#F56C6C',   # 红色
}


def normalize_type_name(type_name: str) -> str:
    """将任意题型名称归一化为4种标准类型之一"""
    if not type_name:
        return '论述题'  # 默认
    # 精确匹配优先
    if type_name in TYPE_NORMALIZE_MAP:
        return TYPE_NORMALIZE_MAP[type_name]
    # 模糊匹配：包含关键词
    for old, new in TYPE_NORMALIZE_MAP.items():
        if old in type_name:
            return new
    return '论述题'  # 无法识别 → 默认论述题


# ============ 题型识别关键词工程 ============

# 多选题判定关键词（仅在有选项的前提下生效）
MULTI_CHOICE_KEYWORDS = [
    '多选', '多项选择', '不定项', '不定项选择',
    '两项以上', '三项以上', '四项以上', '2项以上', '3项以上', '4项以上',
    '至少两项', '至少三项', '至少两个', '至少三个', '至少选择两个',
    '两个以上', '多个选项', '有几项', '正确的有几项', '符合的有几项',
    '哪些', '下列哪些', '哪些是', '哪些属于',
    '属于.*的有', '包括.*的有', '符合.*的有',
    '正确的有', '错误的有', '正确的包括', '错误的包括',
    '正确的组合', '正确的搭配', '全部正确的是', '均正确的',
    '下列说法正确的有', '下列说法错误的有',
]

# 写作题判定关键词（无选项时生效，优先于论述关键词）
WRITING_KEYWORDS = [
    '作文', '写作', '大作文', '小作文', '应用文', '议论文', '申论写作', '公文',
    '写一篇', '写一段', '写一篇文章', '写一篇短文', '写一篇作文',
    '题目自拟', '自拟标题', '自选角度', '结合材料', '联系实际',
    '不少于', '不超过', '以.*为题', '以.*为话题', '围绕.*写',
    '请以.*为题', '请根据.*写', '撰写', '拟写',
]

# 论述题/简答题判定关键词（无选项且非写作时生效）
ESSAY_KEYWORDS = [
    '论述', '简述', '简答', '分析', '综合分析', '说明', '谈谈', '谈一谈',
    '阐述', '论证', '为什么', '如何理解', '怎样理解', '试述', '试析',
    '评价', '评析', '原因', '意义', '影响', '作用', '措施', '对策', '建议',
    '概括', '归纳', '总结', '指出', '比较', '谈谈你的看法', '谈谈你的理解',
    '你怎么看', '请分析', '请说明', '请阐述', '简述理由', '简要说明',
]


def count_options(content: str, options) -> int:
    """
    统计选项数量（单一事实来源）。

    - 优先使用传入的 options（list / dict / JSON 字符串）
    - 为空时从题干文本扫描 A-H 选项标记（行首 + 内联），解决 OCR 文本内联选项漏检，
      从而避免"有选项的选择题"被误判为论述题。
    """
    # 1. 传入的 options
    if options:
        if isinstance(options, (list, tuple)):
            valid = [o for o in options if o]
            if valid:
                return len(valid)
        elif isinstance(options, dict):
            valid_keys = [k for k, v in options.items() if v]
            if valid_keys:
                return len(valid_keys)
        elif isinstance(options, str):
            import json
            try:
                parsed = json.loads(options)
                return count_options(content, parsed)
            except (json.JSONDecodeError, TypeError):
                pass

    # 2. 文本扫描（行首 + 内联），A-H
    if content:
        text = content
        # 行首标记：A. / A、 / A． / A) / A） / A: / A：
        markers = re.findall(r'(?:^|[\n；;])\s*([A-H])\s*[.、．)）:：]', text, re.MULTILINE)
        if len({m.upper() for m in markers}) < 2:
            # 内联标记：'A. xxx B. xxx' / 'A、xxx B、xxx'
            markers = re.findall(r'([A-H])\s*[.、．)）:：]\s*\S', text)
        distinct = {m.upper() for m in markers}
        if len(distinct) >= 2:
            return len(distinct)
    return 0


def _judge_option_text(o: Any) -> str:
    """把选项（str / dict）归一化为纯文本，供题型判定使用。"""
    if o is None:
        return ''
    if isinstance(o, dict):
        s = o.get('value') or o.get('text') or o.get('label') or ''
    else:
        s = o
    s = UTB_PATTERN.sub('', str(s)).strip()
    s = re.sub(r'^[A-H]\s*[.、．)）\]]\s*', '', s).strip()
    return s


# 判断题的"判断对"选项特征
_JUDGE_OPTION_TOKENS = ('正确', '错误', '对', '错', '√', '×', 'TRUE', 'FALSE')
_JUDGE_ANSWER_TOKENS = {'对', '错', '正确', '错误', '√', '×', 'T', 'F', 'TRUE', 'FALSE'}

# 主观题关键词（P3 收窄：不再用"文本长度"当题型信号）
_WRITING_KW = ('作文', '写作', '撰写', '写一篇', '写一段', '议论文', '申论',
               '应用文', '自拟标题', '题目自拟', '不少于', '字左右', '请以', '为题写')
_ESSAY_KW = ('论述', '试述', '评析', '阐述', '论证', '如何理解', '怎样理解',
             '谈谈你的看法', '谈谈你的理解', '综合分析', '评价并')
_SHORT_ANSWER_KW = ('简述', '简答', '列举', '概括', '归纳', '指出', '说明理由')
_FILL_BLANK_KW = ('填空', '横线处', '划线处', '括号内', '内填写')
_MULTI_KW = ('多选', '多项选择', '不定项', '正确的有', '错误的有',
             '正确的包括', '错误的包括', '至少两个', '至少两个以上', '两个以上')


def _detect_question_type(content: str, options: List[str], answer: str = '',
                          section_hint: str = '') -> tuple[str, float]:
    """题型分类器（P3 重写：由加权投票改为**规则优先级**）。

    返回 (type_name, confidence)

    为什么重写
    ----------
    旧实现是 7 个维度的**加权累加**，各维度分数互相叠加、互相抵消，
    同一份证据会被重复计分，且最终用 max() 决胜 —— dict 顺序即优先级，
    "谁先写进字典谁赢"。实测后果：
      - 「有 4 个选项但选项解析失败」的题 opt_count=0，
        落入 `opt_count==0 → 论述题+2, 简答题+2` 的平局，靠 dict 顺序
        判成"论述题"（30 份真实语料 76 道）；
      - 题干里混入"二、多项选择题"（P2 修复前的分节污染）会被
        MULTI_CHOICE_KEYWORDS 加 6 分，把单选题误判成多选题；
      - `text.length > 200 → 写作题` 这类长度阈值与题型无因果关系。

    新实现按**结构硬约束**逐层判定，命中即返回，不再累加：
      L1 有选项 → 答案字母数是唯一依据（1 个=单选，≥2 个=多选）
      L2 有选项 + 选项为判断对 + 答案为判断词 → 判断题
      L3 无选项 → 按题型关键词细分（写作 > 论述 > 简答 > 填空）
      L4 以上均无 → 保守兜底 + 低置信度（供 need_review 标记）
    """
    content_text = content or ''
    # 题型判定前先剥掉分节指令段/材料头，防止它们污染关键词信号
    # （P2 已把它们从题干里剥离，这里是双保险：OCR/Excel 路径可能绕过 P2）
    clean_content = _SECTION_DIRECTIVE_RE.sub(' ', content_text)
    clean_content = re.sub(
        r'(?:根据|阅读)(?:以下|下面)[^\n]{0,20}?回答[ \t]*\d+[ \t]*[-~\u2014\uff0d\u81f3][ \t]*\d+[ \t]*题',
        ' ', clean_content)

    cleaned_options = []
    for o in (options or []):
        t = _judge_option_text(o)
        if t:
            cleaned_options.append(t)
    opt_count = len(cleaned_options)

    # 答案归一化：只保留 A-D 字母（中文数字答案在别处已转阿拉伯）
    ans = UTB_PATTERN.sub('', str(answer or '')).strip().upper()
    letters = ''.join(sorted(set(ch for ch in ans if ch in 'ABCD')))
    n_letter = len(letters)
    is_judge_answer = ans in _JUDGE_ANSWER_TOKENS

    # ---------- L2：判断题（结构特征最明确，先判）----------
    if opt_count == 2:
        has_pos = any(('正确' in t) or (t.strip() == '对') for t in cleaned_options)
        has_neg = any(('错误' in t) or (t.strip() == '错') for t in cleaned_options)
        if (has_pos and has_neg) or is_judge_answer:
            return '判断题', 0.95

    # ---------- L1：有选项 → 答案字母数是唯一依据 ----------
    if opt_count >= 2:
        if is_judge_answer:
            return '判断题', 0.90
        if n_letter >= 2:
            return '多选题', 0.95
        if n_letter == 1:
            return '单选题', 0.95
        # 答案缺失：题干关键词降级
        if any(k in clean_content for k in _MULTI_KW):
            return '多选题', 0.70
        if '判断' in clean_content or '对错' in clean_content:
            return '判断题', 0.70
        # 有 4 个以上选项却给不出答案 → 保守按单选，置信度低，交给人工复核
        return ('单选题' if opt_count <= 4 else '多选题'), 0.40

    # ---------- L1.5：分节声明的题型（仅对无选项题生效）----------
    # 判断题在真题里普遍以"陈述句 +（  ）"呈现，本身没有选项，题块层面
    # 与主观题无法区分。此时题块自身无任何信号，只能、也只应采用分节声明。
    # 有选项的题不在此处理 —— 选项结构是强于分节标题的证据。
    if section_hint and opt_count < 2:
        if section_hint == '判断题':
            return '判断题', 0.90
        # 主观题分节：分节声明比题干关键词更可信（题干里可能只是引用了"简述"二字）
        if section_hint in ('简答题', '论述题', '写作题', '填空题',
                            '案例分析题', '情景分析题', '材料题'):
            return section_hint, 0.85

    # ---------- L3：无选项 → 主观题，按关键词细分 ----------
    has = lambda kws: any(k in clean_content for k in kws)  # noqa: E731
    if has(_WRITING_KW):
        return '写作题', 0.90
    if has(_FILL_BLANK_KW):
        return '填空题', 0.85
    if has(_ESSAY_KW):
        return '论述题', 0.85
    if has(_SHORT_ANSWER_KW):
        return '简答题', 0.85
    if is_judge_answer:
        return '判断题', 0.90
    # 答案本身是长文本（参考答案式主观题）
    if len(ans) > 20:
        return '简答题', 0.70

    # ---------- L4：兜底 ----------
    # 说明：0 选项 + 无任何题型关键词的题，绝大多数是"情景分析题/材料题"
    #   （题干整体是一张图，选项也在图里）。旧实现判成"论述题"，
    #   新实现判成"简答题"并给低置信度，由 need_review 引导教师复核。
    return '简答题', 0.40

# ============ 答案一致性校验（静默错答检测） ============

def _norm_answer_letters(answer: Any) -> str:
    """归一化答案为排序去重的字母串（'C,A' / 'ca' → 'AC'）；无有效字母返回 ''。"""
    if not answer:
        return ''
    s = re.sub(r'[^A-Da-d]', '', str(answer).upper())
    return ''.join(sorted(set(s)))


def _declared_answer_in_analysis(analysis: Any) -> str:
    """从解析正文中提取"本题正确答案"的权威声明；无声明返回 ''。

    按权威性依次尝试：题头声明 → 结论声明（排除干扰项前缀）→ 显式答案标签。
    与 extract_answer_from_lines 的优先级保持一致，确保校验口径与解析口径同源。
    """
    if not analysis:
        return ''
    text = str(analysis)

    # 1) 题头声明："## 79、正确答案是：C" / "79. 答案：B"
    for line in text.split('\n')[:3]:
        s = line.strip()
        if not s or len(s) > 60:
            continue
        m = _BLOCK_HEADER_ANSWER_RE.match(s)
        if m:
            v = _norm_answer_letters(canonical_answer(m.group(1)))
            if v:
                return v

    # 2) 结论声明："故正确答案为C"（取末位，跳过"看似选D"这类干扰项）
    concl = _pick_conclusion_answer(text)
    if concl:
        return _norm_answer_letters(concl)

    # 3) 显式答案标签："答案：C" / "【答案】C"
    m = re.search(r'(?:【\s*答案\s*】|\s答案\s*[：:：])\s*([A-Da-d]{1,4})(?![A-Za-z])', text)
    if m:
        return _norm_answer_letters(canonical_answer(m.group(1)))

    return ''


def detect_answer_conflicts(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """检测 answer 字段与解析正文中显式声明答案之间的矛盾（静默错答）。

    为什么必须有这道门禁：
      「答案存在」不等于「答案正确」。字段完整率检查对**错答案完全免疫**——
      一道题有答案就能通过完整率校验，哪怕这个答案是从干扰项或下一题里取错的。
      实测（20 份真实试卷 / 1929 题）在完整率 100% 的同时存在 17 处此类损坏。

    处置：不在此处自动改写答案（源数据可能自相矛盾，如"故正确答案为AC。
    但是本题为单选"这类），而是显式上报，交 need_confirm_items 走人工复核。
    这样冲突从"不可见"变为"可见、可定位、可复核"，成为可持续门禁维度。
    """
    conflicts: List[Dict[str, Any]] = []
    for q in questions or []:
        ans = _norm_answer_letters(q.get('answer'))
        if not ans:
            continue
        # 兼容两种字段名：解析器内部用 analysis，API 入库层用 answer_analysis
        analysis = q.get('analysis') or q.get('answer_analysis') or ''
        declared = _declared_answer_in_analysis(analysis)
        if declared and declared != ans:
            conflicts.append({
                'question_number': q.get('question_number'),
                'answer': ans,
                'declared_in_analysis': declared,
                'reason': f'答案字段为 {ans}，但解析正文声明为 {declared}',
            })
    return conflicts


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
对于对错型单选题，"对/正确/是"对应A，"错/错误/否"对应B。

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
                    if num and ans and all(c in "ABCD" for c in str(ans)):
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


def _merge_answer_entry(answer_map: Dict[int, Dict[str, Optional[str]]],
                        num: int, ans_data: Dict[str, Optional[str]]) -> None:
    """策略间答案条目"字段级互补"合并。

    修复案例：先执行的"题号分段解析"产出 {answer:'A', analysis:None}，
    其后"嵌入式答案提取"携带完整 full_block 解析却因 `num in answer_map`
    守卫被整体丢弃 → 答案对而解析全空（真实案例 2016江西 解析缺失）。

    规则：
      - 新号直接写入；
      - 已有条目缺 answer 时补齐；
      - analysis 取更长者（解析宁多勿缺）。
    """
    if not isinstance(ans_data, dict):
        return
    prev = answer_map.get(num)
    if prev is None or not isinstance(prev, dict):
        answer_map[num] = ans_data
        return
    if not prev.get('answer') and ans_data.get('answer'):
        prev['answer'] = ans_data['answer']
    new_analysis = str(ans_data.get('analysis') or '')
    old_analysis = str(prev.get('analysis') or '')
    if len(new_analysis) > len(old_analysis):
        prev['analysis'] = ans_data['analysis']


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
    3. 连续答案序列匹配（含增强纯序列）
    4. 内联答案提取
    5. 增强纯序列位置匹配（无题号场景——修复0%匹配率问题）
    6. 宽松正则全局匹配
    7. 位置兜底匹配
    8. LLM智能匹配兜底（仅前7级<99%时触发）
    """
    strategies = []

    # ===== 预处理：噪声过滤 =====
    questions_text = ContentCleaner.clean_text(questions_text)
    answers_text = ContentCleaner.clean_text(answers_text)

    if not questions_text.strip():
        return MatchResult(
            match_rate=0.0, matched_count=0, total_questions=0,
            questions=[], unmatched_question_numbers=[], extra_answer_numbers=[],
            analysis_count=0, strategy_used='题目文本为空',
            details={}
        )

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
            _merge_answer_entry(answer_map, num, ans_data)

    # ===== 策略3: 连续答案序列补充 =====
    seq_map = parse_answer_sequence(answers_text)
    if seq_map:
        strategies.append('连续答案序列')
        for num, ans_data in seq_map.items():
            _merge_answer_entry(answer_map, num, ans_data)

    # ===== 策略4: 从题目文本提取内联答案 =====
    inline_from_q = _extract_inline_answers(questions_text)
    if inline_from_q:
        strategies.append('题目内联答案')
        for num, ans_data in inline_from_q.items():
            _merge_answer_entry(answer_map, num, ans_data)

    # ===== 策略5: 检测两文本相似度，高相似度时从答案文件提取内联答案 =====
    sim = compute_text_similarity(questions_text, answers_text)
    if sim > 0.6:  # 降低阈值以覆盖更多场景
        inline_from_a = _extract_inline_answers(answers_text, exclude_paren_bracket=True)
        if inline_from_a:
            strategies.append('答案文件内联答案')
            for num, ans_data in inline_from_a.items():
                _merge_answer_entry(answer_map, num, ans_data)

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
            _is_choice = block_accepts_letter_answer(block)
            # ---- 无选项题（判断题/主观题）绝不允许落 A/B/C/D ----
            # 真实事故：判断题没有 A/B 选项，答案却被写成字母，既无法判分，
            # 也会让教师在题目管理里看到与题干无关的假答案。
            # 改为从解析结论直读"正确/错误"；读不到就留空，交 need_review 复核。
            if not _is_choice:
                _verdict = judge_verdict_from_text(ans_entry.get('analysis') or '')
                if not _verdict:
                    # ans_entry 里的 analysis 可能被前序策略截断/替换，
                    # 回落按题号直接从答案文本取整段再判一次。
                    _verdict = judge_verdict_from_text(answer_region_for(answers_text, q_num))
                if _verdict:
                    block['answer'] = _verdict
                    matched_count += 1
                    answer_keys_used.add(q_num)
                if ans_entry.get('analysis') and len(str(ans_entry['analysis'])) > 10:
                    block['analysis'] = ans_entry['analysis']
                    analysis_count += 1
            else:
                if ans in CN_ANSWER_MAP:
                    ans = CN_ANSWER_MAP[ans]
                if all(c in "ABCD" for c in str(ans)):
                    block['answer'] = ans
                    matched_count += 1
                    answer_keys_used.add(q_num)
                if ans_entry.get('analysis') and len(str(ans_entry['analysis'])) > 10:
                    block['analysis'] = ans_entry['analysis']
                    analysis_count += 1
        else:
            # 无选项题（判断题/主观题）：宽松字母搜索一律拒绝。
            # 真实事故：判断题 81–90 被宽松重试灌入 C/D/D/B 假答案。
            # 改为从该题答案段直读"正确/错误"；读不到就留空交 need_review。
            if not block_accepts_letter_answer(block):
                _region = answer_region_for(answers_text, q_num)
                _verdict = judge_verdict_from_text(_region)
                if _verdict:
                    block['answer'] = _verdict
                    matched_count += 1
                    answer_keys_used.add(q_num)
                    if len(_region) > 10:
                        block['analysis'] = _region
                        analysis_count += 1
                else:
                    no_answer_nums.append(q_num)
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

    # ===== 策略5: 增强纯序列位置匹配（修复无题号0%问题） =====
    # Always attempt enhanced pure sequence as supplement (Fix 3)
    pure_seq_map = _match_pure_sequence_enhanced(answers_text, len(question_blocks))
    if pure_seq_map:
        strategies.append(f'增强纯序列匹配({len(pure_seq_map)}题)')
        for num, ans_data in pure_seq_map.items():
            _merge_answer_entry(answer_map, num, ans_data)
        # 重新执行匹配
        for block in question_blocks:
            q_num = block['question_number']
            if not block.get('answer') and q_num in answer_map:
                ans_entry = answer_map[q_num]
                # 判断题/无选项题禁止接受字母答案（见 block_accepts_letter_answer）
                if (ans_entry and ans_entry.get('answer')
                        and block_accepts_letter_answer(block)
                        and all(c in "ABCD" for c in str(ans_entry.get("answer", "")))):
                    block['answer'] = ans_entry['answer']
                    matched_count += 1
                    answer_keys_used.add(q_num)
                    if q_num in no_answer_nums:
                        no_answer_nums.remove(q_num)
                if ans_entry.get('analysis') and len(str(ans_entry['analysis'])) > 0:
                        block['analysis'] = ans_entry['analysis']
                        analysis_count += 1

    # ===== 策略6: 位置兜底匹配 =====
    if matched_count == 0 and len(question_blocks) > 0:
        # 从答案文本中提取所有A-D字母
        all_answers = re.findall(r'\b([A-Da-d])\b', answers_text)
        all_answers = [a.upper() for a in all_answers]

        # 如果答案数量与题目数量接近（误差 < 25%）
        if abs(len(all_answers) - len(question_blocks)) <= max(2, len(question_blocks) * 0.25):
            strategies.append('位置兜底匹配')
            for i, block in enumerate(question_blocks):
                # 判断题/无选项题禁止按位置灌字母（见 block_accepts_letter_answer）
                if not block.get('answer') and i < len(all_answers) \
                        and block_accepts_letter_answer(block):
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
                        if ans_entry.get('answer') and all(c in "ABCD" for c in str(ans_entry.get("answer", ""))):
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

    # ===== 静默错答检测（答案字段 vs 解析正文声明） =====
    # 字段完整率对"错答案"完全免疫：这里把矛盾显式化，写入 details 供上层上报。
    try:
        answer_conflicts = detect_answer_conflicts(question_blocks)
    except Exception as e:  # 校验绝不能阻断解析主流程
        logger.warning(f"答案一致性检测异常（已忽略）: {e}")
        answer_conflicts = []
    if answer_conflicts:
        logger.warning(
            f"检测到 {len(answer_conflicts)} 处答案与解析声明不一致（静默错答），"
            f"题号: {[c['question_number'] for c in answer_conflicts][:20]}"
        )

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
            'answer_conflicts': answer_conflicts,
            'answer_conflict_count': len(answer_conflicts),
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

    numbers = extract_question_numbers(text, exclude_paren_bracket=True, monotonic=True)
    if not numbers:
        # 无题号时：全局搜索嵌入式答案标记，按顺序分配
        all_embedded = []
        for fmt_name, pattern in EMBEDDED_ANSWER_PATTERNS:
            for m in pattern.finditer(text):
                ans = m.group(1).strip().upper()
                if ans in CN_ANSWER_MAP:
                    ans = CN_ANSWER_MAP[ans]
                if all(c in "ABCD" for c in str(ans)):
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
                if all(c in "ABCD" for c in str(ans)):
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
        scan_lines = lines[i:min(i + 200, len(lines))]  # Fix 7: extended from 30 to 200
        scan_text = '\n'.join(scan_lines)

        # 先尝试嵌入式答案模式
        for fmt_name, pattern in EMBEDDED_ANSWER_PATTERNS:
            m = pattern.search(scan_text)
            if m:
                ans = m.group(1).strip().upper()
                if ans in CN_ANSWER_MAP:
                    ans = CN_ANSWER_MAP[ans]
                if all(c in "ABCD" for c in str(ans)):
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
                if all(c in "ABCD" for c in str(ans)):
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
            if all(c in "ABCD" for c in str(ans)):
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


def _extract_inline_answers(text: str, exclude_paren_bracket: bool = False) -> Dict[int, Dict[str, Optional[str]]]:
    """从完整文本中按题号提取内联答案。

    exclude_paren_bracket=True 用于答案解析文本（解析正文"（1）（2）"子项序号
    会被 paren 模式误判为题号，需排除）。
    """
    numbers = extract_question_numbers(text, exclude_paren_bracket=exclude_paren_bracket,
                                       monotonic=exclude_paren_bracket)
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
        if extracted and extracted.get('answer') and all(c in 'ABCD' for c in (extracted.get('answer') or '')):
            result[qn.number] = {
                'answer': extracted['answer'],
                'analysis': extracted.get('analysis'),
            }

    return result


# ============ 科目检测 ============

def detect_subject_category(text: str) -> tuple[str, float]:
    """
    从文本内容自动检测科目大类。
    返回: (subject, confidence) - 如 ('公专', 0.85)
    置信度 < 0.3 时回退默认 '行测'
    """
    if not text:
        return '行测', 0.0

    scores = {'行测': 0, '申论': 0, '公专': 0}
    text_sample = text[:3000].lower()  # 扩大采样范围，转小写匹配

    for subject, kw_groups in SUBJECT_KEYWORDS.items():
        for kw in kw_groups.get('core', []):
            count = text_sample.count(kw.lower())
            scores[subject] += count * 5  # 核心词权重 5（从3提升）
        for kw in kw_groups.get('high', []):
            count = text_sample.count(kw.lower())
            scores[subject] += count * 3  # 高权重词权重 3（从2提升）
        for kw in kw_groups.get('normal', []):
            count = text_sample.count(kw.lower())
            scores[subject] += count * 1  # 普通词权重 1

    best = max(scores, key=scores.get)
    max_score = scores[best]
    total = sum(scores.values())

    # 置信度归一化
    confidence = min(max_score / max(total, 1), 1.0) if total > 0 else 0.0

    # 低置信度回退默认
    if confidence < 0.3:
        return '行测', confidence

    return best, round(confidence, 2)


# ============ 答案解析提取 ============

# 解析格式模式（支持多种常见格式）
ANALYSIS_PATTERNS = [
    # 标准格式：解析：xxx / 答案解析：xxx / 详细解析：xxx
    r'解析[：:]\s*(.+?)(?=\n\n|\n\d+[\.、]|\n[第一二三四五六七八九十]|\Z)',
    r'答案解析[：:]\s*(.+?)(?=\n\n|\n\d+[\.、]|\n[第一二三四五六七八九十]|\Z)',
    r'详细解析[：:]\s*(.+?)(?=\n\n|\n\d+[\.、]|\n[第一二三四五六七八九十]|\Z)',
    # 方括号格式：【解析】xxx / 【答案解析】xxx / 【详解】xxx
    r'【解析】\s*(.+?)(?=\n\n|\n\d+[\.、]|\n[第一二三四五六七八九十]|\Z)',
    r'【答案解析】\s*(.+?)(?=\n\n|\n\d+[\.、]|\n[第一二三四五六七八九十]|\Z)',
    r'【详解】\s*(.+?)(?=\n\n|\n\d+[\.、]|\n[第一二三四五六七八九十]|\Z)',
    # 括号格式：(解析)xxx
    r'\(解析\)\s*(.+?)(?=\n\n|\n\d+[\.、]|\n[第一二三四五六七八九十]|\Z)',
    # 换行格式
    r'解析[:：]\s*\n(.+?)(?=\n\n|\n\d+[\.、]|\n[第一二三四五六七八九十]|\Z)',
]

def extract_analysis(text: str) -> str:
    """
    从文本中提取答案解析，支持多种格式
    返回提取的解析文本，未找到返回空字符串
    """
    if not text:
        return ''
    
    for pattern in ANALYSIS_PATTERNS:
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            analysis = match.group(1).strip()
            # 清洗多余空白
            analysis = re.sub(r'\s+', ' ', analysis)
            if len(analysis) > 10:  # 过滤太短的误匹配
                return analysis
    
    # 位置兜底：答案后、下一题目前的文本
    answer_pos = max(
        text.rfind('答案'),
        text.rfind('answer'),
        text.rfind('正确答案'),
    )
    if answer_pos > 0:
        remaining = text[answer_pos:answer_pos+500]
        # 取第一段非空文本
        for para in remaining.split('\n\n'):
            para = para.strip()
            if len(para) > 10 and not re.match(r'^[\d一二三四五六七八九十][\.、]', para):
                return para
    
    return ''


# ============ AnswerValidator: 数据完整性校验 ============

class AnswerValidator:
    """
    Pipeline第6阶段 — 对匹配后的题目进行系统性校验。
    校验答案合法性、字段完整性、图片关联、题号连续性，并计算置信度。
    """

    @staticmethod
    def validate(questions: List[Dict[str, Any]], strategy_used: str = '') -> List[Dict[str, Any]]:
        """
        对每道题执行校验，填充 confidence 和 validation_errors 字段。

        校验规则：
        1. 答案-选项一致性：答案字母必须在options中存在
        2. 多选题答案拆分校验
        3. 必填字段检查
        4. 题型-选项一致性
        5. 置信度评分
        """
        for q in questions:
            errors = []
            options = q.get('options', [])
            answer = q.get('answer', '') or ''
            qtype = q.get('question_type', '单选题')
            content = q.get('content', '') or q.get('question_content', '')

            # ★ 申论题豁免选择题校验。
            #   下面 1-4 条规则全部是为「有选项、答案是字母」的选择题设计的：
            #     · 第3条 `len(options) < 2 → 选项不足` 对申论**必然**成立
            #       （申论是主观题，本来就没有选项）→ 每题都进validation_errors
            #       → 前端弹「校验异常题目: 第1,2,3,4题」
            #     · 第1条答案字母校验对长文本答案同样会误报
            #     · _compute_confidence 也是按选项匹配度打分 → confidence 0.0
            #       → 前端弹「低置信度题目(建议人工核对): 第1,2,3,4题」
            #   申论的正确性判据是**题号+分值+题干指纹**三方交叉校验
            #   （见 question_import._essay_cross_validate），不是选项匹配。
            #   故此处直接给高分放行，把正确性判定交给申论专用校验器。
            if q.get('format') == 'essay':
                if not content or len(str(content).strip()) < 4:
                    errors.append('题目内容为空或过短')
                q['confidence'] = 0.95
                q['validation_errors'] = errors
                continue

            # 1. 答案-选项一致性
            option_keys = {o.get('key', '') for o in options if isinstance(o, dict)}
            if answer and answer != '待补充':
                answer_letters = list(answer.upper())
                for letter in answer_letters:
                    if letter in 'ABCD' and letter not in option_keys:
                        if option_keys:  # 有选项但答案不在选项中
                            errors.append(f'答案"{letter}"不在选项{option_keys}中')
                            break

            # 2. 多选题答案拆分校验
            if qtype == '多选题' and len(answer) > 1:
                if not all(c in 'ABCD' for c in answer.upper()):
                    errors.append(f'多选题答案"{answer}"包含非法字符')

            # 3. 必填字段检查
            if not content or len(str(content).strip()) < 4:
                errors.append('题目内容为空或过短')
            if len(options) < 2:
                errors.append(f'选项不足(仅{len(options)}个)')

            # 4. 题型-选项一致性(判断题)
            if len(options) == 2 and qtype == '单选题':
                if answer and answer.upper() not in ('A', 'B'):
                    errors.append('判断题答案必须为A或B')

            # 5. 置信度评分
            confidence = AnswerValidator._compute_confidence(
                answer, q, strategy_used, errors
            )

            q['confidence'] = round(confidence, 2)
            q['validation_errors'] = errors

        # 题号连续性检测
        # ★ 题号可能是 str（申论解析器统一产出 str），必须先转 int 再比较，
        #   否则 min()/max() 在混合类型上抛 TypeError: '<' not supported between str and int
        numbers = []
        for q in questions:
            raw_no = q.get('question_number')
            if raw_no in (None, ''):
                continue
            try:
                numbers.append(int(raw_no))
            except (TypeError, ValueError):
                continue
        if numbers:
            expected = set(range(min(numbers), max(numbers) + 1))
            missing = sorted(expected - set(numbers))
            if missing:
                logger.warning(f"[Validator] 题号不连续，缺失: {missing[:20]}")

        return questions

    @staticmethod
    def _compute_confidence(answer: str, question: dict, strategy: str, errors: list) -> float:
        """计算匹配置信度"""
        score = 0.60  # 默认基准

        # 答案来源评分
        if strategy:
            if '题号分段解析' in strategy:
                score = 0.95
            elif '嵌入式答案提取' in strategy:
                score = 0.85
            elif '连续答案序列' in strategy or '纯序列' in strategy:
                score = 0.75
            elif '增强纯序列' in strategy:
                score = 0.65
            elif '位置兜底' in strategy:
                score = 0.50
            elif 'LLM' in strategy:
                score = 0.40

        # 完整性加分
        analysis = question.get('analysis', '') or ''
        if analysis and len(str(analysis)) > 10:
            score += 0.05

        # 无答案扣分
        if not answer or answer == '待补充':
            score -= 0.20

        # 有校验错误扣分
        if errors:
            score -= 0.10 * len(errors)

        return max(0.0, min(1.0, score))


# ============ NumberFormatNormalizer: 跨格式题号统一 ============

class NumberFormatNormalizer:
    """
    统一不同文档来源的题号表示差异。
    处理全角数字、中文数字、不同分隔符等格式差异。
    """

    # 全角数字→半角映射
    FULLWIDTH_DIGITS = str.maketrans('０１２３４５６７８９', '0123456789')

    # 中文数字(1-99常用)
    CN_NUMBERS = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
        '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20,
    }

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """
        预处理文本：统一所有题号格式为 "N." 格式。
        - 全角数字→半角
        - 中文数字→阿拉伯（仅行首题号位置）
        - 统一分隔符
        """
        if not text:
            return text

        # 全角数字→半角
        text = text.translate(cls.FULLWIDTH_DIGITS)

        # 行首中文数字→阿拉伯（仅题号位置）
        lines = text.split('\n')
        for i, line in enumerate(lines):
            stripped = line.strip()
            for cn, num in cls.CN_NUMBERS.items():
                # 匹配 "一、" "一." "一．" "一)" 等格式
                if stripped.startswith(cn) and len(stripped) > 1:
                    if stripped[len(cn)] in '.、．)）':
                        lines[i] = line.replace(cn, str(num), 1)
                        break

        return '\n'.join(lines)

    @classmethod
    def extract_number(cls, text: str) -> Optional[int]:
        """从文本行提取标准化的题号"""
        if not text:
            return None
        text = text.strip().translate(cls.FULLWIDTH_DIGITS)
        for cn, num in cls.CN_NUMBERS.items():
            if text.startswith(cn):
                return num
        # 标准数字提取
        m = re.match(r'(\d+)', text)
        return int(m.group(1)) if m else None
