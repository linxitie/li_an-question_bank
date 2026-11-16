# -*- coding: utf-8 -*-
"""Q1（2026-11-15，导题缺号定位）：把"仍缺号的页/坐标"留下来。

设计取舍（为什么要 sidecar 而不是加库字段）：
  · 草稿目录已经存在（`parse_drafts/<id>/`，题图也放这），一个 JSON 就够；
  · 加列要走迁移，与项目「零迁移」的既有做法冲突；
  · 纯诊断数据，丢了也不影响导题 → 所有读写异常都只记日志。
"""
from __future__ import annotations

import json

import pytest

from app.models.models import StudyMaterial
from app.services import ocr_sidecar
from app.services.paper_ingest import ocr_retry, readers, service


def _row(text, y, *, page=1, x=200.0, w=900.0, h=31.0, score=0.99):
    return {"text": text, "x": x, "y": y, "w": w, "h": h, "score": score, "page": page}


def _layout_two_pages():
    """第 1 页有 1、2，第 2 页有 4 → 缺 3（模拟真卷缺号）。"""
    p1 = [
        _row("1.第一题的题干足够长，可以当题干（　　）。", 200, page=1),
        _row("A.甲", 260, page=1), _row("B.乙", 320, page=1),
        _row("2.第二题的题干足够长，可以当题干（　　）。", 380, page=1),
        _row("A.丙", 440, page=1), _row("B.丁", 500, page=1),
    ]
    p2 = [
        _row("4.第四题的题干足够长，可以当题干（　　）。", 200, page=2),
        _row("A.戊", 260, page=2), _row("B.己", 320, page=2),
    ]
    return [p1, p2]


# ------------------------------------------------------------------ 纯函数
def test_write_and_read_qno_gaps(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "_storage_root", lambda: str(tmp_path))
    gaps = [{"no": 3, "page": 1, "y0": 500.0, "y1": 560.0, "x0": 0.0, "x1": 1000.0,
             "missing": [3]}]
    path = service.write_qno_gaps(7, gaps, dpi=200, page_count=2)
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["v"] == service.QNO_GAPS_SCHEMA
    assert data["dpi"] == 200 and data["page_count"] == 2
    assert data["gaps"] == gaps
    assert service.read_qno_gaps(7)["gaps"] == gaps


def test_write_qno_gaps_removes_stale_file(tmp_path, monkeypatch):
    """重新导题后缺口补上了 → 旧 sidecar 必须删掉，不能让前端拿旧页码骗人。"""
    monkeypatch.setattr(service, "_storage_root", lambda: str(tmp_path))
    service.write_qno_gaps(8, [{"no": 3, "page": 1, "y0": 1.0, "y1": 2.0,
                                "x0": 0.0, "x1": 10.0, "missing": [3]}])
    service.write_qno_gaps(8, [])
    assert service.read_qno_gaps(8)["gaps"] == []
    assert not (tmp_path / "8" / service.QNO_GAPS_FILE).exists()


def test_read_qno_gaps_tolerates_missing_and_broken(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "_storage_root", lambda: str(tmp_path))
    assert service.read_qno_gaps(99) == {"v": 0, "dpi": 0, "page_count": 0, "gaps": []}
    broken = tmp_path / "100"
    broken.mkdir(parents=True)
    (broken / service.QNO_GAPS_FILE).write_text("{not json", encoding="utf-8")
    assert service.read_qno_gaps(100)["gaps"] == []


# ------------------------------------------------------------------ read_pdf_ocr 产出 meta
def test_read_pdf_ocr_reports_qno_gaps(monkeypatch):
    monkeypatch.setattr(ocr_sidecar, "read_pdf_text",
                        lambda *a, **kw: ("", {"layout": _layout_two_pages(), "pages": 2,
                                               "pages_done": 2, "dpi": 200}))
    monkeypatch.setattr(ocr_retry, "enabled", lambda: False)      # 不真的去重跑条带
    out = readers.read_pdf_ocr("x.pdf")
    meta = out["meta"]
    assert meta["qno_gaps_dpi"] == 200
    gaps = meta["qno_gaps"]
    assert [g["no"] for g in gaps] == [3]
    # 缺口落在"上一题（第 1 页第 2 题）之后"：y0 应大于第 2 题那行的 y，且页面合法
    assert gaps[0]["page"] in (1, 2)
    assert gaps[0]["y0"] < gaps[0]["y1"]
    assert gaps[0]["missing"] == [3]


def test_read_pdf_ocr_no_gap_no_key(monkeypatch):
    """没有缺号 → 不产生 qno_gaps（行为与改动前逐字节一致）。"""
    rows = _layout_two_pages()
    rows[1] = [_row("3.第三题的题干足够长，可以当题干（　　）。", 600, page=1)]
    monkeypatch.setattr(ocr_sidecar, "read_pdf_text",
                        lambda *a, **kw: ("", {"layout": rows, "pages": 2,
                                               "pages_done": 2, "dpi": 200}))
    monkeypatch.setattr(ocr_retry, "enabled", lambda: False)
    out = readers.read_pdf_ocr("x.pdf")
    assert "qno_gaps" not in out["meta"]


# ------------------------------------------------------------------ fill_draft 落盘
def _material(db, title="Q1 探针"):
    m = StudyMaterial(subject="gongzhuan", type="paper", status=1,
                      title=title, creator_id=2)
    db.add(m)
    db.commit()
    return m


def test_fill_draft_writes_sidecar(monkeypatch, db_session, tmp_path):
    monkeypatch.setattr(service, "_storage_root", lambda: str(tmp_path))
    gaps = [{"no": 3, "page": 1, "y0": 500.0, "y1": 560.0, "x0": 0.0, "x1": 1000.0,
             "missing": [3]}]

    def fake_read_any(path, ext, progress=None):
        return {"lines": ["1.题干（　　）。", "A、甲", "B、乙", "C、丙", "D、丁"],
                "images": [],
                "meta": {"reader": "pdf-ocr", "pages": 2, "parsed_pages": 2, "scanned": True,
                         "truncated": False, "failed_pages": [],
                         "qno_gaps": gaps, "qno_gaps_dpi": 200}}
    monkeypatch.setattr(readers, "read_any", fake_read_any)

    draft = service.create_draft(db_session, _material(db_session), ext="pdf",
                                 status="parsing", actor_id=2, message="OCR 排队中")
    db_session.commit()
    service.fill_draft(db_session, draft, ext="pdf", abs_path="x.pdf")
    db_session.commit()
    assert draft.status == "pending"
    assert service.read_qno_gaps(draft.draft_id)["gaps"] == gaps


def test_fill_draft_sidecar_failure_does_not_break_draft(monkeypatch, db_session, tmp_path):
    """写盘失败（磁盘满/权限）→ 只记日志，草稿照样 pending。"""
    monkeypatch.setattr(service, "_storage_root", lambda: str(tmp_path))

    def boom(*a, **kw):
        raise OSError("disk full")
    monkeypatch.setattr(service, "write_qno_gaps", boom)

    def fake_read_any(path, ext, progress=None):
        return {"lines": ["1.题干（　　）。", "A、甲", "B、乙", "C、丙", "D、丁"],
                "images": [],
                "meta": {"reader": "pdf-ocr", "pages": 1, "parsed_pages": 1, "scanned": True,
                         "qno_gaps": [{"no": 3, "page": 1, "y0": 1, "y1": 2, "x0": 0, "x1": 1,
                                       "missing": [3]}], "qno_gaps_dpi": 200}}
    monkeypatch.setattr(readers, "read_any", fake_read_any)

    draft = service.create_draft(db_session, _material(db_session, "Q1 写盘失败"), ext="pdf",
                                 status="parsing", actor_id=2, message="OCR 排队中")
    db_session.commit()
    service.fill_draft(db_session, draft, ext="pdf", abs_path="x.pdf")
    db_session.commit()
    assert draft.status == "pending" and draft.item_count == 1
