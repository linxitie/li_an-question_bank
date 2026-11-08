# -*- coding: utf-8 -*-
"""R8 回归（2026-11-08）：试卷预览接口必须按 `paper_type` 判可见性。

补丁前实测：学生 token 请求 `GET /api/exams/preview/{已回收卷}` 返回 **200**，
因为 `ExamService.get_exam_preview` 只校验"卷存在"。草稿卷一旦配了题，
学生就能直读题干与选项（不含答案/解析）。

覆盖两条预览口：
- `GET /api/exams/preview/{paper_id}`（本次修补的主口子）
- `GET /api/papers/{paper_id}/preview`（原本就有角色守卫，做回归防退化）
教师/管理员仍可预览未发布卷（避免把内部预览一起堵死）。
"""
from app.models.models import ExamPaper, PaperQuestionRelation, QuestionBank


def _make_paper(db_session, subject_id, type_id, creator_id, *,
                paper_type="PUBLISHED", code="R8-PREVIEW-1", name="R8 预览卷", count=2):
    paper = ExamPaper(
        paper_name=name,
        paper_code=code,
        subject_id=subject_id,
        composition_method="MANUAL",
        creator_id=creator_id,
        duration=120,
        total_score=100,
        difficulty=3,
        exam_type="SIMULATION",
        paper_type=paper_type,
        question_count=count,
        max_attempts=5,
    )
    db_session.add(paper)
    db_session.commit()
    db_session.refresh(paper)

    for index in range(count):
        question = QuestionBank(
            subject_id=subject_id,
            type_id=type_id,
            question_content=f"R8 预览题 {index + 1}",
            options=[{"key": "A", "value": "1"}, {"key": "B", "value": "2"}],
            answer="A",
            answer_analysis="预览不得包含答案",
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
    db_session.commit()
    return paper


def _paths(paper_id):
    return (f"/api/exams/preview/{paper_id}", f"/api/papers/{paper_id}/preview")


def test_student_can_preview_published(client, db_session, test_subject,
                                       test_question_type, test_user, auth_headers):
    paper = _make_paper(db_session, test_subject.subject_id,
                        test_question_type.type_id, test_user.user_id,
                        paper_type="PUBLISHED", code="R8-PUB-1")
    for path in _paths(paper.paper_id):
        resp = client.get(path, headers=auth_headers)
        assert resp.status_code == 200, (path, resp.text)
        body = resp.json()
        assert len(body["questions"]) == 2
        first = body["questions"][0]
        # 预览可以给题干/选项，但绝不能带答案与解析
        assert "question_content" in first and "options" in first
        assert "answer" not in first and "answer_analysis" not in first


def test_student_blocked_on_draft(client, db_session, test_subject,
                                  test_question_type, test_user, auth_headers):
    paper = _make_paper(db_session, test_subject.subject_id,
                        test_question_type.type_id, test_user.user_id,
                        paper_type="DRAFT", code="R8-DRAFT-1", name="R8 草稿卷")
    for path in _paths(paper.paper_id):
        resp = client.get(path, headers=auth_headers)
        assert resp.status_code == 404, (path, resp.status_code, resp.text)


def test_student_blocked_on_ended(client, db_session, test_subject,
                                  test_question_type, test_user, auth_headers):
    paper = _make_paper(db_session, test_subject.subject_id,
                        test_question_type.type_id, test_user.user_id,
                        paper_type="ENDED", code="R8-ENDED-1", name="R8 回收站卷")
    for path in _paths(paper.paper_id):
        resp = client.get(path, headers=auth_headers)
        assert resp.status_code == 404, (path, resp.status_code, resp.text)


def test_teacher_level1_matches_papers_guard(client, db_session, test_subject,
                                             test_question_type, test_user, teacher_headers):
    """教师（实测 `role_level=1`，与 papers.py 的 `role_level < 2` 判据一致）也被拦。

    依据真实数据：`sys_user` 里 student=0 / teacher=1 / admin=3，
    `catalog/papers.py:229` 用的就是 `< 2`，所以两条预览口对教师口径相同。
    教师预览自己的卷走教师端端点（teacher_papers 等），不走这两个学生口。
    若要放行教师，需同时改 papers.py 的阈值（建议单独立项，别在本次补丁里悄悄改）。
    """
    paper = _make_paper(db_session, test_subject.subject_id,
                        test_question_type.type_id, test_user.user_id,
                        paper_type="DRAFT", code="R8-DRAFT-2", name="R8 教师草稿")
    for path in _paths(paper.paper_id):
        resp = client.get(path, headers=teacher_headers)
        assert resp.status_code == 404, (path, resp.status_code, resp.text)


def test_admin_can_preview_ended(client, db_session, test_subject,
                                 test_question_type, test_user, admin_headers):
    paper = _make_paper(db_session, test_subject.subject_id,
                        test_question_type.type_id, test_user.user_id,
                        paper_type="ENDED", code="R8-ENDED-2", name="R8 管理员回收站")
    for path in _paths(paper.paper_id):
        resp = client.get(path, headers=admin_headers)
        assert resp.status_code == 200, (path, resp.status_code, resp.text)


def test_missing_paper_is_404(client, db_session, test_subject,
                              test_question_type, test_user, auth_headers):
    _make_paper(db_session, test_subject.subject_id,
                test_question_type.type_id, test_user.user_id,
                paper_type="PUBLISHED", code="R8-PUB-2", name="R8 占位", count=1)
    for path in ("/api/exams/preview/999999", "/api/papers/999999/preview"):
        resp = client.get(path, headers=auth_headers)
        assert resp.status_code == 404, (path, resp.status_code)
