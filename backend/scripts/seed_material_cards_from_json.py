# -*- coding: utf-8 -*-
"""用 content JSON 批量落库卡片（P3，幂等）。

规则
----
- 以 (subject, point_id) 为准：已有该考点的卡片 → 更新正/背面、摘要、难度、时长、分类；
  没有 → 新建一张（status=1 上架，creator_id 取管理员）。
- category 必须命中 sub_categories 词表，否则该条跳过并报错（不猜）。
- 默认 dry-run；`--apply` 才写库；`--cleanup-e2e` 顺带删掉 3 张 E2E 测试残留卡。

用法
----
    python scripts/seed_material_cards_from_json.py                 # 只看计划
    python scripts/seed_material_cards_from_json.py --apply
    python scripts/seed_material_cards_from_json.py --apply --cleanup-e2e
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BACKEND, "data", "question_bank.db")
SRC = os.path.join(BACKEND, "scripts", "data", "material_cards_supplement.json")
SUBJECTS = {1: "xingce", 2: "shenlun", 3: "gongzhuan"}
E2E_TITLES = ("E2E 私有卡", "E2E 分享卡", "C 改过的副本")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--cleanup-e2e", action="store_true")
    a = ap.parse_args()

    with open(SRC, encoding="utf-8") as fh:
        items = json.load(fh)
    print(f"内容文件 {len(items)} 条")

    con = sqlite3.connect(DB)
    con.execute("PRAGMA journal_mode=WAL")
    cats = {}
    for cid, name, sid in con.execute("SELECT id, name, subject_id FROM sub_categories"):
        cats[(SUBJECTS.get(sid), (name or "").strip())] = cid
    points = {}
    for pid, name, sid in con.execute(
            "SELECT point_id, point_name, subject_id FROM knowledge_point WHERE status=1"):
        points[(SUBJECTS.get(sid), (name or "").strip())] = pid

    admin = con.execute(
        "SELECT user_id FROM sys_user WHERE user_type='admin' "
        "ORDER BY user_id LIMIT 1").fetchone()
    admin_id = admin[0] if admin else None

    plan_new, plan_upd, bad = [], [], []
    for it in items:
        subj = it.get("subject")
        pname = (it.get("point") or "").strip()
        cat = (it.get("category") or "").strip()
        pid = points.get((subj, pname))
        if not pid:
            bad.append((pname, "考点不存在"))
            continue
        if (subj, cat) not in cats:
            bad.append((pname, f"分类不在词表: {cat}"))
            continue
        row = con.execute(
            "SELECT material_id FROM study_material WHERE type='card' AND subject=? "
            "AND point_id=? ORDER BY material_id LIMIT 1", (subj, pid)).fetchone()
        (plan_upd if row else plan_new).append((it, pid, row[0] if row else None))

    print(f"  将更新 {len(plan_upd)} 张、新建 {len(plan_new)} 张、跳过 {len(bad)} 条")
    for p in bad[:5]:
        print("   跳过:", p)
    if not a.apply:
        print("（dry-run，加 --apply 生效）")
        con.close()
        return 0

    with con:
        for it, pid, mid in plan_upd:
            con.execute(
                "UPDATE study_material SET card_front=?, card_back=?, summary=?,"
                " category=?, difficulty=?, read_time=?, title=?, status=1"
                " WHERE material_id=?",
                (it.get("front"), it.get("back"), it.get("summary"),
                 it.get("category"), it.get("difficulty"), it.get("minutes"),
                 it.get("front"), mid))
        for it, pid, _ in plan_new:
            con.execute(
                "INSERT INTO study_material(subject, type, category, point_id, title,"
                " summary, card_front, card_back, read_time, difficulty, status,"
                " sort_order, creator_id)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,1,0,?)",
                (it.get("subject"), "card", it.get("category"), pid, it.get("front"),
                 it.get("summary"), it.get("front"), it.get("back"),
                 it.get("minutes"), it.get("difficulty"), admin_id))
        if a.cleanup_e2e:
            cond = " OR ".join("title LIKE ?" for _ in E2E_TITLES)
            args = [t + "%" for t in E2E_TITLES]
            n = con.execute(
                f"SELECT COUNT(*) FROM study_material WHERE status<0 AND ({cond})", args
            ).fetchone()[0]
            con.execute(f"DELETE FROM study_material WHERE status<0 AND ({cond})", args)
            print(f"  清理 E2E 残留卡 {n} 张")

    total = con.execute("SELECT COUNT(*) FROM knowledge_point WHERE status=1").fetchone()[0]
    covered = con.execute(
        "SELECT COUNT(DISTINCT point_id) FROM study_material WHERE type='card' "
        "AND point_id IS NOT NULL AND status>0").fetchone()[0]
    per = con.execute(
        "SELECT subject, COUNT(DISTINCT point_id) FROM study_material WHERE type='card' "
        "AND point_id IS NOT NULL AND status>0 GROUP BY 1").fetchall()
    cards = con.execute(
        "SELECT COUNT(*) FROM study_material WHERE type='card' AND status>0").fetchone()[0]
    short = con.execute(
        "SELECT COUNT(*) FROM study_material WHERE type='card' AND status>0 "
        "AND LENGTH(COALESCE(card_back,''))<60").fetchone()[0]
    no_summary = con.execute(
        "SELECT COUNT(*) FROM study_material WHERE type='card' AND status>0 "
        "AND COALESCE(TRIM(summary),'')=''").fetchone()[0]
    print(f"✅ 完成：上架卡片 {cards} 张；考点覆盖 {covered}/{total}；按科目 {dict(per)}")
    print(f"   背面<60字 {short} 张；summary 为空 {no_summary} 张")
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
