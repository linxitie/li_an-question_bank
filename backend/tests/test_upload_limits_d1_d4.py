# -*- coding: utf-8 -*-
"""D1 / D3 / D4（2026-11-14）的护栏测试。

- D3：文章导入 `_save_tmp` 按扩展名取上限（PDF 60MB / docx 20MB / xlsx 5MB）+ >8MB 流式；
- D4：答案上传同样按扩展名取上限（PDF 60MB），不再「30MB 一刀切」；
- D1：列表回包 exam 块带 `paper_type`（前端据此标「资料上架 ↔ 卷发布 不一致」）。
"""
from __future__ import annotations

import hashlib
import io

import pytest
from starlette.datastructures import UploadFile

import app.api.v1.library.materials as m
from app.models.models import StudyMaterial
from app.services import material_files


def _upload(name: str, data: bytes) -> UploadFile:
    """构造 UploadFile（BytesIO → 无 fileno，正好覆盖"拿不到大小"的流式分支）。"""
    return UploadFile(file=io.BytesIO(data), filename=name)


def test_max_bytes_by_ext_matches_material_files():
    assert material_files.max_bytes_for("pdf") == 60 * 1024 * 1024
    assert material_files.max_bytes_for("docx") == 20 * 1024 * 1024


def test_save_tmp_allows_21mb_pdf():
    """D3：21MB 的 PDF 以前会被「20MB 一刀切」挡住；现在按类型放行到 60MB。"""
    payload = b"%PDF-1.4\n" + b"0" * (21 * 1024 * 1024)
    path, ext, sha = m._save_tmp(_upload("scan_lecture.pdf", payload))
    try:
        assert ext == ".pdf"
        assert sha == hashlib.sha256(payload).hexdigest()
        import os
        assert os.path.getsize(path) == len(payload)
    finally:
        import os
        os.unlink(path)


def test_save_tmp_rejects_21mb_docx():
    """docx 仍是 20MB 上限（按类型，不放宽）。"""
    payload = b"PK\x03\x04" + b"0" * (21 * 1024 * 1024)
    with pytest.raises(Exception) as exc:
        m._save_tmp(_upload("big.docx", payload))
    assert "20MB" in str(getattr(exc.value, "detail", exc.value))


def test_save_tmp_rejects_bad_magic():
    with pytest.raises(Exception) as exc:
        m._save_tmp(_upload("fake.pdf", b"NOTPDF" + b"0" * 100))
    assert "格式" in str(getattr(exc.value, "detail", exc.value))


def test_spool_upload_roundtrip(tmp_path):
    """D4 的落盘工具：流式写出后字节完全一致。"""
    data = b"%PDF-1.4\n" + b"x" * (9 * 1024 * 1024)
    path = m._spool_upload(io.BytesIO(data), "pdf")
    try:
        import os
        assert os.path.getsize(path) == len(data)
        with open(path, "rb") as fh:
            assert hashlib.sha256(fh.read()).hexdigest() == hashlib.sha256(data).hexdigest()
    finally:
        import os
        os.unlink(path)


def test_answer_upload_cap_is_per_ext(client, admin_headers, db_session,
                                      test_subject, test_question_type, test_admin):
    """D4：答案文件从 30MB 一刀切改成按扩展名（txt 仍 20MB）→ 21MB txt 被 400。"""
    from app.models.models import ExamPaper, PaperQuestionRelation, QuestionBank

    paper = ExamPaper(paper_name="D4 限额卷", paper_code="D4-CAP-1",
                      subject_id=test_subject.subject_id, composition_method="MANUAL",
                      creator_id=test_admin.user_id, duration=120, total_score=100,
                      difficulty=3, exam_type="SIMULATION", paper_type="PUBLISHED",
                      question_count=1, max_attempts=5)
    db_session.add(paper)
    db_session.commit()
    db_session.refresh(paper)
    q = QuestionBank(subject_id=test_subject.subject_id, type_id=test_question_type.type_id,
                     question_content="<p>1</p>", answer="", answer_analysis="",
                     difficulty=3, score=1, creator_id=test_admin.user_id,
                     status=1, audit_status=1)
    db_session.add(q)
    db_session.commit()
    db_session.refresh(q)
    db_session.add(PaperQuestionRelation(paper_id=paper.paper_id, question_id=q.question_id,
                                         question_order=1, question_score=1))
    db_session.commit()

    big = b"1 A\n" + b"0" * (21 * 1024 * 1024)
    r = client.post(f"/api/materials/admin/papers/{paper.paper_id}/answers/parse",
                    files={"file": ("big.txt", big)}, headers=admin_headers)
    assert r.status_code == 400, r.text
    assert "20MB" in r.json()["detail"]


def test_admin_list_carries_paper_type(client, admin_headers, db_session,
                                       test_subject, test_admin):
    """D1：列表回包的 exam 块必须带 paper_type（前端判漂移要用）。"""
    material = StudyMaterial(subject="gongzhuan", type="paper", status=1,
                             title="D1 列表 paper_type", creator_id=test_admin.user_id,
                             paper_code="GZ-D1-T")
    db_session.add(material)
    db_session.commit()

    body = client.get("/api/materials/admin/list?type=paper&page_size=50",
                      headers=admin_headers).json()
    row = next(i for i in body["items"] if i["id"] == material.material_id)
    # 没建卷：known=False，但键仍在（前端统一处理）
    assert "exam" in row and row["exam"] is not None
    assert "paper_type" in row["exam"], row["exam"]
