# -*- coding: utf-8 -*-
"""OCR 文本 → 段落 HTML（P2，2026-11-12）。

**为什么需要这一层**：RapidOCR 的产出是"按文本框、按行"的碎片（一行 40±2 字，按栏宽硬切）。
直接 `"\\n".join` 入库会得到一堆碎行；文章/讲义要的是**能读的段落**，而且 confirm 落库的是
`content`（HTML），详情页按 HTML 渲染 —— 所以必须在入库前重排成 `<p>`。

三层规则（全部纯函数、可单测，边界见 `tests/test_ocr_html.py`）：
  1. **去噪**：页眉/页脚/公众号导流/页码（这份语料每页首行都是同一条导流）；
  2. **合并断行**：上一行没有句末标点 → 与下一行直接拼接（中文不加空格）；
  3. **断段**：遇到句末标点，或遇到"新块起始"（题号 `1、`、`一、`、`（一）`、`A、`、`第X章`、`【`）。

刻意的取舍：
  · 不做标点纠错（错字是 OCR 固有问题，纠错会引入新错）；
  · 不做版式还原（双栏/表格会按阅读顺序拆散），只保证"段落可读"；
  · 单段超过 `MAX_PARA_CHARS` 再按句切，避免一页变成一整段。
"""
from __future__ import annotations

import html
import re
from typing import Iterable, List, Tuple

#: 句末标点：以它结尾视为一个语义段落结束
SENT_END = "。！？；：!?;:…"

#: 噪声行（页眉/页脚/导流/页码）——命中即丢弃
NOISE_PATTERNS: Tuple[str, ...] = (
    r"^\s*获取试卷更新",          # 这份语料每页首行
    r"公众号",
    r"^\s*来源\s*[：:]",
    r"整理\s*[：:]",
    r"微信\s*[：:]",
    r"^\s*第\s*\d{1,3}\s*页\s*$",
    r"^\s*\d{1,3}\s*/\s*\d{1,3}\s*$",
    r"^\s*[-—=]{3,}\s*$",
)
NOISE_RE = re.compile("|".join(NOISE_PATTERNS))

#: 新段落的开头特征：题号 / 中文序号 / 括号序号 / 选项 / 章节条 / 方括号小标题
NEW_BLOCK_RE = re.compile(
    r"^(?:\d{1,3}\s*[、.．]"
    r"|[一二三四五六七八九十]{1,3}\s*[、.]"
    r"|[（(]\s*[一二三四五六七八九十\d]{1,3}\s*[）)]"
    r"|[A-D]\s*[、.．]"
    r"|第\s*[一二三四五六七八九十百\d]{1,4}\s*[章节条款]"
    r"|【)")

#: 单段最大字数（超过按句再切）
MAX_PARA_CHARS = 1000

#: 段落最短字数（小于它的碎片合并到上一段，避免"故正确答案为C。"这类孤立行与下文割裂时丢上下文）
MIN_PARA_CHARS = 1


def is_noise_line(line: str) -> bool:
    """这一行是不是页眉/页脚/页码噪声（P1，2026-11-15）。

    为什么要单独暴露：`paper_ingest` 需要**按行保留坐标**地过滤噪声（页过滤/题号自洽都要
    用 x/y），不能先把行拍平成文本再筛；共用同一套 `NOISE_RE` 才不会有第二份口径。
    """
    text = (line or "").strip()
    if not text:
        return True
    return bool(NOISE_RE.search(text))


def drop_noise(lines: Iterable[str]) -> List[str]:
    """去掉页眉/页脚/页码等噪声行，并做基础去空白。"""
    out: List[str] = []
    for raw in lines:
        line = (raw or "").strip()
        if not line:
            continue
        if NOISE_RE.search(line):
            continue
        out.append(line)
    return out


def _split_long(para: str, limit: int = MAX_PARA_CHARS) -> List[str]:
    """超长段落按句号切分（找不到句号就硬切，保证没有巨型段落）。"""
    if len(para) <= limit:
        return [para]
    parts: List[str] = []
    buf = ""
    for ch in para:
        buf += ch
        if ch in SENT_END and len(buf) >= limit // 2:
            parts.append(buf)
            buf = ""
    if buf:
        if parts and len(buf) < limit // 2:
            parts[-1] += buf
        else:
            parts.append(buf)
    # 兜底：仍然超长的再硬切
    out: List[str] = []
    for p in parts:
        while len(p) > limit:
            out.append(p[:limit])
            p = p[limit:]
        if p:
            out.append(p)
    return out


def reflow(lines: Iterable[str], *, drop: bool = True) -> List[str]:
    """行 → 段落列表。

    :param lines: OCR 的逐行文本（可跨页，顺序即阅读顺序）
    :param drop: 是否先去噪（默认 True；单测里可关掉验证合并规则本身）
    """
    seq = drop_noise(lines) if drop else [ln.strip() for ln in lines if (ln or "").strip()]
    paras: List[str] = []
    buf = ""
    for line in seq:
        if buf and NEW_BLOCK_RE.match(line):
            paras.append(buf)
            buf = line
            continue
        if not buf:
            buf = line
        elif buf.endswith(tuple(SENT_END)):
            paras.append(buf)
            buf = line
        else:
            buf += line                     # 断行合并：中文不加空格
        if buf.endswith(tuple(SENT_END)) and len(buf) >= MIN_PARA_CHARS:
            paras.append(buf)
            buf = ""
    if buf:
        paras.append(buf)

    out: List[str] = []
    for p in paras:
        out.extend(_split_long(p))
    return [p for p in out if p.strip()]


def to_html(paras: Iterable[str]) -> str:
    """段落 → `<p>…</p>` 拼接（文本一律 HTML 转义，防注入）。"""
    return "".join(f"<p>{html.escape(p.strip())}</p>" for p in paras if (p or "").strip())


def text_to_html(text: str, *, drop: bool = True) -> Tuple[str, dict]:
    """OCR 全文 → `(html, stats)`。

    `stats` 里的 `chars` 是**纯文本字数**（不含标签），用于 `word_count` 与"预计阅读时间"。
    """
    lines = (text or "").splitlines()
    paras = reflow(lines, drop=drop)
    chars = sum(len(p) for p in paras)
    stats = {
        "paragraphs": len(paras),
        "chars": chars,
        "avg_para": round(chars / len(paras), 1) if paras else 0,
    }
    return to_html(paras), stats
