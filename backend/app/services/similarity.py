"""
多维度相似度计算器

提供多种相似度计算方法，用于题目文本的智能匹配：
1. 编辑距离相似度（字符级）
2. 余弦相似度（词频向量级）
3. Jaccard相似度（词汇重叠级）
4. 序列相似度（最长公共子序列级）
5. 综合相似度（加权平均）
"""
import math
from collections import Counter
from difflib import SequenceMatcher
from typing import Dict


class SimilarityCalculator:
    """多维度相似度计算器"""

    def calculate_edit_distance(self, s1: str, s2: str) -> float:
        """
        计算编辑距离相似度。
        基于 SequenceMatcher 的字符级相似度。
        """
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        matcher = SequenceMatcher(None, s1, s2)
        return matcher.ratio()

    def calculate_cosine_similarity(self, s1: str, s2: str) -> float:
        """
        计算余弦相似度。
        基于字符级词频向量化。
        """
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        counter1 = Counter(s1)
        counter2 = Counter(s2)

        intersection = set(counter1.keys()) & set(counter2.keys())
        numerator = sum(counter1[x] * counter2[x] for x in intersection)

        sum1 = sum(v ** 2 for v in counter1.values())
        sum2 = sum(v ** 2 for v in counter2.values())
        denominator = math.sqrt(sum1) * math.sqrt(sum2)

        if not denominator:
            return 0.0

        return float(numerator) / denominator

    def calculate_jaccard_similarity(self, s1: str, s2: str) -> float:
        """
        计算 Jaccard 相似度。
        基于字符集合的重叠度。
        """
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        set1 = set(s1)
        set2 = set(s2)

        intersection = len(set1 & set2)
        union = len(set1 | set2)

        if union == 0:
            return 0.0

        return intersection / union

    def calculate_sequence_similarity(self, s1: str, s2: str) -> float:
        """
        计算序列相似度。
        基于最长公共子序列的结构相似度。
        """
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0

        matcher = SequenceMatcher(None, s1, s2)
        return matcher.ratio()

    def calculate_combined_similarity(self, s1: str, s2: str) -> Dict[str, float]:
        """
        综合多种相似度指标。
        返回：{edit_distance, cosine_similarity, jaccard_similarity, sequence_similarity, combined_score}
        """
        edit_distance = self.calculate_edit_distance(s1, s2)
        cosine_similarity = self.calculate_cosine_similarity(s1, s2)
        jaccard_similarity = self.calculate_jaccard_similarity(s1, s2)
        sequence_similarity = self.calculate_sequence_similarity(s1, s2)

        # 加权平均综合得分
        combined_score = (
            edit_distance * 0.3 +
            cosine_similarity * 0.3 +
            jaccard_similarity * 0.2 +
            sequence_similarity * 0.2
        )

        return {
            'edit_distance': edit_distance,
            'cosine_similarity': cosine_similarity,
            'jaccard_similarity': jaccard_similarity,
            'sequence_similarity': sequence_similarity,
            'combined_score': combined_score,
        }
