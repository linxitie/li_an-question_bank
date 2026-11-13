# -*- coding: utf-8 -*-
"""P4 补答案扫描件（2026-11-13）：扫描答案件转后台 OCR。

覆盖：
  1. `pdf_text_layer_empty()`：扫描件判定的唯一依据（前 3 页 0 文字）；
  2. 材料上传**按类型上限**（PDF 60MB / 其余 20MB）—— 真实 41 页真卷 56.97MB 靠它才进得来；
  3. `fill_answer_draft()`：成功置 pending、进度回调、已放弃的草稿不被"救活"；
  4. 路由：扫描件立刻回 `parsing`（不再阻塞 3–7 分钟）；
  5. 幂等：OCR 在跑时重复上传 → 复用同一份草稿，不起第二个任务；
  6. 惰性超时：卡在 parsing 超 40 分钟 → 查询时判 failed。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.models.models import ExamPaper, PaperAnswerDraft, PaperQuestionRelation, QuestionBank
from app.services import material_files
from app.services.answer_ingest import service


def _blank_pdf(path, pages: int = 1) -> str:
    """没有文字层的 PDF = 扫描件（最小复现，不需要真图片）。"""
    import pymupdf
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page()
    doc.save(str(path))
    doc.close()
    return str(path)


def _text_pdf(path) -> str:
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "1 A  2 B", fontsize=12)
    doc.save(str(path))
    doc.close()
    return str(path)


def _make_paper(db, subject_id, type_id, creator_id, *, code="P4-OCR-1", count=3):
    paper = ExamPaper(
        paper_name=f"P4 OCR 测试卷 {code}", paper_code=code, subject_id=subject_id,
        composition_method="MANUAL", creator_id=creator_id, duration=120,
        total_score=100, difficulty=3, exam_type="SIMULATION",
        paper_type="PUBLISHED", question_count=count, max_attempts=5,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    for i in range(1, count + 1):
        q = QuestionBank(subject_id=subject_id, type_id=type_id,
                         question_content=f"<p>第 {i} 题题干</p>",
                         options=[{"key": "A", "value": "甲"}, {"key": "B", "value": "乙"}],
                         answer="", answer_analysis="", difficulty=3, score=1,
                         creator_id=creator_id, status=1, audit_status=1)
        db.add(q)
        db.commit()
        db.refresh(q)
        db.add(PaperQuestionRelation(paper_id=paper.paper_id, question_id=q.question_id,
                                    question_order=i, question_score=1))
    db.commit()
    return paper


# ------------------------------------------------------- 判扫描 + 按类型上限
def test_pdf_text_layer_empty_detects_scan(tmp_path):
    assert service.pdf_text_layer_empty(_blank_pdf(tmp_path / "scan.pdf", 2)) is True
    assert service.pdf_text_layer_empty(_text_pdf(tmp_path / "text.pdf")) is False


def test_material_size_caps_by_ext():
    """2026-11-13：真卷 56.97MB 之所以传不进来，就是这里只有一个 20MB 全局上限。"""
    assert material_files.max_bytes_for("pdf") == 60 * 1024 * 1024
    assert material_files.max_bytes_for("docx") == 20 * 1024 * 1024
    material_files.check_size("pdf", 57 * 1024 * 1024)          # 不抛
    with pytest.raises(ValueError) as exc:
        material_files.check_size("docx", 21 * 1024 * 1024)
    assert "20MB" in str(exc.value)


# --------------------------------------------------------------- 服务层
def test_fill_answer_draft_sets_pending(db_session, test_subject, test_question_type,
                                        test_admin, monkeypatch):
    paper = _make_paper(db_session, test_subject.subject_id,
                        test_question_type.type_id, test_admin.user_id)
    seen: list[str] = []

    def fake_read(path, ext, *, meta=None, progress=None):
        if progress:
            progress(1, 3)
            progress(3, 3)
        return ("1、正确答案为 A。本题考查公安时政。\n"
                "2、正确答案为 B。本题考查党史。\n"
                "3、正确答案为 C。本题考查法律。\n")

    monkeypatch.setattr(service, "read_text_of", fake_read)
    draft = service.create_answer_draft(db_session, paper_id=paper.paper_id, ext="pdf",
                                       source_name="扫描答案.pdf", actor_id=test_admin.user_id)
    service.fill_answer_draft(db_session, draft, ext="pdf", abs_path="x.pdf",
                              progress_cb=seen.append)
    db_session.commit()
    assert draft.status == "pending"
    assert draft.item_count == 3
    assert "识别 3 题 / 卷共 3 题" in (draft.message or "")


def test_fill_answer_draft_does_not_resurrect_discarded(db_session, test_subject,
                                                        test_question_type, test_admin,
                                                        monkeypatch):
    """后台任务跑完时用户已经「放弃」→ 不许把草稿救回 pending（否则抽屉里冒出幽灵草稿）。"""
    paper = _make_paper(db_session, test_subject.subject_id,
                        test_question_type.type_id, test_admin.user_id, code="P4-OCR-2")
    monkeypatch.setattr(service, "read_text_of",
                        lambda *a, **k: ("1、正确答案为 A。本题考查公安时政。\n"
                                         "2、正确答案为 B。本题考查党史。\n"
                                         "3、正确答案为 C。本题考查法律。\n"))
    draft = service.create_answer_draft(db_session, paper_id=paper.paper_id, ext="pdf",
                                       status="parsing", message="OCR 排队中")
    db_session.commit()
    draft.status = "discarded"
    db_session.commit()

    service.fill_answer_draft(db_session, draft, ext="pdf", abs_path="x.pdf")
    db_session.commit()
    assert draft.status == "discarded"
    assert draft.item_count == 0


# --------------------------------------------------------------- 路由
def test_scanned_answer_route_returns_parsing(client, db_session, admin_headers,
                                              test_subject, test_question_type,
                                              test_admin, monkeypatch, tmp_path):
    paper = _make_paper(db_session, test_subject.subject_id,
                        test_question_type.type_id, test_admin.user_id, code="P4-OCR-3")
    import app.api.v1.library.materials as m
    calls: list[tuple] = []
    monkeypatch.setattr(m, "_answer_parse_job", lambda *a, **kw: calls.append(a))

    pdf = _blank_pdf(tmp_path / "scan_answer.pdf", 3)
    with open(pdf, "rb") as fh:
        resp = client.post(f"/api/materials/admin/papers/{paper.paper_id}/answers/parse",
                           files={"file": ("scan_answer.pdf", fh.read())},
                           headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "parsing"
    assert body["can_edit"] is False
    assert body["message"] and "OCR" in body["message"]
    assert body["items"] == []
    assert len(calls) == 1

    row = db_session.query(PaperAnswerDraft).filter(
        PaperAnswerDraft.draft_id == body["draft_id"]).first()
    assert row is not None and row.status == "parsing"


def test_scanned_answer_route_is_idempotent(client, db_session, admin_headers,
                                            test_subject, test_question_type,
                                            test_admin, monkeypatch, tmp_path):
    """OCR 在跑时再传一次 → 复用同一份草稿，别烧第二份 CPU。"""
    paper = _make_paper(db_session, test_subject.subject_id,
                        test_question_type.type_id, test_admin.user_id, code="P4-OCR-4")
    import app.api.v1.library.materials as m
    calls: list[tuple] = []
    monkeypatch.setattr(m, "_answer_parse_job", lambda *a, **kw: calls.append(a))

    pdf = _blank_pdf(tmp_path / "scan_answer2.pdf", 2)
    raw = open(pdf, "rb").read()
    first = client.post(f"/api/materials/admin/papers/{paper.paper_id}/answers/parse",
                        files={"file": ("scan_answer2.pdf", raw)},
                        headers=admin_headers).json()
    second = client.post(f"/api/materials/admin/papers/{paper.paper_id}/answers/parse",
                         files={"file": ("scan_answer2.pdf", raw)},
                         headers=admin_headers).json()
    assert first["draft_id"] == second["draft_id"]
    assert second.get("reused") is True
    assert len(calls) == 1


def test_stale_parsing_answer_draft_becomes_failed(client, db_session, admin_headers,
                                                   test_subject, test_question_type,
                                                   test_admin):
    paper = _make_paper(db_session, test_subject.subject_id,
                        test_question_type.type_id, test_admin.user_id, code="P4-OCR-5")
    draft = PaperAnswerDraft(paper_id=paper.paper_id, status="parsing", source_ext="pdf",
                             source_name="scan.pdf", item_count=0,
                             message="OCR 12/43 页",
                             create_time=datetime.now() - timedelta(minutes=41),
                             update_time=datetime.now() - timedelta(minutes=41),
                             expires_at=datetime.now() + timedelta(days=30))
    db_session.add(draft)
    db_session.commit()

    body = client.get(f"/api/materials/admin/answers/drafts/{draft.draft_id}",
                      headers=admin_headers).json()
    assert body["status"] == "failed"
    assert "超时中断" in (body["message"] or "")
