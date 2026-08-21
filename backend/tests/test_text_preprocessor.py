"""
TextPreprocessor 文本预处理器单元测试
对应 Task 1: 文本预处理优化
"""
import pytest

from app.services.text_parser import TextPreprocessor


class TestCleanText:
    """clean_text 文本清理测试"""

    def test_normalizes_whitespace(self):
        preprocessor = TextPreprocessor()
        text = "  这是  一个  测试  "
        result = preprocessor.clean_text(text)
        assert result == "这是一个测试"

    def test_removes_page_numbers(self):
        preprocessor = TextPreprocessor()
        text = "题目内容 第1页 更多内容"
        result = preprocessor.clean_text(text)
        assert "第1页" not in result
        assert "题目内容" in result
        assert "更多内容" in result

    def test_removes_bare_page_numbers(self):
        preprocessor = TextPreprocessor()
        text = "内容A 10页 内容B"
        result = preprocessor.clean_text(text)
        assert "10页" not in result

    def test_empty_input(self):
        preprocessor = TextPreprocessor()
        assert preprocessor.clean_text("") == ""
        assert preprocessor.clean_text(None) == ""


class TestNormalizeQuestionNumbers:
    """normalize_question_numbers 题号归一化测试"""

    def test_chinese_numbers(self):
        preprocessor = TextPreprocessor()
        text = "一、题目内容\n二、更多内容"
        result = preprocessor.normalize_question_numbers(text)
        assert "1." in result
        assert "2." in result

    def test_parenthesized_numbers(self):
        preprocessor = TextPreprocessor()
        text = "（1）题目一\n（2）题目二"
        result = preprocessor.normalize_question_numbers(text)
        assert "1." in result
        assert "2." in result

    def test_di_ti_format(self):
        preprocessor = TextPreprocessor()
        text = "第1题 内容\n第2题 内容"
        result = preprocessor.normalize_question_numbers(text)
        assert "1." in result
        assert "2." in result

    def test_q_prefix_format(self):
        preprocessor = TextPreprocessor()
        text = "Q1: 内容\nQ2: 内容"
        result = preprocessor.normalize_question_numbers(text)
        assert "1." in result
        assert "2." in result

    def test_empty_input(self):
        preprocessor = TextPreprocessor()
        assert preprocessor.normalize_question_numbers("") == ""
        assert preprocessor.normalize_question_numbers(None) == ""
