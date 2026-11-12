# -*- coding: utf-8 -*-
"""文章/讲义批量导入的「立即上架」开关（2026-11-12 修复）。

事故：`import_confirm` 顶部读了 `publish`，但**只对 xlsx 卡片分支生效**；
文档分支写死 `status=0`，而回包仍回 `published: publish`（传 true 会谎报）。
前端「批量上传文章」也没有这个开关 → 一批 20 篇要手点 20 次上架。

本文件锁死：
  1. 不传 `publish` → `status=0`（默认安全，回归）；
  2. 传 `publish=true` → `status=1`，且回包 `published=true`（不再谎报）；
  3. `type=lecture` 同样生效（与 article 共用分支）。
"""
import io

from app.models.models import StudyMaterial


def _docx_bytes(paragraphs):
    from docx import Document
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _import_article(client, headers, name, body_lines):
    up = client.post("/api/materials/admin/import/upload",
                     files={"file": (name, _docx_bytes(body_lines))},
                     headers=headers)
    assert up.status_code == 200, up.text
    iid = up.json()["import_id"]
    return iid


def _confirm(client, headers, iid, **body):
    payload = {"subject": "gongzhuan"}
    payload.update(body)
    return client.post(f"/api/materials/admin/import/{iid}/confirm",
                       json=payload, headers=headers)


def test_article_defaults_unpublished(client, admin_headers, db_session):
    iid = _import_article(client, admin_headers, "pub_default.docx",
                          ["默认未上架：批改时先看正文再上线。", "这是第二段，保证有正文。"])
    resp = _confirm(client, admin_headers, iid, type="article", title="默认未上架")
    assert resp.status_code == 200, resp.text
    mid = resp.json()["material_ids"][0]
    row = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).one()
    assert row.status == 0
    assert resp.json()["published"] is False


def test_article_publish_true_goes_live(client, admin_headers, db_session):
    iid = _import_article(client, admin_headers, "pub_live.docx",
                          ["立即上架：本批直接对学生可见。", "第二段正文，避免被当成空文档。"])
    resp = _confirm(client, admin_headers, iid, type="article", title="立即上架文章",
                    publish=True)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    mid = data["material_ids"][0]
    row = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).one()
    assert row.status == 1
    assert data["published"] is True


def test_lecture_publish_true_goes_live(client, admin_headers, db_session):
    iid = _import_article(client, admin_headers, "pub_lecture.docx",
                          ["讲义也能立即上架。", "第二段正文。"])
    resp = _confirm(client, admin_headers, iid, type="lecture", title="立即上架讲义",
                    publish=True)
    assert resp.status_code == 200, resp.text
    mid = resp.json()["material_ids"][0]
    row = db_session.query(StudyMaterial).filter(StudyMaterial.material_id == mid).one()
    assert row.type == "lecture"
    assert row.status == 1
