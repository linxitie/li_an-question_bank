"""F4：业务侧写文档投影事件（只入 Outbox，不直接写文档库）。

所有文档写入都必须经 Outbox 同事务：业务行 commit 与事件行 commit 是同一个
事务，文档库挂了只会让 Dispatcher 重试，不会回滚业务。直接调用 DocumentStore
会让重放/重建失效，F4 起禁止。
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core import events
from app.foundation import config as foundation_config
from app.foundation import outbox

logger = logging.getLogger(__name__)


def _emit(
    db: Session,
    *,
    event_name: str,
    aggregate_type: str,
    aggregate_id: object,
    payload: dict,
    producer: str,
    dedupe_key: str | None = None,
) -> str | None:
    # 关闭开关时没有消费者，写事件只会堆积；记录一次告警便于发现「文档库
    # 开着但事件总线关着」的错配配置。
    if not foundation_config.FOUNDATION_ENABLED or not foundation_config.EVENT_OUTBOX_ENABLED:
        if foundation_config.DOC_STORE_ENABLED:
            logger.warning(
                "[f4] 事件总线未启用，%s 的文档投影不会发生", event_name
            )
        return None
    return outbox.emit(
        db,
        event_name=event_name,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        producer=producer,
        dedupe_key=dedupe_key,
    )


def emit_exam_snapshot(
    db: Session, paper_id: int, *, producer: str = "catalog.papers"
) -> str | None:
    """试卷发布/更新后写快照事件；questionRefs 不含题干正文。"""
    return _emit(
        db,
        event_name=events.EV_PAPER_SNAPSHOT,
        aggregate_type="exam_paper",
        aggregate_id=paper_id,
        payload={"paper_id": int(paper_id)},
        producer=producer,
    )


def emit_import_snapshot(
    db: Session, source_table: str, import_id: int, *, producer: str
) -> str | None:
    """题目/资料导入状态变化后写快照事件。"""
    return _emit(
        db,
        event_name=(
            events.EV_QUESTION_IMPORT_SNAPSHOT
            if source_table == "question_import_record"
            else events.EV_MATERIAL_IMPORT_SNAPSHOT
        ),
        aggregate_type=source_table,
        aggregate_id=import_id,
        payload={"source_table": source_table, "import_id": int(import_id)},
        producer=producer,
    )


def emit_forum_content(
    db: Session, post_id: int, *, producer: str = "community.forum"
) -> str | None:
    """发帖/评论/删除后写论坛内容事件；软删也写，文档保留 DELETED 状态。"""
    return _emit(
        db,
        event_name=events.EV_FORUM_CONTENT_CHANGED,
        aggregate_type="forum_post",
        aggregate_id=post_id,
        payload={"post_id": int(post_id)},
        producer=producer,
    )
