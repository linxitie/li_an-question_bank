# -*- coding: utf-8 -*-
"""P1-4（2026-11-15）：题号缺号的「条带重跑回收」+ 无分隔符题号。

真机依据（`_run/qno41_recover_exp.json`，300dpi 条带实测）：
  · 第 47 题 → `47.肇南市“冠军杯"国际马拉松赛将于2024年9月21日隆重举行…` 逐字捞回；
  · 第 87 题 → `87.小张发现事故现场一片混乱，有3人倒地不起…` 逐字捞回；
  · 第 27 题 → `27在公安队伍建设中，公安机关及时奖励…`（**原卷没有分隔符**）；
  · 第 45 题 → `45东江市人民群众业余文化生活十分丰富…`（同上）；
  · 46 / 86 / 92 连 300dpi 条带也捞不到 → 只能体检点名，交人工核对。
"""
from __future__ import annotations

import pytest

from app.services import ocr_sidecar
from app.services.paper_ingest import ocr_retry, splitter


def _row(text, y=100.0, *, page=1, x=200.0, w=900.0, h=31.0, score=0.99):
    return {"text": text, "x": x, "y": y, "w": w, "h": h, "score": score, "page": page}


# ==================================================== 无分隔符题号（宽松版）
def test_loose_qno_recognised_for_number_without_separator():
    rows = [
        _row("26.上一题的题干足够长，可以当题干（　　）。", 100),
        _row("27在公安队伍建设中，公安机关及时奖励在各项工作中做出突出成绩的集体和", 160),
        _row("A.甲", 220),
        _row("28.下一题题干足够长，可以当题干（　　）。", 280),
    ]
    starts, issues = splitter.guard_qno_starts(rows)
    assert [no for _, no in starts] == [26, 27, 28]
    assert issues["loose"] == [27]


def test_loose_qno_out_of_window_rejected():
    """不连续的数字不当题号（`2024年` 这种连正则都不命中，55 距 26 太远也不认）。"""
    rows = [
        _row("26.上一题的题干足够长，可以当题干（　　）。", 100),
        _row("55在别处的某段说明文字，长度也够（　　）。", 160),
        _row("2024年7月15日至18日，党的二十届三中全会在北京召开。", 220),
    ]
    starts, issues = splitter.guard_qno_starts(rows)
    assert [no for _, no in starts] == [26]
    assert issues["loose"] == []


def test_loose_qno_does_not_duplicate_seen_number():
    rows = [
        _row("1.第一题题干足够长，可以当题干（　　）。", 100),
        _row("2.第二题题干足够长，可以当题干（　　）。", 160),
        _row("1在别处又出现的一次说明文字，长度也够（　　）。", 220),
    ]
    starts, issues = splitter.guard_qno_starts(rows)
    assert [no for _, no in starts] == [1, 2]
    assert issues["loose"] == []


def test_loose_qno_prefix_is_stripped_from_stem():
    lines = ["26.上一题的题干足够长，可以当题干（　　）。", "A.甲",
             "27在公安队伍建设中，公安机关及时奖励在各项工作中做出突出成绩的集体和个人",
             "A.乙", "B.丙"]
    starts, _ = splitter.guard_qno_starts([{"text": t} for t in lines])
    items = splitter.split_questions(lines, starts=starts)
    assert [it["no"] for it in items] == [26, 27]
    assert items[1]["stem"].startswith("在公安队伍建设中")


# ==================================================== 缺号条带：同页 / 跨页
def _seq_rows(nums, page=1, step=60.0, y0=100.0):
    return [_row(f"{n}.第{n}题的题干足够长，可以当题干（　　）。", y0 + i * step, page=page)
            for i, n in enumerate(nums)]


def test_find_number_holes_same_page_single_strip():
    rows = _seq_rows([1, 2, 3, 5])
    starts, _ = splitter.guard_qno_starts(rows)
    holes = ocr_retry.find_number_holes(rows, starts)
    assert len(holes) == 1
    assert holes[0]["missing_nos"] == [4]
    assert holes[0]["page"] == 1 and holes[0]["kind"] == "qno_missing"
    assert holes[0]["y0"] < holes[0]["y1"]


def test_find_number_holes_cross_page_three_strips():
    rows = _seq_rows([45 - 1], page=15, y0=300.0) + _seq_rows([45 + 3], page=17, y0=100.0)
    starts, _ = splitter.guard_qno_starts(rows)
    holes = ocr_retry.find_number_holes(rows, starts)
    assert [h["page"] for h in holes] == [15, 16, 17]      # 页尾 + 中间整页 + 页首
    assert {tuple(h["missing_nos"]) for h in holes} == {(45, 46, 47)}


def test_find_number_holes_respects_cap():
    rows = _seq_rows([1, 9, 17, 25, 33, 41, 49], step=60.0)
    starts, _ = splitter.guard_qno_starts(rows)
    holes = ocr_retry.find_number_holes(rows, starts, max_total=3)
    assert len(holes) == 3


def test_find_number_holes_empty_when_no_gap():
    rows = _seq_rows([1, 2, 3])
    starts, _ = splitter.guard_qno_starts(rows)
    assert ocr_retry.find_number_holes(rows, starts) == []


# ==================================================== 回收：只认本组缺号
def test_recover_into_accepts_loose_number_of_missing_group(monkeypatch, tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(ocr_sidecar, "available", lambda: (True, ""))
    monkeypatch.setattr(
        ocr_sidecar, "read_region_text",
        lambda *a, **kw: [{"text": "27在公安队伍建设中，公安机关及时奖励在各项工作中做出突出成绩的集体和",
                           "score": 0.99, "x": 95.6, "y": 369.6, "w": 419.5, "h": 11.8}])
    rows = _seq_rows([26], page=7, y0=300.0) + _seq_rows([28], page=8, y0=200.0)
    starts, _ = splitter.guard_qno_starts(rows)
    holes = ocr_retry.find_number_holes(rows, starts)
    out, stats = ocr_retry.recover_into(str(pdf), rows, layout_dpi=200, holes=holes)
    # 两条带（p7 页尾 + p8 页首）都会重跑；替身对两条带返回同一行，所以它会各插一行
    # （真实场景两条带内容不重叠；去重按页内 y 做，跨页不合并 —— 这里不做过度断言）
    assert stats["recovered"] >= 1
    assert stats["rows"] >= 1
    assert any(r["text"].startswith("27") for r in out)


def test_recover_into_rejects_other_numbers(monkeypatch, tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(ocr_sidecar, "available", lambda: (True, ""))
    monkeypatch.setattr(
        ocr_sidecar, "read_region_text",
        lambda *a, **kw: [{"text": "99.别的题号，不该被这条缝接进来（　　）。",
                           "score": 0.99, "x": 95.6, "y": 369.6, "w": 419.5, "h": 11.8}])
    rows = _seq_rows([26], page=7, y0=300.0) + _seq_rows([28], page=8, y0=200.0)
    starts, _ = splitter.guard_qno_starts(rows)
    holes = ocr_retry.find_number_holes(rows, starts)
    out, stats = ocr_retry.recover_into(str(pdf), rows, layout_dpi=200, holes=holes)
    assert stats["recovered"] == 0
    assert stats["rejected"] >= 1
    assert not any(r["text"].startswith("99") for r in out)
