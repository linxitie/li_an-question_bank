# -*- coding: utf-8 -*-
"""教师成绩总览接口回归（2026-11-16，P4 发现并修复的 500）。

**为什么有这个文件**：`GET /api/teacher/scores/overview` 在本仓库是**只要有一条已交卷记录就 500**。
根因：`schemas.teacher.StudentScoreItem` 的 `xingce_score / shenlun_score / police_score`
写成 `Optional[float]` 但没给默认值 —— pydantic v2 里这仍是**必填**，
而 handler（`api/v1/platform/teacher.py::get_score_overview`）不传这三个字段，
于是每次构造都抛 `ValidationError`，被全局错误处理器包成 500。

修复：schema 补 `= None`（分科分数系统目前未拆分统计）。本文件把"有记录/无记录"两条路径锁住，
避免以后有人再给 Optional 字段加必填、或改 handler 时又把参数漏掉。
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.models.models import ExamPaper, ExamRecord, QuestionSubject, SysUser
from app.core.security import get_password_hash


@pytest.fixture
def student_with_class(db_session):
    student = SysUser(
        user_no="stu-score-1",
        username="成绩学生甲",
        password=get_password_hash("stu123456"),
        phone="13900001111",
        user_type="student",
        role_level=1,
        status=1,
        class_name="一班",
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)
    return student


@pytest.fixture
def completed_paper(db_session):
    subject = db_session.query(QuestionSubject).first()
    if subject is None:
        subject = QuestionSubject(subject_name="公专", subject_code="gongzhuan")
        db_session.add(subject)
        db_session.commit()
        db_session.refresh(subject)
    paper = ExamPaper(
        paper_name="成绩总览回归卷",
        paper_code="SCORE-REG-1",
        subject_id=subject.subject_id,
        composition_method="MANUAL",
        creator_id=1,
        duration=120,
        total_score=100,
        question_count=10,
        paper_type="PUBLISHED",
    )
    db_session.add(paper)
    db_session.commit()
    db_session.refresh(paper)
    return paper


def _completed_record(db_session, student, paper, score=72.5):
    record = ExamRecord(
        paper_id=paper.paper_id,
        user_id=student.user_id,
        exam_type="MOCK_EXAM",
        is_completed=1,
        is_scored=1,
        total_score=score,
        duration_used=900,
        start_time=datetime.now(),
        submit_time=datetime.now(),
        attempt_count=1,
    )
    db_session.add(record)
    db_session.commit()
    db_session.refresh(record)
    return record


def test_overview_returns_200_when_records_exist(client, teacher_headers, db_session,
                                                student_with_class, completed_paper):
    """核心回归：有已交卷记录时必须是 200（修复前是 500）。"""
    _completed_record(db_session, student_with_class, completed_paper, 72.5)

    r = client.get("/api/teacher/scores/overview", headers=teacher_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] is True
    assert body["total_students"] >= 1
    assert body["max_score"] >= 72.5
    assert body["min_score"] <= 72.5

    # 分布：5 段，计数之和 == 学生数
    counts = body["distribution"]["student_counts"]
    assert len(counts) == 5
    assert sum(counts) == body["total_students"]

    # 明细：分科分数缺失为 None（而不是报错）
    rows = body["student_scores"]
    assert rows, body
    top = rows[0]
    assert top["user_name"] == "成绩学生甲"
    assert top["class_name"] == "一班"
    assert top["xingce_score"] is None
    assert top["shenlun_score"] is None
    assert top["police_score"] is None


def test_overview_returns_200_when_no_records(client, teacher_headers, db_session):
    """无记录时也要 200（空分布），不能 500。"""
    r = client.get("/api/teacher/scores/overview", headers=teacher_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_students"] == 0
    assert body["distribution"]["student_counts"] == [0, 0, 0, 0, 0]
    assert body["student_scores"] == []
