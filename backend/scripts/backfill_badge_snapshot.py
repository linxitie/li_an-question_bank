# -*- coding: utf-8 -*-
"""S5-1b：回填历史 user_achievement.tier_snapshot（按当前累计积分估算）。"""
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "question_bank.db")
THRESHOLDS = [(0, 0), (200, 1), (400, 2), (600, 3), (800, 4)]


def tier_index(score: int) -> int:
    idx = 0
    for low, i in THRESHOLDS:
        if score >= low:
            idx = i
    return idx


def main() -> int:
    if not os.path.exists(DB):
        print(f"[FAIL] 数据库不存在: {DB}")
        return 1
    con = sqlite3.connect(DB)
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(user_achievement)")]
        if "tier_snapshot" not in cols:
            print("[FAIL] 缺 tier_snapshot 列，请先执行迁移 20261029_001")
            return 1

        rows = con.execute(
            "SELECT id, user_id FROM user_achievement WHERE tier_snapshot IS NULL").fetchall()
        if not rows:
            print("没有需要回填的记录")
            return 0

        by_user: dict[int, list[int]] = {}
        for rec_id, uid in rows:
            by_user.setdefault(uid, []).append(rec_id)

        filled = 0
        for uid, ids in by_user.items():
            score = con.execute(
                "SELECT COALESCE(SUM(coin_change),0) FROM coin_record "
                "WHERE user_id=? AND coin_change>0", (uid,)).fetchone()[0] or 0
            idx = tier_index(int(score))
            con.executemany(
                "UPDATE user_achievement SET tier_snapshot=? WHERE id=?",
                [(idx, i) for i in ids])
            filled += len(ids)
            print(f"  用户 {uid}: 累计积分 {score} → 档位索引 {idx}，回填 {len(ids)} 条")
        con.commit()
        left = con.execute(
            "SELECT COUNT(*) FROM user_achievement WHERE tier_snapshot IS NULL").fetchone()[0]
        print(f"\n回填完成：{filled} 条；仍为空 {left} 条")
    finally:
        con.close()
    print("说明：历史数据按**当前**累计积分估算，无法还原发放当时的真实积分。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
