"""内容安全知识库 Schema Guard。

职责：启动时幂等建 cg_* 表并种入目录；不写业务数据、不改既有表。
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from .database import Base

logger = logging.getLogger(__name__)

_REQUIRED_TABLES = (
    "cg_policy",
    "cg_term",
    "cg_variant",
    "cg_judgment",
    "cg_task",
    "cg_proposal",
    "cg_case",
    "cg_audit_event",
    "cg_edge",
    "cg_stat_daily",
    "cg_redteam_sample",
    "cg_sync_state",
)


def ensure_content_guard_schema(engine: Engine) -> dict:
    from ..models import content_guard  # noqa: F401  # 触发模型注册
    from ..models import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    present = set(inspector.get_table_names())
    missing = [name for name in _REQUIRED_TABLES if name not in present]

    db = sessionmaker(bind=engine)()
    try:
        from ..services.content_guard import seed_defaults

        report = seed_defaults(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    report["missing_tables"] = missing
    if missing:
        logger.error("内容安全知识库缺表: %s", missing)
    return report
