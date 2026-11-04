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

# ==================== T1 管理员新建成就（词库自动命名） ====================
def _require_admin(user: SysUser) -> None:
    if (getattr(user, "user_type", "") or "").lower() not in ("admin", "super_admin"):
        from fastapi import HTTPException
        raise HTTPException(403, "需要管理员权限")


def _pick_bank_name(db: Session, category: str, taken: set) -> tuple:
    """按类别取一条未占用的词库名；同类别优先，再退化为任意未用。"""
    from ....models.models import BadgeNameBank
    for scope in (True, False):
        q = db.query(BadgeNameBank).filter(BadgeNameBank.used == 0)
        if scope and category:
            q = q.filter(BadgeNameBank.category == category)
        rows = q.order_by(BadgeNameBank.score.desc(), BadgeNameBank.id).limit(50).all()
        for r in rows:
            nm = (r.name or "").strip()
            if nm and nm not in taken:
                return r, nm
    return None, None


@router.post("/admin", summary="新建成就徽章（管理员，词库自动命名）")
async def admin_create_achievement(
    body: dict,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """新建一枚成就徽章。

    - `name` 缺省时从 `badge_name_bank` 取未用名（同类别优先），并置 `used=1`
    - `badge_tier` 缺省时按 `condition_code + threshold` 推导（固定成色，不随数据变）
    - 词库耗尽且未显式给 name → 409
    """
    from fastapi import HTTPException
    from sqlalchemy import func
    from ....services import badge_service

    _require_admin(current_user)
    category = (body.get("category") or "").strip()
    code = (body.get("condition_code") or "").strip()
    if not category or not code:
        raise HTTPException(400, "category 与 condition_code 必填")
    try:
        threshold = int(body.get("threshold") or 0)
    except (TypeError, ValueError):
        raise HTTPException(400, "threshold 必须是整数")

    taken = {n for (n,) in db.query(Achievement.name).all()}
    name = (body.get("name") or "").strip()
    bank_row = None
    if not name:
        bank_row, name = _pick_bank_name(db, category, taken)
        if not name:
            raise HTTPException(409, "命名词库已耗尽，请显式提供 name 或先补充词库")
    elif name in taken:
        raise HTTPException(409, f"成就名「{name}」已存在")

    tier = (body.get("badge_tier") or "").strip() or \
        badge_service.tier_for_condition(code, threshold)
    if tier not in ("黑铁", "青铜", "白银", "黄金", "钻石"):
        raise HTTPException(400, "badge_tier 非法")

    max_sort = db.query(func.max(Achievement.sort_order)).scalar() or 0
    a = Achievement(
        name=name, category=category, condition_code=code, threshold=threshold,
        condition_desc=(body.get("condition_desc") or f"达成 {code} ≥ {threshold}").strip(),
        reward_coins=int(body.get("reward_coins") or 0),
        trigger_type=(body.get("trigger_type") or "general").strip(),
        badge_tier=tier, sort_order=max_sort + 1, is_hidden=bool(body.get("hidden")),
    )
    db.add(a)
    if bank_row is not None:
        bank_row.used = 1
    db.commit()
    db.refresh(a)
    return {
        "id": a.achievement_id,
        "name": a.name,
        "category": a.category,
        "badge_tier": a.badge_tier,
        "threshold": a.threshold,
        "named_from_bank": bank_row is not None,
        "bank_id": getattr(bank_row, "id", None),
    }


@router.get("/name-bank/status", summary="命名词库余量（管理员）")
async def name_bank_status(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ....models.models import BadgeNameBank
    _require_admin(current_user)
    total = db.query(BadgeNameBank).count()
    used = db.query(BadgeNameBank).filter(BadgeNameBank.used != 0).count()
    return {"total": total, "used": used, "left": total - used}
