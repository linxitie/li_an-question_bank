-- 迁移脚本: 20250823_001_add_paper_fields.sql
-- 描述: 为 exam_paper 表新增试卷检测相关字段
-- 执行: mysql -u root -p police_exam < this_file.sql

USE police_exam;

-- 1. 新增字段
ALTER TABLE exam_paper 
ADD COLUMN original_title TEXT COMMENT '原始文档标题' AFTER paper_name,
ADD COLUMN subject_confidence DECIMAL(3,2) COMMENT '科目识别置信度' AFTER subject_id,
ADD COLUMN is_manually_confirmed TINYINT(1) DEFAULT 0 COMMENT '是否人工确认' AFTER subject_confidence,
ADD COLUMN detected_subject VARCHAR(50) COMMENT '系统识别的科目' AFTER is_manually_confirmed;

-- 2. 新增索引
CREATE INDEX idx_papers_subject_status ON exam_paper (subject_id, paper_type);
CREATE INDEX idx_papers_creator_status ON exam_paper (creator_id, paper_type);

-- 回滚脚本 (注释掉，回滚时取消注释执行)
-- ALTER TABLE exam_paper DROP COLUMN detected_subject;
-- ALTER TABLE exam_paper DROP COLUMN is_manually_confirmed;
-- ALTER TABLE exam_paper DROP COLUMN subject_confidence;
-- ALTER TABLE exam_paper DROP COLUMN original_title;
-- DROP INDEX idx_papers_creator_status ON exam_paper;
-- DROP INDEX idx_papers_subject_status ON exam_paper;