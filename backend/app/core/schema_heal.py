# -*- coding: utf-8 -*-
"""模型/存量库列漂移自愈。

为什么需要它：
    Base.metadata.create_all() 只建缺失的表，不会给已有表补列；模型新增字段后，
    旧库仍缺列，ORM 一旦 SELECT 该表就会抛 "no such column" 并变成 500。
    例如 2026-11 合并后 study_material.point_id / achievement.badge_tier 缺失，
    直接导致管理员资料列表与成就接口不可用。

安全边界：
    - 只补「表已存在、模型有、库里没有」的列；不建表、不改列、不删列。
    - 只补可空列；非空列一律跳过并告警，避免在存量数据上 ALTER 失败。
      非空列应走正式迁移（带 DEFAULT 或先回填再收紧）。
    - 每次启动幂等执行，已存在的列不会重复 ALTER。
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def ensure_model_columns(engine: Engine, metadata=None) -> list[str]:
    """为已存在的表补齐模型新增的可空列，返回 table.column 列表。"""
    if metadata is None:
        from .database import Base

        metadata = Base.metadata

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    added: list[str] = []
    skipped: list[str] = []

    for table in metadata.sorted_tables:
        if table.name not in existing_tables:
            # 缺表交给 create_all；这里只处理「表在、列不全」的存量库。
            continue

        existing_columns = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_columns:
                continue
            if column.primary_key:
                skipped.append(f"{table.name}.{column.name} (primary key)")
                continue
            if not column.nullable:
                skipped.append(f"{table.name}.{column.name} (not null)")
                continue

            ddl_type = column.type.compile(dialect=engine.dialect)
            with engine.begin() as conn:
                conn.execute(
                    text(
                        f'ALTER TABLE "{table.name}" '
                        f'ADD COLUMN "{column.name}" {ddl_type}'
                    )
                )
            existing_columns.add(column.name)
            added.append(f"{table.name}.{column.name}")
            logger.info("自动迁移: %s.%s 添加列", table.name, column.name)

    if skipped:
        logger.warning("自动迁移跳过不可安全补列的字段: %s", ", ".join(skipped))
    return added
