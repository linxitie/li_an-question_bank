"""R1 Obsidian 审核收件箱回写。"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models.models import EssayQuote
from . import quote_review_service
from .obsidian_export import _safe_path

_FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.S)

_STATUS_ACTIONS = {
    "published": "approve",
    "已审核": "approve",
    "通过": "approve",
    "approve": "approve",
    "rejected": "reject",
    "已拒绝": "reject",
    "reject": "reject",
    "draft": "request_changes",
    "需修改": "request_changes",
    "退回": "request_changes",
    "request_changes": "request_changes",
}


def parse_note(text: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        fields[key.strip()] = value
    return fields, match.group(2)


def _move(vault: Path, path: Path, *parts: str, name: str) -> None:
    target_dir = _safe_path(vault, *parts)
    target_dir.mkdir(parents=True, exist_ok=True)
    path.replace(target_dir / name)


def sync_review_inbox(db: Session, vault: Path, dry_run: bool = False) -> dict[str, Any]:
    """扫描收件箱与审核看板，按 frontmatter.status 回写审核结果。"""
    vault = Path(vault).expanduser()
    if not vault.exists() or not vault.is_dir():
        return {"ok": False, "error": "vault_not_found", "vault": str(vault)}

    inbox = _safe_path(vault, "00-收件箱", "金句")
    board = _safe_path(vault, "00-收件箱", "审核看板")
    report: dict[str, Any] = {
        "ok": True,
        "processed": 0,
        "skipped": 0,
        "moved": 0,
        "errors": [],
    }
    folders = [folder for folder in (inbox, board) if folder.is_dir()]
    if not folders:
        return report

    for folder in folders:
        is_board = folder == board
        for path in sorted(folder.glob("*.md")):
            fields, _body = parse_note(path.read_text(encoding="utf-8"))
            uid = fields.get("uid") or path.stem
            raw_status = (fields.get("status") or "").strip()
            action = _STATUS_ACTIONS.get(raw_status.lower())
            if not action:
                report["skipped"] += 1
                continue

            quote = quote_review_service.get_quote(db, uid)
            if not quote:
                report["errors"].append(f"{uid}: quote not found")
                continue

            current = quote.review_status or "published"
            allowed = ("pending", "draft", "published") if is_board else ("pending", "draft")
            if current not in allowed:
                report["skipped"] += 1
                if not dry_run:
                    _move(
                        vault,
                        path,
                        "00-收件箱",
                        "冲突",
                        name=f"{uid}-{datetime.now():%Y%m%d_%H%M%S_%f}.md",
                    )
                    report["moved"] += 1
                continue

            if dry_run:
                report["processed"] += 1
                continue

            noop = (
                (action == "approve" and current == "published")
                or (action == "reject" and current == "rejected")
                or (action == "request_changes" and current == "draft")
            )
            if not noop:
                try:
                    quote_review_service.review_quote(
                        db,
                        quote_ref=uid,
                        action=action,
                        reviewer=None,
                        reason=fields.get("review_note", ""),
                    )
                except ValueError as exc:
                    report["errors"].append(f"{uid}: {exc}")
                    continue

            _move(
                vault,
                path,
                "07-归档",
                "审核记录",
                name=f"{uid}-{datetime.now():%Y%m%d_%H%M%S_%f}.md",
            )
            report["processed"] += 1
            report["moved"] += 1

    if board.is_dir() and report["processed"] and not dry_run:
        from .review_board_export import export_review_board

        report["board_refresh"] = export_review_board(db, vault)

    return report
