# -*- coding: utf-8 -*-
"""横线回填 diff 清单（v8 M3 / 决策点 D5）。

方案 D5 明确：存量题只出 diff 清单，不自动改库。本脚本扫描 question_bank，
找出「题干提到横线/填空，但没有任何占位符」以及「中文之间夹多空格」两类可疑题，
输出 JSON + Markdown 供人工确认后再决定是否 backfill。

用法：
  python scripts/taxonomy/backfill_blanks.py            # 只出清单
  python scripts/taxonomy/backfill_blanks.py --json-only
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BACKEND_DIR / "data" / "question_bank.db"
OUT_JSON = BACKEND_DIR.parent / "docs" / "design" / "横线回填diff_v1.json"
OUT_MD = BACKEND_DIR.parent / "docs" / "design" / "横线回填diff_v1.md"

# 提到「横线」的题干，但没有任何占位符 → 横线在导入时丢失
_ASK_BLANK = re.compile(r"横线|划线|填空")
_HAS_PLACEHOLDER = re.compile(r"_{2,}|<u>|＿＿|（\s*）")
# 两个中文字之间夹 >=2 个空格：常见于「下划线格式的空格」被剥离后的残留
_CJK_GAP = re.compile(r"[\u4e00-\u9fa5][ \t]{2,}[\u4e00-\u9fa5]")


def scan(db_path: Path = DB_PATH):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT question_id, question_content FROM question_bank "
            "WHERE status = 1 AND question_content IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()

    lost = []
    gaps = []
    for r in rows:
        text = r["question_content"] or ""
        qid = r["question_id"]
        if _ASK_BLANK.search(text) and not _HAS_PLACEHOLDER.search(text):
            lost.append({"question_id": qid, "reason": "提到横线但无占位符", "snippet": _snip(text)})
        elif _CJK_GAP.search(text):
            gaps.append({"question_id": qid, "reason": "中文间夹多空格（疑似下划线空格残留）", "snippet": _snip(text)})
    return {"total": len(rows), "lost_blank": lost, "cjk_gap": gaps}


def _snip(text: str, width: int = 80) -> str:
    plain = re.sub(r"\s+", " ", text).strip()
    hit = _ASK_BLANK.search(plain) or _CJK_GAP.search(plain)
    if not hit:
        return plain[:width]
    start = max(0, hit.start() - width // 2)
    return ("…" if start else "") + plain[start:start + width] + ("…" if start + width < len(plain) else "")


def write_outputs(result: dict) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 横线回填 diff 清单 v1",
        "",
        f"- 扫描题量：{result["total"]}",
        f"- 提到横线但无占位符：**{len(result["lost_blank"])}** 题",
        f"- 中文间夹多空格（疑似残留）：**{len(result["cjk_gap"])}** 题",
        "",
        "> 本清单只做诊断，不自动改库。确认后再决定是否回填。",
        "",
        "## 一、提到横线但无占位符",
        "",
        "| question_id | 片段 |",
        "| --- | --- |",
    ]
    for item in result["lost_blank"]:
        lines.append(f"| {item["question_id"]} | {item["snippet"]} |")
    lines += ["", "## 二、中文间夹多空格", "", "| question_id | 片段 |", "| --- | --- |"]
    for item in result["cjk_gap"][:200]:
        lines.append(f"| {item["question_id"]} | {item["snippet"]} |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-only", action="store_true")
    args = ap.parse_args()
    result = scan()
    write_outputs(result)
    print(f"扫描 {result["total"]} 题 | 提到横线无占位符 {len(result["lost_blank"])} | 中文夹空格 {len(result["cjk_gap"])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())