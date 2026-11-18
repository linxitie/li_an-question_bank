# -*- coding: utf-8 -*-
"""L1（2026-11-08）：投放位 placement 的回归。

覆盖：
  · 上传时 placement 三态落到库；非试卷传 exam → 400；非法值 → 400
  · 上架后：exam → 卷 PUBLISHED 但资料库不露出；library → 卷 DRAFT 但资料库可见；
    both → 两边都通
  · 改投放位（both→library）立即把卷落回 DRAFT
  · 详情返回 files/placement；仅考试页资料直连详情 404、原件学生不可下
  · 列表 brief 带 placement/has_files/file_count

所有用例用 conftest 的内存库（create_all 会带上新列），不碰真实库。
"""
import io
import json

import pytest

from app.models.models import ExamPaper, StudyMaterial


# ---------- 小工具 ----------

def _upload(client, admin_headers, tmp_path, *, type="lecture", placement=None,
            name="投放位探针.pdf", content=b"%PDF-1.4\n%probe\n"):
    f = tmp_path / name
    f.write_bytes(content)
    data = {"subject": "gongzhuan", "type": type}
    if placement is not None:
        data["placement"] = placement
    with open(f, "rb") as fh:
        return client.post(
            "/api/materials/admin/files/upload",
            headers=admin_headers,
            data=data,
            files={"file": (name, fh, "application/pdf")},
        )


def _make_paper_with_question(db, *, code="GZ-L1-001", subject_id=3, type_id=1, creator_id=1):
    """造一张草稿卷 + 1 道题，让 P5 有东西可发布。"""
    from app.models.models import ExamPaper, PaperQuestionRelation, QuestionBank
    paper = ExamPaper(paper_name="L1 投放位卷", paper_code=code, subject_id=subject_id,
                      composition_method="IMPORT", creator_id=creator_id,
                      duration=120, total_score=100, difficulty=3,
                      exam_type="SIMULATION", paper_type="DRAFT", question_count=1)
    db.add(paper)
    db.commit()
    db.refresh(paper)
    q = QuestionBank(subject_id=subject_id, type_id=type_id,
                     question_content="L1 探针题", options=[{"key": "A", "value": "1"}],
                     answer="A", answer_analysis="x", difficulty=1, score=1,
                     creator_id=creator_id, status=1, audit_status=1)
    db.add(q)
    db.commit()
    db.refresh(q)
    db.add(PaperQuestionRelation(paper_id=paper.paper_id, question_id=q.question_id,
                                 question_order=1, question_score=1))
    db.commit()
    return paper


# ---------- 上传参数 ----------

def test_upload_paper_placement_exam_is_saved(client, admin_headers, tmp_path, db_session):
    r = _upload(client, admin_headers, tmp_path, type="paper", placement="exam")
    assert r.status_code == 200, r.text
    mid = r.json()["material_id"]
    m = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).one()
    assert m.placement == "exam"
    assert m.status == 0  # 上传仍是"未上架"


def test_upload_paper_without_placement_defaults_both(client, admin_headers, tmp_path, db_session):
    r = _upload(client, admin_headers, tmp_path, type="paper")
    assert r.status_code == 200, r.text
    mid = r.json()["material_id"]
    m = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).one()
    assert m.placement == "both"


def test_upload_non_paper_ignores_placement_and_stays_library(client, admin_headers, tmp_path,
                                                              db_session):
    r = _upload(client, admin_headers, tmp_path, type="lecture", placement="library")
    assert r.status_code == 200, r.text
    m = db_session.query(StudyMaterial).filter(
        StudyMaterial.material_id == r.json()["material_id"]).one()
    assert m.placement == "library"


def test_upload_non_paper_with_exam_placement_is_rejected(client, admin_headers, tmp_path):
    r = _upload(client, admin_headers, tmp_path, type="article", placement="exam")
    assert r.status_code == 400
    assert "试卷" in r.json()["detail"]


def test_upload_invalid_placement_is_rejected(client, admin_headers, tmp_path):
    r = _upload(client, admin_headers, tmp_path, type="paper", placement="somewhere")
    assert r.status_code == 400


# ---------- 上架后的可见性 ----------

def test_exam_only_paper_publishes_but_hidden_from_library(client, admin_headers, auth_headers,
                                                           tmp_path, db_session, test_subject,
                                                           test_question_type, test_user):
    paper = _make_paper_with_question(db_session, code="GZ-L1-EXAM",
                                      subject_id=test_subject.subject_id,
                                      type_id=test_question_type.type_id,
                                      creator_id=test_user.user_id)
    r = _upload(client, admin_headers, tmp_path, type="paper", placement="exam",
                name="GZ-L1-EXAM.pdf")
    mid = r.json()["material_id"]
    m = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).one()
    m.paper_code = "GZ-L1-EXAM"
    db_session.commit()

    up = client.put(f"/api/materials/admin/{mid}/status", headers=admin_headers, json={"status": 1})
    assert up.status_code == 200, up.text

    db_session.expire_all()
    assert db_session.get(ExamPaper, paper.paper_id).paper_type == "PUBLISHED"

    lst = client.get("/api/materials?subject=gongzhuan&type=paper&page_size=50",
                     headers=auth_headers)
    assert lst.status_code == 200
    ids = [i["id"] for i in lst.json()["items"]]
    assert mid not in ids, "仅考试页的资料不应出现在资料库"

    det = client.get(f"/api/materials/{mid}", headers=auth_headers)
    assert det.status_code == 404


def test_library_only_paper_visible_but_not_published(client, admin_headers, auth_headers,
                                                      tmp_path, db_session, test_subject,
                                                      test_question_type, test_user):
    paper = _make_paper_with_question(db_session, code="GZ-L1-LIB",
                                      subject_id=test_subject.subject_id,
                                      type_id=test_question_type.type_id,
                                      creator_id=test_user.user_id)
    r = _upload(client, admin_headers, tmp_path, type="paper", placement="library",
                name="GZ-L1-LIB.pdf")
    mid = r.json()["material_id"]
    m = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).one()
    m.paper_code = "GZ-L1-LIB"
    db_session.commit()

    up = client.put(f"/api/materials/admin/{mid}/status", headers=admin_headers, json={"status": 1})
    assert up.status_code == 200, up.text

    db_session.expire_all()
    assert db_session.get(ExamPaper, paper.paper_id).paper_type == "DRAFT", \
        "仅资料页的卷不得被发布"

    lst = client.get("/api/materials?subject=gongzhuan&type=paper&page_size=50",
                     headers=auth_headers)
    ids = [i["id"] for i in lst.json()["items"]]
    assert mid in ids


def test_both_paper_gives_library_and_exam(client, admin_headers, auth_headers, tmp_path,
                                           db_session, test_subject, test_question_type, test_user):
    paper = _make_paper_with_question(db_session, code="GZ-L1-BOTH",
                                      subject_id=test_subject.subject_id,
                                      type_id=test_question_type.type_id,
                                      creator_id=test_user.user_id)
    r = _upload(client, admin_headers, tmp_path, type="paper", placement="both",
                name="GZ-L1-BOTH.pdf")
    mid = r.json()["material_id"]
    m = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).one()
    m.paper_code = "GZ-L1-BOTH"
    db_session.commit()

    client.put(f"/api/materials/admin/{mid}/status", headers=admin_headers, json={"status": 1})
    db_session.expire_all()
    assert db_session.get(ExamPaper, paper.paper_id).paper_type == "PUBLISHED"

    lst = client.get("/api/materials?subject=gongzhuan&type=paper&page_size=50",
                     headers=auth_headers)
    assert mid in [i["id"] for i in lst.json()["items"]]


# ---------- 改投放位 ----------

def test_patch_placement_both_to_library_unpublishes(client, admin_headers, tmp_path, db_session,
                                                     test_subject, test_question_type, test_user):
    paper = _make_paper_with_question(db_session, code="GZ-L1-EDIT",
                                      subject_id=test_subject.subject_id,
                                      type_id=test_question_type.type_id,
                                      creator_id=test_user.user_id)
    r = _upload(client, admin_headers, tmp_path, type="paper", placement="both",
                name="GZ-L1-EDIT.pdf")
    mid = r.json()["material_id"]
    m = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).one()
    m.paper_code = "GZ-L1-EDIT"
    db_session.commit()
    client.put(f"/api/materials/admin/{mid}/status", headers=admin_headers, json={"status": 1})
    db_session.expire_all()
    assert db_session.get(ExamPaper, paper.paper_id).paper_type == "PUBLISHED"

    resp = client.patch(f"/api/materials/admin/{mid}/meta", headers=admin_headers,
                        json={"placement": "library"})
    assert resp.status_code == 200, resp.text
    assert "placement" in resp.json()["changed"]

    db_session.expire_all()
    assert db_session.get(ExamPaper, paper.paper_id).paper_type == "DRAFT"


def test_patch_placement_rejects_non_paper(client, admin_headers, tmp_path, db_session):
    r = _upload(client, admin_headers, tmp_path, type="lecture")
    mid = r.json()["material_id"]
    resp = client.patch(f"/api/materials/admin/{mid}/meta", headers=admin_headers,
                        json={"placement": "exam"})
    assert resp.status_code == 400


# ---------- 详情 / 列表字段 ----------

def test_detail_returns_files_and_placement(client, admin_headers, auth_headers, tmp_path,
                                            db_session):
    r = _upload(client, admin_headers, tmp_path, type="lecture")
    mid = r.json()["material_id"]
    client.put(f"/api/materials/admin/{mid}/status", headers=admin_headers, json={"status": 1})

    det = client.get(f"/api/materials/{mid}", headers=auth_headers)
    assert det.status_code == 200, det.text
    body = det.json()
    assert body["placement"] == "library"
    assert body["has_files"] is True
    assert body["file_count"] == 1
    assert body["files"][0]["download_url"].endswith("/download")


def test_list_brief_carries_placement_and_file_flags(client, admin_headers, auth_headers,
                                                      tmp_path):
    r = _upload(client, admin_headers, tmp_path, type="lecture")
    mid = r.json()["material_id"]
    client.put(f"/api/materials/admin/{mid}/status", headers=admin_headers, json={"status": 1})
    lst = client.get("/api/materials?subject=gongzhuan&type=lecture&page_size=50",
                     headers=auth_headers).json()
    row = next(i for i in lst["items"] if i["id"] == mid)
    assert row["placement"] == "library"
    assert row["has_files"] is True
    assert row["file_count"] == 1


def test_exam_only_original_is_not_downloadable_by_student(client, admin_headers,
                                                           auth_headers, tmp_path, db_session):
    r = _upload(client, admin_headers, tmp_path, type="paper", placement="exam",
                name="GZ-L1-DL.pdf")
    mid = r.json()["material_id"]
    fid = r.json()["file"]["file_id"]
    client.put(f"/api/materials/admin/{mid}/status", headers=admin_headers, json={"status": 1})

    d = client.get(f"/api/materials/files/{fid}/download", headers=auth_headers)
    assert d.status_code == 403, "仅考试页的原卷学生不该能下载"

    d2 = client.get(f"/api/materials/files/{fid}/download", headers=admin_headers)
    assert d2.status_code == 200, "管理员始终可下"
