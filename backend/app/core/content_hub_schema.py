"""内容知识中枢 R0 Schema Guard。

职责：
1. 确保新表存在（依赖 models.py 中的模型定义）；
2. 对既有 SQLite 表幂等补列（create_all 不会 ALTER）；
3. 种入关系类型注册表。

只在应用启动或显式脚本中调用；不在此处写业务数据。
"""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from .database import Base

# 既有表需要补的列：table -> [(column, ddl_type)]
_CONTENT_HUB_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "essay_quote": [
        ("quote_uid", "TEXT"),
        ("normalized_hash", "TEXT"),
        ("review_status", "TEXT NOT NULL DEFAULT 'published'"),
        ("source_id", "INTEGER"),
        ("quality_score", "REAL"),
        ("deleted_at", "DATETIME"),
    ],
}

# 当前基线 user_notification 的字段（R0 早期版本用过 ntype/body/read_at）
_USER_NOTIFICATION_COLUMNS: list[tuple[str, str]] = [
    ("type", "TEXT NOT NULL DEFAULT 'system'"),
    ("content", "TEXT"),
    ("related_type", "TEXT"),
    ("related_id", "INTEGER"),
    ("is_read", "INTEGER DEFAULT 0"),
]

# 关系类型初始数据（relation, description, directed, src_types, dst_types）
RELATION_SEED: tuple[tuple[str, str, int, str, str], ...] = (
    ("covers", "内容覆盖考点", 1, '["quote","news","recruitment"]', '["knowledge_point"]'),
    ("has_topic", "内容归属主题", 1, '["quote","news","recruitment"]', '["topic"]'),
    ("derived_from", "内容来源", 1, '["quote","news","recruitment"]', '["source"]'),
    ("related_to", "相似内容", 0, '["quote","news"]', '["quote","news"]'),
    ("opposite_to", "对立观点", 0, '["quote"]', '["quote"]'),
    ("scheduled_as", "招考对应事件", 1, '["recruitment"]', '["event"]'),
    ("prerequisite_of", "先修考点", 1, '["knowledge_point"]', '["knowledge_point"]'),
    ("broader_than", "主题上位", 1, '["topic"]', '["topic"]'),
    ("has_evidence", "内容证据", 1, '["quote","news","recruitment"]', '["media"]'),
)


def _migrate_user_notification(engine: Engine, inspector) -> None:
    """把 R0 早期的 user_notification 结构迁到当前基线。

    - 空表：直接删除，交由 create_all 按当前模型重建；
    - 有数据：只补缺失列，保留原数据与旧列。
    """
    tables = set(inspector.get_table_names())
    if "user_notification" not in tables:
        return
    existing = {col["name"] for col in inspector.get_columns("user_notification")}
    missing = [(name, ddl) for name, ddl in _USER_NOTIFICATION_COLUMNS if name not in existing]
    if not missing:
        return
    with engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM user_notification")).scalar() or 0
        if count == 0:
            conn.execute(text("DROP TABLE user_notification"))
            return
        for name, ddl in missing:
            conn.execute(text(f'ALTER TABLE "user_notification" ADD COLUMN "{name}" {ddl}'))


def ensure_content_hub_schema(engine: Engine) -> None:
    """幂等建表、补列、种关系类型；可重复调用。"""
    # 确保所有 ORM 模型已注册到 metadata，再建缺失的新表
    from ..models import models  # noqa: F401  # 触发模型注册

    inspector = inspect(engine)
    _migrate_user_notification(engine, inspector)

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    for table, columns in _CONTENT_HUB_COLUMNS.items():
        if table not in tables:
            continue
        existing = {col["name"] for col in inspector.get_columns(table)}
        missing = [(name, ddl) for name, ddl in columns if name not in existing]
        if not missing:
            continue
        with engine.begin() as conn:
            for name, ddl in missing:
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {ddl}'))

    with engine.begin() as conn:
        for relation, description, directed, src_types, dst_types in RELATION_SEED:
            conn.execute(
                text(
                    "INSERT OR IGNORE INTO kg_relation_type "
                    "(relation, description, directed, src_types, dst_types) "
                    "VALUES (:relation, :description, :directed, :src_types, :dst_types)"
                ),
                {
                    "relation": relation,
                    "description": description,
                    "directed": directed,
                    "src_types": src_types,
                    "dst_types": dst_types,
                },
            )
