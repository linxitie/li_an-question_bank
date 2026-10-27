#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""QBDM CLI — 题库设计模式命令行（只读）。

用法：qbdm.py module <关键字> | qbdm.py gate --role BE|FE|API|DATA|SEC|QA|PM
约束：纯标准库零依赖；只读（不写文件/不跑门禁/不连库/不联网）；
      输出带数据源时间与 git HEAD；找不到模块时退出码 1 并列出候选。
详见 docs/plans/题库设计模式_QBDM命令行工具_设计方案_v1.md
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:  # Windows 控制台 GBK 下打印中文/框线不崩
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
API_SURFACE = ROOT / "backend/data/refactor_baseline/api_surface.json"
PROJECTS_DIR = ROOT / ".vtj/projects"
ROUTER = ROOT / "src/router/index.ts"
BACKEND_TESTS = ROOT / "backend/tests"
SRC = ROOT / "src"
GATES = ROOT / "backend/scripts/gates"

ALIASES = {
    "论坛": ["forum"],
    "教师": ["teacher"],
    "管理": ["admin"],
    "错题": ["wrong"],
    "组卷": ["paper", "exam"],
    "试题": ["question"],
    "练习": ["practice"],
    "成就": ["achievement"],
    "金币": ["coin"],
    "素材": ["material"],
}

# (脚本名, 用途)。描述保持短，一行放下即可。
ROLE_GATES = {
    "BE": [("gate_l4_api_contract.py", "端点契约(343条基准)"),
           ("check_module_boundary.py", "跨域 import"),
           ("gate_l1g_field_fingerprint.py", "字段指纹(改模型时)")],
    "FE": [("gate_l5_frontend_contract.py", "前端契约(改 .vtj 页时)")],
    "API": [("gate_l4_api_contract.py", "端点契约(343条基准)")],
    "DATA": [("gate_l1g_field_fingerprint.py", "字段指纹"),
             ("gate_l2_matching.py", "题干/答案匹配"),
             ("gate_l3_ingest.py", "入库")],
    "SEC": [("check_secrets.py", "疑似凭据扫描"),
            ("gate_l0_redlines.py", "红线检查")],
    "QA": [("gate_all.py", "全量编排(加 --quick)"),
           ("check_module_boundary.py", "跨域 import")],
    "PM": [("gate_all.py", "全量编排(加 --quick)")],
}


# ---------------------------------------------------------------- 数据源
def mtime_date(p: Path) -> str:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
    except OSError:
        return "n/a"


def git_head() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or "n/a"
    except Exception:
        return "n/a"


def load_api() -> dict:
    try:
        return json.loads(API_SURFACE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_pages() -> dict:
    """返回 {page_id: {"raw": bool, "name": str}}，取第一个可读的项目配置。"""
    for jf in sorted(PROJECTS_DIR.glob("*.json")):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue
        pages = {}
        for p in data.get("pages") or []:
            pid = p.get("id")
            if pid:
                pages[pid] = {"raw": p.get("raw") is True, "name": p.get("name") or pid}
        if pages:
            return pages
    return {}


def load_routes() -> dict:
    """从 src/router/index.ts 粗略解析 {组件文件名: 路由 path}。"""
    routes = {}
    try:
        text = ROUTER.read_text(encoding="utf-8")
    except Exception:
        return routes
    current = None
    for line in text.splitlines():
        m = re.search(r"path:\s*'([^']+)'", line)
        if m:
            current = m.group(1)
            continue
        m = re.search(r"import\('(?:\$vtj/vue|@/views)/([^']+)'\)", line)
        if m and current:
            routes.setdefault(Path(m.group(1)).name, current)
    return routes


def collect_files(pattern: str, base: Path):
    return sorted(p for p in base.rglob(pattern) if p.is_file())


# ---------------------------------------------------------------- 匹配
def expand_keyword(kw: str):
    words = [kw.strip()]
    for alias, targets in ALIASES.items():
        if alias in kw:
            words.extend(targets)
    return [w.lower() for w in words if w]


def match_modules(api: dict, kw: str):
    words = expand_keyword(kw)
    hits = {}
    for fname, info in api.items():
        blob = (fname + " " + (info.get("prefix") or "")).lower()
        if any(w in blob for w in words):
            hits[fname] = info
    return hits


def related_pages(pages: dict, words):
    out = []
    for pid, meta in pages.items():
        if any(w in pid.lower() or w in (meta["name"] or "").lower() for w in words):
            out.append((pid, meta))
    return sorted(out)


def related_files(words, base: Path, pattern: str, limit=40):
    out = []
    for p in collect_files(pattern, base):
        if any(w in p.name.lower() for w in words):
            out.append(p)
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------- 输出
def box(title: str, lines):
    width = max([len(title)] + [len(s) for s in lines]) + 2
    print("┌─ " + title + " " + "─" * max(2, width - len(title) - 3))
    for s in lines:
        print("│ " + s)
    print("└" + "─" * (width + 1))


def warn(marker: str, text: str):
    print(f"  {marker} {text}")


def cmd_module(kw: str) -> int:
    api = load_api()
    pages = load_pages()
    routes = load_routes()
    words = expand_keyword(kw)
    mods = match_modules(api, kw)

    box(f"模块 {kw}", [
        f"数据源：api_surface.json（{mtime_date(API_SURFACE)}）｜"
        f".vtj/projects（{len(pages)} 页）｜git {git_head()}",
    ])
    print()

    if not mods and not related_pages(pages, words):
        print(f"[!] 没有匹配到任何模块或页面：{kw}")
        print("    候选模块（前 20）：")
        for name in sorted(api)[:20]:
            print("      - " + name)
        return 1

    total = 0
    for fname, info in mods.items():
        prefix = info.get("prefix") or ""
        eps = info.get("endpoints") or []
        total += len(eps)
        print(f"端点 {len(eps)} 条（前缀 {prefix}，来源 {fname}）")
        for ep in eps:
            method = str(ep.get("method") or "").ljust(6)
            path = prefix + (ep.get("path") or "")
            print(f"  {method} {path:<44} {ep.get('fn')}  L{ep.get('line')}")
        print()

    page_hits = related_pages(pages, words)
    vtj_hits = [(pid, meta) for pid, meta in page_hits if (ROOT / f".vtj/vue/{pid}.vue").exists()]
    sfc_hits = [(pid, meta) for pid, meta in page_hits if not (ROOT / f".vtj/vue/{pid}.vue").exists()]
    handwritten = related_files(words, SRC, "*.vue")

    if vtj_hits or handwritten:
        raw_n = len([1 for _, m in vtj_hits if m["raw"]])
        print(f"页面/组件 {len(vtj_hits) + len(handwritten)} 个（{raw_n} 个 raw）")
        for pid, meta in vtj_hits:
            tag = "raw " if meta["raw"] else "    "
            rel = f".vtj/vue/{pid}.vue"
            route = routes.get(f"{pid}.vue", "")
            print(f"  {tag} {rel:<48} {route}")
        for p in handwritten:
            rel = p.relative_to(ROOT).as_posix()
            print(f"  SFC  {rel}")
        print()

    tests = [p for p in related_files(words, BACKEND_TESTS, "*.py") if p.name.startswith("test_")]
    specs = related_files(words, SRC, "*.spec.ts")
    if tests or specs:
        print(f"测试 {len(tests) + len(specs)} 个")
        for p in tests:
            print(f"  backend/tests/{p.name}")
        for p in specs:
            print(f"  {p.relative_to(ROOT).as_posix()}")
        print()

    if mods:
        print("改这个模块要跑的门禁")
        for script, desc in ROLE_GATES["BE"] + ROLE_GATES["FE"]:
            print(f"  python backend/scripts/gates/{script:<34} ← {desc}")
        if tests:
            print(f"  cd backend; python -m pytest tests -q -k {words[0]}")
        print()

    raw_count = len([1 for _, m in vtj_hits if m["raw"]])
    if raw_count:
        print(f"红线提醒（自动生成）")
        print(f"  · {raw_count} 个 .vtj 页 raw=true → 禁 vtj_sync_vue_to_dsl（R2）")
        print(f"  · 改 .vtj 的 <template> 需用户逐次授权 + .bak_<日期> 备份（R3）")
    if mods and any((info.get("prefix") or "").startswith("/api/") for info in mods.values()):
        print(f"  · 新增接口必须挂在与既有前缀一致的位置，不得新开 /api/v1（R11）")
    return 0


def cmd_gate(role: str) -> int:
    role = role.upper()
    if role not in ROLE_GATES:
        print(f"[!] 未知角色 {role}；可选：{', '.join(ROLE_GATES)}")
        return 1
    box(f"角色 {role} 必跑门禁", [f"数据源：backend/scripts/gates（{mtime_date(GATES)}）"])
    print()
    for script, desc in ROLE_GATES[role]:
        exists = (GATES / script).exists()
        flag = "" if exists else "  [!] 脚本不存在"
        print(f"  python backend/scripts/gates/{script:<34} ← {desc}{flag}")
    return 0


def main(argv) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == "module":
        if len(argv) < 3:
            print("[!] 用法：qbdm.py module <关键字>")
            return 1
        return cmd_module(argv[2])
    if cmd == "gate":
        role = "BE"
        if "--role" in argv:
            idx = argv.index("--role")
            if idx + 1 < len(argv):
                role = argv[idx + 1]
        return cmd_gate(role)
    print(f"[!] 未知子命令：{cmd}")
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
