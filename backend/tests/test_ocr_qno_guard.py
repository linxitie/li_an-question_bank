# -*- coding: utf-8 -*-
"""P1（2026-11-15）：41 页整卷的题号缺号/重号治理。

真机证据（`_run/qno41_report.txt`，200dpi 实测）：
  · 缺号 8 个 [27,39,45,46,47,86,87,92] / 重号 5 组 [1,4,79,80,98] / 96 题；
  · **39 是我们自己丢的**：p11 既是图表页又夹着第 39 题，v1 整页丢 → 真题消失；
  · 1 / 4 是图内数字被当题号（p28「1.12-2」、p12「4.小时以内数封定神」）；
  · 79/80 是影印重复页（p32/p33 题号行 y、x、文本逐字相同）；
  · 98 是题号行被拆成两框（p40 y=1081 半行 + y=1125 完整行）。

本文件只测纯逻辑（不跑 OCR）：页判定、题号自洽、折行合并、页去重、starts 透传。
真机整卷数字见方案 §6。
"""
from __future__ import annotations

import pytest

from app.services import ocr_html
from app.services.paper_ingest import readers, splitter


def _row(text, y=100.0, *, page=1, x=200.0, w=900.0, h=31.0, score=0.99):
    return {"text": text, "x": x, "y": y, "w": w, "h": h, "score": score, "page": page}


HEADER = [
    "由于25年联考真题难度大，争议题多，本PDF最后面放了其他机构老师的答案供各位考生参考。",
    "25联考真题各大机构题库均未更新，所以缺少相关解析，可以添加店主微信txw1663，及时获取更新信息",
]


# ==================================================== P1-2 题号像不像题干
@pytest.mark.parametrize("line,expected", [
    ("39.公安机关的人民警察为了维护社会治安秩序，依法对有违法犯罪嫌疑的人员", True),
    ("1.12-2", False),                       # p28 楼层图标注
    ("125.60%", False),                      # 图表百分比
    ("98.为了", False),                       # 题号后太短（残缺半行）
    ("4.小时以内数封定神", True),              # 字面像题干 → 由"重复题号"规则挡
    ("这是一段没有题号的话", False),
])
def test_looks_like_question_start(line, expected):
    assert splitter.looks_like_question_start(line) is expected


def test_qno_guard_switch(monkeypatch):
    monkeypatch.delenv(splitter.QNO_GUARD_ENV, raising=False)
    assert splitter.qno_guard_enabled() is True
    monkeypatch.setenv(splitter.QNO_GUARD_ENV, "0")
    assert splitter.qno_guard_enabled() is False


# ==================================================== P1-2 行级题号自洽
def test_guard_drops_fake_numbers_from_figures():
    rows = [
        _row("1.2024年7月15日至18日，党的二十届三中全会在北京召开。会议提出，高质", 100),
        _row("以下为楼层平面图（单位：米）", 120),
        _row("1.12-2", 140, x=758.9),                  # p28 图内标注
        _row("685", 160, x=1296.9),
        _row("33.40%", 180, x=900.0),
        _row("2.下列说法正确的是（　　）。", 200),
    ]
    starts, issues = splitter.guard_qno_starts(rows)
    assert [no for _, no in starts] == [1, 2]
    assert [x["no"] for x in issues["rejected"]] == [1, 33]   # 1.12-2 / 33.40%
    assert issues["dup_dropped"] == []


def test_guard_drops_duplicate_numbers():
    rows = [
        _row("98.为了提高反诈宣传的精准性，情指中心民警小许对案件数据分析发现", 100),
        _row("99.下一题题干在这里，用来验证重复题号被挡住（　　）。", 140),
        _row("98.为了提高反诈宣传的精准性，情指中心民警小许对案件数据分析发现", 180),
    ]
    starts, issues = splitter.guard_qno_starts(rows)
    assert [no for _, no in starts] == [98, 99]
    assert [x["no"] for x in issues["dup_dropped"]] == [98]


def test_guard_allows_renumbering_after_section_header():
    """分段重新编号：中间有「二、多项选择题」时，允许题号从头再来（否则整段丢失）。"""
    rows = [
        _row("1.第一段第一题的题干内容足够长（　　）。", 100),
        _row("二、多项选择题（每题 2 分）", 140),
        _row("1.第二段重新从 1 开始编号的题干内容（　　）。", 180),
    ]
    starts, issues = splitter.guard_qno_starts(rows)
    assert [no for _, no in starts] == [1, 1]
    assert issues["restarts"] == [1]


def test_guard_keeps_rejected_line_text_in_body():
    """被挡掉的行不能删字：它只是不当新题起点，文字仍归上一题。"""
    rows = [
        _row("1.题干第一行，内容足够长可以当题干（　　）。", 100),
        _row("1.12-2", 140),
        _row("2.第二题题干（　　）。", 180),
    ]
    starts, _ = splitter.guard_qno_starts(rows)
    lines = [r["text"] for r in rows]
    items = splitter.split_questions(lines, starts=starts)
    assert [it["no"] for it in items] == [1, 2]
    assert "1.12-2" in " ".join(it["stem"] for it in items)


# ==================================================== P1-3b 折行题号合并
def test_merge_split_qno_rows_keeps_longer_line():
    rows = [
        _row("98.为了提高反诈室", 1081.1, page=40, x=391.2, h=20.0),
        _row("98.为了提高反诈宣传的精准性，情指中心民警小许对案件数据分析发现", 1125.3, page=40),
        _row("99.下一题", 1200.0, page=40),
    ]
    out, merged = splitter.merge_split_qno_rows(rows)
    assert [r["text"][:7] for r in out] == ["98.为了提高", "99.下一题"]
    assert out[0]["text"].startswith("98.为了提高反诈宣传的精准性")
    assert merged[0]["no"] == 98
    assert merged[0]["kept"].startswith("98.为了提高反诈宣传的精准性")


def test_merge_split_qno_rows_ignores_far_or_cross_page():
    rows = [
        _row("98.为了提高反诈室", 1081.1, page=40),
        _row("98.为了提高反诈宣传的精准性", 1400.0, page=40),   # y 差太大
        _row("98.为了提高反诈宣传的精准性", 1081.1, page=41),   # 跨页
    ]
    out, merged = splitter.merge_split_qno_rows(rows)
    assert len(out) == 3
    assert merged == []


# ==================================================== P1-1 图表页里的真题
def _chart_page(page=11, with_real=False):
    rows = [_row(t, 40 + i * 30, page=page) for i, t in enumerate(HEADER)]
    rows += [_row("东江市拟举办活动一览表", 120, page=page)]
    rows += [_row("文艺汇演", 150, page=page)]
    rows += [_row(f"{n}.{d}%", 300 + i * 30, page=page) for i, (n, d) in
             enumerate(((125, 6), (98, 3), (76, 8), (54, 1), (31, 9), (12, 4)))]
    # 行数必须 ≥ MIN_PAGE_LINES(20)，否则 page_kind 直接判 text（短页不判）
    rows += [_row(f"项目{i}", 520 + i * 30, page=page) for i in range(14)]
    if with_real:
        rows.append(_row("39.公安机关的人民警察为了维护社会治安秩序，依法对违法", 880, page=page))
    return rows


def test_chart_page_without_real_question_is_dropped():
    assert readers.page_kind(_chart_page(with_real=False)) == "chart"


def test_chart_page_with_real_question_is_kept():
    """41 页 p11 的回归：图表页夹着第 39 题 → 整页保留（假题号交给题号自洽挡）。"""
    assert readers.page_kind(_chart_page(with_real=True)) == "text"


def test_answer_page_still_dropped():
    rows = [_row(t, 40 + i * 30) for i, t in enumerate(HEADER)]
    rows += [_row(t, 120 + i * 30) for i, t in enumerate(["A", "B", "C", "D"] * 4)]
    rows += [_row(str(n), 640 + i * 30) for i, n in enumerate((12, 34, 56, 78, 90, 21, 43, 65))]
    assert readers.page_kind(rows) == "answer"


# ==================================================== P1-3a 影印重复页
def test_duplicate_page_dropped_once():
    page32 = [_row(t, 100 + i * 30, page=32) for i, t in enumerate(HEADER)] + [
        _row("79.2024年3月20日，海西省恒安市周边发生地震。地震发生后，海西省地震局测定", 1071.6, page=32, x=196.2),
        _row("80.2024年3月20日11时许，恒安市政府成立现场应急指挥部，开展路面塌陷应急", 1882.8, page=32, x=196.2),
    ]
    page33 = [{**r, "page": 33} for r in page32]          # 影印页：逐字相同
    page34 = [_row("81.下一道真题的题干内容足够长，不会被当成噪声（　　）。", 200, page=34)]
    kept, info = readers._dedup_pages(page32 + page33 + page34)
    assert info["duplicated_pages"] == [33]
    assert all(int(r["page"]) != 33 for r in kept)
    assert any(int(r["page"]) == 34 for r in kept)


def test_normal_adjacent_pages_kept():
    p1 = [_row(t, 40 + i * 30, page=1) for i, t in enumerate(HEADER)]
    p1 += [_row("1.第一题的题干足够长，可以当题干（　　）。", 200, page=1)]
    p2 = [_row(t, 40 + i * 30, page=2) for i, t in enumerate(HEADER)]
    p2 += [_row("2.第二题的题干足够长，可以当题干（　　）。", 200, page=2)]
    kept, info = readers._dedup_pages(p1 + p2)
    assert info["duplicated_pages"] == []
    assert len(kept) == len(p1) + len(p2)


# ==================================================== starts 透传
def test_split_questions_without_starts_is_legacy():
    lines = ["1.第一题（　　）。", "A.甲", "B.乙", "2.第二题（　　）。", "A.丙"]
    items = splitter.split_questions(lines)
    assert [it["no"] for it in items] == [1, 2]


def test_split_questions_honours_given_starts():
    """给了 starts 就完全照办：假题号行（不在 starts 里）不再切出新题，但文字留在本题正文里。"""
    lines = ["1.第一题（　　）。", "A.甲", "125.60%", "B.乙", "2.第二题（　　）。", "A.丙"]
    starts = [(0, 1), (4, 2)]
    items = splitter.split_questions(lines, starts=starts)
    assert [it["no"] for it in items] == [1, 2]
    body = items[0]["stem"] + "".join(items[0]["options"].values())
    assert "125.60%" in body


def test_is_noise_line_matches_drop_noise():
    cases = ["获取试卷更新", "公众号：题库", "第 3 页", "3/41", "———", "", "39.正常题目"]
    for text in cases:
        assert ocr_html.is_noise_line(text) is (text not in {"39.正常题目"})
