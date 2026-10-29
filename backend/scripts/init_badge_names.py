# -*- coding: utf-8 -*-
"""S1：播种徽章命名词库 badge_name_bank（幂等）。

背景：badge_name_bank 当前 0 行，徽章无法生成名字。
achievement 实际有 7 个类别：数量/坚持/正确率/综合/社交/错题/成长。
本脚本为每个类别生成 12 个名字（3 前缀 × 2 主体 × 2 后缀），共 84 条。

命名规则：name = prefix_word + body_word + suffix_word
判重键：(name, category)

用法（在 backend 目录）：
    python scripts/init_badge_names.py            # 实跑
    python scripts/init_badge_names.py --dry-run  # 预演
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "question_bank.db")

# 每个类别：3 个前缀 × 2 个主体 × 2 个后缀 = 12 个名字
NAMES: dict[str, tuple[list[str], list[str], list[str]]] = {
    "坚持": (["不辍", "晨光", "铁壁"], ["行者", "守望"], ["者", "印记"]),
    "正确率": (["精准", "无瑕", "磐石"], ["神射", "判官"], ["之眼", "勋章"]),
    "数量": (["百题", "千锤", "万卷"], ["斩", "破阵"], ["者", "勋章"]),
    "综合": (["全科", "通盘", "融会"], ["通关", "贯通"], ["者", "之证"]),
    "社交": (["并肩", "共鸣", "引路"], ["同行", "灯塔"], ["之友", "勋章"]),
    "错题": (["复盘", "破茧", "凿壁"], ["苦手", "追光"], ["之刃", "者"]),
    "成长": (["初启", "登阶", "凌云"], ["新芽", "登攀"], ["之始", "者"]),
}

# score 用于同名竞争时排序：前缀越靠前越高
PREFIX_SCORE = [90, 80, 70]


def build_rows() -> list[tuple]:
    rows = []
    for category, (prefixes, bodies, suffixes) in NAMES.items():
        for pi, prefix in enumerate(prefixes):
            for bi, body in enumerate(bodies):
                for si, suffix in enumerate(suffixes):
                    name = f"{prefix}{body}{suffix}"
                    score = PREFIX_SCORE[pi] - bi * 5 - si * 3
                    style_seed = (pi * 37 + bi * 11 + si * 5) % 1000
                    rows.append((name, category, prefix, body, suffix,
                                 score, "seed_v1", 0, style_seed))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(DB):
        print(f"[FAIL] 数据库不存在: {DB}")
        return 1

    rows = build_rows()
    con = sqlite3.connect(DB)
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(badge_name_bank)")]
        need = {"name", "category", "prefix_word", "body_word", "suffix_word",
                "score", "source", "used", "style_seed"}
        missing = need - set(cols)
        if missing:
            print(f"[FAIL] badge_name_bank 缺列: {sorted(missing)}")
            return 1

        created = skipped = 0
        dup_in_batch = 0
        seen: set[tuple[str, str]] = set()
        for (name, category, pre, body, suf, score, source, used, seed) in rows:
            key = (name, category)
            if key in seen:
                dup_in_batch += 1
                continue
            seen.add(key)
            hit = con.execute(
                "SELECT id FROM badge_name_bank WHERE name=? AND category=?",
                (name, category)).fetchone()
            if hit:
                skipped += 1
                continue
            if not args.dry_run:
                con.execute(
                    "INSERT INTO badge_name_bank(name,category,prefix_word,body_word,"
                    "suffix_word,score,source,used,style_seed) VALUES(?,?,?,?,?,?,?,?,?)",
                    (name, category, pre, body, suf, score, source, used, seed))
            created += 1
        if not args.dry_run:
            con.commit()

        total = con.execute("SELECT COUNT(*) FROM badge_name_bank").fetchone()[0]
        cats = con.execute(
            "SELECT category, COUNT(*) FROM badge_name_bank GROUP BY category "
            "ORDER BY 2 DESC").fetchall()
        print(f"模式：{'DRY-RUN（不写库）' if args.dry_run else '实际执行'}")
        print(f"生成规则：{len(NAMES)} 类 × 12 = {len(rows)} 条")
        print(f"结果：新增 {created}，已存在跳过 {skipped}，批内重复 {dup_in_batch}")
        print(f"库内当前总数：{total}")
        for c, n in cats:
            print(f"  {c}: {n}")
        if not args.dry_run:
            # 基本体检：名字非空且无重复
            empty = con.execute(
                "SELECT COUNT(*) FROM badge_name_bank WHERE TRIM(name)=''").fetchone()[0]
            dup = con.execute(
                "SELECT COUNT(*) FROM (SELECT name, category, COUNT(*) c FROM badge_name_bank "
                "GROUP BY name, category HAVING c > 1)").fetchone()[0]
            print(f"体检：空名 {empty} 条，重复(名+类) {dup} 组")
    finally:
        con.close()
    print("\n完成。可重复执行（幂等）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
