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

    def test_cross_subject_not_misclassified(self, db):
        # 「逻辑填空」属行测；若声明 subject=shenlun 不应被判成 xingce 的子类
        got = _auto_classify(db, "shenlun", "逻辑填空", None, None)
        assert got is None
