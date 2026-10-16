#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P3B 域迁移工具：把 app/api/v1/ 下的模块移入对应域子目录。

固化 P3B.0 踩坑得出的规则 —— 每迁一域必须同时处理三类引用：
  ① 绝对路径      app.api.v1.<mod>
  ② 同目录相对    from .<mod> import
  ③ patch 字符串  patch("app.api.v1.<mod>....")

用法：python scripts/migrate_domain.py <domain> <mod> [<mod> ...]
只做搬迁与引用改写，不改任何业务逻辑；改完须跑 pytest 与 gate_all 验收。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V1 = os.path.join(BACKEND, "app", "api", "v1")
ROOTS = ["app", "tests", "scripts"]


def run(*args: str) -> str:
    return subprocess.run(args, cwd=BACKEND, capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout


def read(p: str) -> str:
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p: str, s: str) -> None:
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def iter_py(sub: str):
    for root, _dirs, files in os.walk(os.path.join(BACKEND, sub)):
        if "__pycache__" in root or "node_modules" in root:
            continue
        for fn in files:
            if fn.endswith(".py"):
                yield os.path.join(root, fn)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    domain, mods = sys.argv[1], sys.argv[2:]
    dest = os.path.join(V1, domain)
    os.makedirs(dest, exist_ok=True)
    init = os.path.join(dest, "__init__.py")
    if not os.path.exists(init):
        write(init, "")

    # ── 1. 搬迁 ────────────────────────────────────────────
    for m in mods:
        src = os.path.join(V1, f"{m}.py")
        if not os.path.exists(src):
            print(f"  [跳过] {m}.py 不存在")
            continue
        run("git", "mv", os.path.relpath(src, BACKEND),
            os.path.relpath(os.path.join(dest, f"{m}.py"), BACKEND))
        p = os.path.join(dest, f"{m}.py")
        t = read(p)
        n = len(re.findall(r"(?m)^\s*from\s+\.\.\.", t))
        t = re.sub(r"(?m)^(\s*from\s+)\.\.\.", r"\1....", t)
        write(p, t)
        print(f"  [迁移] {m}.py → {domain}/  3点式改4点式 {n} 处")

    # ── 2. 三类引用改写 ────────────────────────────────────
    moved = set(mods)
    pat_abs = re.compile(r"\bapp\.api\.v1\.(" + "|".join(moved) + r")\b")
    pat_sib = re.compile(r"(?m)^(\s*from\s+)\.(" + "|".join(moved) + r")\b")
    pat_from = re.compile(
        r"(?m)^(\s*from\s+\.api\.v1\s+import\s+)([^\n]+)$")

    hits = {"abs": 0, "sib": 0, "from": 0}
    for sub in ROOTS:
        for path in iter_py(sub):
            rel = os.path.relpath(path, BACKEND)
            if rel.replace("\\", "/").endswith(
                    tuple(f"api/v1/{domain}/{m}.py" for m in mods)):
                continue
            orig = read(path)
            t = pat_abs.sub(lambda m: f"app.api.v1.{domain}.{m.group(1)}", orig)
            t = pat_sib.sub(lambda m: f"{m.group(1)}.{domain}.{m.group(2)}", t)

            def _from(mo):
                names = [n.strip() for n in mo.group(2).split(",")]
                hit = [n for n in names if n in moved]
                if not hit:
                    return mo.group(0)
                rest = [n for n in names if n not in moved]
                lines = [f"{mo.group(1)}{', '.join(rest)}"] if rest else []
                lines.append(
                    f"from .api.v1.{domain} import {', '.join(hit)}")
                return "\n".join(lines)

            t = pat_from.sub(_from, t)
            if t != orig:
                n_abs = len(pat_abs.findall(orig))
                n_sib = len(pat_sib.findall(orig))
                n_frm = len(pat_from.findall(orig))
                hits["abs"] += n_abs
                hits["sib"] += n_sib
                hits["from"] += n_frm
                write(path, t)
                print(f"  [引用] {rel}  绝对{n_abs} 同目录{n_sib} from-import{n_frm}")
    print(f"  合计：绝对 {hits['abs']} · 同目录 {hits['sib']} · from-import {hits['from']}")

    # ── 3. 残留检查 ────────────────────────────────────────
    left = []
    for sub in ROOTS:
        for path in iter_py(sub):
            t = read(path)
            rel = os.path.relpath(path, BACKEND)
            if rel.replace("\\", "/").endswith(
                    tuple(f"api/v1/{domain}/{m}.py" for m in mods)):
                continue
            for m in mods:
                if re.search(rf"\bapp\.api\.v1\.{m}\b", t):
                    left.append(f"{rel}: 绝对路径 app.api.v1.{m}")
                if re.search(rf"(?m)^\s*from\s+\.{m}\s+import", t):
                    left.append(f"{rel}: 同目录 from .{m}")
    if left:
        print("  [残留] 迁移后仍有未改写引用：")
        for x in left:
            print("    - " + x)
        return 1
    print("  [残留] 无 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())