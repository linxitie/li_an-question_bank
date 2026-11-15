#!/usr/bin/env python3
"""清理新闻 Vault 中的非新闻残留文件。

新闻 Vault 只保留：
- 02-新闻/index.md
- 00-收件箱/新闻/*
- 04-归档/news_*.md
- 00-系统总览看板.md

金句相关文档移到金句 Vault，招考索引移到招考 Vault。
默认 dry-run；确认后加 --apply。
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from scripts.obsidian_organizer import unique_target


def target_for(relative: Path, quote_root: Path, job_root: Path) -> Path | None:
    parts = relative.parts
    if not parts:
        return None
    top = parts[0]
    if top in {"04-主题地图"}:
        return quote_root / relative
    if top in {"00-收件箱", "01-金句"} and (
        "审核看板" in parts or "金句" in parts
    ):
        return quote_root / "04-归档" / "迁移自新闻库" / relative
    if top in {"03-招考"}:
        return job_root / "99-系统" / "迁移自新闻库" / relative
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--news-vault", default=settings.VAULT_PATH_NEWS)
    parser.add_argument("--quote-vault", default=settings.VAULT_PATH_QUOTE)
    parser.add_argument("--job-vault", default=settings.VAULT_PATH_JOB)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    news = Path(args.news_vault).expanduser().resolve()
    quote = Path(args.quote_vault).expanduser().resolve()
    job = Path(args.job_vault).expanduser().resolve()
    for root in (news, quote, job):
        if not root.is_dir():
            raise SystemExit(f"Vault 不存在: {root}")

    moved = 0
    skipped = 0
    for path in sorted(news.rglob("*.md")):
        relative = path.relative_to(news)
        target = target_for(relative, quote, job)
        if target is None or target.resolve() == path.resolve():
            skipped += 1
            continue
        target = unique_target(target)
        print(
            f"[{'MOVE' if args.apply else 'DRY-RUN'}] "
            f"{relative} -> {target}"
        )
        if args.apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
            moved += 1

    if args.apply:
        # 清理空目录，但保留新闻 Vault 的顶层结构
        for directory in sorted(news.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if directory.is_dir() and directory.name not in {".obsidian", "uploads"}:
                try:
                    directory.rmdir()
                except OSError:
                    pass
        log_dir = news / "99-系统" / "迁移日志"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"新闻库清理_{datetime.now():%Y%m%d_%H%M%S}.log").write_text(
            f"moved={moved} skipped={skipped}\n", encoding="utf-8"
        )
    print(f"[SUMMARY] moved={moved} skipped={skipped} apply={args.apply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
