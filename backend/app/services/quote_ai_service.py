"""金句 AI 质量审核：低质量金句标记并隔离。"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.models import EssayQuote, QuoteReview
from . import llm_client

_SYSTEM = (
    "你是公安联考申论金句审核员。只输出 JSON，不输出 Markdown。"
    "审核目标：判断这条内容是否适合作为申论素材展示。"
    "必须检查：内容是否完整通顺、是否有明确出处或作者、是否疑似占位/广告/碎片、"
    "是否存在明显错误归属。不要因为古典名句没有个人作者就误判。"
)
_JSON_RE = re.compile(r"\{.*\}", re.S)
_PLACEHOLDER_RE = re.compile(
    r"(此处插入|金句内容|示例|测试内容|placeholder|test|example|未知来源|内容待补)",
    re.IGNORECASE,
)


def _prompt(quote: EssayQuote) -> str:
    return (
        "请审核下面这条申论金句，输出 JSON：\n"
        '{"quality":"approved|rejected","score":0,'
        '"reason":"不超过80字的原因"}\n'
        "approved 表示可作为申论素材；rejected 表示低质、残缺、出处不明或明显错误。"
        "古典名句只有书名/篇名出处、没有个人作者，可以通过。\n"
        f"内容：{quote.content}\n"
        f"来源：{quote.source or ''}\n"
        f"作者：{quote.author or ''}\n"
        f"分类：{quote.category or ''}"
    )


def _extract_json(text: str) -> dict[str, Any]:
    match = _JSON_RE.search(text)
    if not match:
        raise ValueError("AI response has no JSON")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("AI response must be object")
    return data


def _call_llm(prompt: str) -> str:
    async def run() -> str:
        return await llm_client._post(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            prompt_name="quote_quality",
        )

    return asyncio.run(run())


def _rule_reject_reason(quote: EssayQuote) -> str:
    content = (quote.content or "").strip()
    source = (quote.source or "").strip()
    author = (quote.author or "").strip()
    if _PLACEHOLDER_RE.search(content):
        return "疑似占位/模板内容"
    if len(content) < 5:
        return "内容少于 5 字"
    if not source and not author:
        return "缺少作者与出处"
    if not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", content):
        return "内容无有效文字"
    return ""


def _normalize(data: dict[str, Any]) -> tuple[str, int, str]:
    quality = str(data.get("quality") or "").strip().lower()
    if quality in {"approved", "pass", "ok", "good"}:
        quality = "approved"
    elif quality in {"rejected", "reject", "bad", "fail"}:
        quality = "rejected"
    else:
        quality = "pending"
    try:
        score = max(0, min(100, int(data.get("score") or 0)))
    except (TypeError, ValueError):
        score = 0
    reason = str(data.get("reason") or "").strip()[:500]
    return quality, score, reason


def review_quotes(
    db: Session,
    *,
    limit: int = 50,
    apply: bool = True,
    client: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """审核待处理金句；rejected 同时置 status=0，立即从展示接口隔离。"""
    batch = (
        db.query(EssayQuote)
        .filter(
            or_(
                EssayQuote.status == 1,
                EssayQuote.ai_quality == "pending",
            ),
            or_(
                EssayQuote.ai_quality.is_(None),
                EssayQuote.ai_quality == "pending",
            ),
        )
        .order_by(EssayQuote.quote_id)
        .limit(max(1, min(limit, 200)))
        .all()
    )
    approved = 0
    rejected = 0
    errors = 0
    for quote in batch:
        rule_reason = _rule_reject_reason(quote)
        if rule_reason:
            quality, score, reason = "rejected", 0, rule_reason
        else:
            try:
                data = _normalize(_extract_json((client or _call_llm)(_prompt(quote))))
                quality, score, reason = data
            except Exception as exc:
                quality, score, reason = "error", 0, f"AI审核失败: {exc}"
                errors += 1
        if apply:
            previous_status = quote.status
            previous_review = quote.review_status
            quote.ai_quality = quality
            quote.ai_quality_reason = reason
            quote.ai_reviewed_at = datetime.now()
            quote.quality_score = float(score)
            if quality == "approved":
                quote.status = 1
                quote.review_status = "published"
                approved += 1
            elif quality == "rejected":
                quote.status = 0
                quote.review_status = "rejected"
                rejected += 1
            db.add(
                QuoteReview(
                    quote_id=quote.quote_id,
                    reviewer_id=None,
                    action=f"ai_{quality}",
                    reason=reason,
                    diff_json=json.dumps(
                        {
                            "from": previous_review,
                            "to": quote.review_status,
                            "status_from": previous_status,
                            "status_to": quote.status,
                            "score": score,
                        },
                        ensure_ascii=False,
                    ),
                )
            )
        elif quality == "approved":
            approved += 1
        elif quality == "rejected":
            rejected += 1
    if apply:
        db.commit()
    return {
        "total": len(batch),
        "approved": approved,
        "rejected": rejected,
        "errors": errors,
        "applied": apply,
    }
