# -*- coding: utf-8 -*-
"""P2（2026-11-09）考试开关 + 定时窗口。

用户决策（2026-11-09 批准）：
  ⑥ 考试开关支持定时（`exam_open_at` / `exam_close_at`，服务器本地时间）；
  ⑦ 关闭考试**保留历史成绩**（`exam_record` / `exam_answer_detail` 一律不动）；
  ⑧ 开关与「资料上架」相互独立；
  ⑨ 判定不靠定时任务 —— 每次读取时用当前时间算（进程重启/漏跑都不影响）。

S1–S3（用户确认）：S1 用服务器本地时间；S2 关闭时**正在作答的仍可继续/交卷**，
只禁止新开；S3 解析草稿保留 30 天（P3 用，本文件无关）。

覆盖：学生列表过滤、开考拦截（两条链路）、定时窗口三态、0 题保护、
关闭后历史成绩仍在、教师仍能看到已关闭卷、资料详情 `paper` 块的 answerable/exam。
"""
from datetime import datetime, timedelta

from app.models.models import (ExamPaper, ExamRecord, QuestionBank,
                               PaperQuestionRelation)


def _paper(db, subject_id, *, code="P2-T-1", questions=2,
           ptype="PUBLISHED", open_=1, open_at=None, close_at=None, duration=120):
    """造一张卷。`question_count` 与实际挂的题数保持一致，避免假数据。

    `creator_id` 是 NOT NULL：测试里不关心是谁建的，取库里第一个用户兜底
    （conftest 保证至少有一个 `test_user`）。
    """
    from app.models.models import SysUser

    creator = db.query(SysUser).order_by(SysUser.user_id).first()
    paper = ExamPaper(
        paper_name=f"P2 测试卷 {code}", paper_code=code,
        subject_id=subject_id, composition_method="MANUAL",
        creator_id=creator.user_id,
        duration=duration, total_score=100, difficulty=3,
        exam_type="SIMULATION", paper_type=ptype,
        question_count=questions, max_attempts=5,
        exam_open=open_, exam_open_at=open_at, exam_close_at=close_at,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return paper


def _add_questions(db, paper, subject_id, type_id, user_id, count=2):
    ids = []
    for i in range(count):
        q = QuestionBank(
            subject_id=subject_id, type_id=type_id,
            question_content=f"P2 题 {i + 1}",
            options=[{"key": "A", "value": "1"}, {"key": "B", "value": "2"}],
            answer="A", answer_analysis="回归用", difficulty=1, score=10,
            creator_id=user_id, status=1, audit_status=1,
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        db.add(PaperQuestionRelation(paper_id=paper.paper_id,
                                     question_id=q.question_id,
                                     question_order=i + 1, question_score=10))
        ids.append(q.question_id)
    db.commit()
    return ids


def _list_ids(client, headers):
    resp = client.get("/api/papers/list?page=1&page_size=100", headers=headers)
    assert resp.status_code == 200, resp.text
    return [p["paper_id"] for p in resp.json()["items"]]


# ------------------------------------------------------------------ 列表过滤
def test_student_list_hides_closed_paper(client, db_session, test_subject,
                                         auth_headers, test_admin):
    closed = _paper(db_session, test_subject.subject_id, code="P2-CLOSED", open_=0)
    opened = _paper(db_session, test_subject.subject_id, code="P2-OPEN")
    ids = _list_ids(client, auth_headers)
    assert opened.paper_id in ids
    assert closed.paper_id not in ids


def test_student_list_hides_zero_question_paper(client, db_session, test_subject,
                                               auth_headers):
    """0 题的已发布卷不该出现在学生列表里（#128 的坑：点进去考不了）。"""
    empty = _paper(db_session, test_subject.subject_id, code="P2-EMPTY", questions=0)
    full = _paper(db_session, test_subject.subject_id, code="P2-FULL")
    ids = _list_ids(client, auth_headers)
    assert full.paper_id in ids
    assert empty.paper_id not in ids


def test_student_list_hides_not_started_and_expired(client, db_session, test_subject,
                                                    auth_headers):
    now = datetime.now()
    future = _paper(db_session, test_subject.subject_id, code="P2-FUTURE",
                    open_at=now + timedelta(hours=2))
    past = _paper(db_session, test_subject.subject_id, code="P2-PAST",
                  close_at=now - timedelta(minutes=1))
    current = _paper(db_session, test_subject.subject_id, code="P2-NOW",
                     open_at=now - timedelta(hours=1),
                     close_at=now + timedelta(hours=1))
    ids = _list_ids(client, auth_headers)
    assert current.paper_id in ids
    assert future.paper_id not in ids
    assert past.paper_id not in ids


def test_teacher_list_keeps_closed_paper(client, db_session, test_subject,
                                         teacher_headers, test_teacher):
    """教师要看得到、管得到已关闭的卷（D3：可预览未发布）。"""
    closed = _paper(db_session, test_subject.subject_id, code="P2-T-CLOSED",
                    open_=0)
    assert closed.paper_id in _list_ids(client, teacher_headers)


# ------------------------------------------------------------------ 开考拦截
def test_start_blocked_when_closed(client, db_session, test_subject,
                                   test_question_type, auth_headers, test_user):
    paper = _paper(db_session, test_subject.subject_id, code="P2-S-CLOSED", open_=0)
    _add_questions(db_session, paper, test_subject.subject_id,
                   test_question_type.type_id, test_user.user_id)

    new = client.post(f"/api/exams/start?paper_id={paper.paper_id}", headers=auth_headers)
    legacy = client.post(f"/api/exams/{paper.paper_id}/start", headers=auth_headers)

    assert new.status_code == 400, new.text
    assert "已关闭" in new.json()["detail"]
    assert legacy.status_code == 400, legacy.text
    assert "已关闭" in legacy.json()["detail"]
    assert db_session.query(ExamRecord).count() == 0


def test_start_blocked_before_window(client, db_session, test_subject,
                                     test_question_type, auth_headers, test_user):
    paper = _paper(db_session, test_subject.subject_id, code="P2-S-FUTURE",
                   open_at=datetime.now() + timedelta(hours=2))
    _add_questions(db_session, paper, test_subject.subject_id,
                   test_question_type.type_id, test_user.user_id)
    resp = client.post(f"/api/exams/start?paper_id={paper.paper_id}", headers=auth_headers)
    assert resp.status_code == 400
    assert "开始时间" in resp.json()["detail"]


def test_start_blocked_after_window(client, db_session, test_subject,
                                    test_question_type, auth_headers, test_user):
    paper = _paper(db_session, test_subject.subject_id, code="P2-S-PAST",
                   close_at=datetime.now() - timedelta(minutes=1))
    _add_questions(db_session, paper, test_subject.subject_id,
                   test_question_type.type_id, test_user.user_id)
    resp = client.post(f"/api/exams/start?paper_id={paper.paper_id}", headers=auth_headers)
    assert resp.status_code == 400
    assert "已结束" in resp.json()["detail"]


def test_start_blocked_when_no_questions(client, db_session, test_subject,
                                         auth_headers):
    paper = _paper(db_session, test_subject.subject_id, code="P2-S-EMPTY",
                   questions=0)
    resp = client.post(f"/api/exams/start?paper_id={paper.paper_id}", headers=auth_headers)
    assert resp.status_code == 400
    assert "没有题目" in resp.json()["detail"]


def test_start_allowed_inside_window(client, db_session, test_subject,
                                     test_question_type, auth_headers, test_user):
    now = datetime.now()
    paper = _paper(db_session, test_subject.subject_id, code="P2-S-NOW",
                   open_at=now - timedelta(minutes=5),
                   close_at=now + timedelta(hours=1))
    _add_questions(db_session, paper, test_subject.subject_id,
                   test_question_type.type_id, test_user.user_id)
    resp = client.post(f"/api/exams/start?paper_id={paper.paper_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["exam_id"] > 0


def test_start_allowed_with_only_open_at(client, db_session, test_subject,
                                        test_question_type, auth_headers, test_user):
    """只设开始、不设结束（长期开放）→ 过了开始时间就能考。"""
    paper = _paper(db_session, test_subject.subject_id, code="P2-S-ONLY-OPEN",
                   open_at=datetime.now() - timedelta(days=1))
    _add_questions(db_session, paper, test_subject.subject_id,
                   test_question_type.type_id, test_user.user_id)
    resp = client.post(f"/api/exams/start?paper_id={paper.paper_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text


# ------------------------------------------------------------------ S2：进行中的仍可交卷
def test_in_progress_attempt_continues_after_close(client, db_session, test_subject,
                                                   test_question_type, auth_headers,
                                                   test_user):
    """S2：关闭考试时正在作答的学生仍可继续，只禁止新开。"""
    paper = _paper(db_session, test_subject.subject_id, code="P2-S2-CONT")
    questions = _add_questions(db_session, paper, test_subject.subject_id,
                               test_question_type.type_id, test_user.user_id)

    first = client.post(f"/api/exams/start?paper_id={paper.paper_id}", headers=auth_headers)
    assert first.status_code == 200, first.text
    exam_id = first.json()["exam_id"]

    # 管理员此刻关掉考试
    paper.exam_open = 0
    db_session.commit()

    again = client.post(f"/api/exams/start?paper_id={paper.paper_id}", headers=auth_headers)
    assert again.status_code == 200, again.text
    assert again.json()["exam_id"] == exam_id          # 继续原场，不新建

    # 交卷走的是 `/{record_id}/submit`（路由声明顺序在前，`{exam_id}/submit` 被它先匹配），
    # body 是 `{题目ID: 答案}` 的字典 —— 与答题卡页一致。
    submit = client.post(f"/api/exams/{exam_id}/submit", headers=auth_headers,
                         json={str(questions[0]): "A"})
    assert submit.status_code == 200, submit.text


def test_history_kept_after_close(client, db_session, test_subject,
                                  test_question_type, auth_headers, test_user):
    """决策 ⑦：关闭考试不动历史成绩。"""
    paper = _paper(db_session, test_subject.subject_id, code="P2-HIST")
    questions = _add_questions(db_session, paper, test_subject.subject_id,
                               test_question_type.type_id, test_user.user_id)
    start = client.post(f"/api/exams/start?paper_id={paper.paper_id}", headers=auth_headers)
    exam_id = start.json()["exam_id"]
    client.post(f"/api/exams/{exam_id}/submit", headers=auth_headers,
                json={str(questions[0]): "A"})

    paper.exam_open = 0
    db_session.commit()

    db_session.expire_all()
    record = db_session.query(ExamRecord).filter(
        ExamRecord.record_id == exam_id).one()
    assert record.is_completed == 1
    # 关闭后仍能继续看到这张卷（学生只读列表按 gate 过滤，但记录/成绩仍在库）
    assert db_session.query(ExamRecord).count() == 1


# ------------------------------------------------------------------ 契约单测（无 HTTP）
def test_contract_exam_state_reasons(test_subject):
    from app.api.v1.exam import contract

    now = datetime.now()
    assert contract.exam_state(None)["reason"] == "no_paper"

    class _P:  # 轻量替身：只测纯函数分支
        pass

    p = _P()
    p.paper_type = "DRAFT"; p.question_count = 5
    p.exam_open = 1; p.exam_open_at = None; p.exam_close_at = None
    assert contract.exam_state(p, now)["reason"] == "draft"

    p.paper_type = "PUBLISHED"; p.question_count = 0
    assert contract.exam_state(p, now)["reason"] == "no_questions"

    p.question_count = 5; p.exam_open = 0
    assert contract.exam_state(p, now)["reason"] == "closed"

    p.exam_open = 1; p.exam_open_at = now + timedelta(hours=1)
    assert contract.exam_state(p, now)["reason"] == "not_started"

    p.exam_open_at = None; p.exam_close_at = now - timedelta(minutes=1)
    assert contract.exam_state(p, now)["reason"] == "expired"

    p.exam_close_at = None
    state = contract.exam_state(p, now)
    assert state["reason"] == "ready" and state["ready"] is True


def test_contract_block_message_is_human_readable():
    from app.api.v1.exam import contract

    assert contract.exam_block_message({"reason": "ready"}) == ""
    assert "已关闭" in contract.exam_block_message({"reason": "closed"})
    text = contract.exam_block_message(
        {"reason": "not_started", "open_at": "2026-11-09 20:00:00"})
    assert "2026-11-09 20:00" in text


# ------------------------------------------------------------------ 资料详情 paper 块
def test_material_preview_reports_not_answerable(client, db_session, test_subject,
                                                 admin_headers, test_admin):
    """资料详情 `paper.answerable` 必须跟开关一致，且给出 exam 状态块。"""
    from app.models.models import StudyMaterial

    paper = _paper(db_session, test_subject.subject_id, code="P2-MAT-1",
                   ptype="PUBLISHED", open_=0)
    material = StudyMaterial(subject="gongzhuan", type="paper",
                             title="P2 资料", status=1, placement="both",
                             paper_code="P2-MAT-1", badge="P2-MAT-1")
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)

    body = client.get(f"/api/materials/admin/{material.material_id}/preview",
                      headers=admin_headers).json()
    block = body["paper"]
    assert block["exam_paper_id"] == paper.paper_id
    assert block["answerable"] is False
    assert block["exam"]["reason"] == "closed"
    assert "已关闭" in block["exam_hint"]

    paper.exam_open = 1
    db_session.commit()
    body = client.get(f"/api/materials/admin/{material.material_id}/preview",
                      headers=admin_headers).json()
    assert body["paper"]["answerable"] is True
    assert body["paper"]["exam"]["reason"] == "ready"
