# -*- coding: utf-8 -*-
"""修复「AI 学习计划任务被刷题量误判完成」的历史数据（2026-11-23）

背景
----
修复前 `services/goal_progress.sync_goal_progress()` 把 CUSTOM 与 DAILY 同口径，
按「当天刷题量」重算进度；而 AI 学习计划生成的任务是 `goal_type=CUSTOM`、
`target_count=1`，于是**做任意 1 道题**就把"申论大作文 1 篇 / 睡前错题复盘"这类任务
判成 100% 并标记完成、自动发金币。

代码已修（plan_id 非空的计划任务只由用户勾选完成），本脚本负责把历史上被误判的记录回到未完成。

用法（默认只看不改）
    python scripts/fix_plan_task_false_completion.py
    python scripts/fix_plan_task_false_completion.py --days 7
    python scripts/fix_plan_task_false_completion.py --apply

口径
----
- 只处理 `plan_id IS NOT NULL AND status = 1 AND is_completed = 1` 的计划任务；
- 跳过 target_count > 1 的（手动刷题目标不在此列）；
- 只回退完成标记（is_completed/current_count/completed_time），**不回收已发金币**，
  但会打印这些任务是否领过币，供人工判断是否需要补偿；
- 幂等：重复执行不会重复改动。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal  # noqa: E402
from app.models.models import StudyGoal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="回退计划任务的历史误判完成")
    parser.add_argument("--days", type=int, default=30, help="只看最近 N 天创建的任务（默认 30）")
    parser.add_argument("--apply", action="store_true", help="真正写库（默认 dry-run）")
    parser.add_argument("--user-id", type=int, default=0, help="只处理某个用户（0=全部）")
    args = parser.parse_args()

    since = datetime.now() - timedelta(days=args.days)
    db = SessionLocal()
    try:
        query = db.query(StudyGoal).filter(
            StudyGoal.plan_id.isnot(None),
            StudyGoal.status == 1,
            StudyGoal.is_completed == 1,
            StudyGoal.target_count <= 1,
            StudyGoal.create_time >= since,
        )
        if args.user_id:
            query = query.filter(StudyGoal.user_id == args.user_id)
        rows = query.order_by(StudyGoal.goal_id.asc()).all()

        print(f"计划任务误判完成候选：{len(rows)} 条（最近 {args.days} 天）")
        if not rows:
            print("没有需要修复的数据。")
            return 0

        for g in rows:
            print(
                f"  goal_id={g.goal_id} user={g.user_id} plan={g.plan_id} "
                f"count={g.current_count}/{g.target_count} reward={g.reward_coins or 0} "
                f"claimed={g.coin_claimed} done_at={g.completed_time} title={g.title[:24]}"
            )

        if not args.apply:
            print("\n[dry-run] 以上仅预览；确认后加 --apply 执行。")
            return 0

        changed = 0
        for g in rows:
            g.is_completed = 0
            g.current_count = 0
            g.completed_time = None
            # 不回收金币，也不重发：把 reward_coins 清零，避免再次完成时按旧奖励直接入账
            g.reward_coins = 0
            g.coin_claimed = 0
            changed += 1
        db.commit()
        print(f"\n已回退 {changed} 条计划任务的完成标记（金币未回收，如需补偿请人工处理）。")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
