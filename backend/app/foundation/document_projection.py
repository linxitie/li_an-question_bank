"""F4：文档投影处理器（Outbox 消费侧，只重建文档库，不写业务表）。

所有写入口都经 Outbox 同事务事件；handler 不 commit，失败由 Dispatcher
回滚重试。文档库故障必须上抛（DocumentStoreUnavailable），不得吞掉后
让文档库与事实源永久漂移。
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.foundation import config as foundation_config
from app.foundation.document_schema import (
    build_exam_resource,
    build_forum_content,
    build_import_snapshot,
)
from app.foundation.inbox import claim
from app.foundation.stores.base import OutboxEvent
from app.foundation.stores.document import build_document_store

logger = logging.getLogger(__name__)

EXAM_CONSUMER = "f4_document_exam"
QUESTION_IMPORT_CONSUMER = "f4_document_question_import"
MATERIAL_IMPORT_CONSUMER = "f4_document_material_import"
FORUM_CONSUMER = "f4_document_forum"


def exam_key(paper_id: int | str) -> str:
    return str(paper_id)


def import_key(source_table: str, import_id: int | str) -> str:
    return f"{source_table}:{import_id}"


def forum_key(post_id: int | str) -> str:
    return str(post_id)


def _as_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _upsert(session: Session, collection: str, key: str, builder, event: OutboxEvent) -> None:
    if not foundation_config.DOC_STORE_ENABLED:
        logger.debug("[f4] 文档存储关闭，跳过 %s/%s", collection, key)
        return
    doc = builder()
    if doc is None:
        logger.info("[f4] 源数据不完整，跳过文档 %s/%s", collection, key)
        return
    # 用全局 outbox id 作 version：回填写 1 后，任何后续增量 id 都更大，
    # 避免 aggregate_ver 从 1 重来把新文档挡在旧版本之外。
    version = max(1, int(event.id or 0))
    build_document_store().upsert(collection, key, doc, version=version)


def handle_exam_snapshot(session: Session, event: OutboxEvent) -> None:
    payload = event.payload or {}
    paper_id = _as_int(payload.get("paper_id") or event.aggregate_id)
    if paper_id is None:
        logger.warning("[f4] 试卷快照缺少 paper_id: %s", payload)
        return
    if not claim(session, EXAM_CONSUMER, event):
        return
    _upsert(
        session,
        "exam_resources",
        exam_key(paper_id),
        lambda: build_exam_resource(session, paper_id, version=max(1, int(event.id or 1))),
        event,
    )


def _import_handler(consumer: str, source_table: str, prefix: str):
    def handler(session: Session, event: OutboxEvent) -> None:
        payload = event.payload or {}
        import_id = _as_int(payload.get("import_id") or event.aggregate_id)
        if import_id is None:
            logger.warning("[f4] %s 快照缺少 import_id: %s", prefix, payload)
            return
        if not claim(session, consumer, event):
            return
        key = import_key(source_table, import_id)
        _upsert(
            session,
            "import_snapshots",
            key,
            lambda: build_import_snapshot(
                session, source_table, import_id, version=max(1, int(event.id or 1))
            ),
            event,
        )

    return handler


def handle_forum_changed(session: Session, event: OutboxEvent) -> None:
    payload = event.payload or {}
    post_id = _as_int(payload.get("post_id") or event.aggregate_id)
    if post_id is None:
        logger.warning("[f4] 论坛文档缺少 post_id: %s", payload)
        return
    if not claim(session, FORUM_CONSUMER, event):
        return
    _upsert(
        session,
        "forum_contents",
        forum_key(post_id),
        lambda: build_forum_content(session, post_id, version=max(1, int(event.id or 1))),
        event,
    )


handle_question_import_snapshot = _import_handler(
    QUESTION_IMPORT_CONSUMER, "question_import_record", "题目导入"
)
handle_material_import_snapshot = _import_handler(
    MATERIAL_IMPORT_CONSUMER, "material_import_record", "资料导入"
)
