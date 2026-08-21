"""
StructureMatcher 结构特征匹配器单元测试
对应 Task 5: 结构特征匹配
"""
import pytest

from app.services.structure_matcher import StructureMatcher


class TestExtractStructureFeatures:
    """extract_structure_features 结构特征提取测试"""

    def test_basic_features(self):
        matcher = StructureMatcher()
        question_block = {
            'content': '这是一道测试题目，包含选项A、B、C、D。',
            'options': [
                {'key': 'A', 'value': '选项A'},
                {'key': 'B', 'value': '选项B'},
                {'key': 'C', 'value': '选项C'},
                {'key': 'D', 'value': '选项D'},
            ],
            'question_type': '单选题',
        }
        result = matcher.extract_structure_features(question_block)
        assert 'question_length' in result
        assert 'option_count' in result
        assert 'option_type' in result
        assert 'has_image' in result
        assert 'has_formula' in result
        assert 'question_type' in result
        assert result['option_count'] == 4
        assert result['question_type'] == 'single'

    def test_empty_block(self):
        matcher = StructureMatcher()
        result = matcher.extract_structure_features({})
        assert result['question_length'] == 0
        assert result['option_count'] == 0
        assert result['question_type'] == 'single'

    def test_image_detection(self):
        matcher = StructureMatcher()
        block = {'content': '如图所示 <img src="test.jpg"> 题目内容', 'options': [], 'question_type': '单选题'}
        result = matcher.extract_structure_features(block)
        assert result['has_image'] is True


class TestCalculateStructureSimilarity:
    """calculate_structure_similarity 结构相似度计算测试"""

    def test_identical_features(self):
        matcher = StructureMatcher()
        features = {
            'question_length': 100,
            'option_count': 4,
            'option_type': 'text',
            'option_format': 'numbered',
            'has_image': False,
            'has_formula': False,
            'paragraph_count': 1,
            'sentence_count': 2,
            'word_count': 50,
            'avg_sentence_length': 25.0,
            'punctuation_type': 'chinese',
            'question_type': 'single',
        }
        result = matcher.calculate_structure_similarity(features, features)
        assert result == pytest.approx(1.0)

    def test_similar_features(self):
        matcher = StructureMatcher()
        features1 = {
            'question_length': 100, 'option_count': 4, 'option_type': 'text',
            'option_format': 'numbered', 'has_image': False, 'has_formula': False,
            'paragraph_count': 1, 'sentence_count': 2, 'word_count': 50,
            'avg_sentence_length': 25.0, 'punctuation_type': 'chinese', 'question_type': 'single',
        }
        features2 = {
            'question_length': 120, 'option_count': 4, 'option_type': 'text',
            'option_format': 'numbered', 'has_image': False, 'has_formula': False,
            'paragraph_count': 1, 'sentence_count': 2, 'word_count': 60,
            'avg_sentence_length': 30.0, 'punctuation_type': 'chinese', 'question_type': 'single',
        }
        result = matcher.calculate_structure_similarity(features1, features2)
        assert 0.0 <= result <= 1.0
        assert result > 0.8

    def test_different_types(self):
        matcher = StructureMatcher()
        f1 = {**{'question_length': 50, 'option_count': 4, 'option_type': 'text',
                  'option_format': 'numbered', 'has_image': False, 'has_formula': False,
                  'paragraph_count': 1, 'sentence_count': 1, 'word_count': 25,
                  'avg_sentence_length': 25.0, 'punctuation_type': 'chinese'}, 'question_type': 'single'}
        f2 = {**f1, 'question_type': 'essay'}
        result = matcher.calculate_structure_similarity(f1, f2)
        assert 0.0 <= result < 1.0

    def test_empty_features(self):
        matcher = StructureMatcher()
        assert matcher.calculate_structure_similarity({}, {}) == 0.0
