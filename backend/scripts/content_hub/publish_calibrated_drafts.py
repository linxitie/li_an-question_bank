#!/usr/bin/env python3
"""把最终校准版中的 draft 批量转为 published。"""
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


def _uids(text: str) -> list[str]:
    result = []
    for _num, _title, body in _SECTION_RE.findall(text):
        uid = re.search(r"- UID：`([^`]+)`", body)
        if uid and "- [x] 已修改" in body:
            result.append(uid.group(1))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    uids = _uids(Path(args.input).read_text(encoding="utf-8"))
    db = SessionLocal()
    changed = 0
    missing = []
    try:
        for uid in uids:
            quote = get_quote(db, uid)
            if not quote or quote.review_status != "draft":
                missing.append(uid)
                continue
            if args.apply:
                quote.review_status = "published"
                quote.status = 1
                db.add(
                    QuoteReview(
                        quote_id=quote.quote_id,
                        reviewer_id=None,
                        action="publish_calibrated_draft",
                        reason="最终校准完成，批量发布",
                        diff_json=json.dumps(
                            {"from": "draft", "to": "published"},
                            ensure_ascii=False,
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
        "input_uids": len(uids),
        "published": changed,
        "missing_or_not_draft": missing[:20],
        "missing_count": len(missing),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
