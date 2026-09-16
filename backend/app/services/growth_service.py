"""
学习等级服务：成长值累加 + 等级/进度计算

等级阈值：Lv.n 累计成长值 = round(100 × (n-1)^1.6)，n=2..10，Lv.1 = 0
成长值只增不减，增量写入 SysUser.growth_points，可全量重算。
"""
import logging
from sqlalchemy.orm import Session

from ..models.models import SysUser

logger = logging.getLogger(__name__)

# 成长值规则（只增不减）
GROWTH_RULES = {
    "correct_answer": 2,    # 做对一题
    "wrong_answer": 1,      # 做错一题
    "checkin": 5,           # 完成一次签到
    "checkin_7day": 20,     # 连续签到满7天
    "achievement": 15,      # 获得一枚成就
    "exam_done": 10,        # 完成一套试卷/模考
}

# 等级阈值与称号（10 级）
_LEVEL_TITLES = {
    1: "新手学员", 2: "入门学员", 3: "进阶学员", 4: "勤学学员", 5: "专注学员",
    6: "资深学员", 7: "优秀学员", 8: "精英学员", 9: "学霸", 10: "砺安大师",
}


def level_threshold(n: int) -> int:
    """第 n 级的累计成长值阈值（Lv.1 = 0）"""
    if n <= 1:
        return 0
    return int(round(100 * ((n - 1) ** 1.6)))


def get_level_info(growth_points: int) -> dict:
    """根据成长值计算等级、称号、进度"""
    growth = max(0, int(growth_points or 0))
    level = 1
    for n in range(2, 11):
        if growth >= level_threshold(n):
            level = n
        else:
            break

    title = _LEVEL_TITLES.get(level, "新手学员")

    if level >= 10:
        progress = 100
    else:
        cur = level_threshold(level)
        nxt = level_threshold(level + 1)
        progress = round((growth - cur) / (nxt - cur) * 100, 1) if nxt > cur else 0

    return {
        "level": level,
        "title": title,
        "growth_points": growth,
        "current_threshold": level_threshold(level),
        "next_threshold": level_threshold(level + 1) if level < 10 else None,
        "progress": progress,
    }


def add_growth(db: Session, user: SysUser, points: int) -> int:
    """累加成长值（只增不减），返回最新成长值。不 commit，由调用方统一提交。"""
    if points <= 0:
        return user.growth_points or 0
    user.growth_points = (user.growth_points or 0) + points
    logger.info(f"成长值 +{points} → 用户 {user.user_id} 当前 {user.growth_points}")
    return user.growth_points
