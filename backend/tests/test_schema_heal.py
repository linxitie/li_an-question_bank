# -*- coding: utf-8 -*-
"""存量库列漂移自愈的回归测试。

背景：create_all 不会给已有表补列，模型新增字段后 ORM SELECT 直接 500。
本测试用一张「只有 id」的旧表模拟存量库，验证只补可空列、跳过非空列，且幂等。
"""
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, text

from app.core.schema_heal import ensure_model_columns


def _legacy_engine():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE legacy (id INTEGER PRIMARY KEY)"))
    metadata = MetaData()
    Table(
        "legacy",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("new_nullable", String(20), nullable=True),
        Column("required_without_default", Integer, nullable=False),
        Column("required_with_default", Integer, default=0, nullable=False),
    )
    return engine, metadata


def test_adds_only_safe_missing_columns():
    engine, metadata = _legacy_engine()
    added = ensure_model_columns(engine, metadata=metadata)

    assert added == ["legacy.new_nullable"]

    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(legacy)"))}
    assert {"id", "new_nullable"} <= cols
    assert "required_without_default" not in cols
    assert "required_with_default" not in cols


def test_is_idempotent():
    engine, metadata = _legacy_engine()
    ensure_model_columns(engine, metadata=metadata)
    assert ensure_model_columns(engine, metadata=metadata) == []
