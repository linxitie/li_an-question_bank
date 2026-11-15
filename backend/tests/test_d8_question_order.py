# -*- coding: utf-8 -*-
"""D8（2026-11-15）：分批补录造成的题序错位 —— 按题号对齐。

真机/历史：导入是"追加模型"（`next_question_order()` = max+1），一张卷分批补录时，
后补的题排到卷尾（2024 国考卷 #4 实测 100 条里 60 条错位）。现在导入后自动按题号对齐。
"""
from __future__ import annotations

import json

from app.models.models import ExamPaper, PaperQuestionRelation, QuestionBank
from app.services import paper_ingest
from app.services.paper_ingest import service as ingest_service
from app.services.paper_stats import normalize_question_orders, next_question_order


def _paper(db, code="D8-TEST-1"):
    p = ExamPaper(paper_code=code, paper_name="D8 测试卷", subject_id=3,
                  paper_type="DRAFT", composition_method="IMPORT",
                  duration=120, total_score=100, question_count=0, creator_id=2)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _q(db, no):
    q = QuestionBank(subject_id=3, type_id=1, question_content="题干",
                     options=[{"key": "A", "value": "甲"}], answer="A",
                     answer_analysis="", difficulty=3, score=1.0, status=1,
                     audit_status=1, creator_id=2,
                     question_number=(str(no) if no is not None else None))
    db.add(q)
    db.commit()
    db.refresh(q)
    return q


def _rel(db, paper, q, order):
    db.add(PaperQuestionRelation(paper_id=paper.paper_id, question_id=q.question_id,
                                 question_order=order, question_score=1.0))
    db.commit()
    return order


def _orders(db, paper_id):
    rows = (db.query(PaperQuestionRelation.question_order, QuestionBank.question_number)
              .join(QuestionBank, QuestionBank.question_id == PaperQuestionRelation.question_id)
              .filter(PaperQuestionRelation.paper_id == paper_id)
              .order_by(PaperQuestionRelation.question_order).all())
    return [(int(o), str(n) if n is not None else None) for o, n in rows]


# --------------------------------------------------------------- 服务函数
def test_aligned_paper_is_noop(db_session):
    p = _paper(db_session)
    for i in (1, 2, 3):
        _rel(db_session, p, _q(db_session, i), i)
    out = normalize_question_orders(db_session, p.paper_id)
    assert out == {"total": 3, "changed": 0, "skipped_reason": None}
    assert _orders(db_session, p.paper_id) == [(1, "1"), (2, "2"), (3, "3")]


def test_batch_appended_orders_are_fixed(db_session):
    """先导 1/2/5，再补 3/4 → 现在的 order 是 1,2,3,4,5，按题号应为 1,2,5,3,4。"""
    p = _paper(db_session)
    q1, q2, q5, q3, q4 = (_q(db_session, n) for n in (1, 2, 5, 3, 4))
    _rel(db_session, p, q1, 1)
    _rel(db_session, p, q2, 2)
    _rel(db_session, p, q5, 3)
    _rel(db_session, p, q3, 4)
    _rel(db_session, p, q4, 5)
    assert _orders(db_session, p.paper_id) == [(1, "1"), (2, "2"), (3, "5"), (4, "3"), (5, "4")]

    out = normalize_question_orders(db_session, p.paper_id)
    assert out["changed"] == 3          # 题号 5/3/4 的三条关系要挪位
    assert out["skipped_reason"] is None
    assert _orders(db_session, p.paper_id) == [(1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5")]


def test_non_numeric_number_is_skipped(db_session):
    """卷 #5 那种"没有题号"的卷：一条都不动（宁可不改也不误伤）。"""
    p = _paper(db_session)
    _rel(db_session, p, _q(db_session, 1), 1)
    _rel(db_session, p, _q(db_session, None), 2)
    before = _orders(db_session, p.paper_id)
    out = normalize_question_orders(db_session, p.paper_id)
    assert out == {"total": 2, "changed": 0, "skipped_reason": "non-numeric"}
    assert _orders(db_session, p.paper_id) == before


def test_duplicate_number_is_skipped(db_session):
    """题号重复（探针/解析卷常见）无法定义唯一顺序 → 不动。"""
    p = _paper(db_session)
    a, b = _q(db_session, 7), _q(db_session, 7)
    _rel(db_session, p, a, 1)
    _rel(db_session, p, b, 2)
    out = normalize_question_orders(db_session, p.paper_id)
    assert out == {"total": 2, "changed": 0, "skipped_reason": "duplicate"}
    assert _orders(db_session, p.paper_id) == [(1, "7"), (2, "7")]


def test_empty_paper(db_session):
    p = _paper(db_session)
    out = normalize_question_orders(db_session, p.paper_id)
    assert out == {"total": 0, "changed": 0, "skipped_reason": "empty"}


def test_dry_run_reports_without_writing(db_session):
    p = _paper(db_session)
    q1, q3 = _q(db_session, 1), _q(db_session, 3)
    _rel(db_session, p, q1, 1)
    _rel(db_session, p, q3, 2)
    out = normalize_question_orders(db_session, p.paper_id, apply=False)
    assert out["changed"] == 1
    db_session.rollback()
    assert _orders(db_session, p.paper_id) == [(1, "1"), (2, "3")]


def test_next_question_order_still_appends(db_session):
    """D8 不改追加语义（没题号时仍要靠它续号），只是导完再对齐一次。"""
    p = _paper(db_session)
    _rel(db_session, p, _q(db_session, 1), 1)
    _rel(db_session, p, _q(db_session, 2), 2)
    assert next_question_order(db_session, p.paper_id) == 3


def test_import_module_wires_normalizer():
    """导入模块必须真的拿到这个函数 —— 两处调用都在 try/except 里，
    名字写错会被吞成"规整没生效"（静默失败），所以单独锁一下。"""
    from app.api.v1.catalog import question_import as qi

    assert qi.normalize_question_orders is normalize_question_orders


# --------------------------------------------------------------- P3 导题写题号
def test_p3_confirm_writes_question_number(db_session):
    """导题入库的题现在也带题号（以前只有 order，没有 question_number）。"""
    from app.models.models import StudyMaterial

    m = StudyMaterial(subject="gongzhuan", type="paper", status=0,
                      title="D8 导题探针", creator_id=2)
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)

    draft = ingest_service.create_draft(db_session, m, ext="pdf", status="pending", actor_id=2)
    draft.items_json = json.dumps([
        {"no": n, "type": "单选", "stem": f"第{n}题（　　）。",
         "options": {"A": "甲", "B": "乙", "C": "丙", "D": "丁"},
         "shared": "", "section": 0, "images": [], "flags": []} for n in (1, 2, 3)],
        ensure_ascii=False)
    draft.item_count = 3
    db_session.commit()

    result = paper_ingest.confirm_draft(db_session, draft, actor_id=2)
    db_session.commit()
    nums = [r[0] for r in db_session.query(QuestionBank.question_number)
            .filter(QuestionBank.question_id.in_(result["question_ids"])).all()]
    assert nums == ["1", "2", "3"]
