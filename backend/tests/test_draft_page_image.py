# -*- coding: utf-8 -*-
"""Q2（2026-11-15，导题缺号定位）：按题号渲染原卷页图的只读端点。

为什么这些用例必须存在：
  · 这是**新增的对外端点**（R11 登记项），越权/越界/放大三类风险都要有测试兜住；
  · 前端要按 code 给不同文案（旧草稿 / docx / 原件丢了），所以错误码必须被钉住；
  · 高亮框是 0–1 相对坐标，算错就是"框在别处"，必须有断言。
"""
from __future__ import annotations

import base64

import pytest

from app.models.models import MaterialFile, PaperParseDraft, StudyMaterial
from app.services.paper_ingest import service


def _pdf(path, pages=3):
    """造一个 n 页空白 PDF（有页面尺寸就行，渲染不需要内容）。"""
    import pymupdf
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page()
    doc.save(str(path))
    doc.close()
    return path


def _gaps(no=46, page=2):
    return [{"no": no, "page": page, "y0": 100.0, "y1": 160.0,
             "x0": 0.0, "x1": 1200.0, "missing": [no]}]


def _skeleton(db, tmp_path, monkeypatch, *, ext="pdf", with_file=True, bad_path=False, pages=3):
    """建 资料 + 原件（可选）+ 草稿；返回 (material, draft)。

    说明：`resolve_abs_path()` 只接受"storage 根下的相对路径"，测试里没有真实 storage 根，
    所以这里**只替身它一个函数**（返回 tmp 里的真 PDF），端点其余逻辑走真代码。
    """
    from app.services import material_files

    monkeypatch.setattr(service, "_storage_root", lambda: str(tmp_path / "drafts"))
    pdf = _pdf(tmp_path / "src.pdf", pages=pages)

    def _resolve(row):
        if bad_path:
            raise FileNotFoundError("文件不存在")
        return pdf

    monkeypatch.setattr(material_files, "resolve_abs_path", _resolve)

    m = StudyMaterial(subject="gongzhuan", type="paper", status=1,
                      title=f"Q2 探针-{ext}", creator_id=2)
    db.add(m)
    db.commit()
    if with_file:
        db.add(MaterialFile(
            material_id=m.material_id, role="primary", file_name="src.pdf",
            file_ext="pdf", file_size=pdf.stat().st_size,
            storage_path="ab/abcdef.pdf"))
        db.commit()
    d = PaperParseDraft(material_id=m.material_id, paper_id=None, status="pending",
                        source_ext=ext, item_count=1, items_json="[]",
                        warnings_json="[]", created_by=2)
    db.add(d)
    db.commit()
    return m, d


# ------------------------------------------------------------------ 正常路径
def test_page_image_ok(client, admin_headers, db_session, tmp_path, monkeypatch):
    m, d = _skeleton(db_session, tmp_path, monkeypatch)
    service.write_qno_gaps(d.draft_id, _gaps(), dpi=200, page_count=3)
    r = client.get(f"/api/materials/admin/parse-drafts/{d.draft_id}/page-image?no=46&dpi=120",
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["no"] == 46 and body["page"] == 2
    assert body["dpi"] == 120 and body["image_w"] > 0 and body["image_h"] > 0
    assert base64.b64decode(body["image_b64"])[:8] == b"\x89PNG\r\n\x1a\n"
    hl = body["highlight"]
    assert 0.0 <= hl["x0"] < hl["x1"] <= 1.0
    assert 0.0 <= hl["y0"] < hl["y1"] <= 1.0


# ------------------------------------------------------------------ 错误码（前端按 code 分支）
def test_page_image_gap_not_found(client, admin_headers, db_session, tmp_path, monkeypatch):
    m, d = _skeleton(db_session, tmp_path, monkeypatch)
    service.write_qno_gaps(d.draft_id, _gaps(no=46))
    r = client.get(f"/api/materials/admin/parse-drafts/{d.draft_id}/page-image?no=99",
                   headers=admin_headers)
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert detail["code"] == "GAP_NOT_FOUND"
    assert "旧版本草稿" in detail["message"]


def test_page_image_old_draft_without_sidecar(client, admin_headers, db_session, tmp_path,
                                              monkeypatch):
    m, d = _skeleton(db_session, tmp_path, monkeypatch)
    r = client.get(f"/api/materials/admin/parse-drafts/{d.draft_id}/page-image?no=46",
                   headers=admin_headers)
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "GAP_NOT_FOUND"


def test_page_image_docx_returns_409(client, admin_headers, db_session, tmp_path, monkeypatch):
    m, d = _skeleton(db_session, tmp_path, monkeypatch, ext="docx")
    r = client.get(f"/api/materials/admin/parse-drafts/{d.draft_id}/page-image?no=46",
                   headers=admin_headers)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "NOT_PDF"


def test_page_image_draft_missing(client, admin_headers):
    r = client.get("/api/materials/admin/parse-drafts/999999/page-image?no=46",
                   headers=admin_headers)
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "DRAFT_NOT_FOUND"


def test_page_image_file_missing(client, admin_headers, db_session, tmp_path, monkeypatch):
    m, d = _skeleton(db_session, tmp_path, monkeypatch, bad_path=True)
    service.write_qno_gaps(d.draft_id, _gaps())
    r = client.get(f"/api/materials/admin/parse-drafts/{d.draft_id}/page-image?no=46",
                   headers=admin_headers)
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "FILE_MISSING"


def test_page_image_requires_admin(client, auth_headers, db_session, tmp_path, monkeypatch):
    m, d = _skeleton(db_session, tmp_path, monkeypatch)
    r = client.get(f"/api/materials/admin/parse-drafts/{d.draft_id}/page-image?no=46",
                   headers=auth_headers)
    assert r.status_code in (401, 403)


def test_page_image_dpi_out_of_range(client, admin_headers, db_session, tmp_path, monkeypatch):
    m, d = _skeleton(db_session, tmp_path, monkeypatch)
    r = client.get(f"/api/materials/admin/parse-drafts/{d.draft_id}/page-image?no=46&dpi=400",
                   headers=admin_headers)
    assert r.status_code == 422


# ------------------------------------------------------------------ Q4 用到的只读标记
def test_draft_payload_reports_gaps_available(client, admin_headers, db_session, tmp_path,
                                              monkeypatch):
    m, d = _skeleton(db_session, tmp_path, monkeypatch)
    r1 = client.get(f"/api/materials/admin/parse-drafts/{d.draft_id}", headers=admin_headers)
    assert r1.status_code == 200
    assert r1.json()["qno_gaps_available"] is False
    service.write_qno_gaps(d.draft_id, _gaps())
    r2 = client.get(f"/api/materials/admin/parse-drafts/{d.draft_id}", headers=admin_headers)
    assert r2.json()["qno_gaps_available"] is True


# ------------------------------------------------------------------ 跨页：主选页 / 备选页
def _cross_gaps():
    return [{"no": 46, "page": 16, "y0": 100.0, "y1": 200.0,
             "x0": 0.0, "x1": 1200.0, "alt_page": 17, "missing": [46]}]


def test_page_image_alt_page_allowed(client, admin_headers, db_session, tmp_path, monkeypatch):
    """跨页缺口：备选页（下一题所在页）可以显式请求，返回时标记 on_alt_page。"""
    m, d = _skeleton(db_session, tmp_path, monkeypatch, pages=17)
    service.write_qno_gaps(d.draft_id, _cross_gaps(), dpi=200, page_count=17)
    r = client.get(f"/api/materials/admin/parse-drafts/{d.draft_id}/page-image?no=46&page=17",
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["page"] == 17 and body["on_alt_page"] is True
    assert body["highlight"]["y0"] == 0.0            # 备选页只给顶部提示条


def test_page_image_other_page_rejected(client, admin_headers, db_session, tmp_path, monkeypatch):
    """只允许在主选页与备选页之间切换，别把端点变成"任意页渲染器"。"""
    m, d = _skeleton(db_session, tmp_path, monkeypatch)
    service.write_qno_gaps(d.draft_id, _cross_gaps(), dpi=200, page_count=17)
    r = client.get(f"/api/materials/admin/parse-drafts/{d.draft_id}/page-image?no=46&page=9",
                   headers=admin_headers)
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "PAGE_NOT_ALLOWED"
