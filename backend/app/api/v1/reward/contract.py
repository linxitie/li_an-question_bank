"""reward 域公开契约 —— 跨域唯一合法的发币入口。

其它域不得直接实例化 CoinRecord 或改写 total_coins，
一律经 grant_coins / spend_coins。P4.2 逐点改造时新增契约函数，
字段只增不删。
"""
from __future__ import annotations

from typing import Optional

from ....models.models import CoinRecord


def grant_coins(db, user, amount: int, *, source_type: str,
                related_id: Optional[int] = None,
                description: Optional[str] = None) -> int:
    """加币并落流水。返回新余额。不 commit，随调用方事务一起提交。"""
    user.total_coins = (user.total_coins or 0) + amount
    db.add(CoinRecord(
        user_id=user.user_id,
        coin_change=amount,
        current_balance=user.total_coins,
        transaction_type="GAIN",
        source_type=source_type,
        related_id=related_id,
        description=description,
    ))
    return user.total_coins


def spend_coins(db, user, amount: int, *, source_type: str,
                related_id: Optional[int] = None,
                description: Optional[str] = None) -> int:
    """扣币并落流水。余额不足时抛 ValueError，由调用方决定如何呈现。"""
    balance = user.total_coins or 0
    if balance < amount:
        raise ValueError(f"金币不足：余额 {balance}，需要 {amount}")
    user.total_coins = balance - amount
    db.add(CoinRecord(
        user_id=user.user_id,
        coin_change=-amount,
        current_balance=user.total_coins,
        transaction_type="SPEND",
        source_type=source_type,
        related_id=related_id,
        description=description,
    ))
    return user.total_coins


def has_grant(db, user_id: int, *, source_type: str, related_id: int) -> bool:
    """是否已发过该来源/关联对象的币（供其他域做幂等判断，不必直接查 CoinRecord）。"""
    from sqlalchemy import func as _f

    n = (db.query(_f.count(CoinRecord.record_id))
         .filter(CoinRecord.user_id == user_id,
                 CoinRecord.source_type == source_type,
                 CoinRecord.related_id == related_id)
         .scalar() or 0)
    return int(n) > 0


def sum_granted(db, user_id: int, *, source_type: str, since=None) -> int:
    """某来源的累计发币量（since 传 datetime 时只统计该时间之后）。"""
    from sqlalchemy import func as _f

    q = (db.query(_f.coalesce(_f.sum(CoinRecord.coin_change), 0))
         .filter(CoinRecord.user_id == user_id,
                 CoinRecord.source_type == source_type,
                 CoinRecord.coin_change > 0))
    if since is not None:
        q = q.filter(CoinRecord.transaction_time >= since)
    return int(q.scalar() or 0)
