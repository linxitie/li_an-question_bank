-- B1：个人库与分享溯源
-- 2026-10-27
-- status 语义扩展：0 草稿 / 1 公开 / 2 私有（仅创建者+管理员可见）；-1 已删除
ALTER TABLE study_material ADD COLUMN source_material_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_material_owner ON study_material (creator_id, status);
