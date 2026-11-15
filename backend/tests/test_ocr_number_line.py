# -*- coding: utf-8 -*-
"""T6（2026-11-15）：题号行漏检回收 / 页码噪声 / 选项被覆盖标记。

真机缺陷（用户指出）：第 5 题的选项其实是第 6 题的、第 6 题整题消失。
根因：第 6 题第一行（含题号 6）被 OCR 整行跳过 → 拆题器认不出新题 →
第 6 题并进第 5 题，且 `split_options` 同字母静默覆盖（第 5 题"看起来齐全"）。
本文件用第 2 页实测坐标做回归，不跑真 OCR。
"""
from __future__ import annotations

import pytest

from app.services import ocr_sidecar
from app.services.paper_ingest import ocr_retry, readers, splitter

#: 第 2 页那一簇（200dpi，取自 `_run/p2_ocr_items.json`）
P2_ROWS = [
    ("5.“中国人民警察节”是人民警察荣誉制度体系的承要组成部分。经党中央批准、", 546.4, 262.0),
    ("国务院批复，将每年1月10日设立为“中国人民警察节”。“中国人民警察节”是", 605.4, 198.5),
    ("A.第3个“中国人民警察节”", 786.9, 264.3),
    ("B.第4个“中国人民警察节”", 845.9, 263.1),
    ("C.第5个“中国人民警察节”", 907.2, 264.3),
    ("D.第6个“中国人民警察节”", 966.7, 264.3),
    ("的令球公共安全合作论坛在江苏省连云港市开幕，有122个国家共2100余人参会，", 1088.2, 199.7),
    ("国务委员、公安都部长王小洪出席并在主旨发言中指出;面对世界之变、时代之变、", 1148.9, 199.7),
    ("A.共同、综合、合作、可持续", 1330.4, 265.5),
    ("B.精细、务实、协商、可对话", 1390.5, 264.3),
    ("C.创新、共享、规范、可协同", 1451.3, 266.7),
    ("D.普惠、包容开放、可发展", 1509.6, 264.3),
    ("7.当千家万户沉浸在春节的团圆和欢笑时，西南某省东湖边检站民警老陈仍坚守", 1570.3, 266.7),
]


def _row(text, y, x=265.5, *, w=430.0, h=31.0, page=1, score=0.99):
    return {"text": text, "x": x, "y": y, "w": w, "h": h, "score": score, "page": page}


def _p2_rows(page=1):
    return [_row(t, y, x, page=page) for t, y, x in P2_ROWS]


# --------------------------------------------------- S1：第二组 A. 触发判洞
def test_option_restart_detects_missing_number_line():
    holes = ocr_retry.find_holes(_p2_rows())
    assert len(holes) == 1
    hole = holes[0]
    assert hole["kind"] == "number"          # 补回来必须是题号行
    assert hole["qno"] == 5
    assert hole["missing"] == []             # 字母不缺：第 5 题四个都在
    # 缝落在 D.第6个 与 下一行之间
    assert 966.7 < hole["y0"] < hole["y1"] < 1090.0
    assert hole["gap"] == pytest.approx(121.5, abs=0.2)


def test_missing_letters_still_works():
    """T5 的老触发不能被 T6 顶掉：第 9 题那种「缺 C」仍是 option 类洞。"""
    rows = [
        _row("9.题干", 100.0, 264.3),
        _row("题干续行", 160.0, 199.7),
        _row("A.甲", 220.0),
        _row("B.乙", 280.0),
        _row("D.丁", 400.0),
        _row("10.下一题", 470.0, 264.3),
    ]
    holes = ocr_retry.find_holes(rows)
    assert len(holes) == 1
    assert holes[0]["kind"] == "option"
    assert holes[0]["qno"] == 9 and holes[0]["missing"] == ["C"]


def test_option_restart_without_gap_is_ignored():
    """两组 A 挨得很近（没有 1.6× 的缝）→ 不判洞，避免误重跑。"""
    rows = [_row(t, y, x) for t, y, x in P2_ROWS]
    for r in rows:
        if r["y"] >= 1000.0:                 # 把后半段整体上移，缝消失
            r["y"] -= 200.0
    assert ocr_retry.find_holes(rows) == []


# --------------------------------------------------- S3：只收「题号行」
def test_number_hole_rejects_non_qno_line(monkeypatch, tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(ocr_sidecar, "available", lambda: (True, ""))
    monkeypatch.setattr(
        ocr_sidecar, "read_region_text",
        lambda *a, **kw: [{"text": "页眉噪声", "score": 0.99,
                           "x": 95.0, "y": 369.6, "w": 200.0, "h": 12.0}])
    rows = _p2_rows()
    out_rows, stats = ocr_retry.recover_into(str(pdf), rows, layout_dpi=200)
    assert out_rows == rows                  # 一个字都没收
    assert stats["rejected"] == 1 and stats["recovered"] == 0


def test_number_hole_accepts_qno_line_and_splits(monkeypatch, tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setattr(ocr_sidecar, "available", lambda: (True, ""))
    monkeypatch.setattr(
        ocr_sidecar, "read_region_text",
        lambda *a, **kw: [{"text": "6.2024年9月9日，以“变局下的合作共赢”为主题",
                           "score": 0.99, "x": 95.6, "y": 369.6, "w": 419.5, "h": 11.8}])
    rows = _p2_rows()
    out_rows, stats = ocr_retry.recover_into(str(pdf), rows, layout_dpi=200)
    assert stats["recovered"] == 1 and stats["rows"] == 1 and stats["rejected"] == 0
    texts = [r["text"] for r in out_rows]
    assert "6.2024年9月9日，以“变局下的合作共赢”为主题" in texts
    # 插在 D.第6个 之后、下一行之前
    assert texts.index("6.2024年9月9日，以“变局下的合作共赢”为主题") == \
        texts.index("D.第6个“中国人民警察节”") + 1

    items = splitter.split_questions([r["text"] for r in out_rows])
    by_no = {it["no"]: it for it in items}
    assert 6 in by_no, "第 6 题还是没拆出来"
    assert by_no[5]["options"]["C"] == "第5个“中国人民警察节”"
    assert by_no[5]["options"]["D"] == "第6个“中国人民警察节”"
    assert by_no[6]["options"]["A"] == "共同、综合、合作、可持续"


# --------------------------------------------------- S4a：页脚页码
def test_page_number_row_dropped():
    layout = [[
        _row("A.专注", 1871.6, 263.1, w=103.4, h=36.5),
        _row("B.执着", 1931.7, 262.0, w=102.2, h=36.5),
        _row("2", 2072.0, 802.3, w=24.7, h=29.5, score=0.9987),   # 页脚页码
    ]]
    texts = [r["text"] for r in readers._layout_lines(layout)]
    assert texts == ["A.专注", "B.执着"]


def test_body_numbers_are_kept():
    """正文里的数字（有邻居 / 不是最底行）不能被当页码删掉。"""
    layout = [[
        _row("2024年7月15日至18日，党的二十届三中全会在北京召开。", 400.0, 262.0, w=1200.0),
        _row("2025", 460.0, 262.0, w=90.0),
    ]]
    texts = [r["text"] for r in readers._layout_lines(layout)]
    assert texts == ["2024年7月15日至18日，党的二十届三中全会在北京召开。", "2025"]


def test_end_to_end_page_number_not_glued_to_option():
    """实测缺陷：`C.忠诚` 被拼成 `C.忠诚 2`。"""
    layout = [[
        _row("7.题干", 1570.3, 266.7, w=1163.0),
        _row("A.专注", 1871.6, 263.1, w=103.4, h=36.5),
        _row("B.执着", 1931.7, 262.0, w=102.2, h=36.5),
        _row("C.忠诚", 1991.2, 263.1, w=101.0, h=37.7),
        _row("2", 2072.0, 802.3, w=24.7, h=29.5, score=0.9987),
    ]]
    lines = [r["text"] for r in readers._layout_lines(layout)]
    items = splitter.split_questions(lines)
    assert items[0]["options"]["C"] == "忠诚"


# --------------------------------------------------- S4b：选项被覆盖标记
def test_option_overwrite_flag_added():
    lines = [
        "5.题干（　　）。",
        "A.第3个",
        "B.第4个",
        "C.第5个",
        "D.第6个",
        "下一题的第一行（题号被漏）",
        "A.共同",
        "B.精细",
        "C.创新",
        "D.普惠",
    ]
    items = splitter.split_questions(lines)
    assert len(items) == 1
    assert "选项被覆盖(A/B/C/D)" in items[0]["flags"]
    assert items[0]["options"]["A"] == "共同"      # 行为未变：仍是后者覆盖（只加提示）


def test_option_overwrite_absent_for_normal_question():
    lines = ["1.题干（　　）。", "A.甲", "B.乙", "C.丙", "D.丁"]
    items = splitter.split_questions(lines)
    assert not any("选项被覆盖" in f for f in items[0]["flags"])


def test_option_overwrites_helper():
    assert splitter.option_overwrites(["A.甲", "B.乙", "A.丙"]) == ["A"]
    assert splitter.option_overwrites(["A.甲", "B.乙", "C.丙", "D.丁"]) == []
