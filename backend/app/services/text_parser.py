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

# ============ 常量 ============

# 去重相似度阈值（>= 此值视为重复）
DEDUP_SIMILARITY_THRESHOLD = 0.75  # 从0.80降低，更严格的去重

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

    @classmethod
    def clean(cls, lines: List[str]) -> List[str]:
        """
        过滤文本行中的噪声。
        返回过滤后的行列表。
        """
        if not lines:
            return []

        # Phase 1: 行级模式过滤
        filtered = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue  # 跳过完全空行
            is_noise = False
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

# 去重阈值：0.70（从0.75降低，配合答案硬约束提高准确性）
DEDUP_SIMILARITY_THRESHOLD = 0.70

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
            if ans and all(c in "ABCD" for c in str(ans)) and num not in seen:
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

        # 检测题型（传入 answer 支持多字母答案检测）
        qtype = _detect_question_type(content_text, options, answer or '')

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
    # 判断题 → 单选题（判断题本质上是二选一的选择题）
    '判断题': '单选题',
}

# 题型徽章颜色映射（供前端使用）
TYPE_BADGE_COLORS = {
    '单选题': '#409EFF',   # 蓝色
    '多选题': '#67C23A',   # 绿色
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


def _detect_question_type(content: str, options: List[str], answer: str = '') -> str:
    """
    分层题型分类器（v4 · 关键词工程 · 单一事实来源）。

    确定性分层规则（优先级从高到低）：
      Step1 有选项(>=2) → 客观选择题：
              答案多字母(>=2) 或 命中多选关键词 → 多选题；否则 → 单选题
            （判断题自然归入单选题——其选项为"对/错"两项、答案归一化为单字母 A/B）
      Step2 无选项 → 命中写作关键词 → 写作题
      Step3 无选项 → 命中论述/简答关键词 → 论述题
      Step4 兜底 → 论述题（记低置信日志）
    """
    content_text = content or ''
    norm_answer = canonical_answer(answer)

    opt_count = count_options(content_text, options)

    # === Step 1: 客观选择题 ===
    if opt_count >= 2:
        if len(norm_answer) >= 2:
            return '多选题'
        if any(re.search(kw, content_text) for kw in MULTI_CHOICE_KEYWORDS):
            return '多选题'
        return '单选题'

    # === Step 2: 写作题 ===
    if any(re.search(kw, content_text) for kw in WRITING_KEYWORDS):
        return '写作题'

    # === Step 3: 论述题 ===
    if any(re.search(kw, content_text) for kw in ESSAY_KEYWORDS):
        return '论述题'

    # === Step 4: 兜底 ===
    logger.warning(f"[type-detect] 低置信度兜底为论述题: {content_text[:50]!r}")
    return '论述题'


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
            if all(c in "ABCD" for c in str(ans)):
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

    # ===== 策略5: 增强纯序列位置匹配（修复无题号0%问题） =====
    # Always attempt enhanced pure sequence as supplement (Fix 3)
    pure_seq_map = _match_pure_sequence_enhanced(answers_text, len(question_blocks))
    if pure_seq_map:
        strategies.append(f'增强纯序列匹配({len(pure_seq_map)}题)')
        for num, ans_data in pure_seq_map.items():
            if num not in answer_map:
                answer_map[num] = ans_data
        # 重新执行匹配
        for block in question_blocks:
            q_num = block['question_number']
            if not block.get('answer') and q_num in answer_map:
                ans_entry = answer_map[q_num]
                if ans_entry and ans_entry.get('answer') and all(c in "ABCD" for c in str(ans_entry.get("answer", ""))):
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
        if extracted and extracted.get('answer') and all(c in 'ABCD' for c in (extracted.get('answer') or '')):
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
        numbers = [q.get('question_number', 0) for q in questions if q.get('question_number')]
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
