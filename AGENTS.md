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
| ORM | `backend/app/models/models.py` **1969 行（含 280 空行；非空 1689）/ 72 个模型**（P3B 已拆出 `models/` 目录，勿再按「单文件 1668 行」描述） |
| 健康检查 | `/health`（`main.py:633`）与 `lifespan` **已存在**，勿重复实现 |
| 门禁 | **9 层**脚本（L0 / L1-G / L1 / L1-H / L2 / L3 / L4 / L5 / L6），由 `backend/scripts/gates/gate_all.py` 编排；`--quick` 只跑 L0/L1-G/L1/L1-H |

**重要**：旧方案文档 `学生端容器化模块化设计方案_v1.md` 的 9 条主张中 **8 条与系统实际不符**（容器数、数据库类型、拆分必要性、badge 服务、健康检查等）。**以 v2.0 为准，勿以 v1 为据。**

> **2026-11-04 复核（实测）**：上表部分数字已变化——`models/models.py` 2567 行 / 99 类；`.vtj/vue` 80 页 + `.vtj/files` 75；`src/views` 38 页；`backend/tests` 141 个 `test_*.py`；`api/v1` 51 个非 `__init__` py / `main.py` 52 处 `include_router`；门禁 13 个脚本 / 10 层（含 L7）；`api_surface.json` 仍为 37 模块 / 343 条目，但实际 `app.openapi()` 为 414 paths / 462 operations（快照 2026-10-15 已过期）。
> **数字唯一来源改为 `docs/plans/题库设计模式_事实基线_v2.md`（F1–F30）**；本表仅作 2026-10-26 前基线，引用前先查基线 v2。
> `solve_problems_files/` 已不存在（目录分层重构完成）：归档只写 `docs/{design,plans,ops,archive}/` + `docs/README.md` 索引，不再新增副本。

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
| 本机 profile | `~/.dsh/profiles/web/`（**只有 web；不存在 `profiles/desktop`**） | dsh `0.1.7-rc.2`；`cordis.patch.yml` 仅 4 条覆盖（ui-settings-general / agent-default-model / subagent / permission）；模型 provider `deepseek-official` / `deepseek-flash` / `reasoningEffort: max`（2026-11-04 实测） |
| 项目技能根 | `.dsh/skills` → `.opencode/skills`（Windows 目录联接 / junction） | dsh 按 `project-dsh` 根扫描；本机 `.opencode/skills` 实测 **2 个**（`qbdm-role-switch`、`qbdm-design-mode`，历史机 22 个）；正文不入 Git，缺失按 `docs/plans/题库设计模式_技能重建手册_v2.md` 重建 |
| 联接的 Git 处理 | `.gitignore` 中 `.dsh/skills` | 若不加，git 会穿过 junction 把技能重复登记为未跟踪文件（实测） |
| MCP 桥接 | `.mcp.json` = `vtj-mcp-server`（19 工具 / 3 资源） | **本机未桥接**：profile `web` 无 `mcp-vtj` 行、`dsh-mcp-client` 未挂载、会话无 `mcp__vtj__*`（2026-11-04 实测）；需要时补 MCP bundle（需用户批准） |
| 门禁编码 | `backend/scripts/gates/gate_all.py` | 子进程强制 `PYTHONIOENCODING=utf-8`；否则 Windows GBK 控制台下子脚本打印 `✅/ℹ` 会抛 `UnicodeEncodeError`，被误判为 FAIL |

**注意**：MCP 行是**宿主级**配置，`cwd` 固定指向本仓库。在 dsh 里打开其它工作区时
vtj 工具仍会读写本仓库，不需要时把该行 `disabled` 改为 `true` 后重启 dsh。

重建技能联接（换机 / 误删后）：

```powershell
New-Item -ItemType Directory -Force .dsh | Out-Null
New-Item -ItemType Junction -Path .dsh\skills -Target (Resolve-Path .opencode\skills)
```

---

## 8. 题库设计模式 QBDM（2026-11-04 起以 v5 为唯一权威）

任何涉及题库功能模块的设计 / 编码 / 测试 / 归档任务，**开工前先戴帽**，再动手。

| 项 | 位置 | 说明 |
|---|---|---|
| **总纲（v5，现行）** | `docs/plans/题库设计模式_v5.md` | **唯一入口总纲**：GitHub 分工接管（模块 4/7）、三分支方案、MCP/Skills/Workflows 重点分析、DeepInfer 契约、Token 100% 可审计协议、九角色、Q0–Q6 + 三态、门禁、A1–A39、G1–G27 |
| **事实基线（v2，数字唯一来源）** | `docs/plans/题库设计模式_事实基线_v2.md` | F1–F30（2026-11-04 实测）：主线/分支/契约/装配/ORM/页面/测试/门禁/技能/MCP/dsh/DeepInfer/模块 4/7/Phase 2；v1 的历史错值保留为反面凭证 |
| 热加载角色卡（v3） | `docs/plans/题库设计模式_角色卡_v3.md` | **换角色只读这个**（声明头 v5、九角色真实技能、Token 自检、分支一屏） |
| 热加载模块作战卡（v3） | `docs/plans/题库设计模式_模块作战卡_v3.md` | **领到模块任务只读这个**（开工五步、M1–M12、D/O/T、模块 4/7 入口） |
| 技能重建手册（v2） | `docs/plans/题库设计模式_技能重建手册_v2.md` | `.opencode/skills` 不入 Git：换机按 16 技能清单重建（本机缺 13 个） |
| 模块 4/7 接管档案（v1） | `docs/plans/题库设计模式_模块4_7交接档案_v1.md` | 模块 4/7 的分支、页面、端点、表、测试、Phase 2 现状与下一步任务 |
| 历史版本（v1–v4） | `docs/superpowers/specs/题库设计模式_v1/v2/v3.md` + `docs/plans/题库设计模式_v4.md` | v4 已被 v5 取代；v1–v3 仅追溯用 |
| **模块台账** | `docs/design/题库模块台账_v1.md` + `.json` | 25 模块 × 端点/页面/测试/事件；生成于 2026-10-30，**当前 `--check` = DRIFT**（模块 4 未入账、模块 7 为 stub），重生成单独立项 |
| 模式入口 CLI | `python scripts/qbdm/qbdm.py role / gate / modules / module / design / branch / handoff / token / status` | 角色、门禁、模块三段清单、三态管线、**分支拓扑、模块 4/7 接管、Token 账单**一条命令可查；`status` 自检模式资产 |
| 装载预算闸 / 测试扫描 | `scripts/qbdm/ctx_budget.py` / `scripts/qbdm/test_sweep.py` | 装载前估算 token（Z4）；全量 pytest 挂起时拿 OK/FAIL/HANG 三态 |
| 机器可读绑定 | `scripts/qbdm/design_mode.json` | `version: v5`，含 roles/states/mcp/github/token/deepinfer/facts 指针 |

**最少记住 9 条**：
1. 九角色 = ARCH / PM / DATA / BE / API / FE / SEC / QA / DOC，**一次只戴一顶帽子**；仲裁链 `SEC > API > ARCH > PM > DATA > BE ≈ FE > QA > DOC`。
2. 流程 Q0→Q6，**Q2/Q3/Q4/Q5/Q6 不可跳**；方案须用户批准后才进入实施。
3. 五零指标：Z1 重复读=0、Z2 未验证断言=0、Z3 返工=0、Z4 超预算=0、Z5 归档遗漏=0；每轮必须写 `[TOKEN]` 账单（v5 §6）。
4. 没有门禁输出的"完成"一律判为未完成；未跑的层标「未验证 + 验证方式」。
5. 模块任务先跑 `python scripts/qbdm/qbdm.py module <id>`；模块 4/7 先跑 `qbdm.py handoff` 并读接管档案。
6. 分支：**只在子分支干活、只向父域合并、禁止直连 main**；父 ref 与斜杠子 ref 同仓不可并存（D/F），默认 `feat/<模块>-<子任务>`。
7. 用户只负责模块 4（学习计划）/ 7（联考小智）；其他模块只读，跨模块需求走 Handoff + 用户裁决。
8. 本机 MCP 未桥接、DeepInfer 零证据：文档不得写「已接入」；dsh 唯一 profile 是 `web`（不是 desktop）。
9. 数字只认事实基线 v2；v1–v4 与 AGENTS §3 旧表均为历史输入（api_surface 343 条是 2026-10-15 冻结值，实际 openapi 462 操作）。

> 与第 7 节的关系：第 7 节讲**工具怎么接**，本节讲**任务怎么跑**，两者不重叠。
