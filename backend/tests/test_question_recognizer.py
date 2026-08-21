"""
QuestionNumberRecognizer 题号识别器单元测试
对应 Task 2: 题号识别增强
"""
import pytest

from app.services.text_parser import QuestionNumberRecognizer


class TestRecognizeWithConfidence:
    """recognize_with_confidence 带置信度题号识别测试"""

    def test_standard_numbers(self):
        recognizer = QuestionNumberRecognizer()
        text = "1. 题目一\n2. 题目二\n3. 题目三"
        result = recognizer.recognize_with_confidence(text)
        assert len(result) == 3
        assert result[0]['number'] == 1
        assert result[1]['number'] == 2
        assert result[2]['number'] == 3

    def test_chinese_numbers(self):
        recognizer = QuestionNumberRecognizer()
        text = "一、题目一\n二、题目二\n三、题目三"
        result = recognizer.recognize_with_confidence(text)
        assert len(result) == 3
        assert result[0]['number'] == 1
        assert result[1]['number'] == 2
        assert result[2]['number'] == 3

    def test_mixed_formats(self):
        recognizer = QuestionNumberRecognizer()
        text = "1. 题目一\n二、题目二\n(3) 题目三"
        result = recognizer.recognize_with_confidence(text)
        assert len(result) == 3

    def test_consecutive_boosts_confidence(self):
        recognizer = QuestionNumberRecognizer()
        text = "1. 题\n2. 题"
        result = recognizer.recognize_with_confidence(text)
        # 连续题号置信度应高于基础值
        assert result[0]['confidence'] < result[1]['confidence']

    def test_does_not_match_digits_inside_content(self):
        recognizer = QuestionNumberRecognizer()
        text = "根据2016年规定，下列说法正确的是"
        result = recognizer.recognize_with_confidence(text)
        assert len(result) == 0

    def test_empty_input(self):
        recognizer = QuestionNumberRecognizer()
        assert recognizer.recognize_with_confidence("") == []
        assert recognizer.recognize_with_confidence(None) == []


class TestResolveConflicts:
    """resolve_conflicts 冲突解决测试"""

    def test_selects_longest_consecutive_sequence(self):
        recognizer = QuestionNumberRecognizer()
        candidates = [
            {'number': 5, 'position': 0, 'format': 'x', 'confidence': 0.8, 'context': ''},
            {'number': 1, 'position': 10, 'format': 'x', 'confidence': 0.8, 'context': ''},
            {'number': 2, 'position': 20, 'format': 'x', 'confidence': 0.8, 'context': ''},
            {'number': 3, 'position': 30, 'format': 'x', 'confidence': 0.8, 'context': ''},
        ]
        result = recognizer.resolve_conflicts(candidates)
        assert [c['number'] for c in result] == [1, 2, 3]

    def test_empty_candidates(self):
        recognizer = QuestionNumberRecognizer()
        assert recognizer.resolve_conflicts([]) == []
