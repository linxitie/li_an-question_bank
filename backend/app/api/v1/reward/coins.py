"""
金币 API：余额概览 + 分页流水
"""
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from ....core.database import get_db
from ....core.security import get_current_user
from ....models.models import SysUser, CoinRecord
from ....services import coin_ledger

router = APIRouter(prefix="/api/coins", tags=["金币"])


@router.get("/overview", summary="金币余额概览")
async def coins_overview(
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """返回余额 + 本月收入/支出"""
    month_start = datetime.now().replace(day=1)

    income = db.query(func.coalesce(func.sum(CoinRecord.coin_change), 0)).filter(
        CoinRecord.user_id == current_user.user_id,
        CoinRecord.transaction_type == "GAIN",
        CoinRecord.transaction_time >= month_start,
    ).scalar() or 0

    expense = db.query(func.coalesce(func.sum(CoinRecord.coin_change), 0)).filter(
        CoinRecord.user_id == current_user.user_id,
        CoinRecord.transaction_type == "SPEND",
        CoinRecord.transaction_time >= month_start,
    ).scalar() or 0

    # M1：把"快到期"的额度一起返回，前端可在余额旁提示，避免用户白丢金币
    expiring = coin_ledger.expiring_soon(db, current_user.user_id, days=30)

    return {
        "balance": current_user.total_coins or 0,
        "month_income": int(income),
        "month_expense": abs(int(expense)),
        "expiring_30d": expiring["total"],
    }


@router.get("/expiring", summary="近 N 天将到期的金币明细")
async def coins_expiring(
    days: int = Query(30, ge=1, le=365),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """金币有效期 12 个月滚动清零；该接口供"到期提醒"与"兜底换券"入口使用。"""
    return coin_ledger.expiring_soon(db, current_user.user_id, days=days)


@router.get("/transactions", summary="金币流水（分页）")
async def coins_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """分页返回金币流水，按时间倒序"""
    query = db.query(CoinRecord).filter(CoinRecord.user_id == current_user.user_id)
    total = query.count()
    items = query.order_by(CoinRecord.transaction_time.desc())\
        .offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "record_id": r.record_id,
                "coin_change": r.coin_change,
                "current_balance": r.current_balance,
                "transaction_type": r.transaction_type,
                "source_type": r.source_type,
                "description": r.description,
                "transaction_time": r.transaction_time.isoformat() if r.transaction_time else None,
            }
            for r in items
        ],
    }
