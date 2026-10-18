"""事件消费者 —— 订阅 user.action.v1 并分发到成就判定。

架构（P2-53）
-------------
::

    EV_USER_ACTION
        └─ achievement_judge.judge_action()      判据：任务进度 + 成就决策
             └─ achievement_reward.grant_newly() 奖励单点：幂等发币/成长值

行为契约：

- 绝不向上抛异常：单条事件处理失败记日志、继续下一条
- 每条事件开独立 DB 会话，处理完提交；异常回滚
- 判据异常与奖励异常互不影响主流程（业务侧调用方已提交，事件只是加速器）
- 事件 payload 契约（字段只增不删）：
    user_id: int            必填
    trigger_type: str       必填（E1–E10，E5 为两个字符串值）
    session: dict|null      可选，稳定身份键用于去重
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

    # 延迟导入：避免模块加载顺序耦合，也让测试可单独 monkeypatch 判据/奖励。
    from ..models.models import SysUser
    from ..services import achievement_judge, achievement_reward

    db = SessionLocal()
    try:
        session: Optional[dict[str, Any]] = payload.get("session")
        if session is not None and not isinstance(session, dict):
            session = None

        result = achievement_judge.judge_action(
            user_id, trigger_type, db, session=session
        )
        newly = result.get("newly_unlocked") or []
        if newly:
            user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
            if user is not None:
                achievement_reward.grant_newly(db, user, newly)

        db.commit()
        if newly:
            logger.info(
                f"[consumer] 成就授予 user={user_id} trigger={trigger_type} "
                f"新增 {len(newly)} 项"
            )
    except Exception as e:  # noqa: BLE001 — 单条失败不拖垮订阅循环
        db.rollback()
        logger.warning(f"[consumer] 处理 user={user_id} "
                       f"trigger={trigger_type} 失败: {type(e).__name__}: {e}")
    finally:
        db.close()


async def _dispatch_paper_published(event: events.Event) -> None:
    """试卷发布 → 推送 data-changed 到在线端（纵向通信，事件加速器）。"""
    paper_id = (event.payload or {}).get("paper_id")
    if not isinstance(paper_id, (int, str)):
        logger.warning(f"[consumer] 试卷发布载荷缺少 paper_id: {event.payload}")
        return
    try:
        from ..api.v1.platform.websocket import (
            publish_data_changed,
            ws_connection_manager,
        )
        await publish_data_changed(
            ws_connection_manager.get_online_users(),
            domain="exam",
            type="paper.published",
            id=paper_id,
        )
    except Exception as e:  # noqa: BLE001 — 推送失败不阻断主流程
        logger.warning(f"[consumer] 试卷发布推送失败 paper_id={paper_id}: "
                       f"{type(e).__name__}: {e}")


async def consume_user_actions(idle_ms: int = 5000) -> None:
    """长驻订阅循环。Redis 不可用或 Stream 不支持时由 events 层自动降级，
    此处无需关心传输细节。

    消费者带重连：subscribe 因 Redis 断连返回后，等待重试间隔再次订阅，
    避免 Redis 重启后消费者永久静默。
    """
    import asyncio

    async def _loop(name, handler):
        while True:
            try:
                await events.subscribe([name], handler, idle_ms=idle_ms)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 — 订阅循环自身异常后重连
                logger.warning(f"[consumer] 订阅 {name} 异常，5 秒后重连: "
                               f"{type(e).__name__}: {e}")
            await asyncio.sleep(5)

    await asyncio.gather(
        _loop(events.EV_USER_ACTION, _dispatch),
        _loop(events.EV_PAPER_PUBLISHED, _dispatch_paper_published),
    )


async def record_user_action(db, user_id: int, trigger_type: str,
                             session=None) -> bool:
    """发布 user.action 事件；Redis 不可用时同步兜底走判据 + 奖励单点。

    折中方案（P5.2）：保证重要数据不丢失——
    - publish 成功 → 消费者异步判定/授予（不阻塞请求），返回 True
    - publish 失败（Redis 宕机）→ 立即同步兜底判定 + 发奖，返回 False
    """
    ok = await events.publish(events.Event(
        name=events.EV_USER_ACTION,
        payload={"user_id": user_id, "trigger_type": trigger_type,
                 "session": session if isinstance(session, dict) else None},
        aggregate_id=f"u-{user_id}",
    ))
    if not ok:
        from ..models.models import SysUser
        from ..services import achievement_judge, achievement_reward

        logger.warning(f"[consumer] Redis 不可用，同步兜底判定: "
                       f"user={user_id} trigger={trigger_type}")
        try:
            result = achievement_judge.judge_action(
                user_id, trigger_type, db, session=session
            )
            newly = result.get("newly_unlocked") or []
            if newly:
                user = db.query(SysUser).filter(SysUser.user_id == user_id).first()
                if user is not None:
                    achievement_reward.grant_newly(db, user, newly)
            # 判据可能更新了 badge_task 进度，需要由本函数提交。
            db.commit()
        except Exception as e:  # noqa: BLE001 — 兜底失败不影响业务主流程
            db.rollback()
            logger.warning(f"[consumer] 同步兜底失败 user={user_id} "
                           f"trigger={trigger_type}: {type(e).__name__}: {e}")
    return ok
