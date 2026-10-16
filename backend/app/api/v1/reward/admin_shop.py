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
