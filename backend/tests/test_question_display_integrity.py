# -*- coding: utf-8 -*-
"""题目展示与导入完整性：要求切分、图片选项、来源标题的单元测试。"""
from app.services.question_ingest.tags import _auto_detect_tags, _clean_source_title
from app.services.text_parser import _split_essay_requirements, _split_image_only_options


def test_split_requirements_with_explicit_mark_and_inline_items():
    stem, reqs = _split_essay_requirements(
        "根据给定材料1，概括Z县做法。（15分） 要求： （1）准确全面； （2）分条列出； （3）不超过200字。"
    )
    assert stem == "根据给定材料1，概括Z县做法。（15分）"
    assert reqs == ["（1）准确全面；", "（2）分条列出；", "（3）不超过200字。"]


def test_split_requirements_without_mark_falls_back_to_score_then_numbering():
    stem, reqs = _split_essay_requirements(
        "根据给定资料，分析问题。（20分）（1）观点明确；（2）条理清晰。"
    )
    assert stem == "根据给定资料，分析问题。（20分）"
    assert reqs == ["（1）观点明确；", "（2）条理清晰。"]


def test_split_requirements_does_not_misread_verb_yaoqiu():
    text = "本题要求你概括材料中的问题。"
    stem, reqs = _split_essay_requirements(text)
    assert stem == text
    assert reqs == []


def test_split_image_only_options_expands_into_a_to_d():
    options = [
        {"key": "A", "value": "[IMAGE:a_1_0] [IMAGE:a_1_1]"},
        {"key": "B", "value": "[IMAGE:a_1_2]"},
        {"key": "C", "value": "[IMAGE:a_1_3]"},
    ]
    assert _split_image_only_options(options) == [
        {"key": "A", "value": "[IMAGE:a_1_0]"},
        {"key": "B", "value": "[IMAGE:a_1_1]"},
        {"key": "C", "value": "[IMAGE:a_1_2]"},
        {"key": "D", "value": "[IMAGE:a_1_3]"},
    ]


def test_split_image_only_options_keeps_valid_four_image_options():
    options = [
        {"key": "A", "value": "[IMAGE:a_1_0]"},
        {"key": "B", "value": "[IMAGE:a_1_1]"},
        {"key": "C", "value": "[IMAGE:a_1_2]"},
        {"key": "D", "value": "[IMAGE:a_1_3]"},
    ]
    assert _split_image_only_options(options) == options


def test_clean_source_title_strips_extension_and_copy_suffix():
    assert _clean_source_title("2025年安徽省公务员录用考试《行测》题（网友回忆版）.pdf") == (
        "2025年安徽省公务员录用考试《行测》题（网友回忆版）"
    )
    assert _clean_source_title("题目_2024年北京市考申论真题_副本.docx") == "2024年北京市考申论真题"


def test_auto_tags_exposes_clean_document_title():
    tags = _auto_detect_tags("2025年天津市公务员考试《公安专业科目》试题.pdf", "")
    assert tags["source_title"] == "2025年天津市公务员考试《公安专业科目》试题"
    assert tags["paper_name"]
