"""周任务设计分配 Schema Guard：启动时幂等建 weekly_task_* 四张表。

不写业务数据；导入由 scripts/import_weekly_task_pack.py 显式执行。
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from .database import Base

logger = logging.getLogger(__name__)

_REQUIRED_TABLES = (
    "weekly_task_theme",
    "weekly_task_template",
    "weekly_task_plan",
    "weekly_task_instance",
)


def ensure_weekly_task_schema(engine: Engine) -> dict:
    from ..models import weekly_task  # noqa: F401  # 触发模型注册
    from ..models import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    present = set(inspector.get_table_names())
    missing = [name for name in _REQUIRED_TABLES if name not in present]
    if missing:
        logger.error("周任务设计分配缺表: %s", missing)
    return {"missing_tables": missing}
