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

> ⚠️ **目录已分层（2026-10-17）**：历史方案已迁往 `docs/{design,plans,archive}/`，
> 本目录保留 v2.0 方案/计划、使用说明归档与图片素材。历史文档查找路径：
> - 设计方案 → `docs/design/`（95 份终版）
> - 实施计划 → `docs/plans/`（24 份）
> - 历史版本/报告 → `docs/archive/`（37 份）

- [学生端容器化模块化设计方案_v2.0.md](./学生端容器化模块化设计方案_v2.0.md) — **容器化+模块化总方案 v2.0（现行，取代 v1）**：基于三轮实测推翻 v1 的 8 条错误主张（容器数 18→3、PostgreSQL→SQLite、不拆分已存在模块、不建 badge 服务、复用既有健康检查）、十个业务域按能力划分、目录分层六类归位、设备双轴（角色×设备）识别、三级清理红线、L0~L7 八道门禁
- [学生端容器化模块化设计方案_v2.0_实施计划.md](./学生端容器化模块化设计方案_v2.0_实施计划.md) — **实施计划**：P0~P6 共 20 个任务，9 条硬性约束，逐阶段验收判据与 PowerShell 验证命令
- [整体系统使用和结构说明_v1_运维手册.md](./整体系统使用和结构说明_v1_运维手册.md) — **使用/运维手册归档**：系统目录结构、克隆与启动、拉取更新、设计收尾、SQLite 存储/备份/恢复、多人共享、验收与排错；权威版在 `docs/ops/整体系统使用和结构说明_v1.md`
- [题库设计模式_v1.md](./题库设计模式_v1.md) — **QBDM v1 归档**：九角色、Q0–Q6、五零指标、分支细则、门禁矩阵、13 条反模式；权威版在 `docs/superpowers/specs/题库设计模式_v1.md`
- [题库设计模式_v2.md](./题库设计模式_v2.md) — **QBDM v2 模块层归档**：25 模块台账、设计 D1–D10 / 优化 O1–O8 / 测试 T1–T8、影响面五步、A14–A20；权威版在 `docs/superpowers/specs/题库设计模式_v2.md`
- [题库设计模式_v3.md](./题库设计模式_v3.md) — **「题库设计」模式（会话执行版）归档**：标准/创造/PTC 分层、九角色落地形态、设计/测试/优化三态、技能+MCP+工作流绑定、12 条实测坑；权威版在 `docs/superpowers/specs/题库设计模式_v3.md`
- [题库设计模式_模块作战卡_v1.md](./题库设计模式_模块作战卡_v1.md) — **模块热加载一屏卡**：开工三步、D/O/T 速查、五条硬约束、收尾四问
- [题库模块台账_v1.md](./题库模块台账_v1.md) — **模块台账归档**：25 模块 × 端点/页面/测试/事件（机器生成，`gen_module_ledger.py --check` 查漂移）

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
