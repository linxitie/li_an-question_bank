-- 迁移脚本: 20250823_003_add_operation_log.sql
-- 描述: 新建操作日志表 (补充现有 sys_operation_log)
-- 执行: mysql -u root -p police_exam < this_file.sql

USE police_exam;

-- 1. 创建 operation_logs 表 (专用于试卷/题目操作审计)
CREATE TABLE operation_logs (
    log_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '日志ID',
    user_id BIGINT NOT NULL COMMENT '操作人ID',
    action VARCHAR(50) NOT NULL COMMENT '操作类型: delete_paper/update_paper/confirm_paper/batch_update_type/batch_add_explanation',
    target_type VARCHAR(50) NOT NULL COMMENT '目标类型: paper/question',
    target_id BIGINT COMMENT '目标ID',
    details TEXT COMMENT '操作详情(JSON)',
    ip_address VARCHAR(45) COMMENT 'IP地址',
    user_agent VARCHAR(500) COMMENT '用户代理',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (user_id) REFERENCES sys_user(user_id) ON DELETE CASCADE,
    INDEX idx_user_action_time (user_id, action, created_at),
    INDEX idx_target (target_type, target_id)
) COMMENT '试卷/题目操作审计日志';

-- 回滚脚本
-- DROP TABLE operation_logs;