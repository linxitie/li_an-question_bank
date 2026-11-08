# -*- coding: utf-8 -*-
"""C2/C4 回归（2026-11-08）：试卷资料补录 + 预览 paper 区块。

背景：题库里有 2 套真实公专真题（`exam_paper`，各 100 题、PUBLISHED），
但 `study_material` 里 `type=paper` 是 0 条 → 资料管理看不到它们。
本批把它们反向补录成资料，并用 `paper_code` 建立一对一关联。

锁死的行为：
1. `plan_backfill()` 默认**不写库**；`apply=False` 与 dry-run 等价；
2. 人读编号 `GZ-2019-BJ-T` 从卷名解析；解析不出就沿用 exam_paper 原编号（关联得住、不编造）；
3. 幂等：已有同 code 的资料 → skip，重复 apply 不产生副本；
4. 编号冲突（别的卷已占了同一人读编号）→ 保留原编号，并在计划里标注；
5. 预览 `paper` 区块给出年份/地区/题量/总分/时长/是否可考，非试卷类为 None。
"""
import pytest

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


def _paper(db, paper_id=2, name="2019年北京市公务员考试《公安专业科目》真题",
           code="PAPER-OLD-0001", paper_type="PUBLISHED", count=100):
    p = ExamPaper(paper_id=paper_id, paper_name=name, paper_code=code,
                  subject_id=3, creator_id=1, paper_type=paper_type,
                  composition_method="IMPORT",       # NOT NULL：真实数据的卷子都是导入的
                  question_count=count, total_score=100, duration=120)
    db.add(p)
    db.commit()
    return p


class TestPlanBackfill:
    def test_dry_run_writes_nothing(self, db_session):
        _subject(db_session)
        _paper(db_session)
        plan = paper_backfill.apply_backfill(db_session, apply=False)

        assert len(plan) == 1
        item = plan[0]
        assert item["action"] == "create"
        assert item["paper_code"] == "GZ-2019-BJ-T"
        assert item["generated_code"] is True
        assert item["meta"]["year"] == 2019
        assert item["meta"]["region_name"] == "北京"
        assert item["subject"] == "gongzhuan"
        assert db_session.query(StudyMaterial).filter(
            StudyMaterial.type == "paper").count() == 0, "dry-run 不许写库"

    def test_only_published_or_approved_considered(self, db_session):
        _subject(db_session)
        _paper(db_session, paper_id=2, code="P-2", paper_type="PUBLISHED")
        _paper(db_session, paper_id=3, name="2020年草稿卷", code="P-3", paper_type="DRAFT")
        plan = paper_backfill.apply_backfill(db_session)
        assert [p["paper_id"] for p in plan] == [2]

    def test_unparseable_name_keeps_original_code(self, db_session):
        _subject(db_session)
        _paper(db_session, paper_id=9, name="扫描件_001", code="PAPER-RAW-9")
        item = paper_backfill.apply_backfill(db_session)[0]
        assert item["paper_code"] == "PAPER-RAW-9"
        assert item["generated_code"] is False


class TestApplyBackfill:
    def test_creates_paper_material_and_links_both_sides(self, db_session):
        _subject(db_session)
        paper = _paper(db_session)
        plan = paper_backfill.apply_backfill(db_session, apply=True, creator_id=7)

        item = plan[0]
        assert item["action"] == "created"
        material = db_session.query(StudyMaterial).filter(
            StudyMaterial.material_id == item["material_id"]).one()
        assert material.type == "paper"
        assert material.subject == "gongzhuan"
        assert material.status == 1                     # 卷子已发布，资料不能是未上架
        assert material.paper_code == "GZ-2019-BJ-T"
        assert material.badge == "GZ-2019-BJ-T"
        assert material.creator_id == 7

        db_session.refresh(paper)
        assert paper.paper_code == "GZ-2019-BJ-T", "exam_paper 侧也要改成人读编号，两侧才关联得上"
        assert item["old_paper_code"] == "PAPER-OLD-0001"

    def test_idempotent(self, db_session):
        _subject(db_session)
        _paper(db_session)
        paper_backfill.apply_backfill(db_session, apply=True)
        again = paper_backfill.apply_backfill(db_session, apply=True)

        assert again[0]["action"] == "skip"
        assert db_session.query(StudyMaterial).filter(
            StudyMaterial.type == "paper").count() == 1

    def test_existing_material_by_title_is_skipped(self, db_session):
        _subject(db_session)
        paper = _paper(db_session)
        # 早先手工建过同名试卷资料（没有 paper_code）
        db_session.add(StudyMaterial(subject="gongzhuan", type="paper",
                                     title=paper.paper_name, status=0))
        db_session.commit()

        item = paper_backfill.apply_backfill(db_session, apply=True)[0]
        assert item["action"] == "skip"
        assert item["existing_material_id"] is not None

    def test_code_conflict_keeps_original(self, db_session):
        _subject(db_session)
        # 另一套卷先占了人读编号
        _paper(db_session, paper_id=1, name="占位卷", code="GZ-2019-BJ-T")
        _paper(db_session, paper_id=2, code="PAPER-OLD-0002")
        plan = paper_backfill.apply_backfill(db_session, apply=True)

        item = [p for p in plan if p["paper_id"] == 2][0]
        assert item["paper_code"] == "PAPER-OLD-0002"
        assert item["code_conflict_with"] == 1


class TestPreviewPaperBlock:
    def test_preview_returns_paper_meta_and_link(self, client, admin_headers, db_session):
        _subject(db_session)
        _paper(db_session)
        plan = paper_backfill.apply_backfill(db_session, apply=True)
        mid = plan[0]["material_id"]

        resp = client.get(f"/api/materials/admin/{mid}/preview", headers=admin_headers)
        assert resp.status_code == 200, resp.text
        block = resp.json()["paper"]
        assert block["paper_code"] == "GZ-2019-BJ-T"
        assert block["year"] == 2019
        assert block["region_name"] == "北京"
        assert block["book_kind_label"] == "题本"
        assert block["exam_paper_id"] == 2
        assert block["question_count"] == 100
        assert block["total_score"] == 100
        assert block["duration"] == 120
        assert block["answerable"] is True

    def test_preview_paper_none_for_card(self, client, admin_headers, db_session):
        m = StudyMaterial(subject="gongzhuan", type="card", title="卡片",
                          card_front="正", card_back="背", status=1)
        db_session.add(m)
        db_session.commit()
        resp = client.get(f"/api/materials/admin/{m.material_id}/preview",
                          headers=admin_headers)
        assert resp.json()["paper"] is None

    def test_answerable_false_when_not_published(self, client, admin_headers, db_session):
        _subject(db_session)
        paper = _paper(db_session)
        plan = paper_backfill.apply_backfill(db_session, apply=True)
        paper.paper_type = "DRAFT"
        db_session.commit()

        block = client.get(f"/api/materials/admin/{plan[0]['material_id']}/preview",
                           headers=admin_headers).json()["paper"]
        assert block["answerable"] is False
