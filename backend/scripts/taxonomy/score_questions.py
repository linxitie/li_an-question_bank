# -*- coding: utf-8 -*-
"""存量题质量分回填（v8 M4）。

给 question_bank 现有题补 quality_score / quality_flags，便于教师端筛「待修正」。
只读题库内容 + 写这两列，不动题干答案。

用法： python scripts/taxonomy/score_questions.py [--apply]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

import sys

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

from app.services.question_ingest.quality import PASS_SCORE, score_question  # noqa: E402

DB_PATH = BACKEND_DIR / "data" / "question_bank.db"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT question_id, question_content, options, answer, answer_analysis, source, year, type_id "
        "FROM question_bank WHERE status = 1"
    ).fetchall()

    # 图片数：只数「磁盘上真实存在」的图。
    # 只数 DB 行会漏判：question_image 里有 298 行，实测有 13 张图文件已被删除，
    # 前端表现为「图片加载失败」，必须按文件存在性判定才算修对。
    img_counts = {}
    missing_files = 0
    for qid, path in conn.execute("SELECT question_id, image_path FROM question_image"):
        if not path:
            continue
        rel = str(path).lstrip('/')
        on_disk = (BACKEND_DIR / 'app' / rel).exists() or (BACKEND_DIR.parent / rel).exists()
        if on_disk:
            img_counts[qid] = img_counts.get(qid, 0) + 1
        else:
            missing_files += 1
    print(f"图片文件缺失：{missing_files} 条 question_image 记录指向不存在的文件")

    updates = []
    flags_counter: Counter = Counter()
    below = 0
    for r in rows:
        payload = {
            "question_content": r["question_content"],
            "options": r["options"],
            "answer": r["answer"],
            "answer_analysis": r["answer_analysis"],
            "source": r["source"],
            "year": r["year"],
            "image_count": img_counts.get(r["question_id"], 0),
        }
        res = score_question(payload)
        for f in res["flags"]:
            flags_counter[f] += 1
        if not res["pass"]:
            below += 1
        updates.append((float(res["score"]), ",".join(res["flags"]) or None, r["question_id"]))

    print(f"扫描 {len(rows)} 题 | 低于 {PASS_SCORE} 分：{below} | 问题分布：{json.dumps(dict(flags_counter.most_common()), ensure_ascii=False)}")
    if args.apply:
        conn.executemany(
            "UPDATE question_bank SET quality_score = ?, quality_flags = ? WHERE question_id = ?",
            updates,
        )
        conn.commit()
        print("已写回 quality_score / quality_flags")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())