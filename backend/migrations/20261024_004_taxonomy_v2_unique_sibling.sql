-- 迁移脚本: 20261024_004_taxonomy_v2_unique_sibling.sql
-- 描述: 为可见知识树（status = 1）建立同级节点唯一索引
--
-- 目的:
--   保证「可见」知识树中不存在同级重名节点，即同一
--   (subject_id, sub_category_id, parent_id, point_name) 只能出现一次。
--
-- 为什么必须是部分索引（WHERE status = 1）:
--   T-04 将 531 条历史遗留行标记为 status = 0 予以隐藏；这些隐藏别名中有意保留了
--   与可见规范节点相同的名称（例如“其他”）。因此对全表建立唯一索引会直接失败，
--   唯一性只应约束可见规范树，故使用部分唯一索引。
--
-- 执行顺序:
--   必须在 T-04 为 knowledge_point 增加 status 列之后执行；若 status 列不存在，
--   本迁移会报 "no such column: status"。
--
-- 数据库: SQLite（本项目生产库为 SQLite/WAL），不含 MySQL 专有语法。
-- 重复执行安全: IF NOT EXISTS。

CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_point_sibling_visible
    ON knowledge_point (subject_id, sub_category_id, parent_id, point_name)
    WHERE status = 1;

-- 回滚:
-- DROP INDEX IF EXISTS uq_knowledge_point_sibling_visible;
