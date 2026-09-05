"""备考资料多格式解析服务（同步轻量部分，spec 第五章）。

- parse_docx       : Word -> 章节树 + 消毒前HTML + 内嵌图片提取
- parse_xlsx       : Excel -> 表头 + 行数据（卡片列映射语义后置到 confirm）
- build_cards      : 行数据 + 列映射 -> 卡片列表（空行跳过/去重/500上限）
- parse_pdf_text   : 文字型 PDF -> 文章结构（字号聚类推断标题层级）
- detect_scanned   : 平均每页可提取字符 < 100 判定扫描件（路由至 MinerU）

纯函数式：输入文件路径，输出结构化 dict，便于单测（tests/test_material_parser.py）。
"""
import os
import re


def detect_scanned(pdf_path: str, threshold: int = 100) -> bool:
    """平均每页可提取字符 < threshold 判定为扫描件。"""
    import pdfplumber
    chars = pages = 0
    with pdfplumber.open(pdf_path) as doc:
        for page in doc.pages:
            chars += len((page.extract_text() or "").strip())
            pages += 1
    return pages > 0 and (chars // max(pages, 1)) < threshold


def _esc(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_docx(docx_path: str, image_dir=None) -> dict:
    """Word -> {chapters:[{level,title}], html, word_count, images:[tmp_paths]}

    标题样式映射：Heading1/标题1 -> h2(章节), Heading2/标题2 -> h3, Heading3/标题3 -> h4。
    内嵌图片写入 image_dir 并以 /uploads/materials/tmp/ 引用（confirm 阶段统一迁移改写）。
    """
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(docx_path)
    chapters, html_parts, images = [], [], []

    def _render_table(tbl) -> str:
        rows_html = []
        for r in tbl.rows:
            cells = "".join(f"<td>{_esc(c.text.strip())}</td>" for c in r.cells)
            rows_html.append(f"<tr>{cells}</tr>")
        return "<table><tbody>" + "".join(rows_html) + "</tbody></table>"

    def _extract_image(run) -> str:
        try:
            rid = run._element.xpath(".//a:blip/@r:embed")[0]
            part = doc.part.related_parts[rid]
            ext = os.path.splitext(str(part.partname))[1] or ".png"
            if image_dir is None:
                return ""
            image_dir.mkdir(parents=True, exist_ok=True)
            name = f"{os.urandom(8).hex()}{ext}"
            (image_dir / name).write_bytes(part.blob)
            images.append(name)
            return f"/uploads/materials/tmp/{name}"
        except Exception:
            return ""

    body = doc.element.body
    for child in body.iterchildren():
        if child.tag.endswith("}p"):
            para = Paragraph(child, doc)
            text = para.text.strip()
            style_name = getattr(para.style, "name", "") or ""
            style = style_name.lower()
            if not text and not any(r._element.findall(
                    ".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip")
                    for r in para.runs):
                continue
            is_h1 = "heading 1" in style or "标题 1" in style
            is_h2 = "heading 2" in style or "标题 2" in style
            is_h3 = "heading 3" in style or "标题 3" in style
            if is_h1:
                chapters.append({"level": 1, "title": text})
                html_parts.append(f"<h2>{_esc(text)}</h2>")
            elif is_h2:
                chapters.append({"level": 2, "title": text})
                html_parts.append(f"<h3>{_esc(text)}</h3>")
            elif is_h3:
                chapters.append({"level": 3, "title": text})
                html_parts.append(f"<h4>{_esc(text)}</h4>")
            else:
                inner = ""
                for run in para.runs:
                    esc = _esc(run.text or "")
                    img = _extract_image(run)
                    if img:
                        inner += f'<img src="{img}" alt=""/>'
                    elif esc.strip():
                        inner += f"<strong>{esc}</strong>" if run.bold else esc
                if inner.strip():
                    html_parts.append(f"<p>{inner}</p>")
        elif child.tag.endswith("}tbl"):
            html_parts.append(_render_table(Table(child, doc)))

    full_html = "".join(html_parts)
    word_count = len(re.sub(r"<[^>]+>", "", full_html))
    return {"chapters": chapters, "html": full_html,
            "word_count": word_count, "images": images}


def parse_xlsx(xlsx_path: str, max_rows: int = 500) -> dict:
    """Excel -> {headers, rows(预览截断200行), total_rows, over_limit}"""
    from openpyxl import load_workbook
    wb = load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active
    if ws is None:
        return {"headers": [], "rows": [], "total_rows": 0, "over_limit": False}
    headers, all_rows = [], []
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        vals = [("" if v is None else str(v).strip()) for v in row]
        if i == 0:
            headers = vals
            continue
        if any(vals):
            all_rows.append(vals)
    wb.close()
    total = len(all_rows)
    return {"headers": headers, "rows": all_rows[:200], "total_rows": total,
            "over_limit": total > max_rows}


def build_cards(rows: list, col_front: int, col_back: int,
                col_category=None, limit: int = 500) -> list:
    """按列映射生成卡片。空行跳过、正反面去重；超 limit 抛 ValueError。"""
    cards, seen = [], set()
    for r in rows:
        front = r[col_front].strip() if col_front < len(r) else ""
        back = r[col_back].strip() if col_back < len(r) else ""
        if not front or not back:
            continue
        key = (front, back)
        if key in seen:
            continue
        seen.add(key)
        cat = ""
        if col_category is not None and col_category < len(r):
            cat = r[col_category].strip()
        cards.append({"card_front": front[:200], "card_back": back, "category": cat})
    if len(cards) > limit:
        raise ValueError(f"有效卡片 {len(cards)} 张超过上限 {limit}，请拆分文件")
    return cards


def parse_pdf_text(pdf_path: str) -> dict:
    """文字型 PDF -> {chapters, html, word_count}。

    以全文中位字号为正文基准，字号 >= 1.3 倍的行判定为章节标题(h2)。
    """
    import pdfplumber
    html_parts, chapters, sizes = [], [], []
    pages_data = []
    with pdfplumber.open(pdf_path) as doc:
        for page in doc.pages:
            words = page.extract_words(extra_attrs=["size"]) or []
            pages_data.append(words)
            sizes.extend(round(w.get("size", 0), 1) for w in words)
    body_size = sorted(sizes)[len(sizes) // 2] if sizes else 0
    h2_threshold = body_size * 1.3 if body_size else 0

    def flush_line(words):
        if not words:
            return
        text = "".join(w["text"] for w in words).strip()
        if not text:
            return
        size = max(w.get("size", 0) for w in words)
        if h2_threshold and size >= h2_threshold and len(text) <= 50:
            chapters.append({"level": 1, "title": text})
            html_parts.append(f"<h2>{_esc(text)}</h2>")
        else:
            html_parts.append(f"<p>{_esc(text)}</p>")

    for words in pages_data:
        line, last_top = [], None
        for w in sorted(words, key=lambda x: (round(x["top"], 1), x["x0"])):
            if last_top is None or abs(w["top"] - last_top) <= 3:
                line.append(w)
            else:
                flush_line(line)
                line = [w]
            last_top = w["top"]
        flush_line(line)

    full = "".join(html_parts)
    return {"chapters": chapters, "html": full,
            "word_count": len(re.sub(r"<[^>]+>", "", full))}


# ==================== 扩展格式支持（Task 11）====================


def parse_video_metadata(file_path: str) -> dict:
    """使用 ffprobe 解析视频元数据（时长、大小、格式）。"""
    import json as _json
    import subprocess

    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            file_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = _json.loads(result.stdout)
            fmt = data.get("format", {})
            return {
                "duration": int(float(fmt.get("duration", 0))),
                "size": int(fmt.get("size", 0)),
                "format": fmt.get("format_name", ""),
            }
    except Exception:
        pass
    return {"duration": 0, "size": 0, "format": ""}


def detect_video_type(file_path: str) -> str:
    """根据视频时长判断类型：≤15min 为 video_intro，>15min 为 video_advanced。"""
    meta = parse_video_metadata(file_path)
    return "video_intro" if meta["duration"] <= 15 * 60 else "video_advanced"


def parse_image_ocr(file_path: str) -> str:
    """图片 OCR（可选，依赖 pytesseract + PIL）。"""
    try:
        from PIL import Image
        import pytesseract

        img = Image.open(file_path)
        text = pytesseract.image_to_string(img, lang="chi_sim+eng")
        return text.strip()
    except Exception:
        return ""
