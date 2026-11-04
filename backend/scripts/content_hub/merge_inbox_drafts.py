#!/usr/bin/env python3
"""把 00-收件箱/金句 里的 draft 合并成一个可编辑清单。

用法（在 backend 目录）：
    python -m scripts.content_hub.merge_inbox_drafts
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from app.core.database import SessionLocal
from app.models.models import EssayQuote
from app.services.obsidian_export import _quote_topics

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VAULT = BACKEND_ROOT / "content_hub_vault"
FINAL_DOC = DEFAULT_VAULT / "00-收件箱" / "审核看板" / "人工复核总清单_最终版.md"
_SECTION_RE = re.compile(r"(?ms)^### (\d+)\. ([^\n]+)\n(.*?)(?=^### |\Z)")


def _final_reasons(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for _num, _title, body in _SECTION_RE.findall(path.read_text(encoding="utf-8")):
        uid = re.search(r"- UID：`([^`]+)`", body)
        note = re.search(r"^- 备注：(.+)$", body, re.M)
        decision = re.search(r"^- \[x\] (通过|拒绝|退回修改)$", body, re.M)
        if uid and decision and decision.group(1) == "退回修改":
            result[uid.group(1)] = note.group(1) if note else ""
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="合并收件箱退回稿")
    parser.add_argument("--vault", default=str(DEFAULT_VAULT))
    args = parser.parse_args()

    vault = Path(args.vault)
    reasons = _final_reasons(FINAL_DOC)
    db = SessionLocal()
    try:
        quotes = (
            db.query(EssayQuote)
            .filter(EssayQuote.review_status == "draft")
            .order_by(EssayQuote.quality_score.desc(), EssayQuote.quote_id)
            .all()
        )
        rows = []
        for quote in quotes:
            rows.append({
                "uid": quote.quote_uid,
                "score": quote.quality_score,
                "source": quote.source or "",
                "author": quote.author or "",
                "content": quote.content,
                "topics": _quote_topics(db, quote.quote_id),
                "reason": reasons.get(quote.quote_uid, ""),
            })
    finally:
        db.close()

    lines = [
        "# 退回修改金句合并清单",
        "",
        f"> 生成时间：{datetime.now():%Y-%m-%d %H:%M:%S}",
        f"> 共 {len(rows)} 条；来自 00-收件箱/金句 的 draft 金句。",
        "> 每条补作者/出处或修改内容后，勾选“已修改”；单条原笔记仍保留。",
        "",
        "---",
        "",
    ]
    for index, row in enumerate(rows, 1):
        lines.extend([
            f"### {index}. {row['uid']} — {row['score']} 分",
            "",
            f"- UID：`{row['uid']}`",
            f"- 来源：{row['source'] or '（缺失）'}",
            f"- 作者：{row['author'] or '（缺失）'}",
            f"- 主题：{'、'.join(row['topics']) or '（未关联）'}",
        ])
        if row["reason"]:
            lines.append(f"- 最终审核备注：{row['reason']}")
        lines.extend([
            "",
            f"> {row['content']}",
            "",
            "- [ ] 已修改",
            "- 修改备注：",
            "",
        ])

    out = vault / "00-收件箱" / "金句" / f"退回修改合并清单_{len(rows)}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.replace(out)
    print(json.dumps({"ok": True, "path": str(out), "total": len(rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
