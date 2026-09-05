-- 迁移脚本: 20250823_002_add_question_fields.sql
-- 描述: 为 question_bank 表新增内容清洗和题型置信度字段
-- 执行: mysql -u root -p police_exam < this_file.sql

USE police_exam;

-- 1. 新增字段
ALTER TABLE question_bank 
ADD COLUMN clean_content TEXT COMMENT '清洗后的题目内容(用于显示)' AFTER question_content,
ADD COLUMN type_confidence DECIMAL(3,2) COMMENT '题型识别置信度' AFTER type_id,
ADD COLUMN is_type_confirmed TINYINT(1) DEFAULT 0 COMMENT '题型是否人工确认' AFTER type_confidence;

-- 2. 更新现有数据: 清洗 clean_content (移除 UTBxxx 系统ID)
UPDATE question_bank 
SET clean_content = REGEXP_REPLACE(question_content, 'UTB[a-f0-9]{16}', '')
WHERE question_content REGEXP 'UTB[a-f0-9]{16}';

-- 对于没有 UTB ID 的题目，clean_content 设为原内容
UPDATE question_bank 
SET clean_content = question_content
WHERE clean_content IS NULL OR clean_content = '';

-- 3. 新增索引
CREATE INDEX idx_questions_subject_status ON question_bank (subject_id, status);
CREATE INDEX idx_questions_creator_status ON question_bank (creator_id, status);

-- 回滚脚本
-- ALTER TABLE question_bank DROP COLUMN is_type_confirmed;
-- ALTER TABLE question_bank DROP COLUMN type_confidence;
-- ALTER TABLE question_bank DROP COLUMN clean_content;
-- DROP INDEX idx_questions_creator_status ON question_bank;
-- DROP INDEX idx_questions_subject_status ON question_bank;