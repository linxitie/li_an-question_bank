"""R2.3 Obsidian 新闻审核勾选回写。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .news_review_service import review_news
from .obsidian_export import _safe_path

_FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.S)
_CHECKS = {"通过": "publish", "拒绝": "reject", "退回修改": "needs_changes"}
_CHECK_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s*(通过|拒绝|退回修改)", re.M)
_NOTE_RE = re.compile(r"^\s*-\s*备注\s*[:：]\s*(.+)$", re.M)


def _parse(text: str):
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    fields = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip('"')
    return fields, match.group(2)


def _action(body: str) -> tuple[str | None, str | None]:
    checked = [label for mark, label in _CHECK_RE.findall(body) if mark.lower() == "x"]
    if len(checked) > 1:
        return None, "only one checkbox may be checked"
    return (_CHECKS[checked[0]] if checked else None), None


def sync_news_review(db: Session, vault: Path, dry_run: bool = False) -> dict[str, Any]:
    vault = Path(vault).expanduser()
    root = vault / "00-收件箱" / "新闻"
    report = {"ok": True, "processed": 0, "skipped": 0, "moved": 0, "errors": []}
    if not root.is_dir():
        return report
    for path in sorted(root.rglob("news_*.md")):
        fields, body = _parse(path.read_text(encoding="utf-8"))
        raw_id = fields.get("news_id")
        if not raw_id:
            report["skipped"] += 1
            continue
        action, error = _action(body)
        if error:
            report["errors"].append(f"{path.name}: {error}")
            continue
        if not action:
            report["skipped"] += 1
            continue
        note = _NOTE_RE.search(body)
        reason = note.group(1).strip() if note else ""
        try:
            news_id = int(raw_id)
        except ValueError:
            report["errors"].append(f"{path.name}: invalid news_id")
            continue
        if dry_run:
            report["processed"] += 1
            continue
        try:
            review_news(db, news_id=news_id, action=action, reason=reason)
        except Exception as exc:
            report["errors"].append(f"{path.name}: {exc}")
            continue
        target = _safe_path(vault, "07-归档", "新闻审核")
        target.mkdir(parents=True, exist_ok=True)
        path.replace(target / f"{news_id}-{datetime.now():%Y%m%d_%H%M%S_%f}.md")
        report["processed"] += 1
        report["moved"] += 1
    return report
