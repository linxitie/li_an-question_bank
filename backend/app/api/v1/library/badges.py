# -*- coding: utf-8 -*-
"""徽章接口（登录用户）：目录 / 我的徽章 / 概览。

端点（新增，不改既有 343 个端点）：
- GET /api/badges/catalog  徽章目录（48 成就 + 6 称号）
- GET /api/badges/my       我的徽章（含获得状态、获得时档位快照）
- GET /api/badges/summary  积分与档位概览（供个人主页/徽章墙使用）
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....models.models import Achievement, Title, UserAchievement, SysUser
from ....services import badge_service
from ....core.security import get_current_user

router = APIRouter(prefix="/api/badges", tags=["badges"])


def _achievement_item(a: Achievement) -> dict:
    return {
        "kind": "achievement",
        "id": a.achievement_id,
        "name": a.name,
        "category": a.category,
        "icon": a.icon,
        "shape": badge_service.shape_of(a.category),
        "condition_desc": a.condition_desc,
        "reward_coins": a.reward_coins or 0,
        "threshold": a.threshold or 0,
        "hidden": bool(a.is_hidden),
    }


def _title_item(t: Title) -> dict:
    return {
        "kind": "title",
        "id": t.title_id,
        "name": t.name,
        "category": "称号",
        "icon": None,
        "shape": "ribbon",
        "condition_desc": t.description or f"达到 {t.unlock_level} 级解锁",
        "reward_coins": 0,
        "threshold": t.unlock_level or 0,
        "hidden": False,
    }


@router.get("/catalog", summary="徽章目录（成就 + 称号）")
async def badge_catalog(
    category: str = Query("", description="按类别过滤，如 坚持"),
    kind: str = Query("", description="achievement / title"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = []
    if kind in ("", "achievement"):
        q = db.query(Achievement)
        if category:
            q = q.filter(Achievement.category == category)
        items += [_achievement_item(a) for a in
                  q.order_by(Achievement.sort_order.asc(), Achievement.achievement_id.asc()).all()]
    if kind in ("", "title") and (not category or category == "称号"):
        titles = db.query(Title).order_by(Title.sort_order.asc()).all()
        items += [_title_item(t) for t in titles]
    return {"total": len(items), "items": items}


@router.get("/summary", summary="积分与档位概览")
async def badge_summary(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    score = badge_service.total_score(db, current_user.user_id)
    tier = badge_service.tier_of(score)
    progress = badge_service.progress_to_next(score)
    owned = (db.query(UserAchievement)
             .filter(UserAchievement.user_id == current_user.user_id).count())
    total = db.query(Achievement).count() + db.query(Title).count()
    return {
        "score": score,
        "tier": tier,
        "progress": progress,
        "owned": owned,
        "total": total,
        "tiers": [{"code": c, "label": l, "threshold": lo}
                  for (lo, c, l) in badge_service.TIERS],
    }


@router.get("/my", summary="我的徽章（含获得状态与档位快照）")
async def my_badges(
    category: str = Query(""),
    kind: str = Query(""),
    only_owned: bool = Query(False),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    score = badge_service.total_score(db, current_user.user_id)
    tier = badge_service.tier_of(score)
    progress = badge_service.progress_to_next(score)

    rows = (db.query(UserAchievement)
            .filter(UserAchievement.user_id == current_user.user_id).all())
    obtained = {r.achievement_id: r for r in rows}

    items = []
    if kind in ("", "achievement"):
        q = db.query(Achievement)
        if category:
            q = q.filter(Achievement.category == category)
        for a in q.order_by(Achievement.sort_order.asc(),
                            Achievement.achievement_id.asc()).all():
            it = _achievement_item(a)
            rec = obtained.get(a.achievement_id)
            it.update({
                "owned": rec is not None,
                "obtained_at": rec.obtained_at.isoformat() if rec and rec.obtained_at else None,
                "snapshot_tier": badge_service.tier_label_by_index(
                    getattr(rec, "tier_snapshot", None)) if rec else None,
                "current_tier": tier["label"],
            })
            if only_owned and not rec:
                continue
            items.append(it)

    if kind in ("", "title") and (not category or category == "称号"):
        for t in db.query(Title).order_by(Title.sort_order.asc()).all():
            it = _title_item(t)
            it.update({"owned": False, "obtained_at": None,
                       "snapshot_tier": None, "current_tier": tier["label"]})
            if only_owned:
                continue
            items.append(it)

    return {
        "score": score,
        "tier": tier,
        "progress": progress,
        "total": len(items),
        "owned": sum(1 for i in items if i.get("owned")),
        "items": items,
    }
