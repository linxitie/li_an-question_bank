# -*- coding: utf-8 -*-
"""把 docx / pdf 读成「文本行 + 图片（带归属题号）」（P3，2026-11-09）。

设计要点：
  · **只读文件，不落库、不落盘**：图片以 `bytes` 返回，落盘由 `service.py` 决定
    （草稿目录 → 确认后才复制到 `static/questions/{qid}/`）；
  · **两路输出结构一致**，`splitter.split_questions(lines)` 对两种来源完全通用；
  · 图片归属 = "离它最近的那道题"，两种格式各按自己最可靠的方式算：
      - docx：按**段落顺序**（图在哪段之后，就归最近出现过的题号行）；
      - pdf ：按**版面坐标**（图与上下两道题的纵向距离取更近者，来自
        `_run/map_all_images_v2.py` 在 2024 国考那套卷上跑通的规则）。

为什么 docx 不用坐标：Word 里"图在段落中"是结构信息，比坐标稳；
而 PDF 只有坐标，没有段落概念，必须用纵向距离。
"""
from __future__ import annotations

import io
import os
import re
from typing import Dict, List, Optional

from .splitter import qno_of

#: 过滤"伪图"的门槛：短边 ≥60 **且** 面积 ≥8000 才算题图。
#: 口径依据（两轮实测）：
#:   · 2024 国考 PDF：28 张真题图（最小的一批约 100px 高）—— 门槛设到 120 会误删 6 张，
#:     那 6 题就变成"让你看图但没图"，比多留一张更糟；
#:   · 2016 江西 docx：末尾两张 592x201 / 535x201 的二维码/水印图会挂到最后一题上 ——
#:     尺寸上没法可靠区分，所以**不在这里硬猜**，改为在确认页打「有图待核对」，让人一眼删掉。
#: 结论：门槛只负责挡掉真正的行内符号（几像素的图标），可疑归属交给「待确认」这一步。
MIN_SIDE = 60
MIN_AREA = 8000
#: 单次解析最多抽这么多图（防止一份巨型扫描件把内存打满）
MAX_IMAGES = 400
#: 单张图上限 12MB（超过就当不是题图，跳过并留告警）
MAX_IMAGE_BYTES = 12 * 1024 * 1024


class ReaderError(ValueError):
    """读不了这个文件（加密/损坏/格式不支持）→ 调用方把草稿标 failed。"""


def _keep_image(width: int, height: int) -> bool:
    """这张图够不够"像题图"（尺寸未知时传 0 → 视为不确定，保留由人工在确认页判断）。"""
    if width <= 0 or height <= 0:
        return True
    return min(width, height) >= MIN_SIDE and width * height >= MIN_AREA


def _part_size(part) -> tuple:
    """从 python-docx 的图片 part 取像素尺寸；取不到返回 (0, 0)（= 保留）。

    实测（python-docx 1.x）：`part.image.size` 是 `None`，真正可用的是
    `part.image.px_width / px_height`（`size` 只在少数版本里有值）。
    """
    image = getattr(part, "image", None)
    if image is None:
        return 0, 0
    px = (int(getattr(image, "px_width", 0) or 0),
          int(getattr(image, "px_height", 0) or 0))
    if px[0] and px[1]:
        return px
    try:
        size = getattr(image, "size", None)
        if size and len(size) == 2:
            return int(size[0]), int(size[1])
    except Exception:                              # noqa: BLE001
        pass
    return 0, 0


# ---------------------------------------------------------------------- docx
def read_docx(path: str) -> dict:
    """docx → {lines, images, meta}。

    Word 的题本常见排法：题干一段、四个选项各一段（甚至一行四个）。
    `splitter` 两种都能吃，所以这里**不做**结构化，只按段落顺序吐行。
    表格里的文字也拼成行（很多题库把选项放两列表格里）。
    """
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        doc = Document(path)
    except Exception as exc:                       # noqa: BLE001
        raise ReaderError(f"这个 docx 打不开（可能已加密或损坏）：{exc}") from exc

    lines: List[str] = []
    images: List[dict] = []
    current_no: Optional[int] = None
    seq = 0

    def _collect_images(paragraph: Paragraph) -> None:
        nonlocal seq, current_no
        try:
            blips = paragraph._element.xpath(".//a:blip/@r:embed")
        except Exception:                          # noqa: BLE001
            return
        for rid in blips:
            if len(images) >= MAX_IMAGES:
                return
            try:
                part = doc.part.related_parts[rid]
            except KeyError:
                continue
            blob = getattr(part, "blob", b"") or b""
            if not blob or len(blob) > MAX_IMAGE_BYTES:
                continue
            ext = os.path.splitext(str(part.partname))[1].lower() or ".png"
            if ext not in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".emf", ".wmf"):
                continue
            width, height = _part_size(part)
            if not _keep_image(width, height):
                continue
            seq += 1
            images.append({
                "no": current_no,                  # 归属：本段之前最近的题号
                "file": f"docx_{seq}{ext}",
                "bytes": blob,
                "origin": "docx",
                "width": width or None,
                "height": height or None,
            })

    body = doc.element.body
    for child in body.iterchildren():
        tag = getattr(child, "tag", "")
        if tag.endswith("}p"):
            para = Paragraph(child, doc)
            text = (para.text or "").strip()
            if text:
                lines.append(text)
                no = qno_of(text)
                if no is not None:
                    current_no = no
            _collect_images(para)
        elif tag.endswith("}tbl"):
            try:
                table = Table(child, doc)
            except Exception:                      # noqa: BLE001
                continue
            for row in table.rows:
                cells = [(c.text or "").strip() for c in row.cells]
                joined = "  ".join(c for c in cells if c)
                if joined:
                    lines.append(joined)
                    no = qno_of(joined)
                    if no is not None:
                        current_no = no
    return {"lines": lines, "images": images, "meta": {"reader": "docx"}}


# ----------------------------------------------------------------------- pdf
def read_pdf(path: str) -> dict:
    """pdf → {lines, images, meta}。

    文本用 `get_text()`（与 `_run/smoke_2024_gk_parse_v3.py` 同口径），
    图片用 `get_images(full=True)` + `get_image_rects()` 取版面坐标，
    再按"同页上下两题谁更近"归属（跨页时回退到全卷最后一个更早的题）。
    """
    try:
        import pymupdf  # PyMuPDF
    except ImportError as exc:                     # pragma: no cover
        raise ReaderError("当前环境没有 PyMuPDF，无法解析 PDF") from exc

    try:
        doc = pymupdf.open(path)
    except Exception as exc:                       # noqa: BLE001
        raise ReaderError(f"这个 pdf 打不开（可能已加密或损坏）：{exc}") from exc

    lines: List[str] = []
    starts: List[tuple] = []                       # (page, y, no)
    images: List[dict] = []
    seq = 0
    try:
        for pno in range(doc.page_count):
            page = doc[pno]
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                first = "".join(span.get("text", "")
                                for line in block.get("lines", [])
                                for span in line.get("spans", []))
                no = qno_of(first.strip()) if first.strip() else None
                if no is not None:
                    starts.append((pno, float(block["bbox"][1]), no))
            lines.extend((page.get_text() or "").splitlines())
        starts.sort()

        for pno in range(doc.page_count):
            page = doc[pno]
            for img in page.get_images(full=True):
                if len(images) >= MAX_IMAGES:
                    break
                xref = img[0]
                try:
                    rects = page.get_image_rects(xref)
                except Exception:                  # noqa: BLE001
                    rects = []
                if not rects:
                    continue
                rect = rects[0]
                width, height = int(rect.width), int(rect.height)
                if not _keep_image(width, height):
                    continue
                try:
                    info = doc.extract_image(xref)
                except Exception:                  # noqa: BLE001
                    continue
                blob = info.get("image") or b""
                if not blob or len(blob) > MAX_IMAGE_BYTES:
                    continue
                ext = "." + (info.get("ext") or "png").lower()
                if ext == ".jpeg":
                    ext = ".jpg"
                no, why = _attribute(starts, pno, float(rect.y0))
                seq += 1
                images.append({
                    "no": no,
                    "file": f"pdf_{seq}{ext}",
                    "bytes": blob,
                    "origin": f"pdf:{why}",
                    "width": width,
                    "height": height,
                })
        page_count = doc.page_count
    finally:
        doc.close()
    return {"lines": lines, "images": images,
            "meta": {"reader": "pdf", "pages": page_count}}


def _attribute(starts: List[tuple], page: int, y: float) -> tuple:
    """图归哪道题：同页上一题/下一题谁更近；跨页回退到最后一个更早的题。"""
    prev = nxt = None
    for (pp, yy, no) in starts:
        if pp == page and yy <= y + 1:
            prev = (yy, no)
        elif pp == page and yy > y + 1 and nxt is None:
            nxt = (yy, no)
    if prev and nxt:
        return ((prev[1], "上一题更近") if (y - prev[0]) <= (nxt[0] - y)
                else (nxt[1], "下一题更近"))
    if prev:
        return prev[1], "仅上一题"
    if nxt:
        return nxt[1], "仅下一题"
    before = [(pp, yy, no) for (pp, yy, no) in starts if (pp, yy) <= (page, y)]
    return (before[-1][2], "跨页回退") if before else (None, "未归属")


# ------------------------------------------------------------------- 统一入口
def read_any(path: str, ext: str) -> dict:
    """按扩展名分派。不支持的格式抛 `ReaderError`（调用方标 failed，不炸上传）。"""
    ext = (ext or "").lower().lstrip(".")
    if ext == "docx":
        return read_docx(path)
    if ext == "pdf":
        return read_pdf(path)
    raise ReaderError(f"暂不支持自动导题的文件类型：.{ext}（目前支持 docx / pdf）")


def attach_images(items: List[dict], images: List[dict]) -> List[dict]:
    """把图片挂到对应题目上（返回未归属的图片数，供告警用）。

    归属为 None 的图（卷首图、页首图没落到题上）**丢弃并告警**，
    绝不"猜"给第一题 —— 猜错等于把别的题的图挂上去，学生看到的就是错题。
    """
    by_no: Dict[int, List[dict]] = {}
    orphans = 0
    for img in images:
        no = img.get("no")
        if not no:
            orphans += 1
            continue
        by_no.setdefault(int(no), []).append({
            "name": img["file"],
            "width": img.get("width"),
            "height": img.get("height"),
        })
    index = {it["no"]: it for it in items}
    for no, imgs in by_no.items():
        if no in index:
            index[no]["images"] = imgs
    return [orphans]
