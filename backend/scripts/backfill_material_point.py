# -*- coding: utf-8 -*-
"""回填资料的考点与游离分类（P2.1/P2.2，幂等）。

两件事：
1. **考点回填**：卡片标题能对上 knowledge_point.point_name 的，写 point_id
   （支持「标题 == 考点名」与「标题包含考点名」，取最长匹配）。
2. **游离类目归位**：category 不在 sub_categories 词表内的卡片，用考点所属
   子类覆盖（当前行测 9 张「方法技巧」就是这一类）；category 为空但有考点的也补上。

默认只报告，`--apply` 才写库。绝不删除任何行。
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BACKEND, "data", "question_bank.db")
SUBJECTS = {1: "xingce", 2: "shenlun", 3: "gongzhuan"}

# 标题对不上考点名、但语义明确的存量卡（人工确认过的映射，逐条可追溯）
TITLE_TO_POINT = {
    "资料分析·平均数增长率": "统计术语",
    "判断推理·加强削弱": "逻辑判断",
    "语句排序解题步骤": "语句表达",
    "细节判断题避坑": "片段阅读",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写库（默认 dry-run）")
    a = ap.parse_args()

    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL")
    cols = {r[1] for r in con.execute("PRAGMA table_info(study_material)")}
    if "point_id" not in cols:
        print("FAIL: study_material 缺 point_id 列，请先跑 "
              "python scripts/init_material_data.py --apply")
        con.close()
        return 2

    cats = {r[0]: (r[1] or "").strip() for r in con.execute("SELECT id, name FROM sub_categories")}
    points = con.execute(
        "SELECT point_id, point_name, subject_id, sub_category_id FROM knowledge_point "
        "WHERE status=1").fetchall()
    by_subject: dict[str, list] = {}
    for pid, name, sid, scid in points:
        subj = SUBJECTS.get(sid)
        if not subj:
            continue
        by_subject.setdefault(subj, []).append(
            ((name or "").strip(), pid, cats.get(scid, "")))
    for subj in by_subject:
        # 长名优先，避免「逻辑判断」抢走「逻辑填空」
        by_subject[subj].sort(key=lambda x: len(x[0]), reverse=True)

    valid = {s: {c[2] for c in v} for s, v in by_subject.items()}
    rows = con.execute(
        "SELECT material_id, subject, title, category, point_id, status "
        "FROM study_material WHERE type='card'").fetchall()

    plan, unmatched = [], []
    for mid, subj, title, cat, pid, st in rows:
        title = (title or "").strip()
        hit = None
        alias = TITLE_TO_POINT.get(title)
        if alias:
            for pname, ppid, pcat in by_subject.get(subj, []):
                if pname == alias:
                    hit = (pname, ppid, pcat)
                    break
        if not hit:
            for pname, ppid, pcat in by_subject.get(subj, []):
                if pname and (title == pname or pname in title):
                    hit = (pname, ppid, pcat)
                    break
        if not hit:
            unmatched.append((mid, subj, title, cat))
            continue
        pname, ppid, pcat = hit
        new_point = pid or ppid
        new_cat = cat if (cat or "").strip() in valid.get(subj, set()) else pcat
        if new_point != pid or new_cat != cat:
            plan.append((mid, subj, title, cat, new_cat, pid, new_point, pname))

    print(f"卡片 {len(rows)} 张：可回填 {len(plan)} 张，无可匹配考点 {len(unmatched)} 张")
    moved = [p for p in plan if p[3] != p[4] and (p[3] or "").strip()]
    print(f"  其中「游离类目归位」{len(moved)} 张，仅补考点/补空分类 {len(plan) - len(moved)} 张")
    for p in moved:
        print(f"    改类目 id={p[0]} {p[3]} → {p[4]}  ({p[2]})")
    for u in unmatched[:10]:
        print(f"    无考点 id={u[0]} [{u[1]}] title={u[2]!r} cat={u[3]!r}")

    if not a.apply:
        print("（dry-run，加 --apply 生效）")
        con.close()
        return 0

    with con:
        for mid, subj, title, old_cat, new_cat, old_pid, new_pid, pname in plan:
            con.execute(
                "UPDATE study_material SET point_id=?, category=? WHERE material_id=?",
                (new_pid, new_cat, mid))
    # 覆盖统计
    total = con.execute("SELECT COUNT(*) FROM knowledge_point WHERE status=1").fetchone()[0]
    covered = con.execute(
        "SELECT COUNT(DISTINCT point_id) FROM study_material "
        "WHERE type='card' AND point_id IS NOT NULL").fetchone()[0]
    per = con.execute(
        "SELECT subject, COUNT(DISTINCT point_id) FROM study_material "
        "WHERE type='card' AND point_id IS NOT NULL GROUP BY 1").fetchall()
    print(f"✅ 回填完成：考点覆盖 {covered}/{total}；按科目 {dict(per)}")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
