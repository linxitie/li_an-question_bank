# -*- coding: utf-8 -*-
"""交卷结果契约 + 答案覆盖率闸门（2026-11-11 用户真机验收后补）。

背景：PC 答题页交卷弹窗把 `scored_count`（参与评分题数）当"答对数"，显示成 97/0；
逐题回顾因为没有答案字段，一律显示"错误"。修复的第一步是**后端把准数交出来**：
`correct_count / wrong_count / unanswered_count / details[]`。

另外用户批准了「没补答案的卷不许开考」，这里同时钉住那道闸门。
"""
from app.models.models import (ExamPaper, PaperQuestionRelation, QuestionBank,
                               QuestionType)

from app.services.exam_scoring import scoring_flags


def _make_paper(db, subject_id, type_id, user_id, *, code="RES-1",
                answers=("A", "B"), count=None):
    """造卷：默认 2 道题、答案 A/B；`answers` 传 None 表示这道题没答案。"""
    answers = list(answers) if answers else []
    count = count if count is not None else len(answers)
    paper = ExamPaper(
        paper_name=f"结果契约卷 {code}", paper_code=code, subject_id=subject_id,
        composition_method="MANUAL", creator_id=user_id, duration=120,
        total_score=100, difficulty=3, exam_type="SIMULATION",
        paper_type="PUBLISHED", question_count=count, max_attempts=5,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)

    ids = []
    for i in range(count):
        ans = answers[i] if i < len(answers) else ""
        q = QuestionBank(
            subject_id=subject_id, type_id=type_id,
            question_content=f"契约题 {i + 1}",
            options=[{"key": "A", "value": "甲"}, {"key": "B", "value": "乙"}],
            # 注意：`question_bank.answer` 是 NOT NULL，所以"没答案"用空串表示
            answer=ans, answer_analysis="契约用", difficulty=1, score=1,
            creator_id=user_id, status=1, audit_status=1,
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        db.add(PaperQuestionRelation(paper_id=paper.paper_id,
                                     question_id=q.question_id,
                                     question_order=i + 1, question_score=1))
        ids.append(q.question_id)
    db.commit()
    return paper, ids


def test_submit_returns_correct_counts_and_details(client, db_session, test_subject,
                                                   test_question_type, auth_headers,
                                                   test_user):
    """答对 1 题、另 1 题空着：回包必须给出 1/1/1 与逐题 details。"""
    paper, ids = _make_paper(db_session, test_subject.subject_id,
                             test_question_type.type_id, test_user.user_id,
                             code="RES-COUNTS")
    start = client.post(f"/api/exams/{paper.paper_id}/start", headers=auth_headers)
    assert start.status_code == 200, start.text
    record_id = start.json()["record_id"]

    resp = client.post(f"/api/exams/{record_id}/submit", headers=auth_headers,
                       json={str(ids[0]): "A", str(ids[1]): ""})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["correct_count"] == 1
    # wrong_count 只算"作答了但答错"，空白归 unanswered，三个数互不重叠
    assert data["wrong_count"] == 0
    assert data["unanswered_count"] == 1
    assert data["question_total"] == 2
    assert data["correct_count"] + data["wrong_count"] + data["unanswered_count"] == data["question_total"]

    details = {d["question_id"]: d for d in data["details"]}
    assert details[ids[0]]["is_correct"] is True
    assert details[ids[0]]["correct_answer"] == "A"
    assert details[ids[1]]["is_correct"] is False
    assert details[ids[1]]["correct_answer"] == "B"
    assert details[ids[1]]["student_answer"] == ""


def test_submit_response_keeps_scored_count_semantics(client, db_session, test_subject,
                                                       test_question_type, auth_headers,
                                                       test_user):
    """`scored_count` 仍是"参与评分题数"，不是答对数（老字段语义不变，防再次误用）。"""
    paper, ids = _make_paper(db_session, test_subject.subject_id,
                             test_question_type.type_id, test_user.user_id,
                             code="RES-SCORED")
    record_id = client.post(f"/api/exams/{paper.paper_id}/start",
                            headers=auth_headers).json()["record_id"]
    data = client.post(f"/api/exams/{record_id}/submit", headers=auth_headers,
                       json={str(ids[0]): "A", str(ids[1]): "B"}).json()["data"]

    assert data["correct_count"] == 2
    assert data["scored_count"] == 2          # 两题都提交了 → 参与评分 2 题
    assert data["scored_count"] != 0


class TestAnswerGate:
    """没补答案的卷不许开考（用户 2026-11-11 批准）。"""

    def test_start_blocked_when_no_answers(self, client, db_session, test_subject,
                                          test_question_type, auth_headers, test_user):
        paper, _ = _make_paper(db_session, test_subject.subject_id,
                               test_question_type.type_id, test_user.user_id,
                               code="RES-NOANS", answers=(), count=1)
        resp = client.post(f"/api/exams/{paper.paper_id}/start", headers=auth_headers)
        assert resp.status_code == 400, resp.text
        assert "正确答案" in resp.json()["detail"]

    def test_start_blocked_when_answers_incomplete(self, client, db_session, test_subject,
                                                   test_question_type, auth_headers, test_user):
        paper, _ = _make_paper(db_session, test_subject.subject_id,
                               test_question_type.type_id, test_user.user_id,
                               code="RES-PARTANS", answers=("A",), count=2)
        resp = client.post(f"/api/exams/{paper.paper_id}/start", headers=auth_headers)
        assert resp.status_code == 400, resp.text
        detail = resp.json()["detail"]
        assert "正确答案" in detail and "还差 1 题" in detail

    def test_exam_list_reports_missing_answers(self, client, db_session, test_subject,
                                               test_question_type, auth_headers, test_user):
        paper, _ = _make_paper(db_session, test_subject.subject_id,
                               test_question_type.type_id, test_user.user_id,
                               code="RES-LIST-NOANS", answers=(), count=1)
        resp = client.get("/api/exams/list?page=1&page_size=100", headers=auth_headers)
        item = next(i for i in resp.json()["data"] if i["paper_id"] == paper.paper_id)
        assert item["answerable"] is False
        assert item["exam"]["reason"] == "no_answers"
        assert item["exam"]["answers_missing"] == 1
        assert "正确答案" in item["exam_hint"]


def test_scoring_flags_unchanged_by_gate():
    """闸门只影响"能不能开考"，不改变评分口径（A 口径仍由 exam_scoring 决定）。"""

    class _D:
        def __init__(self, ok, ans=""):
            self.is_correct = ok
            self.student_answer = ans

    flags = scoring_flags([_D(1, "A"), _D(0, "")], question_total=2)
    assert flags.is_scored is True
    assert flags.answered_count == 1
    assert flags.manual_pending_count == 0
