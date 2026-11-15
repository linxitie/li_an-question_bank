# -*- coding: utf-8 -*-
"""D10（2026-11-15）：没有编号的试卷资料也能建卷、也能入库。

真机现场（material 139「验收探针_扫描5页_请勿上架」）：
  `paper_code = NULL` → 列表里连「建卷」都不显示 → 点「确认入库」被打回
  「这条资料还没有可作答卷」→ 死路。
根因三条：列表只回 `badge` 不回 `paper_code`；前端按钮 `v-if` 要求编号且无编号时静默 return；
`confirm_draft` 无卷直接抛错、无引导。
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from app.models.models import ExamPaper, PaperParseDraft, PaperQuestionRelation, StudyMaterial
from app.services import paper_ingest
from app.services.paper_meta_parser import suggest_paper_code
from app.services.paper_ingest import service as ingest_service
from app.api.v1.library.materials import _item_brief


def _material(db_session, *, title="验收探针_D10", code=None, badge=None):
    m = StudyMaterial(subject="gongzhuan", type="paper", status=0, title=title,
                      paper_code=code, badge=badge, creator_id=2, placement="library")
    db_session.add(m)
    db_session.commit()
    db_session.refresh(m)
    return m


def _items(n=2):
    return [{"no": i, "type": "单选", "stem": f"第{i}题题干（　　）。",
             "options": {"A": "甲", "B": "乙", "C": "丙", "D": "丁"},
             "shared": "", "section": 0, "images": [], "flags": []}
            for i in range(1, n + 1)]


def _draft(db_session, material, n=2):
    draft = ingest_service.create_draft(db_session, material, ext="pdf",
                                        status="pending", actor_id=2)
    draft.items_json = json.dumps(_items(n), ensure_ascii=False)
    draft.item_count = n
    db_session.commit()
    return draft


# --------------------------------------------------------------- 建议编号
def test_suggest_code_keeps_existing():
    assert suggest_paper_code("随便什么标题", "gongzhuan", existing="gz-2025-lk") == "GZ-2025-LK"


def test_suggest_code_parses_title():
    assert suggest_paper_code("2025多省联考公安《公安专业》", "gongzhuan") == "GZ-2025-LK"


def test_suggest_code_fallback_uses_material_id():
    code = suggest_paper_code("验收探针_扫描5页_请勿上架", "gongzhuan", material_id=139)
    assert code == f"MAT-{date.today().strftime('%Y%m%d')}-139"


# --------------------------------------------------------------- 列表契约
def test_item_brief_exposes_paper_code(db_session):
    m = _material(db_session, code="GZ-2025-LK-5P")
    assert _item_brief(m)["paper_code"] == "GZ-2025-LK-5P"


# --------------------------------------------------------------- 入库自动建卷
def test_confirm_auto_creates_paper(db_session):
    m = _material(db_session, code=None)
    draft = _draft(db_session, m, n=2)

    result = paper_ingest.confirm_draft(db_session, draft, actor_id=2)
    db_session.commit()

    assert result["paper_auto_created"] is True
    assert result["created"] == 2
    paper_id = result["paper_id"]
    paper = db_session.query(ExamPaper).filter(ExamPaper.paper_id == paper_id).one()
    assert paper.paper_type == "DRAFT"                       # 能不能考由"上架"决定
    assert paper.paper_code == result["paper_code"]
    assert result["paper_code"].startswith("MAT-")           # 兜底编号
    # 编号写回资料 + 草稿留痕
    db_session.refresh(m)
    db_session.refresh(draft)
    assert m.paper_code == result["paper_code"]
    assert draft.paper_id == paper_id
    assert db_session.query(PaperQuestionRelation).filter(
        PaperQuestionRelation.paper_id == paper_id).count() == 2


def test_confirm_auto_paper_reuses_existing_by_code(db_session):
    """第二次导题不会再建第二张卷（ensure_paper 以编号为唯一键）。"""
    m = _material(db_session, code=None)
    first = paper_ingest.confirm_draft(db_session, _draft(db_session, m, n=1), actor_id=2)
    db_session.commit()
    second = paper_ingest.confirm_draft(db_session, _draft(db_session, m, n=1),
                                        actor_id=2, replace=True)
    db_session.commit()
    assert second["paper_id"] == first["paper_id"]
    assert second["paper_auto_created"] is False             # 走的是"已有卷"分支
    assert db_session.query(ExamPaper).filter(
        ExamPaper.paper_code == first["paper_code"]).count() == 1


def test_confirm_without_auto_paper_raises(db_session):
    m = _material(db_session, code=None)
    draft = _draft(db_session, m)
    with pytest.raises(paper_ingest.IngestError) as exc:
        paper_ingest.confirm_draft(db_session, draft, actor_id=2, auto_paper=False)
    assert "可作答卷" in str(exc.value)


# --------------------------------------------------------------- 建卷接口
def test_ensure_paper_route_accepts_code(client, db_session, admin_headers):
    m = _material(db_session, code=None, title="临时建卷探针")
    resp = client.post(f"/api/materials/admin/{m.material_id}/ensure-paper",
                       json={"paper_code": "TST-2025-001"}, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"] if "data" in resp.json() else resp.json()
    assert data["created"] is True
    assert data["paper_code"] == "TST-2025-001"
    db_session.expire_all()
    db_session.refresh(m)
    assert m.paper_code == "TST-2025-001"


def test_ensure_paper_route_suggests_when_missing(client, db_session, admin_headers):
    m = _material(db_session, code=None, title="验收探针_无编号")
    resp = client.post(f"/api/materials/admin/{m.material_id}/ensure-paper",
                       json={}, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"] if "data" in resp.json() else resp.json()
    assert data["created"] is True
    assert (data["paper_code"] or "").startswith("MAT-")
    db_session.expire_all()
    db_session.refresh(m)
    assert (m.paper_code or "").startswith("MAT-")


def test_confirm_route_passes_auto_paper(client, db_session, admin_headers):
    """路由层也要把 auto_paper 传下去（服务层测过，路由漏传就白搭）。"""
    m = _material(db_session, code=None, title="路由层自动建卷探针")
    draft = _draft(db_session, m, n=1)
    resp = client.post(f"/api/materials/admin/parse-drafts/{draft.draft_id}/confirm",
                       json={}, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["paper_auto_created"] is True
    assert (data["paper_code"] or "").startswith("MAT-")
    assert data["created"] == 1
