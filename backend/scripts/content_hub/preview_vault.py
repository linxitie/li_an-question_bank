#!/usr/bin/env python3
"""预览金句素材库解析结果（只读，不写数据库）。

用法（在 backend 目录）：
    python -m scripts.content_hub.preview_vault --limit 2
    python -m scripts.content_hub.preview_vault --vault "D:\\砺安题库\\li_an-question_bank\\每日金句知识库" --limit 2

默认扫描 <vault>/01-金句素材库 下的全部 .md。
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_VAULT = r"D:\砺安题库\li_an-question_bank\每日金句知识库"
DEFAULT_SUBDIR = "01-金句素材库"

_FRONTMATTER_RE = re.compile(r"^\ufeff?---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.S)


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _inline_list(value: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [_unquote(item) for item in inner.split(",") if item.strip()]


def parse_frontmatter(raw: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current_key:
            fields.setdefault(current_key, [])
            if isinstance(fields[current_key], list):
                fields[current_key].append(_unquote(stripped[2:]))
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        current_key = key
        if not value:
            fields[key] = []
        elif value.startswith("[") and value.endswith("]"):
            fields[key] = _inline_list(value)
        else:
            fields[key] = _unquote(value)
    return fields


def parse_file(path: Path, library_root: Path) -> dict[str, Any] | None:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return None
    fields = parse_frontmatter(match.group(1))
    body = match.group(2).strip()

    quote = str(fields.get("quote") or fields.get("content") or fields.get("金句") or "").strip()
    topics = fields.get("applicable_topics") or fields.get("topics") or []
    if isinstance(topics, str):
        topics = [topics] if topics else []
    keywords = fields.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [keywords] if keywords else []

    relative = path.relative_to(library_root)
    category = relative.parts[0] if relative.parts else ""

    return {
        "file": relative.as_posix(),
        "category": category,
        "quote": quote,
        "source": str(fields.get("source") or "").strip(),
        "author": str(fields.get("author") or "").strip(),
        "topics": topics,
        "keywords": keywords,
        "status": str(fields.get("status") or "").strip(),
        "date": str(fields.get("date") or "").strip(),
        "type": str(fields.get("type") or "").strip(),
        "body": body[:200],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="预览金句素材库解析（只读）")
    parser.add_argument("--vault", default=DEFAULT_VAULT)
    parser.add_argument("--subdir", default=DEFAULT_SUBDIR)
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--status", default=None, help="仅显示指定 status，如 已审核")
    args = parser.parse_args()

    library_root = Path(args.vault) / args.subdir
    if not library_root.is_dir():
        print(json.dumps({"ok": False, "error": "library_not_found", "path": str(library_root)}, ensure_ascii=False, indent=2))
        return 2

    files = sorted(library_root.rglob("*.md"))
    parsed: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    skipped = 0
    for path in files:
        item = parse_file(path, library_root)
        if not item:
            skipped += 1
            continue
        statuses[item["status"] or "(空)"] += 1
        if args.status and item["status"] != args.status:
            continue
        parsed.append(item)

    samples = parsed[: max(0, args.limit)]
    missing = {
        "quote": sum(1 for item in parsed if not item["quote"]),
        "source": sum(1 for item in parsed if not item["source"]),
        "topics": sum(1 for item in parsed if not item["topics"]),
    }
    print(
        json.dumps(
            {
                "ok": True,
                "library": str(library_root),
                "total_files": len(files),
                "parsed": len(parsed),
                "skipped": skipped,
                "status_counts": dict(statuses),
                "missing": missing,
                "samples": samples,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
