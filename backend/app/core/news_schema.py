"""R2 新闻 Schema Guard：新表、扩列、分类种子与 FTS5 trigram。"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from .database import Base
from .news_sources import NEWS_SOURCES

logger = logging.getLogger(__name__)

NEWS_COLUMNS = (
    ("category_code", "TEXT"),
    ("content_hash", "TEXT"),
    ("review_status", "TEXT NOT NULL DEFAULT 'published'"),
    ("event_date", "DATE"),
    ("region_code", "TEXT"),
    ("source_id", "INTEGER REFERENCES content_source(source_id)"),
    ("deleted_at", "DATETIME"),
    ("ai_summary", "TEXT"),
    ("ai_exam_points", "TEXT"),
    ("ai_entities", "TEXT"),
    ("ai_risk_flags", "TEXT"),
    ("ai_status", "TEXT DEFAULT 'pending'"),
    ("ai_confidence", "REAL"),
    ("ai_run_at", "DATETIME"),
)

CATEGORY_SEED = (
    ("theory", "理论", 10),
    ("party_history", "党史", 20),
    ("police_news", "公安报", 30),
    ("current_politics", "时政", 40),
    ("policy", "政策", 50),
    ("heroes", "英模事迹", 60),
    ("local_recruitment", "地方招警", 70),
)

CATEGORY_ALIASES = {
    "理论": "theory",
    "党史": "party_history",
    "公安报": "police_news",
    "公安要闻": "police_news",
    "时政": "current_politics",
    "政策": "policy",
    "英模事迹": "heroes",
    "招警": "local_recruitment",
    "地方招警": "local_recruitment",
}


def ensure_news_schema(engine: Engine) -> None:
    """幂等升级新闻表、分类字典、来源注册表与 FTS。"""
    from ..models import models  # noqa: F401 触发模型注册

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "news_article" in tables:
        existing = {col["name"] for col in inspector.get_columns("news_article")}
        missing = [(name, ddl) for name, ddl in NEWS_COLUMNS if name not in existing]
        with engine.begin() as conn:
            for name, ddl in missing:
                conn.execute(text(f'ALTER TABLE news_article ADD COLUMN "{name}" {ddl}'))
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_news_category_code ON news_article(category_code)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_news_review_status ON news_article(review_status)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_news_content_hash ON news_article(content_hash)"
                )
            )
    if "news_image" in tables:
        existing_image = {col["name"] for col in inspector.get_columns("news_image")}
        if "media_asset_id" not in existing_image:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        'ALTER TABLE news_image ADD COLUMN "media_asset_id" TEXT '
                        "REFERENCES media_assets(asset_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_news_image_media_asset "
                        "ON news_image(media_asset_id)"
                    )
                )

    with engine.begin() as conn:
        for code, name, sort in CATEGORY_SEED:
            conn.execute(
                text(
                    "INSERT OR IGNORE INTO news_category "
                    "(category_code, name, sort, enabled) VALUES (:code, :name, :sort, 1)"
                ),
                {"code": code, "name": name, "sort": sort},
            )
        for source in NEWS_SOURCES:
            conn.execute(
                text(
                    "INSERT OR IGNORE INTO news_source "
                    "(source_code, name, base_url, adapter, cron, trust_level, enabled, robots_note) "
                    "VALUES (:code, :name, :base_url, :adapter, '0 8,18 * * *', :trust, :enabled, :note)"
                ),
                {
                    "code": source.code,
                    "name": source.name,
                    "base_url": source.base_url,
                    "adapter": source.adapter,
                    "trust": source.trust_level,
                    "enabled": source.enabled,
                    "note": "待人工确认授权/robots",
                },
            )
        for name, code in CATEGORY_ALIASES.items():
            conn.execute(
                text(
                    "UPDATE news_article SET category_code = :code "
                    "WHERE category = :name AND (category_code IS NULL OR category_code = '')"
                ),
                {"code": code, "name": name},
            )
        conn.execute(
            text(
                "UPDATE news_article SET review_status = 'published' "
                "WHERE review_status IS NULL OR review_status = ''"
            )
        )

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS news_fts USING fts5("
                    "news_id UNINDEXED, title, summary, content, tokenize='trigram')"
                )
            )
            conn.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS news_fts_ai AFTER INSERT ON news_article BEGIN "
                    "INSERT INTO news_fts(news_id, title, summary, content) "
                    "VALUES (new.news_id, new.title, COALESCE(new.summary, ''), COALESCE(new.content, '')); "
                    "END"
                )
            )
            conn.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS news_fts_ad AFTER DELETE ON news_article BEGIN "
                    "DELETE FROM news_fts WHERE news_id = old.news_id; END"
                )
            )
            conn.execute(
                text(
                    "CREATE TRIGGER IF NOT EXISTS news_fts_au AFTER UPDATE ON news_article BEGIN "
                    "DELETE FROM news_fts WHERE news_id = old.news_id; "
                    "INSERT INTO news_fts(news_id, title, summary, content) "
                    "VALUES (new.news_id, new.title, COALESCE(new.summary, ''), COALESCE(new.content, '')); "
                    "END"
                )
            )
            conn.execute(text("DELETE FROM news_fts"))
            conn.execute(
                text(
                    "INSERT INTO news_fts(news_id, title, summary, content) "
                    "SELECT news_id, title, COALESCE(summary, ''), COALESCE(content, '') FROM news_article"
                )
            )
    except Exception as exc:  # FTS5 不可用时保留业务可用性
        logger.warning("news FTS unavailable: %s", exc)
