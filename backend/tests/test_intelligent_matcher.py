"""
IntelligentMatcher 智能匹配引擎单元测试
对应 Task 6: 智能匹配引擎
"""
import pytest

from app.services.text_parser import IntelligentMatcher, MatchResult


class TestMatchQuestionsAnswers:
    """match_questions_answers 智能匹配测试"""

    def test_basic_match(self):
        matcher = IntelligentMatcher()
        questions_text = "1. 题目一\n2. 题目二\n3. 题目三"
        answers_text = "1. A\n2. B\n3. C"
        result = matcher.match_questions_answers(questions_text, answers_text)
        assert result.match_rate > 0.9
        assert result.matched_count == 3
        assert result.total_questions == 3

    def test_match_with_analysis(self):
        matcher = IntelligentMatcher()
        questions_text = "1. 题目一\n2. 题目二"
        answers_text = "1. A 解析：这是第一题的解析\n2. B 解析：这是第二题的解析"
        result = matcher.match_questions_answers(questions_text, answers_text)
        assert result.analysis_count == 2

    def test_empty_questions(self):
        matcher = IntelligentMatcher()
        result = matcher.match_questions_answers("", "1. A")
        assert result.match_rate == 0.0
        assert result.total_questions == 0

    def test_unmatched_answers(self):
        matcher = IntelligentMatcher()
        questions_text = "1. 题目一\n2. 题目二\n3. 题目三"
        answers_text = "1. A\n2. B"
        result = matcher.match_questions_answers(questions_text, answers_text)
        assert result.matched_count == 2
        assert result.total_questions == 3

    def test_returns_match_result(self):
        matcher = IntelligentMatcher()
        result = matcher.match_questions_answers("1. 题", "1. A")
        assert isinstance(result, MatchResult)
        assert hasattr(result, 'match_rate')
        assert hasattr(result, 'strategy_used')


class TestEvaluateMatchQuality:
    """evaluate_match_quality 匹配质量评估测试"""

    def test_perfect_match_quality(self):
        matcher = IntelligentMatcher()
        result = matcher.match_questions_answers("1. 题目\n2. 题目", "1. A\n2. B")
        quality = matcher.evaluate_match_quality(result)
        assert 'match_rate' in quality
        assert 'confidence' in quality
        assert 'quality_score' in quality
        assert quality['quality_score'] > 0.8
