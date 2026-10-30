# 砺安题库 × DeepSeek-Harness × DeepInfer 联合执行与优化总方案

> **状态**：已落盘（2026-10-25）。用户已在对话中作为执行输入下发；本文件为 dsh 会话的**最高指令**。
> **归档**：`docs/plans/dsh-optimization-master-plan.md`（按 AGENTS.md §1.3「迁移后」规则写入 `docs/plans/`，`solve_problems_files/` 不再新增副本）。
> **索引**：`docs/README.md` 活跃文档表已登记。

---

## 0. 落盘前的实测校正（不修正则方案会指挥错方向）

| 方案原文 | 实测（2026-10-25 09:2x） | 处置 |
|---|---|---|
| 当前分支 `feat/student-containerization` | 实际为 **`feat/fix-bug`**（`git rev-parse --abbrev-ref HEAD`） | 阻断条件需重新评估：P3B 是否已完成以 `feat/fix-bug` 的提交为准，不能按分支名判断 |
| 门禁 8 个脚本，由 `backend/scripts/gate_all.py` 编排 | 实际 **9 层**（L0/L1-G/L1/L1-H/L2/L3/L4/L5/L6），入口在 `backend/scripts/gates/gate_all.py`（不在 `backend/scripts/` 根下） | 所有文档中的旧路径失效，本方案按新路径执行 |
| 「dsh 全栈 Agent + 插件套件」 | dsh 已有原生插件：`dsh-skill-filesystem`（技能发现）、`dsh-mcp-client`（MCP 桥接）、`dsh-fuse`、`dsh-design-skills` | **不新写 LLM 适配器**，优先用原生插件配置达成，避免重复造轮子 |
| DeepInfer 本地推理后端 | 在 dsh 公开文档与本机均**无证据**存在该服务；未发现可用的 adapter 或 API 契约 | 标记为**阻塞待补**：需要用户提供 DeepInfer 的 endpoint/协议/模型名，才能写 `ctx.llm` adapter；在此之前不得虚构配置 |
| 「343 端点冻结」 | 与 `backend/data/refactor_baseline/api_surface.json` 口径一致（L4 契约门禁可验证） | 保留 |

> 原则：**实测优先**（AGENTS.md §4）。本文件与实测冲突时以实测为准，并回写本节。

---

## 1. 联合架构与 dsh 编排

### 1.1 角色映射

| 角色 | dsh 映射 | 职责 | 已就绪的通道 |
|---|---|---|---|
| 总设计师 / Lead | 主 Agent | 全局统筹、契约定义、审核节点、冲突阻断 | `li-an-workflow`、`plan-first-workflow`、`scope-guard` |
| 前端建模师 | subagent | 只改 `.vtj/vue/*.vue` 的 `<script>`，`dryRun` 预览后同步 DSL | **MCP `vtj`（19 工具）** + `vtj-frontend` |
| 后端建模师 | subagent | FastAPI 路由/模型、SQLite WAL 设计 | 本地 shell + `gate_all.py`（暂无独立 MCP） |
| 接口与测试 | subagent | API 契约比对、回归测试 | L2/L4 门禁 + `completion-verifier` |
| 管理 / 审计 | subagent | 凭据、健康检查、日志、备份 | `dsh-credentials-local` + 门禁 |

### 1.2 模式调用策略（Token 节流）

| 模式 | 场景 | 路由 | 节流手段 |
|---|---|---|---|
| 标准 | 常规 CRUD、重构、文档 | 当前云端 `deepseek-flash` | compaction、`tool-result-pruner`、最小文件加载 |
| 创造 | 新架构、复杂算法（组卷/判题） | 云端高 reasoning | 产出强制归档 `docs/superpowers/specs/` 供复用 |
| PTC | 662MB 语料清洗、4.3GB 题图索引、压测 | 本地执行，不进模型上下文 | 只传路径 + 统计摘要；结果落盘再读 |

> DeepInfer 作为「本地推理」路线的前提未验证（见 §0），当前 PTC 的「本地」仅指**本地进程执行**，不是本地推理。

---

## 2. Token 极简与上下文控制

1. **最小加载**：单任务只读 1~3 个相关文件，禁止整树遍历（`context-minimal-loader`）。
2. **大文件隔离**：`题库/`（662 MB）、`backend/app/static/`（4.3 GB）只传路径与元数据。
3. **防返工**：宣称完成前必须跑门禁/命令并贴输出（`completion-verifier`）。
4. **需求蔓延拦截**：只执行已批准计划（`scope-guard`）。

---

## 3. 工程红线与强制工作流

### 3.1 红线（AGENTS.md R1–R12，违反即报废）

R1 `.vtj/` 禁移动改名删除 · R2 `raw:true` 页面禁 `vtj_sync_vue_to_dsl` · R3 禁改 `<template>`（仅 `<script>`，先 `dryRun`）· R4 `device.ts` 原样保留 · R5 `mobile_*`/`tablet_*` 前缀不改 · R6 `题库/` 不删不移 · R7 `backend/app/static/` 不删 · R8 `backend/data/*.bak*` 不清 · R9 `audit/` 与待推断清单不是垃圾 · R10 备份用 `sqlite3.backup()` · R11 `/api/v1/` 冻结 · R12 平板不复制手机页

### 3.2 五步法（`li-an-workflow`）

规划（计划模式出计划）→ 人工审核（未确认不动文件）→ 执行（逐步验证）→ 人工审查（`git diff`）→ 交付（归档）。

### 3.3 代码前置思考链（CTC，10 问）

1 为什么这样写 · 2 安全（注入/XSS/越权） · 3 可运维 · 4 文件位置 · 5 前端状态更新 · 6 后端字段与迁移 · 7 路由注册 · 8 接口闭环 · 9 VTJ 语法版本 · 10 是否与既有算法冲突（**保留原合理设计，禁重复造轮子**）。

---

## 4. 阶段规划与阻断

**阻断**：教师端题目导入改造、三端数据一致性代码编写，须等 P3B 完成（按 `feat/fix-bug` 实际提交判定）。

- Phase 1（当前）：dsh 侧能力就绪 + 门禁/测试基线恢复（已完成，见 §5）。
- Phase 2：P3B 完成后启动三端一致性与导入改造。
- Phase 3：把 dsh 编排用于重构与回归。

---

## 5. 本次已落地（2026-10-25）

| 项 | 落地内容 | 验证方式 | 状态 |
|---|---|---|---|
| 项目技能 | `.dsh/skills` → `.opencode/skills` 目录联接（Windows junction），dsh 按 `project-dsh` 根发现 | 会话技能目录由 33 → **53** 条，`li-an-workflow`/`vtj-frontend`/`scope-guard` 等 20 条出现 | ✅ 免重启生效 |
| 技能防重复入库 | `.gitignore` 增 `.dsh/skills` | `git status -uall` 不再出现该路径 | ✅ |
| MCP | `~/.dsh/profiles/desktop/cordis.patch.yml` 增 `mcp-vtj` 行（`@deepseek-ai/dsh-mcp-client`） | `mcp__vtj__vtj_list_pages` 等 19 工具出现在工具列表，资源服务器 `vtj` 可列 | ✅ 免重启生效 |
| 门禁编码缺陷 | `gate_all.py` 子进程强制 UTF-8 + 主进程输出 `errors='replace'` | 默认 GBK 控制台下不再出现 `UnicodeEncodeError` 假 FAIL | ✅ |

### 5.1 基线与验证记录（2026-10-25 09:25–09:45）

| 检查 | 命令 | 结果 | 结论 |
|---|---|---|---|
| 后端门禁 9 层 | `python backend/scripts/gates/gate_all.py` | **8/9 PASS**；L2 FAIL | L2 为既有失败：`分节题号区间全等 4/85`；材料守卫全绿（材料块 306、块内题号 0、图片错位 0/2512、表格行归属 1.0）。`last_run.json` 连续 3 个提交均为 L2 FAIL |
| 前端单测 | `npm run test:unit` | **331 passed / 21 files** | 通过 |
| Vite 韧性 | `npm run test:vite-resilience` | **PASS** | ws 代理 / 50 次重连 / strictPort / 后端中断均通过 |
| 后端测试 | `python -m pytest -q` | **550 passed / 19 failed / 3 xfailed**（629.85s，572 collected，内存库） | 失败分组见下表 |
| 类型检查 | `npx vue-tsc --noEmit -p tsconfig.json` | 修复前 **58 errors**（基线 8）→ 修复后 **0** | ✅ `build:prod` 恢复 |
| 项目健康 | `npm run verify:health` | **通过（阻断类 0）** | 仍余 25 条警告：24 个未被路由引用的 `.vue` + 1 处 VTJ DSL 漂移（不阻断） |

**后端 19 个失败分组（均与本次配置改动无关）**：

| 组 | 数量 | 证据 | 性质 |
|---|---|---|---|
| 已知破损（`known_broken.json`） | 5 | `test_materials_admin::test_batch_delete_empty`、`test_monitoring`、3 个 playwright | 既有 |
| 安全测试 API 误用 | 9 | `tests/test_security.py` 用 `from jose import jwt` 却按 PyJWT 签名调用 `jwt.decode(token, options=...)`；python-jose 要求 `key` 必填 → `TypeError` | 测试代码缺陷 |
| API 契约 | 1 | `test_api_surface` 报未登记新端点 `POST /api/questions/group/{group_id}/images` | **需授权决策**（R11） |
| 解析行为 | 1 | `test_gongzhuan_regression`：0 题文档产出 1 个 `format=unnumbered` 题块 | 行为变更，待定 |
| 统计口径 | 1 | `test_practice_unified`：subjects 实数 0，期望 1 | 待定 |
| MinerU 回退 | 2 | 回退断言返回 MinerU 文本而非 PADDLE 兜底文本 | 测试期望与实现不一致 |

**类型错误分布（修复前 58 条）**：`.vtj/vue/home_page.vue` 47（`state.recruitCategories` 推断为 `never[]` / `{}`）、
`.vtj/vue/teacher_papers.vue` 5（`v-for` 索引被推断为 `string | number`）、`src/views/student/mobile/*.vue` 6
（`string | null` 传参、隐式 any）。

### 5.2 类型错误修复记录（2026-10-25 09:45–09:56）

| 文件 | 改动 | 为什么 |
|---|---|---|
| `.vtj/vue/home_page.vue` | 新增 `RecruitItem` / `RecruitCategory` / `RecruitMeta` 接口；`reactive` 初值显式标注；方法形参标注；`icons/bgs` 标 `Record<string,string>`；`catch (e: any)`；`_recruitRefresher` 改名 `recruitRefresher` 并进 `data()` 声明 | 空数组/空对象被推断成 `never[]`/`{}`，模板逐字段访问即 TS2339；下划线前缀会被 Vue 当内部属性 |
| `.vtj/vue/teacher_papers.vue` | `ref<any>` → `ref<any[]>`（`paperQuestions` / `previewQuestions` / `aiResultPapers`）；`currentAiPaper` 显式 `computed<AiPaper>` | `ref<any>` 让模板 `v-for` 索引变成 `string | number`，`idx + 1` 与 `number` 形参全部报错 |
| `src/views/student/mobile/mobile_wrong_review.vue` | 局部变量 `answers` → `reviewPayload` | 初始化表达式内 `answers.value` 指向自身，TS7022 隐式 any 自引用 |
| `src/views/student/mobile/mobile_news.vue` | `content` 缺省时传 `''` | 入参声明是 `string`，实参为 `string | null` |
| `src/views/student/mobile/mobile_forum_detail.vue` | `formatTime(iso?: string | null)` | 帖子未加载时 `createTime` 为 null |
| `src/views/student/mobile/mobile_student_papers.vue` | `examTypeName(t?: string | null)` + 显式映射表 | `p.exam_type` 可能缺省 |
| `src/modules/community/store.ts` | `export type { ForumShareType }` | 调用方从 store 导入该类型，store 只 import 未 re-export |
| `tsconfig.json` + `src/utils/{recruitmentRefresh,newsRender}.d.ts` | 补 `node` 类型、补两份 JS 模块声明 | 消除 `process` TS2591 与 JS 模块 TS7016（配置层噪音） |
| `.typecheck-baseline.json` | 基线 8 → 0 项 | 那 8 条 `teacher_papers` 旧错误已随代码修复消失，残留基线会掩盖未来回归 |

**红线合规**：两个 `.vtj` 页面只动 `<script>`，`git diff` 的 hunk 全部 ≥ 第 133 行（`<template>` 段 1–130 行零改动）；
两页均为 `raw: true`，**未执行** `vtj_sync_vue_to_dsl`（R2）。

**修复后验证**：`vue-tsc` 0 errors → `typecheck:guarded` 通过（零新增）→ `test:unit` 331 passed →
`verify:health` 通过（阻断 0）→ `build:prod` **✓ built in 25.75s**（4025 modules）。

---

## 6. 交付与审批

1. 本文件即为该方案的落盘权威副本。
2. 后续新任务：先 CTC 思考链，再给实施方案，批准后执行。
3. **待用户决策**：DeepInfer 接入细节（endpoint/协议/模型）、L2 门禁「分节题号区间全等 4/85」是否按既有噪声接受或单独立项修复。

---

*本次仅改动 dsh 配置、门禁脚本可运行性、类型声明与 `.vtj` 页 `<script>` 段的类型标注；
未改动任何接口、数据模型、业务分支与 `<template>`。*
