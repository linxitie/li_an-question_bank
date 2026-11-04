#!/usr/bin/env python3
"""温和检查新闻来源 robots.txt（仅 robots，不抓文章）。"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from app.core.news_sources import NEWS_SOURCES

UA = "LiAnNewsBot/1.0 (robots compliance check)"


def fetch_robots(base_url: str, timeout: int = 12):
    host = urlparse(base_url).netloc
    scheme = urlparse(base_url).scheme or "https"
    candidates = (scheme, "https" if scheme == "http" else "http")
    last = None
    for candidate in candidates:
        url = f"{candidate}://{host}/robots.txt"
        try:
            response = requests.get(
                url,
                headers={"User-Agent": UA, "Accept": "text/plain,*/*;q=0.1"},
                timeout=timeout,
                allow_redirects=True,
            )
            return url, response
        except Exception as exc:  # noqa: BLE001 - 连接失败需要记录
            last = exc
    return f"{scheme}://{host}/robots.txt", last


def is_plain_robots(text: str) -> bool:
    body = (text or "").lstrip("\ufeff \t\r\n")
    return bool(body) and not body.lower().startswith(("<", "<!doctype", "<html"))


def inspect(timeout: int = 12, delay: float = 1.1) -> list[dict]:
    results = []
    for source in NEWS_SOURCES:
        robots_url, response = fetch_robots(source.base_url, timeout=timeout)
        row = {
            "code": source.code,
            "name": source.name,
            "base_url": source.base_url,
            "robots_url": robots_url,
            "status": None,
            "declared": False,
            "can_fetch_list": None,
            "crawl_delay": None,
            "rule_count": 0,
            "sitemaps": [],
            "note": "",
        }
        if isinstance(response, Exception):
            row["note"] = f"连接失败: {response}"
            results.append(row)
            time.sleep(delay)
            continue
        row["status"] = response.status_code
        text = response.content.decode("utf-8-sig", errors="replace")
        if response.status_code == 200 and is_plain_robots(text):
            row["declared"] = True
            parser = RobotFileParser()
            parser.parse(text.splitlines())
            row["can_fetch_list"] = bool(parser.can_fetch("*", source.list_url))
            row["crawl_delay"] = parser.crawl_delay("*")
            row["rule_count"] = sum(
                1
                for line in text.splitlines()
                if line.strip().lower().startswith(("allow:", "disallow:"))
            )
            row["sitemaps"] = parser.site_maps() or []
        elif response.status_code == 404:
            row["note"] = "未发布 robots.txt（协议层面无显式规则）"
        elif response.status_code in (401, 403):
            row["note"] = f"robots 返回 HTTP {response.status_code}"
        elif response.status_code == 200:
            row["note"] = "返回 HTML/挑战页，非有效 robots"
        else:
            row["note"] = f"HTTP {response.status_code}"
        results.append(row)
        print(
            f"{source.code:14s} {str(row['status']):4s} "
            f"declared={row['declared']!s:5s} allow={row['can_fetch_list']!s:5s} "
            f"{row['note']}"
        )
        time.sleep(delay)
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--delay", type=float, default=1.1)
    parser.add_argument("--out", default="data/audit/news_robots_report.json")
    args = parser.parse_args()
    results = inspect(timeout=args.timeout, delay=args.delay)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
