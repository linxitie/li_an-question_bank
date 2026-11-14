#!/usr/bin/env python3
"""Obsidian 内容库整理器。

默认 dry-run，只打印计划；确认后使用 --apply 才移动文件。

用法：
    cd backend
    python -m scripts.obsidian_organizer --vault content_hub_vault --dry-run
    python -m scripts.obsidian_organizer --vault content_hub_vault --apply
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.S)
SKIP_DIRS = {".obsidian", ".trash", "uploads", "node_modules", "__pycache__"}
SKIP_NAMES = {"index.md", "dashboard.md", "readme.md"}

MODULE_DIRS = {
    "quote": "01-每日金句",
    "news": "02-每日新闻",
    "recruitment": "03-招考信息",
}
MODULE_TITLES = {
    "01-每日金句": "每日金句",
    "02-每日新闻": "每日新闻",
    "03-招考信息": "招考信息",
}
STATUS_DIRS = {
    "inbox": "00-收件箱",
    "pending": "01-待审核",
    "approved": "02-已发布",
    "rejected": "03-已拒绝",
    "archived": "04-归档",
}
STATUS_TITLES = {
    "00-收件箱": "收件箱",
    "01-待审核": "待审核",
    "02-已发布": "已发布",
    "03-已拒绝": "已拒绝",
    "04-归档": "归档",
}


def normalize_type(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"quote", "quotes", "金句"}:
        return "quote"
    if text in {"news", "新闻"}:
        return "news"
    if text in {"recruitment", "招考", "招聘"}:
        return "recruitment"
    return None


def normalize_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"pending", "review", "待审核"}:
        return "pending"
    if text in {"approved", "published", "已发布"}:
        return "approved"
    if text in {"rejected", "已拒绝"}:
        return "rejected"
    if text in {"archived", "归档"}:
        return "archived"
    return "inbox"


def read_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, "no_frontmatter"
    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        return {}, f"yaml_error:{exc.__class__.__name__}"
    if not isinstance(data, dict):
        return {}, "frontmatter_not_mapping"
    return data, ""


def iter_markdown(vault: Path):
    for path in vault.rglob("*.md"):
        try:
            relative = path.relative_to(vault)
        except ValueError:
            continue
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if path.name.lower() in SKIP_NAMES:
            continue
        yield path


def unique_target(target: Path) -> Path:
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    for index in range(1, 10000):
        candidate = target.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"无法生成不冲突文件名: {target}")


def infer_status(meta: dict[str, Any], source: Path, vault: Path) -> str:
    """优先使用 frontmatter；缺失时按历史审核目录兜底，避免归档文件回流收件箱。"""
    explicit = normalize_status(meta.get("status") or meta.get("review_status"))
    parts = source.relative_to(vault).parts
    if "07-归档" in parts:
        return "archived"
    if "03-建议拒绝" in parts:
        return "rejected"
    if "01-优先通过" in parts:
        return "approved"
    if "02-重点复核" in parts:
        return "pending"
    return explicit


def index_content(module: str, status: str | None = None) -> str:
    title = MODULE_TITLES.get(module, module)
    if status:
        title = f"{title} · {STATUS_TITLES.get(status, status)}"
    parent = (
        "../../00-Dashboard/Dashboard.md"
        if status
        else "../00-Dashboard/Dashboard.md"
    )
    return (
        f"# {title}\n\n"
        f"> 本目录由 Obsidian 内容库规范维护。返回 [[{parent}|总览 Dashboard]]。\n\n"
        "## 说明\n\n"
        "- 本目录只存放对应业务模块和生命周期状态的内容。\n"
        "- 文件 frontmatter 的 `type` 和 `status` 决定目录归属。\n"
        "- 迁移前请先执行 dry-run，确认移动计划。\n"
    )


def ensure_indexes(vault: Path, dry_run: bool) -> list[str]:
    created: list[str] = []
    targets: list[tuple[Path, str]] = [
        (vault / "00-Dashboard" / "Dashboard.md", index_content("Dashboard")),
    ]
    for module in MODULE_DIRS.values():
        targets.append((vault / module / "index.md", index_content(module)))
        for status in STATUS_DIRS.values():
            targets.append(
                (vault / module / status / "index.md", index_content(module, status))
            )
    for path, content in targets:
        if path.exists():
            continue
        created.append(str(path))
        if dry_run:
            print(f"[DRY-RUN] 准备创建导航: {path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"[CREATE] 已创建导航: {path}")
    return created


def organize(vault: Path, apply: bool, make_indexes: bool) -> dict[str, Any]:
    dry_run = not apply
    vault = vault.expanduser().resolve()
    if not vault.is_dir():
        raise SystemExit(f"Vault 不存在或不是目录: {vault}")

    report: dict[str, Any] = {
        "vault": str(vault),
        "mode": "apply" if apply else "dry-run",
        "planned": 0,
        "moved": 0,
        "skipped": 0,
        "unknown": [],
        "collisions": [],
        "indexes_created": [],
    }
    if make_indexes:
        report["indexes_created"] = ensure_indexes(vault, dry_run)

    for source in iter_markdown(vault):
        meta, meta_error = read_frontmatter(source)
        module_key = normalize_type(meta.get("type"))
        if module_key is None:
            report["unknown"].append(
                {
                    "path": str(source.relative_to(vault)),
                    "reason": meta_error or "unknown_type",
                    "type": meta.get("type"),
                }
            )
            report["skipped"] += 1
            continue
        status_key = infer_status(meta, source, vault)
        target_dir = vault / MODULE_DIRS[module_key] / STATUS_DIRS[status_key]
        target = unique_target(target_dir / source.name)
        if target == source:
            report["skipped"] += 1
            continue
        report["planned"] += 1
        relative_source = source.relative_to(vault)
        relative_target = target.relative_to(vault)
        if dry_run:
            print(f"[DRY-RUN] 准备把 {relative_source} 移动到 {relative_target}")
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        if target.exists():
            report["collisions"].append(
                {
                    "source": str(relative_source),
                    "target": str(relative_target),
                }
            )
        shutil.move(str(source), str(target))
        report["moved"] += 1
        print(f"[MOVE] {relative_source} -> {relative_target}")

    if apply:
        log_dir = vault / "99-系统" / "迁移日志"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"迁移_{datetime.now():%Y%m%d_%H%M%S}.json"
        log_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report["log_path"] = str(log_path)
        print(f"[LOG] {log_path}")
    else:
        print("[DRY-RUN] 未移动任何文件。确认计划后加 --apply 执行。")

    print(
        "[SUMMARY] "
        f"planned={report['planned']} moved={report['moved']} "
        f"skipped={report['skipped']} unknown={len(report['unknown'])}"
    )
    return report


def main() -> int:
    repo_backend = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="整理 Obsidian 内容库目录")
    parser.add_argument(
        "--vault",
        default=str(repo_backend / "content_hub_vault"),
        help="Vault 路径，默认 backend/content_hub_vault",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印移动计划，不移动文件（默认模式）",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="真正移动文件；不加此参数时始终为 dry-run",
    )
    parser.add_argument(
        "--no-index",
        action="store_true",
        help="不自动创建 index.md/Dashboard.md",
    )
    args = parser.parse_args()
    if args.apply and args.dry_run:
        parser.error("--apply 与 --dry-run 不能同时使用")
    organize(Path(args.vault), apply=args.apply, make_indexes=not args.no_index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
