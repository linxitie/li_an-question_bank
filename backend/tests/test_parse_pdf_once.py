# -*- coding: utf-8 -*-
"""S-A（2026-11-13）：PDF 单遍解析 `parse_pdf_once`。

锁四件事：
  1. 文字版 PDF：`html` 与旧 `parse_pdf_text` **逐字节等价**（同一套规则，避免"快了但变了"）；
  2. 无文字层 → `scanned=True`，且只回页数（不再解析第二遍）；
  3. 采样前 3 页：页数多也只读 3 页做判定；
  4. 坏文件抛异常（调用方转 400）。
"""
from __future__ import annotations

import pytest

from app.services.material_parser import parse_pdf_once, parse_pdf_text


def _text_pdf(path, pages=3, line="这是一段用于测试的中文正文，长度超过阈值。", per_page=40):
    import pymupdf
    doc = pymupdf.open()
    for _ in range(pages):
        page = doc.new_page()
        y = 60
        for _i in range(per_page):
            page.insert_text((50, y), line, fontsize=10, fontname="china-s")
            y += 14
    doc.save(str(path))
    doc.close()
    return str(path)


def _blank_pdf(path, pages=2):
    import pymupdf
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page()
    doc.save(str(path))
    doc.close()
    return str(path)


def test_text_pdf_matches_legacy_output(tmp_path):
    p = _text_pdf(tmp_path / "text.pdf", pages=3)
    new = parse_pdf_once(p)
    old = parse_pdf_text(p)
    assert new["scanned"] is False
    assert new["html"] == old["html"]           # 逐字节等价
    assert new["word_count"] == old["word_count"]
    assert new["chapters"] == old["chapters"]


def test_blank_pdf_is_scanned_and_returns_only_meta(tmp_path):
    p = _blank_pdf(tmp_path / "scan.pdf", pages=4)
    out = parse_pdf_once(p)
    assert out["scanned"] is True
    assert out["pages"] == 4
    assert "html" not in out                  # 扫描件不再白解析一遍


def test_threshold_and_sampling(tmp_path):
    # 单页 50 字 → 平均 50 < 100 → 扫描件
    thin = _text_pdf(tmp_path / "thin.pdf", pages=1, per_page=2)
    assert parse_pdf_once(thin)["scanned"] is True
    # 单页 40 行 → 远超 100 → 文字版
    thick = _text_pdf(tmp_path / "thick.pdf", pages=1, per_page=40)
    out = parse_pdf_once(thick)
    assert out["scanned"] is False
    assert out["sampled_pages"] == 1


def test_sample_pages_capped_at_three(tmp_path):
    p = _text_pdf(tmp_path / "many.pdf", pages=6, per_page=20)
    out = parse_pdf_once(p)
    assert out["pages"] == 6
    assert out["sampled_pages"] == 3


def test_broken_pdf_raises(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf at all")
    with pytest.raises(Exception):
        parse_pdf_once(str(bad))
