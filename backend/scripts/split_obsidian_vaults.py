#!/usr/bin/env python3
"""把混杂的 Obsidian 内容按 type 拆分到三个独立 Vault。

默认 dry-run。确认后使用 --apply。
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from scripts.obsidian_organizer import (
    STATUS_DIRS,
    infer_status,
    normalize_type,
    read_frontmatter,
    unique_target,
)

TYPE_TARGETS = {
    "quote": "quick_note",
    "news": "news_note",
    "recruitment": "job_note",
}


def normalize_job_type(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"job", "jobs", "recruitment", "招考", "招聘", "招考信息"}:
        return "recruitment"
    return normalize_type(value)


def collect(source: Path, targets: dict[str, Path], apply: bool = False) -> dict[str, Any]:
    report = {
        "source": str(source),
        "mode": "apply" if apply else "dry-run",
        "planned": 0,
        "moved": 0,
        "skipped": 0,
        "unknown": [],
    }
    if not source.is_dir():
        raise SystemExit(f"源 Vault 不存在: {source}")
    for path in source.rglob("*.md"):
        if any(part in {".obsidian", ".trash", "uploads", "node_modules"} for part in path.parts):
            continue
        if path.name.lower() in {"index.md", "dashboard.md", "readme.md"}:
            continue
        meta, meta_error = read_frontmatter(path)
        kind = normalize_job_type(meta.get("type"))
        if kind is None:
            report["unknown"].append(
                {"path": str(path.relative_to(source)), "reason": meta_error or "unknown_type"}
            )
            report["skipped"] += 1
            continue
        status = infer_status(meta, path, source)
        target_root = targets[kind]
        desired = target_root / STATUS_DIRS[status] / path.name
        if desired.resolve() == path.resolve():
            report["skipped"] += 1
            continue
        target = unique_target(desired)
        if target.resolve() == path.resolve():
            report["skipped"] += 1
            continue
        report["planned"] += 1
        print(
            f"[{'MOVE' if apply else 'DRY-RUN'}] "
            f"{path.relative_to(source)} -> {target}"
        )
        if apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
            report["moved"] += 1
    return report


def main() -> int:
    backend = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="拆分 Obsidian 内容到三个独立 Vault")
    parser.add_argument(
        "--source-vault", default=str(backend / "content_hub_vault"), help="当前混杂 Vault"
    )
    parser.add_argument("--quote-vault", default=settings.VAULT_PATH_QUOTE)
    parser.add_argument("--news-vault", default=settings.VAULT_PATH_NEWS)
    parser.add_argument("--job-vault", default=settings.VAULT_PATH_JOB)
    parser.add_argument("--dry-run", action="store_true", help="只打印计划（默认）")
    parser.add_argument("--apply", action="store_true", help="实际移动")
    args = parser.parse_args()
    if args.apply and args.dry_run:
        parser.error("--apply 与 --dry-run 不能同时使用")

    targets = {
        "quote": Path(args.quote_vault).expanduser().resolve(),
        "news": Path(args.news_vault).expanduser().resolve(),
        "recruitment": Path(args.job_vault).expanduser().resolve(),
    }
    source = Path(args.source_vault).expanduser().resolve()
    if not args.apply:
        report = collect(source, targets)
        print("[DRY-RUN] 未移动任何文件。确认后加 --apply。")
    else:
        for root in targets.values():
            root.mkdir(parents=True, exist_ok=True)
        report = collect(source, targets, apply=True)
        log_dir = targets["news"] / "99-系统" / "迁移日志"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"拆分迁移_{datetime.now():%Y%m%d_%H%M%S}.json"
        log_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[LOG] {log_path}")
    print(
        f"[SUMMARY] planned={report['planned']} moved={report['moved']} "
        f"skipped={report['skipped']} unknown={len(report['unknown'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
