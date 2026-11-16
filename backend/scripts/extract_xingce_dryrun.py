# 行测题本 PDF 抽取（试运行，不写数据库）
#
# 背景：MinerU 环境缺失曾被视为 P0 的硬阻塞。实测抽样 40 个 PDF，40/40 都有文本层，
# 用已有的 pdfplumber 即可抽取，无需下载几 GB 模型。
#
# 用法：
#   python backend/scripts/extract_xingce_dryrun.py --limit 1
#   （只读 PDF，输出 JSON 到 backend/data/tmp/，绝不写 question_bank）
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "backend" / "data" / "tmp"

Q_HEAD = re.compile(r"^\s*(\d{1,3})[.、]\s*(.+)$")
OPT = re.compile(r"^\s*([ABCD])[.、]\s*(.+)$")


def parse_pages(text: str) -> list[dict]:
    """把整段文本切成题目。识别不了选项的题目会被跳过（宁可少提，不要脏数据）。"""
    lines = [ln.rstrip() for ln in text.splitlines()]
    items: list[dict] = []
    cur: dict | None = None

    for ln in lines:
        m = Q_HEAD.match(ln)
        if m and (cur is None or cur.get("options")):
            if cur and len(cur.get("options", {})) >= 2:
                items.append(cur)
            cur = {"qno": int(m.group(1)), "stem": m.group(2).strip(), "options": {}}
            continue
        if cur is None:
            continue
        mo = OPT.match(ln)
        if mo:
            cur["options"][mo.group(1)] = mo.group(2).strip()
            continue
        if cur["options"]:
            # 选项后还有续行，接到最后一个选项上
            last = list(cur["options"])[-1]
            cur["options"][last] += ln.strip()
        else:
            cur["stem"] += ln.strip()

    if cur and len(cur.get("options", {})) >= 2:
        items.append(cur)
    items = [it for it in items if not _is_meta(it)]
    for it in items:
        it["task_kind"] = "single_choice" if len(it["options"]) == 4 else "multi_or_other"
    return items


# 题本里混着「本题正确率…默认答案为A」「缺失」这类元信息行，必须剔除，否则会当成题目入库
META_MARKERS = ("默认答案为", "正确率", "本题得分率", "答案见解析")
PLACEHOLDER = {"缺失", "无", "略", "选项缺失"}


def _is_meta(it: dict) -> bool:
    stem = it.get("stem", "")
    if any(m in stem for m in META_MARKERS):
        return True
    opts = list(it.get("options", {}).values())
    if opts and all(o.strip() in PLACEHOLDER for o in opts):
        return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1, help="抽取几个题本 PDF（试运行用）")
    ap.add_argument("--pages", type=int, default=6, help="每个 PDF 取前几页")
    args = ap.parse_args()

    files = sorted(glob.glob(str(ROOT / "题库" / "行测" / "**" / "*题本.pdf"), recursive=True))
    if not files:
        print("[SKIP] 未找到 题本.pdf")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for f in files[: args.limit]:
        with pdfplumber.open(f) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages[: args.pages])
        items = parse_pages(text)
        total += len(items)
        out = OUT_DIR / (os.path.splitext(os.path.basename(f))[0][:40] + ".json")
        out.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] {os.path.basename(f)[:36]} -> {len(items)} 题  ({out.name})")

    print(f"[SUMMARY] 共抽取 {total} 题（仅试运行，未写数据库）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
