"""我的装扮：称号 / 头像框（2026-11-05）。

背景：商城里能兑换称号与头像框，但兑换后没有任何入口佩戴，
`user_title.equipped` 与 `sys_user.avatar_frame` 一直是初始值。

职责：
- 列出用户已拥有的称号（user_title + badge_title）与头像框（来自兑换记录/商品 payload）；
- 佩戴称号：写 `sys_user.title` + `user_title.equipped`（同一用户只能戴一个）；
- 佩戴头像框：写 `sys_user.avatar_frame`，可取消（置空）。
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import CoinExchange, ShopProduct, SysUser, Title, UserTitle
from ....services import decoration_expiry

router = APIRouter(prefix="/api/user/decoration", tags=["我的装扮"])
logger = logging.getLogger(__name__)


class EquipTitlePayload(BaseModel):
    title_id: Optional[int] = None  # None = 取消佩戴


class EquipFramePayload(BaseModel):
    frame: Optional[str] = None  # None = 取消佩戴


def _owned_frames(db: Session, user: SysUser) -> list[dict]:
    """已拥有的头像框：来自兑换记录里 deliverable_type=avatar_frame 的商品 payload。"""
    rows = (
        db.query(CoinExchange)
        .filter(CoinExchange.user_id == user.user_id)
        .all()
    )
    frames: dict[str, dict] = {}
    for r in rows:
        if (r.deliverable_type or "") != "avatar_frame":
            continue
        payload = r.deliverable_payload if isinstance(r.deliverable_payload, dict) else {}
        frame = payload.get("frame") or payload.get("frame_id") or payload.get("avatar_frame")
        if not frame:
            continue
        key = str(frame)
        frames.setdefault(
            key,
            {
                "frame": key,
                "name": r.product_name or key,
                "product_id": r.product_id,
                "acquired_at": r.created_at.isoformat() if r.created_at else None,
            },
        )

    # 兜底：商品表里配置了 avatar_frame 且用户兑换过（覆盖旧数据无 payload 的情况）
    if not frames:
        products = (
            db.query(ShopProduct)
            .filter(ShopProduct.deliverable_type == "avatar_frame")
            .all()
        )
        exchanged_ids = {r.product_id for r in rows}
        for p in products:
            if p.id not in exchanged_ids:
                continue
            payload = p.deliverable_payload if isinstance(p.deliverable_payload, dict) else {}
            frame = payload.get("frame") or payload.get("frame_id") or f"frame_{p.id}"
            frames.setdefault(str(frame), {"frame": str(frame), "name": p.name, "product_id": p.id})

    return list(frames.values())


@router.get("/mine", summary="我拥有的称号与头像框")
async def my_decorations(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    owned_titles = (
        db.query(UserTitle, Title)
        .join(Title, Title.title_id == UserTitle.title_id)
        .filter(UserTitle.user_id == current_user.user_id)
        .all()
    )
    titles = [
        {
            "title_id": ut.title_id,
            "name": t.name,
            "description": t.description,
            "equipped": bool(ut.equipped),
            "obtained_at": ut.obtained_at.isoformat() if ut.obtained_at else None,
        }
        for ut, t in owned_titles
    ]
    # 到期处理：当前佩戴的若已过期，先摘掉
    if decoration_expiry.expire_equipped_frame(db, current_user):
        db.commit()

    frames = _owned_frames(db, current_user)
    status = {x["frame"]: x for x in decoration_expiry.frame_status(db, current_user.user_id)}
    for f in frames:
        info = status.get(f["frame"], {})
        f.update(
            {
                "expire_at": info.get("expire_at"),
                "expired": info.get("expired", False),
                "days_left": info.get("days_left"),
            }
        )

    return {
        "titles": titles,
        "frames": frames,
        "current_title_id": next((t["title_id"] for t in titles if t["equipped"]), None),
        "current_title": current_user.title or None,
        "current_frame": current_user.avatar_frame or None,
        "expired_frames": [x["frame"] for x in status.values() if x["expired"]],
    }


@router.post("/equip-title", summary="佩戴/取消称号")
async def equip_title(
    payload: EquipTitlePayload,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.title_id is None:
        db.query(UserTitle).filter(UserTitle.user_id == current_user.user_id).update(
            {UserTitle.equipped: 0}, synchronize_session=False
        )
        current_user.title = None
        db.commit()
        return {"success": True, "current_title": None}

    owned = (
        db.query(UserTitle)
        .filter(
            UserTitle.user_id == current_user.user_id,
            UserTitle.title_id == payload.title_id,
        )
        .first()
    )
    if not owned:
        raise HTTPException(status_code=403, detail="尚未拥有该称号，请先在商城兑换")

    title = db.query(Title).filter(Title.title_id == payload.title_id).first()
    if not title:
        raise HTTPException(status_code=404, detail="称号不存在")

    db.query(UserTitle).filter(UserTitle.user_id == current_user.user_id).update(
        {UserTitle.equipped: 0}, synchronize_session=False
    )
    owned.equipped = 1
    current_user.title = title.name
    db.commit()
    logger.info("用户 %s 佩戴称号 %s", current_user.user_id, title.name)
    return {"success": True, "current_title": title.name, "title_id": title.title_id}


@router.post("/equip-frame", summary="佩戴/取消头像框")
async def equip_frame(
    payload: EquipFramePayload,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.frame is None:
        current_user.avatar_frame = None
        db.commit()
        return {"success": True, "current_frame": None}

    owned = {f["frame"] for f in _owned_frames(db, current_user)}
    if payload.frame not in owned:
        raise HTTPException(status_code=403, detail="尚未拥有该头像框，请先在商城兑换")

    # 到期校验（2026-11-05）
    status = {x["frame"]: x for x in decoration_expiry.frame_status(db, current_user.user_id)}
    info = status.get(payload.frame, {})
    if info.get("expired"):
        raise HTTPException(status_code=400, detail="该头像框已过期，不能佩戴")

    current_user.avatar_frame = payload.frame
    db.commit()
    logger.info("用户 %s 佩戴头像框 %s", current_user.user_id, payload.frame)
    return {"success": True, "current_frame": payload.frame}
