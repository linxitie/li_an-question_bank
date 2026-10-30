# -*- coding: utf-8 -*-
"""徽章接口（登录用户）：目录 / 我的徽章 / 概览。

端点（新增，不改既有 343 个端点）：
- GET /api/badges/catalog  徽章目录（48 成就 + 6 称号）
- GET /api/badges/my       我的徽章（含获得状态、获得时档位快照）
- GET /api/badges/summary  积分与档位概览（供个人主页/徽章墙使用）
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....models.models import SysUser
from ..growth import contract as growth_contract
from ....services import badge_service
from ....core.security import get_current_user

router = APIRouter(prefix="/api/badges", tags=["badges"])


def _achievement_item(a) -> dict:
    f = growth_contract.achievement_fields(a)
    f.update({"kind": "achievement", "shape": badge_service.shape_of(f.get("category"))})
    return f


def _title_item(t) -> dict:
    f = growth_contract.title_fields(t)
    return {
        "kind": "title",
        "id": f["id"],
        "name": f["name"],
        "category": "称号",
        "icon": None,
        "shape": "ribbon",
        "condition_desc": f["description"] or f"达到 {f['unlock_level']} 级解锁",
        "reward_coins": 0,
        "threshold": f["unlock_level"],
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
        items += [_achievement_item(a) for a in
                  growth_contract.list_achievements(db, category or None)]
    if kind in ("", "title") and (not category or category == "称号"):
        items += [_title_item(t) for t in growth_contract.list_titles(db)]
    return {"total": len(items), "items": items}


@router.get("/summary", summary="积分与档位概览")
async def badge_summary(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    score = badge_service.total_score(db, current_user.user_id)
    tier = badge_service.tier_of(score)
    progress = badge_service.progress_to_next(score)
    owned = growth_contract.count_user_achievements(db, current_user.user_id)
    total = (growth_contract.count_achievements(db)
             + growth_contract.count_titles(db))
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
    sort: str = Query("catalog", description="catalog=目录顺序；recent=已获得按时间倒序"),
    limit: int = Query(0, ge=0, le=200, description="0 表示不限制"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    score = badge_service.total_score(db, current_user.user_id)
    tier = badge_service.tier_of(score)
    progress = badge_service.progress_to_next(score)

    rows = growth_contract.list_user_achievements(db, current_user.user_id)
    obtained = {r.achievement_id: r for r in rows}

    # 稀有度：每个成就的获得人数 + 全站用户数（一次聚合，经由 growth 契约）
    counts = growth_contract.achievement_owner_counts(db)
    total_users = growth_contract.total_users(db)
    first_owners = growth_contract.achievement_first_owners(db)

    items = []
    if kind in ("", "achievement"):
        for a in growth_contract.list_achievements(db, category or None):
            it = _achievement_item(a)
            rec = obtained.get(a.achievement_id)
            cnt = int(counts.get(a.achievement_id, 0))
            it.update({
                "owned": rec is not None,
                "obtained_at": rec.obtained_at.isoformat() if rec and rec.obtained_at else None,
                # 成色 = 徽章自身固定档位（按获取难度），与玩家分数/基数无关
                "badge_tier": it.get("badge_tier") or "青铜",
                "snapshot_tier": badge_service.tier_label_by_index(
                    getattr(rec, "tier_snapshot", None)) if rec else None,
                # 稀有度只做文字：全服多少人拿到（相对量，随时间变，不参与颜色）
                "rarity_text": (f"全服 {round(cnt / total_users * 100, 1)}% 获得"
                                if total_users else ""),
                # 「全服首个获得」是真正的稀有感：不改颜色，只加一枚文字标记
                "is_first_owner": bool(
                    rec is not None
                    and first_owners.get(a.achievement_id) == current_user.user_id),
                "first_owner_text": ("全服首个获得" if (
                    rec is not None
                    and first_owners.get(a.achievement_id) == current_user.user_id) else ""),
                "owned_count": cnt,
                "owned_percent": round(cnt / total_users * 100, 1) if total_users else 0.0,
            })
            if only_owned and not rec:
                continue
            items.append(it)

    if kind in ("", "title") and (not category or category == "称号"):
        for t in growth_contract.list_titles(db):
            it = _title_item(t)
            it.update({"owned": False, "obtained_at": None,
                       "snapshot_tier": None, "current_tier": tier["label"]})
            if only_owned:
                continue
            items.append(it)

    total_before = len(items)
    if (sort or "").lower() == "recent":
        # 已获得按获得时间倒序在前，未获得保持目录顺序在后
        owned_items = [i for i in items if i.get("owned")]
        rest = [i for i in items if not i.get("owned")]
        owned_items.sort(key=lambda i: i.get("obtained_at") or "", reverse=True)
        items = owned_items + rest
    if limit and limit > 0:
        items = items[:limit]

    return {
        "score": score,
        "tier": tier,
        "progress": progress,
        "total": total_before,
        "returned": len(items),
        "owned": sum(1 for i in items if i.get("owned")),
        "items": items,
    }


@router.get("/wall", summary="个人主页徽章墙（最近获得）")
async def badge_wall(
    limit: int = Query(6, ge=1, le=12),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """返回最近获得的 N 枚徽章（默认 6），供个人主页展示。

    只返回已获得徽章；未获得不占位（避免空槽观感）。
    """
    score = badge_service.total_score(db, current_user.user_id)
    tier = badge_service.tier_of(score)

    rows = growth_contract.list_user_achievements(db, current_user.user_id)[: limit * 3]
    if not rows:
        return {"items": [], "score": score, "tier": tier}

    ids = [r.achievement_id for r in rows]
    achs = {a.achievement_id: a for a in growth_contract.list_achievements(db)
            if a.achievement_id in ids}

    counts = growth_contract.achievement_owner_counts(db, ids)
    total_users = growth_contract.total_users(db)

    items = []
    for rec in rows:
        a = achs.get(rec.achievement_id)
        if not a:
            continue
        it = _achievement_item(a)
        cnt = int(counts.get(a.achievement_id, 0))
        it.update({
            "owned": True,
            "obtained_at": rec.obtained_at.isoformat() if rec.obtained_at else None,
            "snapshot_tier": badge_service.tier_label_by_index(
                getattr(rec, "tier_snapshot", None)),
            "current_tier": tier["label"],
            "owned_count": cnt,
            "owned_percent": round(cnt / total_users * 100, 1) if total_users else 0.0,
        })
        items.append(it)
        if len(items) >= limit:
            break

    return {"items": items, "score": score, "tier": tier}
