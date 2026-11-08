# -*- coding: utf-8 -*-
"""A2-4（2026-11-08）：题目导入按 `paper_code` 归卷。

背景：`_get_or_create_import_paper` 原来只会"同名+同创建者复用"或
`generate_paper_code()` 新建一张，于是"上传真题（资料侧编号 GZ-2024-GK-T）→ 建卷 → 导题"
会生成 **第二张** 卷（PAPER-xxxx），两侧编号对不上。
现在支持传入资料侧编号：命中复用、未命中用该编号新建。
"""
import pytest

from app.models.models import ExamPaper
from app.services.question_ingest.tags import _get_or_create_import_paper


def _paper(db, *, code="GZ-TEST-1", name="资料侧试卷", ptype="DRAFT",
           subject_id=3, creator_id=None):
    p = ExamPaper(
        paper_name=name, paper_code=code, subject_id=subject_id,
        composition_method="IMPORT", creator_id=creator_id or 1,
        duration=120, total_score=100, difficulty=3,
        exam_type="SIMULATION", paper_type=ptype, question_count=0,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _tags(name="导入试卷名"):
    return {"paper_name": name, "exam_type": "真题", "subject_category": "公专"}


def test_reuses_paper_by_code(db_session, test_admin):
    existing = _paper(db_session, code="GZ-HIT-1", name="资料侧试卷", creator_id=test_admin.user_id)
    before = db_session.query(ExamPaper).count()

    got = _get_or_create_import_paper(
        db_session, test_admin, _tags("完全不同的标题"), "x.docx",
        question_count=6, paper_code="GZ-HIT-1")

    assert got is not None and got.paper_id == existing.paper_id
    assert got.paper_name == "资料侧试卷", "不得用导入时的标题覆盖已有卷"
    assert db_session.query(ExamPaper).count() == before, "不得新建第二张卷"


def test_revives_ended_paper_by_code(db_session, test_admin):
    ended = _paper(db_session, code="GZ-END-1", ptype="ENDED", creator_id=test_admin.user_id)
    got = _get_or_create_import_paper(db_session, test_admin, _tags(), "x.docx",
                                     question_count=6, paper_code="GZ-END-1")
    assert got.paper_id == ended.paper_id
    # 台账函数**不 commit**（由调用方事务决定成败），所以先在会话内断言，再提交后复核落库
    assert got.paper_type == "DRAFT", "ENDED 卷按编号命中时应复活为 DRAFT"
    db_session.commit()
    db_session.refresh(ended)
    assert ended.paper_type == "DRAFT"


def test_creates_with_given_code_when_missing(db_session, test_admin):
    got = _get_or_create_import_paper(db_session, test_admin, _tags(), "x.docx",
                                     question_count=6, paper_code="GZ-NEW-9")
    assert got.paper_code == "GZ-NEW-9", "未命中时应使用资料侧编号，而不是生成 PAPER-xxxx"
    assert got.paper_type == "DRAFT"


def test_without_code_keeps_legacy_generation(db_session, test_admin):
    got = _get_or_create_import_paper(db_session, test_admin, _tags(), "x.docx",
                                     question_count=6)
    assert got.paper_code and got.paper_code != "GZ-NEW-9"
    assert got.paper_type == "DRAFT"


def test_hit_by_code_ignores_question_threshold(db_session, test_admin):
    """命中已有卷时**不受 ≥5 题限制**：给已建好的卷补 2 道题也要能挂上。

    修复前：阈值检查在按编号命中之前，题数 <5 直接返回 None → 题目静默不挂卷。
    """
    existing = _paper(db_session, code="GZ-SMALL-1", creator_id=test_admin.user_id)
    got = _get_or_create_import_paper(db_session, test_admin, _tags(), "x.docx",
                                     question_count=2, paper_code="GZ-SMALL-1")
    assert got is not None and got.paper_id == existing.paper_id


def test_miss_by_code_still_respects_threshold(db_session, test_admin):
    """库里没有这个编号且题数 <5 → 不新建卷（避免产生空卷）。"""
    got = _get_or_create_import_paper(db_session, test_admin, _tags(), "x.docx",
                                     question_count=2, paper_code="GZ-SMALL-2")
    assert got is None
    assert db_session.query(ExamPaper).filter(
        ExamPaper.paper_code == "GZ-SMALL-2").first() is None


def test_below_threshold_creates_nothing(db_session, test_admin):
    assert _get_or_create_import_paper(db_session, test_admin, _tags(), "x.docx",
                                      question_count=4, paper_code="GZ-THR-1") is None
    assert db_session.query(ExamPaper).filter(
        ExamPaper.paper_code == "GZ-THR-1").first() is None
