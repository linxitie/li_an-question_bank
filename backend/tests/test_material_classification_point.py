# -*- coding: utf-8 -*-
"""P2：分类法第三层（子类 → 考点 → 资料）单元测试。

覆盖：
- 子类词表校验（合法通过 / 非法 400 且带提示）
- 考点校验（跨科目考点必须拒绝）
- 两级自动分类（一条规则同时产出子类 + 考点）
- _finalize_classification 的「显式 > 自动」与「考点反推子类」
- 规则库规模（110 条 = 16 子类 + 94 考点）
"""
import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.v1.library.materials import (  # noqa: E402
    _auto_classify_ex,
    _category_names,
    _finalize_classification,
    _point_id_by_name,
    _resolve_classification,
    _validate_category,
    _validate_point,
)
from app.core.database import SessionLocal  # noqa: E402


@pytest.fixture()
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


class TestCategoryWhitelist:
    def test_known_category_passes(self, db):
        assert _validate_category(db, "xingce", "判断推理") == "判断推理"
        assert _validate_category(db, "gongzhuan", "基本警务能力") == "基本警务能力"

    def test_empty_is_allowed(self, db):
        assert _validate_category(db, "xingce", "") is None
        assert _validate_category(db, "xingce", None) is None

    def test_drift_category_rejected_with_hint(self, db):
        with pytest.raises(HTTPException) as ei:
            _validate_category(db, "xingce", "方法技巧")
        assert ei.value.status_code == 400
        assert "方法技巧" in str(ei.value.detail)
        # 必须给出可操作的提示：最近词或可选清单
        assert "判断推理" in str(ei.value.detail) or "可选" in str(ei.value.detail)

    def test_cross_subject_category_rejected(self, db):
        # 「归纳概括」是申论子类，不能挂到行测资料上
        with pytest.raises(HTTPException):
            _validate_category(db, "xingce", "归纳概括")

    def test_wordlist_not_empty(self, db):
        assert len(_category_names(db, "xingce")) == 8
        assert len(_category_names(db, "shenlun")) == 5
        assert len(_category_names(db, "gongzhuan")) == 3


class TestPointBinding:
    def test_point_belongs_to_subject(self, db):
        pid = _point_id_by_name(db, "xingce", "图形推理")
        assert pid
        assert _validate_point(db, "xingce", pid) == pid

    def test_point_of_other_subject_rejected(self, db):
        pid = _point_id_by_name(db, "shenlun", "问题概括")
        assert pid
        with pytest.raises(HTTPException):
            _validate_point(db, "xingce", pid)

    def test_bad_point_id_rejected(self, db):
        with pytest.raises(HTTPException):
            _validate_point(db, "xingce", "abc")
        with pytest.raises(HTTPException):
            _validate_point(db, "xingce", 999999)


class TestTwoLevelAutoClassify:
    def test_point_rule_yields_both_levels(self, db):
        got = _auto_classify_ex(db, "xingce", "图形推理", None, None)
        assert got is not None
        assert got["point_name"] == "图形推理"
        assert got["point_id"] == _point_id_by_name(db, "xingce", "图形推理")
        assert got["category"] == "判断推理"

    def test_body_fallback(self, db):
        # 标题不含考点词，正文含考点名 → 第二轮兜底
        got = _auto_classify_ex(db, "shenlun", "综合练习A", "归纳概括的作答顺序", None)
        assert got is not None
        assert got["category"] == "归纳概括"

    def test_no_match_returns_none(self, db):
        assert _auto_classify_ex(db, "xingce", "QWERTYUIOP", None, None) is None

    def test_cross_subject_not_misclassified(self, db):
        got = _auto_classify_ex(db, "shenlun", "逻辑填空", None, None)
        assert got is None or got["category"] != "言语理解与表达"


class TestFinalizeClassification:
    def test_auto_fills_both(self, db):
        data = {"subject": "xingce", "title": "逻辑判断", "card_front": "逻辑判断",
                "card_back": "加强削弱"}
        _finalize_classification(db, data)
        assert data["category"] == "判断推理"
        assert data["point_id"] == _point_id_by_name(db, "xingce", "逻辑判断")

    def test_explicit_category_conflict_with_point(self, db):
        """只给考点时，子类由考点反推；同时给非法子类必须 400。"""
        data = {"subject": "xingce", "title": "图形推理", "card_front": "图形推理",
                "point_id": _point_id_by_name(db, "xingce", "图形推理")}
        _finalize_classification(db, data)
        assert data["category"] == "判断推理"

        bad = {"subject": "xingce", "title": "图形推理", "card_front": "图形推理",
               "category": "方法技巧"}
        with pytest.raises(HTTPException):
            _finalize_classification(db, bad)

    def test_strict_false_reports_rejected(self, db):
        out = _resolve_classification(
            db, "xingce", "图形推理", "图形推理", None,
            explicit_category="方法技巧", strict=False)
        assert out["rejected_category"] == "方法技巧"
        assert out["category"] == "判断推理"   # 回退自动分类


class TestRuleInventory:
    def test_rules_cover_all_points(self, db):
        import json

        from app.models.models import MaterialClassificationRule
        rules = db.query(MaterialClassificationRule).all()

        def _has_point(cfg):
            if isinstance(cfg, str):
                try:
                    cfg = json.loads(cfg)
                except ValueError:
                    return False
            return isinstance(cfg, dict) and bool(cfg.get("point"))

        point_rules = [r for r in rules if _has_point(r.rule_config)]
        assert len(rules) >= 110, f"规则应 ≥110 条（16 子类 + 94 考点），实际 {len(rules)}"
        assert len(point_rules) >= 94, f"考点级规则应 ≥94，实际 {len(point_rules)}"

    def test_materials_carry_point(self, db):
        from app.models.models import StudyMaterial
        total = db.query(StudyMaterial).filter(StudyMaterial.type == "card").count()
        bound = (db.query(StudyMaterial)
                 .filter(StudyMaterial.type == "card",
                         StudyMaterial.point_id.isnot(None)).count())
        assert bound >= 35, f"已有考点绑定的卡片应 ≥35 张，实际 {bound}/{total}"
