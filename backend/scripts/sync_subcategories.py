#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""同步缺失的子科目「科学推理」到 seed.py SUB_CATEGORIES

D-1 任务（v3 方案 4.2 节）：把 seed 缺失的 id=16「科学推理」补进 seed
定义，保证 seed 幂等重跑与 DB 一致。

DB 现状：sub_categories 已有 id=16 科学推理（subject_id=1，运行时由
导入侧创建），但 seed.py 的 SUB_CATEGORIES 缺失该条目 → 全新库 seed
后三级分类断裂。

策略：仅增不改（只追加一条代码行，不重写列表、不动其余条目）。

用法：
    python scripts/sync_subcategories.py             # 默认 dry-run，仅预览
    python scripts/sync_subcategories.py --apply     # 实际写入 seed.py
"""
from __future__ import annotations

import argparse
import os
import re
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED_PATH = os.path.join(BACKEND_DIR, "app", "seed.py")


def _read_seed_sub_categories(path: str) -> list[tuple]:
    """Extract SUB_CATEGORIES list from seed.py as a list of tuples."""
    # newline="" 关闭通用换行转换：读到的 \r\n 原样保留，写回时才不会
    # 被 Windows 默认转成 CRLF 而把整个文件「改写」（曾导致全文件 diff）。
    with open(path, encoding="utf-8", newline="") as f:
        content = f.read()

    # Find the SUB_CATEGORIES = [ ... ] block
    m = re.search(
        r"SUB_CATEGORIES\s*=\s*\[(.*?)\]",
        content,
        re.DOTALL | re.MULTILINE,
    )
    if not m:
        print("[error] 无法在 seed.py 中找到 SUB_CATEGORIES 定义")
        return []

    block = m.group(1)
    # Parse tuples (subject_id, name, description, sort_order)
    tuples = []
    # Match lines like: (1, "政治理论", "习近平新时代...", 1),
    for line_match in re.finditer(
        r"\s*\(\s*(\d+)\s*,\s*\"([^\"]+)\"\s*,\s*\"([^\"]+)\"\s*,\s*(\d+)\s*\)",
        block,
    ):
        subj_id = int(line_match.group(1))
        name = line_match.group(2)
        desc = line_match.group(3)
        order = int(line_match.group(4))
        tuples.append((subj_id, name, desc, order))

    return tuples


def _read_bytes(path: str) -> tuple:
    """读文件，(文本, 主换行符)。

    newline="" 关闭 Windows 的文本模式换行转译，保证
    LF 文件读进来仍是 LF、写回去仍是 LF（不会被悄悄转成 CRLF，
    导致一次单行插入在 git diff 里显示成整文件 471 行重写）。
    """
    with open(path, "r", encoding="utf-8", newline="") as f:
        content = f.read()
    if "\r\n" in content:
        nl = "\r\n"
    elif "\r" in content:
        nl = "\r"
    else:
        nl = "\n"
    return content, nl


def _write_bytes(path: str, content: str) -> None:
    """写文件，newline="" 保证字节级原样输出，不做换行转译。"""
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)


def _append_tuple_line(path: str, entry: tuple) -> bool:
    """在 SUB_CATEGORIES 列表的右括号前插入新条目的代码行。

    只做「单行插入」，不重写整个列表，原有格式 100% 保留
    （含原文件的换行风格与缩进）。
    返回 True 表示已插入，False 表示未找到插入点。
    """
    content, nl = _read_bytes(path)

    # 定位 SUB_CATEGORIES = [ ... ] 的结束右括号。
    # 用「SUB_CATEGORIES」关键字后的第一个 ] 作为列表边界（列表内无嵌套括号）。
    m = re.search(r"SUB_CATEGORIES\s*=\s*\[", content)
    if not m:
        print("[error] 无法定位 seed.py 中的 SUB_CATEGORIES 起点")
        return False
    start = m.end()
    end = content.find("]", start)
    if end == -1:
        print("[error] 无法定位 SUB_CATEGORIES 列表的结束括号")
        return False

    subj_id, name, desc, order = entry
    line = '    (%d, "%s", "%s", %d)' % (subj_id, name, desc, order)

    # 保留原列表其余部分，仅把新条目插到最后一条之前。
    # 原列表末行形如 "    (3, \"xxx\", ...)," 后跟 "]"，插入后需保证
    # "]" 回到顶格，故按原文件缩进风格重建尾部。
    head = content[:end]        # 到 ] 之前（含前面各行与换行）
    tail = content[end:]        # 从 ] 开始

    # head 末行若有缩进，沿用其缩进写新行；否则用 4 空格
    stripped = head.rstrip("\r\n")
    last_nl = max(stripped.rfind("\n"), stripped.rfind("\r"))
    prev_line = stripped[last_nl + 1:]
    indent = prev_line[:len(prev_line) - len(prev_line.lstrip())] or "    "

    new_content = stripped + nl + indent + line + "," + nl + tail.lstrip()

    _write_bytes(path, new_content)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="同步科学推理子科目到 seed.py")
    ap.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="实际写入 seed.py（默认 dry-run，仅预览）",
    )
    args = ap.parse_args()

    tuples = _read_seed_sub_categories(SEED_PATH)
    if tuples is None:
        return 1

    # Check if 科学推理 already exists (subject_id=1, name="科学推理")
    exists = any(
        t[0] == 1 and t[1] == "科学推理" for t in tuples
    )

    if exists:
        print("[ok] 科学推理 已存在于 seed.py SUB_CATEGORIES 中，无需添加")
        return 0

    # 追加「科学推理」到 SUB_CATEGORIES 末尾（subject_id=1，行测）
    entry = (1, "科学推理", "物理/化学/生物等科学推理（部分省份替代数量关系）", 8)
    new_tuples = tuples + [entry]

    if args.apply:
        # 幂等校验：再读一次，避免并发/重复执行导致写两次
        if any(t[0] == 1 and t[1] == "科学推理" for t in _read_seed_sub_categories(SEED_PATH)):
            print("[ok] 科学推理 已存在（并发安全校验），未重复写入")
            return 0
        if not _append_tuple_line(SEED_PATH, entry):
            return 1
        # 写后校验：必须可解析出 16 条且含科学推理
        after = _read_seed_sub_categories(SEED_PATH)
        ok = len(after) == len(tuples) + 1 and after[-1] == entry
        print("[done] 已将 科学推理 添加到 seed.py SUB_CATEGORIES 末尾" if ok
              else "[fail] 写入后校验失败")
        print("  位置: 索引 %d（subject_id=1，sort_order=8），总条目 %d → %d"
              % (len(after) - 1, len(tuples), len(after)))
        return 0 if ok else 1
    else:
        # dry-run：展示将为加入的条目
        print("[dry-run] 将为 seed.py SUB_CATEGORIES 末尾追加：")
        print('    (%d, "%s", "%s", %d)' % entry)
        print()
        print("  当前 SUB_CATEGORIES 共 %d 条，追加后将变为 %d 条" % (len(tuples), len(new_tuples)))
        print("  使用 --apply 确认后实际写入 seed.py")
        return 0


if __name__ == "__main__":
    sys.exit(main())