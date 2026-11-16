"""周任务种子（2026-11-05 M2）：8 个 A/B/C 类周任务（幂等）。

对应《金币购体系_设计方案_v1》§3.3 的配置表：
| 类型 | 任务 | 指标 | 阈值 | 基础 | 难度 |
|---|---|---|---|---|---|
| A | 本周完成 300 道题 | week_questions | 300 | 200 | 1.6 |
| A | 本周完成 3 套真题 | week_exam_papers | 3 | 180 | 1.4 |
| A | 本周错题重做正确率 ≥80%（用本周正确率代理） | week_accuracy | 80 | 220 | 1.6 |
| B | 本周 5 天有刷题记录 | week_active_days | 5 | 150 | 1.2 |
| B | 本周 7 天每日≥10 题 | week_daily_practice_days | 7 | 200 | 1.4 |
| C | 2 套真题 → 解锁月卡 8 折券 | week_exam_papers | 2 | 120 | 1.0 |
| C | 本周正确率≥85% → 文具 9 折券 | week_accuracy | 85 | 120 | 1.1 |
| A | 本周完成 150 道题（入门档） | week_questions | 150 | 150 | 1.2 |

置顶由 weekly_task_pool 决定（前 3 个按 sort_order），不在这里写死。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal  # noqa: E402
from app.models.models import Task  # noqa: E402

TASKS = [
    # (code, title, desc, metric, threshold, base, difficulty, category, coupon, sort, pin_eligible)
    # 前 3 个设为可置顶（设计文档 §3.3 中的置顶样例）
    ("wk_questions_300", "本周完成 300 道题", "累计刷题 300 道", "week_questions", 300, 120, 1.6, "A", None, 1, 1),
    ("wk_exam_3", "本周完成 3 套真题", "完整做完并提交 3 套试卷", "week_exam_papers", 3, 110, 1.4, "A", None, 2, 1),
    ("wk_active_5", "本周 5 天有刷题记录", "本周至少 5 天保持练习", "week_active_days", 5, 90, 1.2, "B", None, 3, 1),
    ("wk_accuracy_80", "本周正确率 ≥80%", "本周答题正确率达到 80%", "week_accuracy", 80, 130, 1.6, "A", None, 4, 0),
    ("wk_daily_7", "本周 7 天每日≥10 题", "连续型：每天至少 10 题的打卡节奏", "week_daily_practice_days", 7, 120, 1.4, "B", None, 5, 0),
    ("wk_questions_150", "本周完成 150 道题", "入门档刷题目标", "week_questions", 150, 90, 1.2, "A", None, 6, 0),
    ("wk_exam_2_coupon", "完成 2 套真题 → 月卡 8 折券", "完成 2 套真题解锁题库月卡 8 折券", "week_exam_papers", 2, 70, 1.0, "C", "MONTH_CARD_20OFF", 7, 0),
    ("wk_accuracy_85_coupon", "本周正确率 ≥85% → 文具 9 折券", "正确率达标解锁文具套装 9 折券", "week_accuracy", 85, 70, 1.1, "C", "STATIONERY_10OFF", 8, 0),
]


def main() -> None:
    db = SessionLocal()
    created, updated = 0, 0
    try:
        for code, title, desc, metric, threshold, base, difficulty, category, coupon, sort, pin in TASKS:
            task = db.query(Task).filter(Task.task_code == code).first()
            if task:
                changed = False
                for field, value in (
                    ("t_type", "weekly"),
                    ("metric", metric),
                    ("threshold", threshold),
                    ("difficulty_factor", difficulty),
                    ("category", category),
                    ("coupon_code", coupon),
                    ("pin_eligible", pin),
                ):
                    if getattr(task, field) != value:
                        setattr(task, field, value)
                        changed = True
                if changed:
                    updated += 1
                continue

            db.add(
                Task(
                    task_code=code,
                    t_type="weekly",
                    title=title,
                    description=desc,
                    metric=metric,
                    mode="calc",
                    threshold=threshold,
                    reward_coins=base,
                    reward_growth=0,
                    difficulty_factor=difficulty,
                    scarcity_factor=1.0,
                    category=category,
                    coupon_code=coupon,
                    pin_eligible=pin,
                    sort_order=sort,
                    enabled=1,
                )
            )
            created += 1

        db.commit()
        total = db.query(Task).filter(Task.t_type == "weekly").count()
        print(f"周任务：新增 {created} / 更新 {updated} / 当前共 {total}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
