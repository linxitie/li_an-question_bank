-- F3 媒体资产元数据（Relational SoT）
-- 字节在 Object 投影（local/MinIO），本表只存元数据；可重建视图，不做跨库事务。
CREATE TABLE IF NOT EXISTS media_assets (
    asset_id      TEXT PRIMARY KEY,
    sha256        TEXT NOT NULL,
    object_key    TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    content_type  TEXT NOT NULL,
    kind          TEXT NOT NULL,
    original_name TEXT,
    created_by    INTEGER,
    status        TEXT NOT NULL DEFAULT 'active',
    created_at    TEXT NOT NULL,
    deleted_at    TEXT
);
CREATE INDEX IF NOT EXISTS ix_media_assets_sha256 ON media_assets(sha256);
CREATE INDEX IF NOT EXISTS ix_media_assets_status ON media_assets(status);
CREATE INDEX IF NOT EXISTS ix_media_assets_created_by ON media_assets(created_by);
