"""金币产出再平衡（2026-11-05）。

用户反馈「金币挣得太快」：任务奖励偏高，最便宜商品 800 币，一周就能换。

策略：把任务奖励整体下调（不与商品涨价叠加，避免双重削弱）：
- 周任务基础值 × 0.6（置顶 416 → 250 左右）
- 每日/随机任务 × 0.7
- 签到保持（习惯触发，金额本来就低）

幂等：脚本执行两次结果一致（按目标值直接写）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.models.models import Task  # noqa: E402

WEEKLY_MULTIPLIER = 0.6
DAILY_MULTIPLIER = 0.7
MIN_REWARD = 20


def rebalance(value: int, multiplier: float) -> int:
    return max(MIN_REWARD, int(round((value or 0) * multiplier / 10.0) * 10))


def main() -> None:
    db = SessionLocal()
    changed = 0
    try:
        tasks = db.query(Task).filter(Task.enabled == 1).all()
        for t in tasks:
            if t.t_type == "weekly" and not t.personalized_for:
                target = rebalance(t.reward_coins, WEEKLY_MULTIPLIER)
            elif t.t_type in ("daily", "random"):
                target = rebalance(t.reward_coins, DAILY_MULTIPLIER)
            else:
                continue
            if (t.reward_coins or 0) != target:
                t.reward_coins = target
                changed += 1
        db.commit()

        print(f"调整任务 {changed} 个")
        print("=== 周任务（含置顶加成后的实际发放）===")
        from app.services import weekly_tasks as weekly

        slots = weekly.pinned_slots(db)
        for t in (
            db.query(Task)
            .filter(Task.t_type == "weekly", Task.enabled == 1, Task.personalized_for.is_(None))
            .order_by(Task.sort_order.asc())
            .all()
        ):
            slot = slots.get(t.task_id, 0)
            scarcity = weekly.PINNED_SCARCITY.get(slot)
            print(
                f"  {t.title[:22]:<24} base={t.reward_coins:>4} "
                f"难度={float(t.difficulty_factor or 1):.1f} "
                f"置顶={'是' if slot else '否'} 实发={weekly.effective_reward(t, scarcity)}"
            )
        print("=== 每日/随机任务 ===")
        for t in (
            db.query(Task)
            .filter(Task.t_type.in_(["daily", "random"]), Task.enabled == 1)
            .order_by(Task.task_id.asc())
            .all()
        ):
            print(f"  {t.title[:22]:<24} {t.reward_coins} 币")
    finally:
        db.close()


if __name__ == "__main__":
    main()
