# docs/ 文档索引

> 本索引由 `solve_problems_files/README.md` 迁移而来（目录分层重构）。
> 归档规则：展示方案的同时落盘；定稿当场归档；归档即更新本索引。

## 目录说明

| 目录 | 用途 |
|---|---|
| `design/` | 历史设计方案（91 份，含 v1 旧版容器化方案等） |
| `plans/` | 实施计划与当前活跃设计 |
| `archive/` | 已归档的历史文档（37 份） |
| `superpowers/` | Superpowers 工作流产物（specs/plans 子目录） |

## 活跃文档索引

| 文档 | 版本 | 状态 | 说明 |
|---|---|---|---|
| `plans/学生端模块化设计方案_v1.md` | v1 | ✅ 已定稿（2026-10-18，已修订） | 学生端 20 业务模块化（⑱⑲⑳ 未开发）：星型横向数据流（成就成长枢纽）、三角色+三设备纵向通信、一人一分支协作规范、VTJ 红线守护 |
| `plans/学生端模块化设计方案_v1_实施计划.md` | v1 | 🚧 执行中（P1✅ P2✅ P3 手工验收待执行） | 三阶段 123 任务：基础设施 33 ✅ + 逐域改造 82 ✅ + 验收 8（P3-01~07 真机手工验收待用户执行）；⑱⑲⑳ 排除 |
| `plans/分支使用说明书_v1.md` | v1 | ✅ 已定稿（2026-10-18） | 多人协作独立文档：红线速查+环境准备+一人一分支+20 模块所有权映射+域卡模板+跨域通信规则+合并验收+冲突处置 |
| `plans/学生端模块化基线快照_v1.md` | v1 | ✅ 已定稿（2026-10-18） | P1-01 实测基线：75 页/73 JSON/343 端点/pytest 278-17-3/门禁 7-8/13 调用点 |
| `plans/学生端模块化_P3手工验收核对表_v1.md` | v1 | 📋 待用户执行 | P3-01~07 真机手工验收执行清单：17 域逐项勾选 + 事件观测记录位 + 三设备一致性/WS 兜底演练步骤 + 缺陷记录区 |
| `plans/三端数据流一致性修复方案_v1.md` | v1 | 🚧 执行中（P0 ✅；P1-1 ✅；P1-2 ✅；P1-3~P1-9 待执行） | 6 项三端数据流一致性问题的根因+修复方案：统一可见性/计数口径、主观题渲染、考点 canonical 展示、材料归属与教师编辑、存量修复与验收；P0-P4 分阶段，含 7 个待拍板决策 |
| `plans/三端数据流一致性修复方案_v2.md` | v2 | 🚧 执行中（已批准；T-01 ✅ 2bd7d6e；T-02 ✅ 32c1cdb；T-03 ✅ f1c402b；T-04 ✅ f1bc4bb；T-05 ✅ 995e971；T-06 ✅ e42b3c8；T-07 ✅ 4cd6079；T-08~T-12 进行中） | v1 的完整替代/增强版：覆盖 6 个问题的逐项方案；新增 91 L2/427 L3/518 节点分类树、505 别名隐藏、583 未分类回填、`sub_category_id`、P1/P2/P3 任务表、VTJ 9 页落地、验收/回滚/commit 计划；新增 §14 RT 富文本统一展示/编辑（答题卡/教师端/导入/管理员端，图片/文字/HTML/链接，双端清洗）；含“主代理直接落盘、未经子代理独立审查”说明 |

## 变更记录

- 2026-10-24：Phase A 进展：T-07 完成（commit `4cd6079`，新增部分唯一索引 `uq_knowledge_point_sibling_visible`（`WHERE status=1`）+ 7 个测试，taxonomy 合计 49 passed；t06→t07 用 sqlite backup 复制，0 可见同级重复、重复可见插入 IntegrityError、隐藏同名插入允许、重复执行幂等、integrity ok；生产库只读未写：631 行、已有 status 列、无该索引、integrity ok；22 行 sub_category_id NULL，SQLite 唯一索引不约束 NULL）；T-08~T-12 进行中。
- 2026-10-24：Phase A 进展：T-06 完成（commit `e42b3c8`，`backfill-point-id` + 10 个新测试，taxonomy 合计 42 passed；temp 首次 apply：filled_from_relation 2130、filled_ambiguous 1、no_canonical_relation 1226、updated_rows 2131、after_nonnull 2131、after_null 1226；歧义题 162 在 68/71 中取最小 68；第二次 apply updated_rows 0 幂等；非空 point_id 指向 status=0 的行 0；隐藏点 124/125/126 的 643 条关系保留且未被引用；生产库只读未写：631 行、无 alias_of、3357 题 point_id 全 NULL、integrity ok）；T-07~T-12 进行中。
- 2026-10-24：Phase A 进展：T-05 完成（commit `995e971`，`migrate-relations` + 6 个新测试，taxonomy 合计 32 passed；人工映射 17→692、18→689、25→736、26→737，124/125/126 保留为 unmigrated；temp 连续两次 apply 幂等：relations 2775、distinct pairs 2775、duplicate 0、migrated 5、deduped 0、unmigrated 643、relations_to_alias_nonnull 0、relations_to_hidden_null 643、integrity ok；生产库 dry-run 未写：631 行、无 alias_of、relations 2775、integrity ok）；T-06~T-12 进行中。
- 2026-10-24：Phase A 进展：T-04 完成（commit `f1bc4bb`，`apply-aliases` + 6 个新测试，taxonomy 合计 26 passed；temp 连续两次 apply 幂等：1049 行、canonical 518、status=0 531、legacy visible 0、alias_of 464/41、坏目标 0；生产库仍 631 行、status=0 0、无 alias_of、integrity ok；models 加 `KnowledgePoint.status`，树 API 三处加 `status=1`；`alias_of` 暂不入 ORM，待 T-11 迁移后补）；T-05~T-12 进行中。
- 2026-10-24：Phase A 进展：T-03 完成（commit `f1c402b`，`build-tree` + 3 个新测试，taxonomy 合计 20 passed；生产 dry-run 631 行未写；temp 连续两次 apply 幂等：1049 行、canonical 518、status=0 61、待 T-04 470、旧“其他”合并 32、未决 `[401,571,592]`、同级重名 0；7 个被 648 条关系使用的旧 seed 仍待 T-05 人工映射）；T-04~T-12 进行中。
- 2026-10-24：Phase A 进展：T-02 完成（commit `32c1cdb`，`build_taxonomy_v2.py` + 505 行别名 CSV + 9 tests passed；exact 35 / alias 133 / subcategory_other 296 / hidden 41；只读 DB，未写库）；T-03~T-12 进行中。
- 2026-10-23：Phase A 启动进展：T-01 完成（commit `2bd7d6e`，`KNOWLEDGE_TREE_V2` + 8 tests passed；91/427/518 计数、每 L2 一个“其他”、无同级重名）；T-02~T-12 按计划推进中，未写库。
- 2026-10-23：用户批准 v2 全部 1~10 项（含 RT 富文本）；进入 Phase A（T-01~T-07）dry-run，未写库。
- 2026-10-23：`plans/三端数据流一致性修复方案_v2.md` 追加 §14 RT 富文本统一展示/编辑（答题卡/教师端/导入/管理员端；图片/文字/HTML/链接；后端 bleach + 前端 DOMPurify；§14.9 五项待确认）；v2 状态仍为“待用户批准”。
- 2026-10-23：新增 `plans/三端数据流一致性修复方案_v2.md`（6 个三端数据流问题全覆盖；91 L2/427 L3/518 节点分类树；505 别名隐藏、583 未分类回填、`sub_category_id`、P1/P2/P3 任务表、VTJ 9 页落地、验收/回滚/commit 计划；待用户批准后实施）。同步修正 v1 索引状态为 P1-2 ✅。
- 2026-10-20：三端修复 P0 全部完成：P0-3 解析门禁基线（公专 L1 PASS；行测 L1 既有 FAIL，材料指纹 364/1.0 与基线一致）；5 个真实案例入库（commit `a634820`），第 3 类“材料在答案解析之后”标 `not_found`，未使用合成案例；P0-4 golden corpus（commit `4f291ed`）；P0-5 `MATERIAL_OWNERSHIP_V2=False` 灰度开关（commit `54de949`）。
- 2026-10-20：三端修复 P1-1 完成：`QuestionStatsService.visible_query` 统一三端默认可见性为 `status=1 AND audit_status=1`，新增 `visible_total`、教师 `my_total`、管理端 `include_offline/include_pending`；`backend/tests/test_question_stats_service.py` 4 passed（commit `fa3683a`）。
- 2026-10-19：新增 `plans/三端数据流一致性修复方案_v1.md`（三端数据流一致性 6 问题修复方案；数据库实测 + 代码逐行核对；待用户审批后实施）。
- 2026-10-19：三端修复方案获批；P0-1 备份完成、P0-2 基线脚本完成（commit `db4a5c2`）；基线修正：2 组无可见成员、组 24 仅 1 个 source。
- 2026-10-18：⑱⑲⑳ 三未开发模块补目录定位：`src/modules/{ai-assistant,mock-exam,mini-exam}` 占位外壳落地（四件套×3、零事件、不认领），生成器 17→20 域，shells.spec 161 全绿；规格 5.1 目录树与《分支使用说明书》⑱⑲⑳ 三行同步更新。
- 2026-10-18：新增 `plans/学生端模块化设计方案_v1.md`（学生端功能模块化设计终稿，用户已批准）。
- 2026-10-18：新增 `plans/学生端模块化设计方案_v1_实施计划.md`（123 个原子任务；P1 33 任务、P2 82 任务已全部完成并逐任务双提交；P3 真机手工验收待执行）。
- 2026-10-18：新增 `plans/分支使用说明书_v1.md` 与 `plans/学生端模块化基线快照_v1.md`。
