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

from . import ocr_retry
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
def read_pdf(path: str, progress=None) -> dict:
    """pdf → {lines, images, meta}。

    文本用 `get_text()`（与 `_run/smoke_2024_gk_parse_v3.py` 同口径），
    图片用 `get_images(full=True)` + `get_image_rects()` 取版面坐标，
    再按"同页上下两题谁更近"归属（跨页时回退到全卷最后一个更早的题）。
    """
    # P3（2026-11-13）：扫描件没有文字层 → 走 OCR（只出逐行文本，不带图/版式）。
    from ..material_parser import parse_pdf_once
    info = parse_pdf_once(path)
    if info.get("scanned"):
        return read_pdf_ocr(path, pages=int(info.get("pages") or 0), progress=progress)

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


#: 试卷特有的广告/导流噪声（与 ocr_html 的通用噪声互补）。
#: 注意「扫码」只在**带引导动作**时算噪声——否则会误杀「下列属于新型支付方式：A、扫码支付」。
PAPER_NOISE = re.compile(
    r"店主|加微信|公众号|扫码(?:关注|领取|进群|加群|获取|下载|免费)|其他机构"
    r"|本PDF|本 PDF|参考答案在最后|题库均未更新|获取更新")

#: 广告**粘在正文行末**时的锚点（2026-11-13 真机发现：OCR 会把页脚广告并到选项行尾，
#: 例如「B、用党的创新理论武装全党 常加微信 txw1663 赠送最新」）。只认「像广告」的片段：
#: 带微信号/QQ 号，或带赠送/领取/免费 + 资料类词——避免误伤「关于微信支付的说法」这类题干。
AD_CONTACT = re.compile(
    r"(?:店主|客服)?\s*(?:加|添加|关注)?\s*(?:微信号|微信|公众号|[Qq]{2}|[Qq]群)\s*(?:群)?\s*[:：]?\s*"
    r"[A-Za-z0-9][A-Za-z0-9_\-]{4,}")
AD_PROMO = re.compile(
    r"(?:免费|赠送|领取|获取|更新)\s*(?:最新|更多|全套|全套最新)?\s*"
    r"(?:资料|课程|题库|押题|真题集|视频)")
#: 「扫码 + 引导动作」才算广告（单独一个「扫码」可能只是题干在问扫码支付）
AD_SCAN = re.compile(
    r"(?:扫码|扫一扫|二维码)\s*(?:关注|领取|进群|加群|添加|获取|下载|免费|赠送|资料)")
#: 被切断后残留在行尾的广告引导字（「常」「请」「可」…），只在结尾出现时剥掉
AD_LEAD_TAIL = "常请可欢迎快立即赶紧扫码关注添加加"
#: 切完后行尾可能还剩「加」「Q」「qq」「微信群」这类半截引导词，逐层剥掉（最多 3 层）
AD_TAIL_STUB = re.compile(
    r"[\s，,、;；:：·\-—|/]*(?:加|添加|关注|请|可|常|立即|欢迎|快)?\s*"
    r"(?:微信|公众号|[Qq]{2}群|[Qq]{2}|[Qq]群|群|[Qq])\s*$")
#: 光秃秃的号（真机第二轮 OCR 把「加微信」吃掉了，只剩「xwl663赠送最」）：
#: 字母+数字的号后面跟的若是纯推广字，一律从号处切掉——这是判定「号」最稳的特征。
AD_BARE_ID = re.compile(r"[A-Za-z]{1,6}\d{3,}[A-Za-z0-9_\-]*")
PROMO_CHARS = set("赠送最新全套资料微信公共号QQ群免费领取课件视频课程题库押题加关注扫码店铺客服")


def strip_inline_noise(line: str) -> str:
    """把粘在正文行末的广告片段切掉，保留正文（切不出正文就整行丢弃）。"""
    text = line or ""
    cut = None
    for pat in (AD_CONTACT, AD_PROMO, AD_SCAN):
        m = pat.search(text)
        if m and (cut is None or m.start() < cut):
            cut = m.start()
    if cut is None:                             # 只剩「xwl663赠送最」这种裸号时
        m = AD_BARE_ID.search(text)
        if m and all((ch in PROMO_CHARS or ch.isspace() or not ch.isalnum())
                     for ch in text[m.end():]):
            cut = m.start()
    if cut is None:
        return text
    head = text[:cut].rstrip(" \t　，,、;；:：·-—|/")
    for _ in range(3):
        head = head.rstrip(AD_LEAD_TAIL + " \t　")
        trimmed = AD_TAIL_STUB.sub("", head).rstrip(" \t　，,、;；:：·-—|/")
        if trimmed == head:
            break
        head = trimmed
    # 切完只剩题号/选项字母（「B、」「3.」）说明原本就是纯广告行 → 丢掉
    if len(re.sub(r"^[\s\d一二三四五六七八九十]+[、.．)）]?\s*[ABCD]?\s*[、.．)）]?\s*$", "", head)) < 2:
        return ""
    return head


MAX_OCR_PAGES = 60

#: 水印/装饰框的判定（T2，2026-11-14）：真机实测正文行框高 30–34px，
#: 斜向水印框高 187 / 343px；孤立小水印（`X`）宽 34px、置信 0.866。
WATERMARK_HEIGHT_RATIO = 2.5
WATERMARK_MIN_HEIGHT = 10.0
ISOLATED_MAX_W = 40.0
ISOLATED_LOW_SCORE = 0.92
#: 短水印词（只在**整行 ≤ 8 字**时兜底删，避免误伤「微信支付」这类正文）
WATERMARK_WORDS = re.compile(
    r"^(?:五星好评?|公安院校联考真题|赠送最新?|真题|好评|扫码关注|"
    r"xwl?\d{0,6}|txw\d{0,6}|xw\d{0,6}|微信号?|公众号)$", re.IGNORECASE)


def base_height(rows: List[dict]) -> float:
    """正文行高中位数（只在 10–80px 取样；斜向水印框 187–343px 自然被排除）。"""
    heights = [r["h"] for r in rows if WATERMARK_MIN_HEIGHT <= r["h"] <= 80.0]
    return sorted(heights)[len(heights) // 2] if heights else 0.0


def is_watermark_row(row: dict, base_h: float) -> bool:
    """这一行是不是水印/装饰框（T2：几何优先、词表兜底）。

    抽成函数是因为缺行回收（`ocr_retry`）也要用同一套判定过滤补回来的行 ——
    两处各写一份的话，水印迟早从补行这条路漏回正文。
    """
    if base_h and row["h"] > base_h * WATERMARK_HEIGHT_RATIO:
        return True                                    # 斜向水印（高瘦框）
    if row["w"] < ISOLATED_MAX_W and row["h"] < base_h * 1.6 \
            and row["score"] < ISOLATED_LOW_SCORE:
        return True                                    # 孤立水印碎片（如 X）
    return len(row["text"]) <= 8 and bool(WATERMARK_WORDS.match(row["text"]))


def _layout_lines(layout: List[List[dict]]) -> List[dict]:
    """带坐标的 OCR 框 →（已丢水印、按阅读顺序）的行列表。T2（2026-11-14）。

    两步：
      1. **几何**：框高 > 2.5×正文行高中位数 → 斜向水印；孤立低置信小框 → 水印碎片；
      2. **词表兜底**：整行 ≤8 字且命中水印词（`五星好` / `xwl663` 等）。
    为什么先几何后词表：水印文案会换（"五星好评"→别的），但斜排必然"高瘦"，这一条最稳。
    """
    flat: List[dict] = []
    for page_no, page_lines in enumerate(layout, 1):
        for it in page_lines or []:
            text = (it.get("text") or "").strip()
            if not text:
                continue
            flat.append({
                "text": text,
                "x": float(it.get("x") or 0.0),
                "y": float(it.get("y") or 0.0),
                "w": float(it.get("w") or 0.0),
                "h": float(it.get("h") or 0.0),
                "score": float(it.get("score") or 1.0),
                "page": page_no,
            })
    if not flat:
        return flat

    base_h = base_height(flat)
    return [it for it in flat if not is_watermark_row(it, base_h)]


def read_pdf_ocr(path: str, *, pages: int = 0, progress=None) -> dict:
    """扫描版试卷 → `{lines, images: [], meta}`（P3 v1：只出文字，不带图/版式）。

    - OCR 复用 P1/S-C 的 `ocr_sidecar`（常驻 worker）；
    - T1/T2（2026-11-14）：带坐标取回 → 先按几何剔水印 → 再用缩进把丢标签的选项补回（`splitter`）；
    - 去噪：通用噪声（`ocr_html.drop_noise`）+ 试卷专属（`PAPER_NOISE`）；
    - 超过 `MAX_OCR_PAGES` 页会被 sidecar 截断，`meta.truncated=True` 交给警告提示。
    """
    from .. import ocr_html, ocr_sidecar

    cb = None
    if progress is not None:
        def cb(done: int, total: int) -> None:      # noqa: ANN001
            progress(f"OCR {done}/{total} 页")

    text, meta = ocr_sidecar.read_pdf_text(path, max_pages=MAX_OCR_PAGES,
                                           progress=cb, with_layout=True)
    layout = meta.get("layout") or []
    retry: dict = {}
    if layout:
        rows = _layout_lines(layout)
        # T5（2026-11-14）：被斜向水印压住的整行，OCR 会**连框都不出**（第 9 题 C）。
        # 这里按「缺选项字母 + 行距异常」定位那个洞，只把那一小条带重跑一次再插回行序；
        # 没有洞时是纯内存判断，零额外耗时（开关 PAPER_OCR_RETRY=0 可整体关掉）。
        rows, retry = ocr_retry.recover_into(
            path, rows, layout_dpi=int(meta.get("dpi") or 200), progress=progress)
        from . import splitter
        rows = splitter.repair_option_tags(rows)
        # 修复后再做文本级去噪；顺序很重要：水印必须在校验/分词之前就没了
        clean = [strip_inline_noise(r["text"]) for r in rows]
    else:                                          # 兜底：旧 worker / 拿不到坐标
        clean = (text or "").splitlines()
    clean = ocr_html.drop_noise([ln for ln in clean if ln])
    clean = [ln for ln in clean if ln and not PAPER_NOISE.search(ln)]
    info = {
        "reader": "pdf-ocr",
        "pages": int(meta.get("pages") or pages or 0),
        "parsed_pages": int(meta.get("pages_done") or 0),
        "scanned": True,
        "truncated": bool(meta.get("truncated")),
        "failed_pages": [e.get("page") for e in (meta.get("errors") or [])],
        "seconds": meta.get("seconds"),
    }
    if retry.get("holes") or retry.get("recovered"):   # 只有真的判过洞/补过行才回传
        info["ocr_retry"] = retry
    return {"lines": clean, "images": [], "meta": info}


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
def read_any(path: str, ext: str, progress=None) -> dict:
    """按扩展名分派。不支持的格式抛 `ReaderError`（调用方标 failed，不炸上传）。"""
    ext = (ext or "").lower().lstrip(".")
    if ext == "docx":
        return read_docx(path)
    if ext == "pdf":
        return read_pdf(path, progress=progress)
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
