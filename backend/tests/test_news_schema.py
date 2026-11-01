"""R2 新闻 Schema Guard / FTS 测试。"""
from sqlalchemy import create_engine, inspect, text

from app.core.news_schema import ensure_news_schema


def _legacy_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'news_legacy.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE news_article ("
            "news_id INTEGER PRIMARY KEY, title TEXT, url TEXT, source TEXT, "
            "category TEXT, publish_date DATETIME, summary TEXT, content TEXT, "
            "status INTEGER, create_time DATETIME)"
        ))
        conn.execute(text(
            "INSERT INTO news_article(news_id,title,url,source,category,summary,content,status) "
            "VALUES (1,'坚持和发展枫桥经验','https://x/1','people','理论','基层治理','枫桥经验',1)"
        ))
    return engine


def test_guard_adds_columns_categories_and_fts(tmp_path):
    engine = _legacy_engine(tmp_path)

    ensure_news_schema(engine)
    ensure_news_schema(engine)

    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("news_article")}
    assert {"category_code", "content_hash", "review_status", "event_date"} <= columns
    assert "news_category" in inspector.get_table_names()
    with engine.connect() as conn:
        assert conn.execute(text("SELECT category_code FROM news_article WHERE news_id=1")).scalar() == "theory"
        assert conn.execute(text("SELECT COUNT(*) FROM news_category")).scalar() >= 3
        ids = [row[0] for row in conn.execute(text(
            "SELECT news_id FROM news_fts WHERE news_fts MATCH '枫桥经验'"
        )).all()]
        assert ids == [1]
        assert conn.execute(text("SELECT COUNT(*) FROM news_fts")).scalar() == 1
