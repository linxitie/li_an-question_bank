#!/usr/bin/env python3
"""把最终复核清单的勾选结果回写到数据库。

用法（在 backend 目录）：
    python -m scripts.content_hub.apply_final_review --dry-run
    python -m scripts.content_hub.apply_final_review --apply
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from app.core.database import SessionLocal
from app.models.models import QuoteReview
from app.services.quote_review_service import get_quote

DEFAULT_INPUT = Path(__file__).resolve().parents[2] / "content_hub_vault" / "00-收件箱" / "审核看板" / "人工复核总清单_最终版.md"
_SECTION_RE = re.compile(r"(?ms)^### (\d+)\. ([^\n]+)\n(.*?)(?=^### |\Z)")


def _parse(text: str):
    for match in _SECTION_RE.finditer(text):
        _num, _title, body = match.groups()
        uid_match = re.search(r"- UID：`([^`]+)`", body)
        decision = re.search(r"^- \[x\] (通过|拒绝|退回修改)$", body, re.M)
        note = re.search(r"^- 备注：(.+)$", body, re.M)
        if uid_match and decision:
            yield uid_match.group(1), decision.group(1), (note.group(1) if note else "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply and args.dry_run:
        parser.error("--apply and --dry-run cannot be used together")

    text = Path(args.input).read_text(encoding="utf-8")
    db = SessionLocal()
    changed = 0
    missing = []
    try:
        for uid, decision, reason in _parse(text):
            quote = get_quote(db, uid)
            if not quote:
                missing.append(uid)
                continue
            target = "published" if decision == "通过" else "draft"
            target_status = 1 if target == "published" else 0
            if quote.review_status == target and quote.status == target_status:
                continue
            changed += 1
            if args.dry_run:
                continue
            before = quote.review_status or ""
            quote.review_status = target
            quote.status = target_status
            db.add(
                QuoteReview(
                    quote_id=quote.quote_id,
                    reviewer_id=None,
                    action="final_review_approve" if decision == "通过" else "final_review_request_changes",
                    reason=reason or f"final review: {decision}",
                    diff_json=json.dumps(
                        {"from": before, "to": target, "decision": decision},
                        ensure_ascii=False,
                    ),
                )
            )
        if args.apply:
            db.commit()
    finally:
        db.close()

    print(json.dumps({
        "apply": bool(args.apply),
        "changed": changed,
        "missing": missing,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
