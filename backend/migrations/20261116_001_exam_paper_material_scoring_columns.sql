-- 2026-11-16 备考资料批（feat/material-multi-format-import）存量库补列 DDL 存档
--
-- 本文件是**存档**，不是执行入口。真实执行路径有两条：
--   1) exam_record 4 列 → 应用启动自愈（app/main.py::_ensure_exam_record_scoring_columns，D5-b 起，
--      补列后按口径 A 回填）；也可用
--      python backend/scripts/migrate/migrate_add_exam_scoring_fields.py --apply（离线补列，不回填）
--   2) exam_paper 3 列 + study_material 5 列 → 应用启动自愈
--      （app/main.py 的 exam_paper / study_material 分支，含 3 个索引与 list_time/placement 回填）
--
-- 为什么不登记进 backend/scripts/migrate/apply.py：该执行器的契约是
-- 「DDL 全部 IF NOT EXISTS，重复执行 changed=0」；而 SQLite 的
-- `ALTER TABLE ... ADD COLUMN` 没有 IF NOT EXISTS，重复执行必然报
-- duplicate column name。列级幂等由上面两条路径各自承担（PRAGMA table_info /
-- inspector.get_columns 先查再加），所以本存档不进执行器。
--
-- 手工执行前请先确认列不存在（幂等责任在使用者）：
--   PRAGMA table_info(exam_record); PRAGMA table_info(exam_paper); PRAGMA table_info(study_material);
--
-- 本批另新增 3 张表（material_file / paper_parse_draft / paper_answer_draft），
-- 它们由 app/main.py 的 Base.metadata.create_all 直接建出（create_all 能建表、不能补列，
-- 这正是本文件存在的原因），故不在此重复 DDL。

-- ========== 1. exam_record：评分口径 A 的 4 列 ==========
-- is_scored = 1 <=> 已交卷 且 不存在待人工评分明细（is_correct IS NULL）
ALTER TABLE exam_record ADD COLUMN is_scored INTEGER DEFAULT 0;
ALTER TABLE exam_record ADD COLUMN manual_pending_count INTEGER DEFAULT 0;
ALTER TABLE exam_record ADD COLUMN answered_count INTEGER DEFAULT 0;
ALTER TABLE exam_record ADD COLUMN question_total INTEGER DEFAULT 0;

-- ========== 2. exam_paper：考试开关 + 定时窗口（P2，2026-11-09）==========
-- 可进入 = paper_type=PUBLISHED 且 exam_open=1 且 now ∈ [exam_open_at, exam_close_at)
-- 且 question_count > 0；NULL 视为开，兼容老数据。
ALTER TABLE exam_paper ADD COLUMN exam_open INTEGER DEFAULT 1;
ALTER TABLE exam_paper ADD COLUMN exam_open_at DATETIME;
ALTER TABLE exam_paper ADD COLUMN exam_close_at DATETIME;

-- ========== 3. study_material：试卷编号 / 元数据 / 大纲 / 排序键 / 投放位 ==========
-- paper_code（C4）：与 exam_paper.paper_code 同值即成对；非试卷类留空。
ALTER TABLE study_material ADD COLUMN paper_code VARCHAR(50);
-- paper_meta（C2b）：管理员订正的试卷元数据 JSON；合并优先级见 services/paper_registry.paper_block()
ALTER TABLE study_material ADD COLUMN paper_meta TEXT;
-- doc_meta（C1）：讲义大纲 JSON {word_count, chapter_count, chapters[]}，存快照避免列表逐行解析 docx
ALTER TABLE study_material ADD COLUMN doc_meta TEXT;
-- list_time（ID 方案 A）：列表排序键；恢复回收站资料时刷新为 now 以置顶，create_time 保持真实
ALTER TABLE study_material ADD COLUMN list_time DATETIME;
-- placement（L1）：投放位 exam/library/both，NULL 由 _placement_of() 归一化（试卷=both，非试卷=library）
ALTER TABLE study_material ADD COLUMN placement VARCHAR(10) DEFAULT 'library';

CREATE INDEX IF NOT EXISTS idx_material_paper_code ON study_material(paper_code);
CREATE INDEX IF NOT EXISTS idx_material_list_time ON study_material(list_time);
CREATE INDEX IF NOT EXISTS idx_material_placement ON study_material(placement);
