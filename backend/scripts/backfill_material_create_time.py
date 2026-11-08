#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P2：回填 `study_material.create_time` 为 NULL 的历史资料（默认 dry-run）。

**背景**：实测 58 条历史资料（ID 48–105）**没有上传时间**。管理端列表把 NULL 排到最后
（`null_last`），于是第一页看到 `107,106 → 45,44…` 的跳号，看起来"ID 没按降序"。
这不是排序 bug，是这 58 行缺时间（详见 `docs/plans/资料管理_ID连续与排序_修复方案_v1.md` §1.1）。

**补的值是"补记"不是真实时间**：真实上传时间已不可考（`update_time` 也大多为空）。
按 material_id 升序，以 `2026-10-28 21:26:44`（同批 44/45 号资料的实际时间）为基准，
每条 +1 秒，保证：
  · 与相邻的真实时间不矛盾（48 号紧随 45 号之后，且远早于 106 号的 11-01）；
  · ID 序 == 时间序（第①条需求"按上传时间先后给 ID"成立）；
  · 时间列不再显示「—」，排序稳定。

用法（在 backend/ 下）：
    python scripts/backfill_material_create_time.py           # 只看清单（默认，不写库）
    python scripts/backfill_material_create_time.py --apply   # 真的写
    python scripts/backfill_material_create_time.py --db path/to.db
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timedelta

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(os.path.dirname(_HERE), "data", "question_bank.db")
BASE = datetime(2026, 10, 28, 21, 26, 45)   # 44/45 号是 21:26:44.x，从 45 秒开始避免同秒


def main() -> int:
    ap = argparse.ArgumentParser(description="回填缺失的 study_material.create_time")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--apply", action="store_true", help="真的写库（默认只打印清单）")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    rows = list(conn.execute(
        "SELECT material_id, type, substr(title, 1, 24) FROM study_material "
        "WHERE create_time IS NULL ORDER BY material_id ASC"))
    total = conn.execute("SELECT count(*) FROM study_material").fetchone()[0]
    print(f"库: {args.db}\n资料总数 {total} ｜ create_time 为空的 {len(rows)} 条")
    if not rows:
        print("✅ 没有需要回填的行（全部已有上传时间）")
        conn.close()
        return 0

    plan = []
    for idx, (mid, mtype, title) in enumerate(rows):
        when = (BASE + timedelta(seconds=idx)).strftime("%Y-%m-%d %H:%M:%S")
        plan.append((mid, when, mtype, title))

    print(f"\n{'ID':>5}  {'补记时间':<20} {'类型':<12} 标题")
    for mid, when, mtype, title in plan:
        print(f"{mid:>5}  {when:<20} {mtype:<12} {title}")
    print(f"\n时间区间: {plan[0][1]} … {plan[-1][1]}（每条 +1s，共 {len(plan)} 条）")

    if not args.apply:
        print("\n（dry-run）加 --apply 才会写库；写库前请先 sqlite3.backup() 快照")
        conn.close()
        return 0

    cur = conn.cursor()
    # `list_time` 是 ID 方案 A 新增的列，只有后端启动过（自动补列）之后才存在；
    # 不存在时只补 create_time/update_time，list_time 交给启动期回填补齐。
    cols = {row[1] for row in conn.execute("PRAGMA table_info(study_material)")}
    has_list_time = "list_time" in cols
    for mid, when, _t, _title in plan:
        if has_list_time:
            cur.execute(
                "UPDATE study_material SET create_time = ?, "
                "update_time = COALESCE(update_time, ?), "
                "list_time = COALESCE(list_time, ?) WHERE material_id = ?",
                (when, when, when, mid))
        else:
            cur.execute(
                "UPDATE study_material SET create_time = ?, "
                "update_time = COALESCE(update_time, ?) WHERE material_id = ?",
                (when, when, mid))
    conn.commit()
    left = conn.execute(
        "SELECT count(*) FROM study_material WHERE create_time IS NULL").fetchone()[0]
    conn.close()
    print(f"\n已写入 {len(plan)} 行；剩余 create_time 为空: {left}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
