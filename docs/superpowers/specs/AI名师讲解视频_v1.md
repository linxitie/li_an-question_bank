# AI 名师讲解视频模块 · 可落地方案 v1.0

> 文档类型：设计规格 / 方案（待审批，未实施）　版本：v1.0　日期：2026-11-03
> 适用系统：砺安题库（公安联考题库）· 备考资料模块
> 归档：`docs/superpowers/specs/AI名师讲解视频_v1.md`（本文件）
> 前置阅读：`docs/superpowers/specs/砺安题库终态总体架构_v2.0.md`（SoT + 四投影 + Outbox）、`docs/superpowers/specs/向量投影Embedding服务配置与故障治理_v1.md`

---

## 0. 一页纸结论

### 0.1 六个判定（直接回答用户的七个设计要求）

| # | 问题 | 结论 | 一句话理由 |
|---|---|---|---|
| 1 | AI 角色定位 | **考点讲解渲染引擎的「导览员」**，不是答疑机器人 | 答疑已由 `agent_router.py` 的「联考小智」承担；本模块不可替代的价值是「按图谱顺序把考点讲透」 |
| 2 | 是否搭 Obsidian 自生长库 | **必须搭，但只作「教研生产面 / 编译源」，绝不参与运行时** | Obsidian 的价值是人类可 diff 的 Markdown + 可追溯；一旦让学生端读 Markdown，就把格式耦合进业务代码 |
| 3 | 知识图谱建在哪 | **建在题库系统（GraphStore），按图族 + 命名空间隔离；Obsidian 只产「图谱意图」** | F5 图投影已建成（3823 节点/4354 边）；Obsidian 未装 `.obsidian`、无图计算能力；Graph-RAG 需进程内低延迟遍历 |
| 4 | 是否要多 Agent 分工 | **要，但必须是「7 个确定性工位 + 2 个 LLM 调用点」，不是 7 个模型互相聊天** | 7 个对话不可复现、不可测、成本不可控；工位化后每步产物是 JSON，可断点重跑 |
| 5 | 五库（关系/文档/向量/图片/图） | **不新建五个库，映射到既有 SoT + F3/F4/F5/F6**；Mongo/Neo4j/Milvus **当前全部不可用** | 已有底座可承载且支持开关降级；新建库立刻带来运维负担与 35 GB 磁盘硬冲突 |
| 6 | 可视化 CRUD + 日志 | **Canvas 纯 JSON 程序化生成图谱视图 + MCP 做 CRUD + Git/审计双日志** | `AI讲师知识库` 是空目录且未装插件；`.canvas` 是纯 JSON，脚本可直接生成 |
| 7 | 长期稳定与准确 | **四条硬机制**：确定性渲染、Citation-grounded、ASR 回环、内容哈希幂等 | 教学对「字错/公式错/法条错」零容忍，而这恰是生成式视频模型最不擅长的 |

### 0.2 与「第一版方案」的 9 处关键修正

| # | 第一版说法 | 实测事实 | 修正 |
|---|---|---|---|
| 1 | 「PostgreSQL 存元数据」 | 系统是 **SQLite WAL**（`backend/data/question_bank.db`，183.6 MB） | 元数据留 SQLite；不引入 PostgreSQL |
| 2 | 「MongoDB 存脚本」 | Mongo **未运行**（Docker 未起），F4 Mongo 适配器仅 fake HTTP 单测 | 脚本存 SQLite 表 + F4 文档投影（local），Mongo 留开关 |
| 3 | 「Neo4j 承载 Graph-RAG」 | Neo4j **未运行**，F5 Neo4j 适配器同样仅 fake 测试 | 运行时走 GraphStore local，Neo4j 仅可选后端 |
| 4 | 「Milvus 存视频片段向量」 | Milvus **未装未运行**，`VECTOR_BACKEND=off`、`EMBEDDING_ENABLED=false`；DeepSeek 官方无 `/embeddings` | 向量列为 **P2 条件项**，先接 BGE-M3/第三方 embedding |
| 5 | 「LongCat-Video-Avatar 13.6B DiT」 | 本机 **8151 MiB**，Blackwell(sm_120) 需 cu128+，现有 torch 2.13.0+cpu | 13.6B 数字人**本地不可行**；云端 API 或租卡，本地降级轻量模型 |
| 6 | 「MinIO 存视频」 | MinIO 需 Docker，**未运行**；F3 默认 local | P1 用 local 对象存储（同 `ObjectStore` 接口），上线只改配置 |
| 7 | 隐含「图谱现成可用」 | 只有 **2 层**（91 + 427），缺考点层与法条层；F5 **无增量事件** | 必须先做**考点层扩展**，否则「讲考点」无处可挂 |
| 8 | 「llm-wiki-canvas / Qoderian / Mappy 插件」 | `AI讲师知识库` **无 `.obsidian` 目录**，插件全未装 | 改为「Markdown + Canvas JSON + MCP + 脚本」，插件仅可选增强 |
| 9 | 「用 Manim 渲染板书」 | Manim 需 LaTeX + 独立 venv，Python 3.13 兼容未验证，CPU 单页数十秒 | 板书默认 **HTML/SVG 确定性渲染**，Manim 仅用于公式推导专项页 |

### 0.3 对现有代码的改动性质

- **零破坏性改动**：不迁移 `static/` 4.3 GB、不动 `uploads/`、不改 343 个既有端点、不动 `.vtj/vue/*.vue` 的 `<template>`（R3）。
- **新增为主**：新增表（事实源）、新增服务模块、新增独立 venv worker、新增管理端端点、新增学生端播放组件。
- **复用为纲**：上传走 `/api/video/upload*`，存储走 F3 `media_service`，脚本落 F4，关系落 F5，挂载走 `study_material.video_id`。

---

## 1. 现状实测基线（本机只读命令，2026-11-03）

### 1.1 数据与代码

| 项 | 实测值 | 对方案的含义 |
|---|---|---|
| 数据库 | SQLite WAL，`backend/data/question_bank.db`，183.6 MB | 事实源唯一，投影可重建 |
| `study_material` | **0 行** | 备考资料为空模块，改造无历史包袱 |
| `video_resource` / `video_watch_record` | **0 行 / 0 行** | 视频链路从未投产，可安全扩展 |
| `knowledge_point` | 1049 行，`status=1` 518 行 | 531 行草稿/停用需在编译期过滤 |
| 图谱层级 | level=2 共 91、level=3 共 427，143 节点有子，0 孤儿 | **只有 2 层**，缺考点/法条层 |
| `question_knowledge` | 2924 行 | 可反推考点热度与题量 |
| `question_bank.video_url` 非空 | 0 行 | 旧「题目绑视频」字段无人使用 |
| 后端 | 单一 FastAPI 单体，37 个模块，**343 端点冻结**（R11） | 新端点须登记进 `api_surface.json` 比对 |
| 前端 | VTJ 低代码，75 页 = PC 61/平板 7/手机 7；**47/50 为 raw 手写页** | raw 页禁 `vtj_sync_vue_to_dsl` |

### 1.2 已有基础设施（必须复用）

| 层 | 组件 | 现状 | 本模块用法 |
|---|---|---|---|
| F3 对象存储 | `media_assets` + `ObjectStore`（local/MinIO）+ `/media/{asset_id}` | ✅ 已上线；ETag=sha256、Range 206/304/416、immutable | 存 MP4/HLS/封面/板书帧，**不新建文件服务** |
| F4 文档投影 | `DocumentStore`（local/Mongo），3 集合 | ✅ 已上线，`DOC_STORE_ENABLED=true` | 存讲解脚本 JSON、分镜时间轴、字幕 |
| F5 图投影 | `GraphStore`（local SQLite 表/Neo4j HTTP） | ✅ 已上线；3823 节点/4354 边；**无增量事件** | Graph-RAG 检索；需扩节点/边类型 |
| F6 向量投影 | `VectorStore` + `EmbeddingPort` | ⚠️ 框架已上线，**默认关闭** | P2 条件启用 |
| 视频 API | `backend/app/api/v1/library/videos.py`（444 行，prefix `/api/video`） | 上传/分片/流式/Range 全有 | 直接复用 |
| 资料模型 | `StudyMaterial`（`models.py:1375`） | 已有 `type=video_intro/video_advanced`、`video_id`、`content_hash` | 挂载关系现成 |
| 管理端页 | `.vtj/vue/admin_materials.vue` | 已有视频类型、分片上传、`state.form.video_id` | 加「生成任务」面板 |
| 学生端页 | `study_materials.vue` / `materials_xingce/shenlun/gongzhuan.vue` | 已按科目分页 | 加播放器与「跳到考点」 |
| 重活隔离先例 | `ocr_worker.py` 独立子进程 + `_ocr_python()` 解析解释器 | ✅ 生产验证 | **视频 worker 完全照抄** |
| LLM 端口 | `llm_client.py`（OpenAI 兼容，DeepSeek 默认） | ✅ 可用；无 embedding | 脚本生成、审校两处调用 |
| Obsidian 桥 | `obsidian_export.py`（251 行）/ `obsidian_sync.py`（170 行） | ✅ 单向导出 + frontmatter 审核回写 | 复用 `_safe_path` 与状态机 |

### 1.3 硬约束（决定方案的形状）

| 约束 | 实测 | 直接后果 |
|---|---|---|
| GPU | RTX 5060 Laptop，**8151 MiB**，driver 610.62 | 13.6B DiT 数字人本地不可行；≤2B 级口型模型可试 |
| PyTorch | **2.13.0+cpu**，`cuda.is_available()=False` | 任何 GPU 模型须**独立 venv + cu128**，不污染主环境 |
| Python | **3.13.5** | 多数 TTS/数字人仓库要 ≤3.12 → worker venv 锁 3.11/3.12 |
| 磁盘 | D: 剩 **35 GB**（88% 已用）；C: 剩 84 GB | 成品上 D 盘受控目录，中间产物落 C 盘并自动清理 |
| Docker | **daemon 未运行** | Mongo/Neo4j/Milvus/MinIO 当前全部不可用 |
| 前端 | `.vtj` 页面 template 仅用户在设计器可改（R3） | 新增 UI 需 `vtj_create_page_scaffold` + 用户拖拽，AI 只写 script |
| 门禁 | 9 层，历史 8/10（L2/L4 既有 FAIL） | 新功能验收须给 L7 专项项，不能靠全量门禁绿 |

---

## 2. 角色定位：AI 名师是「图谱导览员」，不是「复读机」也不是「答题器」

### 2.1 三个角色边界

| 角色 | 做什么 | 不做什么 |
|---|---|---|
| **AI 名师（本模块）** | 按图谱路径，把「前置知识 → 本考点 → 命题形式 → 易错归因 → 迁移」讲成 3–25 分钟结构化视频 | 不实时答疑、不批改、不押题、不预测分数 |
| **联考小智（既有 `agent_router.py`）** | 多轮对话、选岗建议、面试教练、心理疏导 | 不生产长视频，不承担「讲透一个考点」 |
| **教研员（人）** | 定义考点、写讲义、审脚本、签字放行 | 不做渲染与剪辑 |

**这条边界的意义**：把「内容对不对」与「视频像不像课」拆成两件事。教研员负责前者，AI 负责后者。一旦让模型自己决定讲什么，法条适用与程序步骤上就会出不可控错误——这是公安联考最不能接受的。

### 2.2 讲解的固定五段式（叙事骨架，写进 Prompt 契约）

| 段 | 时长 | 数据来源 | 内容 |
|---|---|---|---|
| ① 定位 | 30s | `question_knowledge` 反查题量 + 考点层级 | 考纲位置、历年题量占比、必考/常考/冷门 |
| ② 前提 | 1–2min | 图上 `PREREQUISITE_OF` 上游节点 | 缺前置则先插 60 秒微课补丁 |
| ③ 拆解 | 3–6min | `knowledge_point.description` + 教研讲义 | 概念→构成要件→程序步骤→适用条件（公专）；题型→解法→速算（行测） |
| ④ 命题 | 2–3min | 真实真题（`question_knowledge` 抽样） | 题干关键词 → 考点 → 陷阱设计 |
| ⑤ 归因 | 1–2min | 真实错题高频错因 | 给「三步自检清单」，可迁移 |

### 2.3 三档讲解模式（按重要性自动分配，不做一律长视频）

| 档位 | 时长 | 触发条件 | 生产成本 |
|---|---|---|---|
| 微课 S | 3–5 min | 冷门考点 / 前置补丁 | 全自动，无数字人 |
| 标准课 M | 8–12 min | `question_knowledge` 关联真题 ≥ 5 的主干考点 | 全自动 + 人工审脚本 |
| 精讲课 L | 15–25 min | 高频必考 + 法条适用类 | 数字人或真人录屏 + 强制人工审片 |

分档规则放 `config/video_tier_policy.json`，不做硬编码，便于教研调整。

---

## 3. 总体架构

```
┌────────────────── 生产面（人类可读、可 diff、可回滚）──────────────────┐
│  Obsidian「AI讲师知识库」                                              │
│   raw/ 只读语料   wiki/ 双链讲义   atlas/ Canvas 图谱视图   output/ 导出 │
│        │ 教研员编辑 + MCP 读写 + Git 提交                                │
│        ▼                                                                │
│  compile_vault.py ─► 契约校验（字段/双链/白名单）─► 变更集 JSON          │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ 只放行「审核通过」的变更集
                                ▼
┌────────────────── 运行面（学生端只读，永不读 Markdown）─────────────────┐
│  SoT: SQLite（knowledge_point / video_resource / study_material / 新表） │
│    ├─ F4 文档投影：脚本 JSON、分镜时间轴、字幕                           │
│    ├─ F5 图投影：考纲图 + 教学图 +（公专）法条适用图                     │
│    ├─ F3 对象存储：MP4/HLS/封面/板书帧 → /media/{asset_id}              │
│    └─ F6 向量投影（P2 条件）：脚本切片语义检索                           │
│                                                                          │
│  视频生产：独立 venv worker 子进程（7 工位流水线）→ 产物入 F3 → 状态回写 │
│  消费端：管理员端（导入/审核/发布）→ 学生端（播放/跳考点/进度）           │
└──────────────────────────────────────────────────────────────────────────┘
```

四条不可逾越的线：

1. **学生端永不读文件系统里的 Markdown**——只读数据库与 API。
2. **模型永不直接写生产库**——所有写入经「变更集 + 审核 + 事务」。
3. **视频画面永不由生成式模型逐帧决定**——教学页一律确定性渲染。
4. **重模型永不进 FastAPI 主进程**——一律独立 venv 子进程（照抄 `ocr_worker.py`）。

---

## 4. 知识底座：Obsidian「AI讲师知识库」怎么搭

### 4.1 结论：搭，且必须搭；但它不是「后备知识库」，是「编辑工厂」

第一版方案把它叫「后备知识库」，容易误解成运行时检索源。正确的定位是：**Obsidian = 教研员的工作台与版本库；题库系统 = 唯一运行时分发源**。

| 维度 | Obsidian 库 | 题库系统 |
|---|---|---|
| 读者 | 教研员、审校、编写者 | 学生、教师、管理员 |
| 格式 | Markdown + 双链 + Canvas | 关系表 + JSON 文档 + 图 |
| 变更 | 人审 + Git | 事务 + Outbox |
| 失败影响 | 只影响下一次编译 | 影响线上学生 |
| 检索 | 全文/双链（人工） | Graph-RAG + 向量（机器） |

**为什么必须建**：考点讲义、法条解读、错因归因这类内容，本质是「专家长期迭代的文本资产」。用后台富文本编辑会丢失版本、diff、双链与批量重构能力；而 AI 生成的内容如果没有人审入口，就会变成不可控的噪音源。Obsidian + Git 是当前唯一「低成本 + 可审 + 可回滚」的组合。

**为什么不直接用**：Markdown 不是事务型存储，双链没有引用完整性，文件系统没有并发控制，学生端读取需要额外服务。所以只做「编译源」。

### 4.2 四个知识库的定位差异（为什么不共用一个）

| 库 | 领域 | 主要读者 | 更新节奏 | 与生产系统的关系 |
|---|---|---|---|---|
| 每日金句知识库 | 素材/文案 | 运营 | 每日 | 与生产弱耦合，人工搬运 |
| 联考小智知识库 | 对话问答（RAG 语料） | 小智 Agent | 每周 | 通过 API 检索，语料型 |
| 论坛舆情监测 AI 知识库 | 舆情规则/话术 | 运营 + 风控 | 事件驱动 | 规则型，与人审联动 |
| **AI讲师知识库（新建）** | 教法/讲义/分镜 | 教研员 | 随考纲 + 随视频 | **编译型：产出机器可读的讲解契约** |

共用一个库会出事：目录语义冲突、审核节奏互相拖累、检索时互相污染、token 预算无法分账。因此**新建独立库**，只复制「联考小智」的骨架约定（AGENTS.md / index.md / log.md / wiki 双链 / templates），不复制其内容。

### 4.3 目录结构（在 `D:\Obsidian仓库\AI讲师知识库` 落地）

```
AI讲师知识库/
├── AGENTS.md                  # 库内铁律：一次只做一件事、只改 wiki/ 不改 raw/、每次改动追加 log
├── index.md                   # 分区索引 + 最近更新表（人工与脚本共用入口）
├── log.md                     # 变更日志（人与脚本都追加，格式统一）
├── config/
│   ├── rules/                 # 讲解宪法.md、法条引用规范.md、避错清单.md
│   ├── templates/             # 讲义模板、脚本模板、考点卡模板
│   └── schema/
│       ├── frontmatter.schema.json    # 编译期强校验的字段契约
│       └── tag-taxonomy.json          # 受控标签表（科目/模块/题型/难度）
├── raw/                       # 只读原始语料（考纲 PDF、教材摘录、真题解析、法条原文）
│   ├── 考纲/  教材/  真题/  法条/  政策/
│   └── _README.md             # 说明：raw 永不手改，改则新版本入 raw/_inbox
├── wiki/                      # 唯一可编辑区（双链 + YAML frontmatter）
│   ├── 行测/  申论/  公专/
│   ├── 考点/                  # 一考点一文件，文件名=考点名，含 exam_point_id
│   ├── 法条/                  # 公专法条卡（条文号 → 适用条件 → 常见误用）
│   ├── 错因/                  # 错因卡（现象 → 根因 → 自检步骤）
│   └── 讲义/                  # 逐页讲解稿（含分镜标记）
├── atlas/                     # Canvas 图谱视图（程序生成 + 人工微调）
│   ├── 考纲全景.canvas
│   ├── 行测-判断推理.canvas
│   └── 公专-执法程序.canvas
├── output/                    # 编译产物（只读，脚本写）
│   ├── changesets/            # 变更集 JSON（待系统审核）
│   ├── reports/               # 校验报告（断链/缺字段/越权标签）
│   └── manifests/             # 每个视频的脚本 + 时间轴 + 字幕清单
└── scripts/
    ├── compile_vault.py       # 库 → 变更集（核心）
    ├── lint_vault.py          # 断链/字段/标签/命名校验
    ├── build_canvas.py        # 图 → .canvas（可视化）
    └── daily-update.sh        # 串联：lint → compile → build_canvas → 刷新 index
```

### 4.4 Frontmatter 契约（编译期强校验，字段缺失即拒收）

```yaml
---
id: GK-FL-ZCXZ-001            # 全局唯一，前缀=科目-模块，系统侧主键映射
type: exam_point              # exam_point | law_article | error_pattern | lesson
subject: gongzhuan            # xingce | shenlun | gongzhuan
module: 执法程序
title: 盘查与继续盘问的适用边界
level: 考点                    # 知识点 | 考点 | 原子要点
parent_point_id: 1024         # 必须命中 knowledge_point.point_id（status=1）
prerequisites: [1001, 1007]   # 前置知识，必须存在且无环
law_refs: ["人民警察法 §9", "公安机关办理行政案件程序规定 §62"]
tier: M                       # S | M | L（讲解档位）
difficulty: 3
exam_freq: high               # high | medium | low
video_id: null                # 已产出视频时回填
status: draft                 # draft | review | approved | archived
reviewer: null
reviewed_at: null
source_hash: sha256:...       # 源语料指纹，语料变更则强制复审
tags: [考点/公安执法, 题型/情境判断]
---
```

**契约的三条硬规则**：

1. `status: approved` 才允许进变更集；`draft/review` 一律编译为「待审」，不落生产。
2. `parent_point_id` 必须存在于 `knowledge_point` 且 `status=1`，否则该文件在报告中标红并跳过（不阻塞其他文件的编译）。
3. `source_hash` 变化 → 关联视频自动标记「需重制」，进管理员端待办，不自动重生成（避免成本失控）。

### 4.5 自生长闭环（7 步，脚本化的「编排」而不是「玄学」）

| 步 | 脚本 | 输入 | 输出 | 失败处理 |
|---|---|---|---|---|
| 1 fetch | `scripts/fetch.py` | 考纲更新、教材新版、新真题 | `raw/_inbox` 新文件 | 记录来源与时间，不自动改写 raw |
| 2 lint | `lint_vault.py` | `wiki/` 全量 | 断链/缺字段/越权标签报告 | 报告落 `output/reports`，CI 式失败不阻塞人工编辑 |
| 3 gap | `gap_analysis.py` | 图谱覆盖 + 题量分布 | 「高题量但无讲义」的考点清单 | 生成待办笔记进 `wiki/_inbox` |
| 4 compile | `compile_vault.py` | `wiki/` + `atlas/` | `output/changesets/*.json` | 单文件失败隔离，其余继续 |
| 5 review | 管理员端「知识变更审核」 | 变更集 | 入库/驳回 + 驳回理由 | 驳回写回库内 `log.md` |
| 6 build | `build_canvas.py` | 库内双链 | `atlas/*.canvas` | 图过大则按模块拆分 |
| 7 index | `update_index.py` | 全库 | `index.md` + `log.md` | 幂等重写，防手工冲突 |

**「自生长」的准确含义**：脚本替人做「发现缺口、生成骨架、校验、画图、记账」这五件机械活；**「写内容」与「签字」永远是人**。这样既能持续长，又不会长出胡说八道。

### 4.6 编译契约（库 → 系统，唯一通道）

```
wiki/*.md  ──parse──►  NoteIR{id,type,fields,links,body}
                        │
                        ├─ 校验：schema / 双链 / parent_point_id 存在 / 标签受控
                        ├─ 归一：法条号标准化（"§9" → "第九条"）、别名合并（knowledge_point.alias_of）
                        └─ 产出：changeset{add:[], update:[], archive:[], needs_video:[]}
                                     │
                                     ▼
                        POST /api/v1/knowledge/changesets（管理员，幂等键 = changeset_id）
                                     │
                        ┌────────────┴─────────────┐
                        ▼                          ▼
                  SQLite 事务写入            F4 文档快照 + F5 图边
                  （事实源，一次提交）        （投影，可重建）
```

要点：

- **幂等**：`changeset_id = sha256(排序后的变更内容)`，重复提交直接返回 `applied=false`。
- **原子**：全部变更在一个 SQLite 事务里，失败整体回滚，不出现半套图谱。
- **可追**：每条变更记录 `source_doc_path` 与 `source_hash`，可从系统反查「这句话来自哪篇笔记的哪个版本」。

---

## 5. 知识图谱：建在题库系统，且一模块多张图

### 5.1 结论与理由

| 候选方案 | 判定 | 理由 |
|---|---|---|
| 建在 Obsidian（双链即图） | ❌ 不能作运行时 | 双链无类型、无方向语义、无查询语言、无索引；学生端无法低延迟遍历 |
| 建在题库系统 `GraphStore` | ✅ 采纳 | F5 已建成（3823 节点/4354 边）；有 `PREREQUISITE_OF/PARALLEL_WITH/INSTANCE_OF` 语义；进程内调用；可切 Neo4j |
| 两边各建一套 | ❌ 双写必分裂 | 以 Obsidian 为「意图」、系统为「事实」，单向编译，不做双向同步 |

**一模块多张图**用「图族（graph_key）+ 命名空间」实现，而不是建多个数据库：节点与边都带 `graph_key`，查询必带该字段，天然隔离。

### 5.2 三个图族

| 图族 | graph_key | 节点 | 边 | 服务对象 |
|---|---|---|---|---|
| 考纲图 | `syllabus` | 科目 → 模块 → 知识点 → 考点 → 原子要点 | `HAS_CHILD`、`PREREQUISITE_OF`、`PARALLEL_WITH`、`ALIAS_OF` | 全站（组卷、推荐、统计） |
| 教学图 | `pedagogy` | 考点、视频、讲义、错因卡 | `EXPLAINS`(video→考点)、`DERIVED_FROM`(视频→讲义版本)、`REMEDIES`(错因→考点) | 本模块（视频挂载与推荐） |
| 法条适用图 | `law` | 法条、构成要件、执法场景、程序步骤 | `APPLIES_TO`、`REQUIRES`、`CONFLICTS_WITH` | 公专（法理推导的正确性约束） |

法条图是本方案相对第一版的新增项：公专最大的错误不是「讲不清」，而是「法条张冠李戴」。把「场景 → 法条 → 适用条件」显式化后，脚本生成阶段可以强制要求「每个结论必须能落到某条 `APPLIES_TO` 边上」。

### 5.3 图谱扩展（P2 的前置工程，必须先做）

现状只有 `level=2`（91）与 `level=3`（427）两层，即「模块 → 知识点」。要讲「考点」，需要：

| 步骤 | 动作 | 数据变更 | 影响面 |
|---|---|---|---|
| E1 | 考点层落地 | `knowledge_point` 新增 `level=4` 行（考点），`parent_id` 指向 level=3 | 只增不改；既有 518 行不动 |
| E2 | 原子要点层 | `level=5`（构成要件/程序步骤/易错点），仅公专与行测高频模块先做 | 同上 |
| E3 | 别名合并 | 复用既有 `alias_of`，把「同一考点不同叫法」指向主节点 | 更新 `alias_of`，不删行 |
| E4 | 图节点类型扩展 | `GraphStore` 节点新增 `ExamPoint/Video/LawArticle/ErrorPattern` | 迁移新增枚举值，向后兼容 |
| E5 | 边类型扩展 | `EXPLAINS / DERIVED_FROM / REMEDIES / APPLIES_TO` | 新增边表记录，旧查询不受影响 |
| E6 | 增量投影 | 给 `backfill_graph.py` 加 `--since` 模式，或接 Outbox 事件 | 解决 F5「无增量事件」的运维痛点 |

E1–E3 是**数据治理**，E4–E6 是**代码**。建议 E1 用脚本从现有 `knowledge_point` 的 `description` 与真题解析中半自动抽取考点名，再由教研确认——避免一次性人工录入几百条。

### 5.4 Graph-RAG 检索模板（讲一个考点前，先固定取这六样）

```
输入: exam_point_id
1) 自身      : 节点 + description + 法条引用
2) 前置链    : PREREQUISITE_OF 反向遍历 ≤3 层（GRAPH_QUERY_MAX_DEPTH=5 内）
3) 同层兄弟  : PARALLEL_WITH（用于「易混淆对比」段落）
4) 真题样本  : INSTANCE_OF 入边，按 question_knowledge 频次取 Top 8
5) 错因      : REMEDIES 边指向的 ErrorPattern
6) 既有视频  : EXPLAINS 入边（避免重复生产，命中则走「更新」而非「新建」）
```

这六样构成脚本生成的**唯一事实输入**，Prompt 里明确写「不得引入上述之外的事实」。这是防幻觉的第一道闸。

---

## 6. 视频生产引擎：7 个工位 + 2 个 LLM 调用点

### 6.1 流水线状态机（可断点、可重跑、可审计）

```
QUEUED → SCRIPTING → SCRIPT_REVIEW → BOARD_RENDER → TTS → AVATAR → COMPOSE → QC → READY
   │         │            │              │          │       │        │      │
   └─────────┴────────────┴──────────────┴──────────┴───────┴────────┴──────┴─► FAILED（带 stage + 原因）
                                    ↑ 任一步可 retry，从该 stage 续跑，不重做前序
```

每个 stage 的产物都落盘并带内容哈希，重跑时哈希一致则跳过。这是「稳定」二字的工程含义：**失败不需要从头再来**。

### 6.2 七个工位

| # | 工位 | 输入 | 输出 | 技术 | 是否调 LLM |
|---|---|---|---|---|---|
| 1 | 脚本工位 | Graph-RAG 六件套 JSON | 分镜脚本 `script.json`（每页：标题/要点/图示/旁白/时长/引用节点 ID） | `llm_client.py` + 结构化输出校验 | ✅ 唯一内容生成点 |
| 2 | 审校工位 | `script.json` + 法条与教材片段 | `review.json`（逐条通过/驳回 + 依据） | 同一 LLM，第二遍「挑错」提示词 | ✅ 唯一质检点 |
| 3 | 板书工位 | `script.json` 的 page 数组 | 每页 PNG（1920×1080） | HTML 模板 → 无头浏览器截图；公式页 SVG；降级 Pillow | ❌ 确定性 |
| 4 | 配音工位 | 旁白文本 + 发音词典 | WAV（44.1kHz）+ `timing.json`（逐句起止） | 基线：Edge-TTS；进阶梯：GPT-SoVITS / VoxCPM | ❌ |
| 5 | 口型工位 | WAV + 主讲形象 | 口型片段（可选） | MuseTalk / 轻量 viseme 驱动；不可用则跳过 | ❌ |
| 6 | 合成工位 | 板书画帧 + 音轨 + 字幕 | MP4（H.264/AAC）→ HLS 分片 | `ffmpeg`（已验证 7.0.2） | ❌ |
| 7 | 质检工位 | 成片音轨 | `qc.json`（ASR 回环差异率、静音段、时长偏差） | whisper.cpp（CPU 可跑） | ❌ |

**为什么只有 2 个 LLM 调用点**：工位 1 决定「说什么」，工位 2 决定「对不对」，其余全是确定性程序。这样每次生成的成本可算（约 2 次长上下文调用），结果可复现（同输入同输出），bug 可定位（哪一步坏了修哪一步）。

### 6.3 进程与依赖隔离（照抄 `ocr_worker.py` 的成熟模式）

| 层 | 位置 | 依赖 | 主进程是否 import |
|---|---|---|---|
| 主进程 | `backend/app/services/video/*.py` | 标准库 + `llm_client` + `media_service` | — |
| 渲染 worker | `backend/workers/render/`，独立 venv（Python 3.11） | `playwright` 或 `imgkit` + Pillow | ❌ 绝不 |
| 语音 worker | `backend/workers/tts/`，独立 venv | `edge-tts` / `GPT-SoVITS` | ❌ 绝不 |
| 口型 worker | `backend/workers/avatar/`，独立 venv（cu128） | `torch` + `MuseTalk` | ❌ 绝不 |
| 合成 | 主进程直接调 `ffmpeg` 子进程 | 无 | — |

解释器解析复用 `ocr_pipeline._ocr_python()` 的思路，新增 `VIDEO_TTS_PYTHON / VIDEO_RENDER_PYTHON / VIDEO_AVATAR_PYTHON` 三个配置项，缺省回退 `sys.executable`。worker 之间只通过「文件 + JSON」通信，超时由父进程强杀，日志落 `backend/data/logs/video/`。

**这条设计的价值**：模型装坏了、CUDA 崩了、显存不够，都只影响一个子进程；FastAPI 主进程与全站服务不受牵连。

### 6.4 画面：确定性渲染优先（本方案最关键的技术主张）

| 方案 | 适用 | 优点 | 风险 |
|---|---|---|---|
| **HTML/CSS 模板 → 截图**（首选） | 95% 讲解页 | 字体可控、可 diff、可 A/B、渲染 1 秒/页 | 需装无头浏览器（P0 实测项） |
| SVG 程序生成 | 流程图、程序步骤、关系图 | 矢量清晰、体积极小 | 复杂排版成本高 |
| Pillow 直接绘制 | 降级兜底 | 零额外依赖 | 排版能力弱 |
| Manim | 公式推导专项 | 动画强 | LaTeX + 独立 venv，CPU 慢 |
| 生成式视频模型（文生视频） | 仅片头 3–5 秒、情境动画 | 氛围好 | **文字必错**，绝不用于教学页 |

设计规范（写进模板，不靠模型自觉）：

- 版式：1920×1080，安全区左右各 96px；标题 56px / 正文 36px / 注释 28px；行高 1.6。
- 单页字数 ≤ 90 字（超过则强制拆页，脚本工位负责）。
- 关键词高亮用色 ≤ 3，深色底 + 高对比文字（对比度 ≥ 4.5:1）。
- 法条引用区固定右下角，格式统一为「《法名》第 N 条」。
- 每页右下角水印「砺安题库 · AI 名师」+ 考点 ID，便于溯源。

### 6.5 语音：清晰与多音字是两件事

| 问题 | 对策 |
|---|---|
| 吐字清晰 | 语速 4.2–4.6 字/秒；句间留白 200–300ms；响度统一到 −16 LUFS（ffmpeg `loudnorm`） |
| 多音字（「行」测、「重」复） | 维护 `pronunciation.json` 词典，脚本阶段就把易错词替换为 SSML/拼音标注 |
| 断句歧义 | 脚本里用显式标点与 `<break>` 标注，不让 TTS 自行判断 |
| 音色一致性 | P1 用固定音色；P3 才做克隆，且必须版权授权 |
| 质量验证 | ASR 回环：合成后识别，与原文比对，字错率 > 2% 或关键术语错 → 打回工位 4 |

### 6.6 数字人：三级降级，永不阻断

| 级别 | 形态 | 硬件需求 | 触发 |
|---|---|---|---|
| L0 旗舰 | 13.6B 级 DiT 数字人 | 24GB+ 显存或云端 | **本机不可行**，仅云端 API 方案 |
| L1 标准 | MuseTalk 类口型同步（半身） | ~8GB 显存（需 P0 实测） | 显存足够且 CUDA 环境就绪 |
| L2 轻量 | 静态主讲形象 + 口型微动/呼吸动效 | CPU 可跑 | L1 失败或未装 |
| L3 兜底 | PPT/板书 + 画外音（无人像） | CPU | 一切异常 |

**默认走 L3，L1 是增强而非依赖**。理由：本机 8GB 显存 + Blackwell 架构 + Python 3.13 + CPU torch，任何一环都能让数字人链路当天跑不起来；而教学内容的价值 99% 在「讲清楚」，不在「有人脸」。

### 6.7 合成与分发

- 编码：H.264 High / AAC 128k；720p 为主，1080p 仅精讲课。
- 封装：MP4（源）+ HLS fMP4 分片（分发，6 秒一片）。
- 字幕：WebVTT 软字幕（可检索、可翻译），不烧录；板书页已含文字，烧录意义不大。
- 封面：自动取第 2 页 + 标题合成，1920×1080，走 F3 `kind=image`。
- 产物入 F3：`media_service.store_file` 返回 `asset_id`，签名/权限统一由 `/media/{asset_id}` 承担。

### 6.8 选型矩阵（状态标注，避免「写了但跑不起来」）

| 能力 | 候选 | 本机状态 | 备注 |
|---|---|---|---|
| 编排/调度 | 自研 Python 工位 + 状态表 | ✅ 可立即做 | 不引入 Airflow/Celery（单机、无 Redis 保障） |
| 脚本生成 | `llm_client.py`（DeepSeek） | ✅ 可用 | 结构化 JSON + 校验重试 |
| 板书渲染 | HTML + 无头浏览器 | ⚠️ P0 实测 | 装 `playwright` 后测 1 页耗时 |
| 板书降级 | Pillow / SVG | ✅ 可用 | 无浏览器时的兜底 |
| 公式动画 | Manim（CPU） | ⚠️ 未验证 Python 3.13 | 仅精讲课少量页 |
| TTS 基线 | Edge-TTS | ⚠️ 需联网实测 | 免费、无 GPU、中文自然度可接受 |
| TTS 进阶梯 | GPT-SoVITS / VoxCPM | ⚠️ 独立 venv + 8GB 显存 | 需版权授权与音色备案 |
| 口型 | MuseTalk 类 | ⚠️ 需 cu128 轮子 | 8GB 显存边界，P0 出结论 |
| 口型旗舰 | LongCat-Video-Avatar 13.6B | ❌ 本机不可行 | 仅云端/租卡 |
| 合成 | `ffmpeg` 7.0.2 | ✅ 已验证 | 并行渲染 + 硬切 |
| ASR 质检 | whisper.cpp（CPU） | ⚠️ 需下载模型 | 中文 small/medium 模型 ~500MB–1.5GB |
| 对象存储 | F3 local / MinIO | ✅ local / ❌ MinIO(Docker 未起) | 同接口切换 |
| 向量检索 | BGE-M3 / 第三方 API + Milvus | ⚠️ 待接入 | P2 条件项 |
| 图查询 | F5 local / Neo4j | ✅ local / ❌ Neo4j(Docker 未起) | 同接口切换 |

**说明**：本表所有 ❌/⚠️ 均来自本机实测（显存、Docker、Python 版本、torch 构建），不是推测；⚠️ 项在 P0 阶段逐项跑基准并出结论，未通过则从方案中删除，不留「写了没跑」的部件。

---

## 7. 五库职责与容量工程（防膨胀是硬指标）

### 7.1 职责划分：一库一职，交叉为零

| 库 | 载体 | 只存 | 绝不存 | 重建方式 |
|---|---|---|---|---|
| 关系库 | SQLite（事实源） | 元数据、状态机、关联、审计、权限 | 大文本、二进制、向量 | 备份恢复（`sqlite3.backup()`） |
| 文档库 | F4（local/Mongo） | 讲解脚本、分镜时间轴、字幕全文、Prompt 快照 | 业务状态（以 SQLite 为准） | 从事件重放/重编译 |
| 向量库 | F6（Milvus/local） | 脚本切片、考点头、真题语义向量 | 原文正文 | 重跑 embedding |
| 图片库 | F3 `kind=image` | 板书帧、封面、示意图、缩略图 | 题图原件（在 `static/` 不动） | 重新渲染 |
| 图库 | F5（local/Neo4j） | 节点、边、图族 | 属性全文 | `backfill_graph.py --reset` |

「图片数据库」在本系统里不是独立服务，而是 F3 的一个 `kind` 维度 + 缩略图规格。这样一套权限、一套 CDN、一套清理策略，避免第五套运维。

### 7.2 容量预算（先算，再定策略）

| 项 | 估算 | 依据 |
|---|---|---|
| 单视频 720p 成品 | 12 min × 1.2 Mbps ≈ **108 MB** | H.264 教学画面（低运动）码率友好 |
| 单视频 1080p 精讲 | 20 min × 2.5 Mbps ≈ **375 MB** | 仅精讲课 |
| 首批 120 个考点 | 100 × 108 MB + 20 × 375 MB ≈ **18 GB** | 三科主干考点 |
| 中间产物峰值 | 板书帧 120×60×0.4 MB ≈ 2.9 GB；音频 120×12 MB ≈ 1.4 GB | 可清理 |
| 三年规模（600 视频） | ≈ **90 GB** | 超出 D 盘剩余 35 GB |

**结论：不设计容量策略，这个功能三个月就会把磁盘吃光。** 因此：

| 策略 | 规则 | 落地 |
|---|---|---|
| 分级存储 | 热（90 天内被播放）/ 冷（更早）/ 归档（下架） | `video_asset_tier` 字段 + 定时任务 |
| 冷数据转码 | 冷数据重编码为 480p（体积约 1/3），保留原片 30 天 | ffmpeg 批量任务，可关 |
| 中间产物 TTL | 板书帧/音频/中间帧 7 天自动删 | 落 C 盘 `%TEMP%/lian_video`，定时清理 |
| 一源多档 | 只保留 HLS 多码率 + MP4 源；不保留逐帧序列 | 合成后立即删帧 |
| 容量闸 | 剩余 < 10 GB 时拒绝新建 L 档任务，只允许 S/M | 任务创建前检查 |
| 去重 | 脚本哈希相同 → 复用资产，不重复渲染 | `script_hash` 唯一索引 |

### 7.3 入库准确性：四道闸

| 闸 | 校验 | 失败动作 |
|---|---|---|
| G1 结构 | 脚本 JSON 必含 `pages[]`，每页必含 `cite:{node_id}` | 拒收，回工位 1 |
| G2 引用 | 每个 `node_id` 必须存在于图投影 | 拒收，标记为幻觉 |
| G3 完整性 | 资产 sha256 与 DB 记录一致；时长差 ≤ 1s | 标记异常，重合成 |
| G4 对账 | 每日核对 `media_assets` ↔ 对象存储实际文件 | 生成差异报告，人工处置 |

### 7.4 数据库防「膨胀损坏」

- **不把视频二进制入库**：任何情况下 `video_resource` 只存 `asset_id`，不存 BLOB（现状已是路径式，继续保持）。
- **大字段外置**：脚本 JSON > 8 KB 时只存 `doc_ref`，正文进 F4（复用 `DOC_STORE_MAX_BYTES=8388608` 的既有阈值思路）。
- **WAL 水位监控**：`-wal` 超过 64 MB 且长期不 checkpoint 时告警（历史上有过 303 MB→46 MB 的 VACUUM 治理）。
- **定期对账 + 季度 VACUUM**：沿用既有 `db_inventory.py` / `content_integrity.py` 工具，纳入 L7 门禁。

---

## 8. 管理员端导入 → 学生端呈现

### 8.1 最小数据模型变更（新增 2 表 + 扩 3 列）

```sql
-- 新表 1：生产任务（事实源）
CREATE TABLE video_production_job (
  job_id        INTEGER PRIMARY KEY AUTOINCREMENT,
  exam_point_id INTEGER NOT NULL,          -- knowledge_point.point_id (level>=4)
  tier          TEXT NOT NULL,             -- S | M | L
  status        TEXT NOT NULL,             -- QUEUED..READY / FAILED / CANCELLED
  stage         TEXT,                      -- 失败时停在哪一步
  script_doc_id TEXT,                      -- F4 文档引用
  script_hash   TEXT,
  video_id      INTEGER,                   -- 成功后关联 video_resource
  attempts      INTEGER DEFAULT 0,
  error_code    TEXT,
  error_msg     TEXT,
  created_by    INTEGER,
  create_time   DATETIME DEFAULT CURRENT_TIMESTAMP,
  update_time   DATETIME
);
CREATE INDEX idx_vpj_status ON video_production_job(status, create_time);
CREATE UNIQUE INDEX uq_vpj_script ON video_production_job(script_hash);

-- 新表 2：视频-考点挂载（事实源，再投影到 F5 的 EXPLAINS 边）
CREATE TABLE video_knowledge_link (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id   INTEGER NOT NULL,
  point_id   INTEGER NOT NULL,
  relation   TEXT NOT NULL DEFAULT 'EXPLAINS',  -- EXPLAINS | REMEDIES
  weight     REAL DEFAULT 1.0,
  create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(video_id, point_id, relation)
);

-- 既有表扩展（只加列，不改语义，0 行数据无回填风险）
ALTER TABLE video_resource ADD COLUMN asset_id TEXT;          -- F3 资产
ALTER TABLE video_resource ADD COLUMN publish_status TEXT DEFAULT 'draft'; -- draft|review|published
ALTER TABLE video_resource ADD COLUMN script_hash TEXT;       -- 幂等与复现
```

对齐既有约束：`study_material.video_id` 继续作为「货架挂载」，`video_resource` 继续作为「资产元数据」，两者不合并（合并会牵动 6 个既有页面）。

### 8.2 API 变更（全部新增，不改既有 343 端点）

| 方法 | 路径 | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/video/jobs` | admin | 为考点创建生产任务（可选 `force` 重做） |
| GET | `/api/video/jobs` | admin | 任务列表（状态/档位/考点/耗时） |
| GET | `/api/video/jobs/{job_id}` | admin | 单任务详情 + 每 stage 产物 |
| POST | `/api/video/jobs/{job_id}/retry` | admin | 从失败 stage 续跑 |
| POST | `/api/video/jobs/{job_id}/cancel` | admin | 取消（子进程强杀） |
| POST | `/api/video/jobs/{job_id}/publish` | admin | 审核通过 → 生成 `study_material` 记录 + 挂架 |
| GET | `/api/video/{video_id}/chapters` | 登录 | 章节/考点时间轴（学生端跳转用） |
| GET | `/api/video/{video_id}/linked-points` | 登录 | 关联考点 + 前置/后继 |
| POST | `/api/knowledge/changesets` | admin | Obsidian 变更集入库（§4.6） |

约束：新端点必须登记到 `backend/data/refactor_baseline/api_surface.json` 的比对清单，并在 L7 加一条「新增端点均在 openapi 中」的守卫（参照既有 `tests/test_router_registration.py` 思路，防「合并丢注册」）。

### 8.3 页面改造（受 R3 约束的落地方式）

| 页面 | 改动 | 谁来做 |
|---|---|---|
| `.vtj/vue/admin_materials.vue` | 加「智能生产」Tab：考点选择、档位、任务队列、预览、发布 | **template 由用户设计器拖拽**；AI 只写 `<script>` 与接口调用，先 `dryRun:true` |
| `.vtj/vue/study_materials.vue` | 卡片加「精讲」角标、播放进度、章节跳转入口 | 同上 |
| 学生端视频播放页 | 若不存在则 `vtj_create_page_scaffold` 新建（建议 id `student_video_player`），再由用户拖拽布局 | 脚手架由 AI 建，布局由用户定 |
| 公共播放组件 | `src/components/video/CoursePlayer.vue`（手写，非 VTJ 页） | AI 可直接写（不在 `.vtj` 内） |

播放器能力：HLS 自适应、倍速、字幕开关、章节锚点跳转、「跳到对应考点练习」按钮（复用既有答题路由）。

### 8.4 审核与发布流

```
教研提交讲义(Obsidian) → 编译变更集 → 管理员审核(入库)
      → 创建生产任务 → 脚本生成 → 审校 → [人工审脚本] → 渲染 → 质检
      → 管理员预览 → 发布(published) → 生成 study_material 记录 → 学生端可见
                                 └─ 驳回：写回原因，任务置 FAILED，可改后重跑
```

权限沿用既有角色模型：`require_admin` 用于生产与发布，教师只读可预览；学生只见 `published`。

---

## 9. Obsidian 可视化治理：CRUD、日志、图形，零插件依赖

### 9.1 增删改查

| 操作 | 方式 | 说明 |
|---|---|---|
| 增 | `obsidian_write` / `obsidian_append` | 从 `config/templates` 复制骨架，自动填 frontmatter |
| 删 | `obsidian_delete`（进 `.trash`） | **不硬删**；或改 `status: archived` 软删 |
| 改 | `obsidian_write` / `obsidian_set_property` | 属性改动走 `set_property`，正文改动走 `write` |
| 查 | `obsidian_search` / `obsidian_list` / `obsidian_backlinks` | 支持按目录、标签、反向链接 |
| 批量 | `obsidian_move`（自动修双链） | 目录重构时用它，不手工 mv |

### 9.2 图形化：用 Canvas 的纯 JSON 格式，程序化生成

Obsidian Canvas 文件（`.canvas`）就是 JSON，无需任何插件即可被 Obsidian 原生打开并拖拽编辑：

```json
{
  "nodes": [
    {"id":"n1","type":"file","file":"wiki/考点/盘查与继续盘问.md","x":0,"y":0,"width":320,"height":200},
    {"id":"n2","type":"text","text":"**执法程序**\n先决条件：表明身份","x":400,"y":0,"width":260,"height":120}
  ],
  "edges": [
    {"id":"e1","fromNode":"n1","fromSide":"right","toNode":"n2","toSide":"left","label":"PREREQUISITE_OF"}
  ]
}
```

`build_canvas.py` 从 `wiki/` 的双链与 F5 图投影导出两种视图：

| 视图 | 来源 | 用途 |
|---|---|---|
| 静态全景 | 目录 + 标签 | 看覆盖度：哪些模块还空 |
| 关系图 | F5 `PREREQUISITE_OF` 等边 | 看结构：是否成环、是否断链 |
| 待办图 | `gap_analysis` 结果 | 看缺口：高题量无讲义 |

这样「可视化」不需要任何社区插件，也不会因为插件停更而失效。

### 9.3 日志：三层，缺一不可

| 层 | 载体 | 内容 | 读者 |
|---|---|---|---|
| 内容日志 | `log.md`（库内） | 谁在何时改了哪篇、为什么改 | 教研员 |
| 版本日志 | Git（库根初始化仓库） | 逐次 diff，可回滚到任意版本 | 教研 + 事故排查 |
| 系统日志 | `foundation_inbox` / 审计表 | 变更集入库记录、视频生产任务状态 | 运维 + 审计 |

补充：若库目录未初始化 Git，P0 阶段执行 `git init` 并加 `.gitignore`（排除 `.trash`、`output/manifests` 大文件），这是「可回滚」的前提，成本接近零。

### 9.4 与 dsh-obsidian 的关系

dsh-obsidian MCP 是**操作通道**（读写搜索移动），不是知识库本身。它的价值在于：让 AI 能在「不打开 Obsidian 客户端」的情况下完成批量建目录、填模板、修断链、生成 Canvas。落盘位置固定为 `D:\Obsidian仓库\AI讲师知识库`，路径必须带子库前缀（vault root 是父目录）。

---

## 10. 创新与长期可靠性（第七问的正面回答）

| # | 机制 | 解决的问题 | 成本 |
|---|---|---|---|
| 1 | **确定性渲染**：教学页由模板+数据生成，不交给视频模型 | 文字/公式/法条幻觉 | 低（一次写模板） |
| 2 | **Citation-grounded 脚本**：每页必须带 `node_id`，图上不存在的句子一律拒收 | 「讲得头头是道但依据不明」 | 低（校验 + 重试 1 次） |
| 3 | **双遍审校**：第二遍只做「找错」，提示词要求逐条给依据 | 单遍生成的系统性偏差 | 中（多一次 LLM 调用） |
| 4 | **ASR 回环**：成片反识别比原文 | 多音字、吞字、断句错 | 低（CPU 可跑） |
| 5 | **内容哈希幂等**：脚本哈希相同即复用，视频版本可回退 | 重复生成、不可复现 | 低 |
| 6 | **三级降级 + 断点续跑** | 单点失败导致整批停摆 | 低（状态机已有） |
| 7 | **黄金集回归**：20 个固定考点作基准，改提示词后跑 diff | 模型/Prompt 升级导致质量漂移 | 中（一次性建集） |
| 8 | **容量闸 + 生命周期** | 磁盘被吃光、库膨胀 | 低（配置 + 定时任务） |
| 9 | **三态 UI**：空/加载/失败均有明确呈现，失败给「为什么 + 怎么办」 | 学生端白屏、管理员端无反馈 | 低 |
| 10 | **变更集 + 双日志** | 「谁把这条改坏了」无法追溯 | 中（一次建管道） |

**长期稳定性的关键判断**：这个模块最大的风险不是「模型不够强」，而是「依赖太多跑不起来」和「内容没人维护」。所以方案把 80% 的工程量放在「隔离、降级、校验、可追溯」上，把模型放在一个很小、很确定的位置。

---

## 11. 分期实施与可量化验收

| 阶段 | 内容 | 工期 | 验收（全部可测） |
|---|---|---|---|
| **P0 基准** | 20 个黄金考点；三条链路实测（HTML 截图 / Edge-TTS / MuseTalk）；容量与耗时基准；库根 git init | 3–5 天 | 出 `docs/ops/AI视频链路基准报告.md`：单页渲染耗时、单分钟配音耗时、口型是否可跑、单视频总成本（分钟/元） |
| **P1 最小闭环** | Obsidian 库骨架（§4.3）；编译管线；工位 1/3/4/6；管理员任务列表 + 发布；学生端播放 | 2–3 周 | 3 个考点端到端出片；学生端可播、可跳章节；任务失败可 retry；L7 新增 4 项门禁通过 |
| **P2 图谱与审校** | 考点层 E1–E3；图族与边扩展 E4–E5；工位 2 审校；ASR 回归；变更集入库 | 3–4 周 | 120 个考点有节点；幻觉拦截率 ≥ 95%（黄金集）；变更集入库可回滚 |
| **P3 语音与形象** | 音色克隆（需授权）；MuseTalk 接入；L1 降级链 | 3–4 周（条件） | 口型链路在 8GB 显存下稳定跑通 10 条不崩；否则正式放弃并写入报告 |
| **P4 规模化与可视化** | Canvas 生成；看板；冷热分层；批量生产 | 2–3 周 | 单日可产 10 条；磁盘占用受控；管理员端有生产看板 |

**里程碑不可跳**：P1 不通过不进 P2；P3 是条件项，允许整体取消而不影响主线。

---

## 12. 风险与回滚

| 风险 | 概率 | 影响 | 对策 | 回滚 |
|---|---|---|---|---|
| 无头浏览器渲染不稳定/装不上 | 中 | P1 主线受阻 | 立即切 Pillow/SVG 渲染，版式降级 | 模板层切换，无数据影响 |
| Edge-TTS 网络不可用 | 中 | 无配音 | 切本地 TTS（Piper 等轻量模型） | 配置切换 |
| 8GB 显存跑不动口型 | 高 | P3 失败 | 直接 L2/L3，不投入 | 放弃 P3，成本已隔离 |
| 磁盘不足（35 GB） | 高 | 生产中断 | 容量闸 + 冷数据转码 + 中间产物 TTL | 清理任务 + 下架冷视频 |
| LLM 幻觉进脚本 | 中 | 内容错误 | Citation 校验 + 双遍审校 + 人工审脚本 | 任务置 FAILED，不发布 |
| 音色克隆版权争议 | 中 | 法务风险 | 仅用已授权音色，签署书面授权 | 切回通用音色 |
| 前端模板改动受限（R3） | 高 | 管理端 UI 无法按期 | 先做「纯脚本 + 既有组件」版本，UI 等用户在设计器拖拽 | 功能可用，体验稍差 |
| 图谱无增量投影 | 中 | 新考点不即时可见 | E6 之前用定时 backfill（每日一次） | 恢复定时任务 |
| 全量门禁既有 FAIL（L2/L4） | 高 | 无法用「全绿」验收 | 只对本模块新增 L7 项负责，报告中明确区分既有失败 | 不适用 |

---

## 13. 非目标（明确不做，防范围蔓延）

1. 不做实时 AI 答疑（属「联考小智」，避免双入口）。
2. 不做自动批改与打分。
3. 不做押题/预测。
4. 不做真人视频剪辑工具（上传仍由管理员手工完成，或直接上传成片）。
5. 不引入 PostgreSQL/MongoDB/Neo4j/Milvus 的强依赖（全部为可选后端）。
6. 不改动 `static/` 存量题图与 `uploads/` 存量文件。
7. 不替换现有 343 个端点中的任何一个。
8. 不在本阶段做多语言配音。

---

## 14. 待审批决策点（请逐条确认）

| # | 决策 | 建议 | 影响面 |
|---|---|---|---|
| D1 | 是否批准「Obsidian 仅作编译源、运行时不读 Markdown」 | 批准 | 决定 §4 全部设计 |
| D2 | 是否批准「图谱建在 GraphStore，Obsidian 只产意图」 | 批准 | 决定 §5 与 E1–E6 工期 |
| D3 | 是否批准 P2 才做考点层扩展（P1 先用现有 518 个知识点出片） | 批准 | P1 可在 3 周内出片 |
| D4 | 是否接受「L3 兜底（板书+画外音）为默认形态，数字人为增强」 | 批准 | 决定 P3 是否立项 |
| D5 | 音色方案：通用音色 / 自录授权音色 / 克隆名师音色 | 建议「自录授权音色」 | 法务风险 |
| D6 | 首批试点科目与考点范围（建议：公专「执法程序」+ 行测「判断推理」各 10 个） | 按建议 | 决定 P0 黄金集 |
| D7 | 视频存储位置：D 盘受控目录 / 外接盘 / 对象存储 | 建议 D 盘受控目录 + 容量闸 | 决定 §7.2 |
| D8 | 是否同意新增 9 个端点与 2 张表 | 同意 | R11 需登记比对 |

---

## 附录 A：本方案引用的实测证据位置

| 结论 | 证据 |
|---|---|
| 数据表行数、图谱层级 | 本机 `sqlite3` 只读查询（2026-11-03） |
| F3/F4/F5/F6 能力与开关 | `docs/superpowers/specs/F3对象存储与媒体资产_报告_20261026.md` 等 4 份报告 |
| 视频上传/流式端点 | `backend/app/api/v1/library/videos.py`（444 行） |
| 资料模型字段 | `backend/app/models/models.py`（`StudyMaterial` 起 1375 行） |
| 重活进程隔离模式 | `backend/app/services/ocr_worker.py` + `ocr_pipeline._ocr_python()` |
| 显存/磁盘/Python/torch/Docker | 本机 `nvidia-smi`、`df -h`、`python -V`、`torch.cuda.is_available()`、`docker ps` |
| Obsidian 库现状 | `obsidian_list` 对 `D:\Obsidian仓库` 的实测结果 |
| 无 embedding 服务 | `docs/superpowers/specs/向量投影Embedding服务配置与故障治理_v1.md` |

## 附录 B：P0 基准报告需要产出的数字（不可省略）

1. 单页 HTML→PNG 渲染耗时（秒/页）。
2. 1 分钟旁白的 Edge-TTS 合成耗时与音频时长偏差。
3. MuseTalk 在 8GB 显存下的显存峰值、单分钟视频耗时、是否 OOM。
4. 单条 12 分钟视频的总耗时与各 stage 占比。
5. 720p 成片实际体积（MB/分钟）。
6. LLM 单条脚本的 token 消耗与费用。
7. ASR 回环在 3 类术语（法条名、多音字、数字）上的字错率。
