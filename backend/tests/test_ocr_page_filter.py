# -*- coding: utf-8 -*-
"""F1–F3（2026-11-15）：41 页整卷里的图表页/答案页排除 + 假题兜底。

真机证据（`_run/41p_pages.json`，200dpi）：
  · p11 图表页 61 行：短行 0.77、纯数字 0.52、正文长行 3、被误认成 **16 个"题号"** → 整页丢；
  · p41 答案页 121 行：短行 0.86、纯数字 0.41、题号 3 → 整页丢；
  · p16/p19/p25 图表页：短行 0.59/0.85/0.61、正文长行 4/3/3、题号 0/**1**/1；
    其中 p19/p25 各夹着 1 道真题 → **不能整页丢**，只剔除图表标签行；
  · p38（短行 0.45）、p12（0.38）、p13（0.43，含真题 41）→ 必须保留。
"""
from __future__ import annotations

from app.services import ocr_sidecar
from app.services.paper_ingest import readers, splitter


def _row(text, y, *, page=1, x=200.0, w=900.0, h=31.0, score=0.99):
    return {"text": text, "x": x, "y": y, "w": w, "h": h, "score": score, "page": page}


HEADER = [
    "由于25年联考真题难度大，争议题多，本PDF最后面放了其他机构老师的答案供各位考生参考。",
    "25联考真题各大机构题库均未更新，所以缺少相关解析，可以添加店主微信txw1663，及时获取更新信息",
]


def _page(kind: str, page: int = 1) -> list:
    """造一页：chart（数字图表，含成片假题号）/ table（表格标签 + 1 道真题）/ answer / text。"""
    rows = [_row(t, 40 + i * 30, page=page) for i, t in enumerate(HEADER)]
    if kind == "chart":
        # 真机 p11：整页数字/百分比，其中 16 行被 qno_of 误认成题号
        rows += [_row("东江市拟举办活动一览表（2024.09）", 120, page=page)]
        rows += [_row("文艺汇演", 150 + i * 30, page=page) for i in range(4)]
        rows += [_row(f"{n}.{d}%", 300 + i * 30, page=page) for i, (n, d) in
                 enumerate(((125, 6), (98, 3), (76, 8), (54, 1), (31, 9), (12, 4)))]
        rows += [_row(f"项目{i}", 520 + i * 30, page=page) for i in range(9)]
        return rows
    if kind == "table":
        # 真机 p19/p25：表格标签全是短词，但中间夹着 1 道真题（题号 39）
        rows += [_row(t, 120 + i * 30, page=page) for i, t in
                 enumerate(("①赵X", "街坊", "老李", "张某", "王某", "李某",
                            "考评内容", "长阳市", "鲜众安", "女", "男", "合计",
                            "得分", "扣分", "备注"))]
        rows += [_row("39.民警老张在处理一起纠纷时，下列做法正确的是（　　）。", 420, page=page)]
        rows += [_row("A.先控制现场再分别询问双方当事人并制作笔录，全程录音录像备查", 460, page=page)]
        rows += [_row("B.直接把双方带回派出所，等第二天上班再安排民警做询问笔录", 500, page=page)]
        return rows
    if kind == "answer":
        # 真机 p41：121 行里 104 行短标签、50 行纯数字、只有 3 个题号
        rows += [_row(t, 120 + i * 30, page=page)
                 for i, t in enumerate(["A", "B", "C", "D"] * 4)]
        rows += [_row(str(n), 640 + i * 30, page=page) for i, n in
                 enumerate((12, 34, 56, 78, 90, 21, 43, 65))]
        return rows
    # text：正常页（题干 + 选项都长）
    rows += [_row(f"{i}.题干第一行：下列说法正确的是（　　）。", 120 + i * 150, page=page)
             for i in range(1, 4)]
    rows += [_row("A.这是一个长度超过三十个字的长选项，用来模拟正常试卷的选项行内容", 180 + i * 150, page=page)  # noqa: E501
             for i in range(3)]
    rows += [_row("B.另一个同样超过三十个字的选项，保证这页的正文长行足够多", 210 + i * 150, page=page)
             for i in range(2)]
    return rows


# --------------------------------------------------------------- 页判定
def test_chart_page_detected():
    assert readers.page_kind(_page("chart")) == "chart"


def test_answer_page_detected():
    assert readers.page_kind(_page("answer")) == "answer"


def test_normal_page_kept():
    assert readers.page_kind(_page("text")) == "text"


def test_short_page_not_judged():
    rows = [_row("800", 40), _row("125.60%", 70), _row("男", 100)]
    assert readers.page_kind(rows) == "text"      # < 20 行不判


def test_headers_do_not_count_as_body_long_lines():
    """每页 2 行页眉广告（≥30 字）不能算正文长行，否则图表页永远判不出来。"""
    p = readers.page_profile(_page("chart"))
    assert p["long_body"] <= 4
    assert p["n"] >= 20


# --------------------------------------------------------------- 整页丢弃
def test_chart_and_answer_pages_dropped():
    rows = _page("text", page=1) + _page("chart", page=2) + _page("answer", page=3)
    kept, meta = readers._drop_non_text_pages(rows)
    assert meta["dropped_pages"] == [2, 3]
    assert meta["reasons"] == {2: "chart", 3: "answer"}
    assert all(int(r["page"]) == 1 for r in kept)


def test_table_page_with_real_question_is_kept_whole():
    """p19/p25 那种"表格页里夹着真题"：**不整页动**。

    首版把这类页也整页丢，结果真题 39/47/50/66 跟着消失（实测）；它们的零星标签
    交给 F3 `drop_junk_items` 按题兜底即可。
    """
    page = _page("table", page=1)
    kept, meta = readers._drop_non_text_pages(page)
    assert meta == {}                       # 一页没丢
    assert len(kept) == len(page)
    assert readers.page_kind(page) == "text"
    assert any("39.民警老张" in r["text"] for r in kept)


def test_drop_pages_noop_when_all_text():
    rows = _page("text", page=1) + _page("text", page=2)
    kept, meta = readers._drop_non_text_pages(rows)
    assert meta == {} and len(kept) == len(rows)


def test_page_filter_switch(monkeypatch):
    monkeypatch.setenv("PAPER_OCR_PAGE_FILTER", "0")
    assert readers.page_filter_enabled() is False
    monkeypatch.delenv("PAPER_OCR_PAGE_FILTER")
    assert readers.page_filter_enabled() is True


# --------------------------------------------------------------- 假题兜底
def test_junk_item_without_chinese():
    assert splitter.is_junk_item({"stem": "125.60%", "options": {}}) is True


def test_junk_item_no_options_short_stem():
    assert splitter.is_junk_item({"stem": "①②③", "options": {}}) is True


def test_keep_short_stem_with_options():
    """简短的题干只要有选项就保留（"题干（）" 这种 5 字判断题也合法）。"""
    assert splitter.is_junk_item({"stem": "题干（）。", "options": {"A": "甲"}}) is False


def test_keep_long_stem_without_options():
    assert splitter.is_junk_item(
        {"stem": "根据以下情境材料，回答 4~5 题，材料正文很长很长", "options": {}}) is False


def test_drop_junk_items_counts():
    items = [
        {"no": 1, "stem": "正常题干（　　）。", "options": {"A": "甲"}},
        {"no": 2, "stem": "800", "options": {}},
        {"no": 3, "stem": "125.60%", "options": {}},
    ]
    kept, dropped = splitter.drop_junk_items(items)
    assert [it["no"] for it in kept] == [1]
    assert dropped == 2


# ------------------------------------------------------ 端到端：read_pdf_ocr
def test_read_pdf_ocr_drops_chart_page(monkeypatch, tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    layout = [_page("chart", page=1), _page("text", page=2)]

    def fake_read(path, *, max_pages=60, progress=None, with_layout=False):
        return "", {"pages": 2, "pages_done": 2, "pages_failed": 0, "truncated": False,
                    "errors": [], "seconds": 1.0, "dpi": 200, "layout": layout}

    monkeypatch.setattr(ocr_sidecar, "read_pdf_text", fake_read)
    monkeypatch.setenv("PAPER_OCR_RETRY", "0")          # 本用例只测页过滤
    out = readers.read_pdf_ocr(str(pdf))
    assert out["meta"]["ocr_pages"]["dropped_pages"] == [1]
    assert all("文艺汇演" not in ln for ln in out["lines"])
    assert any("题干第一行" in ln for ln in out["lines"])
