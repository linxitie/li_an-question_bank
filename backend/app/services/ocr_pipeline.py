"""题目内嵌图片 OCR 管线（P3）。

设计目标：
1. **只做投影与建议**：扫描题干/选项/答案解析/题组材料中的 <img>，逐张识别，
   生成可审阅的候选；apply 只在教师明确选择后把图片原位替换为文字。
2. **位置不变**：替换的是原 <img> 标签本身，前后文字与顺序完全不动，
   因此不会出现“答案文字跑到解析里”这类错位。
3. **可回退**：输出带 data-ocr-src，保留原图路径；media_assets 与静态文件不被删除。
4. **进程隔离**：PaddleOCR 走 app.services.ocr_worker 子进程，主进程不 import paddle；
   本机 Python 3.13 下也不会被原生崩溃带走。
5. **缓存**：按图片内容 SHA-256 缓存到 backend/data/ocr_cache，重复审阅零成本。
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.foundation.config import BACKEND_DIR
from app.services.question_media import (
    MediaRef,
    parse_jsonish,
    resolve_media_ref,
)

logger = logging.getLogger(__name__)

CACHE_DIR = BACKEND_DIR / "data" / "ocr_cache"
_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
_SRC_RE = re.compile(
    r"\bsrc\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))",
    re.IGNORECASE | re.DOTALL,
)

# 位置 -> (模型字段, 展示名)
QUESTION_FIELDS = {
    "stem": ("question_content", "题干"),
    "analysis": ("answer_analysis", "答案解析"),
}
GROUP_FIELDS = {"group_content": ("shared_content", "题组材料")}


@dataclass
class OcrCandidate:
    key: str
    location: str
    location_label: str
    index: int
    tag: str
    src: str
    canonical: str
    status: str
    reason: str | None = None
    width: int = 0
    height: int = 0
    suggest_keep_image: bool = False
    text: str = ""
    confidence: float = 0.0
    cached: bool = False
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "location": self.location,
            "location_label": self.location_label,
            "index": self.index,
            "src": self.src,
            "canonical": self.canonical,
            "status": self.status,
            "reason": self.reason,
            "width": self.width,
            "height": self.height,
            "suggest_keep_image": self.suggest_keep_image,
            "text": self.text,
            "confidence": round(self.confidence, 4),
            "cached": self.cached,
            "error": self.error,
        }


@dataclass
class ApplyReport:
    replaced: int = 0
    skipped: int = 0
    fields: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"replaced": self.replaced, "skipped": self.skipped, "fields": self.fields}


def _src_of(tag: str) -> str:
    match = _SRC_RE.search(tag)
    if not match:
        return ""
    return (match.group(1) or match.group(2) or match.group(3) or "").strip()


def _iter_images(text: Any) -> list[tuple[int, str, str]]:
    value = "" if text is None else str(text)
    out: list[tuple[int, str, str]] = []
    for idx, match in enumerate(_IMG_TAG_RE.finditer(value)):
        tag = match.group(0)
        src = _src_of(tag)
        if src:
            out.append((idx, tag, src))
    return out


def _field_texts(question: Any) -> list[tuple[str, str, Any]]:
    """返回 [(location, 展示名, 文本)]；选项按数组逐项展开。"""
    out: list[tuple[str, str, Any]] = []
    out.append(("stem", "题干", getattr(question, "question_content", "")))
    options = parse_jsonish(getattr(question, "options", None))
    if isinstance(options, list):
        for idx, opt in enumerate(options):
            if isinstance(opt, dict):
                value = opt.get("value") or opt.get("content") or ""
                key = str(opt.get("key") or idx)
            else:
                value, key = opt, str(idx)
            if value:
                out.append((f"option:{idx}", f"选项 {key}", value))
    out.append(("analysis", "答案解析", getattr(question, "answer_analysis", "")))
    return out


def _cache_path(digest: str) -> Path:
    return CACHE_DIR / f"{digest}.json"


def _read_cache(digest: str) -> dict[str, Any] | None:
    path = _cache_path(digest)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _write_cache(digest: str, data: dict[str, Any]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(digest).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:  # 缓存失败不影响识别结果
        logger.warning("OCR 缓存写入失败: %s", exc)


def _ocr_python() -> str:
    configured = (settings.OCR_PYTHON or "").strip()
    if configured and os.path.exists(configured):
        return configured
    return sys.executable


def _run_ocr_bytes(data: bytes) -> str:
    """单图 OCR；用 ocr_worker 子进程，失败抛 RuntimeError 由上层转成 error 字段。"""
    with tempfile.TemporaryDirectory(prefix="ocr_inline_") as tmpdir:
        image_path = os.path.join(tmpdir, "image.png")
        with open(image_path, "wb") as fp:
            fp.write(data)
        out_json = os.path.join(tmpdir, "result.json")
        cmd = [_ocr_python(), "-m", "app.services.ocr_worker", tmpdir, out_json]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=min(int(settings.OCR_SUBPROCESS_TIMEOUT or 600), 180),
                cwd=str(BACKEND_DIR),
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("OCR 超时") from exc
        if proc.returncode != 0:
            raise RuntimeError(f"OCR 子进程退出 {proc.returncode}: {(proc.stderr or '')[-200:]}")
        try:
            result = json.loads(Path(out_json).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RuntimeError("OCR 未返回结果") from exc
        if not result.get("ok"):
            raise RuntimeError(str(result.get("error") or "未识别到文字"))
        return str(result.get("text") or "").strip()


def _image_size(ref: MediaRef) -> tuple[int, int]:
    data = ref.inline
    if data is None and ref.path is not None:
        try:
            data = ref.path.read_bytes()
        except OSError:
            return 0, 0
    if not data:
        return 0, 0
    try:
        from PIL import Image
        import io
        with Image.open(io.BytesIO(data)) as img:
            return int(img.width), int(img.height)
    except Exception:
        return 0, 0


def _ocr_ref(ref: MediaRef) -> tuple[str, bool, str]:
    """返回 (text, cached, error)。"""
    data = ref.inline
    if data is None and ref.path is not None:
        try:
            data = ref.path.read_bytes()
        except OSError as exc:
            return "", False, f"读取图片失败: {exc}"
    if not data:
        return "", False, "图片内容为空"
    digest = hashlib.sha256(data).hexdigest()
    cached = _read_cache(digest)
    if cached and isinstance(cached.get("text"), str):
        return cached["text"], True, ""
    try:
        text = _run_ocr_bytes(data)
    except RuntimeError as exc:
        return "", False, str(exc)
    _write_cache(digest, {"text": text, "engine": "paddleocr-worker", "version": 1})
    return text, False, ""


def _make_candidate(
    *,
    location: str,
    label: str,
    index: int,
    tag: str,
    src: str,
    owner_type: str,
    owner_id: int,
    run_ocr: bool,
) -> OcrCandidate:
    ref = resolve_media_ref(src, loc=location.split(":")[0], owner_type=owner_type,
                            owner_id=owner_id)
    width, height = _image_size(ref)
    # 大尺寸/竖长图通常是图表、几何图、资料图，OCR 成文字会丢信息，默认建议保留原图。
    suggest_keep = bool(width and height and (height >= 260 or width * height >= 180000))
    cand = OcrCandidate(
        key=f"{location}:{index}", location=location, location_label=label,
        index=index, tag=tag, src=src, canonical=ref.canonical, status=ref.status,
        reason=ref.reason, width=width, height=height, suggest_keep_image=suggest_keep,
    )
    if not ref.is_resolved:
        cand.error = ref.reason or "图片未解析"
        return cand
    if run_ocr:
        text, cached, error = _ocr_ref(ref)
        cand.text, cand.cached, cand.error = text, cached, error
        cand.confidence = 0.0 if error else min(1.0, len(text) / 80.0)
    return cand


def question_candidates(
    db: Session, question: Any, *, run_ocr: bool = True,
) -> list[OcrCandidate]:
    qid = int(question.question_id)
    out: list[OcrCandidate] = []
    for location, label, text in _field_texts(question):
        for index, tag, src in _iter_images(text):
            out.append(_make_candidate(
                location=location, label=label, index=index, tag=tag, src=src,
                owner_type="question", owner_id=qid, run_ocr=run_ocr,
            ))
    return out


def group_candidates(
    db: Session, group: Any, *, run_ocr: bool = True,
) -> list[OcrCandidate]:
    gid = int(group.id)
    out: list[OcrCandidate] = []
    for location, (attr, label) in GROUP_FIELDS.items():
        for index, tag, src in _iter_images(getattr(group, attr, "")):
            out.append(_make_candidate(
                location=location, label=label, index=index, tag=tag, src=src,
                owner_type="group", owner_id=gid, run_ocr=run_ocr,
            ))
    return out


def _replacement_html(text: str, src: str) -> str:
    body = html.escape(text.strip()).replace("\n", "<br>")
    return (f'<span class="q-ocr-inline" data-ocr="1" '
            f'data-ocr-src="{html.escape(src, quote=True)}">{body}</span>')


def _apply_to_text(text: str, decisions: list[dict[str, Any]]) -> tuple[str, int, int]:
    images = _iter_images(text)
    if not images:
        return text, 0, len(decisions)
    by_index = {int(item["index"]): item for item in decisions
                if str(item.get("index", "")).lstrip("-").isdigit()}
    replaced = 0
    skipped = 0
    out = text
    # 从后往前替换，前面的位置不受影响
    for index, tag, src in reversed(images):
        item = by_index.get(index)
        if not item or not item.get("replace"):
            skipped += 1
            continue
        value = str(item.get("text") or "").strip()
        if not value:
            skipped += 1
            continue
        out = out.replace(tag, _replacement_html(value, src), 1)
        replaced += 1
    return out, replaced, skipped


def apply_question_decisions(
    db: Session, question: Any, decisions: list[dict[str, Any]],
) -> ApplyReport:
    from app.services.rich_text import sanitize_rich_text

    report = ApplyReport()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in decisions or []:
        location = str(item.get("location") or "")
        if location:
            grouped.setdefault(location, []).append(item)

    for location, items in grouped.items():
        if location.startswith("option:"):
            idx = int(location.split(":", 1)[1])
            options = parse_jsonish(getattr(question, "options", None))
            if not isinstance(options, list) or idx >= len(options):
                report.skipped += len(items)
                continue
            opt = options[idx]
            if not isinstance(opt, dict):
                opt = {"key": chr(65 + idx), "value": opt}
                options[idx] = opt
            new_text, replaced, skipped = _apply_to_text(str(opt.get("value") or ""), items)
            if replaced:
                opt["value"] = new_text
                question.options = json.dumps(options, ensure_ascii=False)
                report.replaced += replaced
                report.fields.append(location)
            report.skipped += skipped
            continue

        field_info = QUESTION_FIELDS.get(location)
        if not field_info:
            report.skipped += len(items)
            continue
        attr = field_info[0]
        new_text, replaced, skipped = _apply_to_text(getattr(question, attr, "") or "", items)
        if replaced:
            setattr(question, attr, sanitize_rich_text(new_text))
            report.replaced += replaced
            report.fields.append(location)
        report.skipped += skipped

    if report.replaced:
        db.add(question)
        db.commit()
    return report


def apply_group_decisions(
    db: Session, group: Any, decisions: list[dict[str, Any]],
) -> ApplyReport:
    from app.services.rich_text import sanitize_rich_text

    report = ApplyReport()
    for location, items in _group_by_location(decisions).items():
        attr = GROUP_FIELDS.get(location, (None, ""))[0]
        if not attr:
            report.skipped += len(items)
            continue
        new_text, replaced, skipped = _apply_to_text(getattr(group, attr, "") or "", items)
        if replaced:
            setattr(group, attr, sanitize_rich_text(new_text))
            report.replaced += replaced
            report.fields.append(location)
        report.skipped += skipped
    if report.replaced:
        db.add(group)
        db.commit()
    return report


def _group_by_location(decisions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in decisions or []:
        location = str(item.get("location") or "")
        if location:
            grouped.setdefault(location, []).append(item)
    return grouped
