"""
成就 API：全部成就列表（含进度）/ 已获得 / 进度
"""
from typing import Dict, Any, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import SysUser, Achievement, UserAchievement
from ....services import achievement_service

router = APIRouter(prefix="/api/achievements", tags=["成就"])


def _get_progress(user_id: int, db: Session) -> Dict[str, Any]:
    """计算各 condition_code 的当前进度值（供前端展示进度条）"""
    from ....services.achievement_service import (
        _count_practice, _total_review_count, _total_chop_count, _post_count,
        _total_likes, _single_post_likes, _subject_counts, _month_study_days,
    )
    from ....models.models import FavoriteQuestion, QuestionNote, NewsNote, QuoteFavorite

    user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
    fav = db.query(FavoriteQuestion).filter(FavoriteQuestion.user_id == user_id).count()
    qn = db.query(QuestionNote).filter(QuestionNote.user_id == user_id).count()
    nn = db.query(NewsNote).filter(NewsNote.user_id == user_id).count()
    qf = db.query(QuoteFavorite).filter(QuoteFavorite.user_id == user_id).count()
    subject_counts = _subject_counts(user_id, db)

    streak_days = user.continuous_checkin_days if user else 0
    accuracy80_streak = user.accuracy80_streak if user else 0
    perfect_streak = user.perfect_streak if user else 0
    growth_points = user.growth_points if user else 0
    total_coins = user.total_coins if user else 0

    return {
        "total_questions": _count_practice(user_id, db),
        "today_questions": _count_practice(user_id, db, days=0),
        "week_questions": _count_practice(user_id, db, week=True),
        "streak_days": streak_days or 0,
        "month_days": _month_study_days(user_id, db),
        "review_count": _total_review_count(user_id, db),
        "chop_count": _total_chop_count(user_id, db),
        "post_count": _post_count(user_id, db),
        "total_likes": _total_likes(user_id, db),
        "single_post_likes": _single_post_likes(user_id, db),
        "favorite_count": fav,
        "note_count": qn + nn,
        "quote_favorite_count": qf,
        "accuracy80_streak": accuracy80_streak or 0,
        "perfect_streak": perfect_streak or 0,
        "level": achievement_service.get_level_info(growth_points or 0)["level"],
        "total_coins": total_coins or 0,
        "subject_counts": subject_counts,
    }


@router.get("", summary="全部成就列表（含已获得标记与进度）")
async def list_achievements(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """返回 45 项成就，标注已获得与实时进度"""
    achievements = db.query(Achievement).order_by(Achievement.sort_order).all()
    obtained = {
        r[0]: (r[1] or 1)
        for r in db.query(UserAchievement.achievement_id, UserAchievement.tier).filter(
            UserAchievement.user_id == current_user.user_id
        ).all()
    }
    progress = _get_progress(current_user.user_id, db)

    categories: Dict[str, List[Dict[str, Any]]] = {}
    for a in achievements:
        item = {
            "achievement_id": a.achievement_id,
            "category": a.category,
            "name": a.name,
            "icon": a.icon,
            "condition_desc": a.condition_desc,
            "reward_coins": a.reward_coins,
            "condition_code": a.condition_code,
            "threshold": a.threshold,
            "extra": a.extra,
            "earned": a.achievement_id in obtained,
            "tier": obtained.get(a.achievement_id, 0),
            "is_hidden": a.is_hidden or 0,
            "tier_times": a.tier_times,
            "style_params": a.style_params,
            "current": progress.get(a.condition_code, 0),
        }
        categories.setdefault(a.category, []).append(item)

    return {
        "total": len(achievements),
        "earned_count": len(obtained),
        "progress": progress,
        "categories": categories,
    }


@router.get("/earned", summary="已获得成就列表")
async def earned_achievements(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    rows = db.query(UserAchievement, Achievement).join(
        Achievement, UserAchievement.achievement_id == Achievement.achievement_id
    ).filter(UserAchievement.user_id == current_user.user_id)\
        .order_by(UserAchievement.obtained_at.desc()).all()

    return {
        "earned_count": len(rows),
        "items": [
            {
                "achievement_id": ua.achievement_id,
                "name": a.name,
                "icon": a.icon,
                "category": a.category,
                "condition_desc": a.condition_desc,
                "reward_coins": a.reward_coins,
                "tier": ua.tier or 1,
                "obtained_at": ua.obtained_at.isoformat() if ua.obtained_at else None,
            }
            for ua, a in rows
        ],
    }


@router.get("/progress", summary="未获得成就的实时进度")
async def progress_achievements(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _get_progress(current_user.user_id, db)
