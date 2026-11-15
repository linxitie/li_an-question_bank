# -*- coding: utf-8 -*-
"""T1–T3（2026-11-14）：扫描件坐标透传 / 水印几何过滤 / 选项标签按缩进补回。

真机缺陷（用户指出）：真卷第 1 页第 3 题的 C 行本来是独立一行，OCR 却丢了 `C.` 标签，
拆题器把它当 B 的续行 → C 空、B 变长；同时斜向水印（框高 187/343px）被当正文并进选项。
"""
from __future__ import annotations

from app.services.paper_ingest import readers, splitter
from scripts.ocr.rapidocr_worker import ocr_page


# --------------------------------------------------------------- T1：坐标透传
class _NP:
    uint8 = "u8"

    @staticmethod
    def frombuffer(b, dtype):        # noqa: ANN001
        return b


class _CV2:
    IMREAD_COLOR = 1

    @staticmethod
    def imdecode(arr, flag):         # noqa: ANN001
        return arr


class _Engine:
    """假引擎：返回 (box, text, score) 三元组，box 为四点多边形。"""

    def __call__(self, arr):         # noqa: ANN001
        return [
            ([[0, 100], [200, 100], [200, 130], [0, 130]], "B.乙", 0.99),
            ([[0, 40], [200, 40], [200, 70], [0, 70]], "A.甲", 0.99),
            ([[0, 200], [60, 200], [60, 230], [0, 230]], "五星好", 0.98),
        ]


def test_ocr_page_layout_returns_boxes():
    items = ocr_page(_Engine(), _CV2(), _NP(), b"png", with_layout=True)
    assert [it["text"] for it in items] == ["A.甲", "B.乙", "五星好"]     # 按 y 排好
    first = items[0]
    assert set(first) >= {"text", "x", "y", "w", "h", "score"}
    assert first["h"] == 30 and first["w"] == 200


def test_ocr_page_default_still_returns_texts():
    assert ocr_page(_Engine(), _CV2(), _NP(), b"png") == ["A.甲", "B.乙", "五星好"]


# --------------------------------------------------------- T2：水印几何过滤
def _box(text, *, x=264.0, y=100.0, w=430.0, h=31.0, score=0.99):
    return {"text": text, "x": x, "y": y, "w": w, "h": h, "score": score}


def _q3_layout():
    """真机实测的框（第 1 页第 3 题那一簇，数值取自 _run/q3_ocr_items.json）。"""
    return [[
        _box("A.坚持党对国家安全工作的绝对领导", x=266.7, y=1595.7, w=533.3, h=34.2),
        _box("B.坚持中国特色国家安全道路", x=264.3, y=1656.4, w=432.3, h=33.0),
        _box("坚持以人民安全为宗旨", x=278.4, y=1716.5, w=350.1, h=30.7, score=0.9993),
        _box("五星好", x=118.6, y=1751.3, w=185.6, h=187.5, score=0.9985),
        _box("D.坚持统筹发展和安全", x=264.3, y=1776.6, w=333.6, h=30.7),
    ]]


def test_layout_lines_drops_diagonal_watermark():
    rows = readers._layout_lines(_q3_layout())
    texts = [r["text"] for r in rows]
    assert "五星好" not in texts                       # 高 187.5 → 判斜向水印
    assert "坚持以人民安全为宗旨" in texts             # 正常行保留（等 T3 补标签）


def test_layout_lines_drops_isolated_low_conf_fragment():
    layout = [[_box("X", x=1092.5, y=842.9, w=34.1, h=23.6, score=0.866)]]
    assert readers._layout_lines(layout) == []


def test_layout_lines_keeps_short_normal_text():
    """`A.甲` 这种短选项不能被误当水印删掉。"""
    layout = [[_box("A.甲", w=120.0, h=30.0)]]
    assert [r["text"] for r in readers._layout_lines(layout)] == ["A.甲"]


# ------------------------------------------------- T3：缩进补标签 + 结构校验
def test_repair_recovers_missing_c_by_indent():
    rows = readers._layout_lines(_q3_layout())
    fixed = splitter.repair_option_tags(rows)
    texts = [r["text"] for r in fixed]
    assert "C.坚持以人民安全为宗旨" in texts
    assert "坚持以人民安全为宗旨" not in texts


def test_repair_leaves_stem_line_alone():
    """题干续行的 x=200，离选项缩进带（≈264）40px 以上 → 不许补标签。"""
    rows = [
        {"text": "3.题干第一行", "x": 200.0},
        {"text": "A.甲", "x": 264.3},
        {"text": "题干续行不缩进", "x": 200.0},
        {"text": "B.乙", "x": 264.3},
    ]
    fixed = splitter.repair_option_tags(rows)
    assert fixed[2]["text"] == "题干续行不缩进"


def test_end_to_end_q3_options_complete():
    rows = splitter.repair_option_tags(readers._layout_lines(_q3_layout()))
    lines = ["3.在平安中国建设中，总体国家安全观的核心要义……属于“根”和“魂”的是："]
    lines += [r["text"] for r in rows]
    items = splitter.split_questions(lines)
    assert len(items) == 1
    opts = items[0]["options"]
    assert opts["C"] == "坚持以人民安全为宗旨"
    assert "五星好" not in opts["B"]
    assert "选项不全" not in "".join(items[0]["flags"])


def test_long_option_gets_sticky_flag():
    lines = [
        "5.题干（　　）。",
        "A.甲",
        "B.乙" + "很长" * 80,
        "C.丙",
        "D.丁",
    ]
    items = splitter.split_questions(lines)
    assert "选项可能粘连" in items[0]["flags"]


# ------------------------------------------- 集成：read_pdf_ocr 走 with_layout
def test_read_pdf_ocr_uses_layout(monkeypatch, tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    payload = {
        "A.甲": _box("A.甲"),
        "B.乙": _box("B.乙"),
        "C 无标签": _box("丙丙丙"),
        "D.丁": _box("D.丁"),
        "water": _box("五星好", h=187.5, x=118.6),
    }
    layout = [[payload["A.甲"], payload["B.乙"], payload["C 无标签"],
               payload["water"], payload["D.丁"]]]

    def fake_read(path, *, max_pages=60, progress=None, with_layout=False):
        assert with_layout is True, "试卷导题必须请求坐标"
        return "A.甲\nB.乙\n丙丙丙\n五星好\nD.丁", {"pages": 1, "pages_done": 1,
                                                 "pages_failed": 0, "truncated": False,
                                                 "errors": [], "seconds": 1.0,
                                                 "layout": layout}
    from app.services import ocr_sidecar
    monkeypatch.setattr(ocr_sidecar, "read_pdf_text", fake_read)

    out = readers.read_pdf_ocr(str(pdf))
    assert "五星好" not in out["lines"]
    assert "C.丙丙丙" in out["lines"]
