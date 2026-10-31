-- 20261031_001：高频列表/组卷查询索引
-- 教师端题目列表按 subject/type/status/audit_status 过滤并按 create_time 排序；
-- 试卷详情与组卷按 paper_id + question_order 读取。
CREATE INDEX IF NOT EXISTS idx_qb_status_audit
    ON question_bank(status, audit_status);
CREATE INDEX IF NOT EXISTS idx_qb_subject_type_status
    ON question_bank(subject_id, type_id, status, audit_status);
CREATE INDEX IF NOT EXISTS idx_pqr_paper_order
    ON paper_question_relation(paper_id, question_order);
