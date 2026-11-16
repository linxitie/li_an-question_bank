# -*- coding: utf-8 -*-
"""Q5 实测暴露的 3 处修复（2026-11-15，导题缺号定位收尾）。

三条都是**真机探针**撞出来的，不是纸面推演：
  ① 缺号下界写死为 1 → 拆分上传（只传 p15 起的片段）被算成"缺号 44 个"；
  ② 跨页缺口取了"下一题页首" → 第 46 题（在 p16）被指到 p17；
  ③ 条带从半句开始出框（`的46.为提升…`）→ 补回了却不成题，第 45 题把第 46 题吞掉。
"""
from __future__ import annotations

import pytest

from app.services import ocr_sidecar
from app.services.paper_ingest import ocr_retry, readers, splitter


def _row(text, y=100.0, *, page=1, x=200.0, w=900.0, h=31.0, score=0.99):
    return {"text": text, "x": x, "y": y, "w": w, "h": h, "score": score, "page": page}


def _q(text, y, *, page=1):
    return _row(text, y, page=page)


# ============================================ ① 缺号下界 = min(卷内题号)
def test_missing_starts_from_min_number_not_one():
    """片段从第 44 题开始 → 只报 45/46/47，不能把 1–43 也算缺号。"""
    rows = [_q("44.第 44 题题干足够长，可以当题干（　　）。", 100),
            _q("A.甲", 160), _q("B.乙", 220),
            _q("48.第 48 题题干足够长，可以当题干（　　）。", 280)]
    starts, _ = splitter.guard_qno_starts(rows)
    items = splitter.split_questions([r["text"] for r in rows], starts=starts)
    warns = splitter.draft_warnings(items)
    missing_line = next(w for w in warns if w.startswith("题号缺号"))
    assert "45" in missing_line and "46" in missing_line and "47" in missing_line
    assert "1," not in missing_line.replace("45", "").replace("46", "").replace("47", "")


def test_number_holes_use_min_number():
    rows = [_q("44.第 44 题题干足够长（　　）。", 100), _q("48.第 48 题题干足够长（　　）。", 400)]
    starts, _ = splitter.guard_qno_starts(rows)
    holes = ocr_retry.find_number_holes(rows, starts)
    assert {h["qno"] for h in holes} == {45}
    assert holes[0]["missing_nos"] == [45, 46, 47]


# ============================================ ② 跨页缺口：主选上一题所在页 + alt_page
def test_cross_page_gap_prefers_previous_page_and_reports_alt():
    """第 45 题在 p16 尾部、第 48 题在 p17 → 缺号 46/47 的主选页应是 p16，alt 是 p17。"""
    rows = [
        _q("44.第 44 题题干足够长（　　）。", 800, page=16),
        _q("A.甲", 860, page=16), _q("B.乙", 920, page=16),
        _q("C.丙", 980, page=16), _q("D.丁", 1040, page=16),
        _q("48.第 48 题题干足够长（　　）。", 120, page=17),
    ]
    starts, _ = splitter.guard_qno_starts(rows)
    holes = ocr_retry.find_number_holes(rows, starts)
    assert holes, "跨页缺口应至少给出 1 条条带"
    first = holes[0]
    assert first["page"] == 16                      # 主选 = 上一题所在页（第 46 题就在这）
    assert first["alt_page"] == 17                  # 备选 = 下一题所在页（第 86 题在这）
    assert first["y0"] > 1040                       # 起点在上一题最后一行之后
    assert any(h["page"] == 17 for h in holes)      # 备选页也要真的去重跑


def test_same_page_gap_has_no_alt_page():
    rows = _seq = [
        _q("1.第 1 题题干足够长（　　）。", 100),
        _q("3.第 3 题题干足够长（　　）。", 400),
    ]
    starts, _ = splitter.guard_qno_starts(rows)
    holes = ocr_retry.find_number_holes(rows, starts)
    assert len(holes) == 1 and holes[0]["page"] == 1 and holes[0]["alt_page"] == 0


# ============================================ ③ 题号不在行首 → 削到行首
def test_locate_qno_in_line_only_short_prefix():
    assert splitter.locate_qno_in_line("的46.为提升地铁站的应急响应能力，民安", {46}) == \
        "46.为提升地铁站的应急响应能力，民安"
    # 前缀太长不动手（避免把正常句子削掉）
    assert splitter.locate_qno_in_line("这是一段很长很长的前缀文字46.某题", {46}) is None
    # 题号不在允许集合里也不动手
    assert splitter.locate_qno_in_line("的99.某题", {46}) is None


def test_recover_accepts_qno_after_short_prefix(monkeypatch, tmp_path):
    """条带返回「的46.为提升…」→ 归一化后插入，并成为题号起点（第 45 题不再吞 46）。"""
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(ocr_sidecar, "available", lambda: (True, ""))
    monkeypatch.setattr(
        ocr_sidecar, "read_region_text",
        lambda *a, **kw: [{"text": "的46.为提升地铁站的应急响应能力，民安市公安局地铁分局",
                           "score": 0.99, "x": 300.0, "y": 1180.0, "w": 600.0, "h": 12.0}])
    rows = [
        _q("44.第 44 题题干足够长（　　）。", 900, page=16),
        _q("45.第 45 题题干足够长（　　）。", 960, page=16),
        _q("A.甲", 1020, page=16), _q("B.乙", 1080, page=16),
        _q("48.第 48 题题干足够长（　　）。", 140, page=17),
    ]
    starts, _ = splitter.guard_qno_starts(rows)
    holes = ocr_retry.find_number_holes(rows, starts)
    out, stats = ocr_retry.recover_into(str(pdf), rows, layout_dpi=200, holes=holes)
    assert stats["recovered"] >= 1
    fixed = [r for r in out if r["text"].startswith("46.")]
    assert fixed, "归一化后应以 46. 开头"
    starts2, _ = splitter.guard_qno_starts(out)
    assert 46 in [no for _, no in starts2]
    items = splitter.split_questions([r["text"] for r in out], starts=starts2)
    assert 46 in [it["no"] for it in items]
    stem45 = next(it["stem"] for it in items if it["no"] == 45)
    assert "为提升地铁站" not in stem45             # 46 的内容不再被吞进 45
