# AGENTS.md — 砺安题库 AI 协作规则

> 本文件是项目的**长期强制规则**，所有 AI 会话（OpenCode / Claude Code / 其他代理）开工前必须先读本文件。
> 规则冲突时，以本文件的用户明示指令为准。

---

## 1. 方案与文档自动归档（强制）

**规则**：任何设计方案、规格文档、实施计划，在**展示给用户的同时**，必须**自动存档**到指定目录留档，不得等用户另行要求。

### 1.1 归档位置对照表

| 文档类型 | 权威位置 | 归档副本位置 |
|---|---|---|
| 设计规格 / 方案 | `docs/superpowers/specs/` | `solve_problems_files/<主题>_v<版本>.md` |
| 实施计划 | `docs/superpowers/plans/` | `solve_problems_files/<主题>_v<版本>_实施计划.md` |
| 运维手册 | `docs/ops/` | `solve_problems_files/<主题>_v<版本>_运维手册.md` |
| 排查报告 / 验收报告 | `docs/superpowers/specs/` | `solve_problems_files/<主题>_报告.md` |

### 1.2 命名规范

```
<主题>_v<版本>.md                    # 设计方案
<主题>_v<版本>_实施计划.md           # 实施计划
<主题>_v<版本>_运维手册.md           # 运维手册
<主题>_报告.md                       # 排查/验收报告
```

版本号用点分：`v1`、`v2.0`、`v3.1`。主题用中文业务名，不用代号。

### 1.3 目录分层重构后的自动归档规则

本项目正在进行目录分层重构（详见 `solve_problems_files/学生端容器化模块化设计方案_v2.0.md`），
`solve_problems_files/` 的内容会迁往 `docs/{design,plans,ops,archive}/`。

**因此，自动化规则必须做到迁移后无需修改仍指向正确位置**：

| 阶段 | `solve_problems_files/` 状态 | 归档动作 |
|---|---|---|
| **当前**（重构未完成） | 存在且为文档主入口 | 写入本目录 + 更新 `README.md` 索引 |
| **迁移后**（目录已分层） | 不存在或仅保留 `README.md` 指向新位置 | 自动写入 `docs/{对应子目录}/`，不再写入本目录 |

**判定方法**：写归档前先检查 `solve_problems_files/` 是否存在且含实质内容。
- 存在 → 写入本目录
- 不存在或为空 → 写入 `docs/` 下对应子目录

### 1.4 归档后必须做的三件事

1. 更新 `solve_problems_files/README.md` 的文档索引（迁移后改为 `docs/README.md`）
2. 在提交信息中写明归档了哪个主题的哪个版本
3. 向用户报告：存档路径 + 文档摘要

### 1.5 禁止事项

- ❌ 只在对话中展示文档而不落盘——**展示与落盘必须同时发生**
- ❌ 方案定稿后不归档，事后补——**定稿当场归档**
- ❌ 归档时不更新 `README.md` 索引——文档会再次变成找不到的「散乱」状态

---

## 2. 本项目不可违反的工程红线

违反以下任一条即视为破坏性改动，必须停下并向用户确认。

| # | 红线 | 原因 |
|---|---|---|
| R1 | **`.vtj/` 禁止移动、改名、删除** | `src/router/index.ts` 有 **92 处** `import('$vtj/vue/<id>.vue')` 硬绑定；VTJ 设计器按 page id 读写。动了直接 404 + 设计器失效 |
| R2 | **`raw: true` 页面禁止 `vtj_sync_vue_to_dsl`** | 同步器提取不到的手写方法会丢失，设计器回存再覆盖回来；工具会返回 `RAW_PAGE_PROTECTED` |
| R3 | **`.vtj/` 页面的 `<template>` 禁止 AI 直接改** | 须由用户在设计器 `http://localhost:9527/__vtj__/` 拖拽完成。AI 只可改 `<script>`，且必须先 `dryRun: true` |
| R4 | **`src/utils/device.ts` 与 `resolveDevicePath()` 原样保留** | 设备双轴核心，承载 PC → mobile/tablet 路径自动映射 |
| R5 | **`mobile_*`、`tablet_*` 文件名前缀不重命名** | 与 `.vtj/vue/` 一一对应，前缀是建立对照关系的唯一线索 |
| R6 | **`题库/` 禁止删除或移动** | 662 MB 原始 PDF 语料，唯一事实来源；行测重导依赖它 |
| R7 | **`backend/app/static/` 禁止删除** | 4.3 GB 题图在库，删除即全站裂图 |
| R8 | **`backend/data/*.bak*` 禁止清理** | 41 份唯一备份；`bak_pre_wipe_20261004_102517` 是全系统唯一存世的 10,171 道行测题副本 |
| R9 | **`backend/data/audit/` 与 `待推断题目清单_*.csv` 不是垃圾** | 数据变更追溯凭证 / 待人工处理的数据清单 |
| R10 | **数据库备份禁用 `shutil.copy2`** | WAL 模式下只拷主库无法保证完整性，必须用 `sqlite3.backup()` API；回滚须同时删 `-wal` 与 `-shm` |
| R11 | **API 路径 `/api/v1/...` 冻结** | 343 个端点已记录于 `backend/data/refactor_baseline/api_surface.json`，重构后须逐条比对一致 |
| R12 | **不为平板新建手机页的重复副本** | `/tablet/news` 等 21 条平板路由中部分直接复用 `@/views/mobile_*.vue`，经 `meta.platform` 区分设备。复制一份会制造双份维护成本 |

---

## 3. 项目技术栈基线（实测，勿凭印象）

| 层 | 技术 |
|---|---|
| 前端 | VTJ 低代码（`@vtj/cli` 0.12.19 / `@vtj/web` 0.16.35）、Vue 3.5.34、Vite 6.3.7、Element Plus 2.13.7、Pinia 3.0.4、**hash 路由** |
| 前端布局 | 位于**仓库根**（`src/`、`.vtj/`、`dist/`、`package.json`）；`vite.config.ts` 有 `workspaceRoot` 强制校验，**不可移入子目录** |
| 前端双轴 | **角色（student/teacher/admin）× 设备（pc/tablet/mobile）**；`.vtj/vue` 75 页 = PC 61 / 平板 7 / 手机 7 |
| 前端页面归属 | **教师端 8 页、管理端 11 页全在 `.vtj/vue/`，`src/views/` 中为 0**。`src/` 分层须按角色 × 设备双轴（`views/<role>/<device>/`），为后续三端手写页预留入口 |
| 前端设备复用 | `/tablet/` 21 条路由中部分直接复用 `@/views/mobile_*.vue`，经 `meta.platform` 区分，**不新建重复组件** |
| 后端 | **单一 FastAPI 单体**，38 处 `include_router`，37 个 `api/v1` 模块，**343 个端点** |
| 数据库 | **SQLite**（WAL，292 MB），**不是 PostgreSQL**；`DB_TYPE` 已预留 `mysql+pymysql` 出口 |
| ORM | `backend/app/models/models.py` **1689 行 / 72 个模型**（P3B 已拆出 `models/` 目录，勿再按「单文件 1668 行」描述） |
| 健康检查 | `/health`（`main.py:633`）与 `lifespan` **已存在**，勿重复实现 |
| 门禁 | **9 层**脚本（L0 / L1-G / L1 / L1-H / L2 / L3 / L4 / L5 / L6），由 `backend/scripts/gates/gate_all.py` 编排；`--quick` 只跑 L0/L1-G/L1/L1-H |

**重要**：旧方案文档 `学生端容器化模块化设计方案_v1.md` 的 9 条主张中 **8 条与系统实际不符**（容器数、数据库类型、拆分必要性、badge 服务、健康检查等）。**以 v2.0 为准，勿以 v1 为据。**

---

## 4. 实测优先原则

| 场景 | 做法 |
|---|---|
| 描述系统现状 | **先测量再陈述**，给出文件路径与行号 |
| 引用数量 | 必须可追溯到测量命令的输出 |
| 不确定的判断 | 显式标注置信度与验证方式，不得断言 |
| 子代理不可用 | 如实告知并说明原因，不得假装已委派成功 |

本项目已建立基线资产，重构前可直接复用：

| 资产 | 路径 |
|---|---|
| API 端点快照（343） | `backend/data/refactor_baseline/api_surface.json` |
| 模型映射（71） | `backend/data/refactor_baseline/model_map.json` |
| 耦合图 | `backend/data/refactor_baseline/coupling.json` |
| 表使用矩阵 | `backend/data/refactor_baseline/table_usage.json` |
| 库表清单（72） | `backend/data/refactor_baseline/db_tables.json` |
| 备份审计报告 | `backend/data/backup_audit_report.json` |
| 语料探测器 | `backend/scripts/probe_xingce_corpus.py` |

---

## 5. 凭据处理

- **禁止**将真实密钥写入 `.md` 文档、源码、提交信息
- `.env` 类文件**禁止**纳入 Git 跟踪；必须配 `.gitignore` + 提供 `.env.example`
- 发现已泄露的密钥：**轮换是唯一彻底解法**，改写 Git 历史只是附加项
- 新增密钥由**用户本人**生成与填写，AI 不经手密钥值

**当前已知两处已泄露（须处理）**：
1. `.omo/plans/configure-deepseek-api.md` — DeepSeek 密钥（✅ 已吊销）
2. `backend/.env` — `JWT_SECRET_KEY` 48 位真实值，跨 3+ 提交（✅ 已于 2026-10-25 由用户本人轮换为 64 字符新值；实测非占位符。旧值仍在 Git 历史中——轮换即为终局处置，改写历史只是附加项）

---

## 6. 目录分层重构进行中

**方案**：`solve_problems_files/学生端容器化模块化设计方案_v2.0.md`
**计划**：`solve_problems_files/学生端容器化模块化设计方案_v2.0_实施计划.md`
**分支**：`feat/student-containerization`

阶段：`P0 测试修复+凭据` → `P1 容器化` → `P2 core 抽离` → `P3A 前端分层` → `P3B 十域搬迁` → `P4 契约改造` → `P5 事件总线` → `P6 目录清理`

> 实测（2026-10-25）：当前检出分支为 `feat/fix-bug`，与上文分支名不一致。
> **P3B 是否完成以提交记录为准，不得只凭分支名判断**。

⚠️ 用户后续的**教师端题目导入改造**与**三端「导入—展示—通信」数据一致性**工作，
必须在 **P3B 完成后再启动**，否则会与目录搬迁改动同一批文件，冲突不可控。

---

## 7. dsh（DeepSeek Harness）接入现状

本仓库同时被 OpenCode / Claude Code / dsh 使用。dsh 侧配置在一次会话中已实测生效，
改动前请先确认下列位置，避免重复搭建或误删：

| 项 | 位置 | 说明 |
|---|---|---|
| 项目技能根 | `.dsh/skills` → `.opencode/skills`（Windows 目录联接 / junction） | dsh 按 `project-dsh` 根（rank 100）扫描；项目自有 20 个技能（`li-an-workflow`、`vtj-frontend`、`plan-first-workflow`、`completion-verifier`、`scope-guard`、`token-optimization` 等）**正文仍只存放在 `.opencode/skills`**，该目录已在 `.gitignore` 中 |
| 联接的 Git 处理 | `.gitignore` 中 `.dsh/skills` | 若不加，git 会穿过 junction 把 20 个技能重复登记为未跟踪文件（实测 21 条） |
| MCP 桥接 | `~/.dsh/profiles/desktop/cordis.patch.yml` 的 `mcp-vtj` 行 | `@deepseek-ai/dsh-mcp-client` + `vtj-mcp-server`，工具名 `mcp__vtj__*`（19 个） |
| 门禁编码 | `backend/scripts/gates/gate_all.py` | 子进程强制 `PYTHONIOENCODING=utf-8`；否则 Windows GBK 控制台下子脚本打印 `✅/ℹ` 会抛 `UnicodeEncodeError`，被误判为 FAIL |

**注意**：MCP 行是**宿主级**配置，`cwd` 固定指向本仓库。在 dsh 里打开其它工作区时
vtj 工具仍会读写本仓库，不需要时把该行 `disabled` 改为 `true` 后重启 dsh。

重建技能联接（换机 / 误删后）：

```powershell
New-Item -ItemType Directory -Force .dsh | Out-Null
New-Item -ItemType Junction -Path .dsh\skills -Target (Resolve-Path .opencode\skills)
```

---

## 8. 题库设计模式 QBDM（2026-10-25 起生效）

任何涉及题库功能模块的设计 / 编码 / 测试 / 归档任务，**开工前先戴帽**，再动手。

| 项 | 位置 | 说明 |
|---|---|---|
| 全文（权威） | `docs/superpowers/specs/题库设计模式_v1.md` | 九角色、Q0–Q6、五零指标、分支细则、门禁矩阵、13 条反模式 |
| 角色卡（热加载） | `docs/superpowers/specs/题库设计模式_角色卡_v1.md` | **每任务只读这个**（3.8KB）即可完成角色切换 |
| 技能（自动触发） | `qbdm-role-switch`（`.opencode/skills/qbdm-role-switch/SKILL.md`） | 已实测被 dsh 即时发现；因 `.opencode/` 在 `.gitignore` 中，**技能正文不纳入 Git**，缺失去从角色卡文档重建 |
| 装载预算闸 | `scripts/qbdm/ctx_budget.py` | 装载前估算 token 并对照 T0–T3 预算（Z4 可测） |

**最少记住 4 条**：
1. 九角色 = ARCH / PM / DATA / BE / API / FE / SEC / QA / DOC，**一次只戴一顶帽子**；仲裁链 `SEC > API > ARCH > PM > DATA > BE ≈ FE > QA > DOC`。
2. 流程 Q0→Q6，**Q2/Q3/Q4/Q5/Q6 不可跳**；方案须用户批准后才进入实施。
3. 五零指标：Z1 重复读=0、Z2 未验证断言=0、Z3 返工=0、Z4 超预算=0、Z5 归档遗漏=0。
4. 没有门禁输出的"完成"一律判为未完成（与 `completion-verifier` 一致）。

> 与第 7 节的关系：第 7 节讲**工具怎么接**，本节讲**任务怎么跑**，两者不重叠。
