"""从已授权外部来源采集金句候选。"""

from __future__ import annotations

import re
import time
import hashlib
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from ..models.models import ContentSource, EssayQuote, QuoteTag, Topic
from .quote_dedupe_service import normalized_hash
from .quote_external_sources import EXTERNAL_QUOTE_SOURCES, ExternalQuoteSource

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LiAnQuoteBot/1.0; +https://localhost)",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
_STOP = (
    "责任编辑",
    "来源：",
    "原标题",
    "编辑：",
    "作者：",
    "版权",
    "扫码",
    "关注",
    "分享",
)
_KEYWORDS = (
    "坚持",
    "必须",
    "人民",
    "群众",
    "法治",
    "治理",
    "基层",
    "发展",
    "安全",
    "作风",
    "纪律",
    "改革",
    "创新",
    "现代化",
    "团结",
    "奋斗",
    "服务",
    "党性",
    "监督",
)
_META_RE = re.compile(r"^(\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}月\d{1,2}日)")


def _request(url: str) -> requests.Response:
    response = requests.get(url, headers=_HEADERS, timeout=15)
    response.raise_for_status()
    if response.encoding in (None, "ISO-8859-1"):
        response.encoding = response.apparent_encoding or "utf-8"
    return response


def _candidate_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) < 16:
        return []
    sentences = re.split(r"(?<=[。！？!?])", text)
    result = []
    for sentence in sentences:
        sentence = sentence.strip(" \t\r\n“”\"'")
        if not 16 <= len(sentence) <= 120:
            continue
        if not re.search(r"[。！？!?]$", sentence):
            continue
        if any(stop in sentence for stop in _STOP):
            continue
        if _META_RE.search(sentence) or sentence.startswith(("——", "（", "(")):
            continue
        if not re.search(r"[\u4e00-\u9fff]", sentence):
            continue
        score = sum(1 for word in _KEYWORDS if word in sentence)
        if score >= 1:
            result.append(sentence)
        if len(result) >= 3:
            break
    return result


def _article_links(source: ExternalQuoteSource, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        url = urljoin(source.list_url, anchor["href"])
        parsed = urlparse(url)
        if parsed.netloc.lower() != source.allowed_host:
            continue
        clean = url.split("#")[0]
        if not re.search(source.link_regex, parsed.path):
            continue
        if clean in seen:
            continue
        seen.add(clean)
        links.append(clean)
        if len(links) >= source.max_articles:
            break
    return links


def _author(soup: BeautifulSoup, source: ExternalQuoteSource) -> str:
    for selector in ('meta[name="author"]', ".author", ".detail_author", ".article-author"):
        node = soup.select_one(selector)
        if node is None:
            continue
        value = (node.get("content") or node.get_text(" ", strip=True) or "").strip()
        if value and len(value) <= 40 and "编辑" not in value and not value.isdigit():
            return value
    return source.name


def _insert_source(db: Session, quote: EssayQuote, source: ExternalQuoteSource, url: str, author: str) -> None:
    record = (
        db.query(ContentSource)
        .filter(ContentSource.content_type == "quote", ContentSource.content_id == quote.quote_id)
        .first()
    )
    if record is None:
        record = ContentSource(
            content_type="quote",
            content_id=quote.quote_id,
            source_type="web",
            url=url,
            publisher=source.name,
            author=author,
            fetched_at=datetime.now(),
            trust_level=80,
        )
        db.add(record)
        db.flush()
    quote.source_id = record.source_id


def _insert_tag(db: Session, quote: EssayQuote, category: str) -> None:
    if not category:
        return
    topic = db.query(Topic).filter(Topic.name == category).first()
    if topic is None:
        topic = Topic(
            name=category,
            slug=f"quote-web-{hashlib.sha1(category.encode('utf-8')).hexdigest()[:8]}",
            kind="theme",
            description="外部金句分类",
            status=1,
        )
        db.add(topic)
        db.flush()
    exists = (
        db.query(QuoteTag)
        .filter(QuoteTag.quote_id == quote.quote_id, QuoteTag.tag_id == topic.topic_id)
        .first()
    )
    if exists is None:
        db.add(
            QuoteTag(
                quote_id=quote.quote_id,
                tag_id=topic.topic_id,
                confidence=0.8,
                source="external",
            )
        )


def collect_external_quotes(
    db: Session, *, dry_run: bool = False, max_articles: int | None = None
) -> list[dict[str, Any]]:
    reports = []
    for source in EXTERNAL_QUOTE_SOURCES:
        report = {
            "source": source.code,
            "name": source.name,
            "links": 0,
            "inserted": 0,
            "duplicates": 0,
            "samples": [],
            "errors": [],
        }
        try:
            list_response = _request(source.list_url)
            links = _article_links(source, list_response.text)
            if max_articles is not None:
                links = links[:max_articles]
            report["links"] = len(links)
            for link in links:
                try:
                    response = _request(link)
                    soup = BeautifulSoup(response.text, "html.parser")
                    title = soup.title.get_text(" ", strip=True) if soup.title else ""
                    author = _author(soup, source)
                    paragraphs = [
                        p.get_text(" ", strip=True)
                        for p in soup.find_all("p")
                        if len(p.get_text(" ", strip=True)) >= 16
                    ]
                    candidates = []
                    for paragraph in paragraphs:
                        candidates.extend(_candidate_sentences(paragraph))
                    for content in candidates[:2]:
                        digest = normalized_hash(content)
                        exists = (
                            db.query(EssayQuote)
                            .filter(EssayQuote.normalized_hash == digest)
                            .first()
                        )
                        if exists:
                            report["duplicates"] += 1
                            continue
                        report["samples"].append(
                            {"content": content, "author": author, "url": link, "title": title[:80]}
                        )
                        if dry_run:
                            report["inserted"] += 1
                            continue
                        quote = EssayQuote(
                            content=content,
                            source=source.name,
                            category=source.category,
                            author=author,
                            status=0,
                            review_status="pending",
                            ai_quality="pending",
                            normalized_hash=digest,
                        )
                        db.add(quote)
                        db.flush()
                        _insert_source(db, quote, source, link, author)
                        _insert_tag(db, quote, source.category)
                        report["inserted"] += 1
                    if not dry_run:
                        db.commit()
                    time.sleep(0.3)
                except Exception as exc:
                    report["errors"].append(f"{link[:100]}: {exc}")
        except Exception as exc:
            report["errors"].append(f"list: {exc}")
        reports.append(report)
    return reports
