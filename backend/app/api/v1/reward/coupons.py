"""我的券（2026-11-04 M1）。

券的两个使用场景：
1. C 类场景任务完成后发放（growth 域调用 `grant_coupon`）；
2. 金币到期兜底：把快过期的金币换成小额券，避免用户白丢（设计文档 §2.4）。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import Coupon, CouponGrant, SysUser

router = APIRouter(prefix="/api/coupons", tags=["优惠券"])
logger = logging.getLogger(__name__)


def grant_coupon(
    db: Session,
    user: SysUser,
    coupon_code: str,
    *,
    source: str = "TASK",
) -> Optional[CouponGrant]:
    """给用户发一张券（由任务/兜底逻辑调用，幂等由调用方保证）。"""
    coupon = db.query(Coupon).filter(Coupon.code == coupon_code, Coupon.status == "active").first()
    if not coupon:
        logger.warning("发券失败：券不存在或已停用 code=%s", coupon_code)
        return None
    if coupon.stock == 0:
        logger.info("发券跳过：券库存为 0 code=%s", coupon_code)
        return None

    grant = CouponGrant(user_id=user.user_id, coupon_id=coupon.id, status="unused", source=source)
    db.add(grant)
    if coupon.stock is not None and coupon.stock > 0:
        coupon.stock -= 1
    return grant


@router.get("/mine", summary="我的券（可用/已用/已过期）")
async def my_coupons(
    status: Optional[str] = Query(None, description="unused/used/expired"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(CouponGrant).filter(CouponGrant.user_id == current_user.user_id)
    if status:
        query = query.filter(CouponGrant.status == status)
    total = query.count()
    rows = (
        query.order_by(CouponGrant.status.asc(), CouponGrant.granted_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    now = datetime.now()
    items = []
    for row in rows:
        coupon = db.query(Coupon).filter(Coupon.id == row.coupon_id).first()
        expired = bool(coupon and coupon.valid_to and coupon.valid_to < now and row.status == "unused")
        items.append(
            {
                "grant_id": row.id,
                "status": "expired" if expired else row.status,
                "title": coupon.title if coupon else "（券已下架）",
                "discount_type": coupon.discount_type if coupon else None,
                "discount_value": float(coupon.discount_value) if coupon and coupon.discount_value is not None else None,
                "scope": coupon.scope if coupon else None,
                "scope_value": coupon.scope_value if coupon else None,
                "valid_to": coupon.valid_to.isoformat() if coupon and coupon.valid_to else None,
                "granted_at": row.granted_at.isoformat() if row.granted_at else None,
                "used_at": row.used_at.isoformat() if row.used_at else None,
            }
        )
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.post("/grant", summary="发券（内部/运营用）")
async def grant_to_user(
    coupon_code: str = Query(..., description="券码"),
    user_id: Optional[int] = Query(None, description="目标用户；为空则发给当前用户"),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """内部发券入口：运营补偿或测试用。

    生产环境下"完成任务自动发券"由 growth 域在服务端内部调用 `grant_coupon`，
    不经过这个 HTTP 接口。
    """
    target = current_user
    if user_id and user_id != current_user.user_id:
        if current_user.user_type not in ("admin", "teacher"):
            raise HTTPException(status_code=403, detail="无权给他人发券")
        target = db.query(SysUser).filter(SysUser.user_id == user_id).first()
        if not target:
            raise HTTPException(status_code=404, detail="目标用户不存在")

    grant = grant_coupon(db, target, coupon_code, source="ADMIN")
    if not grant:
        raise HTTPException(status_code=400, detail="发券失败：券不存在或库存不足")
    db.commit()
    return {"success": True, "grant_id": grant.id}
