"""头像框 / 称号到期（2026-11-05）。

商品 payload 里带 `days` 的权益（如「限定头像框（30天）」）应当到期失效：
- 到期后不能再佩戴；
- 已佩戴的到期后自动摘掉（清空 `sys_user.avatar_frame`）。

数据来源：`coin_exchanges`（deliverable_type='avatar_frame'，payload 里含 days/frame）。
到期时间 = 交付时间（delivered_at，缺省 created_at）+ days 天。
没有 `days` 的视为永久。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..models.models import CoinExchange, SysUser, Title, UserTitle

logger = logging.getLogger(__name__)


def _payload(exchange: CoinExchange) -> dict:
    return exchange.deliverable_payload if isinstance(exchange.deliverable_payload, dict) else {}


def frame_expiries(db: Session, user_id: int) -> dict[str, Optional[datetime]]:
    """{frame: 到期时间}；None 表示永久。

    同一头像框兑换多次时取最晚到期时间（续期效果）。
    """
    rows = (
        db.query(CoinExchange)
        .filter(
            CoinExchange.user_id == user_id,
            CoinExchange.deliverable_type == "avatar_frame",
        )
        .all()
    )
    result: dict[str, Optional[datetime]] = {}
    for r in rows:
        payload = _payload(r)
        frame = payload.get("frame") or payload.get("frame_id") or payload.get("avatar_frame")
        if not frame:
            continue
        frame = str(frame)
        days = payload.get("days")
        if not days:
            result[frame] = None
            continue
        base = r.delivered_at or r.created_at or datetime.now()
        expire_at = base + timedelta(days=int(days))
        current = result.get(frame)
        if current is None and frame in result:
            # 已有永久 → 保持永久
            continue
        if current is None or expire_at > current:
            result[frame] = expire_at
    return result


def frame_status(db: Session, user_id: int) -> list[dict]:
    """头像框列表（含到期信息），供「我的装扮」展示。"""
    expiries = frame_expiries(db, user_id)
    now = datetime.now()
    items = []
    for frame, expire_at in expiries.items():
        expired = bool(expire_at and expire_at <= now)
        days_left = None
        if expire_at:
            days_left = max(0, (expire_at - now).days)
        items.append(
            {
                "frame": frame,
                "expire_at": expire_at.isoformat() if expire_at else None,
                "expired": expired,
                "days_left": days_left,
            }
        )
    items.sort(key=lambda x: (x["expired"], x["expire_at"] or "9999"))
    return items


def expire_equipped_frame(db: Session, user: SysUser) -> bool:
    """当前佩戴的头像框若已过期则摘掉。返回是否发生变更。"""
    frame = user.avatar_frame
    if not frame:
        return False
    expiries = frame_expiries(db, user.user_id)
    expire_at = expiries.get(str(frame))
    if expire_at is None or expire_at > datetime.now():
        return False
    user.avatar_frame = None
    logger.info("用户 %s 的头像框 %s 已到期，自动摘除", user.user_id, frame)
    return True


def expire_all(db: Session) -> dict:
    """调度用：批量摘除已过期头像框（只处理当前佩戴的）。"""
    users = db.query(SysUser).filter(SysUser.avatar_frame.isnot(None)).all()
    removed = 0
    for user in users:
        if expire_equipped_frame(db, user):
            removed += 1
    if removed:
        db.commit()
    return {"checked": len(users), "removed": removed}


def title_expiries(db: Session, user_id: int) -> dict[int, Optional[datetime]]:
    """称号到期时间（当前 badge_title 没有时长字段，保持 None=永久）。

    预留给后续「限时称号」；逻辑与头像框一致。
    """
    rows = (
        db.query(UserTitle)
        .join(Title, Title.title_id == UserTitle.title_id)
        .filter(UserTitle.user_id == user_id)
        .all()
    )
    return {ut.title_id: None for ut, _t in rows}
