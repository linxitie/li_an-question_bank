# -*- coding: utf-8 -*-
"""讲义大纲抽取（C1，2026-11-08）。

要解决的问题：资料列表里「讲义」只有标题和一个原件，管理员看不出**这份讲义多长、分几章**；
预览抽屉也没有目录，长讲义只能从头滚。

做法：解析 docx 的段落样式/编号，抽出一棵两级目录 + 字数，存到 `study_material.doc_meta`（JSON）。

三个取舍：
1. **只认"确定的"标题**：优先 Word 的 Heading 样式；没有样式时退而识别 `第X章/第X节/一、二、` 这类编号行。
   两者都没有 → 不编目录（`chapters=[]`），只给字数。
2. **字数按字符数**（中文语境下比"单词数"有用），只统计非空段落，含标题。
3. **只处理 docx**：PDF 没有样式信息，硬抽目录误报率高；`doc_meta=None` 时前端显示 `—`。
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

#: 编号型标题（无 Word 样式时的兜底）
# 注意：`\b` 是零宽断言，后面不能加 `?`（会抛 "nothing to repeat"）。
# 「第X节」必须在「第X章」之前判，且 RE_CHAPTER 不含「节」，否则节会被当成章（单测抓到过）。
RE_CHAPTER = re.compile(r"^\s*第\s*[0-9一二三四五六七八九十百]+\s*[章篇部]")
RE_SECTION = re.compile(r"^\s*第\s*[0-9一二三四五六七八九十百]+\s*节")
RE_CN_ITEM = re.compile(r"^\s*[一二三四五六七八九十]{1,3}\s*[、.．]")
RE_HEADING_STYLE = re.compile(r"^(heading|标题)\s*([1-9])?$", re.I)

#: 目录最多保留多少条（防超大讲义把 JSON 撑爆）
MAX_CHAPTERS = 200
#: 单条标题最大长度
MAX_TITLE_LEN = 80


def _clean_title(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:MAX_TITLE_LEN]


def extract_docx_outline(path: Path | str) -> Optional[dict]:
    """docx → `{word_count, chapter_count, chapters:[{level,title}]}`；打不开返回 None。"""
    try:
        from docx import Document
        doc = Document(str(path))
    except Exception as exc:                    # 损坏/非 docx：不给目录，但也不能让上传失败
        logger.warning("[doc-outline] 无法解析 %s: %s", path, exc)
        return None

    word_count = 0
    chapters: list[dict] = []
    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if not text:
            continue
        word_count += len(text)

        level = None
        style_name = (getattr(getattr(para, "style", None), "name", "") or "").strip()
        m = RE_HEADING_STYLE.match(style_name)
        if m:
            level = int(m.group(2) or 1)
        elif RE_SECTION.match(text):        # 先判「节」，避免被「章」正则吃掉
            level = 2
        elif RE_CHAPTER.match(text):
            level = 1
        elif RE_CN_ITEM.match(text):
            level = 2

        if level and len(chapters) < MAX_CHAPTERS:
            chapters.append({"level": min(level, 2), "title": _clean_title(text)})

    return {
        "word_count": word_count,
        "chapter_count": len(chapters),
        "chapters": chapters,
        "format": "docx",
    }


def dumps(meta: Optional[dict]) -> Optional[str]:
    return json.dumps(meta, ensure_ascii=False) if meta else None


def loads(raw: Optional[str]) -> Optional[dict]:
    """容错读取（历史脏数据不该把列表打挂）。"""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def apply_to_material(db: Session, material, abs_path: Path | str) -> Optional[dict]:
    """抽一次并写到 `material.doc_meta`（不 commit，由调用方统一提交）。"""
    path = Path(abs_path)
    if path.suffix.lower() != ".docx":
        return None
    meta = extract_docx_outline(path)
    if meta is None:
        return None
    material.doc_meta = dumps(meta)
    return meta


def human_word_count(n: Optional[int]) -> str:
    """`1.2 万字` / `8600 字` / `—`（后端给前端用的展示串，前端也可以自己格式化）。"""
    if not n:
        return "—"
    if n >= 10000:
        return f"{n / 10000:.1f} 万字"
    return f"{n} 字"
