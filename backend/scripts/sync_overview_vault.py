#!/usr/bin/env python3
"""把三个独立内容 Vault 镜像到系统总览 Vault。

总览 Vault 只读镜像，源 Vault 仍是唯一真源。
默认 dry-run；确认后加 --apply。
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from app.core.config import settings
from scripts.obsidian_organizer import (
    STATUS_DIRS,
    infer_status,
    normalize_type,
    read_frontmatter,
)

OVERVIEW = Path(r"D:\砺安题库\li_an-question_bank\系统总览知识库")
MODULES = {
    "quote": ("01-每日金句", Path(settings.VAULT_PATH_QUOTE)),
    "news": ("02-每日新闻", Path(settings.VAULT_PATH_NEWS)),
    "recruitment": ("03-招考信息", Path(settings.VAULT_PATH_JOB)),
}
TITLES = {"01-每日金句": "每日金句", "02-每日新闻": "每日新闻", "03-招考信息": "招考信息"}


def ensure_overview() -> None:
    (OVERVIEW / "00-Dashboard").mkdir(parents=True, exist_ok=True)
    (OVERVIEW / "99-系统").mkdir(parents=True, exist_ok=True)
    dashboard = OVERVIEW / "00-Dashboard" / "Dashboard.md"
    if not dashboard.exists():
        dashboard.write_text(
            "# 系统总览知识库\n\n"
            "> 本库是每日金句、每日新闻、招考信息的只读镜像，用于 Pulsewright 总览。\n"
            "> 源库仍是唯一真源；更新后运行 `python -m scripts.sync_overview_vault --apply`。\n\n"
            "## 三部分\n\n"
            "- [[01-每日金句/index|每日金句]]\n"
            "- [[02-每日新闻/index|每日新闻]]\n"
            "- [[03-招考信息/index|招考信息]]\n",
            encoding="utf-8",
        )
    for module, title in TITLES.items():
        root = OVERVIEW / module
        (root / "index.md").parent.mkdir(parents=True, exist_ok=True)
        index = root / "index.md"
        if not index.exists():
            index.write_text(
                f"# {title}\n\n"
                "> 本目录由同步脚本维护，请勿手工修改。\n"
                "> 返回 [[../00-Dashboard/Dashboard|系统总览]]\n",
                encoding="utf-8",
            )
        for status in STATUS_DIRS.values():
            (root / status).mkdir(parents=True, exist_ok=True)
            idx = root / status / "index.md"
            if not idx.exists():
                idx.write_text(
                    f"# {title} · {status}\n\n"
                    "> 自动镜像目录。\n",
                    encoding="utf-8",
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    ensure_overview()
    copied = 0
    skipped = 0
    for kind, (module, source) in MODULES.items():
        if not source.is_dir():
            print(f"[SKIP] 源 Vault 不存在: {source}")
            continue
        for path in source.rglob("*.md"):
            if any(part in {".obsidian", ".trash", "uploads", "node_modules"} for part in path.parts):
                continue
            if path.name.lower() in {"index.md", "dashboard.md", "readme.md"}:
                continue
            meta, _ = read_frontmatter(path)
            if normalize_type(meta.get("type")) != kind:
                continue
            status = infer_status(meta, path, source)
            relative = path.relative_to(source)
            parts = list(relative.parts)
            if parts and parts[0] == STATUS_DIRS[status]:
                parts = parts[1:]
            target = OVERVIEW / module / STATUS_DIRS[status] / Path(*parts)
            if target.exists() and target.stat().st_size == path.stat().st_size:
                skipped += 1
                continue
            print(f"[{'COPY' if args.apply else 'DRY-RUN'}] {path} -> {target}")
            if args.apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
            copied += 1
    print(f"[SUMMARY] copied={copied} skipped={skipped} apply={args.apply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
