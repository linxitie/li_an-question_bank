"""R2.1 通用新闻采集器：配置驱动，首批 8 个来源。"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.news_sources import NEWS_SOURCES, SOURCE_BY_CODE, NewsSourceConfig
from ..models.models import NewsArticle, NewsImage
from .news_storage import NewsStorage, get_news_storage

logger = logging.getLogger(__name__)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
_NAV_WORDS = ("登录", "注册", "首页", "更多", "English", "网站地图", "联系我们")
_BAD_HOST_PREFIXES = ("en.", "mail.", "search.")
_CONTENT_SELECTORS = (
    "article", ".article-content", ".article", ".content", ".TRS_Editor",
    ".p2j_con3", "#content", "#article", ".main-content", ".detail",
)
_DATE_RE = re.compile(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})")


@dataclass
class ArticleData:
    url: str
    title: str
    content: str
    published_at: datetime | None = None
    images: list[str] = field(default_factory=list)


def _fetch_html(url: str, adapter: str = "http", timeout: int = 20) -> str:
    if adapter == "playwright":
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True, channel="msedge")
            except Exception:
                browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=UA)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                html = page.content()
            finally:
                browser.close()
        return html

    resp = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() in ("iso-8859-1", "ascii"):
        resp.encoding = resp.apparent_encoding or "utf-8"
    return resp.text


def parse_list_links(
    html: str,
    page_url: str,
    limit: int = 10,
    allowed_hosts: tuple[str, ...] = (),
) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        title = " ".join(anchor.get_text(" ", strip=True).split())
        href = anchor["href"].strip()
        if len(title) < 8 or len(title) > 100:
            continue
        if href.startswith(("#", "javascript:", "mailto:")):
            continue
        if any(word in title for word in _NAV_WORDS):
            continue
        url = urljoin(page_url, href)
        if not url.startswith(("http://", "https://")):
            continue
        host = urlparse(url).netloc.lower()
        if any(host.startswith(prefix) for prefix in _BAD_HOST_PREFIXES):
            continue
        if allowed_hosts and not any(
            host == allowed or host.endswith("." + allowed)
            for allowed in allowed_hosts
        ):
            continue
        if url in seen:
            continue
        seen.add(url)
        links.append(url)
        if len(links) >= limit:
            break
    return links


def parse_article(html: str, url: str) -> ArticleData:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = ""
    for selector in ('meta[property="og:title"]', "h1", "title"):
        node = soup.select_one(selector)
        if node:
            title = (node.get("content") or node.get_text(" ", strip=True) or "").strip()
            if title:
                break
    body = ""
    best_score = 0
    for selector in _CONTENT_SELECTORS:
        for node in soup.select(selector):
            text = "\n".join(
                line.strip() for line in node.get_text("\n", strip=True).splitlines() if line.strip()
            )
            if len(text) > best_score:
                body = text
                best_score = len(text)
    if not body:
        body = "\n".join(
            line.strip() for line in soup.get_text("\n", strip=True).splitlines()
            if len(line.strip()) >= 8
        )
    date_match = _DATE_RE.search(soup.get_text(" ", strip=True))
    published_at = None
    if date_match:
        try:
            published_at = datetime(*map(int, date_match.groups()))
        except ValueError:
            published_at = None
    images = []
    for img in soup.find_all("img"):
        src = (img.get("src") or img.get("data-src") or "").strip()
        if not src or src.startswith("data:"):
            continue
        src = urljoin(url, src)
        if src.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
            images.append(src)
        if len(images) >= 5:
            break
    return ArticleData(url=url, title=title, content=body.strip(), published_at=published_at, images=images)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _content_hash(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()


def _suffix(url: str) -> str:
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
        if path.endswith(ext):
            return ext
    return ".jpg"


def _download_image(url: str, storage: NewsStorage, timeout: int = 15) -> str | None:
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
        resp.raise_for_status()
        if len(resp.content) > 8 * 1024 * 1024:
            return None
        return storage.save_image(resp.content, _suffix(url), source_url=url)
    except Exception as exc:
        logger.warning("news image failed %s: %s", url[:100], exc)
        return None


def collect_source(
    db: Session,
    source: NewsSourceConfig,
    *,
    limit: int = 5,
    dry_run: bool = False,
    fetcher: Callable[[str], str] | None = None,
    storage: NewsStorage | None = None,
) -> dict:
    fetch = fetcher or (lambda url: _fetch_html(url, source.adapter))
    storage = storage or get_news_storage()
    report = {
        "source": source.code,
        "ok": False,
        "links": 0,
        "inserted": 0,
        "duplicates": 0,
        "images": 0,
        "errors": [],
        "samples": [],
    }
    try:
        list_html = fetch(source.list_url)
        host = urlparse(source.base_url).netloc.lower()
        allowed_hosts = (host, host.removeprefix("www."))
        links = parse_list_links(list_html, source.list_url, limit=limit, allowed_hosts=allowed_hosts)
        report["links"] = len(links)
        for link in links:
            try:
                article = parse_article(fetch(link), link)
            except Exception as exc:
                report["errors"].append(f"{link[:120]}: {exc}")
                continue
            if not article.title or len(article.content) < 80:
                report["errors"].append(f"{link[:120]}: empty title/content")
                continue
            digest = _content_hash(article.content)
            existing = (
                db.query(NewsArticle)
                .filter(
                    or_(
                        NewsArticle.url == link,
                        NewsArticle.title == article.title,
                        NewsArticle.content_hash == digest,
                    )
                )
                .first()
            )
            if existing:
                report["duplicates"] += 1
                continue
            report["samples"].append({"title": article.title, "url": link, "chars": len(article.content)})
            if dry_run:
                report["inserted"] += 1
                continue
            news = NewsArticle(
                title=article.title[:500],
                url=link[:1000],
                source=source.code,
                category=source.category,
                category_code=source.category_code,
                region_code=source.region_code,
                publish_date=article.published_at or datetime.now(),
                event_date=article.published_at.date() if article.published_at else None,
                summary=article.content[:180],
                content=article.content,
                content_hash=digest,
                review_status="pending",
                status=0,
            )
            db.add(news)
            db.flush()
            for order, image_url in enumerate(article.images):
                rel = _download_image(image_url, storage)
                if rel:
                    db.add(NewsImage(news_id=news.news_id, image_path=rel, image_order=order))
                    report["images"] += 1
            report["inserted"] += 1
        if not dry_run:
            db.commit()
        report["ok"] = True
    except Exception as exc:
        db.rollback()
        report["errors"].append(str(exc))
    return report


def collect_all_sources(db: Session, *, limit: int = 5, dry_run: bool = False) -> list[dict]:
    reports = []
    for source in NEWS_SOURCES:
        if not source.enabled:
            continue
        reports.append(collect_source(db, source, limit=limit, dry_run=dry_run))
    return reports


def source_by_code(code: str) -> NewsSourceConfig | None:
    return SOURCE_BY_CODE.get(code)
