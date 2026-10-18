"""
成就判定与发放服务

45 项成就，覆盖学习坚持/做题数量/正确率/错题管理/社交互动/综合成就。
- 幂等：uk_user_achievement(user_id, achievement_id) 唯一约束，重复触发自动跳过
- 原子：成就插入 + 金币 + 流水 + 成长值在同一事务
- 可追溯：每次发放 logger.info + CoinRecord 流水
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import func, Date, cast
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.models import (
    SysUser, UserAchievement, Achievement, PracticeRecord,
    WrongQuestionPersonal, ForumPost, ForumComment, FavoriteQuestion,
    QuestionNote, NewsNote, QuoteFavorite, DailyCheckin,
)
from ..core.trigger_types import LEGACY_TRIGGER_ALIASES
from .growth_service import add_growth, get_level_info, GROWTH_RULES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 45 项成就目录（category, name, icon, desc, coins, trigger, condition_code, threshold, extra, sort）
# ---------------------------------------------------------------------------
ACHIEVEMENTS = [
    # 学习坚持类（trigger=sign_in）
    ("坚持", "初来乍到", "🌱", "首次登录系统", 10, "sign_in", "first_login", 0, None, 1),
    ("坚持", "连续学习3天", "🔥", "连续3天有学习记录", 30, "sign_in", "streak_days", 3, None, 2),
    ("坚持", "连续学习7天", "🔥", "连续7天有学习记录", 80, "sign_in", "streak_days", 7, None, 3),
    ("坚持", "连续学习15天", "🔥", "连续15天有学习记录", 150, "sign_in", "streak_days", 15, None, 4),
    ("坚持", "连续学习30天", "🔥", "连续30天有学习记录", 300, "sign_in", "streak_days", 30, None, 5),
    ("坚持", "月度学霸", "📅", "单月学习≥25天", 200, "sign_in", "month_days", 25, None, 6),
    ("坚持", "早起鸟", "🐦", "连续7天8:00前学习", 50, "sign_in", "morning_bird", 7, None, 7),
    ("坚持", "夜猫子", "🦉", "连续7天22:00后学习", 50, "sign_in", "night_owl", 7, None, 8),

    # 做题数量类（trigger=do_question）
    ("数量", "初试身手", "📝", "累计做题10道", 10, "do_question", "total_questions", 10, None, 10),
    ("数量", "小试牛刀", "📝", "累计做题50道", 20, "do_question", "total_questions", 50, None, 11),
    ("数量", "渐入佳境", "📝", "累计做题100道", 40, "do_question", "total_questions", 100, None, 12),
    ("数量", "勤学苦练", "📝", "累计做题500道", 80, "do_question", "total_questions", 500, None, 13),
    ("数量", "千题斩", "⚔️", "累计做题1,000道", 150, "do_question", "total_questions", 1000, None, 14),
    ("数量", "三千题", "⚔️", "累计做题3,000道", 300, "do_question", "total_questions", 3000, None, 15),
    ("数量", "五千题", "⚔️", "累计做题5,000道", 500, "do_question", "total_questions", 5000, None, 16),
    ("数量", "万题王", "👑", "累计做题10,000道", 1000, "do_question", "total_questions", 10000, None, 17),
    ("数量", "单日百题", "🚀", "单日做题100道", 50, "do_question", "today_questions", 100, None, 18),
    ("数量", "周做题达人", "🏃", "单周做题500道", 100, "do_question", "week_questions", 500, None, 19),

    # 正确率类（trigger=do_question，session 相关）
    ("正确率", "首战告捷", "✅", "首次全部答对", 20, "do_question", "session_perfect_any", 0, None, 20),
    ("正确率", "满分王", "🥉", "单次练习全部答对（≥20题）", 50, "do_question", "session_perfect", 20, None, 21),
    ("正确率", "精准射手", "🎯", "单次练习正确率≥90%", 40, "do_question", "session_accuracy", 90, None, 22),
    ("正确率", "稳如泰山", "🧘", "连续3次练习正确率≥80%", 60, "do_question", "accuracy80_streak", 3, None, 23),
    ("正确率", "正确率之星", "⭐", "周正确率≥85%（≥100题）", 80, "do_question", "week_accuracy", 85, "100", 24),
    ("正确率", "常胜将军", "🏆", "连续10次练习正确率≥80%", 100, "do_question", "accuracy80_streak", 10, None, 25),
    ("正确率", "完美主义", "💎", "连续5次练习全部答对", 150, "do_question", "perfect_streak", 5, None, 26),
    ("正确率", "正确率大师", "👑", "月正确率≥85%（≥500题）", 200, "do_question", "month_accuracy", 85, "500", 27),

    # 错题管理类
    ("错题", "直面错误", "👀", "首次查看错题集", 10, "view_wrong", "view_wrong_first", 0, None, 30),
    ("错题", "错题复习者", "🔄", "完成10道错题重练", 30, "review", "review_count", 10, None, 31),
    ("错题", "错题终结者", "🏅", "完成50道错题重练", 80, "review", "review_count", 50, None, 32),
    ("错题", "斩题新手", "🎯", "首次斩题", 20, "chop", "chop_count", 1, None, 33),
    ("错题", "斩题达人", "🎖️", "累计斩题50道", 100, "chop", "chop_count", 50, None, 34),
    ("错题", "斩题大师", "👑", "累计斩题200道", 300, "chop", "chop_count", 200, None, 35),

    # 社交互动类（trigger=post）
    ("社交", "初次发声", "💬", "首次发布帖子/评论", 15, "post", "post_count", 1, None, 40),
    ("社交", "论坛活跃者", "🎖️", "发布10条帖子/评论", 50, "post", "post_count", 10, None, 41),
    ("社交", "热门楼主", "🔥", "单帖获得50个赞", 80, "post", "single_post_likes", 50, None, 42),
    ("社交", "获赞达人", "⭐", "累计获得100个赞", 100, "post", "total_likes", 100, None, 43),
    ("社交", "解答高手", "🏆", "累计获赞300次", 150, "post", "total_likes", 300, None, 44),
    ("社交", "社区领袖", "👑", "发布100条帖子/评论", 200, "post", "post_count", 100, None, 45),

    # 综合成就类（trigger=general 或具体行为）
    ("综合", "全能选手", "🌟", "完成行测/申论/公专各100题", 150, "general", "three_subject_each", 100, None, 50),
    ("综合", "三科精通", "🎓", "三科正确率均≥75%", 200, "general", "three_subject_accuracy", 75, None, 51),
    ("综合", "等级达人", "📈", "学习等级达到Lv.10", 300, "general", "level_reach", 10, None, 52),
    ("综合", "金币富翁", "💰", "累计获得10,000金币", 200, "general", "total_coins", 10000, None, 53),
    ("综合", "收藏家", "⭐", "收藏100道题目", 100, "favorite", "favorite_count", 100, None, 54),
    ("综合", "笔记达人", "📓", "添加50条学习笔记", 80, "note", "note_count", 50, None, 55),
    ("综合", "金句收藏家", "📚", "收藏100条金句", 60, "quote_favorite", "quote_favorite_count", 100, None, 56),
]

_TRIGGERS = {a[5] for a in ACHIEVEMENTS}

# 支持五档升档的成就（累计数量型，condition_code 维度）
TIERED_CODES = {
    "total_questions", "today_questions", "week_questions",
    "review_count", "chop_count", "post_count", "total_likes",
    "favorite_count", "note_count", "quote_favorite_count",
}
# 五档达成倍数（档位 = 达到 threshold × 倍数的最高档）
TIER_TIMES = [1, 2, 4, 8, 16]


def _tier_times_for(code: str, threshold: int):
    """升档成就返回 TIER_TIMES，否则返回 None（不升档，固定 tier 1）"""
    if code in TIERED_CODES and threshold > 1:
        return TIER_TIMES
    return None


def _tier_for_value(threshold: int, current: int, tier_times) -> int:
    """根据当前达成值计算应达到的档位（1-5）"""
    tier = 0
    for mult in (tier_times or []):
        if current >= threshold * mult:
            tier += 1
        else:
            break
    return max(tier, 1)


def seed_achievements(db: Session) -> int:
    """初始化成就目录（幂等）：空则插入；已存在则补 tier_times"""
    for cat, name, icon, desc, coins, trigger, code, th, extra, sort in ACHIEVEMENTS:
        existing = db.query(Achievement).filter(Achievement.name == name).first()
        if existing:
            tt = _tier_times_for(code, th)
            if existing.tier_times is None and tt is not None:
                existing.tier_times = tt
            continue
        db.add(Achievement(
            category=cat, name=name, icon=icon, condition_desc=desc,
            reward_coins=coins, trigger_type=trigger, condition_code=code,
            threshold=th, extra=extra, sort_order=sort,
            tier_times=_tier_times_for(code, th),
        ))
    db.commit()
    total = db.query(Achievement).count()
    logger.info(f"成就目录初始化完成：{total} 项")
    return total


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def _trigger_candidates(trigger_type: str) -> List[str]:
    aliases = LEGACY_TRIGGER_ALIASES.get(trigger_type, ())
    return list(dict.fromkeys([trigger_type, *aliases, "general"]))


def check_and_grant(user_id: int, trigger_type: str, db: Session,
                    session: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    判定并发放成就。session 仅 do_question 触发时传入：
    { 'total': int, 'correct': int }（一次练习/交卷会话）
    返回 newly_unlocked 列表，供前端弹窗。
    """
    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    if not user:
        return []

    # 已获得成就 -> tier 映射
    obtained_map = {
        r[0]: (r[1] or 1)
        for r in db.query(UserAchievement.achievement_id, UserAchievement.tier).filter(
            UserAchievement.user_id == user_id
        ).all()
    }

    # 匹配触发类型 + 综合类（general 全触发）；新常量同时匹配历史建档值
    candidates = db.query(Achievement).filter(
        Achievement.trigger_type.in_(_trigger_candidates(trigger_type))
    ).all()

    newly: List[Dict[str, Any]] = []
    for ach in candidates:
        try:
            tier_times = ach.tier_times or []
            if tier_times:
                # 升档成就：计算当前达成值，判定获得/升档
                current = _current_value(user, ach, db)
                if current < ach.threshold:
                    continue
                target_tier = _tier_for_value(ach.threshold, current, tier_times)
                if ach.achievement_id not in obtained_map:
                    _grant(user, ach, db, tier=target_tier)
                    newly.append(_newly_item(ach, target_tier, upgraded=False))
                else:
                    existing_tier = obtained_map[ach.achievement_id]
                    if target_tier > existing_tier:
                        _upgrade_tier(user, ach, db, target_tier)
                        newly.append(_newly_item(ach, target_tier, upgraded=True))
            else:
                # 不升档成就：仅判定新获得
                if ach.achievement_id in obtained_map:
                    continue
                if _check_condition(user, ach, db, session):
                    _grant(user, ach, db, tier=1)
                    newly.append(_newly_item(ach, 1, upgraded=False))
        except Exception as e:
            db.rollback()
            logger.error(f"成就判定异常 user={user_id} ach={ach.name}: {e}")

    if newly:
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            logger.warning(f"成就发放并发冲突 user={user_id}，已回滚（唯一约束兜底）")
            newly = []

    return newly


def _newly_item(ach: Achievement, tier: int, upgraded: bool) -> Dict[str, Any]:
    return {
        "achievement_id": ach.achievement_id,
        "name": ach.name,
        "icon": ach.icon,
        "reward_coins": ach.reward_coins,
        "tier": tier,
        "upgraded": upgraded,
    }


# ---------------------------------------------------------------------------
# 内部实现
# ---------------------------------------------------------------------------

def _obtained_ids(user_id: int, db: Session) -> set:
    rows = db.query(UserAchievement.achievement_id).filter(
        UserAchievement.user_id == user_id
    ).all()
    return {r[0] for r in rows}


def _grant(user: SysUser, ach: Achievement, db: Session, tier: int = 1):
    """发放成就（同一事务）：插入成就 + 加金币 + 写流水 + 加成长值"""
    db.add(UserAchievement(user_id=user.user_id, achievement_id=ach.achievement_id, tier=tier))

    if ach.reward_coins > 0:
        # 跨域写入走 reward 契约（P4.2），禁止直接实例化他域表
        from ..api.v1.reward.contract import grant_coins
        grant_coins(db, user, ach.reward_coins, source_type="SYSTEM",
                    description=f"获得成就：{ach.name}")

    add_growth(db, user, GROWTH_RULES["achievement"])
    logger.info(f"用户 {user.user_id} 获得成就「{ach.name}」tier={tier}，奖励 {ach.reward_coins} 金币")


def _upgrade_tier(user: SysUser, ach: Achievement, db: Session, tier: int):
    """升级成就档位（tier 只增不减）"""
    ua = db.query(UserAchievement).filter(
        UserAchievement.user_id == user.user_id,
        UserAchievement.achievement_id == ach.achievement_id
    ).first()
    if ua and (ua.tier or 1) < tier:
        ua.tier = tier
        logger.info(f"用户 {user.user_id} 成就「{ach.name}」升级到 tier {tier}")


def _current_value(user: SysUser, ach: Achievement, db: Session) -> int:
    """计算升档成就的当前达成值（复用统计函数）"""
    code = ach.condition_code
    if code == "total_questions":
        return _count_practice(user.user_id, db)
    if code == "today_questions":
        return _count_practice(user.user_id, db, days=0)
    if code == "week_questions":
        return _count_practice(user.user_id, db, week=True)
    if code == "review_count":
        return _total_review_count(user.user_id, db)
    if code == "chop_count":
        return _total_chop_count(user.user_id, db)
    if code == "post_count":
        return _post_count(user.user_id, db)
    if code == "total_likes":
        return _total_likes(user.user_id, db)
    if code == "favorite_count":
        return db.query(FavoriteQuestion).filter(FavoriteQuestion.user_id == user.user_id).count()
    if code == "note_count":
        return (db.query(QuestionNote).filter(QuestionNote.user_id == user.user_id).count()
                + db.query(NewsNote).filter(NewsNote.user_id == user.user_id).count())
    if code == "quote_favorite_count":
        return db.query(QuoteFavorite).filter(QuoteFavorite.user_id == user.user_id).count()
    return 0


def _check_condition(user: SysUser, ach: Achievement, db: Session,
                     session: Optional[Dict[str, Any]]) -> bool:
    """按 condition_code 分发判定"""
    code = ach.condition_code
    th = ach.threshold

    if code == "first_login":
        return True  # 有用户即已登录过，幂等保证只发一次

    if code == "streak_days":
        return (user.continuous_checkin_days or 0) >= th

    if code == "month_days":
        return _month_study_days(user.user_id, db) >= th

    if code == "morning_bird":
        return _time_band_streak(user.user_id, db, before=8) >= th

    if code == "night_owl":
        return _time_band_streak(user.user_id, db, after=22) >= th

    if code == "total_questions":
        return _count_practice(user.user_id, db) >= th

    if code == "today_questions":
        return _count_practice(user.user_id, db, days=0) >= th

    if code == "week_questions":
        return _count_practice(user.user_id, db, week=True) >= th

    if code == "session_perfect_any":
        return bool(session) and session.get("total", 0) > 0 and session.get("correct", 0) == session.get("total", 0)

    if code == "session_perfect":
        return bool(session) and session.get("total", 0) >= th and session.get("correct", 0) == session.get("total", 0)

    if code == "session_accuracy":
        if not session or session.get("total", 0) <= 0:
            return False
        return session.get("correct", 0) / session.get("total", 0) * 100 >= th

    if code == "accuracy80_streak":
        return (user.accuracy80_streak or 0) >= th

    if code == "perfect_streak":
        return (user.perfect_streak or 0) >= th

    if code == "week_accuracy":
        min_q = int(ach.extra or 0)
        return _accuracy_in_range(user.user_id, db, days=7, min_questions=min_q) >= th

    if code == "month_accuracy":
        min_q = int(ach.extra or 0)
        return _accuracy_in_range(user.user_id, db, days=30, min_questions=min_q) >= th

    if code == "view_wrong_first":
        return True  # 触发即视为首次查看，幂等保证只发一次

    if code == "review_count":
        return _total_review_count(user.user_id, db) >= th

    if code == "chop_count":
        return _total_chop_count(user.user_id, db) >= th

    if code == "post_count":
        return _post_count(user.user_id, db) >= th

    if code == "single_post_likes":
        return _single_post_likes(user.user_id, db) >= th

    if code == "total_likes":
        return _total_likes(user.user_id, db) >= th

    if code == "three_subject_each":
        return min(_subject_counts(user.user_id, db).values(), default=0) >= th

    if code == "three_subject_accuracy":
        return _three_subject_accuracy(user.user_id, db, th)

    if code == "level_reach":
        return get_level_info(user.growth_points or 0)["level"] >= th

    if code == "total_coins":
        return (user.total_coins or 0) >= th

    if code == "favorite_count":
        return db.query(FavoriteQuestion).filter(FavoriteQuestion.user_id == user.user_id).count() >= th

    if code == "note_count":
        qn = db.query(QuestionNote).filter(QuestionNote.user_id == user.user_id).count()
        nn = db.query(NewsNote).filter(NewsNote.user_id == user.user_id).count()
        return (qn + nn) >= th

    if code == "quote_favorite_count":
        return db.query(QuoteFavorite).filter(QuoteFavorite.user_id == user.user_id).count() >= th

    return False


# ---------------------------------------------------------------------------
# 统计辅助
# ---------------------------------------------------------------------------

def _count_practice(user_id: int, db: Session, days: Optional[int] = None, week: bool = False) -> int:
    q = db.query(PracticeRecord).filter(PracticeRecord.user_id == user_id)
    if week:
        start = datetime.now() - timedelta(days=7)
        q = q.filter(PracticeRecord.practice_time >= start)
    elif days is not None:
        start = datetime.now() - timedelta(days=days)
        q = q.filter(PracticeRecord.practice_time >= start)
    return q.count()


def _month_study_days(user_id: int, db: Session) -> int:
    start = datetime.now().replace(day=1)
    rows = db.query(func.DATE(PracticeRecord.practice_time)).filter(
        PracticeRecord.user_id == user_id,
        PracticeRecord.practice_time >= start,
    ).distinct().all()
    return len(rows)


def _time_band_streak(user_id: int, db: Session, before: Optional[int] = None, after: Optional[int] = None) -> int:
    """连续 N 天在指定时段内有学习记录（自然日，跨数据库安全：Python 过滤小时）"""
    from datetime import time as _time
    today = datetime.now().date()
    streak = 0
    for i in range(30):
        day = today - timedelta(days=i)
        day_start = datetime.combine(day, _time.min)
        day_end = datetime.combine(day + timedelta(days=1), _time.min)
        rows = db.query(PracticeRecord.practice_time).filter(
            PracticeRecord.user_id == user_id,
            PracticeRecord.practice_time >= day_start,
            PracticeRecord.practice_time < day_end,
        ).all()
        hit = False
        for (pt,) in rows:
            if pt is None:
                continue
            h = pt.hour
            if before is not None and h < before:
                hit = True
                break
            if after is not None and h >= after:
                hit = True
                break
        if hit:
            streak += 1
        else:
            break
    return streak


def _accuracy_in_range(user_id: int, db: Session, days: int, min_questions: int) -> float:
    start = datetime.now() - timedelta(days=days)
    rows = db.query(PracticeRecord).filter(
        PracticeRecord.user_id == user_id,
        PracticeRecord.practice_time >= start,
    ).all()
    total = len(rows)
    if total < min_questions:
        return 0.0
    correct = sum(1 for r in rows if r.is_correct == 1)
    return round(correct / total * 100, 1)


def _total_review_count(user_id: int, db: Session) -> int:
    return db.query(func.coalesce(func.sum(WrongQuestionPersonal.review_count), 0)).filter(
        WrongQuestionPersonal.user_id == user_id
    ).scalar() or 0


def _total_chop_count(user_id: int, db: Session) -> int:
    return db.query(WrongQuestionPersonal).filter(
        WrongQuestionPersonal.user_id == user_id,
        WrongQuestionPersonal.is_cut == 1,
    ).count()


def _post_count(user_id: int, db: Session) -> int:
    posts = db.query(ForumPost).filter(
        ForumPost.user_id == user_id, ForumPost.status == "NORMAL"
    ).count()
    comments = db.query(ForumComment).filter(
        ForumComment.user_id == user_id, ForumComment.status == 1
    ).count()
    return posts + comments


def _single_post_likes(user_id: int, db: Session) -> int:
    max_like = db.query(func.max(ForumPost.like_count)).filter(
        ForumPost.user_id == user_id, ForumPost.status == "NORMAL"
    ).scalar() or 0
    return int(max_like)


def _total_likes(user_id: int, db: Session) -> int:
    post_likes = db.query(func.coalesce(func.sum(ForumPost.like_count), 0)).filter(
        ForumPost.user_id == user_id, ForumPost.status == "NORMAL"
    ).scalar() or 0
    comment_likes = db.query(func.coalesce(func.sum(ForumComment.like_count), 0)).filter(
        ForumComment.user_id == user_id, ForumComment.status == 1
    ).scalar() or 0
    return int(post_likes) + int(comment_likes)


def _subject_counts(user_id: int, db: Session) -> Dict[int, int]:
    rows = db.query(PracticeRecord.subject_id, func.count()).filter(
        PracticeRecord.user_id == user_id
    ).group_by(PracticeRecord.subject_id).all()
    return {r[0]: r[1] for r in rows if r[0]}


def _three_subject_accuracy(user_id: int, db: Session, threshold: int) -> bool:
    rows = db.query(PracticeRecord.subject_id, PracticeRecord.is_correct).filter(
        PracticeRecord.user_id == user_id,
        PracticeRecord.subject_id.in_([1, 2, 3]),
    ).all()
    from collections import defaultdict
    stat = defaultdict(lambda: [0, 0])  # subject -> [total, correct]
    for sid, correct in rows:
        stat[sid][0] += 1
        if correct == 1:
            stat[sid][1] += 1
    if len(stat) < 3:
        return False
    for sid in (1, 2, 3):
        total, correct = stat[sid]
        if total <= 0 or (correct / total * 100) < threshold:
            return False
    return True
