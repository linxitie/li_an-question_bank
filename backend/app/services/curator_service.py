"""R1 Curator 复核适配器（LLM 可选，默认只读预览）。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import requests
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.models import EssayQuote
from . import quote_review_service
from .obsidian_sync import parse_note

_FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.S)
_JSON_RE = re.compile(r"\{.*\}", re.S)

_SYSTEM_PROMPT = (
    "你是公安联考申论金句审核员。只判断金句是否适合进入题库，不修改原文。"
    "输出严格 JSON，不要 Markdown 代码块。"
)


@dataclass
class CuratorResult:
    uid: str
    decision: str
    confidence: float
    reasons: list[str] = field(default_factory=list)
    model: str = "police-exam"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "decision": self.decision,
            "confidence": self.confidence,
            "reasons": self.reasons,
            "model": self.model,
            "error": self.error,
        }


def _prompt(quote: EssayQuote) -> str:
    return (
        "请审核下面这条申论金句，判断是否适合入库。\n"
        f"金句：{quote.content}\n"
        f"来源：{quote.source or '无'}\n"
        f"作者：{quote.author or '无'}\n"
        f"分类：{quote.category or '无'}\n"
        f"Scout 规则分：{quote.quality_score}\n\n"
        "返回 JSON："
        '{"decision":"approve|reject|needs_human","confidence":0.0,'
        '"reasons":["简短理由"]}'
    )


def _extract_json(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z]*\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    match = _JSON_RE.search(value)
    if not match:
        raise ValueError("LLM response is not JSON")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("LLM response JSON must be an object")
    return data


def _http_review(prompt: str) -> str:
    url = (settings.LLM_API_URL or "").strip()
    if not url:
        raise RuntimeError("LLM_API_URL 未配置")
    headers = {"Content-Type": "application/json"}
    if settings.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"
    response = requests.post(
        url,
        headers=headers,
        json={
            "model": settings.LLM_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    content = data.get("content")
    if not content and data.get("choices"):
        content = data["choices"][0].get("message", {}).get("content")
    if not content:
        raise ValueError("LLM response missing content")
    return str(content)


def review_quote_with_llm(
    quote: EssayQuote,
    client: Callable[[str], str] | None = None,
) -> CuratorResult:
    raw = (client or _http_review)(_prompt(quote))
    data = _extract_json(raw)
    decision = str(data.get("decision", "")).strip()
    if decision not in ("approve", "reject", "needs_human"):
        raise ValueError(f"invalid decision: {decision}")
    confidence = float(data.get("confidence", 0.0))
    confidence = max(0.0, min(1.0, confidence))
    reasons = data.get("reasons") or []
    if isinstance(reasons, str):
        reasons = [reasons]
    return CuratorResult(
        uid=quote.quote_uid or f"q_{quote.quote_id:06d}",
        decision=decision,
        confidence=confidence,
        reasons=[str(item) for item in reasons][:5],
        model=settings.LLM_MODEL,
    )


def _update_note(text: str, result: CuratorResult) -> str:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("note has no frontmatter")
    lines = match.group(1).splitlines()
    updates = {
        "curator_decision": result.decision,
        "curator_confidence": str(result.confidence),
        "curator_reasons": json.dumps(result.reasons, ensure_ascii=False),
        "curator_model": result.model,
        "curator_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    for key, value in updates.items():
        prefix = f"{key}:"
        for index, line in enumerate(lines):
            if line.startswith(prefix):
                lines[index] = f"{key}: {value}"
                break
        else:
            lines.append(f"{key}: {value}")
    body = match.group(2).lstrip("\n")
    return "---\n" + "\n".join(lines) + "\n---\n\n" + body


def review_notes(
    db: Session,
    vault: Path,
    *,
    bucket: str = "02-重点复核",
    limit: int | None = 5,
    apply: bool = False,
    client: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    vault = Path(vault).expanduser()
    notes_dir = vault / "00-收件箱" / "审核看板" / bucket
    report: dict[str, Any] = {
        "ok": True,
        "bucket": bucket,
        "apply": apply,
        "llm": {
            "url": settings.LLM_API_URL,
            "key_present": bool(settings.LLM_API_KEY),
        },
        "processed": 0,
        "errors": [],
        "items": [],
    }
    if not notes_dir.is_dir():
        return {"ok": False, "error": "notes_dir_not_found", "path": str(notes_dir)}
    if not settings.LLM_API_URL and client is None:
        report["ok"] = False
        report["error"] = "llm_not_configured"
        return report

    paths = sorted(notes_dir.glob("*.md"))
    if limit is not None:
        paths = paths[: max(0, limit)]

    for path in paths:
        fields, _body = parse_note(path.read_text(encoding="utf-8"))
        uid = fields.get("uid") or path.stem
        quote = quote_review_service.get_quote(db, uid)
        if not quote:
            report["errors"].append(f"{uid}: quote not found")
            continue
        try:
            result = review_quote_with_llm(quote, client=client)
        except Exception as exc:
            report["errors"].append(f"{uid}: {exc}")
            continue
        report["items"].append(result.to_dict())
        report["processed"] += 1
        if apply:
            path.write_text(_update_note(path.read_text(encoding="utf-8"), result), encoding="utf-8")

    return report
