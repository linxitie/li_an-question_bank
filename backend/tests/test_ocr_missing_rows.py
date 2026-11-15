# -*- coding: utf-8 -*-
"""T5（2026-11-14）：扫描件「整行漏检」回收 —— 缺行检测 / 条带重跑 / 回填去重。

真机缺陷（5 页探针第 9 题）：C 行被斜向水印压住，rapidocr **连框都不出**，
`splitter` 只看到 B→D 之间 120px 的空白 → C 永远空。补标签（T3）修不了"行不存在"。
本文件用真机实测坐标（`_run/q9_ocr_items.json`）做回归，不跑真 OCR。
"""
from __future__ import annotations

import json

import pytest

from app.models.models import StudyMaterial
from app.services import ocr_sidecar
from app.services.paper_ingest import ocr_retry, readers, service, splitter
from scripts.ocr.rapidocr_worker import crop_event, ocr_page

# --------------------------------------------------------------- 真机行坐标
#: 第 3 页第 9 题那一簇（200dpi，取自 `_run/q9_ocr_items.json`）
Q9_ROWS = [
    ("9.公安队伍是党和人民手中的“刀把子”，具有鲜明的纪律属性，必须在纪律作", 749.8, 264.3, 35.4),
    ("风建设上有更高的标准、更严的要求，坚持纪律面前一律平等，遵守纪律没有例外。", 811.7, 199.7, 34.2),
    ("根据人民警察纪律作风建设相关规定，下列民警行为递反组织纪律的是：", 871.2, 200.9, 30.7),
    ("A.小赵因堵车导致参加集中政治学习时迟到", 932.5, 266.7, 30.7),
    ("B.小钱在某案件结案后接受当事人答谢宴请", 991.5, 265.5, 30.7),
    ("D.小李未经批准着警服参加电视台征婚节目", 1111.7, 265.5, 33.0),
]


def _row(text, y, x=265.5, h=31.0, *, w=430.0, page=1, score=0.99):
    return {"text": text, "x": x, "y": y, "w": w, "h": h, "score": score, "page": page}


def _q9_rows(page=1):
    return [_row(t, y, x, h, page=page) for t, y, x, h in Q9_ROWS]


# ------------------------------------------------------------- S1 缺行检测
def test_find_holes_detects_q9():
    holes = ocr_retry.find_holes(_q9_rows())
    assert len(holes) == 1
    hole = holes[0]
    assert hole["qno"] == 9
    assert hole["missing"] == ["C"]                     # 只缺 C
    assert hole["page"] == 1
    # 条带落在 B 与 D 之间（上下各留 6px 容差），不把邻行切进来
    assert 991.5 + 30.7 / 2 - 6 - 0.1 <= hole["y0"] <= 991.5 + 30.7 / 2 + 0.1
    assert 1111.7 - 33.0 / 2 - 0.1 <= hole["y1"] <= 1111.7 - 33.0 / 2 + 6 + 0.1
    assert hole["x0"] < 200.0 < hole["x1"]              # 覆盖整栏（含缩进的题干行）
    assert hole["gap"] == pytest.approx(120.2, abs=0.1)


def test_find_holes_skips_when_options_complete():
    """同样的大间距，但四个选项都在 → 不是缺行（可能是段间距）。"""
    rows = _q9_rows() + [_row("C.小孙因个人原因拒绝所长安排的外出交流", 1050.0)]
    assert ocr_retry.find_holes(rows) == []


def test_find_holes_skips_when_all_missing():
    """四个选项全缺 = 整题没选项（判断题/整题漏），无法定位 → 不动。"""
    rows = [
        _row("7.题干", 100.0, 264.3),
        _row("题干续行", 160.0, 199.7),
        _row("8.下一题", 300.0, 264.3),
        _row("题干续行", 360.0, 199.7),
        _row("A.甲", 420.0, 265.5),
        _row("B.乙", 480.0, 265.5),
        _row("C.丙", 540.0, 265.5),
        _row("D.丁", 600.0, 265.5),
    ]
    assert ocr_retry.find_holes(rows) == []


def test_find_holes_ignores_normal_gaps():
    rows = [
        _row("3.题干", 100.0, 264.3),
        _row("题干续行", 160.0, 199.7),
        _row("A.甲", 220.0, 265.5),
        _row("B.乙", 292.0, 265.5),          # 72px = 1.2× 中位行距，未到 1.6×
        _row("D.丁", 352.0, 265.5),
    ]
    assert ocr_retry.find_holes(rows) == []


def test_find_holes_skips_page_head_fragment():
    """页首无题号的续块（第 7 题的 D）不能参与：它到第 8 题之间有 184px，但那不是洞。"""
    rows = [
        _row("D.担当", 267.0, 260.8, 38.9),
        _row("8.丽山市公安局金花派出所民警小龚在公交车站台等车回家时，发现一名男子正", 328.9, 265.5),
        _row("在扒窃。小龚上前抓捕时，遭其同伙持刀从背后袭击，身负重伤的他仍然死死抱住其", 388.5, 200.9, 29.5),
        _row("A.坚韧不拔", 509.9, 265.5, 31.8),
        _row("B.执法公正", 570.0, 264.3, 31.8),
        _row("C.英勇顽强", 630.7, 264.3, 35.4),
        _row("D.尽职尽责", 691.4, 265.5, 31.8),
    ]
    assert ocr_retry.find_holes(rows) == []


def test_find_holes_caps_per_page():
    rows = []
    y = 100.0
    for no in range(1, 11):
        rows.append(_row(f"{no}.题干", y, 264.3))
        rows.append(_row("题干续行", y + 60, 199.7))
        rows.append(_row("A.甲", y + 120, 265.5))
        rows.append(_row("B.乙", y + 180, 265.5))
        rows.append(_row("D.丁", y + 300, 265.5))     # 缺 C：B→D 是 120px
        y += 360.0
    holes = ocr_retry.find_holes(rows)
    assert len(holes) == ocr_retry.MAX_PER_PAGE
    assert [h["qno"] for h in holes] == list(range(1, 9))


# --------------------------------------------------------- S3 回填与去重
def _recovered_c():
    return {"text": "C.小孙因个人原因拒绝所长安排的外出交流",
            "x": 263.1, "y": 1049.2, "w": 639.3, "h": 36.7,
            "score": 0.998, "page": 1}


def test_merge_inserts_c_in_place():
    rows = _q9_rows()
    merged = ocr_retry.merge(rows, [_recovered_c()], base_h=31.0)
    texts = [r["text"] for r in merged]
    assert len(merged) == len(rows) + 1
    assert texts.index("C.小孙因个人原因拒绝所长安排的外出交流") == texts.index(
        "B.小钱在某案件结案后接受当事人答谢宴请") + 1
    assert texts[-1] == "D.小李未经批准着警服参加电视台征婚节目"


def test_merge_drops_partial_neighbour_by_y():
    """同一条带重跑会多吐半截邻行（实测 `D小杰去级批准差敬服…`）→ 按坐标丢掉。"""
    rows = _q9_rows()
    noise = {"text": "D小杰去级批准差敬服参加中视台征婚书", "x": 263.0, "y": 1105.0,
             "w": 600.0, "h": 30.0, "score": 0.9, "page": 1}
    merged = ocr_retry.merge(rows, [_recovered_c(), noise], base_h=31.0)
    assert len(merged) == len(rows) + 1
    assert not any("中视台" in r["text"] for r in merged)


def test_merge_drops_duplicate_text_far_by_y():
    rows = _q9_rows()
    dup = {"text": "D小李未经批准着警服参加电视台征婚节目", "x": 263.0, "y": 1090.0,
           "w": 600.0, "h": 30.0, "score": 0.95, "page": 1}
    merged = ocr_retry.merge(rows, [dup], base_h=31.0)
    assert len(merged) == len(rows)


# ------------------------------------------------- S2/S4 端到端（替身 sidecar）
@pytest.fixture()
def fake_pdf(tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    return str(pdf)


def _fake_layout():
    return [[
        _row("9.公安队伍是党和人民手中的“刀把子”，具有鲜明的纪律属性，必须在纪律作", 749.8, 264.3, 35.4),
        _row("风建设上有更高的标准、更严的要求，坚持纪律面前一律平等，遵守纪律没有例外。", 811.7, 199.7, 34.2),
        _row("根据人民警察纪律作风建设相关规定，下列民警行为递反组织纪律的是：", 871.2, 200.9, 30.7),
        _row("A.小赵因堵车导致参加集中政治学习时迟到", 932.5, 266.7, 30.7),
        _row("B.小钱在某案件结案后接受当事人答谢宴请", 991.5, 265.5, 30.7),
        _row("D.小李未经批准着警服参加电视台征婚节目", 1111.7, 265.5, 33.0),
        _row("10.锻造一支让党中央放心，人民群众满意的公安队伍", 1173.0, 266.7, 33.0),
    ]]


def test_read_pdf_ocr_recovers_missing_row(monkeypatch, fake_pdf):
    def fake_read(path, *, max_pages=60, progress=None, with_layout=False):
        assert with_layout is True
        return "", {"pages": 1, "pages_done": 1, "pages_failed": 0, "truncated": False,
                    "errors": [], "seconds": 1.0, "dpi": 200, "layout": _fake_layout()}

    calls = []

    def fake_region(path, *, page, rect, dpi=300, timeout=30.0):
        calls.append({"page": page, "rect": rect, "dpi": dpi})
        # worker 回的是 pt：377.7pt × 200/72 ≈ 1049px
        return [{"text": "C.小孙因个人原因拒绝所长安排的外出交流", "score": 0.998,
                 "x": 94.72, "y": 377.7, "w": 230.16, "h": 13.2}]

    monkeypatch.setattr(ocr_sidecar, "read_pdf_text", fake_read)
    monkeypatch.setattr(ocr_sidecar, "read_region_text", fake_region)
    monkeypatch.setattr(ocr_sidecar, "available", lambda: (True, ""))

    out = readers.read_pdf_ocr(fake_pdf)
    assert "C.小孙因个人原因拒绝所长安排的外出交流" in out["lines"]
    assert out["meta"]["ocr_retry"]["recovered"] == 1
    assert out["meta"]["ocr_retry"]["qnos"] == [9]
    assert calls and calls[0]["page"] == 1 and calls[0]["dpi"] == 300
    # 发出去的矩形是 pt（不是 px）：y 落在 B(991.5px→357pt) 与 D(1111.7px→400pt) 之间
    assert 355.0 < calls[0]["rect"][1] < calls[0]["rect"][3] < 402.0

    items = splitter.split_questions(out["lines"])
    q9 = next(it for it in items if it["no"] == 9)
    assert q9["options"]["C"] == "小孙因个人原因拒绝所长安排的外出交流"
    assert q9["flags"] == []


def test_recover_disabled_by_env(monkeypatch, fake_pdf):
    monkeypatch.setenv("PAPER_OCR_RETRY", "0")

    def boom(*a, **kw):                                # noqa: ANN001
        raise AssertionError("关掉开关后不许调用条带重跑")

    monkeypatch.setattr(ocr_sidecar, "read_region_text", boom)
    stats = ocr_retry.recover_into(fake_pdf, _q9_rows(), layout_dpi=200)[1]
    assert stats["skipped"] == "PAPER_OCR_RETRY=0"
    assert stats["holes"] == 0


def test_recover_timeout_is_lenient(monkeypatch, fake_pdf):
    def slow(*a, **kw):                                # noqa: ANN001
        raise ocr_sidecar.OcrTimeout("条带重跑超时")

    monkeypatch.setattr(ocr_sidecar, "available", lambda: (True, ""))
    monkeypatch.setattr(ocr_sidecar, "read_region_text", slow)
    rows = _q9_rows()
    out_rows, stats = ocr_retry.recover_into(fake_pdf, rows, layout_dpi=200)
    assert out_rows == rows                            # 原样返回，绝不因补行失败而炸
    assert stats["failed"] == 1
    assert stats["skipped"] == "条带重跑超时"


def test_recover_skips_when_runtime_missing(monkeypatch, fake_pdf):
    monkeypatch.setattr(ocr_sidecar, "available", lambda: (False, "OCR 运行时没装"))
    rows = _q9_rows()
    out_rows, stats = ocr_retry.recover_into(fake_pdf, rows, layout_dpi=200)
    assert out_rows == rows
    assert stats["holes"] == 1 and stats["recovered"] == 0
    assert "没装" in stats["skipped"]


# --------------------------------------------- worker：裁剪→pt 坐标换算
class _Rect:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.x1 = sorted((float(x0), float(x1)))
        self.y0, self.y1 = sorted((float(y0), float(y1)))
        self.is_empty = (self.x1 - self.x0) <= 0 or (self.y1 - self.y0) <= 0

    def __and__(self, other):                          # noqa: ANN001
        return _Rect(max(self.x0, other.x0), max(self.y0, other.y0),
                     min(self.x1, other.x1), min(self.y1, other.y1))


class _Pixmap:
    def __init__(self, w, h):
        self.w, self.h = w, h

    def tobytes(self, fmt):                            # noqa: ANN001
        return b"png"


class _Page:
    def __init__(self, clip):
        self.rect = _Rect(0, 0, 595.276, 841.89)
        self.clip = clip

    def get_pixmap(self, dpi, clip):                   # noqa: ANN001
        self.clip = clip
        return _Pixmap(int(clip.x1 - clip.x0), int(clip.y1 - clip.y0))


class _Doc:
    page_count = 1

    def __init__(self, clip):
        self.page = _Page(clip)

    def __getitem__(self, i):                          # noqa: ANN001
        return self.page

    def close(self):
        pass


class _Pymupdf:
    Rect = _Rect

    def __init__(self, clip):
        self._clip = clip

    def open(self, path):                              # noqa: ANN001
        return _Doc(self._clip)


class _NP:
    uint8 = "u8"

    @staticmethod
    def frombuffer(b, dtype):                          # noqa: ANN001
        return b


class _CV2:
    IMREAD_COLOR = 1

    @staticmethod
    def imdecode(arr, flag):                           # noqa: ANN001
        return arr


class _Engine:
    """假引擎：返回**裁剪图内**的像素框（裁剪原点在 60,360pt、300dpi）。"""

    def __call__(self, arr):                           # noqa: ANN001
        return [([[30, 62], [900, 62], [900, 118], [30, 118]],
                 "C.小孙因个人原因拒绝所长安排的外出交流", 0.998)]


def test_crop_event_maps_pixels_back_to_points():
    fake = _Pymupdf(_Rect(60, 360, 500, 400))
    evt = crop_event(_Engine(), _CV2(), _NP(), fake, "x.pdf", 1, [60, 360, 500, 400], 300)
    assert evt["t"] == "crop" and evt["page"] == 1
    line = evt["lines"][0]
    k = 72.0 / 300.0
    assert line["x"] == pytest.approx(60 + 30 * k, abs=0.01)
    assert line["y"] == pytest.approx(360 + 90 * k, abs=0.01)      # (62+118)/2 = 90
    assert line["w"] == pytest.approx(870 * k, abs=0.01)
    assert line["h"] == pytest.approx(56 * k, abs=0.01)


def test_crop_event_page_out_of_range():
    fake = _Pymupdf(_Rect(0, 0, 100, 100))
    with pytest.raises(ValueError, match="页码越界"):
        crop_event(_Engine(), _CV2(), _NP(), fake, "x.pdf", 3, [0, 0, 100, 100], 300)


def test_ocr_page_crop_still_filters_empty_text():
    class _EmptyEngine:
        def __call__(self, arr):                       # noqa: ANN001
            return [([[0, 0], [10, 0], [10, 10], [0, 10]], "   ", 0.9)]

    assert ocr_page(_EmptyEngine(), _CV2(), _NP(), b"png", with_layout=True) == []


# ------------------------------------------------------------- S4 观测/开关
def test_fill_draft_warns_recovered_rows(monkeypatch, db_session):
    """补回来的行要在草稿体检里说出来（"这行是补的，请对着原卷核对"）。"""
    material = StudyMaterial(subject="gongzhuan", type="paper", status=1,
                             title="T5 补行探针", creator_id=2)
    db_session.add(material)
    db_session.commit()

    def fake_read_any(path, ext, progress=None):          # noqa: ANN001
        return {"lines": ["9、题干（　　）。", "A、甲", "B、乙",
                          "C、小孙因个人原因拒绝所长安排的外出交流", "D、丁"],
                "images": [],
                "meta": {"reader": "pdf-ocr", "pages": 1, "parsed_pages": 1,
                         "scanned": True, "truncated": False, "failed_pages": [],
                         "ocr_retry": {"holes": 1, "recovered": 1, "rows": 1, "failed": 0,
                                       "qnos": [9], "recovered_qnos": [9],
                                       "seconds": 2.7, "skipped": ""}}}
    monkeypatch.setattr(readers, "read_any", fake_read_any)

    draft = service.create_draft(db_session, material, ext="pdf", status="parsing",
                                 message="OCR 排队中")
    db_session.commit()
    service.fill_draft(db_session, draft, ext="pdf", abs_path="x.pdf")
    db_session.commit()

    warns = "\n".join(json.loads(draft.warnings_json))
    assert "整行漏检" in warns and "第 9 题" in warns


def test_roundtrip_keeps_readers_base_height():
    """`base_height` / `is_watermark_row` 拆出来后行为不变（T2 的旧判定不能漂）。"""
    rows = [_row("A.甲", 100.0, h=31.0), _row("正文行", 160.0, h=30.0),
            _row("五星好", 200.0, h=187.5)]
    assert readers.base_height(rows) == 31.0        # 偶数个取上中位；水印 187.5 已排除
    assert readers.is_watermark_row(rows[2], 30.0) is True
    assert readers.is_watermark_row(rows[0], 30.0) is False
