# 论坛 AI 言论审核（分层多 Agent）设计方案 v1

> 状态：**已被 v2 取代**（保留存档；v2 见 论坛AI言论审核_分层多Agent_设计方案_v2.md）
> 日期：2026-11-05
> 分支：`feature/forum-ai-moderation`（从 `main @ 6d53e056` 切出）
> 核心理念：**审核即研判、研判即知识沉淀**；Obsidian 不是生产数据库，而是人机协同的知识运营与审计界面

---

## 0. 先说清楚：仓库里已经有什么（实测）

远端 main 已合入一套「评论区舆情审核 M0」，能力比预想的多。**本次不能重复造轮子**，只能在其上补「语义层 + 多 Agent 分层 + 沉淀闭环」。

### 0.1 已有的库表（12 张 `cg_*`，实测行数）

| 表 | 行数 | 作用 |
|---|---|---|
| `cg_policy` | 11 | 政策条款（含 `policy_dsl`、severity、status） |
| `cg_term` | 88 | 敏感词条（level/category/weight/confidence） |
| `cg_variant` | 26 | 词条变体（同音/拆字等） |
| `cg_judgment` | 1 | **每次审核的研判记录**（decision/confidence/hits/policy_ids/evidence/human_override） |
| `cg_task` | 1 | 人审任务（state/priority/assignee/reviewer） |
| `cg_case` | 0 | 案例库（judgment→case，用于沉淀） |
| `cg_proposal` | 0 | 提案（待审的词条/条款变更） |
| `cg_edge` | 205 | 知识图谱边（词—条款—案例关联） |
| `cg_audit_event` | 2 | 审计流水（before/after hash） |
| `cg_stat_daily` | 2 | 每日统计（blocked/masked/reviewed/passed/false_positive） |
| `cg_redteam_sample` | 0 | 红队样本 |
| `cg_sync_state` | 1 | Obsidian 同步游标 |

### 0.2 已有的服务与接口

- `app/services/content_guard/`：`engine`(词库 Aho-Corasick)、`judgments`(决策+证据链)、`proposals`、`reconcile`(对账)、`redteam`、`obsidian`(539 行导出/导入)、`graph`、`stats`、`audit`、`catalog`、`normalizer`
- `guard_text(db, text, scene, source_id, user_id)` 已挂在**发帖**（`forum.py:700`）与**评论**（`forum.py:1162`），决策值 `pass / mask / block / review`
- 接口：`/api/admin/content-guard/*`（overview/terms/policies/judgments/tasks/proposals/audit/graph/stats/redetect/redteam/obsidian/reconcile/seed/reload）、`/api/admin/knowledge-ops/*`（summary/policies/compile/preview/proposals）、`/api/admin/forum/moderation`（审核队列/通过/驳回/回收站）
- LLM 客户端：`app/services/llm_client.chat`（DeepSeek 兼容）
- 论坛侧：`ForumPost` 有 `status=PENDING`、`forum_moderation` 提供通过/驳回/回收站

### 0.3 缺口（本次要做的事）

| # | 缺口 | 影响 |
|---|---|---|
| G1 | **只有词库命中**，没有语义判断 | "言论正当性"（煽动/攻击/谣言/歧视/隐私/擦边）词库覆盖不到，换皮即绕过 |
| G2 | 没有分层 Agent | 无法把"规则命中"与"语义研判"分开，误杀只能整段人工兜底 |
| G3 | `cg_judgment` 只有一层结论 | 无法记录"哪个 Agent 说的、理由是什么、投票分布" |
| G4 | 研判→沉淀链路未闭环 | `cg_case`/`cg_proposal` 为空，红队样本空，知识不会自生长 |
| G5 | Obsidian 仅导出，未见人工回写落地路径 | "人机协同审计界面"只做了一半 |
| G6 | 无可解释性与申诉入口 | 用户被误判后无反馈通道，误杀数据无法回收 |

---

## 1. 总体架构：五层（L0 已有，L1–L3 新增，L4 已有）

```
发帖/评论
   │
   ▼
┌─────────────────────────────────────────────────────────────┐
│ L0 规则层（已有）engine + cg_term/cg_policy                  │
│   命中 → 直接给出 level/confidence/证据；未命中 → L1          │
└─────────────────────────────────────────────────────────────┘
   │ 可疑样本（规则命中 或 抽样）
   ▼
┌─────────────────────────────────────────────────────────────┐
│ L1 语义裁判 Agent（新）LLM + 政策条款                       │
│   输出：categories[{煽动,攻击,谣言,歧视,隐私,擦边,正常}]      │
│        score[0,1]、quoted_evidence（引用原文片段）            │
└─────────────────────────────────────────────────────────────┘
   │ 需要上下文时
   ▼
┌─────────────────────────────────────────────────────────────┐
│ L2 上下文/意图 Agent（新）                                   │
│   输入：帖子正文 + 标题 + 引用/回复链 + 用户近期行为画像       │
│   输出：intent{求助,吐槽,辩论,攻击,招募,广告,...}、加剧因素    │
└─────────────────────────────────────────────────────────────┘
   │ 三方信号汇总
   ▼
┌─────────────────────────────────────────────────────────────┐
│ L3 仲裁 Agent（新，非 LLM，确定性规则）                       │
│   融合 L0/L1/L2 → 最终 decision: pass/mask/block/review      │
│   置信度门槛 + 场景权重 + 用户风险分                          │
└─────────────────────────────────────────────────────────────┘
   │
   ├─ pass   → 直接放行
   ├─ mask   → 打码展示（保留原文给审核）
   ├─ review → 进人审队列（cg_task）
   └─ block  → 仅在高置信 + 明确条款时使用（默认关闭自动 block）
   ▼
┌─────────────────────────────────────────────────────────────┐
│ L4 人审与沉淀（已有 + 扩展）                                  │
│   人审：/admin/forum/moderation 队列 + 通过/驳回/申诉          │
│   沉淀：judgment → cg_case → cg_proposal → 人审 → 编译入库     │
│   界面：Obsidian vault（导出 → 人工批注 → 回写）              │
└─────────────────────────────────────────────────────────────┘
```

**分层原则**
- L0 决定"要不要叫 LLM"，避免每条都烧钱；
- L1/L2 只输出**信号**，不直接处置（可解释、可回放）；
- L3 是唯一的决策点，纯规则、可单测、可灰度；
- L4 保留人类否决权，所有人工改判写 `human_override` + 审计。

---

## 2. 决策路由表（L3 仲裁规则草案）

`rules_score`=L0 命中强度，`sem_score`=L1 最高分类置信度，`intent_risk`=L2 风险加成，`user_risk`=用户历史（近期被驳回数/申诉成立数）。

| 组合 | 决策 | 说明 |
|---|---|---|
| L0 命中 block 级 且 条款明确 | **block**（可配开关） | 涉政/暴恐等硬条款 |
| L0 命中 且 L1 ≥0.8 同向 | **mask/block** | 双证一致 |
| L0 命中 但 L1 ≤0.3 | **review** | 疑似误杀（如"公安"被误命中） |
| L0 未命中 但 L1 ≥0.75 且 L2 ≥0.6 | **review** | 语义型风险，交人工 |
| L0 未命中 且 L1 0.45–0.75 | **shadow**（只记录不处置） | 灰度期观察，不打扰用户 |
| 其余 | **pass** | 放行 |

阈值全部写进 `cg_policy` 的 `policy_dsl` 或环境变量，**不硬编码**，便于运营调参。

---

## 3. 研判即沉淀：从一次判定到一条知识

```
judgment（L0+L1+L2+L3 全链路快照）
   │ 置信度低 / 人工改判 / 新词新梗
   ▼
case（案例：正文片段 + 各 Agent 结论 + 最终裁定 + 标签）
   │ 提炼
   ▼
proposal（提案：新增词条 / 变体 / 条款 / 阈值调整）
   │ 人审（通过 / 驳回，必填理由）
   ▼
编译（knowledge-ops/compile，dry_run 先验证）
   ▼
engine 热更新（/content-guard/reload）+ cg_edge 关联 + cg_audit_event 留痕
```

**关键约束**
- 沉淀只能**增加**知识，不能删除既有知识；
- 提案必须带 `evidence`（judgment_id），可追溯；
- 编译失败自动回滚到上一版引擎快照；
- 每条提案/编译/回滚写 `cg_audit_event`（before/after hash）。

---

## 4. Obsidian 作为"人机协同知识与审计界面"

> 定位：**不是生产库**。生产数据在 SQLite；Obsidian 是给运营/法务看的可读层 + 批注入口。

### 4.1 Vault 结构（导出生成）

```
content-guard/
├── 00-看板/今日研判.md          # 统计 + 待审任务 + 红队结果
├── 10-条款/COD-POL-001.md       # 条款正文 + DSL + 关联词条 + 关联案例
├── 20-词条/<term>.md            # 词条 + 变体 + 命中统计
├── 30-案例/CASE-2026-0001.md    # 案例：原文片段/各 Agent 结论/裁定
├── 40-提案/PRP-0001.md          # 待审提案（人工在正文下方写结论）
└── 90-审计/2026-11-05.md        # 当日变更流水
```

### 4.2 回写协议（解决 G5）

- 人工在提案 md 的固定区块写：`## 审核结论` → `通过`/`驳回` + 理由；
- 后端定时（或手动触发）扫描 `40-提案/`，用**内容哈希 + frontmatter 版本**判重，幂等入库；
- 冲突（人工改动与系统改动撞车）：以"人工优先、系统留档"处理，冲突写 `cg_audit_event`；
- 回写只允许改**提案结论**与**案例标签**，禁止直接改条款正文（防绕过审计）。

---

## 5. 数据模型增量

不新建大表，复用既有结构：

| 变更 | 说明 |
|---|---|
| `cg_judgment` +3 列 | `agent_trace`(JSON：L0/L1/L2 各自结论与耗时)、`model_version`、`cost_ms` |
| 新表 `cg_agent_run` | 每次 LLM 调用的原始请求/响应摘要（脱敏）、token 数、耗时，用于回放与成本核算 |
| `cg_case` 复用 | 已存在；增加 `judgment_id` 唯一约束（防重复沉淀） |
| `cg_proposal` 复用 | 已存在；`kind` 增加 `threshold_adjust` |

---

## 6. 接口清单（新增/扩展）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/admin/content-guard/redetect`（已有，扩展） | 支持 `layers=L0,L1,L2` 指定分层重跑 |
| GET | `/api/admin/content-guard/judgments/{id}`（已有，扩展） | 返回 `agent_trace` 全链路 |
| POST | `/api/admin/content-guard/cases` | judgment → case 沉淀 |
| POST | `/api/admin/content-guard/proposals`（已有） | 支持 `evidence.judgment_id` |
| GET | `/api/admin/content-guard/obsidian/export`（已有） | 增加 `40-提案` 与看板 |
| POST | `/api/admin/content-guard/obsidian/import`（已有，扩展） | 解析提案结论区块 |
| POST | `/api/forum/posts/{id}/appeal`（新） | 用户申诉（进入 review，附申诉理由） |
| GET | `/api/admin/forum/moderation/appeals`（新） | 申诉队列 |
| GET | `/api/admin/content-guard/agent-stats`（新） | 各 Agent 命中率/误杀率/成本 |

---

## 7. 成本、性能与降级

| 项 | 策略 |
|---|---|
| 调用范围 | 只对"可疑样本"调 L1：L0 命中、长度>20 字、含引号/链接/敏感邻域词，或按 2% 抽样做质量监控 |
| 成本上限 | 每日 token 预算（环境变量），超限自动降级为仅 L0 + review |
| 延迟 | L1 超时 3s、L2 超时 3s；超时按"证据不足"→review，不阻塞发帖 |
| 缓存 | 相同 `content_hash` 命中 24h 内结果直接复用 |
| 降级 | LLM 不可用 → 自动回退纯 L0（与现状一致），并打点告警 |

---

## 8. 误杀治理与申诉

- **默认不自动 block**：LLM 只能把内容送进 review；block 需要"L0 硬条款 + L1 ≥0.8"双证；
- 每条 review 内容对用户显示"审核中"，不影响发帖留痕；
- 用户申诉 → 进入高优队列 → 人工改判 → 写 `human_override`；
- 误杀样本自动进 `cg_redteam_sample`，反哺规则；
- 指标：误杀率、漏杀率（红队集）、平均人审时长、申诉成立率。

---

## 9. 排期（三个里程碑）

| 里程碑 | 内容 | 域/接口 | 量级 |
|---|---|---|---|
| **M1 语义层单点** | L1 Agent + 仲裁接入 guard_text（只产出 review）+ agent_trace + 缓存/预算 | content_guard 扩展，+2 接口 | ~600 行 |
| **M2 分层与沉淀** | L2 上下文 Agent、L3 仲裁规则化、judgment→case→proposal 闭环、Obsidian 回写 | +4 接口、+1 表 | ~900 行 |
| **M3 治理与运营** | 申诉通道、误杀回收、成本看板、阈值热调、红队回归 | +4 接口 | ~700 行 |

---

## 10. 验收标准（可量化）

| 指标 | 目标 |
|---|---|
| 词库换皮绕过率 | 由当前基线（需实测）降到 <10% |
| 误杀率（人工复核样本） | <5% |
| L1 平均耗时 | <1.5s（P95 <3s） |
| 每条内容平均成本 | <0.002 元 |
| 沉淀闭环 | 每周 ≥3 条 case → proposal → 编译 |
| 回滚 | 编译失败 100% 自动回滚，审计可查 |

---

## 11. 待确认（可回「按推荐来」）

| # | 决策 | 建议 |
|---|---|---|
| D1 | 是否允许自动 block | **A. 默认关闭，只 review（推荐）** / B. 高置信自动 block |
| D2 | L1 模型 | **A. 现有 llm_client（DeepSeek chat，推荐）** / B. 另接审核专用模型 |
| D3 | 调用范围 | **A. 可疑样本 + 2% 抽样（推荐）** / B. 全量调用 |
| D4 | 沉淀粒度 | **A. 只沉淀"低置信/人工改判/新词"（推荐）** / B. 全部判定都沉淀 |
| D5 | Obsidian 回写 | **A. 只允许改提案结论与案例标签（推荐）** / B. 允许改条款正文 |
| D6 | 灰度策略 | **A. 先 shadow 记录不处置，跑 2 周数据再放开 review（推荐）** / B. 直接上线 review |
| D7 | 申诉入口 | **A. 本里程碑做（M3，推荐）** / B. 后续再做 |
