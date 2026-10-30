# 砺安题库 × DeepSeek-Harness × DeepInfer 联合执行与优化总方案 v1

> **来源**：用户 2026-10-26 输入的《砺安题库系统 × DeepSeek-Harness × DeepInfer 联合执行与优化总方案》（原始状态：待审核）。
> **归档**：本文为原文落盘 + 本仓库适配修正（§6）+ 与 QBDM v4 的落地映射（§7）。
> **效力**：本文是**输入规范**，不是最高指令。效力顺序：`AGENTS.md` R1–R12 ＞ `题库设计模式_事实基线_v1.md` ＞ `题库设计模式_v4.md` ＞ 本文。
> 原文提出的"本方案为最高指令"在执行上落为：**它的约束已全部内化进 v4**（§7 映射表），冲突时以 R1–R12 与事实基线为准。

---

## 第一部分 联合架构与高效能调用矩阵

### 1.1 角色与 dsh 编排

| 角色 | dsh 映射 | 核心职责 | 绑定 MCP / Skills |
|---|---|---|---|
| 总设计师 / Lead | Lead Agent | 全局统筹、契约定义、审核节点、阻断冲突 | `li-an-workflow`、`writing-plans`、`codebase-design` |
| 前端建模师 | Teammate | Vue `<script>` 修改、VTJ 取证 | `vtj-mcp-server`(19 工具)、`li-an-workflow` §5、`design-taste-frontend`(仅手写页) |
| 后端建模师 | Teammate | FastAPI 逻辑、SQLite WAL、路由注册 | `tdd`、`implement`（无 backend MCP，走 CLI） |
| 接口与测试 | Teammate | 343 条路由条目契约比对、回归 | `verification-before-completion`、`qa`（无 test MCP，走 pytest） |
| 管理 / 审计 | Teammate | 凭据、健康检查、日志 | `review`、`check_secrets.py`、`git-guardrails-claude-code` |

### 1.2 模式调用策略（Token 节流）

| 模式 | 调用场景 | 路由策略 | Token 优化手段 |
|---|---|---|---|
| **标准模式** | 常规 CRUD、重构、文档 | 本地/低成本优先，云端兜底 | session compaction、稳定前缀吃缓存 |
| **创造模式** | 新架构、组卷/判题算法 | 高 reasoning effort + 多提供商 fallback | 仅必要时启用；产出**当轮**归档复用 |
| **PTC 模式** | 662MB 级语料、题图索引、压测 | 本地沙箱执行 | 大文件**不进上下文**，只回流结论 |

---

## 第二部分 Token 极简与上下文控制

1. **最小化加载**：只按需加载 1–3 个文件；禁止全库 `tree`、禁止大面积读取。
2. **大文件隔离**：`题库/`（实测 690.9 MB）、`backend/app/static/`（实测 46.5 MB）只传路径与统计摘要。
3. **防返工机制**：宣称"完成"前必须过门禁脚本或实际命令，禁止虚假完成（= v4 P7 / Z3）。
4. **需求蔓延拦截**：只执行已批准计划，禁止顺手优化无关模块（= v4 A4）。

---

## 第三部分 红线与强制工作流

### 3.1 `AGENTS.md` 物理红线

- **R1/R3**：`.vtj/` 禁止移动/改名/删除；**默认禁止直接改 `<template>`**（例外流程见 §6-6）。
- **R2**：`raw:true` 页禁止 `vtj_sync_vue_to_dsl`。**注意：本仓库 raw 页是 47 个，不是 2 个**（基线 F6）。
- **R11**：343 条路由条目冻结（`api_surface.json`），增删改须显式批准。
- **R10**：SQLite 备份必须 `sqlite3.backup()`。
- **凭据**：禁止真实密钥入 `.md`/源码；`backend/.env` 的 `JWT_SECRET_KEY` 待用户轮换，AI 不代填。

### 3.2 强制工作流 `li-an-workflow`

规划 → 复述 → VTJ 技能 → 逐步验证 → 输出摘要（= v4 Q0→Q6 的裁剪版）。

### 3.3 代码前置思考链 CTC-11

原方案列的 11 条（原文第 11 条为"已有开源实现可集成/仿原理"）已完整落为 v4 §6.3 的 CTC-1…CTC-11，每问都加了**可接受证据**，避免答成空话。

---

## 第四部分 分支冲突阻断与阶段规划

### 4.1 分支规则（原文）

```
main
 └── feat/<模块名>              ← 模块工作域，只接受测试过的子分支合并
      └── feat/<模块名>/<子任务>  ← 子分支，一次一件事
```
- 禁止子分支直连 `main`；只向父域合并/PR。
- 开工先 `git pull` 当前子分支；父域有更新则 `rebase`。
- 合并顺序：孙 → 子 → 模块域 → main，不得跳层。

### 4.2 执行阶段（原文）

- **Phase 1（当前）**：待 P3B 完成后，再开始规划新的功能改造。
- **Phase 2**：三端数据一致性 + 题目导入改造。
- **Phase 3**：把 dsh 插件化与 DeepInfer 接入用于重构与测试。

---

## 第五部分 交付与审批机制（原文）

1. 用户确认后，将本方案保存到 `D:\砺安题库\砺安题库\docs\plans`（命名清晰易懂）。
2. dsh 后续必须先输出 CTC 思考链，再给实施方案。
3. 等待用户审阅，决定是否下钻（DeepInfer 适配器细节、Schema 调整等）。

---

## 第六部分 本仓库适配修正（实测，逐条）

| # | 原文/假设 | 实况（基线编号） | 处置 |
|---|---|---|---|
| 6-1 | 归档到 `D:\砺安题库\砺安题库\docs\plans` | 该路径**不存在**；真实仓库根 `D:\AAA项目文件\砺安题库\li_an-question_bank` | 已落盘到真实 `docs/plans/` + `solve_problems_files/` 副本 |
| 6-2 | 子分支 `feat/<模块>/<子任务>` | Git 不允许 `feat/forum` 与 `feat/forum/x` 同时为 ref（F16：`feature/forum` 已存在） | 用 `feat/<模块>-<子任务>`（语义等价，已写入 v4 §7.1） |
| 6-3 | 技能 `plan-control` / `vtj-frontend` / `completion-verifier` / `scope-guard` / `context-minimal-loader` / `token-optimization` | 这些名字**在仓库与插件中都不存在**（F10：只有 39 个 `.agents/skills`） | 全部换成真实技能名（v4 §3 表） |
| 6-4 | "待扩展 backend-mcp-server / test-mcp-server" | 当前只有 vtj 一个 MCP（F11） | 记为缺口 G1，维持 CLI 路线，不虚构 MCP |
| 6-5 | DeepInfer 本地优先 / PTC Runtime | 仓库**无** DeepInfer 适配器配置（无 `.dsh/`、`cordis.patch.yml`，F10） | 只声明路由契约；声称"已接入"必须给配置路径 + 调用日志（v4 §4、G5） |
| 6-6 | "禁止改 `<template>`" | R3 原文为**默认禁止**，用户可逐次授权 | 例外流程：用户明示授权 → `.bak_<日期>` 备份（SHA256 校验）→ 只改目标片段 → 只跑 `check_consistency` 不同步 → 报告里写明例外 |
| 6-7 | 343 端点 | 343 是**路由条目**；按 `prefix+path` 去重 301、按 `(method,完整路径)` 去重 340（F3） | 契约比对一律用"条目数"，避免假差异 |
| 6-8 | `backend/scripts/gate_all.py` | 真实路径 `backend/scripts/gates/gate_all.py`，共 11 个脚本（F9） | 命令已按真实路径写入 v4 §8 |
| 6-9 | Phase 1「待 P3B 完成后再做新功能」 | 当前在途任务：论坛 P3（T9–T14）已完成 P2、P3 未开始 | **待你裁决**：①P3 视为已批准在途，做完再进 Phase 2；②暂停 P3 先做 Phase 2 |
| 6-10 | "本方案为最高指令" | 与 R1–R12 冲突时红线优先 | 效力顺序见本文头部 |

---

## 第七部分 落地映射（原文 → v4）

| 原文条款 | 落到 v4 |
|---|---|
| §1.1 角色 × dsh 编排 | §3 九角色矩阵 |
| §1.2 标准/创造/PTC | §4 模式分层与模型路由 |
| §二 Token 极简 4 条 | §5 Token 零浪费契约（Z1–Z5 + 三账单 + 禁用清单） |
| §3.1 R1/R2/R3/R10/R11 + 凭据 | §0 §7 §8（并新增 raw 页 47 的真实约束） |
| §3.2 li-an-workflow 五步 | §6.1 Q0–Q6 |
| §3.3 CTC-11 | §6.3（逐问加证据要求） |
| §四 分支规则 | §7（含 B9 无 upstream 处置） |
| §四 Phase 1/2/3 | 本文 §6-9 待裁决 + 各 Phase 单独立项 |
| §五 交付与审批 | §9 交付物模板 + §9.5 归档三件事 |

---

## 第八部分 需用户裁决（3 条）

1. **Phase 1 与在途任务冲突**（6-9）：论坛 P3（T9–T14）继续，还是先冻结转 Phase 2？
2. **是否 push 当前分支**：`feature/forum-personalization` 无 upstream（F2），`git pull` 规则无法执行。要不要我推送并设 upstream？（涉及远端写权限）
3. **是否立项做 QBDM CLI**：旧文档的 `scripts/qbdm/qbdm.py` 不存在（R3）。要的话建议单开子分支 `feat/qbdm-cli` 实现 `module/design/gate` 三个子命令，不混进文档任务。

---

## 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1 | 2026-10-26 | 归档用户原始方案（五部分）+ 10 条本仓库适配修正 + 落地映射 + 3 条待裁决 |
