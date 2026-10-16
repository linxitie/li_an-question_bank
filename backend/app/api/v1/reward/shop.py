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
from ....models.models import SysUser, ShopProduct, CoinExchange, CoinRecord
from ....services import deliverable_service

router = APIRouter(prefix="/api/shop", tags=["金币商城"])
logger = logging.getLogger(__name__)


class ExchangeRequest(BaseModel):
    product_id: int
    request_id: str


def _product_to_dict(p: ShopProduct) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "category": p.category,
        "product_type": p.product_type,
        "coin_price": p.coin_price,
        "stock": p.stock,
        "image_url": p.image_url,
        "description": p.description,
        "deliverable_type": p.deliverable_type,
        "deliverable_payload": p.deliverable_payload,
        "status": p.status,
        "sort_order": p.sort_order,
    }


@router.get("/products", summary="商品列表")
async def list_products(
    category: Optional[str] = Query(None, description="分类: 限定称号/专属头像框"),
    search: Optional[str] = Query(None, description="按名称搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(ShopProduct).filter(ShopProduct.status == "on_sale")
    if category:
        query = query.filter(ShopProduct.category == category)
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

    try:
        # 扣币（唯一事实来源）
        current_user.total_coins = (current_user.total_coins or 0) - product.coin_price

        # 写流水
        db.add(CoinRecord(
            user_id=current_user.user_id,
            coin_change=-product.coin_price,
            current_balance=current_user.total_coins,
            transaction_type="SPEND",
            source_type="SHOP",
            related_id=product.id,
            description=f"兑换商品：{product.name}",
        ))

        # 写兑换记录
        exchange_record = CoinExchange(
            user_id=current_user.user_id,
            product_id=product.id,
            product_name=product.name,
            product_type=product.product_type,
            coin_cost=product.coin_price,
            status="completed",
            deliverable_type=product.deliverable_type,
            deliverable_payload=product.deliverable_payload,
            request_id=req.request_id,
            completed_at=datetime.now(),
        )
        db.add(exchange_record)

        # 扣库存（-1 不限库存）
        if product.stock is not None and product.stock > 0:
            product.stock -= 1

        db.flush()  # 确保 exchange_record.id 可用

        # 触发权益发放（同一事务）
        deliverable_service.deliver(exchange_record, current_user, db)

        commit_with_retry(db)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"兑换失败 user={current_user.user_id} product={product.id}: {e}")
        raise HTTPException(status_code=500, detail="兑换失败，请稍后重试")

    logger.info(f"用户 {current_user.user_id} 兑换 {product.name}，消耗 {product.coin_price} 金币")
    return {
        "exchange_id": exchange_record.id,
        "balance": current_user.total_coins,
        "product_name": product.name,
        "coin_cost": product.coin_price,
        "message": "兑换成功",
    }
