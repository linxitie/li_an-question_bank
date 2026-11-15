# -*- coding: utf-8 -*-
"""D7（2026-11-15）：批量改信息（科目 / 分类 / 投放位）。

背景：列表早就有"勾选 + 批量上架/下架/删除"，但没有批量改信息 —— 38 份卡片统一改科目
只能逐条点「改信息」。这里校验新端点 `PATCH /api/materials/admin/batch-meta`。
"""
from __future__ import annotations

from app.models.models import ExamPaper, StudyMaterial


def _mk(db, *, mid_title="批量改信息测试", mtype="card", subject="gongzhuan",
        status=0, category=None, placement="library"):
    m = StudyMaterial(subject=subject, type=mtype, status=status, title=mid_title,
                      category=category, placement=placement, creator_id=2)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _batch(client, headers, **body):
    return client.patch("/api/materials/admin/batch-meta", json=body, headers=headers)


def test_batch_update_category(client, db_session, admin_headers):
    a = _mk(db_session, mid_title="卡片A")
    b = _mk(db_session, mid_title="卡片B")
    r = _batch(client, admin_headers, ids=[a.material_id, b.material_id], category="行测")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["updated"] == 2
    assert data["fields"] == ["category"]
    db_session.expire_all()
    assert db_session.get(StudyMaterial, a.material_id).category == "行测"
    assert db_session.get(StudyMaterial, b.material_id).category == "行测"


def test_batch_update_subject(client, db_session, admin_headers):
    m = _mk(db_session, mid_title="卡片C", subject="xingce")
    r = _batch(client, admin_headers, ids=[m.material_id], subject="gongzhuan")
    assert r.status_code == 200, r.text
    db_session.expire_all()
    assert db_session.get(StudyMaterial, m.material_id).subject == "gongzhuan"


def test_batch_update_placement_and_skip_non_paper(client, db_session, admin_headers):
    paper = _mk(db_session, mid_title="试卷P", mtype="paper", placement="library")
    card = _mk(db_session, mid_title="卡片D", mtype="card")
    r = _batch(client, admin_headers, ids=[paper.material_id, card.material_id],
               placement="both")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["updated"] == 1
    assert data["skipped"] == [{"id": card.material_id, "reason": "not_paper"}]
    db_session.expire_all()
    assert db_session.get(StudyMaterial, paper.material_id).placement == "both"
    assert db_session.get(StudyMaterial, card.material_id).placement == "library"


def test_batch_skips_deleted(client, db_session, admin_headers):
    m = _mk(db_session, mid_title="已删除", status=-1)
    r = _batch(client, admin_headers, ids=[m.material_id], category="X")
    assert r.status_code == 200, r.text
    assert r.json()["updated"] == 0
    assert r.json()["skipped"] == [{"id": m.material_id, "reason": "deleted"}]


def test_batch_rejects_empty_ids(client, admin_headers):
    r = _batch(client, admin_headers, ids=[], category="X")
    assert r.status_code == 400
    assert "ids" in r.json()["detail"]


def test_batch_rejects_no_fields(client, db_session, admin_headers):
    m = _mk(db_session, mid_title="无字段")
    r = _batch(client, admin_headers, ids=[m.material_id])
    assert r.status_code == 400
    assert "至少" in r.json()["detail"]


def test_batch_rejects_bad_placement(client, db_session, admin_headers):
    m = _mk(db_session, mid_title="坏投放位", mtype="paper")
    r = _batch(client, admin_headers, ids=[m.material_id], placement="nowhere")
    assert r.status_code == 400


def test_batch_rejects_bad_subject(client, db_session, admin_headers):
    m = _mk(db_session, mid_title="坏科目")
    r = _batch(client, admin_headers, ids=[m.material_id], subject="yuwen")
    assert r.status_code == 400


def test_batch_requires_admin(client, db_session, auth_headers):
    m = _mk(db_session, mid_title="权限")
    r = _batch(client, auth_headers, ids=[m.material_id], category="X")
    assert r.status_code == 403


def test_batch_placement_syncs_paper(client, db_session, admin_headers):
    """投放位 both→library 时立刻同步卷状态（与单条改信息同一路径）。"""
    m = _mk(db_session, mid_title="投放位联动", mtype="paper", status=1, placement="both")
    paper = ExamPaper(paper_code="D7-SYNC-1", paper_name="D7 同步卷", subject_id=3,
                      paper_type="PUBLISHED", composition_method="IMPORT",
                      duration=120, total_score=100, question_count=0, creator_id=2)
    db_session.add(paper)
    db_session.commit()
    m.paper_code = "D7-SYNC-1"
    db_session.commit()

    r = _batch(client, admin_headers, ids=[m.material_id], placement="library")
    assert r.status_code == 200, r.text
    assert r.json()["updated"] == 1
    db_session.expire_all()
    assert db_session.get(StudyMaterial, m.material_id).placement == "library"
    # 撤出考试页 → 卷被落回 DRAFT
    assert db_session.get(ExamPaper, paper.paper_id).paper_type == "DRAFT"
