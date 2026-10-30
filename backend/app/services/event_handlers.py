"""F2b：Outbox 事件处理器（与业务写同一事务之外的消费侧）。

Dispatcher 在同一事务里依次调用 handler、mark_dispatched、advance cursor。
handler 只做两件事：
1. claim 幂等收件（foundation_inbox，重复投递直接跳过）；
2. 执行副作用（成就判定/发奖、定向 data-changed）。

handler 不 commit：失败由 Dispatcher 回滚并重试，成功与游标一起提交。
WS 推送失败只记日志，不回滚成就数据——推送是加速器，不是事实源。
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core import events
from app.foundation.event_routes import route_for
from app.foundation.inbox import claim
from app.foundation.stores.base import OutboxEvent

logger = logging.getLogger(__name__)

USER_ACTION_CONSUMER = "f2b_user_action"
PAPER_PUBLISHED_CONSUMER = "f2b_paper_published"


def handle_user_action(session: Session, event: OutboxEvent) -> None:
    payload = event.payload or {}
    user_id = payload.get("user_id")
    trigger_type = payload.get("trigger_type")
    if not isinstance(user_id, int) or not isinstance(trigger_type, str):
        logger.warning("[f2b] user.action 载荷不完整，跳过: %s", payload)
        return
    if not claim(session, USER_ACTION_CONSUMER, event):
        logger.debug("[f2b] 重复事件已跳过 id=%s", event.event_id)
        return

    from app.models.models import SysUser
    from app.services import achievement_judge, achievement_reward

    session_data = payload.get("session")
    if session_data is not None and not isinstance(session_data, dict):
        session_data = None
    result = achievement_judge.judge_action(
        user_id, trigger_type, session, session=session_data
    )
    newly = result.get("newly_unlocked") or []
    if newly:
        user = session.query(SysUser).filter(SysUser.user_id == user_id).first()
        if user is not None:
            achievement_reward.grant_newly(session, user, newly)
        logger.info(
            "[f2b] 成就授予 user=%s trigger=%s 新增 %s 项",
            user_id,
            trigger_type,
            len(newly),
        )

    route = route_for(trigger_type)
    user_ids, roles = route.recipients(user_id)
    try:
        from app.api.v1.platform.websocket import publish_data_changed_sync

        publish_data_changed_sync(
            user_ids,
            domain=route.domain,
            type=route.type,
            id=event.event_id,
            roles=roles,
            outbox_id=event.id,
        )
    except Exception as exc:  # noqa: BLE001 - 推送失败不影响成就事实
        logger.warning("[f2b] data-changed 推送失败 trigger=%s: %s", trigger_type, exc)


def handle_paper_published(session: Session, event: OutboxEvent) -> None:
    payload = event.payload or {}
    paper_id = payload.get("paper_id")
    if not isinstance(paper_id, (int, str)):
        logger.warning("[f2b] 试卷发布载荷缺少 paper_id: %s", payload)
        return
    if not claim(session, PAPER_PUBLISHED_CONSUMER, event):
        return
    try:
        from app.api.v1.platform.websocket import publish_data_changed_sync

        publish_data_changed_sync(
            None,
            domain="exam",
            type="paper.published",
            id=paper_id,
            roles=("student", "teacher", "admin"),
            outbox_id=event.id,
        )
    except Exception as exc:  # noqa: BLE001 - 推送失败不回滚发布事实
        logger.warning("[f2b] 试卷发布推送失败 paper_id=%s: %s", paper_id, exc)


def build_handlers() -> dict[str, object]:
    from app.foundation import document_projection

    return {
        events.EV_USER_ACTION: handle_user_action,
        events.EV_PAPER_PUBLISHED: handle_paper_published,
        events.EV_PAPER_SNAPSHOT: document_projection.handle_exam_snapshot,
        events.EV_QUESTION_IMPORT_SNAPSHOT: (
            document_projection.handle_question_import_snapshot
        ),
        events.EV_MATERIAL_IMPORT_SNAPSHOT: (
            document_projection.handle_material_import_snapshot
        ),
        events.EV_FORUM_CONTENT_CHANGED: document_projection.handle_forum_changed,
    }
