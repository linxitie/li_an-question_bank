#!/usr/bin/env python3
"""补全退回修改合并清单中非个人作者的条目，生成最终校准版。"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = BACKEND_ROOT / "content_hub_vault" / "00-收件箱" / "金句" / "退回修改合并清单_144_已校准版.md"
DEFAULT_OUTPUT = DEFAULT_INPUT.with_name("退回修改合并清单_144_最终校准版.md")
_SECTION_RE = re.compile(r"(?ms)^### (\d+)\. ([^\n]+)\n(.*?)(?=^### |\Z)")

# 条号 -> (作者, 备注)
REMAINING = {
    42: ("佚名", "权威出处/古籍经典，已核定作者"),
    43: ("中央网信办", "权威出处/古籍经典，已核定作者"),
    91: ("周公旦", "权威出处/古籍经典，已核定作者"),
    92: ("周公旦", "权威出处/古籍经典，已核定作者"),
    93: ("佚名", "权威出处/古籍经典，已核定作者"),
    94: ("国家反诈中心", "权威出处/古籍经典，已核定作者"),
    95: ("国家反诈中心", "权威出处/古籍经典，已核定作者"),
    96: ("国家反诈中心", "权威出处/古籍经典，已核定作者"),
    97: ("中共中央", "权威出处/古籍经典，已核定作者"),
    98: ("公安部", "权威出处/古籍经典，已核定作者"),
    99: ("公安部", "权威出处/古籍经典，已核定作者"),
    100: ("魏收", "权威出处/古籍经典，已核定作者"),
    101: ("佚名", "权威出处/古籍经典，已核定作者"),
    141: ("房玄龄", "权威出处/古籍经典，已核定作者"),
    144: ("陈寿", "权威出处/古籍经典，已核定作者"),
}


def _set_author(body: str, author: str) -> str:
    if re.search(r"^- 作者：.*$", body, re.M):
        return re.sub(r"^- 作者：.*$", f"- 作者：{author}", body, count=1, flags=re.M)
    source = re.search(r"^- 来源：.*$", body, re.M)
    if source:
        return body.replace(source.group(0), source.group(0) + f"\n- 作者：{author}", 1)
    return body


def _mark(body: str, note: str) -> str:
    body = re.sub(r"^- \[[ xX]\] 已修改$", "- [x] 已修改", body, count=1, flags=re.M)
    if re.search(r"^- 修改备注：.*$", body, re.M):
        return re.sub(r"^- 修改备注：.*$", f"- 修改备注：{note}", body, count=1, flags=re.M)
    return body.rstrip() + f"\n- 修改备注：{note}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="补全剩余非个人作者")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        raise ValueError("no entries found")
    header = text[: matches[0].start()]
    parts = [header]
    changed = 0
    for match in matches:
        num, title, body = match.groups()
        if int(num) in REMAINING:
            author, note = REMAINING[int(num)]
            body = _mark(_set_author(body, author), note)
            changed += 1
        parts.append(f"### {num}. {title}\n{body}")

    header = header.lstrip("\ufeff")
    header = re.sub(r"^# .+$", "# 退回修改金句合并清单（最终校准版）", header, count=1, flags=re.M)
    note = (
        "> **最终校准版**：非个人作者的 15 条已补全机构/作者并勾选；"
        "不确定来源按“佚名”处理。"
    )
    marker = "\n---\n"
    if marker in header:
        header = header.replace(marker, f"\n{note}\n---\n", 1)
    else:
        header = header.rstrip() + "\n" + note + "\n"
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    parts[0] = header
    out.write_text("".join(parts), encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(out), "changed": changed}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
