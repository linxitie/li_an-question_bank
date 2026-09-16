"""
学习等级成长值历史数据回填脚本
================================
根据历史数据回填 SysUser.growth_points（幂等，可重复运行）：

成长值规则（与 growth_service.GROWTH_RULES 一致）：
- 做对一题 +2，做错一题 +1（PracticeRecord）
- 每日签到 +5，连续签到满7天额外 +20（DailyCheckin，continuous_days % 7 == 0）
- 获得一枚成就 +15（UserAchievement）

用法:
    python scripts/backfill_growth_points.py --dry-run   # 仅报告（默认）
    python scripts/backfill_growth_points.py --apply     # 实际写入
"""
import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func
from app.core.database import SessionLocal
from app.models.models import SysUser, PracticeRecord, DailyCheckin, UserAchievement

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def compute_growth(db, user_id: int) -> int:
    """计算某用户的成长值"""
    # 做题成长
    correct = db.query(PracticeRecord).filter(
        PracticeRecord.user_id == user_id, PracticeRecord.is_correct == 1
    ).count()
    wrong = db.query(PracticeRecord).filter(
        PracticeRecord.user_id == user_id, PracticeRecord.is_correct == 0
    ).count()
    practice_growth = correct * 2 + wrong * 1

    # 签到成长
    checkins = db.query(DailyCheckin).filter(DailyCheckin.user_id == user_id).all()
    checkin_base = len(checkins) * 5
    streak_bonus = sum(20 for c in checkins if (c.continuous_days or 0) % 7 == 0)
    checkin_growth = checkin_base + streak_bonus

    # 成就成长
    achievement_count = db.query(UserAchievement).filter(
        UserAchievement.user_id == user_id
    ).count()
    achievement_growth = achievement_count * 15

    return practice_growth + checkin_growth + achievement_growth


def main():
    parser = argparse.ArgumentParser(description="回填学习等级成长值")
    parser.add_argument("--dry-run", action="store_true", help="仅报告，不写入（默认）")
    parser.add_argument("--apply", action="store_true", help="实际写入")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        users = db.query(SysUser).all()
        total = 0
        changed = 0
        for user in users:
            computed = compute_growth(db, user.user_id)
            current = user.growth_points or 0
            total += 1
            if computed != current:
                changed += 1
                if args.apply:
                    user.growth_points = computed
                logger.info(f"user_id={user.user_id} 当前={current} 计算={computed}")

        if args.apply:
            db.commit()
            logger.info(f"已写入 {changed}/{total} 个用户的成长值")
        else:
            logger.info(f"[DRY-RUN] 共 {total} 个用户，{changed} 个需要回填")
            logger.info("使用 --apply 实际写入")
    finally:
        db.close()


if __name__ == "__main__":
    main()
