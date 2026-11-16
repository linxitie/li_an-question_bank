"""
金币购权益发放服务

职责：根据兑换记录(CoinExchange)的 deliverable_type 分发兑现权益。
- 与 shop 兑换逻辑解耦：新增权益类型只需在此新增分支，不改调用方。
- 幂等：兑换层已用 request_id 保证不重复扣币；本层对已存在权益用唯一约束兜底。
- 原子：由 shop.py 在兑换事务内调用本服务，统一 commit，保证「扣币 + 权益」同生共死。

交付类型（M1.5 2026-11-05 扩展）：
| type | 交付物 | 备注 |
|---|---|---|
| title | user_title 记录 | 称号，待用户佩戴 |
| avatar_frame | sys_user.avatar_frame | 头像框，立即生效 |
| code | shop_code 卡密 | 视频会员/电商卡；**无码时兑换层在扣币前拒绝** |
| manual | 待人工处理 | 实物发货 / 需运营开通；兑换单置 pending |
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.models import SysUser, CoinExchange, UserTitle, ShopCode

logger = logging.getLogger(__name__)

# 受支持的交付类型；'none' 与未知类型会被兑换层拒绝，防止"扣了币什么都没拿到"
SUPPORTED_DELIVERABLE_TYPES = {"title", "avatar_frame", "code", "manual"}


def deliver(exchange: CoinExchange, user: SysUser, db: Session) -> bool:
    """
    按兑换记录的 deliverable_type 分发权益。

    返回 True 表示已兑现（或已存在、幂等跳过）；False 表示权益类型未知。
    """
    dtype = (exchange.deliverable_type or "").strip()
    payload = exchange.deliverable_payload if isinstance(exchange.deliverable_payload, dict) else {}

    if dtype == "title":
        return _deliver_title(user, payload, db)

    if dtype == "avatar_frame":
        return _deliver_avatar_frame(user, payload)

    if dtype == "code":
        return _deliver_code(exchange, db)

    if dtype == "manual":
        # 实物 / 需运营开通：兑换单保持 pending，等人工发货或开通
        exchange.status = "pending"
        logger.info("兑换 %s 需要人工处理（manual 交付）", exchange.id)
        return True

    # 未知权益类型：记录日志并返回 False。
    # 兑换层会在扣币前用 SUPPORTED_DELIVERABLE_TYPES 拒绝，这里只是兜底。
    logger.warning(f"未知权益类型 deliverable_type={dtype!r}，跳过兑现 exchange_id={exchange.id}")
    return False


def _deliver_code(exchange: CoinExchange, db: Session) -> bool:
    """发放卡密：从 shop_code 池里按最早入库领取一条，写回兑换单。

    幂等：同一兑换单已发过码就直接返回，避免重复领取。
    """
    if exchange.delivered_code:
        return True

    row = (
        db.query(ShopCode)
        .filter(ShopCode.product_id == exchange.product_id, ShopCode.status == "available")
        .order_by(ShopCode.id.asc())
        .first()
    )
    if not row:
        logger.error(
            "卡密不足，兑换未完成交付 exchange_id=%s product_id=%s",
            exchange.id,
            exchange.product_id,
        )
        return False

    row.status = "assigned"
    row.assigned_user_id = exchange.user_id
    row.assigned_at = datetime.now()
    row.exchange_id = exchange.id

    exchange.delivered_code = row.code
    exchange.delivered_at = datetime.now()
    exchange.status = "completed"
    exchange.completed_at = datetime.now()
    logger.info("兑换 %s 发放卡密成功", exchange.id)
    return True


def has_available_code(db: Session, product_id: int) -> bool:
    """兑换前置检查：code 类商品是否有可发放的卡密。"""
    return (
        db.query(ShopCode.id)
        .filter(ShopCode.product_id == product_id, ShopCode.status == "available")
        .first()
        is not None
    )


def _deliver_title(user: SysUser, payload: dict, db: Session) -> bool:
    """兑现称号：写入 user_title（equipped=0，待用户佩戴）"""
    title_id = payload.get("title_id")
    if not title_id:
        logger.error(f"称号权益缺少 title_id，payload={payload}")
        return False

    # 唯一约束 uk_user_title(user_id, title_id) 兜底：已拥有则幂等跳过
    exists = db.query(UserTitle).filter(
        UserTitle.user_id == user.user_id,
        UserTitle.title_id == title_id,
    ).first()
    if exists:
        logger.info(f"用户 {user.user_id} 已拥有称号 {title_id}，跳过")
        return True

    db.add(UserTitle(user_id=user.user_id, title_id=title_id, equipped=0))
    logger.info(f"用户 {user.user_id} 兑换称号 {title_id} 成功")
    return True


def _deliver_avatar_frame(user: SysUser, payload: dict) -> bool:
    """兑现头像框：写入 sys_user.avatar_frame

    兼容三种 payload 键：`frame`（商品种子用）/`frame_id`（早期约定）/`avatar_frame`。
    """
    frame_id = payload.get("frame") or payload.get("frame_id") or payload.get("avatar_frame")
    if not frame_id:
        logger.error(f"头像框权益缺少 frame，payload={payload}")
        return False

    setattr(user, "avatar_frame", str(frame_id))
    logger.info(f"用户 {user.user_id} 兑换头像框 {frame_id} 成功")
    return True
