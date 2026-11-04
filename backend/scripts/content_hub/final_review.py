#!/usr/bin/env python3
"""在 AI 预审版基础上应用人工修正，生成最终版（不覆盖原文件）。"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = BACKEND_ROOT / "content_hub_vault" / "00-收件箱" / "审核看板" / "人工复核总清单_391_AI预审版.md"
DEFAULT_OUTPUT = DEFAULT_INPUT.with_name("人工复核总清单_最终版.md")

_SECTION_RE = re.compile(r"(?ms)^### (\d+)\. ([^\n]+)\n(.*?)(?=^### |\Z)")

# 03 中需要直接通过的著名诗人/名臣/学者
_FAMOUS = (
    "杜甫", "诸葛亮", "范仲淹", "林则徐", "韩愈", "曹植",
    "文天祥", "王之涣", "白居易", "朱熹", "晏子", "朱柏庐",
    "欧阳修", "陶渊明", "周敦颐", "刘熙载", "于谦", "司马光",
    "柳宗元", "李白", "王维", "孟浩然", "王昌龄", "岑参",
    "高适", "李商隐", "杜牧", "苏轼", "苏辙", "苏洵",
    "辛弃疾", "陆游", "王安石", "屈原", "司马迁", "曹操",
    "郑板桥", "龚自珍", "刘禹锡", "李贺", "王勃", "陈子昂",
    "张九龄", "崔颢", "杜荀鹤", "罗隐", "皮日休", "曾巩",
    "晏殊", "柳永", "秦观", "李清照", "元好问", "纳兰性德",
    "张居正", "魏征", "包拯", "海瑞", "曾国藩", "左宗棠",
)

# 01/02 中视为古籍的来源关键字
_ANCIENT = (
    "尚书", "诗经", "大学", "论语", "左传", "中庸", "孟子",
    "道德经", "老子", "庄子", "礼记", "周易", "史记", "韩非子",
    "管子", "荀子", "墨子", "战国策", "国语", "古文观止",
    "增广贤文", "吕氏春秋", "淮南子", "三国志", "晋书", "后汉书",
    "汉书", "资治通鉴", "春秋", "楚辞", "文选", "说苑", "新序",
    "论衡", "潜夫论", "贞观政要", "菜根谭", "围炉夜话", "朱子家训",
    "颜氏家训", "传习录", "近思录",
)

_XI = (
    "习近平", "人民对美好生活的向往", "我将无我", "绿水青山就是金山银山",
    "空谈误国", "撸起袖子加油干", "不忘初心", "江山就是人民",
    "以人民为中心",
)


def _match(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in (text or "") for term in terms)


def _parse(text: str) -> tuple[str, list[dict[str, Any]]]:
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        raise ValueError("no entries found")
    header = text[: matches[0].start()]
    entries: list[dict[str, Any]] = []
    for match in matches:
        num, title, body = match.groups()
        uid_match = re.search(r"- UID：`([^`]+)`", body)
        if not uid_match:
            continue
        source = re.search(r"^- 来源：(.+)$", body, re.M)
        author = re.search(r"^- 作者：(.+)$", body, re.M)
        quote = re.search(r"^> (.+)$", body, re.M)
        bucket = re.search(r"^- 分档：(.+)$", body, re.M)
        decision = re.search(r"^- \[x\] (通过|拒绝|退回修改)$", body, re.M)
        entries.append({
            "num": num,
            "title": title,
            "body": body,
            "uid": uid_match.group(1),
            "source": source.group(1) if source else "",
            "author": author.group(1) if author else "",
            "quote": quote.group(1) if quote else "",
            "bucket": bucket.group(1) if bucket else "",
            "decision": decision.group(1) if decision else "",
        })
    return header, entries


def _set_decision(body: str, decision: str, reason: str) -> str:
    body = re.sub(r"^- \[[ xX]\] (通过|拒绝|退回修改)$", r"- [ ] \1", body, flags=re.M)
    body = body.replace(f"- [ ] {decision}", f"- [x] {decision}", 1)
    if re.search(r"^- 备注：.*$", body, re.M):
        body = re.sub(r"^- 备注：.*$", f"- 备注：{reason}", body, count=1, flags=re.M)
    else:
        body += f"\n- 备注：{reason}\n"
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description="生成最终复核清单")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    header, entries = _parse(text)
    changes: list[dict[str, str]] = []

    for entry in entries:
        decision = entry["decision"]
        target = None
        reason = ""
        if entry["bucket"] == "03-建议拒绝":
            text_all = f"{entry['source']} {entry['author']} {entry['quote']}"
            if _match(text_all, _XI):
                target, reason = "通过", "AI预审：习近平语录，符合标准"
            elif _match(f"{entry['source']} {entry['author']}", _FAMOUS):
                target, reason = "通过", "AI预审：著名诗人/名臣名句，符合标准"
        elif entry["bucket"] in ("01-优先通过", "02-重点复核"):
            if decision == "退回修改" and _match(entry["source"], _ANCIENT):
                target, reason = "通过", "AI预审：古籍经典，无需补现代作者"

        if target and target != decision:
            entry["body"] = _set_decision(entry["body"], target, reason)
            entry["decision"] = target
            changes.append({
                "uid": entry["uid"],
                "bucket": entry["bucket"],
                "from": decision,
                "to": target,
                "reason": reason,
            })

    header = header.replace("# 金句人工复核总清单", "# 金句人工复核总清单（最终版）", 1)
    header = header.replace(
        "> **AI 预审版**：勾选与备注为自动建议，请在 Obsidian 中人工验收。",
        "> **AI 预审版**：勾选与备注为自动建议，请在 Obsidian 中人工验收。\n"
        "> **最终版**：已按人工核查规则修正；03 名诗人/名臣与习近平语录通过，01/02 古籍退回改通过。",
    )

    counts = {"通过": 0, "拒绝": 0, "退回修改": 0}
    for entry in entries:
        counts[entry["decision"]] = counts.get(entry["decision"], 0) + 1
    stats_block = "\n".join([
        "## 最终建议统计",
        "",
        "| 建议 | 数量 |",
        "|---|---:|",
        f"| 通过 | {counts['通过']} |",
        f"| 拒绝 | {counts['拒绝']} |",
        f"| 退回修改 | {counts['退回修改']} |",
        "",
        "---",
        "",
    ])
    marker = "## 01-优先通过"
    if marker in header:
        index = header.index(marker)
        header = header[:index] + stats_block + "\n" + header[index:]
    else:
        header = header.rstrip() + "\n\n" + stats_block

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
        "changes": len(changes),
        "decisions": counts,
        "changed": changes[:20],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
