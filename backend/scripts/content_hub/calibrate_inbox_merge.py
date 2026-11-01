#!/usr/bin/env python3
"""按人工规则校准退回修改合并清单，生成新文件（不覆盖原文件）。"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = BACKEND_ROOT / "content_hub_vault" / "00-收件箱" / "金句" / "退回修改合并清单_144.md"
DEFAULT_OUTPUT = DEFAULT_INPUT.with_name("退回修改合并清单_144_已校准版.md")

_SECTION_RE = re.compile(r"(?ms)^### (\d+)\. ([^\n]+)\n(.*?)(?=^### |\Z)")


def _parse(text: str):
    matches = list(_SECTION_RE.finditer(text))
    header = text[: matches[0].start()]
    entries: list[dict[str, Any]] = []
    for match in matches:
        num, title, body = match.groups()
        source = re.search(r"^- 来源：(.+)$", body, re.M)
        author = re.search(r"^- 作者：(.+)$", body, re.M)
        entries.append({
            "num": int(num),
            "title": title,
            "body": body,
            "source": source.group(1) if source else "",
            "author": author.group(1) if author else "",
        })
    return header, entries


def _set_author(body: str, author: str) -> str:
    if re.search(r"^- 作者：.*$", body, re.M):
        return re.sub(r"^- 作者：.*$", f"- 作者：{author}", body, count=1, flags=re.M)
    source_line = re.search(r"^- 来源：.*$", body, re.M)
    if source_line:
        return body.replace(source_line.group(0), source_line.group(0) + f"\n- 作者：{author}", 1)
    return body


def _mark(body: str, note: str) -> str:
    body = re.sub(r"^- \[[ xX]\] 已修改$", "- [x] 已修改", body, count=1, flags=re.M)
    if re.search(r"^- 修改备注：.*$", body, re.M):
        body = re.sub(r"^- 修改备注：.*$", f"- 修改备注：{note}", body, count=1, flags=re.M)
    else:
        body = body.rstrip() + f"\n- 修改备注：{note}\n"
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description="校准退回修改合并清单")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    header, entries = _parse(text)
    counts = {"古籍佚名": 0, "官方文献": 0, "诗词名家": 0, "诸子百家": 0}
    changed = 0

    for entry in entries:
        num = entry["num"]
        source = entry["source"]
        author = entry["author"]
        note = ""
        new_author = None

        # 例外：明确标注习近平引用的，作者应为习近平，而不是佚名
        if "习近平" in source and (not author or author == "（缺失）"):
            new_author = "习近平"
            note = "官方文献，出处明确"
            counts["官方文献"] += 1
        elif 1 <= num <= 41 and (not author or author == "（缺失）") and (
            "传统" in source or "官箴" in source or "增广贤文" in source
        ):
            new_author = "佚名"
            note = "已补佚名"
            counts["古籍佚名"] += 1
        elif 44 <= num <= 52 or 61 <= num <= 101:
            if "宪法" in source or "民法典" in source:
                new_author = "全国人大"
                note = "官方文献，出处明确"
                counts["官方文献"] += 1
            elif "政府工作报告" in source:
                new_author = "国务院"
                note = "官方文献，出处明确"
                counts["官方文献"] += 1
            elif "权威官方文件" in source:
                new_author = "国务院"
                note = "官方文献，出处明确"
                counts["官方文献"] += 1
        elif (53 <= num <= 60 or 102 <= num <= 133) and author and author != "（缺失）":
            note = "经典诗词，已补作者信息"
            counts["诗词名家"] += 1
        elif 134 <= num <= 144:
            if "吕氏春秋" in source:
                new_author = "吕不韦"
                note = "古籍经典"
                counts["诸子百家"] += 1
            elif "淮南子" in source:
                new_author = "刘安"
                note = "古籍经典"
                counts["诸子百家"] += 1

        if note:
            body = entry["body"]
            if new_author:
                body = _set_author(body, new_author)
            entry["body"] = _mark(body, note)
            changed += 1

    header = header.replace("# 退回修改金句合并清单", "# 退回修改金句合并清单（已校准版）", 1)
    header = header.replace(
        "> 每条补作者/出处或修改内容后，勾选“已修改”；单条原笔记仍保留。",
        "> 每条补作者/出处或修改内容后，勾选“已修改”；单条原笔记仍保留。\n"
        "> **已校准版**：按人工规则补全作者/机构并勾选，共校准 "
        f"{changed} 条。",
    )
    header = header.rstrip() + (
        "\n\n## 校准统计\n\n| 类型 | 数量 |\n|---|---:|\n"
        f"| 古籍补佚名 | {counts['古籍佚名']} |\n"
        f"| 官方文献 | {counts['官方文献']} |\n"
        f"| 诗词名家 | {counts['诗词名家']} |\n"
        f"| 诸子百家 | {counts['诸子百家']} |\n"
        f"| **合计** | **{changed}** |\n"
        "\n---\n\n"
    )

    parts = [header]
    for entry in entries:
        parts.append(f"### {entry['num']}. {entry['title']}\n{entry['body']}")
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(parts), encoding="utf-8")
    print(json.dumps({
        "ok": True,
        "path": str(output),
        "total": len(entries),
        "changed": changed,
        "counts": counts,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
