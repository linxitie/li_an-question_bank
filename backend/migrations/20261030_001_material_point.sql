-- P2.2：资料挂接考点（分类法第三层 sub_categories → knowledge_point → study_material）
-- 幂等：列已存在时 ALTER 会报错，由 scripts/init_material_data.py 的
-- ensure_migrations() 先查 PRAGMA table_info 再决定是否执行；直接跑本文件前请先确认。
ALTER TABLE study_material ADD COLUMN point_id INTEGER;
CREATE INDEX IF NOT EXISTS idx_material_point ON study_material(point_id);
