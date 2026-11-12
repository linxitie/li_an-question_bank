# -*- coding: utf-8 -*-
"""补答案上传回包契约（2026-11-12 缺陷回归）。

事故：`POST /admin/papers/{id}/answers/parse` 回的是 `draft_payload(db, draft)`，
`with_items` 默认 False → **没有 items**。前端上传后直接读 `data.items`，于是：
提示「已解析 97 题」，抽屉里却是 `识别答案 0/0`、表格空、按钮「确认写入 0 题」。
关掉抽屉再打开走 `/answers/latest`（带 items）才正常。

本文件钉三件事：
  1. 上传回包**必须带 items**，且长度 == item_count；
  2. item 字段齐全（no / answer / tier / current / flags）；
  3. 上传回包与 `/answers/latest` **键集合一致**（防两边再次漂移）。
"""
from app.models.models import (ExamPaper, PaperQuestionRelation, QuestionBank)


def _paper(db, admin, subject, qtype, *, code="ANS-PAYLOAD-1", count=3,
           answers=("A", "", "")):
    paper = ExamPaper(
        paper_name=f"答案回包回归卷 {code}", paper_code=code,
        subject_id=subject.subject_id, composition_method="MANUAL",
        creator_id=admin.user_id, duration=120, total_score=100, difficulty=3,
        exam_type="SIMULATION", paper_type="PUBLISHED",
        question_count=count, max_attempts=5, exam_open=1,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    for i in range(count):
        q = QuestionBank(
            subject_id=subject.subject_id, type_id=qtype.type_id,
            question_content=f"答案回包回归题 {i + 1}",
            options=[{"key": "A", "value": "1"}, {"key": "B", "value": "2"}],
            answer=answers[i] if i < len(answers) else "",
            answer_analysis="", difficulty=1, score=10,
            creator_id=admin.user_id, status=1, audit_status=1,
        )
        db.add(q)
        db.commit()
        db.refresh(q)
        db.add(PaperQuestionRelation(paper_id=paper.paper_id,
                                     question_id=q.question_id,
                                     question_order=i + 1, question_score=10))
    db.commit()
    return paper


def _upload_answers(client, headers, paper_id, text=b"1 B\n2 C\n3 D\n"):
    return client.post(
        f"/api/materials/admin/papers/{paper_id}/answers/parse",
        files={"file": ("answers.txt", text)},
        headers=headers,
    )


def test_parse_response_carries_items(client, admin_headers, db_session,
                                     test_admin, test_subject, test_question_type):
    """上传接口必须把逐题明细一起回（修复前这里没有 items）。"""
    paper = _paper(db_session, test_admin, test_subject, test_question_type)
    resp = _upload_answers(client, admin_headers, paper.paper_id)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["ok"] is True
    assert data["can_edit"] is True
    assert data["item_count"] == 3
    items = data.get("items")
    assert isinstance(items, list) and len(items) == 3, "上传回包缺 items（本次事故形态）"
    for it in items:
        for key in ("no", "answer", "tier", "current", "flags"):
            assert key in it, f"item 缺字段 {key}: {it}"
    assert [it["answer"] for it in items] == ["B", "C", "D"]


def test_parse_and_latest_share_same_shape(client, admin_headers, db_session,
                                          test_admin, test_subject, test_question_type):
    """上传回包与「续草稿」回包键集合一致（否则前端两个入口两套行为）。"""
    paper = _paper(db_session, test_admin, test_subject, test_question_type,
                   code="ANS-PAYLOAD-2")
    up = _upload_answers(client, admin_headers, paper.paper_id)
    assert up.status_code == 200, up.text
    parse_keys = set(up.json().keys())

    latest = client.get(f"/api/materials/admin/papers/{paper.paper_id}/answers/latest",
                        headers=admin_headers)
    assert latest.status_code == 200, latest.text
    latest_keys = set(latest.json().keys())

    assert parse_keys - {"ok"} == latest_keys - {"exists"}, (
        "上传/续草稿回包漂移：", parse_keys ^ latest_keys)


def test_parse_reports_existing_answer_in_current(client, admin_headers, db_session,
                                                  test_admin, test_subject, test_question_type):
    """`current` 要带出库里现有答案（前端据此算"会写入几题"）。"""
    paper = _paper(db_session, test_admin, test_subject, test_question_type,
                   code="ANS-PAYLOAD-3", answers=("A", "A", ""))
    resp = _upload_answers(client, admin_headers, paper.paper_id,
                           b"1 B\n2 A\n3 D\n")
    assert resp.status_code == 200, resp.text
    items = {it["no"]: it for it in resp.json()["items"]}
    assert items[1]["current"] == "A" and items[1]["answer"] == "B"   # 不同 → 默认保留
    assert items[2]["current"] == "A" and items[2]["answer"] == "A"   # 一致 → 无需写
    assert items[3]["current"] == "" and items[3]["answer"] == "D"    # 空位 → 会填
