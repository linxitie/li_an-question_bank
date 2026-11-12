# -*- coding: utf-8 -*-
"""模考交卷 → 错题本（2026-11-12 静默失效修复）。

事故：交卷代码在 `commit` 前用 `query(ExamAnswerDetail)` 查刚 `db.add()` 的明细，
而 session 是 `autoflush=False`（`core/database.py:45`）→ 恒 `None` → 错题本**从来没写过**
（实测 `wrong_question_personal` 0 行，而明细里有 6 条答错）。

本文件锁死三件事：
  1. **答错且作答**的题 → 恰好一条错题；
  2. **答对 / 空白（未作答）** 不进错题本（与结果页"未答≠错"同口径）；
  3. 同一题第二次再错 → 同一条 `error_count` 累加，不产生第二行。
"""
from app.models.models import (ExamPaper, PaperQuestionRelation, QuestionBank,
                               WrongQuestionPersonal)


def _paper_with_questions(db, admin, subject, qtype, count=3, code="WB-REG-1"):
    """一张已发布、题题有答案的卷（默认 3 题，答案都是 A）。"""
    paper = ExamPaper(
        paper_name=f"错题本回归卷 {code}", paper_code=code,
        subject_id=subject.subject_id, composition_method="MANUAL",
        creator_id=admin.user_id, duration=120, total_score=100, difficulty=3,
        exam_type="SIMULATION", paper_type="PUBLISHED",
        question_count=count, max_attempts=5, exam_open=1,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)

    questions = []
    for i in range(count):
        q = QuestionBank(
            subject_id=subject.subject_id, type_id=qtype.type_id,
            question_content=f"错题本回归题 {i + 1}",
            options=[{"key": "A", "value": "1"}, {"key": "B", "value": "2"},
                     {"key": "C", "value": "3"}],
            answer="A", answer_analysis="回归用", difficulty=1, score=10,
            creator_id=admin.user_id, status=1, audit_status=1,
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        db.add(PaperQuestionRelation(paper_id=paper.paper_id,
                                     question_id=q.question_id,
                                     question_order=i + 1, question_score=10))
        questions.append(q)
    db.commit()
    return paper, questions


def _start_and_submit(client, headers, paper, payload):
    start = client.post(f"/api/exams/start?paper_id={paper.paper_id}", headers=headers)
    assert start.status_code == 200, start.text
    record_id = start.json()["exam_id"]
    resp = client.post(f"/api/exams/{record_id}/submit", headers=headers, json=payload)
    assert resp.status_code == 200, resp.text
    return record_id, resp


def test_only_answered_wrong_goes_to_wrong_book(client, db_session, auth_headers,
                                                test_admin, test_subject, test_question_type):
    """答对 1 / 答错 1 / 空白 1 → 只收"答错且作答"那一条。"""
    paper, questions = _paper_with_questions(db_session, test_admin, test_subject,
                                             test_question_type)
    payload = {
        str(questions[0].question_id): "A",   # 对
        str(questions[1].question_id): "B",   # 错（且作答）
        str(questions[2].question_id): "",    # 空白（不算错题）
    }
    _start_and_submit(client, auth_headers, paper, payload)

    db_session.expire_all()
    rows = db_session.query(WrongQuestionPersonal).all()
    assert len(rows) == 1, [(r.question_id, r.user_answer) for r in rows]
    row = rows[0]
    assert row.question_id == questions[1].question_id
    assert row.collection_type == "WRONG"
    assert row.user_answer == "B"
    assert row.error_count == 1
    assert row.subject_id == test_subject.subject_id


def test_all_correct_or_blank_writes_nothing(client, db_session, auth_headers,
                                             test_admin, test_subject, test_question_type):
    """全对 / 全空都不该产生错题（原来会把空白也当错题）。"""
    paper, questions = _paper_with_questions(db_session, test_admin, test_subject,
                                             test_question_type, count=2)
    payload = {str(questions[0].question_id): "A", str(questions[1].question_id): "A"}
    _start_and_submit(client, auth_headers, paper, payload)
    db_session.expire_all()
    assert db_session.query(WrongQuestionPersonal).count() == 0

    paper2, questions2 = _paper_with_questions(db_session, test_admin, test_subject,
                                               test_question_type, count=2, code="WB-REG-2")
    # 换一张卷（避免 max_attempts 之外的因素），全空白提交
    _start_and_submit(client, auth_headers, paper2,
                      {str(questions2[0].question_id): "", str(questions2[1].question_id): ""})
    db_session.expire_all()
    assert db_session.query(WrongQuestionPersonal).count() == 0


def test_wrong_twice_accumulates_one_row(client, db_session, auth_headers,
                                         test_admin, test_subject, test_question_type):
    """同一题考两次都错 → 同一行 error_count=2（不产生第二行）。"""
    paper, questions = _paper_with_questions(db_session, test_admin, test_subject,
                                             test_question_type, count=1)
    qid = questions[0].question_id
    _start_and_submit(client, auth_headers, paper, {str(qid): "B"})
    _start_and_submit(client, auth_headers, paper, {str(qid): "C"})

    db_session.expire_all()
    rows = db_session.query(WrongQuestionPersonal).all()
    assert len(rows) == 1
    assert rows[0].error_count == 2
    assert rows[0].user_answer == "C"      # 最近一次作答覆盖
