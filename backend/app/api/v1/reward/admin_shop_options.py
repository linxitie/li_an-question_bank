"""商城选项（分类 / 权益类型）自定义（2026-11-05）。

需求：管理员在新增商品时可以选「警大文创 / 文具 / 习题册」等分类，
并能「新增类型」自定义。用一个通用选项表存，避免每加一类就改代码。

交付类型（deliverable_type）决定兑换后怎么发东西，是**系统行为**，不是展示分类：
- title：发称号（写 user_title）
- avatar_frame：发头像框（写 sys_user.avatar_frame）
- code：发卡密（从 shop_code 池取）
- manual：待人工处理（实物发货 / 运营开通）
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ....core.database import get_db
from ....core.security import get_current_admin
from ....models.models import ShopOption, ShopProduct, SysUser

router = APIRouter(prefix="/api/admin/shop/options", tags=["管理员端-商城选项"])
logger = logging.getLogger(__name__)

DEFAULT_CATEGORIES = ["专属头像框", "限定称号", "文具", "习题册", "警大文创"]
DEFAULT_DELIVERABLE_TYPES = [
    ("title", "称号"),
    ("avatar_frame", "头像框"),
    ("code", "卡密"),
    ("manual", "人工处理"),
]
KINDS = {"category", "deliverable_type"}


class OptionCreate(BaseModel):
    kind: str
    value: str
    label: str = ""


def ensure_defaults(db: Session) -> None:
    """首次访问时补齐默认选项（幂等）。"""
    for i, name in enumerate(DEFAULT_CATEGORIES):
        exists = (
            db.query(ShopOption)
            .filter(ShopOption.kind == "category", ShopOption.value == name)
            .first()
        )
        if not exists:
            db.add(ShopOption(kind="category", value=name, label=name, sort_order=i))
    for i, (value, label) in enumerate(DEFAULT_DELIVERABLE_TYPES):
        exists = (
            db.query(ShopOption)
            .filter(ShopOption.kind == "deliverable_type", ShopOption.value == value)
            .first()
        )
        if not exists:
            db.add(ShopOption(kind="deliverable_type", value=value, label=label, sort_order=i))
    db.commit()


@router.get("", summary="商城选项列表（分类/权益类型）")
async def list_options(
    kind: str = Query(..., description="category 或 deliverable_type"),
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if kind not in KINDS:
        raise HTTPException(status_code=400, detail="kind 只能是 category / deliverable_type")
    ensure_defaults(db)
    rows = (
        db.query(ShopOption)
        .filter(ShopOption.kind == kind)
        .order_by(ShopOption.sort_order.asc(), ShopOption.id.asc())
        .all()
    )
    return {
        "kind": kind,
        "items": [
            {"value": r.value, "label": r.label or r.value, "custom": bool(r.custom)} for r in rows
        ],
    }


@router.post("", summary="新增自定义选项")
async def create_option(
    data: OptionCreate,
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    if data.kind not in KINDS:
        raise HTTPException(status_code=400, detail="kind 只能是 category / deliverable_type")
    value = (data.value or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="名称不能为空")
    if len(value) > 32:
        raise HTTPException(status_code=400, detail="名称过长（≤32 字）")

    exists = (
        db.query(ShopOption)
        .filter(ShopOption.kind == data.kind, ShopOption.value == value)
        .first()
    )
    if exists:
        return {"success": True, "duplicated": True, "value": value}

    max_sort = (
        db.query(ShopOption.sort_order)
        .filter(ShopOption.kind == data.kind)
        .order_by(ShopOption.sort_order.desc())
        .first()
    )
    next_sort = (max_sort[0] + 1) if max_sort else 0
    db.add(
        ShopOption(
            kind=data.kind,
            value=value,
            label=data.label.strip() or value,
            sort_order=next_sort,
            custom=1,
        )
    )
    db.commit()
    logger.info("管理员 %s 新增商城选项 %s = %s", current_user.username, data.kind, value)
    return {"success": True, "duplicated": False, "value": value}


@router.post("/sync-categories", summary="把现有商品分类补进选项表")
async def sync_categories(
    current_user: SysUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    ensure_defaults(db)
    known = {r.value for r in db.query(ShopOption).filter(ShopOption.kind == "category").all()}
    added = 0
    for (cat,) in db.query(ShopProduct.category).distinct().all():
        cat = (cat or "").strip()
        if cat and cat not in known:
            db.add(ShopOption(kind="category", value=cat, label=cat, sort_order=99))
            known.add(cat)
            added += 1
    db.commit()
    return {"success": True, "added": added}
