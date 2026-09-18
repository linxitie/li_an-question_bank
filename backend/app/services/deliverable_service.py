"""
金币购权益发放服务

职责：根据兑换记录(CoinExchange)的 deliverable_type 分发兑现权益。
- 与 shop 兑换逻辑解耦：新增权益类型只需在此新增分支，不改调用方。
- 幂等：兑换层已用 request_id 保证不重复扣币；本层对已存在权益用唯一约束兜底。
- 原子：由 shop.py 在兑换事务内调用本服务，统一 commit，保证「扣币 + 权益」同生共死。
"""
import logging
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models.models import SysUser, CoinExchange, UserTitle

logger = logging.getLogger(__name__)


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

    # 未知权益类型：记录日志，不阻断兑换（权益层后置扩展点的兜底）
    logger.warning(f"未知权益类型 deliverable_type={dtype!r}，跳过兑现 exchange_id={exchange.id}")
    return False


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
    """兑现头像框：写入 sys_user.avatar_frame"""
    frame_id = payload.get("frame_id")
    if not frame_id:
        logger.error(f"头像框权益缺少 frame_id，payload={payload}")
        return False

    setattr(user, "avatar_frame", str(frame_id))
    logger.info(f"用户 {user.user_id} 兑换头像框 {frame_id} 成功")
    return True
