"""
AnswerExtractor 答案提取器单元测试
对应 Task 3: 答案提取优化
"""
import pytest

from app.services.text_parser import AnswerExtractor


class TestExtractWithContext:
    """extract_with_context 带上下文答案提取测试"""

    def test_single_choice(self):
        extractor = AnswerExtractor()
        text = "答案：A"
        result = extractor.extract_with_context(text, {'question_type': '单选题'})
        assert result['answer'] == 'A'
        assert result['confidence'] > 0.8

    def test_multiple_choice(self):
        extractor = AnswerExtractor()
        text = "参考答案：ABC"
        result = extractor.extract_with_context(text, {'question_type': '多选题'})
        assert result['answer'] == 'ABC'
        assert result['confidence'] > 0.8

    def test_essay_answer(self):
        extractor = AnswerExtractor()
        text = "这是一道论述题的参考答案，至少需要50个字符才能通过验证。" * 2
        result = extractor.extract_with_context(text, {'question_type': '论述题'})
        assert len(result['answer']) >= 50

    def test_empty_input(self):
        extractor = AnswerExtractor()
        result = extractor.extract_with_context('', {'question_type': '单选题'})
        assert result['answer'] == ''
        assert result['confidence'] == 0.0

    def test_no_answer_found(self):
        extractor = AnswerExtractor()
        text = "题目内容完全没有答案信息"
        result = extractor.extract_with_context(text, {'question_type': '单选题'})
        assert result['answer'] == ''

    def test_answer_colon_format(self):
        extractor = AnswerExtractor()
        text = "正确答案：B"
        result = extractor.extract_with_context(text, {'question_type': '单选题'})
        assert result['answer'] == 'B'

    def test_answer_english_format(self):
        extractor = AnswerExtractor()
        text = "Answer: D"
        result = extractor.extract_with_context(text, {'question_type': '单选题'})
        assert result['answer'] == 'D'


class TestValidateAnswer:
    """validate_answer 答案验证测试"""

    def test_single_choice_valid(self):
        extractor = AnswerExtractor()
        assert extractor.validate_answer('A', '单选题') is True
        assert extractor.validate_answer('D', '单选题') is True

    def test_single_choice_invalid(self):
        extractor = AnswerExtractor()
        assert extractor.validate_answer('AB', '单选题') is False
        assert extractor.validate_answer('E', '单选题') is False

    def test_multiple_choice_valid(self):
        extractor = AnswerExtractor()
        assert extractor.validate_answer('AB', '多选题') is True
        assert extractor.validate_answer('ABCD', '多选题') is True

    def test_multiple_choice_invalid_order(self):
        extractor = AnswerExtractor()
        assert extractor.validate_answer('BA', '多选题') is False

    def test_essay_min_length(self):
        extractor = AnswerExtractor()
        short = "短答案"
        long = "这是一道论述题的完整参考答案，需要超过五十个字符才能通过验证。" * 2
        assert extractor.validate_answer(short, '论述题') is False
        assert extractor.validate_answer(long, '论述题') is True
