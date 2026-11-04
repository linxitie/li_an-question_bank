#!/usr/bin/env python3
"""把最终校准版清单里的作者写回 essay_quote（只改 draft 的作者，不改状态）。"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from app.core.database import SessionLocal
from app.models.models import QuoteReview
from app.services.quote_review_service import get_quote

DEFAULT_INPUT = Path(__file__).resolve().parents[2] / "content_hub_vault" / "00-收件箱" / "金句" / "退回修改合并清单_144_最终校准版.md"
_SECTION_RE = re.compile(r"(?ms)^### (\d+)\. ([^\n]+)\n(.*?)(?=^### |\Z)")


def _parse(text: str):
    for match in _SECTION_RE.finditer(text):
        _num, _title, body = match.groups()
        uid = re.search(r"- UID：`([^`]+)`", body)
        author = re.search(r"^- 作者：(.+)$", body, re.M)
        checked = "- [x] 已修改" in body
        if uid and author and checked:
            yield uid.group(1), author.group(1).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    changed = 0
    unchanged = 0
    missing = []
    try:
        for uid, author in _parse(Path(args.input).read_text(encoding="utf-8")):
            quote = get_quote(db, uid)
            if not quote or quote.review_status != "draft":
                missing.append(uid)
                continue
            if quote.author == author:
                unchanged += 1
                continue
            if not args.apply:
                changed += 1
                continue
            before = quote.author or ""
            quote.author = author
            db.add(
                QuoteReview(
                    quote_id=quote.quote_id,
                    reviewer_id=None,
                    action="author_calibration",
                    reason=f"最终校准版补作者：{author}",
                    diff_json=json.dumps(
                        {"from": before, "to": author}, ensure_ascii=False
                    ),
                )
            )
            changed += 1
        if args.apply:
            db.commit()
    finally:
        db.close()

    print(json.dumps({
        "apply": bool(args.apply),
        "changed": changed,
        "unchanged": unchanged,
        "missing_or_not_draft": missing[:20],
        "missing_count": len(missing),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
