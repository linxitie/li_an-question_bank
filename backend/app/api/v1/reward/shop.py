"""
金币商城 API：商品列表 / 详情 / 兑换

兑换关键设计：
- 幂等：request_id 唯一键防重复提交
- 并发安全：事务内校验余额后扣减，total_coins 为唯一事实来源
- 原子：扣币 + 写流水 + 写兑换 + 触发权益在同一事务，失败整体回滚
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ....core.database import get_db, commit_with_retry
from ....core.security import get_current_user
from ....core.trigger_types import TRIGGER_SHOP_PURCHASED
from ....models.models import (
    SysUser,
    ShopProduct,
    CoinExchange,
    CoinRecord,
    Coupon,
    CouponGrant,
)
from ....services import deliverable_service
from ....services import coin_ledger
from ....services.event_consumer import record_user_action

router = APIRouter(prefix="/api/shop", tags=["金币商城"])
logger = logging.getLogger(__name__)

# 分层区间（设计文档 §2.3）：小额 0–500、中额 500–5000、大额 5000+
# 用"上界+1"表达闭区间，避免 500 被算进中额（历史数据里 500 币商品属于小额）
TIER_RANGES = {
    "small": (0, 501),
    "mid": (501, 5001),
    "large": (5001, 10**9),
}


class ExchangeRequest(BaseModel):
    product_id: int
    request_id: str
    # 2026-11-04 M1：可选使用一张券（纯金币通道；混合现金通道按 D6 放 M1.5）
    coupon_grant_id: Optional[int] = None


def _product_to_dict(p: ShopProduct) -> dict:
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
        # M1 分层字段
        "tier": getattr(p, "tier", None) or _infer_tier(p.coin_price or 0),
        "cost_estimate": float(p.cost_estimate) if getattr(p, "cost_estimate", None) is not None else None,
        "shelf_priority": getattr(p, "shelf_priority", None) or "P3",
        "min_stock_alert": getattr(p, "min_stock_alert", None) or 5,
    }


def _infer_tier(coin_price: int) -> str:
    """价格落在哪个区间；用于历史数据没有 tier 时的兜底（闭区间口径）。"""
    if coin_price >= 5001:
        return "large"
    if coin_price >= 501:
        return "mid"
    return "small"


def _coupon_applies(coupon: Coupon, product: ShopProduct) -> bool:
    """券是否适用于该商品：按 scope 判定（product/category/tier）。"""
    if coupon.status != "active":
        return False
    if coupon.scope == "product":
        return coupon.scope_value == str(product.id)
    if coupon.scope == "category":
        return coupon.scope_value == (product.category or "")
    if coupon.scope == "tier":
        return coupon.scope_value == _infer_tier(product.coin_price or 0)
    return coupon.scope == "all"


def _discount_price(coupon: Optional[Coupon], coin_price: int) -> int:
    """按券计算折后金币价（向下取整，最低 1 币）。"""
    if coupon is None:
        return coin_price
    if coupon.discount_type == "rate":
        value = int(float(coupon.discount_value) * coin_price)
    else:
        # amount 券：立减金额按 100 币 = 1 元折算
        value = coin_price - int(float(coupon.discount_value) * 100)
    return max(1, min(coin_price, value))


@router.get("/products", summary="商品列表")
async def list_products(
    category: Optional[str] = Query(None, description="分类: 限定称号/专属头像框"),
    tier: Optional[str] = Query(None, description="价格区间: small/mid/large"),
    search: Optional[str] = Query(None, description="按名称搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(ShopProduct).filter(ShopProduct.status == "on_sale")
    if category:
        query = query.filter(ShopProduct.category == category)
    if tier:
        if tier not in TIER_RANGES:
            raise HTTPException(status_code=400, detail="tier 只能是 small/mid/large")
        low, high = TIER_RANGES[tier]
        query = query.filter(ShopProduct.coin_price >= low, ShopProduct.coin_price < high)
    if search:
        query = query.filter(ShopProduct.name.contains(search))

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
        "items": [_product_to_dict(p) for p in items],
    }


@router.get("/products/{product_id}/quote", summary="兑换报价（含可用券与折后价）")
async def quote_product(
    product_id: int,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """给前端展示"原价 / 可用券 / 券后价 / 余额是否够"。

    为什么不直接在详情里算：券的适用范围、有效期、状态都要动态判断，
    且用户可能持有张券，前端不该知道这些规则（避免前后端两套逻辑漂移）。
    """
    product = db.query(ShopProduct).filter(
        ShopProduct.id == product_id,
        ShopProduct.status == "on_sale",
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")

    now = datetime.now()
    grants = (
        db.query(CouponGrant)
        .filter(CouponGrant.user_id == current_user.user_id, CouponGrant.status == "unused")
        .all()
    )
    usable = []
    for grant in grants:
        coupon = db.query(Coupon).filter(Coupon.id == grant.coupon_id).first()
        if not coupon or not _coupon_applies(coupon, product):
            continue
        if coupon.valid_to and coupon.valid_to < now:
            continue
        usable.append(
            {
                "coupon_grant_id": grant.id,
                "title": coupon.title,
                "discount_type": coupon.discount_type,
                "discount_value": float(coupon.discount_value),
                "price_after": _discount_price(coupon, product.coin_price or 0),
            }
        )

    best = min(usable, key=lambda c: c["price_after"]) if usable else None
    balance = current_user.total_coins or 0
    final_price = best["price_after"] if best else (product.coin_price or 0)
    return {
        "product": _product_to_dict(product),
        "balance": balance,
        "coin_price": product.coin_price or 0,
        "usable_coupons": usable,
        "best_coupon_grant_id": best["coupon_grant_id"] if best else None,
        "final_coin_price": final_price,
        "affordable": balance >= final_price,
        # 混合兑换（现金通道）按 D6 放到 M1.5，这里先明确告知前端
        "cash_channel_available": False,
    }


@router.get("/exchange/mine", summary="我的兑换记录")
async def my_exchanges(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(CoinExchange).filter(CoinExchange.user_id == current_user.user_id)
    total = query.count()
    rows = (
        query.order_by(CoinExchange.created_at.desc(), CoinExchange.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "product_id": r.product_id,
                "product_name": r.product_name,
                "product_type": r.product_type,
                "coin_cost": r.coin_cost,
                "cash_cost": float(r.cash_cost) if r.cash_cost is not None else 0,
                "status": r.status,
                # M1.5：交付物（"我的兑换"页面直接展示这几项）
                "deliverable_type": r.deliverable_type,
                "delivered_code": r.delivered_code,
                "delivered_at": r.delivered_at.isoformat() if r.delivered_at else None,
                "shipped_at": r.shipped_at.isoformat() if r.shipped_at else None,
                "status_text": {
                    "completed": "已交付",
                    "pending": "待发货/待开通",
                    "refunded": "已退款",
                }.get(r.status, r.status),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in rows
        ],
    }


@router.get("/products/{product_id}", summary="商品详情")
async def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.query(ShopProduct).filter(
        ShopProduct.id == product_id,
        ShopProduct.status == "on_sale",
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")
    return _product_to_dict(p)


@router.post("/exchange", summary="金币兑换")
async def exchange(
    req: ExchangeRequest,
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 幂等：request_id 已使用则拒绝（前端重复点击防重）
    if db.query(CoinExchange).filter(CoinExchange.request_id == req.request_id).first():
        raise HTTPException(status_code=409, detail="重复请求")

    product = db.query(ShopProduct).filter(
        ShopProduct.id == req.product_id,
        ShopProduct.status == "on_sale",
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")

    if product.coin_price > (current_user.total_coins or 0):
        raise HTTPException(status_code=400, detail="金币不足")

    if product.stock == 0:
        raise HTTPException(status_code=400, detail="商品库存不足")

    # ===== M1.5：交付防线——先把"能不能真的交付"查清楚，再扣币 =====
    # 背景：历史商品里 deliverable_type='none' 时，旧逻辑照样扣币但不发任何东西，
    # 用户表现为「兑换成功但什么都没有」。这里在扣币前拒绝，并把卡密不足也挡在扣币前。
    dtype = (product.deliverable_type or "none").strip()
    if dtype not in deliverable_service.SUPPORTED_DELIVERABLE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="该商品尚未配置交付方式，暂不可兑换（已阻止扣币）",
        )
    if dtype == "code" and not deliverable_service.has_available_code(db, product.id):
        raise HTTPException(status_code=400, detail="该商品暂无可用卡密，请稍后再试（未扣币）")

    # ===== M1：券校验与折后价 =====
    coupon = None
    grant = None
    pay_price = product.coin_price or 0
    if req.coupon_grant_id:
        grant = db.query(CouponGrant).filter(
            CouponGrant.id == req.coupon_grant_id,
            CouponGrant.user_id == current_user.user_id,
        ).first()
        if not grant:
            raise HTTPException(status_code=404, detail="券不存在")
        if grant.status != "unused":
            raise HTTPException(status_code=400, detail="该券已使用或已失效")
        coupon = db.query(Coupon).filter(Coupon.id == grant.coupon_id).first()
        if not coupon:
            raise HTTPException(status_code=404, detail="券模板不存在")
        now = datetime.now()
        if coupon.valid_to and coupon.valid_to < now:
            raise HTTPException(status_code=400, detail="券已过期")
        if not _coupon_applies(coupon, product):
            raise HTTPException(status_code=400, detail="该券不适用于此商品")
        pay_price = _discount_price(coupon, product.coin_price or 0)

    if pay_price > (current_user.total_coins or 0):
        raise HTTPException(status_code=400, detail="金币不足")

    try:
        # 扣币（M1：走金币台账，按批次 FIFO 扣减，保证到期机制可用）
        coin_ledger.spend(
            db,
            current_user,
            pay_price,
            source_type="SHOP",
            related_id=product.id,
            description=f"兑换商品：{product.name}" + (f"（券：{coupon.title}）" if coupon else ""),
        )
        balance_after = current_user.total_coins

        # 写兑换记录
        exchange_record = CoinExchange(
            user_id=current_user.user_id,
            product_id=product.id,
            product_name=product.name,
            product_type=product.product_type,
            coin_cost=pay_price,
            cash_cost=None,
            status="completed",
            deliverable_type=product.deliverable_type,
            deliverable_payload=product.deliverable_payload,
            request_id=req.request_id,
            completed_at=datetime.now(),
        )
        db.add(exchange_record)

        # 核销券（与兑换同事务，失败整体回滚）
        if grant is not None:
            grant.status = "used"
            grant.used_at = datetime.now()

        # 扣库存（-1 不限库存）
        if product.stock is not None and product.stock > 0:
            product.stock -= 1

        db.flush()  # 确保 exchange_record.id 可用

        if grant is not None:
            grant.exchange_id = exchange_record.id

        # 触发权益发放（同一事务）
        delivered = deliverable_service.deliver(exchange_record, current_user, db)
        if not delivered:
            # code 类商品可能在并发下被抢完：此时必须整体回滚，不能让用户白扣币
            db.rollback()
            raise HTTPException(status_code=409, detail="交付失败（卡密可能已被抢完），本次未扣币，请重试")

        exchange_id = exchange_record.id
        product_id = product.id
        product_name = product.name
        coin_cost = pay_price
        delivered_code = exchange_record.delivered_code
        order_status = exchange_record.status

        # F2b：兑换记录、库存扣减与 E9 事件同一事务提交。
        await record_user_action(
            db,
            current_user.user_id,
            TRIGGER_SHOP_PURCHASED,
            session={
                "exchange_id": exchange_id,
                "product_id": product_id,
                "product_name": product_name,
                "coin_cost": coin_cost,
                "balance": balance_after,
            },
        )
        commit_with_retry(db)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"兑换失败 user={current_user.user_id} product={product.id}: {e}")
        raise HTTPException(status_code=500, detail="兑换失败，请稍后重试")

    logger.info(f"用户 {current_user.user_id} 兑换 {product_name}，消耗 {coin_cost} 金币")
    return {
        "exchange_id": exchange_id,
        "balance": balance_after,
        "product_name": product_name,
        "coin_cost": coin_cost,
        # M1.5：把交付结果直接返回，前端可立刻展示卡密，而不是只弹"兑换成功"
        "delivered_code": delivered_code,
        "status": order_status,
        "message": "兑换成功" if order_status == "completed" else "兑换成功，待人工发货/开通",
    }
