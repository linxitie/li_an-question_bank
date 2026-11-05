"""
管理员端：金币商城商品管理 CRUD

- 仅管理员可访问（get_current_admin）
- 兑换记录存有商品名快照，删除商品不影响历史兑换
- 权限点：复用 Permission 体系中的商品管理（如有），否则依赖 admin 角色
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_admin
from ....models.models import SysUser, ShopProduct

router = APIRouter(prefix="/api/admin/shop", tags=["管理员端-金币商城"])
logger = logging.getLogger(__name__)


class ShopProductCreate(BaseModel):
    name: str
    category: str = ""
    product_type: str = "virtual"
    coin_price: int = 0
    cash_price: Optional[float] = None
    stock: int = -1
    image_url: str = ""
    description: str = ""
    deliverable_type: str = "none"
    deliverable_payload: Optional[dict] = None
    status: str = "on_sale"
    sort_order: int = 0


class ShopProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    product_type: Optional[str] = None
    coin_price: Optional[int] = None
    cash_price: Optional[float] = None
    stock: Optional[int] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    deliverable_type: Optional[str] = None
    deliverable_payload: Optional[dict] = None
    status: Optional[str] = None
    sort_order: Optional[int] = None


def _to_dict(p: ShopProduct) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "category": p.category,
        "product_type": p.product_type,
        "coin_price": p.coin_price,
        "cash_price": float(p.cash_price) if p.cash_price is not None else None,
        "stock": p.stock,
        "image_url": p.image_url,
        "description": p.description,
        "deliverable_type": p.deliverable_type,
        "deliverable_payload": p.deliverable_payload,
        "status": p.status,
        "sort_order": p.sort_order,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("/products", summary="商品列表（含下架）")
async def admin_list_products(
    category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    query = db.query(ShopProduct)
    if category:
        query = query.filter(ShopProduct.category == category)
    if status:
        query = query.filter(ShopProduct.status == status)

    total = query.count()
    items = (
        query.order_by(ShopProduct.sort_order.asc(), ShopProduct.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_to_dict(p) for p in items],
    }


@router.post("/products", summary="创建商品")
async def admin_create_product(
    data: ShopProductCreate,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    p = ShopProduct(
        name=data.name,
        category=data.category,
        product_type=data.product_type,
        coin_price=data.coin_price,
        cash_price=data.cash_price,
        stock=data.stock,
        image_url=data.image_url,
        description=data.description,
        deliverable_type=data.deliverable_type,
        deliverable_payload=data.deliverable_payload,
        status=data.status,
        sort_order=data.sort_order,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    logger.info(f"管理员 {current_user.username} 创建商品 {p.name}")
    return _to_dict(p)


@router.put("/products/{product_id}", summary="更新商品")
async def admin_update_product(
    product_id: int,
    data: ShopProductUpdate,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    p = db.query(ShopProduct).filter(ShopProduct.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在")

    for k, v in data.dict(exclude_unset=True).items():
        setattr(p, k, v)

    db.commit()
    db.refresh(p)
    logger.info(f"管理员 {current_user.username} 更新商品 {p.name}")
    return _to_dict(p)


@router.delete("/products/{product_id}", summary="删除商品")
async def admin_delete_product(
    product_id: int,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    p = db.query(ShopProduct).filter(ShopProduct.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在")

    db.delete(p)
    db.commit()
    logger.info(f"管理员 {current_user.username} 删除商品 {p.name}")
    return {"message": "删除成功"}


# ==================== M1（2026-11-04）：库存预警 / 上下架 / 防通胀指标 ====================


@router.get("/stock-alerts", summary="库存预警（低于预警线的商品）")
async def admin_stock_alerts(
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """返回库存紧张的商品，按"距预警线的比例"升序（最危险的排前面）。

    `stock = -1` 表示不限库存，不参与预警。
    """
    rows = (
        db.query(ShopProduct)
        .filter(ShopProduct.status == "on_sale", ShopProduct.stock >= 0)
        .all()
    )
    alerts = []
    for p in rows:
        limit = p.min_stock_alert if p.min_stock_alert is not None else 5
        if p.stock <= limit:
            alerts.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "stock": p.stock,
                    "min_stock_alert": limit,
                    "tier": getattr(p, "tier", None),
                    "shelf_priority": getattr(p, "shelf_priority", None),
                }
            )
    alerts.sort(key=lambda a: (a["stock"] / max(1, a["min_stock_alert"])))
    return {"total": len(alerts), "items": alerts}


@router.post("/products/{product_id}/shelf", summary="上架 / 下架")
async def admin_shelf_product(
    product_id: int,
    status: str = Query(..., description="on_sale 或 off_shelf"),
    shelf_priority: Optional[str] = Query(None, description="P1/P2/P3"),
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if status not in ("on_sale", "off_shelf"):
        raise HTTPException(status_code=400, detail="status 只能是 on_sale/off_shelf")
    p = db.query(ShopProduct).filter(ShopProduct.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在")
    p.status = status
    if shelf_priority:
        if shelf_priority not in ("P1", "P2", "P3"):
            raise HTTPException(status_code=400, detail="shelf_priority 只能是 P1/P2/P3")
        p.shelf_priority = shelf_priority
    db.commit()
    logger.info(f"管理员 {current_user.username} 设置商品 {p.name} 状态={status}")
    return {"success": True, "id": p.id, "status": p.status, "shelf_priority": p.shelf_priority}


@router.get("/metrics", summary="金币经济体指标（防通胀监控）")
async def admin_coin_metrics(
    days: int = Query(30, ge=1, le=180, description="统计窗口天数"),
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """输出设计文档 §2.6 的 5 个指标：发行、消耗、兑换率、存量、预算占用。

    预算占用按 `年收入 × 2%` 的假设口径计算；年收入可后续接运营配置。
    """
    from datetime import datetime, timedelta

    from sqlalchemy import func

    from ....models.models import CoinLot, CoinRecord

    now = datetime.now()
    start = now - timedelta(days=days)

    issued = (
        db.query(func.coalesce(func.sum(CoinRecord.coin_change), 0))
        .filter(CoinRecord.transaction_type == "GAIN", CoinRecord.transaction_time >= start)
        .scalar()
        or 0
    )
    spent = abs(
        db.query(func.coalesce(func.sum(CoinRecord.coin_change), 0))
        .filter(CoinRecord.transaction_type == "SPEND", CoinRecord.transaction_time >= start)
        .scalar()
        or 0
    )
    expired = abs(
        db.query(func.coalesce(func.sum(CoinRecord.coin_change), 0))
        .filter(
            CoinRecord.source_type == "EXPIRY",
            CoinRecord.transaction_time >= start,
        )
        .scalar()
        or 0
    )
    outstanding = (
        db.query(func.coalesce(func.sum(CoinLot.remaining), 0))
        .filter(CoinLot.remaining > 0)
        .scalar()
        or 0
    )
    # 历史金币：M1 之前发放的记录没有批次，余额里仍有一部分无法归入批次。
    # 不单独统计就会让「存量」指标失真（总余额 ≫ 批次剩余）。
    total_balance = db.query(func.coalesce(func.sum(SysUser.total_coins), 0)).scalar() or 0
    legacy_outstanding = max(0, int(total_balance) - int(outstanding))
    active_users = db.query(func.count(func.distinct(CoinRecord.user_id))).filter(
        CoinRecord.transaction_time >= start
    ).scalar() or 0

    redeem_rate = round(spent / issued, 4) if issued else 0.0
    per_user = round(issued / active_users, 1) if active_users else 0.0

    # 预算：面值 = 金币 / 100；成本 = 面值 × 加权成本率 52.5%（设计文档 §2.1）
    face_value = spent / 100.0
    cost = round(face_value * 0.525, 2)
    annual_budget = 600000.0  # 年收入 3000 万 × 2%
    budget_pct = round(cost / annual_budget, 4) if annual_budget else 0.0

    # 阈值：兑换率 3%~8%；单用户异常见 §2.6
    flags = []
    if redeem_rate > 0.08:
        flags.append("兑换率 > 8%：建议抬高商品价格或收缩发行")
    if redeem_rate and redeem_rate < 0.02:
        flags.append("兑换率 < 2%：激励不足，建议上新或降价")
    if per_user > 800 * (days / 7):
        flags.append("人均获得偏高：建议下调任务基础值")
    if budget_pct > 0.025:
        flags.append("预算占用 ≥2.5%：建议全站提价 15%")

    return {
        "window_days": days,
        "issued": int(issued),
        "spent": int(spent),
        "expired": int(expired),
        "outstanding": int(outstanding),
        "legacy_outstanding": legacy_outstanding,
        "total_balance": int(total_balance),
        "active_users": int(active_users),
        "per_user": per_user,
        "redeem_rate": redeem_rate,
        "face_value_yuan": round(face_value, 2),
        "cost_estimate_yuan": cost,
        "annual_budget_yuan": annual_budget,
        "budget_usage_pct": budget_pct,
        "flags": flags,
    }
