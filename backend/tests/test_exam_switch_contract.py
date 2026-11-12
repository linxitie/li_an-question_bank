# -*- coding: utf-8 -*-
"""考试开关/定时**写端点回包契约**（2026-11-12 缺陷回归）。

事故（用户真机截图）：
  点一下开关 → 行显示「已关闭」，但按钮仍亮着、再点也打不开、设置定时"没用"。
根因：
  `PUT /api/materials/admin/{id}/exam-open` 与 `.../exam-window` 只回
  `contract.exam_state()`，比列表用的 `exam_gate.state_of()` **少三个字段**
  （`manual_open` / `paper_code` / `paper_id`）。前端 `row.exam = state` 整体替换后：
    · `manual_open !== 0` → `undefined !== 0` 恒真 → 开关永远渲染"开"；
    · `manual_open === 0` → 恒假 → 下一次点击永远发 `open:false`，再也打不开。
修法：`exam_gate._enrich()` 成为唯一补字段的地方，`state_of/set_open/set_window` 三处共用。

本文件只钉两件事：
  1. 两个写端点的 `exam` 回包**与列表同形**（键集合一致，含 `manual_open`）；
  2. 关 → 开**可逆**，定时设置/清空不会把手动总闸弄丢。
"""
from datetime import datetime, timedelta

from app.models.models import (ExamPaper, PaperQuestionRelation, QuestionBank,
                               StudyMaterial)

CODE = "SW-CONTRACT-1"


def _material_with_paper(db, admin, subject, qtype, *, code=CODE, questions=2,
                         open_=1):
    """造一张已发布、有题有答案的卷 + 对应「试卷资料」（投放位 both）。"""
    paper = ExamPaper(
        paper_name=f"开关契约卷 {code}", paper_code=code,
        subject_id=subject.subject_id, composition_method="MANUAL",
        creator_id=admin.user_id, duration=120, total_score=100, difficulty=3,
        exam_type="SIMULATION", paper_type="PUBLISHED",
        question_count=questions, max_attempts=5, exam_open=open_,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)

    for i in range(questions):
        q = QuestionBank(
            subject_id=subject.subject_id, type_id=qtype.type_id,
            question_content=f"开关契约题 {i + 1}",
            options=[{"key": "A", "value": "1"}, {"key": "B", "value": "2"}],
            answer="A", answer_analysis="回归用", difficulty=1, score=50,
            creator_id=admin.user_id, status=1, audit_status=1,
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        db.add(PaperQuestionRelation(paper_id=paper.paper_id,
                                     question_id=q.question_id,
                                     question_order=i + 1, question_score=50))
    db.commit()

    material = StudyMaterial(
        subject="gongzhuan", type="paper", title=f"开关契约资料 {code}",
        status=1, placement="both", paper_code=code, badge=code,
        creator_id=admin.user_id,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return material, paper


def _list_exam(client, admin_headers, material_id):
    """列表里的 exam 块 —— 这是"完整形状"的基准。"""
    resp = client.get("/api/materials/admin/list?type=paper&page=1&page_size=50",
                      headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    rows = body.get("items") or (body.get("data") or {}).get("items") or []
    for item in rows:
        if item["id"] == material_id:
            return item["exam"]
    raise AssertionError(f"material {material_id} 不在管理端试卷列表里")


def _put_open(client, headers, material_id, open_):
    return client.put(f"/api/materials/admin/{material_id}/exam-open",
                      headers=headers, json={"open": open_})


def _put_window(client, headers, material_id, open_at=None, close_at=None):
    return client.put(f"/api/materials/admin/{material_id}/exam-window",
                      headers=headers,
                      json={"open_at": open_at, "close_at": close_at})


def test_close_response_is_list_shaped(client, db_session, admin_headers,
                                       test_admin, test_subject, test_question_type):
    """关闭：回包必须带 manual_open/paper_code/paper_id，且与列表键集合一致。"""
    material, paper = _material_with_paper(db_session, test_admin, test_subject,
                                           test_question_type)
    listed = _list_exam(client, admin_headers, material.material_id)

    resp = _put_open(client, admin_headers, material.material_id, False)
    assert resp.status_code == 200, resp.text
    state = resp.json()["exam"]

    assert state["manual_open"] == 0, "关掉后 manual_open 必须是 0（前端开关只认它）"
    assert state["paper_code"] == CODE
    assert state["paper_id"] == paper.paper_id
    assert state["reason"] == "closed"
    assert set(state.keys()) == set(listed.keys()), "写端点回包必须与列表同形"

    # 落库也要对（关是持久化的，不只是回包好看）
    db_session.expire_all()
    row = db_session.query(ExamPaper).filter(ExamPaper.paper_id == paper.paper_id).one()
    assert row.exam_open == 0


def test_reopen_after_close_is_reversible(client, db_session, admin_headers,
                                          test_admin, test_subject, test_question_type):
    """关 → 开可逆：第二次点击必须能真的打开（事故里永远发关闭，打不开）。"""
    material, paper = _material_with_paper(db_session, test_admin, test_subject,
                                           test_question_type)
    assert _put_open(client, admin_headers, material.material_id, False).json()["exam"]["manual_open"] == 0

    resp = _put_open(client, admin_headers, material.material_id, True)
    assert resp.status_code == 200, resp.text
    state = resp.json()["exam"]
    assert state["manual_open"] == 1
    assert state["ready"] is True
    assert state["reason"] == "ready"
    assert state["paper_code"] == CODE

    db_session.expire_all()
    row = db_session.query(ExamPaper).filter(ExamPaper.paper_id == paper.paper_id).one()
    assert row.exam_open == 1


def test_window_save_keeps_manual_open(client, db_session, admin_headers,
                                       test_admin, test_subject, test_question_type):
    """设定时：回包带窗口 + 手动闸原值，且 reason 变成 not_started。"""
    material, paper = _material_with_paper(db_session, test_admin, test_subject,
                                           test_question_type)
    listed = _list_exam(client, admin_headers, material.material_id)

    open_at = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
    close_at = (datetime.now() + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M")
    resp = _put_window(client, admin_headers, material.material_id, open_at, close_at)
    assert resp.status_code == 200, resp.text
    state = resp.json()["exam"]

    assert state["manual_open"] == 1, "定时不该把手动总闸弄丢"
    assert state["open_at"] and state["close_at"]
    assert state["reason"] == "not_started"
    assert set(state.keys()) == set(listed.keys())


def test_window_clear_restores_ready(client, db_session, admin_headers,
                                     test_admin, test_subject, test_question_type):
    """清空定时：两端 None、手动闸不变、回到可进入。"""
    material, _ = _material_with_paper(db_session, test_admin, test_subject,
                                       test_question_type)
    open_at = (datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M")
    _put_window(client, admin_headers, material.material_id, open_at, None)

    resp = _put_window(client, admin_headers, material.material_id, None, None)
    assert resp.status_code == 200, resp.text
    state = resp.json()["exam"]
    assert state["open_at"] is None and state["close_at"] is None
    assert state["manual_open"] == 1
    assert state["reason"] == "ready"
