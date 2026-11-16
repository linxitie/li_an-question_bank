"""金币台账（2026-11-04 M1）：批次化发放、FIFO 消费、到期清零。

为什么要抽成独立服务：
金币原来只有 `sys_user.total_coins` 一个数字，发放点散落在 exam/stats.py 与
growth/tasks.py 里各自 `+=`。要支持"12 个月滚动到期"就必须引入批次，
而批次意味着"发放/消费/过期"三处必须走同一套逻辑，否则余额与批次会越跑越偏。

三条不变量（所有调用方都必须满足）：
1. 任何改变余额的写操作，都要在同一事务里写一条 `coin_record`；
2. 发放 = 加余额 + 建批次；消费 = 扣余额 + 按批次 FIFO 扣 remaining；
3. 兼容历史：早期没有批次的金币，消费时允许直接扣余额（不产生批次扣减）。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..models.models import CoinLot, CoinRecord, SysUser

logger = logging.getLogger(__name__)

# 金币有效期：12 个月滚动清零（设计文档 §2.4）
DEFAULT_EXPIRE_DAYS = 365


def _add_record(
    db: Session,
    user: SysUser,
    change: int,
    *,
    transaction_type: str,
    source_type: str,
    related_id: Optional[int] = None,
    description: str = "",
) -> CoinRecord:
    record = CoinRecord(
        user_id=user.user_id,
        coin_change=change,
        current_balance=user.total_coins or 0,
        transaction_type=transaction_type,
        source_type=source_type,
        related_id=related_id,
        description=description,
    )
    db.add(record)
    return record


def grant(
    db: Session,
    user: SysUser,
    amount: int,
    *,
    source_type: str = "TASK",
    related_id: Optional[int] = None,
    description: str = "",
    expire_days: int = DEFAULT_EXPIRE_DAYS,
) -> Optional[CoinLot]:
    """发放金币：加余额 + 写 GAIN 流水 + 建批次。amount<=0 直接忽略。"""
    if amount <= 0:
        return None

    user.total_coins = (user.total_coins or 0) + amount
    _add_record(
        db,
        user,
        amount,
        transaction_type="GAIN",
        source_type=source_type,
        related_id=related_id,
        description=description,
    )

    now = datetime.now()
    lot = CoinLot(
        user_id=user.user_id,
        amount=amount,
        remaining=amount,
        source_type=source_type,
        related_id=related_id,
        description=description,
        available_at=now,
        expire_at=now + timedelta(days=expire_days),
    )
    db.add(lot)
    return lot


def spend(
    db: Session,
    user: SysUser,
    amount: int,
    *,
    source_type: str = "SHOP",
    related_id: Optional[int] = None,
    description: str = "",
) -> None:
    """消费金币：扣余额 + 写 SPEND 流水 + 按批次 FIFO 扣 remaining。

    兼容性：若批次总额小于本次消费（历史无批次金币），剩余部分只扣余额、不扣批次。
    """
    if amount <= 0:
        return

    user.total_coins = (user.total_coins or 0) - amount
    _add_record(
        db,
        user,
        -amount,
        transaction_type="SPEND",
        source_type=source_type,
        related_id=related_id,
        description=description,
    )

    remaining = amount
    now = datetime.now()
    lots = (
        db.query(CoinLot)
        .filter(
            CoinLot.user_id == user.user_id,
            CoinLot.remaining > 0,
            CoinLot.available_at <= now,
        )
        .order_by(CoinLot.expire_at.asc(), CoinLot.id.asc())
        .all()
    )
    for lot in lots:
        if remaining <= 0:
            break
        take = min(lot.remaining, remaining)
        lot.remaining -= take
        remaining -= take

    if remaining > 0:
        logger.info(
            "金币消费超出批次余额 user=%s 未覆盖=%s（历史无批次金币）",
            user.user_id,
            remaining,
        )


def expire_due(db: Session, limit: int = 500) -> dict:
    """把已到期的批次清零并写 EXPIRE 流水（由定时任务每日调用）。"""
    now = datetime.now()
    lots = (
        db.query(CoinLot)
        .filter(CoinLot.remaining > 0, CoinLot.expire_at <= now)
        .order_by(CoinLot.expire_at.asc())
        .limit(limit)
        .all()
    )

    expired_total = 0
    affected_users = 0
    for lot in lots:
        amount = lot.remaining
        user = db.query(SysUser).filter(SysUser.user_id == lot.user_id).first()
        if not user:
            lot.remaining = 0
            continue
        # 余额可能已被其它路径扣到不足，过期只扣到 0 为止
        deduct = min(amount, max(0, user.total_coins or 0))
        user.total_coins = (user.total_coins or 0) - deduct
        _add_record(
            db,
            user,
            -deduct,
            transaction_type="SPEND",
            source_type="EXPIRY",
            related_id=lot.id,
            description=f"金币到期清零（批次 #{lot.id}）",
        )
        lot.remaining = 0
        expired_total += deduct
        affected_users += 1

    if lots:
        db.commit()
        logger.info("金币到期清零：批次 %s 个，扣减 %s 币，涉及 %s 人", len(lots), expired_total, affected_users)
    return {"lots": len(lots), "expired_coins": expired_total, "users": affected_users}


def expiring_soon(db: Session, user_id: int, days: int = 30) -> dict:
    """查询用户 N 天内将到期的金币（用于提醒）。"""
    now = datetime.now()
    deadline = now + timedelta(days=days)
    lots = (
        db.query(CoinLot)
        .filter(
            CoinLot.user_id == user_id,
            CoinLot.remaining > 0,
            CoinLot.expire_at > now,
            CoinLot.expire_at <= deadline,
        )
        .order_by(CoinLot.expire_at.asc())
        .all()
    )
    total = sum(l.remaining for l in lots)
    return {
        "total": total,
        "days": days,
        "items": [
            {"lot_id": l.id, "remaining": l.remaining, "expire_at": l.expire_at.isoformat()}
            for l in lots
        ],
    }
