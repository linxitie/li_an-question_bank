# -*- coding: utf-8 -*-
"""growth 域对外读取契约（供其他域使用，避免跨域直接 import 模型）。

模块边界规则：library/badges 等域不得直接 import growth 域的
Achievement / UserAchievement / Title 模型；一律经由本契约。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ....models.models import Achievement, SysUser, Title, UserAchievement

__all__ = [
    "list_achievements",
    "count_achievements",
    "achievement_fields",
    "list_titles",
    "count_titles",
    "title_fields",
    "list_user_achievements",
    "count_user_achievements",
    "achievement_owner_counts",
    "total_users",
]


def list_achievements(db: Session, category: Optional[str] = None) -> List[Achievement]:
    q = db.query(Achievement)
    if category:
        q = q.filter(Achievement.category == category)
    return q.order_by(Achievement.sort_order.asc(),
                      Achievement.achievement_id.asc()).all()


def count_achievements(db: Session) -> int:
    return int(db.query(func.count(Achievement.achievement_id)).scalar() or 0)


def achievement_fields(a: Achievement) -> Dict[str, object]:
    """把成长域模型投影成中性 dict（其他域只依赖这个结构）。"""
    return {
        "id": a.achievement_id,
        "achievement_id": a.achievement_id,
        "name": a.name,
        "category": a.category,
        "icon": a.icon,
        "condition_desc": a.condition_desc,
        "reward_coins": a.reward_coins or 0,
        "threshold": a.threshold or 0,
        "badge_tier": getattr(a, "badge_tier", None),
        "hidden": bool(a.is_hidden),
    }


def list_titles(db: Session) -> List[Title]:
    return db.query(Title).order_by(Title.sort_order.asc()).all()


def count_titles(db: Session) -> int:
    return int(db.query(func.count(Title.title_id)).scalar() or 0)


def title_fields(t: Title) -> Dict[str, object]:
    return {
        "id": t.title_id,
        "name": t.name,
        "description": t.description,
        "unlock_level": t.unlock_level or 0,
    }


def list_user_achievements(db: Session, user_id: int) -> List[UserAchievement]:
    return (db.query(UserAchievement)
            .filter(UserAchievement.user_id == user_id)
            .order_by(UserAchievement.obtained_at.desc()).all())


def count_user_achievements(db: Session, user_id: int) -> int:
    return int(db.query(func.count(UserAchievement.id))
               .filter(UserAchievement.user_id == user_id).scalar() or 0)


def achievement_owner_counts(db: Session,
                             achievement_ids: Optional[List[int]] = None) -> Dict[int, int]:
    """每个成就的获得人数（供徽章稀有度）。"""
    q = db.query(UserAchievement.achievement_id,
                 func.count(UserAchievement.id)).group_by(UserAchievement.achievement_id)
    if achievement_ids:
        q = q.filter(UserAchievement.achievement_id.in_(achievement_ids))
    return {int(k): int(v) for k, v in q.all()}


def total_users(db: Session) -> int:
    return int(db.query(func.count(SysUser.user_id)).scalar() or 0)


def snapshot_tier_of(rec: UserAchievement) -> Optional[int]:
    return getattr(rec, "tier_snapshot", None)


def obtained_at_text(rec: UserAchievement) -> Optional[str]:
    return rec.obtained_at.isoformat() if rec.obtained_at else None
