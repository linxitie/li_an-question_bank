# -*- coding: utf-8 -*-
"""播种「读卡」相关成就（幂等）。

背景：3 个 material 成就此前只直接 INSERT 到本地库，未随代码入库；
换机器/换库后成就判定会因缺少目录项而永不触发。本脚本可重复执行。

用法：
    cd backend && python scripts/seed_material_achievements.py
"""
import os
import sqlite3
import sys

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "data", "question_bank.db")

ROWS = [
    ("成长", "开卷有益", "📖", "首次读完 1 篇备考资料", 10, "material", "material_read_count", 1, 50),
    ("成长", "勤读不辍", "📚", "累计读完 10 篇备考资料", 40, "material", "material_read_count", 10, 51),
    ("成长", "博览群书", "🏛️", "累计读完 50 篇备考资料", 100, "material", "material_read_count", 50, 52),
]


def main() -> int:
    if not os.path.exists(DB):
        print(f"[FAIL] 数据库不存在: {DB}")
        return 1
    con = sqlite3.connect(DB)
    created = 0
    for cat, name, icon, desc, coins, trig, code, th, sort in ROWS:
        exists = con.execute(
            "SELECT achievement_id FROM achievement WHERE name=? AND trigger_type=?",
            (name, trig)).fetchone()
        if exists:
            print(f"  跳过（已存在）：{name} (#{exists[0]})")
            continue
        con.execute(
            "INSERT INTO achievement(category,name,icon,condition_desc,reward_coins,"
            "trigger_type,condition_code,threshold,sort_order) VALUES(?,?,?,?,?,?,?,?,?)",
            (cat, name, icon, desc, coins, trig, code, th, sort))
        created += 1
        print(f"  新增：{name} 阈值={th} 奖励={coins}币")
    con.commit()
    total = con.execute(
        "SELECT COUNT(*) FROM achievement WHERE trigger_type='material'").fetchone()[0]
    con.close()
    print(f"\n完成：本次新增 {created} 条；material 成就共 {total} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
