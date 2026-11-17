# -*- coding: utf-8 -*-
"""部署一致性自检（v9 M5）：HEAD / 运行中后端 / 前端构建戳 / 工作区状态 是否同一份代码。

背景（2026-11-17 实测事故）：后端以 nohup 起在 8000 而不带 --reload，改完代码不重启就访问，
接口返回的仍是旧逻辑；前端 dist 未重建，页面里 __BUILD_SHA__ 还是上一版。
两者叠加会出现「代码已改、页面照旧」的假象，排查时极耗时间。本脚本把这些信号一次比完。

退出码：0 全一致；1 有不一致（可用于门禁）。
用法：
    python scripts/ops/verify_deploy.py            # 只比对，不改任何东西
    python scripts/ops/verify_deploy.py --strict   # 工作区 dirty 也算失败
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKEND_URL = os.environ.get("VERIFY_BACKEND_URL", "http://127.0.0.1:8000")


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20,
            encoding="utf-8", errors="replace",
        )
        return (out.stdout or "").strip()
    except Exception:
        return ""


def head() -> dict:
    status = _git("status", "--porcelain")
    return {
        "sha": _git("rev-parse", "--short=8", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(status),
        "dirty_files": len([l for l in status.splitlines() if l.strip()]),
    }


def backend_health() -> dict:
    try:
        with urllib.request.urlopen(BACKEND_URL + "/health", timeout=6) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def frontend_stamp() -> dict:
    """从 dist 里找构建戳；没有 dist 说明前端还没构建（开发态可忽略）。"""
    dist = os.path.join(ROOT, "dist")
    if not os.path.isdir(dist):
        return {"built": False}
    for base, _dirs, files in os.walk(dist):
        for name in files:
            if not name.endswith(".js"):
                continue
            path = os.path.join(base, name)
            try:
                if os.path.getsize(path) > 8 * 1024 * 1024:
                    continue
                text = open(path, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            m = re.search(r'"([0-9a-f]{8})[·\s-]+([0-9a-f]{6,8})"', text)
            if m:
                return {"built": True, "sha": m.group(1), "file": os.path.relpath(path, ROOT)}
    return {"built": True, "sha": ""}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    h, b, f = head(), backend_health(), frontend_stamp()
    rows = [
        ("工作区", "dirty" if h["dirty"] else "clean", "%d 个改动文件" % h["dirty_files"]),
        ("git HEAD", h["sha"], h["branch"]),
        ("后端 /health.revision", b.get("revision") or b.get("error", "?"), "version=%s" % b.get("version")),
        ("前端构建戳", f.get("sha") or ("未构建" if not f.get("built") else "未取到"), f.get("file", "-")),
    ]
    print("== 部署一致性 ==")
    for name, value, extra in rows:
        print("  %-20s %-12s %s" % (name, str(value), extra))

    problems = []
    if b.get("error"):
        problems.append("后端未响应：%s" % b["error"])
    elif b.get("revision") and h["sha"] and h["sha"] not in str(b["revision"]):
        problems.append("后端运行的是 %s，工作区是 %s → 需要重启后端" % (b["revision"], h["sha"]))
    if f.get("built") and f.get("sha") and h["sha"] and f["sha"] != h["sha"]:
        problems.append("前端 dist 构建戳 %s ≠ HEAD %s → 需要重新构建前端" % (f["sha"], h["sha"]))
    if args.strict and h["dirty"]:
        problems.append("工作区有 %d 个未提交改动" % h["dirty_files"])

    if problems:
        print("\n不一致：")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("\n一致：代码、后端、前端构建戳指向同一版本。")


if __name__ == "__main__":
    main()
