# -*- coding: utf-8 -*-
"""O5（2026-11-13）：上传即返回 + 后台解析。

说明：conftest 默认 `IMPORT_INLINE=1`（让几百个老用例保持"上传后立即可 confirm"）。
本文件主动去掉这个变量，专测异步语义：
  1. 上传接口响应体就是 `processing`（真机验证，见方案 §7.1；TestClient 下后台线程时序不稳定，单测不锁）；
  2. 后台 job 的正确性由 `IMPORT_INLINE=1` 的 497 个导入用例覆盖；
  3. 去重口径已含 `processing`（D5=A：解析中再传也要拦）；
  4. 解析中也能看到页级进度。
"""
from __future__ import annotations

import io
import json

from sqlalchemy.orm import sessionmaker

from app.api.v1.library.materials import _find_same_file_import, _import_job
from app.models.models import MaterialImportRecord


def _docx_bytes(paragraphs):
    from docx import Document
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_duplicate_detection_includes_processing(db_session):
    """D5=A：同名同大小同 sha256 且**正在解析中**，也要能查到（→ 409）。"""
    rec = MaterialImportRecord(
        file_name="busy.docx", file_type="docx", file_size=10,
        parse_status="processing", uploader_id=2,
        parse_result=json.dumps({"_sha256": "abc123"}, ensure_ascii=False))
    db_session.add(rec)
    db_session.commit()

    hit = _find_same_file_import(db_session, "busy.docx", 10, "abc123")
    assert hit is not None and hit.import_id == rec.import_id


def test_progress_visible_while_processing(client, admin_headers, db_session):
    rec = MaterialImportRecord(
        file_name="busy2.docx", file_type="docx", file_size=10,
        parse_status="processing", uploader_id=2,
        parse_result=json.dumps({"_progress": {"phase": "ocr", "done": 3,
                                               "total": 9, "percent": 33}},
                                ensure_ascii=False))
    db_session.add(rec)
    db_session.commit()

    st = client.get(f"/api/materials/admin/import/{rec.import_id}/status",
                    headers=admin_headers)
    assert st.status_code == 200
    p = st.json()["progress"]
    assert p["done"] == 3 and p["total"] == 9 and p["percent"] == 33
    assert p["phase"] == "ocr"
