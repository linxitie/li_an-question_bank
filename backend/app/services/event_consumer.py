"""事件消费者 —— 订阅 user.action.v1 并分发到成就判定。

P5.2 基础设施。当前 13 处 fire-and-forget 调用点仍走同步直调，
本消费者默认**不启动**（由配置 EVENT_CONSUMER_ENABLED 控制），
仅在调用点改造完成后启用。行为契约：

- 绝不向上抛异常：单条事件处理失败记日志、继续下一条
- 每条事件开独立 DB 会话，处理完提交；异常回滚
- 事件 payload 契约（字段只增不删）：
    user_id: int            必填
    trigger_type: str       必填（sign_in/view_wrong/chop/post/quote_favorite/
                             favorite/note/review 等既有触发类型）
    session: dict|null      可选，仅 do_question 类触发传入
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from ..core import events
from ..core.database import SessionLocal

logger = logging.getLogger(__name__)


async def _dispatch(event: events.Event) -> None:
    payload = event.payload
    user_id = payload.get("user_id")
    trigger_type = payload.get("trigger_type")
    if not isinstance(user_id, int) or not isinstance(trigger_type, str):
        logger.warning(f"[consumer] user.action 载荷不完整，跳过: {payload}")
        return

    from ..services import achievement_service

    db = SessionLocal()
    try:
        session: Optional[dict[str, Any]] = payload.get("session")
        if session is not None and not isinstance(session, dict):
            session = None
        newly = achievement_service.check_and_grant(
            user_id, trigger_type, db, session=session)
        db.commit()
        if newly:
            logger.info(f"[consumer] 成就授予 user={user_id} "
                        f"trigger={trigger_type} 新增 {len(newly)} 项")
    except Exception as e:  # noqa: BLE001 — 单条失败不拖垮订阅循环
        db.rollback()
        logger.warning(f"[consumer] 处理 user={user_id} "
                       f"trigger={trigger_type} 失败: {type(e).__name__}: {e}")
    finally:
        db.close()


async def consume_user_actions(idle_ms: int = 5000) -> None:
    """长驻订阅循环。Redis 不可用或 Stream 不支持时由 events 层自动降级，
    此处无需关心传输细节。"""
    await events.subscribe([events.EV_USER_ACTION], _dispatch, idle_ms=idle_ms)