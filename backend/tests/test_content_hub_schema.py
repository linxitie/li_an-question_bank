"""R0 Schema Guard 测试：旧库补列 + 幂等 + 关系类型种子。"""
from sqlalchemy import create_engine, inspect, text

from app.core.content_hub_schema import ensure_content_hub_schema


def test_guard_adds_columns_and_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE essay_quote (quote_id INTEGER PRIMARY KEY, content TEXT)"))

    ensure_content_hub_schema(engine)
    ensure_content_hub_schema(engine)

    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("essay_quote")}
    assert {
        "quote_uid",
        "normalized_hash",
        "review_status",
        "source_id",
        "quality_score",
        "deleted_at",
    } <= columns
    assert "kg_relation_type" in inspector.get_table_names()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM kg_relation_type")).scalar() >= 9


def test_guard_rebuilds_empty_legacy_user_notification(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy_notify.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE user_notification ("
                "notification_id INTEGER PRIMARY KEY, user_id INTEGER, ntype TEXT, "
                "title TEXT, body TEXT, link TEXT, read_at DATETIME, created_at DATETIME)"
            )
        )

    ensure_content_hub_schema(engine)

    columns = {col["name"] for col in inspect(engine).get_columns("user_notification")}
    assert {"type", "content", "related_type", "related_id", "is_read"} <= columns
    assert "ntype" not in columns


def test_guard_adds_columns_without_losing_notification_rows(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy_notify_rows.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE user_notification ("
                "notification_id INTEGER PRIMARY KEY, user_id INTEGER, ntype TEXT, "
                "title TEXT, body TEXT, link TEXT, read_at DATETIME, created_at DATETIME)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO user_notification "
                "(notification_id, user_id, ntype, title, body) "
                "VALUES (1, 1, 'system', '旧通知', '正文')"
            )
        )

    ensure_content_hub_schema(engine)

    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("user_notification")}
    assert {"type", "content", "related_type", "related_id", "is_read"} <= columns
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM user_notification")).scalar() == 1
