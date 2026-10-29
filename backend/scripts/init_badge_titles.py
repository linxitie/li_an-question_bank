# -*- coding: utf-8 -*-
"""S2.5：播种 6 档等级称号（badge_title，幂等）。

用户批复：见习 / 入门 / 熟练 / 精通 / 大师 / 宗师，解锁等级 1/5/10/20/30/50。

说明：库里原有 3 条是「金币商城限定称号」（title_li_an_star 等），
属于商城商品，与这 6 档等级称号并存，不冲突。

用法（在 backend 目录）：
    python scripts/init_badge_titles.py
    python scripts/init_badge_titles.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "question_bank.db")

# (code, name, description, unlock_level, sort_order)
TITLES = [
    ("title_level_01", "见习", "学习等级达到 1 级", 1, 10),
    ("title_level_02", "入门", "学习等级达到 5 级", 5, 11),
    ("title_level_03", "熟练", "学习等级达到 10 级", 10, 12),
    ("title_level_04", "精通", "学习等级达到 20 级", 20, 13),
    ("title_level_05", "大师", "学习等级达到 30 级", 30, 14),
    ("title_level_06", "宗师", "学习等级达到 50 级", 50, 15),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(DB):
        print(f"[FAIL] 数据库不存在: {DB}")
        return 1

    con = sqlite3.connect(DB)
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(badge_title)")]
        need = {"title_id", "title_code", "name", "description", "unlock_level", "sort_order"}
        missing = need - set(cols)
        if missing:
            print(f"[FAIL] badge_title 缺列: {sorted(missing)}")
            return 1

        created = skipped = 0
        for code, name, desc, level, sort in TITLES:
            hit = con.execute(
                "SELECT title_id, name FROM badge_title WHERE title_code=?", (code,)).fetchone()
            if hit:
                skipped += 1
                print(f"  跳过（已存在）：{code} → #{hit[0]} {hit[1]}")
                continue
            # 同名但 code 不同（例如人工先建过）也要检查，避免重复展示
            same_name = con.execute(
                "SELECT title_id FROM badge_title WHERE name=?", (name,)).fetchone()
            if same_name:
                skipped += 1
                print(f"  跳过（同名已存在）：{name} → #{same_name[0]}")
                continue
            if not args.dry_run:
                con.execute(
                    "INSERT INTO badge_title(title_code,name,description,unlock_level,sort_order)"
                    " VALUES(?,?,?,?,?)", (code, name, desc, level, sort))
            created += 1
            print(f"  新增：{name}（解锁等级 {level}）")
        if not args.dry_run:
            con.commit()

        total = con.execute("SELECT COUNT(*) FROM badge_title").fetchone()[0]
        levels = con.execute(
            "SELECT name, unlock_level FROM badge_title WHERE title_code LIKE 'title_level%' "
            "ORDER BY unlock_level").fetchall()
        print(f"\n模式：{'DRY-RUN（不写库）' if args.dry_run else '实际执行'}")
        print(f"结果：新增 {created}，跳过 {skipped}")
        print(f"库内称号总数：{total}")
        print(f"等级称号（{len(levels)} 档）：" + "、".join(f"{n}(Lv{l})" for n, l in levels))
    finally:
        con.close()
    print("\n完成。可重复执行（幂等）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
