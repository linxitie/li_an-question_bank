# -*- coding: utf-8 -*-
"""C2a：试卷文件名解析回归（2026-11-08）。

规则要点：
- 年份取**最后一个**（"2024 版 2019 真题" → 2019），限定 1990–2100，不把"100 题/120 分钟"当年份；
- 地区按**长名优先**匹配（"黑龙江"不会被"龙江"之类误吃；"内蒙古/广西"等单字省份也有词条）；
- 「答案/解析」优先于「题本」——"真题答案解析"这种同时出现的，判为答案；
- 人读编号 `GZ-2019-BJ-T` 要求 **科目+年份+地区** 三者齐备，缺一项就不生成（宁缺勿错）。
"""
import pytest

from app.services.paper_meta_parser import (
    build_paper_code,
    format_meta_label,
    parse_paper_file_name,
    parse_year,
)


class TestYear:
    def test_simple(self):
        assert parse_year("2019年北京市公务员考试真题") == 2019

    def test_takes_last(self):
        assert parse_year("2024版 2019年江苏公专真题") == 2019

    def test_ignores_question_count_and_duration(self):
        assert parse_year("公专 100题 120分钟 模拟卷") is None

    def test_out_of_range_ignored(self):
        assert parse_year("1888 年 老卷") is None


class TestParse:
    def test_full_beijing_paper(self):
        meta = parse_paper_file_name("2019年北京市公务员考试《公安专业科目》真题.docx")
        assert meta.year == 2019
        assert (meta.region_code, meta.region_name) == ("BJ", "北京")
        assert meta.subject == "gongzhuan"
        assert meta.book_kind == "T"
        assert meta.paper_code == "GZ-2019-BJ-T"

    def test_jiangsu_paper(self):
        meta = parse_paper_file_name("2017年江苏省公务员考试《公安基础知识》考试真题.pdf")
        assert meta.year == 2017
        assert meta.region_name == "江苏"
        assert meta.paper_code == "GZ-2017-JS-T"

    def test_answer_book(self):
        meta = parse_paper_file_name("2020年国考公安专业科目真题答案解析.pdf")
        assert meta.book_kind == "A"
        assert meta.book_kind_label == "答案"
        assert meta.region_code == "GK"
        assert meta.paper_code == "GZ-2020-GK-A"

    def test_volume(self):
        meta = parse_paper_file_name("2018年浙江省考行测真题 第二卷.docx")
        assert meta.volume == 2
        assert meta.paper_code == "XC-2018-ZJ-T-V2"

    def test_xingce_and_shenlun(self):
        assert parse_paper_file_name("2021年山东省考行测真题.pdf").paper_code == "XC-2021-SD-T"
        assert parse_paper_file_name("2022年广东省考申论真题.docx").paper_code == "SL-2022-GD-T"

    def test_missing_pieces_gives_no_code(self):
        meta = parse_paper_file_name("公专真题.docx")
        assert meta.year is None and meta.region_code is None
        assert meta.paper_code is None
        assert meta.subject == "gongzhuan"

    def test_garbage_name_is_empty(self):
        meta = parse_paper_file_name("扫描件_00123.pdf")
        assert meta.has_any is False
        assert meta.paper_code is None

    def test_fullwidth_and_spaces(self):
        meta = parse_paper_file_name("  2019年 北京 公专 题本 .PDF  ")
        assert meta.year == 2019
        assert meta.paper_code == "GZ-2019-BJ-T"

    def test_long_region_name_not_truncated(self):
        meta = parse_paper_file_name("2020年黑龙江省考公安真题.pdf")
        assert meta.region_name == "黑龙江"
        assert meta.region_code == "HLJ"


class TestCodeAndLabel:
    def test_build_requires_three_parts(self):
        assert build_paper_code(parse_paper_file_name("2019年公专真题.docx")) is None

    @pytest.mark.parametrize("name,label", [
        ("2019年北京市公务员考试《公安专业科目》真题.docx", "2019 · 北京 · 题本"),
        ("2020年国考公安真题答案解析.pdf", "2020 · 国考 · 答案"),
        ("2019年 北京 公专 题本.pdf", "2019 · 北京 · 题本"),
    ])
    def test_label(self, name, label):
        assert format_meta_label(parse_paper_file_name(name)) == label

    def test_label_empty_when_nothing(self):
        assert format_meta_label(parse_paper_file_name("x.pdf")) == ""
