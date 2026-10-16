-- 补建 material_import_record.parse_status 索引
--
-- 背景：models.py 曾为 question_import_record 与 material_import_record
-- 两张表声明同名索引 idx_import_status。SQLite 的索引名是数据库全局的，
-- 因此 material_import_record 的索引从未建成，migrate_study_materials.py 中
-- 的 CREATE INDEX IF NOT EXISTS 也因「同名索引已存在」而静默跳过。
-- 该表生产环境当前 0 行，影响有限，但缺陷真实存在。
--
-- 本迁移创建更正后的索引名，为存量库补齐。重复执行安全（IF NOT EXISTS）。
-- 旧的 idx_import_status 保留给 question_import_record 使用，不得删除。

CREATE INDEX IF NOT EXISTS idx_material_parse_status
    ON material_import_record(parse_status);
