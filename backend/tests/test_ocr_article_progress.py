# -*- coding: utf-8 -*-
"""P2（扫描件 OCR 文章/讲义）的进度与兜底单测。

锁三件事：
  1. 进度写进 `parse_result._ocr`（零迁移口径）；
  2. `/import/{id}/status` 把进度回给前端（只加字段）；
  3. 卡在 processing 超 40 分钟 → 查询时惰性判失败（D6=A），不会永远"解析中"。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from app.api.v1.library.materials import _write_import_progress
from app.models.models import MaterialImportRecord


def _mk_record(db, *, status="processing", ocr=None, age_minutes=0):
    rec = MaterialImportRecord(
        file_name="scan.pdf", file_type="pdf", file_size=1024,
        parse_mode="async(ocr)", parse_status=status, uploader_id=2,
        create_time=datetime.now() - timedelta(minutes=age_minutes),
        parse_result=json.dumps({"_tmp": "", "_ocr": ocr or {}}, ensure_ascii=False),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def test_write_import_progress_merges_into_parse_result(db_session):
    rec = _mk_record(db_session, ocr={"done": 0, "total": 24, "phase": "queued"})
    _write_import_progress(db_session, rec.import_id, done=6, total=24, phase="ocr")
    db_session.expire_all()
    row = db_session.query(MaterialImportRecord).filter(
        MaterialImportRecord.import_id == rec.import_id).first()
    info = json.loads(row.parse_result)["_progress"]
    assert info["done"] == 6 and info["total"] == 24 and info["phase"] == "ocr"
    # 原有内部键不能被吞掉
    assert "_tmp" in json.loads(row.parse_result)


def test_status_returns_progress(client, admin_headers, db_session):
    rec = _mk_record(db_session, ocr={"done": 9, "total": 24, "phase": "ocr"})
    r = client.get(f"/api/materials/admin/import/{rec.import_id}/status",
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["parse_status"] == "processing"
    assert data["progress"]["done"] == 9
    assert data["progress"]["total"] == 24
    assert data["progress"]["percent"] == 37


def test_stale_processing_becomes_failed(client, admin_headers, db_session):
    rec = _mk_record(db_session, ocr={"done": 1, "total": 24}, age_minutes=41)
    r = client.get(f"/api/materials/admin/import/{rec.import_id}/status",
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["parse_status"] == "failed"
    assert "超时中断" in (data["error_message"] or "")
