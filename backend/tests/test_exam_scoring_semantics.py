"""考试评分口径 A：`is_scored` 与三个派生字段（2026-11-09 用户拍板）。

口径：`is_scored = 1` <=> 已交卷且**没有待人工评分的明细**（`is_correct IS NULL`）。
覆盖三条真实路径里的两条（老交卷端点 / 智能组卷），外加纯函数单测。

为什么要这三例：
1. 全客观全答 → 已评分、待评 0、已答 = 题数；
2. **只答 2 题也算已评分**（这正是老实现恒真式想表达、却表达不出来的口径；
   同时验证 `answered_count` 能反映"答了多少"）；
3. 主观题（`is_objective=0`）作答后 `is_correct` 留空 → 待人工评分 → `is_scored=0`，
   且 `manual_pending_count=1`（老实现会错记成 1）。
"""
from app.models.models import (
    ExamPaper,
    QuestionBank,
    QuestionType,
    PaperQuestionRelation,
)
from app.services.exam_scoring import finalize_record, scoring_flags


class _Detail:
    """最小明细替身：只带 is_correct / student_answer 两个字段。"""

    def __init__(self, is_correct, student_answer=""):
        self.is_correct = is_correct
        self.student_answer = student_answer


# ---------------------------------------------------------------- 纯函数单测

def test_scoring_flags_all_answered_objective():
    flags = scoring_flags([_Detail(1, "A"), _Detail(0, "B")], question_total=2)
    assert flags.is_scored is True
    assert flags.manual_pending_count == 0
    assert flags.answered_count == 2
    assert flags.question_total == 2


def test_scoring_flags_partial_answers_still_scored():
    """只答 2 / 97 题：分数结论已定 → 已评分，但已答数只有 2。"""
    details = [_Detail(0, "B"), _Detail(0, "A")] + [_Detail(0, "") for _ in range(95)]
    flags = scoring_flags(details, question_total=97)
    assert flags.is_scored is True
    assert flags.manual_pending_count == 0
    assert flags.answered_count == 2
    assert flags.question_total == 97


def test_scoring_flags_subjective_pending_blocks_scored():
    flags = scoring_flags([_Detail(1, "A"), _Detail(None, "我写的主观题答案")], question_total=2)
    assert flags.is_scored is False
    assert flags.manual_pending_count == 1
    assert flags.answered_count == 2


def test_scoring_flags_not_completed_is_unscored():
    flags = scoring_flags([_Detail(1, "A")], question_total=1, is_completed=False)
    assert flags.is_scored is False


def test_finalize_record_writes_four_fields():
    class _Rec:
        pass

    rec = _Rec()
    finalize_record(rec, [_Detail(1, "A"), _Detail(0, "")], question_total=2)
    assert (rec.is_scored, rec.manual_pending_count, rec.answered_count, rec.question_total) == (1, 0, 1, 2)


# ---------------------------------------------------------------- 接口级（真链路）

def _make_paper(db_session, subject_id, creator_id, objective_type_id, count=2,
                subjective_type_id=None):
    """造一张已发布试卷：count 道客观题（每题 10 分），可选加 1 道主观题。"""
    question_count = count + (1 if subjective_type_id else 0)
    paper = ExamPaper(
        paper_name="is_scored 口径试卷",
        paper_code="SCORED-A-001",
        subject_id=subject_id,
        composition_method="MANUAL",
        creator_id=creator_id,
        duration=120,
        total_score=100,
        difficulty=3,
        exam_type="SIMULATION",
        paper_type="PUBLISHED",
        question_count=question_count,
        max_attempts=5,
    )
    db_session.add(paper)
    db_session.commit()
    db_session.refresh(paper)

    ids = []
    order = 0
    for index in range(count):
        order += 1
        q = QuestionBank(
            subject_id=subject_id, type_id=objective_type_id,
            question_content=f"口径题 {index + 1}",
            options=[{"key": "A", "value": "1"}, {"key": "B", "value": "2"}],
            answer="A", answer_analysis="口径测试", difficulty=1, score=10,
            creator_id=creator_id, status=1, audit_status=1,
        )
        db_session.add(q)
        db_session.commit()
        db_session.refresh(q)
        db_session.add(PaperQuestionRelation(
            paper_id=paper.paper_id, question_id=q.question_id,
            question_order=order, question_score=10,
        ))
        ids.append(q.question_id)

    if subjective_type_id:
        order += 1
        q = QuestionBank(
            subject_id=subject_id, type_id=subjective_type_id,
            question_content="主观题：请简述……",
            options=[], answer="参考答案要点", answer_analysis="按点给分",
            difficulty=2, score=10, creator_id=creator_id, status=1, audit_status=1,
        )
        db_session.add(q)
        db_session.commit()
        db_session.refresh(q)
        db_session.add(PaperQuestionRelation(
            paper_id=paper.paper_id, question_id=q.question_id,
            question_order=order, question_score=10,
        ))
        ids.append(q.question_id)

    db_session.commit()
    return paper, ids


def _make_subjective_type(db_session):
    qtype = QuestionType(
        type_name="主观题-口径测试",
        type_code="SUBJ_TEST",
        subject_id=None,
        is_objective=0,
    )
    db_session.add(qtype)
    db_session.commit()
    db_session.refresh(qtype)
    return qtype


def test_submit_records_scored_and_counts(client, db_session, test_subject,
                                          test_question_type, auth_headers, test_user):
    """全客观题、全作答：`is_scored=1` + 派生字段齐全。"""
    paper, ids = _make_paper(db_session, test_subject.subject_id, test_user.user_id,
                             test_question_type.type_id, count=2)
    start = client.post(f"/api/exams/{paper.paper_id}/start", headers=auth_headers)
    assert start.status_code == 200, start.text
    record_id = start.json()["record_id"]

    resp = client.post(
        f"/api/exams/{record_id}/submit",
        headers=auth_headers,
        json={str(ids[0]): "A", str(ids[1]): "B"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["is_scored"] is True
    assert data["manual_pending_count"] == 0
    assert data["answered_count"] == 2
    assert data["question_total"] == 2

    from app.models.models import ExamRecord
    rec = db_session.query(ExamRecord).filter(ExamRecord.record_id == record_id).first()
    assert (rec.is_scored, rec.manual_pending_count, rec.answered_count, rec.question_total) == (1, 0, 2, 2)


def test_submit_partial_answers_still_scored(client, db_session, test_subject,
                                             test_question_type, auth_headers, test_user):
    """只答 1 / 3 题：仍然算「已评分」（分数结论已定），但 answered_count 只记 1。"""
    paper, ids = _make_paper(db_session, test_subject.subject_id, test_user.user_id,
                             test_question_type.type_id, count=3)
    start = client.post(f"/api/exams/{paper.paper_id}/start", headers=auth_headers)
    record_id = start.json()["record_id"]

    resp = client.post(
        f"/api/exams/{record_id}/submit",
        headers=auth_headers,
        json={str(ids[0]): "A"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["is_scored"] is True
    assert data["answered_count"] == 1
    assert data["question_total"] == 3


def test_submit_with_subjective_question_is_unscored(client, db_session, test_subject,
                                                     test_question_type, auth_headers,
                                                     test_user):
    """含主观题：`is_correct` 留 NULL → 待人工评分 → `is_scored=0`。"""
    subjective = _make_subjective_type(db_session)
    paper, ids = _make_paper(db_session, test_subject.subject_id, test_user.user_id,
                             test_question_type.type_id, count=1,
                             subjective_type_id=subjective.type_id)
    start = client.post(f"/api/exams/{paper.paper_id}/start", headers=auth_headers)
    record_id = start.json()["record_id"]

    resp = client.post(
        f"/api/exams/{record_id}/submit",
        headers=auth_headers,
        json={str(ids[0]): "A", str(ids[1]): "我答的主观题"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["is_scored"] is False
    assert data["manual_pending_count"] == 1
    assert data["question_total"] == 2
