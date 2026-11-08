# -*- coding: utf-8 -*-
"""C2b 回归（2026-11-08）：`PATCH /api/materials/admin/{id}/meta`。

设计要点（详见 `app/services/paper_meta_edit.py`）：
- 只写 `study_material`（`title` / `category` / `paper_code` / `paper_meta` JSON），**不写 `exam_paper`**；
- 订正值的优先级高于文件名解析，可作答卷的题量/总分只在资料没填时兜底（并在 `source` 里标明来源）；
- 字段白名单 + 范围校验；`null`/空串 = 清除该项；编号冲突 400；已删除资料 404；非管理员 403。
"""
import json

from app.models.models import ExamPaper, QuestionSubject, StudyMaterial
from app.services import paper_backfill


def _subject(db):
    row = db.query(QuestionSubject).filter(QuestionSubject.subject_id == 3).first()
    if row:
        return row
    row = QuestionSubject(subject_id=3, subject_name="公专", subject_code="auto_公专", status=1)
    db.add(row)
    db.commit()
    return row


def _paper_material(db, title="扫描件_001", status=0):
    m = StudyMaterial(subject="gongzhuan", type="paper", title=title,
                      content="", status=status)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _patch(client, headers, mid, **body):
    return client.patch(f"/api/materials/admin/{mid}/meta", json=body, headers=headers)


class TestEditBasic:
    def test_update_title_and_category(self, client, admin_headers, db_session):
        m = _paper_material(db_session)
        resp = _patch(client, admin_headers, m.material_id,
                      title="2019年北京市公务员考试《公安专业科目》真题",
                      category="基础知识")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["material"]["title"].startswith("2019年北京")
        assert body["material"]["category"] == "基础知识"
        assert "title" in body["changed"] and "category" in body["changed"]

    def test_empty_title_rejected(self, client, admin_headers, db_session):
        m = _paper_material(db_session)
        assert _patch(client, admin_headers, m.material_id, title="  ").status_code == 400

    def test_deleted_material_404(self, client, admin_headers, db_session):
        m = _paper_material(db_session, status=-1)
        assert _patch(client, admin_headers, m.material_id, title="x").status_code == 404

    def test_teacher_forbidden(self, client, teacher_headers, db_session):
        m = _paper_material(db_session)
        assert _patch(client, teacher_headers, m.material_id, title="x").status_code == 403


class TestPaperMetaEdit:
    def test_set_year_region_kind(self, client, admin_headers, db_session):
        m = _paper_material(db_session)          # 标题解析不出任何元数据
        resp = _patch(client, admin_headers, m.material_id,
                      year=2019, region_name="北京", book_kind="T")
        assert resp.status_code == 200, resp.text
        paper = resp.json()["paper"]
        assert paper["year"] == 2019
        assert paper["region_name"] == "北京"
        assert paper["book_kind_label"] == "题本"
        assert paper["meta_label"] == "2019 · 北京 · 题本"

        db_session.expire_all()
        row = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == m.material_id).one()
        saved = json.loads(row.paper_meta)
        assert saved["year"] == 2019 and saved["region_code"] == "BJ"

    def test_override_beats_filename_parse(self, client, admin_headers, db_session):
        m = _paper_material(db_session, title="2019年北京市公务员考试真题")   # 解析出 2019/北京
        resp = _patch(client, admin_headers, m.material_id, year=2020, region_name="江苏")
        paper = resp.json()["paper"]
        assert paper["year"] == 2020 and paper["region_name"] == "江苏"

    def test_clear_field_returns_to_parse(self, client, admin_headers, db_session):
        m = _paper_material(db_session, title="2019年北京市公务员考试真题")
        _patch(client, admin_headers, m.material_id, year=2020)
        resp = _patch(client, admin_headers, m.material_id, year=None)
        assert resp.json()["paper"]["year"] == 2019, "清空订正后回到文件名解析结果"

    def test_question_count_edit_overrides_exam(self, client, admin_headers, db_session):
        _subject(db_session)
        paper = ExamPaper(paper_id=2, paper_name="2019年北京市公务员考试《公安专业科目》真题",
                          paper_code="GZ-2019-BJ-T", subject_id=3, creator_id=1,
                          composition_method="IMPORT", paper_type="PUBLISHED",
                          question_count=100, total_score=100, duration=120)
        db_session.add(paper)
        db_session.commit()
        plan = paper_backfill.apply_backfill(db_session, apply=True)
        mid = plan[0]["material_id"]

        # 未订正：题量来自可作答卷，source=exam
        before = client.get(f"/api/materials/admin/{mid}/preview",
                            headers=admin_headers).json()["paper"]
        assert before["question_count"] == 100 and before["source"]["question_count"] == "exam"

        resp = _patch(client, admin_headers, mid, question_count=80, total_score=80, duration=90)
        paper_block = resp.json()["paper"]
        assert paper_block["question_count"] == 80
        assert paper_block["total_score"] == 80.0
        assert paper_block["source"]["question_count"] == "edit"
        # 关联不受影响
        assert paper_block["exam_paper_id"] == 2 and paper_block["answerable"] is True

    def test_range_validation(self, client, admin_headers, db_session):
        m = _paper_material(db_session)
        for bad in (dict(year=1800), dict(year=3000), dict(question_count=0),
                    dict(total_score=0), dict(duration=0), dict(volume=99)):
            resp = _patch(client, admin_headers, m.material_id, **bad)
            assert resp.status_code == 400, (bad, resp.text)

    def test_unknown_region_rejected(self, client, admin_headers, db_session):
        m = _paper_material(db_session)
        assert _patch(client, admin_headers, m.material_id,
                      region_name="火星").status_code == 400
        assert _patch(client, admin_headers, m.material_id,
                      region_code="XX").status_code == 400

    def test_unknown_book_kind_rejected(self, client, admin_headers, db_session):
        m = _paper_material(db_session)
        assert _patch(client, admin_headers, m.material_id, book_kind="Z").status_code == 400


class TestPaperCode:
    def test_auto_code_after_edit(self, client, admin_headers, db_session):
        m = _paper_material(db_session, title="扫描件_001")   # 无编号
        resp = _patch(client, admin_headers, m.material_id,
                      year=2019, region_name="北京", book_kind="T", paper_code="")
        assert resp.json()["material"]["paper_code"] == "GZ-2019-BJ-T"

    def test_explicit_code_and_conflict(self, client, admin_headers, db_session):
        a = _paper_material(db_session, title="A")
        b = _paper_material(db_session, title="B")
        assert _patch(client, admin_headers, a.material_id,
                      paper_code="GZ-2020-SD-T").json()["material"]["paper_code"] == "GZ-2020-SD-T"
        clash = _patch(client, admin_headers, b.material_id, paper_code="GZ-2020-SD-T")
        assert clash.status_code == 400 and "已被资料" in clash.text

    def test_empty_code_without_enough_meta_keeps_none(self, client, admin_headers, db_session):
        m = _paper_material(db_session, title="扫描件_002")
        resp = _patch(client, admin_headers, m.material_id, paper_code="")
        assert resp.json()["material"]["paper_code"] is None
