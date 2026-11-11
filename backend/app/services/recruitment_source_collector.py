"""招考官方来源采集器（HTTP + Playwright 降级）。"""

from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from ..models.models import PolicePost, RecruitmentInfo, RecruitmentSourceStatus
from .news_collector import _fetch_html, clean_article_text
from .recruitment_sources import SOURCES, RecruitmentSource

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LiAnRecruitmentBot/1.0)"}
_DATE_RE = re.compile(r"20\d{2}[-/年]\d{1,2}[-/月]\d{1,2}")
_CONTENT_SELECTORS = (
    "article",
    ".article-content",
    ".article",
    ".content",
    ".TRS_Editor",
    "#content",
    ".main-content",
    ".detail",
)
_RECRUITMENT_TERMS = (
    "公务员",
    "招录",
    "招聘",
    "选调",
    "遴选",
    "事业单位",
    "公安",
    "招警",
    "三支一扶",
    "职位",
    "报名",
    "资格审查",
    "资格复审",
    "笔试",
    "面试",
    "体检",
    "考察",
    "公示",
)
_NOISE_TERMS = (
    "习近平",
    "党委",
    "代表大会",
    "长征",
    "红军",
    "图讯",
    "要闻",
    "时政",
    "理论",
    "学习贯彻",
    "会议",
    "讲话",
    "活动",
    "政务服务",
)


def _clean_title(value: str) -> str:
    text = html_lib.unescape(value or "")
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True).strip()


def _is_recruitment_text(title: str, content: str = "") -> bool:
    title = _clean_title(title)
    if not title or len(title) < 8:
        return False
    if any(term in title for term in _NOISE_TERMS):
        return False
    if any(term in title for term in _RECRUITMENT_TERMS):
        return True
    return any(term in (content or "") for term in ("公务员招录", "公开招聘", "招录公告"))



def _source_status(db: Session, source: RecruitmentSource) -> RecruitmentSourceStatus:
    row = db.get(RecruitmentSourceStatus, source.code)
    if row is None:
        row = RecruitmentSourceStatus(source_key=source.code, source_name=source.name)
        db.add(row)
        db.flush()
    return row


def _fetch(url: str, source: RecruitmentSource) -> tuple[str, str]:
    """先 HTTP，失败/疑似反爬时切 Playwright；不绕过验证码。"""
    try:
        html = _fetch_html(url, "http", headers=_HEADERS)
        if len(html) >= 500:
            return html, "http"
    except Exception:
        pass
    html = _fetch_html(url, "playwright", headers=_HEADERS, wait_ms=5000)
    return html, "playwright"


def _links(source: RecruitmentSource, html: str, limit: int) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    result = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        url = urljoin(source.list_url, anchor["href"]).split("#")[0]
        if urlparse(url).netloc.lower() != source.host:
            continue
        text = _clean_title(anchor.get_text(" ", strip=True))
        if len(text) < 8:
            continue
        if not _is_recruitment_text(text):
            continue
        if not re.search(source.link_regex, urlparse(url).path):
            continue
        if url in seen:
            continue
        seen.add(url)
        result.append(url)
        if len(result) >= limit:
            break
    return result


def _parse_detail(html: str, url: str, source: RecruitmentSource) -> tuple[str, str, str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for selector in ('meta[property="og:title"]', "h1", ".article-title", ".title"):
        for node in soup.select(selector):
            value = node.get("content") if node.name == "meta" else node.get_text(" ", strip=True)
            cleaned = _clean_title(value or "")
            if cleaned:
                candidates.append(cleaned)
    if soup.title:
        candidates.append(_clean_title(soup.title.get_text(" ", strip=True)))
    title = max(candidates, key=len) if candidates else ""
    if title == source.name or title == source.list_url:
        title = ""
    node = None
    best = 0
    for selector in _CONTENT_SELECTORS:
        for candidate in soup.select(selector):
            text = candidate.get_text("\n", strip=True)
            if len(text) > best:
                best = len(text)
                node = candidate
    if node is None:
        node = soup
    paragraphs = [
        p.get_text(" ", strip=True) for p in node.find_all("p") if len(p.get_text(" ", strip=True)) >= 10
    ]
    raw = "\n".join(paragraphs) or node.get_text("\n", strip=True)
    content = clean_article_text(title, raw)
    date_match = _DATE_RE.search(node.get_text(" ", strip=True) or soup.get_text(" ", strip=True))
    published = ""
    if date_match:
        nums = re.findall(r"\d+", date_match.group(0))
        if len(nums) >= 3:
            published = "-".join(f"{int(x):02d}" for x in nums[:3])
    return title[:200], content[:30000], published


def _ensure_post(db: Session, rec: RecruitmentInfo) -> PolicePost | None:
    existing = db.query(PolicePost).filter(PolicePost.recruitment_id == rec.recruitment_id).first()
    if existing:
        return existing
    post = PolicePost(
        recruitment_id=rec.recruitment_id,
        job_name=rec.title[:200],
        employer=(rec.organization or "")[:200],
        province=(rec.region or "")[:50],
        city=(rec.region or "")[:50],
        category=(rec.category or "")[:50],
        registration_start=rec.registration_start or None,
        registration_end=rec.registration_end or rec.deadline or None,
        official_url=rec.url or None,
        source=rec.source_name or "招考来源",
        status=1,
        parse_status="pending",
        parse_confidence=0.3,
        evidence_json=json.dumps({"source": rec.source_name, "url": rec.url}, ensure_ascii=False),
    )
    db.add(post)
    db.flush()
    return post


def collect_source(
    db: Session, source: RecruitmentSource, *, limit: int = 5, dry_run: bool = False
) -> dict[str, Any]:
    status = _source_status(db, source)
    report = {
        "source": source.code,
        "name": source.name,
        "adapter": source.adapter,
        "links": 0,
        "inserted": 0,
        "duplicates": 0,
        "errors": [],
    }
    try:
        list_html, adapter = _fetch(source.list_url, source)
        report["adapter"] = adapter
        links = _links(source, list_html, limit)
        report["links"] = len(links)
        for link in links:
            try:
                html, used = _fetch(link, source)
                title, content, published = _parse_detail(html, link, source)
                if not title or len(content) < 80 or not _is_recruitment_text(title, content):
                    report["errors"].append(f"{link[:100]}: not a recruitment article")
                    continue
                exists = db.query(RecruitmentInfo).filter(RecruitmentInfo.url == link).first()
                if exists:
                    report["duplicates"] += 1
                    continue
                if not dry_run:
                    rec = RecruitmentInfo(
                        title=title,
                        organization=source.name,
                        category=source.category,
                        region=source.name.replace("人事考试网", "").replace("省", "")[:50],
                        content=content,
                        url=link,
                        source_key=source.code,
                        source_name=source.name,
                        raw_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                        parse_status="pending",
                        last_seen_at=datetime.now(),
                        publish_date=published,
                        status=1,
                    )
                    db.add(rec)
                    db.flush()
                    db.commit()
                report["inserted"] += 1
            except Exception as exc:
                report["errors"].append(f"{link[:100]}: {exc}")
        status.status = "ok"
        status.last_error = None
        status.last_run_at = datetime.now()
        status.fetched += report["links"]
        status.inserted += report["inserted"]
    except Exception as exc:
        status.status = "blocked"
        status.last_error = str(exc)[:500]
        status.last_run_at = datetime.now()
        report["errors"].append(f"list: {exc}")
    db.commit()
    return report


def collect_all_recruitment_sources(
    db: Session, *, limit: int = 5, dry_run: bool = False
) -> list[dict[str, Any]]:
    return [
        collect_source(db, source, limit=limit, dry_run=dry_run)
        for source in SOURCES
        if source.enabled
    ]
