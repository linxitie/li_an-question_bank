"""
SimilarityCalculator 多维度相似度计算器单元测试
对应 Task 4: 多维度相似度计算
"""
import pytest

from app.services.similarity import SimilarityCalculator


class TestEditDistance:
    """calculate_edit_distance 编辑距离相似度测试"""

    def test_identical_strings(self):
        calculator = SimilarityCalculator()
        assert calculator.calculate_edit_distance("题目", "题目") == 1.0

    def test_similar_strings(self):
        calculator = SimilarityCalculator()
        result = calculator.calculate_edit_distance("题目一", "题目二")
        assert 0.0 <= result <= 1.0
        assert result > 0.5

    def test_empty_strings(self):
        calculator = SimilarityCalculator()
        assert calculator.calculate_edit_distance("", "") == 1.0

    def test_one_empty(self):
        calculator = SimilarityCalculator()
        assert calculator.calculate_edit_distance("abc", "") == 0.0


class TestCosineSimilarity:
    """calculate_cosine_similarity 余弦相似度测试"""

    def test_identical_strings(self):
        calculator = SimilarityCalculator()
        assert calculator.calculate_cosine_similarity("题目", "题目") == pytest.approx(1.0)

    def test_similar_strings(self):
        calculator = SimilarityCalculator()
        result = calculator.calculate_cosine_similarity("这是一道关于数学的题目", "这是一道关于语文的题目")
        assert 0.0 <= result <= 1.0
        assert result > 0.3

    def test_empty_strings(self):
        calculator = SimilarityCalculator()
        assert calculator.calculate_cosine_similarity("", "") == 1.0


class TestJaccardSimilarity:
    """calculate_jaccard_similarity Jaccard相似度测试"""

    def test_identical_strings(self):
        calculator = SimilarityCalculator()
        assert calculator.calculate_jaccard_similarity("ABCD", "ABCD") == 1.0

    def test_similar_strings(self):
        calculator = SimilarityCalculator()
        result = calculator.calculate_jaccard_similarity("ABCD", "ABCE")
        assert 0.0 <= result <= 1.0
        assert result > 0.5

    def test_empty_strings(self):
        calculator = SimilarityCalculator()
        assert calculator.calculate_jaccard_similarity("", "") == 1.0


class TestCombinedSimilarity:
    """calculate_combined_similarity 综合相似度测试"""

    def test_identical_strings(self):
        calculator = SimilarityCalculator()
        result = calculator.calculate_combined_similarity("题目内容", "题目内容")
        assert 'edit_distance' in result
        assert 'cosine_similarity' in result
        assert 'jaccard_similarity' in result
        assert 'sequence_similarity' in result
        assert 'combined_score' in result
        assert result['combined_score'] > 0.9

    def test_result_structure(self):
        calculator = SimilarityCalculator()
        result = calculator.calculate_combined_similarity("A", "B")
        assert all(k in result for k in ['edit_distance', 'cosine_similarity', 'jaccard_similarity', 'sequence_similarity', 'combined_score'])
        assert all(0.0 <= v <= 1.0 for v in result.values())
