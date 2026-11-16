"""提交前密钥扫描：确保 API Key / 令牌不会被 git 跟踪。

为什么需要：
本项目 `backend/.env` 是被 `.gitignore` 忽略的，但历史上仍发生过密钥写进文档的事故。
人工"记得不要提交"不可靠，这里用 git 的已跟踪文件清单做一次确定性扫描。

用法：
    python backend/scripts/check_no_secrets.py          # 扫描已跟踪文件
    python backend/scripts/check_no_secrets.py --all    # 额外扫描未跟踪但未被忽略的文件

退出码：0 = 干净，1 = 发现问题（可直接用于 CI / 门禁）。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# 只匹配"看起来像真密钥"的形态，避免把示例值（<your-key>、sk-xxx）误报
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenAI/DeepSeek 风格密钥", re.compile(r"sk-[A-Za-z0-9]{24,}")),
    ("GitHub Token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("Google API Key", re.compile(r"AIza[0-9A-Za-z_-]{30,}")),
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
]

# 允许出现的占位符样式（文档示例）
PLACEHOLDER_HINTS = ("<", "your", "xxx", "***", "example", "placeholder", "sk-xxx")

# 二进制/大文件跳过，避免拖慢
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".7z", ".rar",
    ".xlsx", ".docx", ".pptx", ".sqlite", ".db", ".pyc", ".woff", ".woff2", ".ttf",
}
MAX_SIZE = 2 * 1024 * 1024


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    ).stdout


def collect_files(include_untracked: bool) -> list[Path]:
    args = ["ls-files"]
    if include_untracked:
        args = ["ls-files", "--cached", "--others", "--exclude-standard"]
    root = Path(_git("rev-parse", "--show-toplevel").strip() or ".").resolve()
    files: list[Path] = []
    for rel in _git(*args).splitlines():
        rel = rel.strip()
        if not rel:
            continue
        p = root / rel
        if not p.is_file():
            continue
        if p.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            if p.stat().st_size > MAX_SIZE:
                continue
        except OSError:
            continue
        files.append(p)
    return files


def scan(files: list[Path]) -> list[str]:
    findings: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            if any(hint in lowered for hint in PLACEHOLDER_HINTS):
                continue
            for label, pattern in PATTERNS:
                if pattern.search(line):
                    findings.append(f"{path}:{lineno}: 命中「{label}」")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="扫描 git 跟踪文件中的疑似密钥")
    parser.add_argument("--all", action="store_true", help="同时扫描未跟踪且未被忽略的文件")
    args = parser.parse_args()

    files = collect_files(include_untracked=args.all)
    findings = scan(files)

    print(f"扫描文件数: {len(files)}")
    if findings:
        print("发现疑似密钥（请改为从环境变量读取，并轮换已泄露的密钥）:")
        for item in findings:
            print("  -", item)
        return 1

    print("未发现疑似密钥 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
