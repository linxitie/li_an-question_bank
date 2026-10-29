# -*- coding: utf-8 -*-
"""B 逻辑层单元测试：卡片格式校验 + 关键词自动分类。

只测纯函数（不启 HTTP），保证快且稳定：
- _check_card_text：长度上限、危险标签
- _auto_classify：命中规则 / 无匹配 / 跨科目不误判
"""
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.v1.library.materials import (  # noqa: E402
    CARD_BACK_MAX,
    CARD_FRONT_MAX,
    _auto_classify,
    _check_card_text,
    _resolve_card_category,
)
from app.core.database import SessionLocal  # noqa: E402


class TestCardFormat:
    def test_front_ok(self):
        _check_card_text("逻辑填空三步排", "先判语境再辨词义")

    def test_front_too_long(self):
        with pytest.raises(HTTPException) as ei:
            _check_card_text("字" * (CARD_FRONT_MAX + 1), None)
        assert "卡片正面" in str(ei.value.detail)

    def test_back_too_long(self):
        with pytest.raises(HTTPException) as ei:
            _check_card_text("ok", "字" * (CARD_BACK_MAX + 1))
        assert "卡片背面" in str(ei.value.detail)

    @pytest.mark.parametrize("bad", ["<script>alert(1)</script>", "<iframe src=x>", "<object>", "<embed>"])
    def test_dangerous_tags_rejected(self, bad):
        with pytest.raises(HTTPException) as ei:
            _check_card_text(bad, None)
        assert "不允许的标签" in str(ei.value.detail)

    def test_empty_passes(self):
        _check_card_text(None, None)


class TestAutoClassify:
    @pytest.fixture()
    def db(self):
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    def test_hit_xingce(self, db):
        got = _auto_classify(db, "xingce", "逻辑填空三步排", "先判语境", None)
        assert got == "言语理解与表达"

    def test_hit_shenlun(self, db):
        got = _auto_classify(db, "shenlun", "归纳概括作答顺序", None, None)
        assert got == "归纳概括"

    def test_hit_gongzhuan(self, db):
        got = _auto_classify(db, "gongzhuan", "人民警察职业道德规范", None, None)
        assert got == "职业素养"

    def test_no_match_returns_none(self, db):
        assert _auto_classify(db, "xingce", "QWERTYUIOP ASDF", None, None) is None

    def test_title_beats_body_keywords(self, db):
        # 标题「图形推理」应压过正文里的「辨词义」（言语理解的关键词）
        got = _auto_classify(db, "xingce", "图形推理-加强削弱专练",
                             "图形推理要点", "先判语境再辨词义")
        assert got == "判断推理"

    def test_body_only_still_works(self, db):
        # 标题无关键词时，仍可由正文命中
        got = _auto_classify(db, "xingce", "综合练习A",
                             "增长率与比重的计算", None)
        assert got == "资料分析"

    def test_explicit_wins(self, db):
        # 表格分类列有值时不覆盖
        got = _resolve_card_category(db, "xingce", "图形推理", "先看元素组成", "方法技巧")
        assert got == "方法技巧"

    def test_auto_when_empty(self, db):
        # 无分类列时自动判定
        got = _resolve_card_category(db, "xingce", "图形推理-加强削弱", "先看元素组成", None)
        assert got == "判断推理"

    def test_empty_string_treated_as_absent(self, db):
        # build_cards 在无分类列时给的是空串，应视为"未分类"
        got = _resolve_card_category(db, "shenlun", "归纳概括要点合并", "", "")
        assert got == "归纳概括"

    def test_none_when_no_match(self, db):
        assert _resolve_card_category(db, "xingce", "QWERTYUIOP", None, None) is None

    def test_cross_subject_not_misclassified(self, db):
        # 「逻辑填空」属行测；若声明 subject=shenlun 不应被判成 xingce 的子类
        got = _auto_classify(db, "shenlun", "逻辑填空", None, None)
        assert got is None
