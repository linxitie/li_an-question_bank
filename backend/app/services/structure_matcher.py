"""
结构特征匹配器

从题目文本中提取结构特征（长度、选项、格式、图片/公式检测等），
并计算两个题目之间的结构相似度，用于辅助智能匹配。
"""
import re
from typing import Dict, List


class StructureMatcher:
    """结构特征匹配器"""

    def extract_structure_features(self, question_block: dict) -> dict:
        """
        提取题目结构特征。
        返回：{
            question_length, option_count, option_type, option_format,
            has_image, has_formula, paragraph_count, sentence_count,
            word_count, avg_sentence_length, punctuation_type, question_type
        }
        """
        content = question_block.get('content', '')
        options = question_block.get('options', [])
        question_type = question_block.get('question_type', '单选题')

        question_length = len(content)
        option_count = len(options)

        option_type = self._detect_option_type(options)
        option_format = self._detect_option_format(options)

        has_image = bool(re.search(r'<img|IMAGE|\.(jpg|jpeg|png|gif)', content, re.IGNORECASE))
        has_formula = bool(re.search(r'\$|\\frac|\\sum|\\int|数学公式', content, re.IGNORECASE))

        paragraph_count = len([p for p in content.split('\n') if p.strip()])

        sentences = re.split(r'[。！？.!?]', content)
        sentence_count = len([s for s in sentences if s.strip()])

        word_count = len(content)
        avg_sentence_length = word_count / sentence_count if sentence_count > 0 else 0.0

        punctuation_type = self._detect_punctuation_type(content)

        question_type_map = {
            '单选题': 'single', '多选题': 'multi',
            '判断题': 'judge', '论述题': 'essay', '写作题': 'essay',
        }
        mapped_type = question_type_map.get(question_type, 'single')

        return {
            'question_length': question_length,
            'option_count': option_count,
            'option_type': option_type,
            'option_format': option_format,
            'has_image': has_image,
            'has_formula': has_formula,
            'paragraph_count': paragraph_count,
            'sentence_count': sentence_count,
            'word_count': word_count,
            'avg_sentence_length': avg_sentence_length,
            'punctuation_type': punctuation_type,
            'question_type': mapped_type,
        }

    def _detect_option_type(self, options: list) -> str:
        """检测选项类型：numeric / text / mixed / none"""
        if not options:
            return 'none'

        numeric_count = sum(1 for o in options if re.match(r'^\d+\.?\d*$', o.get('value', '')))
        text_count = len(options) - numeric_count

        if numeric_count > text_count:
            return 'numeric'
        elif text_count > numeric_count:
            return 'text'
        else:
            return 'mixed'

    def _detect_option_format(self, options: list) -> str:
        """检测选项格式：numbered / plain / none"""
        if not options:
            return 'none'

        numbered_count = sum(1 for o in options if re.match(r'^[A-D]$', o.get('key', '')))
        plain_count = len(options) - numbered_count

        return 'numbered' if numbered_count > plain_count else 'plain'

    def _detect_punctuation_type(self, text: str) -> str:
        """检测标点类型：chinese / english / mixed"""
        chinese_punct = len(re.findall(r'[\u3000-\u303F\uFF00-\uFFEF]', text))
        english_punct = len(re.findall(r'[!-/:-@[-`{-~]', text))

        if chinese_punct > english_punct:
            return 'chinese'
        elif english_punct > chinese_punct:
            return 'english'
        else:
            return 'mixed'

    def calculate_structure_similarity(self, features1: dict, features2: dict) -> float:
        """
        计算两组结构特征的相似度。
        加权综合：题目长度(0.2) + 选项数量(0.3) + 选项类型(0.2) + 题目类型(0.3)
        """
        if not features1 or not features2:
            return 0.0

        similarities = []

        # 题目长度相似度
        len1 = features1.get('question_length', 0)
        len2 = features2.get('question_length', 0)
        length_sim = 1.0 - abs(len1 - len2) / max(len1, len2, 1)
        similarities.append(length_sim * 0.2)

        # 选项数量相似度
        oc1 = features1.get('option_count', 0)
        oc2 = features2.get('option_count', 0)
        option_count_sim = 1.0 - abs(oc1 - oc2) / max(oc1, oc2, 1)
        similarities.append(option_count_sim * 0.3)

        # 选项类型相似度
        ot1 = features1.get('option_type', 'none')
        ot2 = features2.get('option_type', 'none')
        option_type_sim = 1.0 if ot1 == ot2 else 0.5
        similarities.append(option_type_sim * 0.2)

        # 题目类型相似度
        qt1 = features1.get('question_type', 'single')
        qt2 = features2.get('question_type', 'single')
        question_type_sim = 1.0 if qt1 == qt2 else 0.3
        similarities.append(question_type_sim * 0.3)

        total_weight = 0.2 + 0.3 + 0.2 + 0.3
        return sum(similarities) / total_weight if total_weight > 0 else 0.0

    def match_by_structure(self, question_blocks: list, answer_blocks: list) -> dict:
        """
        基于结构特征进行匹配。
        返回：{matches: [{question, answer, similarity}], confidence: float}
        """
        matches = []
        used_answers = set()

        for q_block in question_blocks:
            q_features = self.extract_structure_features(q_block)
            best_match = None
            best_similarity = 0.0

            for i, a_block in enumerate(answer_blocks):
                if i in used_answers:
                    continue
                a_features = self.extract_structure_features(a_block)
                similarity = self.calculate_structure_similarity(q_features, a_features)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = i

            if best_match is not None and best_similarity > 0.7:
                matches.append({
                    'question': q_block,
                    'answer': answer_blocks[best_match],
                    'similarity': best_similarity,
                })
                used_answers.add(best_match)

        confidence = len(matches) / len(question_blocks) if question_blocks else 0.0
        return {'matches': matches, 'confidence': confidence}
