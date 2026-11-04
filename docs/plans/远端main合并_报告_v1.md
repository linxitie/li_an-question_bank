# 远端 main 合并报告 v1（2026-11-04）

> 状态：**✅ 已合并 + 已验收 + 已推送**（2026-11-04，远端 `main` 已对齐 `88c0bd9`）
> 触发：用户要求推送 `origin/main`，实测发现远端已前进 174 个提交、与本地分叉

---

## 1. 分叉实测

| 项 | 值 |
|---|---|
| 合并基点 | `a9e44d9`（2026-10-27） |
| 本地 main（推送前） | `8f03a7d`，独有 **149** 提交（备考资料模块 / 平板同版 / 端口 8000 / VTJ 修复 / 文档） |
| 远端 main（fetch 后） | `639f564` → 合并当天又到 `f423598`，独有 **174** 提交（模块4 学习计划·成就·能力雷达·遗忘曲线、模块7 联考小智·知识图谱·记忆·学习仪表盘、论坛治理、练习管理员、F3 媒体资产） |
| 结论 | 双方都从 `a9e44d9` 长出去 → 非快进，必须合并 |

**备份**：本地 main 先推到远端分支 `backup/local-main-1104`（`8f03a7d`），合并期间远端 main 全程未动。

---

## 2. 冲突与解决（8 个文件）

| 文件 | 冲突规模 | 解决方式 |
|---|---|---|
| `backend/app/models/models.py` | 310 行 | 远端在 `UserFeedback` 末尾追加 ticket/handler/question 三个索引 + 13 个新模型；本地追加 `MaterialShare`/`MaterialAdoptLog`。**索引取并集，远端 13 类在前、本地 2 类在后**；`ast` 校验 92 个类、无重名 |
| `backend/app/main.py` | 7 行 | import 取并集（`practice_admin`/`forum_moderation` + `badges`），两侧 `include_router` 已自动保留 |
| `backend/app/api/v1/library/materials.py` | 7 行 | 上传端点取远端 `db/user_id` 入参（媒体库存档能力）+ 保留本地审计 target 带 `purpose` 口径 |
| `backend/tests/test_api_surface.py` | 45 行 | 白名单取并集；按 R11 补登记远端 **88 个新端点**（此前只在代码里、未登记）；`DOCUMENTED_FEEDBACK_MOVES` 复核后移除已恢复的 `POST /api/feedback/{id}/reply` |
| `src/router/index.ts` | 24 行 | 公开路由白名单取并集（本地 4 条预览/演示放行 + 远端 `/forum` 游客浏览） |
| `src/views/student/shared/profile.vue` | 24 行 | 保留本地徽章墙（后被徽章下线整体移除）+ 远端 `loadStudyData` 注释口径 |
| `scripts/vtj_version_sync.py` | 2 段 | 保留本地 `classify()`/`--check`/`--strict` 实现，吸收远端 `sync_single_file` 的校验口径说明（远端也修过同一问题，属重复劳动） |
| `docs/README.md` | 全文件 | 按本地结构重整，远端新增的 **29 条索引行**集中保留在「远端 main 新增文档（合并收集，2026-11-04）」章节 |

---

## 3. 合并后暴露并修复的 5 个真问题

| # | 问题 | 根因 | 修复 |
|---|---|---|---|
| 1 | 建卡报 500「媒体存储缺少数据库会话」 | 远端把 `MEDIA_STORE_ENABLED` 打开，`_safe_image_upload` 必须传 `db/user_id`，本地两处调用没传 | `my_create_card`、`batch-card-image` 补 `db=db, user_id=…` |
| 2 | vitest 失败：`ai-assistant.SESSIONS_UPDATED 未在 EVENT_NAMES 登记` | 远端新增事件常量只写在模块里 | `event-bus.ts` 补常量 + 载荷类型 + 便捷导出 |
| 3 | L4 模块边界新违规 `[cross_write] exam/exams -> QuestionGroup` | 远端在 exam 域直接 import catalog 的 `QuestionGroup` | 新增 `catalog/contract.py::question_groups_by_ids`（只读、返回纯 dict），exams 改走契约 |
| 4 | L7 DDL checksum 不符 | 媒体/图 DDL 用原始字节算 sha256，Windows 检出 CRLF 必然不符 | 与 foundation DDL 同口径（先 CRLF→LF 再哈希） |
| 5 | L7 迁移序号重复 `[1,2,2,3,3]` | 远端 `002_media_assets`/`003_graph_projection` 与本地 `002_material_*`/`003_material_share` 撞号 | 本地两支改 `004`/`005`（远端文件名与 5 处代码引用不动） |

另：本地库按 `20261027_003_graph_projection.sql` 建了 `foundation_graph_node`/`foundation_graph_edge` 两表 + 两个索引，L7-20 由 FAIL 转 PASS。

---

## 4. 验收（全部在合并结果上实测）

| 项 | 结果 |
|---|---|
| 门禁 `gate_all` | **10/10** |
| 后端守卫 / 模块测试 | `test_api_surface` + `test_route_roles` + `test_library_module` **17 passed** |
| 前端单测 | vitest **46 文件 / 537 通过**（徽章下线后 42/481） |
| 前端类型 | `vue-tsc` **0 error** |
| VTJ 一致性 | `--check` 通过（69 设计器页面一致、10 个非设计器页面跳过） |
| 合并时运行中的服务 | 后端 8000 重启后 `OpenAPI 409`（徽章下线后）、`/health` OK、Vite 代理 200 |

---

## 5. 已知不足

1. **`origin/main` 在合并期间又前进**：fetch 时是 `639f564`，随后到 `f423598`（模块4 继续提交）。本次合并以 `639f564` 为基线；推送前需要再 `fetch` 一次确认远端未再前进，否则仍会被拒。
2. **远端 CI 其余 4 个作业未验证**（black/isort/flake8、prettier/eslint、pytest tests/unit、alembic 迁移）：本地只跑了项目自建 10 层门禁与 vitest，CI 是否全绿未知。
3. **`docs/README.md` 结构取舍**：远端那次是全文件重整，本地选择按自身结构保留并把远端新增 29 行集中附在后面，**不是语义级合并**；如果以后以远端结构为准，需要另行整理。
4. **`test_api_surface` 白名单一次补了 88 条远端端点**：这意味着 R11 的「新增端点必须登记」在远端那条线上长期是欠账状态（他们的端点从未登记），本次是补齐而非新增违规。
5. **推送已完成**：`05857d8..88c0bd9  main -> main`，远端 `main` 与本地一致（ahead 0 / behind 0）。推送前又 fetch 到远端再前进 10 提交（新闻模块恢复、3D 日历、AI 错题本/学习对战等），已再并一次（`88c0bd9`），冲突仅 `models.py` 一处（99 类取并集），页面路由 101→105、白名单再补 93 条端点。
