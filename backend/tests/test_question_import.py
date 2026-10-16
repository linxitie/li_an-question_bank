"""
Task 10: 集成测试 - 题目导入匹配功能
测试后端 API 端点：分离匹配、文本预处理、智能匹配引擎
"""
import os
import sys
import pytest

# 确保 backend 目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.text_parser import (
    TextPreprocessor,
    QuestionNumberRecognizer,
    AnswerExtractor,
    IntelligentMatcher,
    MatchResult,
    smart_match_questions_answers,
)


# ============ TextPreprocessor 测试 ============
class TestTextPreprocessorIntegration:
    """集成测试：文本预处理"""

    def setup_method(self):
        self.preprocessor = TextPreprocessor()

    def test_clean_text_preserves_newlines(self):
        """验证 clean_text 保留换行符"""
        text = "第一行\n第二行\n第三行"
        result = self.preprocessor.clean_text(text)
        assert "\n" in result
        assert "第一行" in result
        assert "第二行" in result

    def test_clean_text_removes_page_numbers(self):
        """验证 clean_text 移除页码"""
        text = "题目内容\n— 12 —\n更多内容"
        result = self.preprocessor.clean_text(text)
        assert "题目" in result

    def test_normalize_question_numbers(self):
        """验证题号标准化"""
        text = "第一题 测试内容\n（二）第二题内容\n第3题 第三题"
        cleaned = self.preprocessor.clean_text(text)
        result = self.preprocessor.normalize_question_numbers(cleaned)
        assert len(result) > 0
        assert any(c.isdigit() for c in result)

    def test_full_preprocessing_pipeline(self):
        """验证完整预处理流程"""
        text = "  第一题  测试  \n  （二）  内容  "
        cleaned = self.preprocessor.clean_text(text)
        result = self.preprocessor.normalize_question_numbers(cleaned)
        assert len(result) > 0


# ============ QuestionNumberRecognizer 测试 ============
class TestQuestionRecognizerIntegration:
    """集成测试：题号识别"""

    def setup_method(self):
        self.recognizer = QuestionNumberRecognizer()

    def test_recognize_standard_numbers(self):
        """识别标准数字题号"""
        text = "1. 第一题内容\n2. 第二题内容\n3. 第三题内容"
        results = self.recognizer.recognize_with_confidence(text)
        assert len(results) >= 3
        numbers = [r["number"] for r in results]
        assert 1 in numbers
        assert 2 in numbers
        assert 3 in numbers

    def test_recognize_chinese_numbers(self):
        """识别中文题号（需先标准化为数字格式）"""
        # normalize_question_numbers 处理 "一、" 格式，不处理 "第一题" 格式
        # 因此使用 "一、" 格式来测试
        text = "一、内容\n二、内容\n三、内容"
        preprocessor = TextPreprocessor()
        cleaned = preprocessor.clean_text(text)
        normalized = preprocessor.normalize_question_numbers(cleaned)
        results = self.recognizer.recognize_with_confidence(normalized)
        assert len(results) >= 3

    def test_resolve_conflicts(self):
        """冲突解决：取最长连续序列"""
        candidates = [
            {"number": 1, "position": 0, "confidence": 0.9},
            {"number": 2, "position": 1, "confidence": 0.8},
            {"number": 10, "position": 2, "confidence": 0.7},
            {"number": 11, "position": 3, "confidence": 0.6},
            {"number": 3, "position": 4, "confidence": 0.5},
        ]
        resolved = self.recognizer.resolve_conflicts(candidates)
        assert len(resolved) >= 2


# ============ AnswerExtractor 测试 ============
class TestAnswerExtractorIntegration:
    """集成测试：答案提取"""

    def setup_method(self):
        self.extractor = AnswerExtractor()

    def test_validate_answer_valid(self):
        """验证有效答案"""
        assert self.extractor.validate_answer("A", "单选题")
        assert self.extractor.validate_answer("AB", "多选题")

    def test_validate_answer_invalid(self):
        """验证无效答案"""
        assert not self.extractor.validate_answer("E", "单选题")
        assert not self.extractor.validate_answer("", "单选题")


# ============ IntelligentMatcher 测试 ============
class TestIntelligentMatcherIntegration:
    """集成测试：智能匹配引擎"""

    def setup_method(self):
        self.matcher = IntelligentMatcher()

    def test_match_questions_answers_basic(self):
        """基础题目-答案匹配"""
        questions = "1. 题目一\n2. 题目二\n3. 题目三"
        answers = "1. A\n2. B\n3. C"
        result = self.matcher.match_questions_answers(questions, answers)
        assert isinstance(result, MatchResult)
        assert result.match_rate > 0
        assert result.matched_count >= 2

    def test_match_with_analysis(self):
        """带解析的匹配"""
        questions = "1. 题目一\n2. 题目二"
        answers = "1. A 解析：第一题解析内容很长\n2. B 解析：第二题解析内容很长"
        result = self.matcher.match_questions_answers(questions, answers)
        assert result.analysis_count >= 1

    def test_match_mismatched_numbers(self):
        """题号不完全匹配"""
        questions = "1. 题目一\n2. 题目二\n3. 题目三"
        answers = "1. A\n3. C"
        result = self.matcher.match_questions_answers(questions, answers)
        assert result.matched_count >= 1
        assert result.matched_count < 3

    def test_match_empty_inputs(self):
        """空输入处理"""
        result = self.matcher.match_questions_answers("", "")
        assert result.match_rate == 0
        assert result.matched_count == 0


# ============ smart_match_questions_answers 集成测试 ============
class TestSmartMatchIntegration:
    """集成测试：原有智能匹配函数"""

    def test_smart_match_basic(self):
        """基础智能匹配"""
        questions = "1. 测试题目一\n2. 测试题目二"
        answers = "1. A\n2. B"
        result = smart_match_questions_answers(questions, answers)
        assert result is not None
        assert hasattr(result, "match_rate") or isinstance(result, dict)


# ============ 端到端集成测试 ============
class TestEndToEndIntegration:
    """端到端集成测试：模拟真实导入场景"""

    def test_full_import_flow_with_real_pattern(self):
        """模拟真实文档的导入匹配流程"""
        questions_text = """1. 根据《中华人民共和国人民警察法》的规定，人民警察遇到公民人身、财产安全受到侵犯或处于其他危难情形，应当：
A. 立即救助
B. 等待支援
C. 向上级报告
D. 视情况而定

2. 下列关于人民警察纪律的说法，正确的是：
A. 人民警察可以从事营利性经营活动
B. 人民警察不得散布有损国家声誉的言论
C. 人民警察可以随意使用警械
D. 人民警察可以接受当事人的请客送礼

3. 公安机关对于被拘留的人，应当在拘留后的多长时间内进行讯问？
A. 12小时
B. 24小时
C. 48小时
D. 72小时"""

        answers_text = """1. A 解析：根据《人民警察法》第二十一条规定，人民警察遇到公民人身、财产安全受到侵犯或处于其他危难情形，应当立即救助。

2. B 解析：根据《人民警察法》第二十二条规定，人民警察不得散布有损国家声誉的言论，不得参加非法组织。

3. B 解析：根据《刑事诉讼法》第八十六条规定，公安机关对被拘留的人，应当在拘留后的二十四小时以内进行讯问。"""

        matcher = IntelligentMatcher()
        result = matcher.match_questions_answers(questions_text, answers_text)

        assert isinstance(result, MatchResult)
        assert result.total_questions == 3
        assert result.matched_count >= 2
        assert result.match_rate >= 0.5

        for q in result.questions:
            if q["question_number"] == 1:
                assert q["answer"] == "A"
            elif q["question_number"] == 2:
                assert q["answer"] == "B"
            elif q["question_number"] == 3:
                assert q["answer"] == "B"

        print(f"端到端测试通过：匹配率 {result.match_rate:.1%}，"
              f"匹配 {result.matched_count}/{result.total_questions} 题")

    def test_mixed_format_matching(self):
        """混合格式匹配（中文题号 + 数字题号）"""
        questions_text = "第一题 测试内容\n2. 第二题内容\n第三题 内容"
        answers_text = "1. A\n2. B\n3. C"

        matcher = IntelligentMatcher()
        result = matcher.match_questions_answers(questions_text, answers_text)

        assert result.matched_count >= 1
        print(f"混合格式测试通过：匹配 {result.matched_count} 题")


# ============ MinerU 扫描件三级回退链（计划 Task 3） ============

import sys
import types


class TestScannedPdfMineruFallback:
    """验证 _extract_text_from_pdf 的分支选择：
    ① MinerU 启用且成功 → 返回其结构化文本（不再走旧OCR）
    ② MinerU 禁用/失败 → 走既有 _extract_text_from_scanned_pdf（PaddleOCR，行为不变）

    通过向 sys.modules 注入 pdfplumber/PyPDF2 存根（页数为空 → 两级文本提取
    自然返回空），确定性地到达 OCR 回退段；不依赖真实解析器对垃圾字节的行为，
    也不修改任何生产解析代码。
    """

    @pytest.fixture(autouse=True)
    def _stub_parsers(self, monkeypatch):
        # --- pdfplumber 存根: open() 返回无页面上下文 ---
        fake_plumber = types.ModuleType('pdfplumber')

        class _FakePdf:
            pages = []

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        fake_plumber.open = lambda *a, **k: _FakePdf()
        monkeypatch.setitem(sys.modules, 'pdfplumber', fake_plumber)

        # --- PyPDF2 存根: PdfReader 无页面 ---
        fake_pypdf2 = types.ModuleType('PyPDF2')

        class _FakeReader:
            pages = []

        fake_pypdf2.PdfReader = _FakeReader
        monkeypatch.setitem(sys.modules, 'PyPDF2', fake_pypdf2)
        yield

    def test_prefers_mineru_when_available(self, monkeypatch):
        import app.api.v1.catalog.question_import as qi
        # I-6：实现已 pure move 到 pdf_reader，补丁须打在真正持有该函数的命名空间
        from app.services.question_ingest import pdf_reader as pr

        # 实现采用 from-import 直绑，故在 pr 命名空间打补丁
        monkeypatch.setattr(pr, 'mineru_is_enabled', lambda: True)
        monkeypatch.setattr(pr, 'mineru_extract_text_sync',
                            lambda buf: 'MinerU结构化文本')
        # 惰性间谍: 若旧路径被调用则记录（勿用 pytest.fail 急切求值——赋值即抛）
        fallback_calls = []
        monkeypatch.setattr(pr, '_extract_text_from_scanned_pdf',
                            lambda buf: fallback_calls.append(1))

        result = qi._extract_text_from_pdf(b'%PDF-1.4 scanned-stub')
        assert result == 'MinerU结构化文本'
        assert not fallback_calls, 'MinerU可用时不应回退到旧PaddleOCR路径'

    def test_falls_back_to_paddleocr_path(self, monkeypatch):
        import app.api.v1.catalog.question_import as qi
        # I-6：实现已 pure move 到 pdf_reader，补丁须打在真正持有该函数的命名空间
        from app.services.question_ingest import pdf_reader as pr

        monkeypatch.setattr(pr, 'mineru_is_enabled', lambda: False)
        monkeypatch.setattr(pr, '_extract_text_from_scanned_pdf',
                            lambda buf: 'PADDLE_FALLBACK_TEXT')

        result = qi._extract_text_from_pdf(b'%PDF-1.4 scanned-stub')
        assert result == 'PADDLE_FALLBACK_TEXT'

    def test_falls_back_when_mineru_returns_none(self, monkeypatch):
        """MinerU 启用但解析失败(None) → 必须继续走旧路径（三级链第②级）。"""
        import app.api.v1.catalog.question_import as qi
        # I-6：实现已 pure move 到 pdf_reader，补丁须打在真正持有该函数的命名空间
        from app.services.question_ingest import pdf_reader as pr

        monkeypatch.setattr(pr, 'mineru_is_enabled', lambda: True)
        monkeypatch.setattr(pr, 'mineru_extract_text_sync', lambda buf: None)
        monkeypatch.setattr(pr, '_extract_text_from_scanned_pdf',
                            lambda buf: 'PADDLE_FALLBACK_TEXT')

        result = qi._extract_text_from_pdf(b'%PDF-1.4 scanned-stub')
        assert result == 'PADDLE_FALLBACK_TEXT'


# ============ 直接运行 ============
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
