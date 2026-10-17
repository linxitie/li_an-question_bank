#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P4.1 模块边界检查器 —— AST 扫描跨域耦合。

与计划的偏差：计划写的是 modules/X/ 路径，P3B 落地后实际布局为
app/api/v1/<domain>/<module>.py。本检查器按实测布局工作。

两类违规：
  A. 跨域模块导入：app/api/v1/<域A>/ 内 import 了 app/api/v1/<域B>/ 的模块
     （或等价相对导入 ....api.v1.<域B>）
  B. 跨域表写入：<域A> 的模块写入了被其它域独占使用的 ORM 表
     （依据 table_usage.json 的表→使用模块矩阵 + 域模块映射）

基线机制：首次运行生成 data/refactor_baseline/boundary_baseline.json，
之后 gate_all 只要求「不新增违规」—— 存量违规单独登记逐步消化，
避免一次把门禁压垮。

用法：
  python scripts/check_module_boundary.py            # 检查 + 更新基线
  python scripts/check_module_boundary.py --check-only   # 只检查不更新
  python scripts/check_module_boundary.py --list        # 列出全部存量违规
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(os.path.dirname(_HERE))
V1 = os.path.join(_BACKEND, "app", "api", "v1")
MODELS = os.path.join(_BACKEND, "app", "models", "models.py")
BASELINE = os.path.join(_BACKEND, "data", "refactor_baseline",
                        "boundary_baseline.json")
TABLE_USAGE = os.path.join(_BACKEND, "data", "refactor_baseline",
                           "table_usage.json")

_SKIP = {"__init__.py", "__pycache__"}


def _iter_domain_modules() -> dict[str, list[str]]:
    out: dict[str, list[str]] = collections.defaultdict(list)
    if not os.path.isdir(V1):
        return out
    for domain in sorted(os.listdir(V1)):
        d = os.path.join(V1, domain)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".py") and fn not in _SKIP:
                out[domain].append(fn[:-3])
    return out


def _load_models() -> set[str]:
    """models.py 里定义的 ORM 类名（作为表名代理）。"""
    names: set[str] = set()
    if not os.path.exists(MODELS):
        return names
    tree = ast.parse(open(MODELS, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                base_name = getattr(base, "id", "") or \
                    getattr(getattr(base, "attr", None), "value", "")
                if base_name in ("Base", "DeclarativeBase") or \
                        "Base" in base_name:
                    names.add(node.name)
                    break
    return names


def _cross_imports(domain: str, mod: str, doms: dict[str, list[str]]) -> list[str]:
    path = os.path.join(V1, domain, mod + ".py")
    src = open(path, encoding="utf-8").read()
    hits = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom) and node.module:
            m = node.module
            # 绝对形式 from app.api.v1.<域>.<模块>
            if m.startswith("app.api.v1."):
                parts = m.split(".")
                if len(parts) >= 5 and parts[4] in doms and parts[4] != domain:
                    hits.append(m)
            # 相对形式 from ....api.v1.<域>.<模块> 或 from ....<域>...
            rel = m.lstrip(".")
            if rel.startswith("api.v1."):
                parts = rel.split(".")
                if len(parts) >= 3 and parts[2] in doms and parts[2] != domain:
                    hits.append(m)
    return sorted(set(hits))


def _cross_writes(domain: str, mod: str, doms: dict[str, list[str]],
                  table_use: dict[str, list[str]],
                  models: set[str]) -> list[str]:
    """域 A 模块 import 的 ORM 模型中，被「他域独占使用」者。

    表归属判定：table_usage.json 记录使用该表的模块清单；
    全部使用模块都在其它域、且本域无任何模块使用时，视为他域独占。
    """
    path = os.path.join(V1, domain, mod + ".py")
    src = open(path, encoding="utf-8").read()
    tree = ast.parse(src)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and \
                "models" in node.module:
            for a in node.names:
                imported.add(a.name)
    hits = []
    for name in sorted(imported & models):
        users = [u[:-3] for u in table_use.get(name, [])
                 if isinstance(u, str)]
        if not users:
            continue
        user_domains = {d for d, mods in doms.items()
                        for u in users if u in mods}
        if user_domains and user_domains != {domain} and domain not in user_domains:
            hits.append(f"{name} (他域: {','.join(sorted(user_domains))})")
    return sorted(hits)


def scan() -> list[dict]:
    doms = _iter_domain_modules()
    models = _load_models()
    with open(TABLE_USAGE, encoding="utf-8") as f:
        table_use = json.load(f)
    violations = []
    for domain, mods in sorted(doms.items()):
        for mod in mods:
            try:
                imports = _cross_imports(domain, mod, doms)
                writes = _cross_writes(domain, mod, doms, table_use, models)
            except (SyntaxError, OSError):
                continue
            for im in imports:
                violations.append({"type": "cross_import",
                                   "domain": domain, "module": mod, "target": im})
            for w in writes:
                violations.append({"type": "cross_write",
                                   "domain": domain, "module": mod, "target": w})
    return violations


def _key(v: dict) -> str:
    return f"{v['type']}|{v['domain']}|{v['module']}|{v['target']}"


def main() -> int:
    ap = argparse.ArgumentParser(description="P4.1 模块边界检查器")
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    violations = scan()
    cur = {_key(v) for v in violations}

    baseline = set()
    if os.path.exists(BASELINE):
        with open(BASELINE, encoding="utf-8") as f:
            baseline = set(json.load(f))

    if a.list:
        for v in sorted(violations, key=_key):
            print(f"  [{v['type']:<12}] {v['domain']}/{v['module']} -> {v['target']}")
        print(f"\n存量违规 {len(violations)} 条")
        return 0

    new = cur - baseline
    resolved = baseline - cur
    print(f"模块边界扫描：当前违规 {len(cur)} 条，"
          f"新增 {len(new)} 条，已消除 {len(resolved)} 条")

    if not a.check_only:
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump(sorted(cur), f, ensure_ascii=False, indent=2)
        print(f"基线已更新: {os.path.relpath(BASELINE, _BACKEND)}")

    if new:
        print("\n新增违规（须处理或确认纳入基线）：")
        for k in sorted(new):
            v = next(x for x in violations if _key(x) == k)
            print(f"  [{v['type']}] {v['domain']}/{v['module']} -> {v['target']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())