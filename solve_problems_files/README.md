# 题目管理高精度优化 — 解决方案归档

本目录归档「题目管理高精度优化」的完整设计方案与数据修复结论，供后期运维与二次开发参考。

## 问题背景

题库系统存在系统性题型识别与答案/解析显示缺陷：
1. 题目内容弹窗 / 编辑弹窗缺失「答案解析」
2. 多选题目答案只选一个（答案被截断）
3. 选择题被误判为「论述题」
4. 多选题被误判为「单选题」
5. 弹窗宽度/高度需调整为 1100px / 80vh

## 根因定位（已用真实数据库验证，793 道题）

| 问题 | 根因 | 量化 |
|---|---|---|
| 选择题显示论述题 / 多选显示单选 | `question_bank.type_id` 与 `question_detail_category.question_type_detail` 分裂；type_id 错位 122 道 | 教师端读 type_id，学生端读 detail |
| 多选答案截断 | 答案正则只捕获连续字母，`A、B、C`→`A` | text_parser.py |
| 答案解析缺失 | 232 道公专题目解析入库时即为空（源数据缺失，非路由 bug）；其余 559 道前端本就正常显示 | 数据层 |
| 题型误判 | `_detect_question_type` 无选项时默认论述；Excel 默认「选择题」→单选；2 参函数遮蔽 3 参 | question_import.py |

## 文档索引

- [keyword_engineering.md](./keyword_engineering.md) — 题型识别关键词工程（分层分类器 + 关键词字典）
- [type_detection.md](./type_detection.md) — 题型判定机制设计与单一事实来源
- [answer_normalization.md](./answer_normalization.md) — 答案归一化 canonical_answer
- [data_repair.md](./data_repair.md) — 数据修复脚本与真实数据结论
- [手机端问题优化完整解决方案_v1.md](./手机端问题优化完整解决方案_v1.md) — 手机端 14 项问题根因定位与分阶段实施方案
- [行测题目导入优化方案.md](./行测题目导入优化方案.md) — **行测 85 套导入机制定稿**：语料实测、分节区间配对安全网、考点树、材料题组、卷级元数据；含 T16 阻塞根因与两处计划偏差记录
- [行测导入门禁与运维手册.md](./行测导入门禁与运维手册.md) — **行测门禁命令与运维手册**：三重门禁、DB 备份/回滚（WAL 注意事项）、常见故障速查、考点/分区/图片阈值扩展流程、VTJ 改动须知
- [题目导入模块全面修复与满血优化方案_v1.md](./题目导入模块全面修复与满血优化方案_v1.md) — **教师端题目导入模块全面修复**：10 条根因诊断（RC-1~RC-10）、上传轮询稳定性、入库链路统一（RC-2/RC-3/RC-4/RC-5）、申论/复合题三端统一预览、六层回归门禁网（L0~L5）、10 步有序拆分、三处下钻专项（J-1/J-2/J-3）、9 个真实语料 Playwright 验收
- [题目导入模块优化方案_v3.md](./题目导入模块优化方案_v3.md) — **科目与分类识别专项**：5 套并行科目/分类字典收敛为单一 DB 事实来源、假考点 ID 治理（101-1519→真实 point_id）、全科目考点归属回填（留空 69→22）、taxonomy API（GET /api/questions/import/taxonomy）、自动识别建议+置信度+手选覆盖（阈值 0.5）、预览建议条一键采用

### 容器化与模块化

- [学生端容器化模块化设计方案_v2.0.md](./学生端容器化模块化设计方案_v2.0.md) — **容器化+模块化总方案 v2.0（现行，取代 v1）**：基于三轮实测推翻 v1 的 8 条错误主张（容器数 18→3、PostgreSQL→SQLite、不拆分已存在模块、不建 badge 服务、复用既有健康检查）、十个业务域按能力划分、目录分层六类归位、设备双轴（角色×设备）识别、三级清理红线、L0~L7 八道门禁
- [学生端容器化模块化设计方案_v2.0_实施计划.md](./学生端容器化模块化设计方案_v2.0_实施计划.md) — **实施计划**：P0~P6 共 20 个任务，9 条硬性约束，逐阶段验收判据与 PowerShell 验证命令

> ⚠️ **v1 与 v2.0 冲突时以 v2.0 为准。** v1（1424 行）中 9 条主张有 8 条与系统实际不符，包括把已存在的功能模块当作待建微服务。

## 修改文件清单

**后端**
- `backend/app/services/text_parser.py` — canonical_answer + 分层分类器 + 关键词字典 + 答案正则拓宽
- `backend/app/api/v1/question_import.py` — 移除遮蔽函数、修复调用点、Excel 默认题型重检测、答案归一化
- `backend/app/api/v1/questions.py` — `_detect_multi_from_content` 改用 canonical_answer
- `backend/app/api/v1/admin.py` — 审核列表补返回 answer_analysis/options/type_name/full_content
- `backend/app/main.py` — 移除「选择题→单选」有害启动迁移折叠
- `backend/scripts/repair_question_types.py` — **新增** 历史数据统一修复脚本

**前端（VTJ raw 手写页）**
- `.vtj/vue/teacher_questions.vue` — 弹窗 CSS 1100px / 80vh
- `.vtj/vue/admin_questions.vue` — 新增审核详情弹窗

## 运维要点

- **数据修复**：`python backend/scripts/repair_question_types.py --dry-run`（预览）→ `--apply`（写入），幂等可重复。
- **232 道公专空解析**：需用修复后的导入管线从公专原始素材（含解析列）重新导入补解析，库内不可恢复。
- **单一事实来源**：答案归一化用 `canonical_answer`，题型判定用 `_detect_question_type`，三处（导入/读路径兜底/修复脚本）全部复用，禁止再各写一套。
