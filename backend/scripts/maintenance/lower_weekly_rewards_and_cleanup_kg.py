#!/usr/bin/env python3
"""周任务奖励下调 + 旧周知识图谱任务清理（2026-11-17）。

做两件事：
1. 把「全站周任务」（personalized_for 为空）的基础金币按难度统一到 30~45：
   难度 1.6 -> 45 / 1.4 -> 40 / 1.2 -> 35 / 1.1 & 1.0 -> 30
   生效值 = 基础 × 难度 × 稀缺（置顶 1.30/1.45/1.50），落在 30~72，不再碾压日任务。
2. 清掉非本周的知识图谱个性化任务（kg_<周>_<用户>_<考点>）及其进度行；
   已有领取记录的保留（避免台账对不上），并在报告里列出。

默认 dry-run，只打印将修改什么；确认后加 --apply 才写库。
写库前用 sqlite3.backup() 做整库备份（R10：禁用 shutil.copy2）。

用法：
    python backend/scripts/maintenance/lower_weekly_rewards_and_cleanup_kg.py
    python backend/scripts/maintenance/lower_weekly_rewards_and_cleanup_kg.py --apply
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEFAULT_DB = REPO / "backend" / "data" / "example_db.sqlite"

DIFFICULTY_TO_BASE = {1.6: 45, 1.5: 42, 1.4: 40, 1.3: 38, 1.2: 35, 1.1: 30, 1.0: 30}


def week_key(d: date | None = None) -> str:
    d = d or date.today()
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        sys.exit("[X] 数据库不存在：" + str(db_path))

    backup_path = None
    if args.apply:
        backup_path = db_path.parent / ("backup_rewards_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".sqlite")
        src = sqlite3.connect(str(db_path))
        dst = sqlite3.connect(str(backup_path))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("== 周任务奖励（全站）==")
    rows = cur.execute(
        "SELECT task_id, task_code, title, reward_coins, difficulty_factor FROM badge_task "
        "WHERE t_type='weekly' AND personalized_for IS NULL ORDER BY reward_coins DESC"
    ).fetchall()
    changes = []
    for r in rows:
        diff = round(float(r["difficulty_factor"] or 1.0), 1)
        target = DIFFICULTY_TO_BASE.get(diff)
        if target is None:
            target = DIFFICULTY_TO_BASE[1.0]
        if int(r["reward_coins"] or 0) != target:
            changes.append({
                "task_id": r["task_id"],
                "task_code": r["task_code"],
                "title": r["title"],
                "difficulty": diff,
                "old_base": r["reward_coins"],
                "new_base": target,
                "old_effective": int(round((r["reward_coins"] or 0) * diff)),
                "new_effective": int(round(target * diff)),
            })
    for c in changes:
        print("  %-24s 难度 %.1f  %s -> %s（生效 %s -> %s）" % (
            c["task_code"], c["difficulty"], c["old_base"], c["new_base"],
            c["old_effective"], c["new_effective"],
        ))
    if not changes:
        print("  已经是最新价，无需修改")

    week = week_key()
    print()
    print("== 旧周图谱任务清理（本周 " + week + "）==")
    kg_rows = cur.execute(
        "SELECT task_id, task_code, title, personalized_for FROM badge_task "
        "WHERE t_type='weekly' AND personalized_for IS NOT NULL "
        "AND task_code NOT LIKE ? ORDER BY task_id",
        ("kg_" + week + "_%",),
    ).fetchall()
    deletable, kept = [], []
    for r in kg_rows:
        claimed = cur.execute(
            "SELECT 1 FROM user_task_progress WHERE task_id=? AND claimed=1 LIMIT 1",
            (r["task_id"],),
        ).fetchone()
        (kept if claimed else deletable).append(dict(r))
        print("  %-28s user=%s  %s" % (
            r["task_code"], r["personalized_for"], "保留（已有领取记录）" if claimed else "删除",
        ))
    print("  合计：删除 %d 条，保留 %d 条" % (len(deletable), len(kept)))

    if args.apply:
        with conn:
            for c in changes:
                cur.execute("UPDATE badge_task SET reward_coins=? WHERE task_id=?", (c["new_base"], c["task_id"]))
            for r in deletable:
                cur.execute("DELETE FROM user_task_progress WHERE task_id=?", (r["task_id"],))
                cur.execute("DELETE FROM badge_task WHERE task_id=?", (r["task_id"],))
        print()
        print("已写入：奖励 %d 条，删除任务 %d 条，备份 %s" % (
            len(changes), len(deletable), backup_path.name if backup_path else "-",
        ))
    else:
        print()
        print("dry-run：未写库。确认后加 --apply。")

    conn.close()
    print(json.dumps({
        "week": week,
        "reward_changes": len(changes),
        "kg_deleted": len(deletable),
        "kg_kept_claimed": len(kept),
        "backup": str(backup_path) if backup_path else None,
        "mode": "apply" if args.apply else "dry-run",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
