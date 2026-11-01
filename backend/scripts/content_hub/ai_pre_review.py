#!/usr/bin/env python3
"""AI 预审人工复核总清单，生成新的 Markdown（不覆盖原文件）。

用法（在 backend 目录）：
    python -m scripts.content_hub.ai_pre_review --limit 5 --output /tmp/test.md
    python -m scripts.content_hub.ai_pre_review
"""
from __future__ import annotations

import argparse
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import requests

from app.core.config import settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = BACKEND_ROOT / "content_hub_vault" / "00-收件箱" / "审核看板" / "人工复核总清单_391.md"
DEFAULT_OUTPUT = DEFAULT_INPUT.with_name("人工复核总清单_391_AI预审版.md")

_SECTION_RE = re.compile(r"(?ms)^### (\d+)\. ([^\n]+)\n(.*?)(?=^### |\Z)")
_JSON_ARRAY_RE = re.compile(r"\[.*\]", re.S)
_CLASSIC = (
    "诗经", "论语", "道德经", "老子", "孟子", "庄子", "大学", "中庸",
    "史记", "韩非子", "管子", "孙子兵法", "荀子", "墨子", "礼记",
    "周易", "尚书", "左传", "国语", "战国策", "增广贤文", "古文观止",
    "唐诗", "宋词", "毛泽东", "习近平", "苏轼", "苏辙", "孟郊",
    "郑板桥", "陈子昂", "后汉书", "传统", "官箴",
)
_HARD = ("赌博", "毒品", "色情", "暴恐", "恐怖主义", "造谣", "谣言", "颠覆",
         "枪支", "自杀", "涉密", "绝密", "机密文件", "此处插入", "占位", "???")

_SYSTEM = (
    "你是公安联考申论金句审核员。严格按给定标准判断，不修改原文。"
    "只输出 JSON 数组，不要 Markdown 代码块。"
)
_CRITERIA = """判定标准：
- 通过：主题契合警校思政/警务素养/法治/心理韧性；内容完整、无错别字乱码；来源或作者明确，或属于耳熟能详的经典；无敏感/负面/广告/PII。
- 拒绝：含敏感词、负面价值观、广告引流、手机号/身份证；纯乱码/占位符；字数过短且语义残缺；主题严重不符；严重重复且无价值。
- 退回修改：句子本身优质但缺作者/出处、来源模糊；有错别字/标点问题；主题标签明显错乱。
注意：经典名句即使很短、缺作者，也应该给“通过”或“退回修改（补出处）”，不要拒绝。
"""


def _is_classic(entry: dict[str, Any]) -> bool:
    text = f"{entry.get('source','')} {entry.get('author','')}"
    return any(term in text for term in _CLASSIC)


def _hard_risk(text: str) -> bool:
    return any(term in text for term in _HARD) or bool(re.search(r"\?{3,}", text))


def _fallback(entry: dict[str, Any]) -> tuple[str, str]:
    text = entry["quote"]
    source = entry.get("source", "")
    author = entry.get("author", "")
    classic = _is_classic(entry)
    if _hard_risk(text):
        return "拒绝", "含敏感词/乱码/占位内容"
    if not author:
        if classic:
            return "退回修改", "经典名句，建议补作者/出处"
        if source:
            return "退回修改", "缺少作者，建议补出处"
        return "退回修改", "缺少作者和明确出处"
    if entry.get("bucket") == "03-建议拒绝" and not classic:
        return "拒绝", "评分偏低，文学性或主题性不足"
    if entry.get("bucket") == "03-建议拒绝":
        return "退回修改", "经典名句，建议补出处后复核"
    if classic and entry.get("score", 0) >= 80:
        return "通过", "经典名句，符合备考主题"
    if entry.get("score", 0) >= 75:
        return "通过", "来源明确，评分较高"
    return "退回修改", "建议补充出处/标签后复核"


def _parse(text: str) -> tuple[str, list[dict[str, Any]]]:
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        raise ValueError("no checklist entries found")
    header = text[: matches[0].start()]
    entries: list[dict[str, Any]] = []
    for match in matches:
        num, title, body = match.groups()
        uid_match = re.search(r"- UID：`([^`]+)`", body)
        if not uid_match:
            continue
        uid = uid_match.group(1)
        source = re.search(r"^- 来源：(.+)$", body, re.M)
        author = re.search(r"^- 作者：(.+)$", body, re.M)
        topics = re.search(r"^- 主题：(.+)$", body, re.M)
        quote = re.search(r"^> (.+)$", body, re.M)
        score = re.search(r"— ([\d.]+) 分 / (\w+)", title)
        bucket = re.search(r"^- 分档：(.+)$", body, re.M)
        entries.append({
            "num": num,
            "title": title,
            "body": body,
            "uid": uid,
            "source": "" if not source or source.group(1) == "（缺失）" else source.group(1),
            "author": "" if not author or author.group(1) == "（缺失）" else author.group(1),
            "topics": topics.group(1) if topics else "",
            "quote": quote.group(1) if quote else "",
            "score": float(score.group(1)) if score else 0.0,
            "status": score.group(2) if score else "",
            "bucket": bucket.group(1) if bucket else "",
        })
    return header, entries


def _call_llm(batch: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:
    if not settings.LLM_API_URL:
        raise RuntimeError("LLM_API_URL 未配置")
    payload_items = [
        {
            "uid": item["uid"],
            "金句": item["quote"],
            "来源": item["source"] or "缺失",
            "作者": item["author"] or "缺失",
            "主题": item["topics"],
            "Scout分": item["score"],
            "分档": item["bucket"],
        }
        for item in batch
    ]
    headers = {"Content-Type": "application/json"}
    if settings.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LLM_API_KEY}"
    response = requests.post(
        settings.LLM_API_URL,
        headers=headers,
        json={
            "model": settings.LLM_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _CRITERIA + "\n请审核以下条目：\n" + json.dumps(payload_items, ensure_ascii=False)},
            ],
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    content = data.get("content")
    if not content and data.get("choices"):
        content = data["choices"][0].get("message", {}).get("content")
    if not content:
        raise ValueError("empty LLM content")
    raw = str(content)
    match = _JSON_ARRAY_RE.search(raw)
    if not match:
        raise ValueError("LLM response has no JSON array")
    arr = json.loads(match.group(0))
    out: dict[str, tuple[str, str]] = {}
    for item in arr:
        uid = str(item.get("uid", ""))
        decision = str(item.get("decision", "")).strip()
        reason = str(item.get("reason", "")).strip()[:40] or "AI 预审"
        if uid and decision in ("通过", "拒绝", "退回修改"):
            out[uid] = (decision, reason)
    return out


def _render(header: str, entries: list[dict[str, Any]], decisions: dict[str, tuple[str, str]]) -> str:
    header = header.replace(
        "> 本文档是汇总清单；逐条可点击复选框，完成后可按此文档统一回写。",
        "> 本文档是汇总清单；逐条可点击复选框，完成后可按此文档统一回写。\n"
        "> **AI 预审版**：勾选与备注为自动建议，请在 Obsidian 中人工验收。",
    )
    parts = [header]
    for entry in entries:
        decision, reason = decisions.get(entry["uid"], _fallback(entry))
        body = entry["body"]
        body = re.sub(r"^- \[[ xX]\] (通过|拒绝|退回修改)\s*$", r"- [ ] \1", body, count=3, flags=re.M)
        body = body.replace(f"- [ ] {decision}", f"- [x] {decision}", 1)
        if re.search(r"^- 备注：.*$", body, re.M):
            body = re.sub(
                r"^- 备注：.*$",
                f"- 备注：AI预审：{reason}",
                body,
                count=1,
                flags=re.M,
            )
        else:
            body += f"\n- 备注：AI预审：{reason}\n"
        parts.append(f"### {entry['num']}. {entry['title']}\n{body}")
    return "".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 预审复核总清单")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    header, entries = _parse(text)
    if args.limit:
        entries = entries[: args.limit]

    decisions: dict[str, tuple[str, str]] = {}
    llm_ok = 0
    llm_failed = 0
    batches = [entries[i:i + args.batch_size] for i in range(0, len(entries), args.batch_size)]

    def run(batch):
        for attempt in range(2):
            try:
                return _call_llm(batch)
            except Exception:
                if attempt == 0:
                    time.sleep(2)
        raise RuntimeError("batch failed")

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(run, b): b for b in batches}
        for future in as_completed(futures):
            batch = futures[future]
            try:
                decisions.update(future.result())
                llm_ok += len(batch)
            except Exception:
                llm_failed += len(batch)
                for item in batch:
                    decisions[item["uid"]] = _fallback(item)

    for entry in entries:
        decisions.setdefault(entry["uid"], _fallback(entry))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render(header, entries, decisions), encoding="utf-8")
    counts = {"通过": 0, "拒绝": 0, "退回修改": 0}
    for entry in entries:
        counts[decisions[entry["uid"]][0]] += 1
    print(json.dumps({
        "ok": True,
        "path": str(output),
        "total": len(entries),
        "decisions": counts,
        "llm_ok": llm_ok,
        "llm_failed": llm_failed,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
