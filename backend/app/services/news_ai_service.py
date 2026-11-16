"""R2.2 新闻 AI 摘要/考点/实体/合规校验。"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Any, Callable

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.models import NewsArticle
from . import llm_client

_SYSTEM = (
    "你是公安联考时政审核员。只输出 JSON，不输出 Markdown。"
    "必须忠实原文，不得编造领导人称谓、机构或政策表述。"
)
_JSON_RE = re.compile(r"\{.*\}", re.S)
_HIGH_RISK_TERMS = (
    "法轮功",
    "暴恐",
    "颠覆国家",
    "六四",
    "台独",
    "藏独",
    "疆独",
    "涉密",
    "绝密",
    "机密文件",
    "发动暴乱",
)


def _prompt(news: NewsArticle) -> str:
    return (
        "请处理下面这篇新闻，输出 JSON：\n"
        "摘要必须完整成句，控制在 150–220 字，不要截断半句话。\n"
        '{"summary":"150-220字完整摘要","exam_points":["申论考点1"],'
        '"official_phrases":["官方表述原文"],'
        '"entities":[{"type":"person|organization|policy|region","name":"..."}],'
        '"risk_flags":["..."],"confidence":0.0}\n'
        f"标题：{news.title}\n来源：{news.source}\n"
        f"正文：{(news.content or '')[:6000]}"
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
            temperature=0.2,
            prompt_name="news_summary",
        )

    return asyncio.run(run())


def _fallback(news: NewsArticle) -> dict[str, Any]:
    return {
        "summary": (news.content or news.title or "")[:100],
        "exam_points": [],
        "official_phrases": [],
        "entities": [],
        "risk_flags": [],
        "confidence": 0.0,
    }


def _normalize(data: dict[str, Any]) -> dict[str, Any]:
    summary = str(data.get("summary") or "").strip()[:400]
    if summary and not re.search(r"[。！？!?]$", summary):
        boundary = max(summary.rfind("。"), summary.rfind("！"), summary.rfind("？"))
        if boundary >= 100:
            summary = summary[: boundary + 1]
    exam_points = [str(item) for item in (data.get("exam_points") or [])][:8]
    official = [str(item) for item in (data.get("official_phrases") or [])][:8]
    entities = []
    for item in data.get("entities") or []:
        if isinstance(item, dict) and item.get("name"):
            entities.append(
                {
                    "type": str(item.get("type") or "unknown"),
                    "name": str(item.get("name")),
                }
            )
    risks = [str(item) for item in (data.get("risk_flags") or [])][:8]
    confidence = float(data.get("confidence") or 0.0)
    return {
        "summary": summary,
        "exam_points": exam_points,
        "official_phrases": official,
        "entities": entities,
        "risk_flags": risks,
        "confidence": max(0.0, min(1.0, confidence)),
    }


def _rule_risks(news: NewsArticle, data: dict[str, Any]) -> list[str]:
    """只把硬合规词视为高风险；模型给出的时效/来源提示保留为人工复核备注。"""
    text = f"{news.title}\n{news.content or ''}\n{data.get('summary', '')}"
    flags = []
    for term in _HIGH_RISK_TERMS:
        if term in text:
            flags.append(f"命中高风险词：{term}")
    return flags


def process_news(
    db: Session,
    *,
    limit: int = 20,
    client: Callable[[str], str] | None = None,
    include_fallback: bool = False,
) -> dict[str, Any]:
    query = db.query(NewsArticle).filter(
        or_(
            NewsArticle.review_status == "pending",
            NewsArticle.review_status == "high_risk",
        )
    )
    if include_fallback:
        query = query.filter(
            or_(
                NewsArticle.ai_summary.is_(None),
                NewsArticle.ai_status == "fallback",
            )
        )
    else:
        query = query.filter(NewsArticle.ai_summary.is_(None))
    news_list = query.order_by(NewsArticle.news_id).limit(max(1, min(limit, 100))).all()
    ok = 0
    fallback = 0
    high_risk = 0
    errors = []
    for news in news_list:
        try:
            raw = (client or _call_llm)(_prompt(news))
            data = _normalize(_extract_json(raw))
            ai_status = "ok"
        except Exception as exc:
            data = _normalize(_fallback(news))
            ai_status = "fallback"
            fallback += 1
            errors.append(f"news {news.news_id}: {exc}")

        risks = _rule_risks(news, data)
        model_risks = list(data.get("risk_flags") or [])
        data["risk_flags"] = list(dict.fromkeys(model_risks + risks))
        news.ai_summary = data["summary"]
        news.ai_exam_points = json.dumps(data["exam_points"], ensure_ascii=False)
        news.ai_entities = json.dumps(data["entities"], ensure_ascii=False)
        news.ai_risk_flags = json.dumps(data["risk_flags"], ensure_ascii=False)
        news.ai_confidence = data["confidence"]
        news.ai_run_at = datetime.now()
        high = bool(risks)
        news.ai_status = "high_risk" if high else ai_status
        news.review_status = "high_risk" if high else "pending"
        ok += 1
        high_risk += int(high)
    db.commit()
    return {
        "total": len(news_list),
        "processed": ok,
        "fallback": fallback,
        "high_risk": high_risk,
        "errors": errors[:10],
    }
