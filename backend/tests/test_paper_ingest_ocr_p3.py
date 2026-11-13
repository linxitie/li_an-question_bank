# -*- coding: utf-8 -*-
"""P3（2026-11-13）：扫描件导题 —— OCR 读取 / 草稿异步 / 惰性超时。

覆盖：
  1. `readers.read_pdf_ocr`：走 OCR、去噪（通用 + 试卷专属）、**不挂图**；
  2. `read_pdf` 的扫描分支（parse_pdf_once 判 scanned → 转 OCR）；
  3. `fill_draft`：扫描件警告三条（无原图/请核对/失败页或截断）；
  4. 路由：扫描件返回 `parsing` 草稿；
  5. 卡在 parsing 超 40 分钟 → 查询时判 failed。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from app.models.models import MaterialFile, PaperParseDraft, StudyMaterial
from app.services import ocr_sidecar
from app.services.paper_ingest import readers, service

OCR_TEXT = "\n".join([
    "获取试卷更新，请关注公众号：gwyeasy",
    "店主微信 txw1663，本PDF最后有答案",
    "第二部分单项选择题",
    "1、人民警察首要的政治要求是（　　）。",
    "A、对党忠诚",
    "B、服务人民",
    "C、执法公正",
    "D、纪律严明",
    "第 2 页",
])


def _blank_pdf(path, pages=1):
    import pymupdf
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page()
    doc.save(str(path))
    doc.close()
    return str(path)


def test_read_pdf_ocr_filters_noise_and_has_no_images(monkeypatch, tmp_path):
    def fake_read(path, **kw):
        return OCR_TEXT, {"pages": 2, "pages_done": 2, "pages_failed": 0,
                          "truncated": False, "errors": [], "seconds": 18.0}
    monkeypatch.setattr(ocr_sidecar, "read_pdf_text", fake_read)

    out = readers.read_pdf_ocr(_blank_pdf(tmp_path / "s.pdf"), pages=2)
    joined = "\n".join(out["lines"])
    assert "1、人民警察首要的政治要求" in joined
    assert "公众号" not in joined and "店主微信" not in joined
    assert "第 2 页" not in joined
    assert out["images"] == []
    assert out["meta"]["scanned"] is True and out["meta"]["reader"] == "pdf-ocr"


def test_strip_inline_noise_keeps_option_text():
    """真机缺陷（2026-11-13）：广告粘在选项行尾 → 切掉广告、保留选项正文。"""
    assert (readers.strip_inline_noise("B、用党的创新理论武装全党 常加微信 txw1663 赠送最新")
            == "B、用党的创新理论武装全党")
    assert readers.strip_inline_noise("3、下列说法正确的是（　　）。 客服QQ 12345678") \
        == "3、下列说法正确的是（　　）。"
    assert readers.strip_inline_noise("C、执法公正 立即扫码领取") == "C、执法公正"
    assert readers.strip_inline_noise("公安工作必须坚持党的绝对领导 加QQ群 88990011") \
        == "公安工作必须坚持党的绝对领导"
    assert readers.strip_inline_noise("A、对党忠诚 微信号：abc12345") == "A、对党忠诚"
    # 第二轮真机：OCR 把「加微信」吃掉，只剩裸号 + 推广字
    assert readers.strip_inline_noise("B、用党的创新理论武装全党 xwl663赠送最") \
        == "B、用党的创新理论武装全党"


def test_strip_inline_noise_keeps_legit_mentions():
    """题干本身聊「微信支付」「扫码」不能当广告删（P3 第一版会整行误杀）。"""
    for line in ("关于微信支付的说法，正确的是（　　）。",
                 "下列属于新型支付方式的是（　　）。 A、扫码支付",
                 "群众路线是公安工作的根本工作路线",
                 "2024年7月15日至18日，党的二十届三中全会在北京召开",
                 "A、GA/T 1234标准"):
        assert readers.strip_inline_noise(line) == line
        assert not readers.PAPER_NOISE.search(line), line


def test_strip_inline_noise_drops_pure_ad_lines():
    for line in ("关注公众号：gwyeasy 领取全套资料", "店主微信 txw1663 加微信送资料"):
        assert readers.strip_inline_noise(line) == ""


def test_read_pdf_routes_scanned_to_ocr(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.services.material_parser.parse_pdf_once",
        lambda path, **kw: {"scanned": True, "pages": 3})

    def fake_ocr(path, *, pages=0, progress=None):
        return {"lines": ["1、题干"], "images": [],
                "meta": {"reader": "pdf-ocr", "pages": pages, "scanned": True}}
    monkeypatch.setattr(readers, "read_pdf_ocr", fake_ocr)

    out = readers.read_pdf(_blank_pdf(tmp_path / "s2.pdf"))
    assert out["meta"]["reader"] == "pdf-ocr"
    assert out["lines"] == ["1、题干"]


def test_fill_draft_scanned_adds_three_warnings(monkeypatch, db_session):
    material = StudyMaterial(subject="gongzhuan", type="paper", status=1,
                             title="P3 扫描件探针", creator_id=2)
    db_session.add(material)
    db_session.commit()

    def fake_read_any(path, ext, progress=None):
        if progress:
            progress("OCR 1/1 页")
        return {"lines": ["1、题干（　　）。", "A、甲", "B、乙", "C、丙", "D、丁"],
                "images": [],
                "meta": {"reader": "pdf-ocr", "pages": 2, "parsed_pages": 2,
                         "scanned": True, "truncated": False, "failed_pages": [2]}}
    monkeypatch.setattr(readers, "read_any", fake_read_any)

    draft = service.create_draft(db_session, material, ext="pdf", status="parsing",
                                 actor_id=2, message="OCR 排队中")
    db_session.commit()
    assert draft.status == "parsing"

    service.fill_draft(db_session, draft, ext="pdf", abs_path="x.pdf")
    db_session.commit()
    assert draft.status == "pending" and draft.item_count == 1
    warns = "\n".join(json.loads(draft.warnings_json))
    assert "扫描件 OCR" in warns and "逐题核对" in warns
    assert "识别失败" in warns


def test_parse_route_scanned_returns_parsing(client, admin_headers, db_session,
                                             monkeypatch, tmp_path):
    pdf = _blank_pdf(tmp_path / "scan_paper.pdf", pages=1)
    data = {"subject": "gongzhuan", "type": "paper", "placement": "both"}
    with open(pdf, "rb") as fh:
        up = client.post("/api/materials/admin/files/upload",
                         files={"file": ("scan_paper.pdf", fh.read())},
                         data=data, headers=admin_headers)
    assert up.status_code == 200, up.text
    mid = up.json()["material_id"]

    # 判定为扫描件 + 后台 job 不真跑（只验路由语义）
    monkeypatch.setattr("app.services.material_parser.parse_pdf_once",
                        lambda path, **kw: {"scanned": True, "pages": 41})
    import app.api.v1.library.materials as m
    monkeypatch.setattr(m, "_paper_parse_job", lambda *a, **kw: None)

    r = client.post(f"/api/materials/admin/{mid}/parse", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "parsing"
    assert "OCR" in (body.get("message") or "")

    row = db_session.query(PaperParseDraft).filter(
        PaperParseDraft.draft_id == body["draft_id"]).first()
    assert row is not None and row.status == "parsing"


def test_parse_route_scanned_is_idempotent_while_parsing(client, admin_headers, db_session,
                                                         monkeypatch, tmp_path):
    """OCR 在跑时再点「导题」→ 复用同一份草稿，不重复起后台任务（2026-11-13）。"""
    pdf = _blank_pdf(tmp_path / "scan_paper2.pdf", pages=1)
    data = {"subject": "gongzhuan", "type": "paper", "placement": "both"}
    with open(pdf, "rb") as fh:
        up = client.post("/api/materials/admin/files/upload",
                         files={"file": ("scan_paper2.pdf", fh.read())},
                         data=data, headers=admin_headers)
    assert up.status_code == 200, up.text
    mid = up.json()["material_id"]

    monkeypatch.setattr("app.services.material_parser.parse_pdf_once",
                        lambda path, **kw: {"scanned": True, "pages": 41})
    import app.api.v1.library.materials as m
    calls = []
    monkeypatch.setattr(m, "_paper_parse_job", lambda *a, **kw: calls.append(a))

    first = client.post(f"/api/materials/admin/{mid}/parse", headers=admin_headers).json()
    second = client.post(f"/api/materials/admin/{mid}/parse", headers=admin_headers).json()
    assert first["status"] == "parsing" and second["status"] == "parsing"
    assert second["draft_id"] == first["draft_id"]
    assert second.get("reused") is True
    assert len(calls) == 1, calls
    assert db_session.query(PaperParseDraft).filter(
        PaperParseDraft.material_id == mid,
        PaperParseDraft.status == "parsing").count() == 1


def test_stale_parsing_draft_becomes_failed(client, admin_headers, db_session):
    material = StudyMaterial(subject="gongzhuan", type="paper", status=1,
                             title="P3 超时探针", creator_id=2)
    db_session.add(material)
    db_session.commit()
    draft = PaperParseDraft(material_id=material.material_id, status="parsing",
                            source_ext="pdf", item_count=0, created_by=2,
                            message="OCR 12/41 页",
                            create_time=datetime.now() - timedelta(minutes=41),
                            expires_at=datetime.now() + timedelta(days=30))
    db_session.add(draft)
    db_session.commit()

    r = client.get(f"/api/materials/admin/parse-drafts/{draft.draft_id}",
                   headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "failed"
    assert "超时中断" in (body.get("message") or "")
