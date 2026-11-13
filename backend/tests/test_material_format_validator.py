# -*- coding: utf-8 -*-
"""P2-B：上传格式校验器单元测试（纯函数，不启 HTTP、不读写文件）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.material_format_validator import (  # noqa: E402
    BACK_MAX,
    FRONT_MAX,
    ROW_LIMIT,
    check_file,
    resolve_columns,
    validate_rows,
)

HEAD = ["正面", "背面", "分类", "考点"]
CATS = ["判断推理", "资料分析"]


def ok_rows(n=2):
    return [[f"正面{i}", f"背面内容{i}" * 5, "判断推理", "图形推理"] for i in range(n)]


class TestColumns:
    def test_alias_resolution(self):
        cols = resolve_columns(["卡片正面", "解析", "子类", "知识点"])
        assert cols == {"front": 0, "back": 1, "category": 2, "point": 3}

    def test_english_headers(self):
        assert resolve_columns(["front", "back"])["front"] == 0


class TestStructure:
    def test_valid_rows(self):
        r = validate_rows(HEAD, ok_rows(3), category_names=CATS, point_names=["图形推理"])
        assert r["ok"] is True
        assert r["stats"]["rows"] == 3
        assert r["stats"]["valid"] == 3
        assert r["stats"]["error_count"] == 0

    def test_missing_back_column(self):
        r = validate_rows(["正面", "分类"], [["a", "判断推理"]])
        assert r["ok"] is False
        assert r["errors"][0]["code"] == "E001"
        assert "背面" in r["errors"][0]["message"]

    def test_empty_cell(self):
        r = validate_rows(HEAD, [["正面", "", "", ""]])
        assert r["errors"][0]["code"] == "E002"

    def test_too_long(self):
        r = validate_rows(HEAD, [["正" * (FRONT_MAX + 1), "背" * (BACK_MAX + 1), "", ""]])
        codes = [e["code"] for e in r["errors"]]
        assert codes.count("E003") == 2

    def test_row_limit(self):
        rows = ok_rows(ROW_LIMIT + 1)
        r = validate_rows(HEAD, rows, max_errors=5)
        assert r["ok"] is False
        assert any(e["code"] == "E004" for e in r["errors"])

    def test_duplicate_rows(self):
        row = ["同一正面", "同一背面", "", ""]
        r = validate_rows(HEAD, [row, row])
        assert any(e["code"] == "E005" and e["row"] == 2 for e in r["errors"])

    def test_dangerous_tag(self):
        r = validate_rows(HEAD, [["<script>x</script>", "背面", "", ""]])
        assert any(e["code"] == "E008" for e in r["errors"])


class TestWordlists:
    def test_category_error_by_default(self):
        r = validate_rows(HEAD, [["a", "b", "方法技巧", ""]], category_names=CATS)
        assert r["ok"] is False
        assert any(e["code"] == "E006" for e in r["errors"])

    def test_category_as_warning_in_import(self):
        r = validate_rows(HEAD, [["a", "b", "方法技巧", ""]], category_names=CATS,
                          category_as_warning=True)
        assert r["ok"] is True
        assert r["stats"]["warning_count"] == 1
        assert r["warnings"][0]["code"] == "E006"

    def test_point_is_warning(self):
        r = validate_rows(HEAD, [["a", "b", "", "不存在的考点"]],
                          point_names=["图形推理"])
        assert r["ok"] is True
        assert r["warnings"][0]["code"] == "E007"

    def test_empty_wordlist_skips_check(self):
        # 科目尚未配置词表时不误报
        r = validate_rows(HEAD, [["a", "b", "随便写", "随便写"]])
        assert r["ok"] is True


class TestFileLevel:
    def test_bad_ext(self):
        assert check_file("a.txt", 100)[0]["code"] == "E009"

    def test_oversize(self):
        errs = check_file("a.xlsx", 11 * 1024 * 1024)
        assert errs and errs[0]["code"] == "E010"

    def test_good_file(self):
        assert check_file("a.xlsx", 1024) == []


class TestErrorCap:
    def test_cap_but_true_count(self):
        rows = [["", "", "", ""] for _ in range(6)]
        r = validate_rows(HEAD, rows, max_errors=3)
        assert len(r["errors"]) == 3
        assert r["stats"]["error_count"] == 6
