"""P0 回归：考试「开始 / 取题 / 交卷」三处 500（2026-10-26 main 分支问题清单）。

三处根因都在 `backend/app/api/v1/exam/exams.py`：
- 取题引用 `PaperQuestionRelation` 未导入 → NameError；
- 交卷引用 `QuestionType` 未导入（且函数内 `from ..models import QuestionType` 路径错误）；
- 开始考试返回 ORM 对象，但 `ExamRecordResponse` 用 Pydantic v1 的 `orm_mode`，
  v2 下等于没有 `from_attributes`，序列化即 500。
"""
from app.models.models import ExamPaper, PaperQuestionRelation, QuestionBank


def _make_published_paper(db_session, subject_id, type_id, creator_id, count=2):
    """造一张已发布试卷：count 道单选客观题，每题 10 分。"""
    paper = ExamPaper(
        paper_name="P0 回归试卷",
        paper_code="P0-REG-001",
        subject_id=subject_id,
        composition_method="MANUAL",
        creator_id=creator_id,
        duration=120,
        total_score=100,
        difficulty=3,
        exam_type="SIMULATION",
        paper_type="PUBLISHED",
        question_count=count,
        max_attempts=5,
    )
    db_session.add(paper)
    db_session.commit()
    db_session.refresh(paper)

    question_ids = []
    for index in range(count):
        question = QuestionBank(
            subject_id=subject_id,
            type_id=type_id,
            question_content=f"P0 回归题 {index + 1}",
            options=[{"key": "A", "value": "1"}, {"key": "B", "value": "2"}],
            answer="A",
            answer_analysis="回归用",
            difficulty=1,
            score=10,
            creator_id=creator_id,
            status=1,
            audit_status=1,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)
        db_session.add(PaperQuestionRelation(
            paper_id=paper.paper_id,
            question_id=question.question_id,
            question_order=index + 1,
            question_score=10,
        ))
        question_ids.append(question.question_id)
    db_session.commit()
    return paper, question_ids


def test_get_paper_questions_no_name_error(client, db_session, test_subject,
                                           test_question_type, test_user):
    """取题端点：PaperQuestionRelation / QuestionType 必须可解析（原 NameError）。"""
    paper, question_ids = _make_published_paper(
        db_session, test_subject.subject_id, test_question_type.type_id,
        test_user.user_id
    )

    response = client.get(f"/api/exams/{paper.paper_id}/questions")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["question_count"] == 2
    assert [q["question_id"] for q in data["questions"]] == question_ids


def test_start_exam_serializes_exam_record(client, db_session, test_subject,
                                           test_question_type, auth_headers,
                                           test_user):
    """开始考试：ORM 记录必须能按 ExamRecordResponse 序列化（原 orm_mode 500）。"""
    paper, _ = _make_published_paper(
        db_session, test_subject.subject_id, test_question_type.type_id,
        test_user.user_id
    )

    response = client.post(f"/api/exams/{paper.paper_id}/start", headers=auth_headers)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["record_id"] > 0
    assert data["paper_id"] == paper.paper_id
    assert data["is_completed"] is False or data["is_completed"] == 0


def test_submit_answers_scores_objective_questions(client, db_session, test_subject,
                                                   test_question_type, auth_headers,
                                                   test_user):
    """交卷：QuestionType 评分分支必须可执行（原函数内错误相对导入 500）。"""
    paper, question_ids = _make_published_paper(
        db_session, test_subject.subject_id, test_question_type.type_id,
        test_user.user_id
    )
    start = client.post(f"/api/exams/{paper.paper_id}/start", headers=auth_headers)
    assert start.status_code == 200, start.text
    record_id = start.json()["record_id"]

    response = client.post(
        f"/api/exams/{record_id}/submit",
        headers=auth_headers,
        json={str(question_ids[0]): "A", str(question_ids[1]): "B"},
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["record_id"] == record_id
    assert data["total_score"] == 10.0  # 第 1 题答对，第 2 题答错
    assert data["scored_count"] == 2
