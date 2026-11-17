# -*- coding: utf-8 -*-
"""填空横线缺失盘点与回填建议（M8）。

背景（v6.0 方案 §9）：Word 里的填空横线是「带下划线格式的空格/制表位」，
旧的 docx 解析只取 run.text，横线在入库时就丢了。解析层已修（新导入不再丢），
但历史题已经丢，只能按上下文定位后人工确认再改。

本脚本只读 + 生成报告，不做任何写库操作：
  python scripts/report_missing_blanks.py

报告里给每条题一个建议方案：
  - 题干中存在连续空白（两个及以上空白字符）→ 建议替换成 4 个下划线（高置信）
  - 否则标「需人工定位」
为什么不自动写库：题干是答题依据，改错一个字就是错题，必须有人确认。
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402

MENTION_RE = re.compile(r"横线|划线|下划线")
BLANK_RE = re.compile(r"_{3,}")
GAP_RE = re.compile(r"\s{2,}")
# 单个空白也可能是横线残留：Word 下划线空格被解析成普通空格后只剩一个。
# 判定条件——两侧都是中文/中文标点（不是英文单词间距、不是句间缩进）。
CJK = "\u4e00-\u9fff，。、；：？！“”‘’（）《》【】…—·"
SPACE_CAND_RE = re.compile(r"(?<=[" + CJK + r"])[ \t]+(?=[" + CJK + r"])")
FENCE = chr(96) * 3


def scan(db, limit: int = 0):
    rows = db.execute(text(
        """
        SELECT question_id, subject_id, question_content
        FROM question_bank
        WHERE question_content LIKE '%横线%'
           OR question_content LIKE '%划线%'
           OR question_content LIKE '%下划线%'
        ORDER BY question_id
        """
    )).mappings().all()
    missing = []
    for row in rows:
        content = row["question_content"] or ""
        if BLANK_RE.search(content):
            continue
        if not MENTION_RE.search(content):
            continue
        gap = GAP_RE.search(content)
        if gap:
            proposal = GAP_RE.sub("____", content, count=1)
            confidence = "高"
            reason = "题干存在连续空白，该空白处即原下划线所在"
        else:
            # 题目末尾「。 下列选项填入横线…」的空白属于排版分段，不是横线，剔除
            INSTRUCTION_TAIL = ("下列", "填入", "请选择", "最恰当", "选项", "横线", "划线")
            candidates = [
                m for m in SPACE_CAND_RE.finditer(content)
                if not content[m.end():m.end() + 6].startswith(INSTRUCTION_TAIL)
            ]
            if len(candidates) == 1:
                start, end = candidates[0].span()
                proposal = content[:start] + "____" + content[end:]
                confidence = "较高"
                reason = "题干仅一处中文字符间的空白，最可能是被吞掉的下划线"
            else:
                proposal = ""
                confidence = "需人工"
                reason = "候选空白 " + str(len(candidates)) + " 处，无法唯一确定横线位置"
        missing.append({
            "question_id": row["question_id"],
            "subject_id": row["subject_id"],
            "content": content,
            "proposal": proposal,
            "confidence": confidence,
            "reason": reason,
        })
        if limit and len(missing) >= limit:
            break
    return rows, missing


def render_markdown(total_mentioned: int, missing, generated_at: str) -> str:
    lines = []
    lines.append("# 填空横线缺失盘点报告")
    lines.append("")
    lines.append("- 生成时间：" + generated_at)
    lines.append("- 提及「横线/划线」的题：" + str(total_mentioned) + " 条")
    lines.append("- 其中没有可见占位符：" + str(len(missing)) + " 条（用户看到的横线没显示）")
    highs = [m for m in missing if m["confidence"] == "高"]
    lines.append("- 可自动定位（题干有连续空白）：" + str(len(highs)) + " 条")
    lines.append("")
    lines.append("> 为什么不自动改库：题干是判分依据，位置错一个字就是错题。")
    lines.append("> 人工确认 question_id 与替换位置后，再逐条 apply。")
    lines.append("")
    for item in missing:
        lines.append("## 题 " + str(item["question_id"]) + "（科目 " + str(item["subject_id"]) + " · " + item["confidence"] + "）")
        lines.append("")
        lines.append("原文：")
        lines.append("")
        lines.append(FENCE)
        lines.append(item["content"])
        lines.append(FENCE)
        if item["proposal"]:
            lines.append("建议（把连续空白替换成 4 个下划线）：")
            lines.append("")
            lines.append(FENCE)
            lines.append(item["proposal"])
            lines.append(FENCE)
        lines.append("判定依据：" + item["reason"])
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="", help="报告输出路径")
    parser.add_argument("--limit", type=int, default=0, help="最多输出多少条")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows, missing = scan(db, args.limit)
    finally:
        db.close()

    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = render_markdown(len(rows), missing, generated_at)
    out = args.out
    if not out:
        audit_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "audit")
        os.makedirs(audit_dir, exist_ok=True)
        out = os.path.join(audit_dir, "missing_blanks_" + dt.datetime.now().strftime("%Y%m%d_%H%M%S") + ".md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(md)
    print("提及横线的题: " + str(len(rows)) + "，缺占位符: " + str(len(missing)))
    print("报告已写入: " + out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
