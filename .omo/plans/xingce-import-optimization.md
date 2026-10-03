# 行测题目导入优化机制 — 实施计划

## TL;DR

> **Quick Summary**：行测 170 个 PDF（85 组「题本+答案解析」）实测**全部含文本层、零扫描件**，语料高度规整（分节头 100% 命中、答案锚点 100% 命中、考点 100% 覆盖）。现有解析器已能解析行测（实测 110 块），但**题本与答案解析被当作两个独立文档、无自动配对**，且行测题库**完全空白**（`question_bank` 2583 题全为公专，行测 0 题）、**行测题型未注册**。本计划在**完全复用既有解析引擎**的前提下，补齐行测专属的「分节区间对齐配对安全网 + 考点树 + 分区落位 + 资料分析题组 + 试卷元数据」，并以三重回归门禁（公专 G1 / 申论 G3 / 行测 G2）保证对存量 2583 道公专题**零回归**。
>
> **Deliverables**：
> - 行测分节路由 + 分离配对安全网内核（新增，纯增量，不改既有切分函数体）
> - 行测题型主数据（`question_type` subject_id=1）+ 分区枚举补全（`科学推理`）
> - 行测考点树（461 token → 层级化知识点，复用 `knowledge_point` 表）
> - 资料分析题组（复用 `question_groups`，`group_type='data_analysis'`）
> - 专用端点 `POST /api/questions/import/separate-match-xingce`（**零改动共享 dispatch**）
> - 卷级元数据自动注入（省份/年份/卷别，`exam_paper` + `exam_paper_tag`）
> - 前端 `question_import.vue` 强化（仅 `<script>`，VTJ raw 页）
> - 6 套试点 → 门禁固化 → 全量 85 套（约 11,000 题）
>
> **Estimated Effort**：Large
> **Parallel Execution**：YES — 5 waves
> **Critical Path**：1（差因诊断）→ 8（配对内核）→ 11（专用端点）→ 15（试点）→ 16（全量）→ F1–F4

---

## Context

### Original Request

解析 `D:\砺安题库\砺安题库\题库\行测` 下所有省份 + 国考文件夹的行测题目内部文档结构形式，制定一套完整的行测题目导入优化机制。方案需深度分析、可下钻、支持用户再提更深要求，**经用户同意后才能实施**，并统一存档到 `solve_problems_files`。

### Interview Summary

**用户已决策的 5 项**：

| # | 决策点 | 决策 |
|---|--------|------|
| Q1 | 图形推理等纯图片题如何入库 | **切图入库 + 人工补文字选项**（复用 `[IMAGE:...]` 六环节协议，不新建机制） |
| Q2 | 解析质量不达标的题如何处理 | **入库 + 标记待复核**（复用 `need_review=1` + 前端 🔴 徽标 + `need_confirm_items`） |
| Q3 | 是否需要前端人工校对工作台 | **不做工作台**，只强化现有预览页（仅改 `<script>`，符合 VTJ 职责分离） |
| Q4 | 清理无用/过期数据的授权范围 | **只清理解析缓存与死代码，不碰业务数据与 DB 备份** |
| Q5 | 85 套全量导入的推进方式 | **先试点 6 套（覆盖 5 类命名异常）→ 固化为门禁语料 → 再全量 85 套** |

**由 Q5 派生的试点语料**（每套必覆盖至少一个结构/命名异常）：

| 套 | 覆盖的变体 |
|---|---|
| 国考 2025 地市级 | 文件名 `题干.pdf` 冒充题本（**唯一命名异常**） |
| 国考 2025 副省级 | 三卷并行中的对照卷 |
| 国考 2023 地市级 | **既有 G2 门禁基线所在卷**（用于证明改动后仍 ≥0.99 不劣化） |
| 江苏 2025 C 类 | 卷别标记 `（C类）` + 行测最高卷数 |
| 甘肃 2025 | 省份名缺「省」字（验证元数据以文件夹名为准） |
| 广东 2023 县级卷 | 同年双卷并存（县级卷/乡镇卷） |

### Research Findings

全部经工具验证，无一项依赖推测。完整证据见 `.omo/drafts/xingce-import-optimization.md` §8。

**PDF 内部结构（170/170 全量实测）**：

| # | 结论 |
|---|------|
| S1 | **170 个 PDF 全部有文本层，0 个扫描件** → OCR 整体旁路 |
| S2 | 85 组题本/答案解析完美配对；题本 2107 页 / 195.9 万字符，答案解析 3185 页 / 405.4 万字符 |
| S3 | 分节头 100% 命中（85/85），5~7 节；词表：政治理论(24)/常识判断(57)/言语理解与表达(55)/数量关系(54)/判断推理(55)/资料分析(57)/**科学推理(3)** |
| S4 | 答案锚点 100% 命中，格式 `N. 正确答案：X` **行首内联，无首页答案表** |
| S5 | `【考点】` 100% 覆盖，461 个不同 token、16,051 次实例，均值 121/卷；**层级化路径**（`中心理解题-关联词-转折`）；含省份私有值（`江苏特色-综合资料` 97 次） |
| S6 | 资料分析材料块 100% 覆盖，共 364 块，锚点为**全角括号独占行** `（一）（二）（三）（四）` |
| S7 | 题号全卷连续 1..N（88–141/卷），跨分节不重排；选项 `A./B./C./D.` 独占行，**文字可为空**（纯图片选项） |
| S8 | 组合题题干内含 `①②③④⑤`，A/B/C/D 为元选项（`A.2项`） |
| S9 | 答案解析**不重复题干、无分值**，与申论结构完全不同 |

**数据库现状**：

| 项 | 实测值 |
|---|--------|
| `question_bank` | **2,583 题，100% 公专，行测 0、申论 0** |
| `question_type` | 🔴 **subject_id=1（行测）零行** → 硬阻塞 |
| `question_bank` 已有列 | ✅ `xingce_subcategory VARCHAR(7)`、`group_id`、`parent_id`、`question_level`、`sort_order`、`question_number`、`need_review`、`requirements`（**结构已就位，全未用于行测**） |
| Enum 约束 | 实测 SQLite `VARCHAR(7)` 且**无 CHECK 约束**（SQLAlchemy 2.0 `Enum.create_constraint` 默认 False）→ 补枚举值**无需 DB 迁移** |
| `models.py` Enum 漂移 | `xingce_subcategory` 在 `models.py:188` 与 `:950` 两处声明 `Column(Enum(...))`，**均缺 `科学推理`** |
| `question_groups` | 21 行全为公专；`group_type` 支持 `data_analysis` 但**当前 0 行** |
| `question_import_record` | 1,376 行：COMPLETED 1064 / **PREVIEW 305 卡死** / PARTIAL 6 / **PARSING 1 卡死** |
| 🔴 决定性证据 | **2026-10-03 13:01** 有人上传安徽行测：id 1375（题本）PREVIEW total=110 success=110；id 1376（答案解析）PREVIEW total=101 success=101；均 `current_phase='DONE'`、`failed_count=0`、**从未确认入库** |
| `exam_paper_tag` | 含 2 行 `subject_category='行测'` 且 `is_complete=0`（失败痕迹） |

**后端管线**：

| 文件 | 体积 | 角色 |
|------|------|------|
| `app/api/v1/question_import.py` | 219.7 KB / 4896 行 | 导入编排器 |
| `app/services/text_parser.py` | 201.6 KB / ~4200 行 | 解析引擎（单一事实来源） |
| `app/services/question_classifier.py` | 59.3 KB | 子科目 + 考点分类 |
| `app/services/composite_matcher.py` | 12.1 KB | 复合题归组（**已支持 `data_analysis`，触发词是 `图表`**，不命中行测的 `（一）（二）`） |
| `app/services/material_parser.py` / `explanation_extractor.py` / `option_utils.py` / `text_cache.py` | 9.2 / 7.5 / 7.1 / 5.3 KB | 材料解析 / 解析提取 / 选项 / 缓存 |
| `app/services/ocr.py` + `ocr_worker.py` | 30.4 KB | OCR（**行测整体旁路**） |

**`separate-match` 分流（`question_import.py:4005-4011`）**：
```python
if _q_blocks[0]['format']=='essay' and _a_blocks[0]['format']=='essay':
    return _separate_match_essay(...)            # 申论：题号+分值+题干指纹
result = smart_match_questions_answers(...)     # 行测落这里：通用 8 级策略链
```

**前端 / VTJ**：

| 项 | 实测值 |
|---|--------|
| 路由 | `/question-import` → `$vtj/vue/question_import.vue`（**下划线**） |
| 规模 | **159 KB / 3640 行** |
| `raw` 标记 | ✅ `.vtj/projects/linxitie.policy-exam-bank.json:437-439` → 可安全手改 `<script>` |
| 已调用端点 | `upload`(L800) / `parse`(L1523) / **`separate-match`(L2157)** / `confirm`(L1056) / `batch-parsed`(L2687) / `single`(L877,2604) / `ocr`(L1121) / `image`(L1229) / `attach-image`(L2417) / `records/{id}/status`(L774) / `records?page=`(L2833) → **分离导入 UI 已存在，无需新建页面** |
| Vite 端口 | **9527**（`vite.config.ts:8` `DEV_PORT=9527`, `strictPort:true`） |

### 核心设计命题

> **行测的「题本↔答案解析」配对缺少可靠安全网。**
>
> 申论有 **题号 + 分值 + 题干指纹** 三重判据；行测答案解析**既不重复题干、也无分值** —— 三重判据只剩 1/3。若上传 2024 题本 + 2025 答案解析，**计数相等也照样全卷配错，且无任何机制能察觉**。
>
> **行测专属替代安全网：分节边界对齐。** 题本与答案解析**携带完全相同的分节头**（实测 100% 命中），题号在分节内连续。因此「每个分节的题号区间」在两份文档中必须逐一相等 —— 这在信息论上等价于申论「分值锚点 + 题干指纹」的合成替代物，**且成本为零**。

### 自审缺口分析（Metis Agent 超时后自行完成，18 项）

**阻塞级**：

| # | 缺口 | 处置 |
|---|------|------|
| GAP-1 | **110 vs 101 差因未诊断** | **列为第 1 个任务**。设计配对前必须先量化差因，否则配对建在错误假设上 |
| GAP-2 | `科学推理` 不在 `models.py:188` / `:950` 的 Enum | 改这 2 处；**无需 DB 迁移** |
| GAP-3 | `question_type` 无 subject_id=1 行 | 幂等 INSERT（**行测入库硬阻塞**） |
| GAP-4 | 共享 dispatch 三科目共用，改动有回归风险 | **不改动 `L4005-4011`**；新建专用端点 |

**设计级**：GAP-5 `data_analysis` 触发词不命中行测（追加规则，`data_analysis` 0 行天然隔离）｜GAP-6 省份私有考点需规范化｜GAP-7 考点只在答案解析，须由配对携带｜GAP-8 `question_detail_category` 是第二个写入点，须同批改｜GAP-9 选非题语义｜GAP-10 组合题元选项误判率｜GAP-11 纯图片选项题（因 `A.` 标记存在，`opt_count>=2` 成立，不会误判为论述题 —— 有利）

**运维/安全级**：GAP-12 不新增上传入口（不新增攻击面）｜GAP-13 图片提取需补最大像素上限（行测图片密度远高于公专）｜GAP-14 一律以文件夹名为省份源，禁止路径拼接｜GAP-15 分批事务 + WAL + 写前强制备份｜GAP-16 312 条卡死记录属业务数据，**待单独授权**

**文档冲突级（裁定）**：

| 冲突 | 裁定 |
|------|------|
| `vtj.md` 附录F 要求每次改 `.vue` 必同步 DSL JSON，但前序铁律 R-2 明确**禁止**（同步工具有损，48 方法中连 `_pollImportStatus` 都提取不到） | **以 R-2 为准**（实证优先）；提请修正 `vtj.md` |
| `vtj.md` 记设计器端口 5173，实测 **9527** | 以代码为准；提请修正 `vtj.md` |

---

## Work Objectives

### Core Objective

在**完全复用既有解析引擎**的前提下，为行测补齐「分节区间对齐配对安全网 + 考点树 + 分区落位 + 资料分析题组 + 卷级元数据」，使 85 套共约 11,000 道行测题可被自动、稳定、可回归地导入，且对存量 2,583 道公专题与申论链路**零回归**。

### Concrete Deliverables

1. `backend/app/services/text_parser.py` 新增 3 个纯增量函数（分节路由 / 行测配对 / 材料锚点）
2. `backend/app/api/v1/question_import.py` 新增专用端点 + 分节/考点/元数据注入
3. `backend/app/services/composite_matcher.py` 追加 1 条规则（不改动既有规则）
4. `backend/app/models/models.py` 两处 Enum 补 `科学推理`
5. 幂等主数据迁移脚本（`question_type` subject_id=1 + 行测考点树）
6. `.vtj/vue/question_import.vue` 仅 `<script>` 强化
7. 三重回归门禁脚本 + 6 套试点语料 + 全量 85 套导入
8. 运维文档 + 方案归档

### Definition of Done

- [ ] `question_bank` 中 `subject_id=1` 的题目数 > 10,000，答案覆盖率 100%，解析覆盖率 ≥ 98%
- [ ] 三重门禁全绿：公专 G1 **逐项与基线完全一致**（30 份 / 2899 块 / 污染 0 / PASS）、申论 G3 全通过、行测 G2 ≥ 0.99
- [ ] 6 套试点全部通过且固化为回归语料
- [ ] 行测题在 `/materials/xingce`、`/student/papers`、`/question-bank`、答题页四处**前端实际可见**
- [ ] `pytest` 失败集合与基线（`16 failed / 168 passed / 52 errors`）**完全一致**
- [ ] 批量改动 `.vue` 后**实际请求 Vite（9527）**验证通过，非仅 SFC 编译通过

### Must Have

- 行测分节路由 + 配对安全网（题号 + 分节区间全等 + 分节头序列全等）
- 行测题型主数据（`question_type` subject_id=1）—— 否则无法入库
- `科学推理` 补入两处 Enum —— 否则 3 套卷分区丢失
- 考点抽取与层级化落库（复用 `knowledge_point` + `question_knowledge`，**不新建表**）
- 资料分析题组（复用 `question_groups` `group_type='data_analysis'`）
- 卷级元数据（省份取**文件夹名**、年份、卷别）→ `exam_paper` + `exam_paper_tag`
- 纯图片题切图 + `[IMAGE:...]` 占位符 + `need_review=1`
- 三重回归门禁（公专 / 申论 / 行测）
- 共享 `separate-match` dispatch **零改动**

### Must NOT Have (Guardrails)

- ❌ **禁止改动 `question_import.py:4005-4011` 的三科目共享 dispatch**
- ❌ **禁止修改 `extract_question_blocks` 既有切分函数体的任何逻辑**（仅允许新增函数 + 入口分支，仿申论 v4 T3 红线）
- ❌ **禁止新建第三套题号解析器**（必须复用 `extract_question_numbers`）
- ❌ **禁止另写答案归一化 / 题型判定**（必须复用 `canonical_answer` / `_detect_question_type`）
- ❌ **禁止同步 `.vtj/files/question_import.json`**（铁律 R-2）
- ❌ **禁止撤销 `block_accepts_letter_answer` 门控**（铁律 R-3）
- ❌ **禁止新建表**（考点树复用 `knowledge_point`；题组复用 `question_groups`）
- ❌ **禁止新增文件上传入口**（复用既有 `/import/upload`，不新增攻击面）
- ❌ **禁止触碰 2,583 道存量公专题的任何数据**（用户决策 Q4）
- ❌ **禁止清理 DB 备份**（用户决策 Q4；`backend/data/` 4 份备份约 430MB 保留）
- ❌ **禁止删除或修改 312 条卡死 import 记录**（业务数据，用户明确**未**授权）
- ❌ **禁止改 `.vtj/vue/*.vue` 的 `<template>`**（VTJ 设计器职责，§3.1）
- ❌ **禁止以「pytest 全绿」作为验收判据**（铁律 R-4）
- ❌ **禁止只凭 SFC 编译通过就宣称前端生效**（G8：必须实请求 Vite）
- ❌ **禁止删除或修改 312 条卡死 import 记录**（业务数据，待单独授权）
- ❌ **禁止删除 `text_cache.bak_*`**（铁律 R-1 的实证证据）
- ❌ **禁止删除 `static/questions/` 下任何非空目录**（2,583 道题的图片）

> ✅ **已授权的清理范围**（用户 2026-10-03 批准）：**死代码 + 空目录** —— 详见任务 6 阶段 B。

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — 全部验证由 Agent 执行。

### Test Decision

- **Infrastructure exists**：YES（`backend/tests/` + `scripts/verify_parser_regression.py` + `backend/data/regression_baseline_before.txt` 基线）
- **Automated tests**：Tests-after（增量）+ 既有回归门禁强制
- **Framework**：pytest（既有）+ 自建行测语料门禁
- **基线判据**：pytest 失败集合与 `16 failed / 168 passed / 52 errors` **完全一致**（铁律 R-4）

### 三重回归门禁（每波必跑）

| 门禁 | 命令 | 通过判据 |
|------|------|---------|
| **G1 公专** | `python scripts/verify_parser_regression.py "D:\砺安题库\砺安题库\题库\公安题目（打印）" --out <tmp>` | 30/30 解析、**2899 块**、**污染 0**、题型分布 {单选2534,多选249,判断80,简答36}、选项分布 {4:2796,1:13,2:14,0:73,3:3}、**PASS** —— 逐项与基线一致 |
| **G3 申论** | 申论 A+B 组不变量 | I-1 题目数==答案段数、I-2 题号连续、I-3 块内无第二题号、I-5 答案覆盖 100%、I-7 `analysis`≠`answer`、I-8 options 恒空 |
| **G2 行测** | 新增行测门禁（任务 2 建） | 分节头命中率 100%、答案锚点 100%、配对率 ≥0.99、分节区间全等、考点覆盖 ≥98% |

**G1 与基线逐项不一致即整体不通过，无论行测多准。**

### QA Policy

每个任务 MUST 包含 Agent 可执行 QA 场景（1 成功路径 + 1 失败/边界路径），证据落 `evidence/task-{N}-{slug}.{ext}`。

- **PDF/解析**：Bash（python -c 内联探针）→ 断言块数、字段完整率、分节区间
- **数据库**：Bash（sqlite3 只读查询）→ 断言行数、覆盖率、type_id 分布
- **API**：Bash（curl 经 Vite 代理 9527）→ 断言状态码 + JSON 字段
- **前端**：Playwright → 实际请求 `localhost:9527`，断言 DOM 与网络请求

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 — 基线与主数据（6 任务并行；只读诊断 + 幂等迁移，互不干扰）
├── 1. 行测语料探针 + 110/101 差因诊断        [unspecified-high] ★关键路径
├── 2. 三重门禁基线快照 + 行测门禁脚本         [unspecified-high] ★关键路径
├── 3. 行测题型主数据迁移（question_type）      [quick]
├── 4. 行测分区枚举补全（科学推理 ×2 处）       [quick]
├── 5. 考点词表规范化规格 + 461 token 分类      [deep]
└── 6. 死代码与空目录清理（已授权执行）+ 分层建议  [unspecified-low]

Wave 2 — 行测解析与配对内核（依赖 1,2；4 个并行，只增不改）
├── 7.  _route_xingce_sections() 分节路由       [deep]     ★关键路径
├── 8.  _xingce_cross_validate() 配对安全网      [deep]     ★关键路径
├── 9.  资料分析材料锚点（（一）（二））          [deep]
└── 10. 考点抽取与层级化落库                     [deep]     ★关键路径

Wave 3 — 端点与元数据（依赖 7,8,9,10）
├── 11. /separate-match-xingce 专用端点         [deep]     ★关键路径
├── 12. 卷级元数据注入（省份/年份/卷别）         [unspecified-high]
└── 13. 纯图片题切图 + need_review 标记         [unspecified-high]

Wave 4 — 前端与试点（依赖 11,12,13）
├── 14. question_import.vue script 改造         [visual-engineering]
└── 15. 6 套试点导入 + 三重门禁回归              [unspecified-high] ★关键路径

Wave 5 — 全量与交付（依赖 15）
├── 16. 全量 85 套导入                          [unspecified-high] ★关键路径
└── 17. 运维文档 + 方案归档 + vtj.md 勘误        [writing]

Wave FINAL — 4 路并行评审 → 用户明确批准
├── F1. 方案合规审计（oracle）
├── F2. 代码质量评审（unspecified-high）
├── F3. 真实手工 QA（unspecified-high + playwright）
└── F4. 范围保真检查（deep）

Critical Path：1 → 2 → 8 → 11 → 15 → 16 → F1–F4 → 用户批准
Max Concurrent：6（Wave 1）
```

### Dependency Matrix

| # | 任务 | 依赖 | 阻塞 | 并行组 | Agent |
|---|------|------|------|--------|-------|
| 1 | 差因诊断 | — | 7,8,9,10 | W1 | unspecified-high |
| 2 | 门禁基线 | — | 全部 | W1 | unspecified-high |
| 3 | 题型主数据 | — | 11,15,16 | W1 | quick |
| 4 | 分区枚举 | — | 11,15,16 | W1 | quick |
| 5 | 考点规格 | — | 10 | W1 | deep |
| 6 | 清理盘点 | — | 17 | W1 | unspecified-low |
| 7 | 分节路由 | 1,2 | 11 | W2 | deep |
| 8 | 配对安全网 | 1,2 | 11 | W2 | deep |
| 9 | 材料锚点 | 1,2 | 11 | W2 | deep |
| 10 | 考点落库 | 2,5 | 11 | W2 | deep |
| 11 | 专用端点 | 3,4,7,8,9,10 | 14,15 | W3 | deep |
| 12 | 卷级元数据 | 11 | 15 | W3 | unspecified-high |
| 13 | 图片切图 | 11 | 15 | W3 | unspecified-high |
| 14 | 前端改造 | 11,12,13 | 15 | W4 | visual-engineering |
| 15 | 6 套试点 | 14 | 16 | W4 | unspecified-high |
| 16 | 全量导入 | 15 | 17,F1–F4 | W5 | unspecified-high |
| 17 | 文档归档 | 6,16 | F1 | W5 | writing |

### Agent Dispatch Summary

- **Wave 1（6）**：1 → `unspecified-high`，2 → `unspecified-high`，3 → `quick`，4 → `quick`，5 → `deep`，6 → `unspecified-low`
- **Wave 2（4）**：7 → `deep`，8 → `deep`，9 → `deep`，10 → `deep`
- **Wave 3（3）**：11 → `deep`，12 → `unspecified-high`，13 → `unspecified-high`
- **Wave 4（2）**：14 → `visual-engineering`，15 → `unspecified-high`
- **Wave 5（2）**：16 → `unspecified-high`，17 → `writing`
- **FINAL（4）**：F1 → `oracle`，F2 → `unspecified-high`，F3 → `unspecified-high`，F4 → `deep`

---

## TODOs

> **红线（每个任务都适用）**：
> - 只增不改既有解析逻辑；共享 dispatch 零改动
> - 每任务完成后必须跑 G1 + G3 门禁，逐项与基线一致才算通过
> - 改 `.vue` 后必须**实际请求 Vite（9527）**，非仅 SFC 编译通过
> - 禁止同步 `.vtj/files/*.json`
> - 每任务完成后更新本文件对应复选框

- [ ] 1. 行测语料探针 + 110/101 差因诊断

  **为什么这个任务是第 1 个**：2026-10-03 13:01 的安徽行测试导入，题本解析出 **110** 块、答案解析 **101** 块，两者 `failed_count=0`、`current_phase='DONE'`，但从未确认入库。**9 题差额未解释**。若不先量化差因就设计配对内核，配对规则会建立在错误假设上 —— 这是整套方案唯一的真风险点。

  **What to do**：
  - 新建 `backend/scripts/probe_xingce_corpus.py`（**只读探针，不写库**）：遍历 `题库/行测` 全部 170 个 PDF，逐份输出 JSON 清单
  - 每份提取并落盘：分节头序列（含 char offset）、题号序列、选项序列、`（一）（二）` 材料锚点序列、页数、字符数、嵌入图片数（按页）
  - **差因诊断**：对安徽行测这一对（及试点 6 套全部），逐题号比对题本块与答案块的差集，输出 `only_in_questions[]` / `only_in_answers[]`
  - 对差集题号**逐个打印原文上下文**（题本侧 300 字 + 答案侧 300 字），人工可判读成因
  - 候选成因需逐一证伪或证实：(a) 组合题 `①②③` 被计为独立题；(b) 答案解析存在多题共用一段解析；(c) 分页切断块；(d) `monotonic` 单调过滤丢题；(e) 选项标记缺失导致块未闭合
  - 同时验证既有 G2 基线：国考 2023 地市级须复现 130 块 / options 130/130 / smart_match ≥0.99

  **Must NOT do**：
  - ❌ 不得修改任何解析代码（本任务纯诊断）
  - ❌ 不得写数据库
  - ❌ 不得触发 OCR（实测 170/170 有文本层，OCR 是纯浪费）

  **Recommended Agent Profile**：
  - **Category**：`unspecified-high`
    - Reason：需横跨 170 份 PDF 的模式识别 + 差因归因推理，边界清晰但需要高强度自主诊断，且结论直接决定后续 4 个内核任务的形状
  - **Skills**：`[]`
    - `pdf-converter`：省略 —— 本任务用 pymupdf 直读文本层即可（实测无需 OCR/版面转换），加载反而引入不必要的 MinerU 路径依赖
  - **Skills Evaluated but Omitted**：
    - `diagnose`：省略 —— 该 skill 面向"代码 bug 复现→定位→修复"，本任务是语料结构测绘 + 差因归因，无代码可复现
    - `deep`：省略 —— Agent 类别而非 skill，不适用

  **Parallelization**：
  - **Can Run In Parallel**：YES
  - **Parallel Group**：Wave 1（与 2,3,4,5,6 并行）
  - **Blocks**：7, 8, 9, 10
  - **Blocked By**：None

  **References**：

  *Pattern References（现有机制，必须先理解再动手）*：
  - `backend/app/api/v1/question_import.py:1413` `_auto_detect_tags()` — 参考它如何用正则从文件名提取年份/省份/考试类型，本探针的元数据提取须与其口径一致
  - `backend/app/api/v1/question_import.py:1475` `_detect_complete_paper()` — 「完整试卷判定」启发式（连续递增题号≥5 且 60% 连续 + 答案区检测），探针用它交叉验证题号连续性
  - `backend/data/regression_baseline_before.txt` — 公专门禁基线原文，作为探针输出格式的参照

  *API/Type References（数据契约）*：
  - `question_import_record` 表列：`import_id / paper_id / user_id / original_filename / file_type / total_questions / success_count / failed_count / duplicate_count / import_status / preview_data(JSON) / error_messages(JSON) / import_time / complete_time / progress_percent / current_phase`
  - 探针输出 JSON 须与 `preview_data` 的 `questions[]` 结构对齐，便于后续直接对比

  *External References（工具链，已实测）*：
  - `pymupdf 1.28.2` — 本机已装，`doc.get_text('text')` 取文本层、`doc[i].get_images(full=True)` 取图片。**禁止用 `fitz` 旧别名**（已 deprecated 警告）
  - `pdfplumber 0.11.9` — 备选，用于需要表格结构时；本任务以 pymupdf 为主

  **WHY Each Reference Matters**：
  - `_auto_detect_tags()` 是既有元数据口径的**唯一权威**。探针若自创一套年份/省份正则，会与入库时的元数据不一致 → 探针结论无法指导实现
  - `_detect_complete_paper()` 的连续性判据必须被探针复用，否则「110 vs 101」可能是探针正则与生产解析器口径不同造成的**伪差因**
  - `regression_baseline_before.txt` 给出基线输出的确切格式，探针照此格式输出才能做逐项 diff

  **Acceptance Criteria**：

  - [ ] `python backend/scripts/probe_xingce_corpus.py` 成功运行，退出码 0
  - [ ] 产出 `tmp/xingce_probe/corpus_manifest.json`，含 **170 条记录**（85 QB + 85 ANS），字段完整无缺
  - [ ] 输出**跨卷不变式汇总表**，至少包含：分节头命中率、答案锚点命中率、题号连续率、选项闭合率、材料锚点计数
  - [ ] 安徽行测差集**逐题可判读**：输出 `only_in_questions` 与 `only_in_answers` 的题号列表 + 每题双侧原文上下文
  - [ ] 差因结论**明确到成因分类**（a–e 五类中哪一类或哪几类），并给出每类的确切题号
  - [ ] G2 基线复现：国考 2023 地市级 = **130 块 / options 130/130 / smart_match ≥0.99**
  - [ ] 未修改任何 `.py` 业务代码 —— `git diff --stat` 仅新增 `probe_xingce_corpus.py`

  **QA Scenarios**：

  ```
  Scenario: 全量语料探针成功（成功路径）
    Tool: Bash
    Preconditions: Python 3.13.5 + pymupdf 1.28.2 已装；`题库/行测` 可读
    Steps:
      1. cd D:\砺安题库\砺安题库
      2. python backend/scripts/probe_xingce_corpus.py --out tmp/xingce_probe
      3. 断言退出码 == 0
      4. python -c "import json;d=json.load(open('tmp/xingce_probe/corpus_manifest.json',encoding='utf-8'));print(len(d));assert len(d)==170"
      5. 断言 QB 记录数 == 85 且 ANS 记录数 == 85
      6. 断言分节头命中率 == 100.0（85/85）
      7. 断言答案锚点命中率 == 100.0（85/85）
    Expected Result: 170 条记录；分节头与答案锚点均 100% 命中；退出码 0
    Failure Indicators: 记录数 ≠ 170；命中率 < 100%（说明此前实测有误或环境文件变动）
    Evidence: evidence/task-1-corpus-probe.txt

  Scenario: 110/101 差因可判读（成功路径）
    Tool: Bash
    Preconditions: 上一步已产出 corpus_manifest.json
    Steps:
      1. python backend/scripts/probe_xingce_corpus.py --pair "2023年安徽省公务员录用考试《行测》题（网友回忆版）" --diff
      2. 断言输出含 "only_in_questions" 与 "only_in_answers" 两个非空节
      3. 断言每个差集题号都附带双侧原文上下文（各 ≥100 字）
      4. 断言差集总数 == 9（若诊断结论为「差额由某成因解释」，则断言该成因的题号集合与差集一致）
    Expected Result: 差集可被人工直接判读成因，无需再跑代码
    Failure Indicators: 差集为空（说明探针口径与生产不一致）；或上下文缺失
    Evidence: evidence/task-1-diff-110-101.txt

  Scenario: G2 基线不可复现则任务失败（失败路径）
    Tool: Bash
    Preconditions: 探针已运行
    Steps:
      1. python backend/scripts/probe_xingce_corpus.py --baseline-g2
      2. 断言国考 2023 地市级 块数 == 130
      3. 断言 options 数 == 130
      4. 断言 smart_match_rate >= 0.99
    Expected Result: 4 项断言全过，证明探针口径与生产解析器一致
    Failure Indicators: 任一断言失败 → **立即停止后续 Wave 2，先修正探针口径**（这是红线：口径不一致会让所有下游配对结论失效）
    Evidence: evidence/task-1-g2-baseline.txt
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-1-corpus-probe.txt` — 170 条记录清单 + 跨卷不变式汇总表
  - [ ] `evidence/task-1-diff-110-101.txt` — 差集题号 + 双侧原文上下文
  - [ ] `evidence/task-1-g2-baseline.txt` — G2 四项断言输出

  **Commit**：YES
  - Message：`feat(xingce): add read-only corpus probe and diagnose 110-vs-101 discrepancy`
  - Files：`backend/scripts/probe_xingce_corpus.py`

- [ ] 2. 三重回归门禁基线快照 + 行测门禁脚本

  **为什么需要**：前序铁律 R-4 要求「验收判据是失败集合与基线完全一致」，但**行测从来没有过门禁**（行测全部是 2021–2025，恰在前序 P2 待办「剩余 2020–2025 纳入门禁」的门外）。没有行测门禁，本方案的每次改动都无法判断是否劣化。

  **What to do**：
  - **先采基线（不可跳过）**：跑公专 G1，把输出存为 `backend/data/xingce_regression_baseline.txt`；跑申论 G3 A+B 组，存为 `backend/data/shenlun_g3_baseline.txt`；跑 pytest，存失败集合为 `backend/data/pytest_baseline.txt`
  - 新建 `backend/scripts/verify_xingce_regression.py`：对指定行测语料目录逐份解析，输出并可 diff 以下指标
    - 分节头命中率、答案锚点命中率、题号连续率、选项闭合率
    - **分节区间表**：`section_name → (min_qno, max_qno, count)`（这是 G2 安全网的核心断言对象）
    - 配对率（题号 join 命中率）、答案覆盖率、解析覆盖率、考点覆盖率
    - 题型分布、选项数量分布、材料块数
  - 支持 `--reparse` 增量（只重跑解析不重跑提取，前序经验：20 份门禁 1 秒内跑完）
  - 支持 `--compare <baseline>` 做逐项 diff，**任一项不一致即退出码非 0**
  - 语料落盘为可复现缓存 `{slot}.q.txt` / `{slot}.a.txt` / `{slot}.result.json`（仿前序做法）

  **Must NOT do**：
  - ❌ 不得修改 `text_parser.py` / `question_import.py` 任何逻辑
  - ❌ 不得修改 `backend/data/question_bank.db`
  - ❌ 不得让门禁脚本依赖网络或 LLM 兜底（前序经验：回归须离线可复现，需 monkeypatch 掉 LLM）

  **Recommended Agent Profile**：
  - **Category**：`unspecified-high`
    - Reason：需要精确复刻前序 `verify_parser_regression.py` 的门禁语义（基线比对、增量、缓存、离线复现），且要设计行测特有的分节区间断言 —— 对规格准确性要求高
  - **Skills**：`[]`
  - **Skills Evaluated but Omitted**：
    - `tdd`：省略 —— 门禁脚本本身不是被测对象；且铁律 R-4 明确不以 pytest 全绿为判据，套 TDD 会误导

  **Parallelization**：
  - **Can Run In Parallel**：YES
  - **Parallel Group**：Wave 1（与 1,3,4,5,6 并行）
  - **Blocks**：7, 8, 9, 10, 11, 15, 16
  - **Blocked By**：None

  **References**：

  *Pattern References（必须照抄其语义，不可自行发明）*：
  - `backend/scripts/verify_parser_regression.py` — **本任务的直接模板**。其基线比对、增量 `--reparse`、缓存落盘、离线复现（monkeypatch LLM）全部照搬
  - `backend/data/regression_baseline_before.txt`（6,232 字节）— 公专基线原文，格式必须能被新脚本 `--compare` 消费
  - `backend/data/parser_regression.txt`（6,228 字节）— 上一轮实测输出，用于确认格式

  *API/Type References*：
  - `text_parser.extract_question_blocks()` 返回的块结构：`question_number` / `content` / `options` / `answer` / `analysis` / `format` / `score` / `requirements` / `material_text` / `material_titles` / `block_reasons` / `blocked` / `confidence` / `suspicious`
  - `text_parser.smart_match_questions_answers()` 返回：`questions[]` / `match_rate` / `matched_count` / `total_questions` / `unmatched_question_numbers` / `extra_answer_numbers` / `analysis_count` / `strategy_used` / `details[]`

  *Test References*：
  - `backend/tests/test_answer_extractor.py:47` — 已含 `text = "正确答案：B"` 用例，**证明行测答案锚点格式已有测试覆盖**，本任务的门禁须与之一致
  - `backend/tests/test_realworld_formats.py:34-56` — 含 `故正确答案为A。` / `故本题正确答案为AC。` 用例，答案归一化口径参照

  **WHY Each Reference Matters**：
  - `verify_parser_regression.py` 是前序会话**已通过验证**的门禁实现。重新发明必然引入偏差，且违反 G6「去粗取精」。其 `--reparse` 增量能力是「改一行解析代码 1 秒跑完 20 份」的关键，必须继承
  - `extract_question_blocks()` 的块字段清单决定门禁要断言哪些属性；漏一个字段就漏一类回归
  - `test_answer_extractor.py:47` 已用 `正确答案：B` —— 说明这条格式**已被认定为标准**，行测门禁必须复用同一提取器，**不得为行测另写锚点正则**

  **Acceptance Criteria**：

  - [ ] `backend/data/xingce_regression_baseline.txt` 存在且包含公专 30 份全部指标
  - [ ] `backend/data/shenlun_g3_baseline.txt` 存在
  - [ ] `backend/data/pytest_baseline.txt` 存在且记录 `16 failed / 168 passed / 52 errors`
  - [ ] `python backend/scripts/verify_xingce_regression.py "D:\砺安题库\砺安题库\题库\行测" --out tmp/g2` 退出码 0
  - [ ] 门禁输出**分节区间表**，格式 `section_name → (min, max, count)`，覆盖全部 85 套
  - [ ] `--compare` 模式在基线一致时退出 0、**任一项不一致时退出码非 0**
  - [ ] `--reparse` 模式在 85 套上 **≤ 60 秒**跑完
  - [ ] 门禁全程**无网络请求**（断网可跑）

  **QA Scenarios**：

  ```
  Scenario: 行测门禁首次建立基线（成功路径）
    Tool: Bash
    Preconditions: 三重基线文件已采集
    Steps:
      1. cd D:\砺安题库\砺安题库
      2. python backend/scripts/verify_xingce_regression.py "D:\砺安题库\砺安题库\题库\行测" --out tmp/g2
      3. 断言退出码 == 0
      4. 断言输出含 "分节区间表" 且行数 == 85（每套一张表）
      5. 断言 "分节头命中率" == 100.0
      6. 断言 "答案锚点命中率" == 100.0
      7. time 断言 --reparse 模式 ≤ 60 秒
    Expected Result: 退出码 0；85 套分节区间表齐全；两项命中率均 100%
    Failure Indicators: 任一命中率 < 100%（与本计划 §8 实测矛盾，须先排查环境差异）；耗时 > 60s（说明未继承 `--reparse` 增量）
    Evidence: evidence/task-2-xingce-gate.txt

  Scenario: --compare 检测到劣化则退出非 0（失败路径）
    Tool: Bash
    Preconditions: 已建立基线 tmp/g2/baseline.txt
    Steps:
      1. 手工把 baseline.txt 中 "答案覆盖率" 由 99.5 改为 98.0（模拟劣化）
      2. python backend/scripts/verify_xingce_regression.py "D:\砺安题库\砺安题库\题库\行测" --compare tmp/g2/baseline.txt --out tmp/g2/cmp
      3. 断言退出码 != 0
      4. 断言输出明确指出 "答案覆盖率 99.5 → 98.0" 的差异行
    Expected Result: 退出码非 0；差异被精确定位到具体指标
    Failure Indicators: 退出码 == 0（门禁失效，等于没有门禁 —— 这是最危险的失败模式）
    Evidence: evidence/task-2-compare-detect.txt

  Scenario: 公专 G1 基线逐项一致（防回归，红线）
    Tool: Bash
    Preconditions: 无（每波必跑）
    Steps:
      1. python backend/scripts/verify_parser_regression.py "D:\砺安题库\砺安题库\题库\公安题目（打印）" --out tmp/g1
      2. 断言 "30/30 解析"
      3. 断言 "2899 块"
      4. 断言 "污染 0"
      5. 断言 题型分布 == {单选2534, 多选249, 判断80, 简答36}
      6. 断言 选项分布 == {4:2796, 1:13, 2:14, 0:73, 3:3}
      7. 断言 结论 == "PASS"
    Expected Result: 7 项断言逐项与基线完全一致
    Failure Indicators: 任一项不一致 → **整体不通过，无论行测多准**（前序铁律）
    Evidence: evidence/task-2-g1-gongzhuan.txt
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-2-xingce-gate.txt` — 85 套门禁全量输出 + 分节区间表
  - [ ] `evidence/task-2-compare-detect.txt` — `--compare` 劣化检出验证
  - [ ] `evidence/task-2-g1-gongzhuan.txt` — 公专 G1 七项断言

  **Commit**：YES
  - Message：`test(xingce): add xingce regression gate with section-interval assertions`
  - Files：`backend/scripts/verify_xingce_regression.py`、`backend/data/xingce_regression_baseline.txt`、`backend/data/shenlun_g3_baseline.txt`、`backend/data/pytest_baseline.txt`

- [ ] 3. 行测题型主数据迁移（`question_type` subject_id=1）

  **为什么这是硬阻塞**：`question_bank.type_id` 是 NOT NULL 外键。实测 `question_type` 表中 **subject_id=1（行测）零行**（现有 8 行属公专、6 行属申论）。不补这一项，行测题目**根本无法入库** —— 任何一条 INSERT 都会因找不到对应题型而失败或写入错误题型。

  **What to do**：
  - 写**幂等**迁移脚本 `backend/scripts/migrate_xingce_question_types.py`（`--dry-run` 预览 / `--apply` 写入，与既有 `repair_question_types.py` 同一约定）
  - 行测实际只出现客观题（单选/多选/判断），前序 `type_detection.md` 已定「系统仅保留 4 种标准类型：单选/多选/论述/写作；判断题自然归入单选题」
  - 幂等 INSERT：`单选题`(subject_id=1)、`多选题`(subject_id=1)。**不创建**论述/写作（行测语料实测 0 例，创建即冗余）
  - **必须先检查现有 `question_type` 表结构**（是否有 `subject_id`/`status`/`sort_order` 等 NOT NULL 无默认列），按实际列补齐
  - 迁移前**强制备份** `question_bank.db`
  - 回滚脚本：按 `subject_id=1` 定向 DELETE，不触碰公专/申论行

  **Must NOT do**：
  - ❌ 不得修改 `subject_id=3`（公专）或 `subject_id=2`（申论）的任何现有行 —— 前序 M-2 迁移的教训是「保留原行不动 → 公专零影响」
  - ❌ 不得新建 Alembic 迁移（既有约定是 `backend/migrations/` + 幂等 SQL 脚本；且 SQLite 不支持 `ADD COLUMN IF NOT EXISTS`）
  - ❌ 不得在迁移中修改 `question_bank` 任何行

  **Recommended Agent Profile**：
  - **Category**：`quick`
    - Reason：单文件幂等 SQL 脚本 + 备份/回滚，边界清晰、模式有先例（`repair_question_types.py`、`add_shenlun_subject.sql`），无需深度推理
  - **Skills**：`[]`
  - **Skills Evaluated but Omitted**：
    - `deep`：省略 —— 过度配置；这是有成熟先例的机械性幂等迁移

  **Parallelization**：
  - **Can Run In Parallel**：YES
  - **Parallel Group**：Wave 1（与 1,2,4,5,6 并行）
  - **Blocks**：11, 15, 16
  - **Blocked By**：None

  **References**：

  *Pattern References（幂等迁移的既有范式，必须照抄）*：
  - `backend/scripts/repair_question_types.py` — `--dry-run` / `--apply` 二态、幂等可重复、调用既有单一事实来源函数（不重写判定逻辑）
  - `solve_problems_files/README.md:39` — 该脚本的登记位置与运维要点原文
  - `solve_problems_files/申论题目导入精准化方案_v4.md` §T9 — 前序 `M-1`/`M-2` 迁移规格：「保留原 `subject_id=3` 行不动 → 公专零影响」，**本任务沿用同一手法**

  *API/Type References*：
  - `question_type` 实测现有数据：`(1,'单选题',3) (2,'论述题',3) (4,'多选题',3) (5,'判断题',3) (6,'写作题',3) (7,'简述题',3) (8,'简答题',3) (9,'归纳概括',2) (10,'综合分析',2) (11,'提出对策',2) (12,'贯彻执行',2) (13,'文章写作',2) (14,'简答题',2)`
  - ⚠️ **注意 type_id 空洞**：1,2,4,5,6,7,8,9..14 连续但 **3 号缺失** → 新增行须让 DB 自增分配，**不得硬编码 type_id**
  - `question_bank.type_id` 列定义：`BigInteger NOT NULL`（外键指向 `question_type.type_id`）
  - `question_bank.question_type_detail VARCHAR(20)` — `models.py:971` 声明 `Enum("单选题","多选题","不定项","选择题","写作题","简答题","案例分析题","论述题","无")`，默认 `"选择题"`。**这是 type_id 之外的第二个题型事实来源**，须与 type_id 同批写入以避免前序「三处事实来源分裂」重演

  *Why This Reference Matters*：
  - 前序 v4 M-2 的「保留原行不动」是**公专零影响的唯一保证手法**。本任务若图省事重建整个 `question_type` 表，会立刻破坏 2583 道公专题的题型外键
  - type_id=3 空洞说明该表历史上删过行 → 硬编码 ID 会撞车，必须自增

  **Acceptance Criteria**：

  - [ ] 迁移前生成 DB 备份 `backend/data/question_bank.db.bak_xingce_types_<timestamp>`
  - [ ] `--dry-run` 输出待插入行，**不写库**
  - [ ] `--apply` 后 `select type_id,type_name,subject_id from question_type where subject_id=1` 返回 **2 行**（单选题、多选题）
  - [ ] 公专行数 `where subject_id=3` 仍为 **8**，申论 `where subject_id=2` 仍为 **6** —— 逐条比对迁移前快照
  - [ ] 脚本**重复执行 3 次结果一致**（幂等验证）
  - [ ] `.rollback.sql` 生成，回滚后 `subject_id=1` 归零而公专/申论不变
  - [ ] 提供回滚命令原文

  **QA Scenarios**：

  ```
  Scenario: 幂等迁移成功（成功路径）
    Tool: Bash
    Preconditions: 已生成 DB 备份
    Steps:
      1. cd D:\砺安题库\砺安题库
      2. python backend/scripts/migrate_xingce_question_types.py --dry-run  断言输出含 "将插入 2 行" 且 未写库
      3. python -c "import sqlite3;c=sqlite3.connect(r'backend/data/question_bank.db');print(c.execute('select count(*) from question_type where subject_id=1').fetchone())" 断言 == 0
      4. python backend/scripts/migrate_xingce_question_types.py --apply  断言退出码 0
      5. 断言 select count(*) where subject_id=1 == 2
      6. 断言 select count(*) where subject_id=3 == 8
      7. 断言 select count(*) where subject_id=2 == 6
      8. 连续再执行 --apply 两次，断言 subject_id=1 仍 == 2（幂等）
    Expected Result: 行测 2 行；公专 8 / 申论 6 分毫未动；重复执行无副作用
    Failure Indicators: 公专或申论行数变化 → 立即回滚，这是红线
    Evidence: evidence/task-3-migrate-types.txt

  Scenario: 回滚脚本正确还原（失败路径演练）
    Tool: Bash
    Preconditions: 迁移已 apply
    Steps:
      1. python backend/scripts/migrate_xingce_question_types.py --rollback
      2. 断言 select count(*) where subject_id=1 == 0
      3. 断言 select count(*) where subject_id=3 == 8
      4. 断言 select count(*) where subject_id=2 == 6
      5. python -c "…select count(*) from question_bank" 断言仍 == 2583
    Expected Result: 行测题型归零，公专/申论题型与 2583 道题完全不变
    Failure Indicators: question_bank 行数变化 → 回滚脚本误伤业务数据，立即用备份还原
    Evidence: evidence/task-3-rollback.txt
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-3-migrate-types.txt` — dry-run + apply + 三次幂等的行数快照
  - [ ] `evidence/task-3-rollback.txt` — 回滚后三科目行数与题库总数

  **Commit**：YES
  - Message：`feat(db): add idempotent migration for xingce question types`
  - Files：`backend/scripts/migrate_xingce_question_types.py`、生成的 `.rollback.sql`

  - [ ] 4. 行测分区枚举补全（`科学推理` × 2 处 Enum）

  **为什么需要**：实测 170 份语料中 **3 套卷含 `科学推理` 分区**（广东/河南类以科学推理替代数量关系）。而 `models.py` 两处 `Column(Enum(...))` **均未声明该值**。不补则这 3 套卷的分区被静默丢成 `无`，且这 3 套卷无法通过 `VALID_SUBCATEGORY_NAMES` 的显式值校验。

  **What to do**：
  - `backend/app/models/models.py:188-192`（`QuestionBank.xingce_subcategory`）Enum 列表补 `"科学推理"`
  - `backend/app/models/models.py:950-954`（`QuestionDetailCategory.xingce_subcategory`）**同样补** —— 这是第二处写入点，漏改即重演前序「三处事实来源分裂」
  - `backend/app/api/v1/question_import.py:243` 的 `VALID_SUBCATEGORY_NAMES[1]` 列表补 `"科学推理"`
  - 实测确认**无需 DB 迁移**（已验证 SQLite `VARCHAR(7)` 且无 CHECK 约束，SQLAlchemy 2.0 `Enum.create_constraint` 默认 False）
  - 同步核对 `sub_categories` 表是否需要对应行；若该表是 `VALID_SUBCATEGORY_NAMES` 的 DB 镜像则一并幂等 INSERT

  **Must NOT do**：
  - ❌ **不得改动既有 11 个 Enum 值中的任何一个**（含 3 个「旧值兼容」值 `常识`/`速度与知觉训练`/`语言理解与表达`）—— 前序公专/申论数据可能已写入旧值
  - ❌ 不得执行 `ALTER TABLE` 或任何 DB 结构变更
  - ❌ 不得删除 `知觉速度与准确性`（语料中 0 出现，但可能是历史数据或规划中的分区，删除会破坏既有行）
  - ❌ 不得改动 `shenlun_subcategory` / `gongzhuan_subcategory` 的 Enum

  **Recommended Agent Profile**：
  - **Category**：`quick`
    - Reason：3 处字符串列表各加 1 个值，边界极清晰。真正的风险在「不要动其他东西」，而非编码难度
  - **Skills**：`[]`

  **Parallelization**：
  - **Can Run In Parallel**：YES
  - **Parallel Group**：Wave 1（与 1,2,3,5,6 并行；与任务 3 同改 `question_import.py` 但不同行，Wave 1 内串行执行以避免编辑冲突）
  - **Blocks**：11, 15, 16
  - **Blocked By**：None

  **References**：

  *API/Type References（枚举权威定义，两处必须一致）*：
  - `backend/app/models/models.py:188-192` — `QuestionBank.xingce_subcategory`：`Enum("政治理论","常识判断","言语理解与表达","数量关系","判断推理","资料分析","知觉速度与准确性","常识","速度与知觉训练","语言理解与表达","无")`
  - `backend/app/models/models.py:950-954` — `QuestionDetailCategory.xingce_subcategory`：同上 11 值
  - `backend/app/api/v1/question_import.py:242-246` — `VALID_SUBCATEGORY_NAMES`：`{1:[7值], 2:[5值], 3:[3值]}`，注释写明「与 `question_classifier.SUB_CATEGORY_IDS` 保持一致」

  *Cross-check References*：
  - `backend/app/services/question_classifier.py` — `SUB_CATEGORY_IDS` 是**第三个**必须同步的位置；注释已声明三处一致性要求。**必须核对该处是否也缺 `科学推理`**
  - `backend/app/services/question_classifier.py` 的 `detect_subcategory_enhanced()` — 分区推断引擎，其输出须落在 `VALID_SUBCATEGORY_NAMES` 内

  *实测证据（本任务的事实依据）*：
  - 分区词频：`常识判断` 57 / `言语理解与表达` 55 / `判断推理` 55 / `资料分析` 57 / `数量关系` 54 / `政治理论` 24 / **`科学推理` 3**
  - 分节数分布：5 节 57 份 / 6 节 27 份 / 7 节 1 份

  **WHY Each Reference Matters**：
  - **三处必须同步**（`models.py:188` / `models.py:950` / `question_import.py:243`，外加 `question_classifier.SUB_CATEGORY_IDS`）。前序 README 的根因表第一条就是「`question_bank.type_id` 与 `question_detail_category.question_type_detail` 分裂 → 122 道错位」，本任务若只改一处就等于制造新的分裂
  - `question_classifier.py` 的注释「与 `question_classifier.SUB_CATEGORY_IDS` 保持一致」是**既有代码自己写下的约束**，必须遵守

  **Acceptance Criteria**：

  - [ ] `models.py:188` 的 Enum 列表含 `"科学推理"`
  - [ ] `models.py:950` 的 Enum 列表含 `"科学推理"`
  - [ ] `question_import.py:243` 的列表含 `"科学推理"`
  - [ ] `question_classifier.SUB_CATEGORY_IDS` 含 `科学推理`（若该常量存在）
  - [ ] **其余 11 个值逐一未变** —— `git diff` 中只允许出现 `+ "科学推理"` 一类的新增，不得有 `-` 行
  - [ ] 无任何 `ALTER TABLE` 语句
  - [ ] `sub_categories` 表若为镜像则已幂等补行，重复执行 2 次行数不变
  - [ ] `python -c "from app.models.models import QuestionBank"` 导入无异常

  **QA Scenarios**：

  ```
  Scenario: 三处枚举同步且无副作用（成功路径）
    Tool: Bash
    Preconditions: 无
    Steps:
      1. cd D:\砺安题库\砺安题库\backend
      2. python -c "from app.models.models import QuestionBank, QuestionDetailCategory; a=set(QuestionBank.__table__.c.xingce_subcategory.type.enums); b=set(QuestionDetailCategory.__table__.c.xingce_subcategory.type.enums); assert a==b; assert '科学推理' in a; print(sorted(a))"
      3. 断言退出码 0，输出含 科学推理
      4. python -c "from app.api.v1.question_import import VALID_SUBCATEGORY_NAMES as V; assert '科学推理' in V[1]; print(V[1])"
      5. git diff -- backend/app/models/models.py  断言无以 "- " 开头的枚举删除行
    Expected Result: 两处 model Enum 集合完全相等且含 科学推理；VALID_SUBCATEGORY_NAMES[1] 含该值；git diff 只有新增
    Failure Indicators: 集合不相等（制造新的事实来源分裂）；diff 出现删除行（旧值被误删）
    Evidence: evidence/task-4-enum-sync.txt

  Scenario: 含科学推理的卷可正确归类（失败路径演练）
    Tool: Bash
    Preconditions: 探针已定位 3 套含 科学推理 的卷
    Steps:
      1. 从 corpus_manifest.json 取出含 科学推理 的 3 套卷名
      2. python backend/scripts/verify_xingce_regression.py --only "<卷名>" --out tmp/g2
      3. 断言输出中该卷的分节表出现 科学推理 行，且其题号区间非空
      4. 断言该分区题目数 == 该区间 count 之和
    Expected Result: 3 套卷的科学推理分区被完整识别，不再退化为 无
    Failure Indicators: 科学推理 分节缺失或题号区间为空 → 分类链路未生效
    Evidence: evidence/task-4-kexue-tuilii.txt
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-4-enum-sync.txt` — 两处 Enum 集合打印 + VALID_SUBCATEGORY_NAMES + git diff 摘要
  - [ ] `evidence/task-4-kexue-tuilii.txt` — 3 套卷科学推理分区识别结果

  **Commit**：YES
  - Message：`feat(xingce): add 科学推理 to xingce subcategory enums (3 locations)`
  - Files：`backend/app/models/models.py`、`backend/app/api/v1/question_import.py`、`backend/app/services/question_classifier.py`

- [ ] 5. 考点词表规范化规格 + 461 token 分类清单

  **为什么需要**：实测行测答案解析 **100% 覆盖** `【考点】`，共 **461 个不同 token、16,051 次实例**（均值 121/卷）。这是行测**独有的免费增值**（申论/公专答案解析均无此字段）。但它有两个必须先解决的问题，否则直接入库会污染知识点库：
  1. **层级化路径**：`中心理解题-关联词-转折` 是 3 层路径，现有 `knowledge_point` 表是平铺的
  2. **省份私有考点**：`江苏特色-综合资料`（97 次）—— 直接入库会产生 24 套互不相同的省级私有知识点

  **What to do**：
  - 产出**规格文档**（不是代码），落 `solve_problems_files/行测考点词表规范.md`
  - 规格须定义：
    - **层级拆解规则**：以 `-` 为分隔符拆成 path，`中心理解题-关联词-转折` → 3 级节点；根节点（如 `中心理解题`）作为父，其子为叶子
    - **省份私有值归一化**：`^(江苏|北京|广东|…|国考|多省)特色[-－]?` 前缀剥离 → 映射到全局节点；剥离后若全局不存在，挂到「省份变体」父节点下并打标，**不与全局节点混同**
    - **同义归并表**：461 token 中语义重复的合并（如 `综合资料` 与 `文字资料` 与 `统计表`/`统计图` 的关系需明确定义）
    - **长尾策略**：74 个 token 出现 ≤2 次、34 个仅 1 次 —— 明确「出现 1 次的 token 是否入库」的判据（前序经验：「关键词表完备性靠语料穷举，不靠推理完备」→ 建议全部入库但打低频标）
    - **落库映射**：复用 `knowledge_point` 表 + `question_knowledge` 关联表，**不新建表**；层级用 `parent_id` 或路径字段承载（须先核对 `knowledge_point` 实际列结构）
  - 产出**完整分类清单**（461 行，逐 token 标注：出现次数、所属分区、层级拆解结果、归一化目标、是否入库），落 CSV/JSON 供任务 10 直接消费
  - 校验：每个 token 都能从答案解析原文定位到至少一个题号

  **Must NOT do**：
  - ❌ 不得新建表承载层级（必须复用 `knowledge_point`）
  - ❌ 不得在此任务写库（本任务只出规格 + 清单，落库在任务 10）
  - ❌ 不得丢弃任何 token（即使只出现 1 次），除非规格中明确给出丢弃判据并说明理由
  - ❌ 不得凭推测扩充词表 —— 只允许基于实测 461 token

  **Recommended Agent Profile**：
  - **Category**：`deep`
    - Reason：需要从 16,051 次实例中归纳出层级结构、识别语义同义簇、界定省份私有值边界 —— 是分类学判断而非机械转换；且错误的归并会永久污染知识点库
  - **Skills**：`[]`
  - **Skills Evaluated but Omitted**：
    - `ultrabrain`：省略 —— 该类别用于"目标明确但逻辑极重"的题；本任务边界清晰（461 个 token 的归类），`deep` 的自主研究模式更合适

  **Parallelization**：
  - **Can Run In Parallel**：YES
  - **Parallel Group**：Wave 1（与 1,2,3,4,6 并行）
  - **Blocks**：10
  - **Blocked By**：None（不依赖任务 1，可直接扫 `答案解析` PDF）

  **References**：

  *API/Type References（落库目标结构）*：
  - `knowledge_point` 表（实测 126 行）— 须先 `PRAGMA table_info(knowledge_point)` 确认是否有 `parent_id`/`path`/`level`/`subject_id` 列；若无，规格须给出用 `parent_id` 自引用的承载方案
  - `question_knowledge` 表（实测 2,292 行）— 关联表，字段 `question_id` / `knowledge_point_id`
  - `backend/app/services/question_classifier.py` — `classify_with_db()` 是既有考点关联入口。规格须说明新树如何与之共存（是替换其词表，还是并入）

  *Pattern References（考点抽取的既有实现）*：
  - `backend/app/api/v1/question_import.py:277-306` `_link_knowledge_points()` — 既有考点关联函数，**幂等、不 commit、异常不阻断**的既有约定必须继承
  - `backend/app/api/v1/question_import.py:4578` / `:4593` / `:4711` / `:4725` — `question.xingce_subcategory` 与 `detail.xingce_subcategory` 的**双写点**，考点若也双写须同批考虑

  *实测数据（本任务的输入）*：
  - 461 token / 16,051 实例 / 85 卷全覆盖（min 90、max 135、avg 121）
  - 高频 TOP20：综合资料749、前后呼应735、词的辨析-搭配对象653、实词填空426、混搭填空398、成语填空316、文字资料309、中心理解题-主题词252、重要文件248、常规解题方法234、经济建设228、重大会议及讲话225、补充论据200、综合分析198、关联关系-并列关系193、和差倍比问题190、常规问法185、现期比重177、定义-方式目的176、一般增长率172、普通篇章161、统计表156
  - 长尾：74 个 token ≤2 次，34 个 = 1 次
  - 省份私有：`江苏特色-综合资料` 97 次

  **WHY Each Reference Matters**：
  - `knowledge_point` 的实际列结构决定层级能否落地。**若它没有 `parent_id`，则层级方案必须换设计** —— 这是本任务最关键的前置核对，猜错会导致任务 10 返工
  - `_link_knowledge_points()` 是既有唯一考点关联实现。461 token 若另写一套关联逻辑，就违反 G6「禁止新建」
  - 实测高频 token 清单是规格的**唯一事实依据**，不得用推理补充

  **Acceptance Criteria**：

  - [ ] `solve_problems_files/行测考点词表规范.md` 存在，含层级拆解、省份归一化、同义归并、长尾策略、落库映射 5 个章节
  - [ ] 分类清单含 **461 行**，每行有：token、出现次数、所属分区、层级拆解、归一化目标、是否入库
  - [ ] `PRAGMA table_info(knowledge_point)` 结果记录在规格中，并据此确定层级承载方案
  - [ ] 省份私有 token 全部有明确归一化目标（无一遗漏、无一标记为"待定"）
  - [ ] 长尾 token（≤2 次）的处置判据明确成文
  - [ ] 随机抽 20 个 token 从清单反查答案解析原文，**100% 能定位到题号**
  - [ ] 规格明确说明与 `question_classifier.classify_with_db()` 的共存关系

  **QA Scenarios**：

  ```
  Scenario: 清单完整且可反查（成功路径）
    Tool: Bash
    Preconditions: 已提取 461 token
    Steps:
      1. 断言清单行数 == 461
      2. python -c 随机抽 20 个 token，逐个在答案解析全集中 grep「【考点】」上下文
      3. 断言 20/20 均能定位到至少一个题号
      4. 断言清单中"是否入库=否"的行数 == 0（除非规格给出丢弃判据）
      5. 断言所有含"江苏特色"或其他省名前缀的 token 均有非空"归一化目标"
    Expected Result: 461 行齐全；20/20 可反查；无省份私有值悬空
    Failure Indicators: 抽样反查失败 → 清单与真实语料脱节，任务 10 会写入脏数据
    Evidence: evidence/task-5-token-inventory.txt

  Scenario: 层级承载方案不成立则必须显式失败（失败路径）
    Tool: Bash
    Preconditions: 已 PRAGMA table_info(knowledge_point)
    Steps:
      1. 断言 knowledge_point 含 parent_id 或 path 列
      2. 若不含，断言规格中给出了明确的替代承载方案（而非留空）
      3. 断言规格中的方案不要求新建表（Must NOT Have 约束）
    Expected Result: 层级方案在"不新建表"约束下可落地；若无 parent_id 则规格给出自引用/路径前缀等替代
    Failure Indicators: 方案要求新建表 → 违反 G6，任务 5 判定失败
    Evidence: evidence/task-5-hierarchy-design.txt
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-5-token-inventory.txt` — 461 行清单 + 20 抽样反查结果
  - [ ] `evidence/task-5-hierarchy-design.txt` — `knowledge_point` 列结构 + 层级承载方案论证

  **Commit**：YES
  - Message：`docs(xingce): knowledge-point taxonomy spec for 461 tokens`
  - Files：`solve_problems_files/行测考点词表规范.md`、`backend/data/xingce_kao_points.json`

- [ ] 6. 死代码与空目录清理（**已获用户额外授权**）+ 分层建议

  **授权状态（2026-10-03 用户已批准）**：用户 Q4 原定「只清理解析缓存与死代码，不碰业务数据」，现**额外授权执行「死代码 + 空目录」的清理**。
  **仍禁止**：DB 4 份备份（约 430MB）、活跃 DB、312 条卡死 import 记录、非空图片目录。

  **Why 需要**：用户 G8 指出「系统代码文件和数据库文件较多且杂乱」。实测 `backend/app/static/questions/` 有 **~3,100 个按题号命名的目录**，行测全量导入后将再增约 11,000 个 → 目录膨胀已成实际风险。

  **What to do（两阶段）**：

  **阶段 A — 只读盘点（先做，不可跳过）**
  - 产出待清理清单，每条含：绝对路径、占用体积、判定、回滚方式
  - 5 类：缓存 / 死代码死数据 / DB 备份 / 空目录 / `题库/` 分层建议
  - **判定为「禁止动」的必须显式列出**：DB 4 份备份、活跃 DB、312 条 import 记录、非空图片目录

  **阶段 B — 执行清理（仅限已授权两类）**
  - **死代码/死数据**（须先验证为死）：
    - `backend/mineru_1787720440/`、`backend/mineru_1787720560/` — 须**先验证 `D:\mineru-env` 不存在**且 `/api/questions/import/mineru-health` 返回不可用，方可删除
    - `backend/` 根级 4 个 **0 字节** `.db` 占位：`police_exam.db` / `questions.db` / `question_bank.db` / `题库.db` — 须先 grep 全仓确认无任何代码引用这些路径
    - `.pytest_cache` / `__pycache__`（在 .gitignore 内则跳过）
  - **空目录**：`backend/app/static/questions/` 下**确认为空**（`Get-ChildItem` 递归计数 == 0）的目录
  - **清理前必须**：① 落 `git status` 快照；② 复用既有清理脚本范式（`clean_irrelevant_images_v2.py --dry-run` → `--apply`）；③ 清理报告落 `backend/data/audit/`
  - **分层建议（只出建议，不执行）**：`题库/行测` 24 个文件夹完全扁平 → 建议按 `年份/省份` 分层。⚠️ 分层会改变导入脚本相对路径，须先评估与 `题库/申论`、`题库/公安题目（打印）` 既有引用（`verify_parser_regression.py` 硬编码绝对路径）的冲突

  **Must NOT do**：
  - ❌ 不得删除 `backend/data/question_bank.db` 及 4 份备份（用户 Q4，未授权）
  - ❌ 不得删除/修改 312 条卡死 import 记录（业务数据，未授权）
  - ❌ 不得删除 `text_cache.bak_20261001_200518`（前序「全文翻倍」旧文本的证据）
  - ❌ 不得删除 `static/questions/` 下**任何非空目录**（2,583 道题的图片）
  - ❌ 不得重组 `题库/` 目录（只出建议）
  - ❌ 不得跳过阶段 A 直接删（未验证是否为死数据 = 误删）
  - ❌ 不得在验证 `D:\mineru-env` 不存在之前删除 MinerU 目录

  **Recommended Agent Profile**：
  - **Category**：`unspecified-low`
    - Reason：机械性目录/体积统计 + 受限删除。选低自主性配置以降低误删风险；但阶段 A 的「是否为死」判断需谨慎，不可纯机械
  - **Skills**：`[]`

  **Parallelization**：
  - **Can Run In Parallel**：YES
  - **Parallel Group**：Wave 1（与 1,2,3,4,5 并行；**独立于其他任务的文件**，无冲突）
  - **Blocks**：17
  - **Blocked By**：None

  **References**：

  *Pattern References（既有清理范式，必须复用）*：
  - `backend/scripts/clean_irrelevant_images_v2.py`、`backend/fix_irrelevant_images.py`、`backend/clean_questions.py` — **必须复用而非重写**（G6）
  - `solve_problems_files/题目导入四大问题根因分析与解决方案.md` P1.5 — 既有清理范式：先 `--dry-run` 预览再 `--apply`，「先备份再 apply」
  - `backend/data/audit/` — 既有审计输出目录，清理报告落此处

  *实测证据（本任务的输入）*：
  - `backend/data/` 体积：`question_bank.db` 120MB（活跃）、`bak_shenlun_20261002` 113.9MB、`bak_20261001_191550` 113.2MB、`bak_20260826` 58.3MB、`backup_question_bank_pre_type_repair.sqlite` 41MB → **备份合计约 430MB（禁止动）**
  - `backend/app/static/questions/` 子目录实测从 `432` 连续到 `3114`，另有 `1222–1261`、`1290–1359` 等连续段
  - `backend/` 根目录实测 4 个 **0 字节** `.db`：`police_exam.db` / `questions.db` / `question_bank.db` / `题库.db`
  - `question_import_record` 卡死记录：PREVIEW 305 / PARTIAL 6 / PARSING 1 = **312 条（禁止动）**
  - `D:\mineru-env` — 前序实测**不存在**；`question_import.py:4054` `mineru_health()` 为探测入口

  **WHY Each Reference Matters**：
  - 既有清理脚本已处理「推广图」等**业务级**脏数据（前序 P1.5 清理过 3 题 6 图）。本任务只做**死代码与空目录**，必须与业务级清理严格分离 —— 用户只授权了后者之外的两类
  - `verify_parser_regression.py` 的 G1 命令里写了**绝对路径** `题库\公安题目（打印）` → 重组 `题库/` 会直接打断门禁。这是分层建议只能「出建议不能执行」的直接原因
  - `text_cache.bak_20261001_200518` 是铁律 R-1 的实证依据（缓存了「全文翻倍」旧文本），删掉它等于销毁前序教训的证据

  **Acceptance Criteria**：

  **阶段 A**
  - [ ] 盘点清单覆盖 5 类，每条含路径/体积/判定/回滚方式
  - [ ] **禁止动清单**显式列出：DB 4 份备份、活跃 DB、312 条 import 记录、非空图片目录、`text_cache.bak_*`
  - [ ] 产出体积统计：`已清理 X MB / 未清理 Y MB / 禁止动 Z MB`
  - [ ] `题库/` 分层建议含「是否影响既有脚本硬编码路径」的明确结论

  **阶段 B**
  - [ ] 删除前已落 `git status` 快照
  - [ ] MinerU 目录删除**前**已验证 `D:\mineru-env` 不存在 **且** `mineru-health` 不可用
  - [ ] 4 个 0 字节 `.db` 删除**前**已 grep 全仓确认无引用
  - [ ] 空目录删除仅限递归计数 == 0 者；删除前后目录数差 == 删除数
  - [ ] 清理后 `git status` 中**无任何 `.py` / `.vue` / `.json` 业务文件被删**
  - [ ] 清理后断言公专 2583 道题的图片目录仍全部存在
  - [ ] 清理后公专 G1 门禁仍 PASS
  - [ ] 清理报告落 `backend/data/audit/xingce_cleanup_report.md`
  - [ ] 全部 4 份 DB 备份 + 312 条记录仍在

  **QA Scenarios**：

  ```
  Scenario: 阶段 A 盘点完整且禁止动清单齐全（成功路径）
    Tool: Bash
    Preconditions: 无
    Steps:
      1. 断言盘点清单含 5 个类别
      2. 断言「禁止动」清单含 question_bank.db 及 4 份备份
      3. 断言「禁止动」清单含 312 条 import 记录
      4. 断言「禁止动」清单含 text_cache.bak_20261001_200518
      5. 断言「禁止动」清单含所有非空图片目录
    Expected Result: 5 类齐全；禁止动清单 5 项完整
    Failure Indicators: 禁止动清单缺项（清理阶段可能误删）
    Evidence: evidence/task-6-inventory.txt

  Scenario: 死代码删除前验证为死（失败路径 — 防误删）
    Tool: Bash
    Preconditions: 阶段 A 完成
    Steps:
      1. Test-Path D:\mineru-env  断言 == False  ← 未过则中止删除
      2. curl http://localhost:8000/api/questions/import/mineru-health 断言返回不可用
      3. 断言 backend/mineru_1787720440 与 mineru_1787720560 已被删除
      4. 对 4 个 0 字节 .db：grep 全仓确认无引用后删除
      5. 断言 git status 中无 .py/.vue/.json 业务文件被删
    Expected Result: 仅死数据被删，业务文件零删除
    Failure Indicators: D:\mineru-env 存在却已删（误删有效产物）；业务文件出现在 git status 的 D 行
    Evidence: evidence/task-6-deadcode-removed.txt

  Scenario: 空目录清理不伤非空目录（失败路径 — 红线）
    Tool: Bash
    Preconditions: 阶段 B 已执行
    Steps:
      1. 清理前记录 static/questions 下非空目录数，断言 == N
      2. 执行空目录清理
      3. 断言清理后非空目录数仍 == N（一个不少）
      4. 断言公专 2583 道题中至少抽样 20 道的图片目录存在且非空
      5. 断言公专 G1 门禁仍 PASS
      6. 断言 4 份 DB 备份与 312 条记录仍在
    Expected Result: 只删空目录；非空目录一个不少；门禁仍 PASS
    Failure Indicators: 非空目录数减少（误删题目图片 → 公专题库损坏，立即从备份恢复）
    Evidence: evidence/task-6-emptydir-safe.txt
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-6-inventory.txt` — 5 类盘点 + 禁止动清单
  - [ ] `evidence/task-6-deadcode-removed.txt` — 死代码删除前的"为死"验证 + `git status` 快照
  - [ ] `evidence/task-6-emptydir-safe.txt` — 非空目录数前后比对 + G1 门禁

  **Commit**：YES
  - Message：`chore(ops): remove dead MinerU artifacts, empty db placeholders and empty image dirs`
  - Files：`backend/data/audit/xingce_cleanup_report.md`（删除类文件不入 git）

  - [ ] 7. `_route_xingce_sections()` — 行测分节路由（纯新增函数）

  **这是整套方案的地基**。行测的 5~7 个分区（`一、政治理论：` … `六、资料分析：`）是**分区落位、配对安全网、材料归属**三者的共同依据。实测 85/85 题本与 85/85 答案解析**都带分节头**（100% 命中），所以这个函数可以做到零成本、零猜测。

  **What to do**：
  - 在 `backend/app/services/text_parser.py` **新增**（不改动任何既有函数体）：
    ```python
    # 行测分节词表（实测 170 份语料的完整枚举，勿凭推理扩充）
    XINGCE_SECTION_PATTERNS = (
        '政治理论', '常识判断', '常识', '言语理解与表达',
        '数量关系', '判断推理', '科学推理', '资料分析',
    )

    def route_xingce_sections(text) -> Optional[SectionMap]:
        """
        返回 {'sections': [(name, start, end)], 'form': 'numbered'|'paren',
               'materials': [(idx, start, end)]}
        命中 <2 个分节锚点 → 返回 None（走原路径，保证公专/申论零回归）
        """
    ```
  - **锚点正则**（按实测形态，逐字兼容）：
    - `^[ \t]*([一二三四五六七八九十]{1,3})[、.．][ \t]*\s*(政治理论|常识判断|常识|言语理解与表达|数量关系|判断推理|科学推理|资料分析)\s*[：:]?\s*$`
    - **必须容忍「标记与内容同行」** —— 前序铁律经验：「行级正则必须处理标记与内容同行的常态；锚定 `$` 是脆弱假设」（实测公专 docx 曾因 `$` 锚定导致材料污染 4 题）
    - 必须容忍分节序号与词表**不一致**（实测：同一分区在不同卷里序号不同，如 `一、常识判断` 与 `四、常识判断` 都出现过）
  - **安全门槛（保公专/申论零影响，红线）**：仅当**同时命中 ≥2 个行测分节锚点**才返回非 `None`；否则返回 `None` 走原路径。仿申论 v4 §T2 的门槛设计
  - `form` 判别：`numbered` = `（一）（二）` 全角括号材料头（行测资料分析实测形态）；`paren` 备用
  - 输出 `materials`：`（一）（二）…` 独占行在**资料分析分区内**的位置，供任务 9 使用
  - **回归自测**：对 24 个省级文件夹的 85 套题本全部断言：命中分节数 == 探针（任务 1）测得的分节数

  **Must NOT do**：
  - ❌ **不得修改 `extract_question_blocks()` 既有函数体的任何一行**（申论 v4 T3 红线：仅允许新增函数 + 入口分支）
  - ❌ 不得修改 `ContentCleaner`(`:556`) / `_mark_and_split_suspected`(`:2199`) / `_INNER_QN_LINE`(`:2204`)
  - ❌ 不得让新增函数在公专/申论语料上返回非 `None`（≥2 锚点门槛是硬保险）
  - ❌ 不得把分区词表写死为 `VALID_SUBCATEGORY_NAMES` 的引用（那是校验用清单，不是解析用词表；且它含语料中 0 出现的 `知觉速度与准确性`）
  - ❌ 不得在本任务接入调用链（接入在任务 11，避免半成品上线）

  **Recommended Agent Profile**：
  - **Category**：`deep`
    - Reason：正则的"标记与内容同行"容忍、序号不一致容忍、≥2 锚点安全门槛三者需要同时成立，是典型的需要在多约束下求正解的任务；且必须证明对公专/申论零影响
  - **Skills**：`[]`

  **Parallelization**：
  - **Can Run In Parallel**：YES
  - **Parallel Group**：Wave 2（与 8,9,10 并行；同改 `text_parser.py` 但不同区域，**必须新增到文件末尾独立区块**，避免编辑冲突）
  - **Blocks**：11
  - **Blocked By**：1, 2

  **References**：

  *Pattern References（必须照抄其安全门槛设计）*：
  - `solve_problems_files/申论题目导入精准化方案_v4.md` §T2 — `_route_sections()` 的 `SectionMap` 定义与**安全门槛**：「仅当同时命中 ≥2 个申论锚点才返回非 None；否则返回 None 走原路径」。本任务是同一模式的行测版
  - `solve_problems_files/申论题目导入精准化方案_v4.md` §T3 — 接入红线：「不得修改原切分函数体的任何逻辑（仅新增函数 + 入口分支）」
  - `backend/app/services/text_parser.py:556` `ContentCleaner` — 噪声清洗实现参考；注意其 Phase2「选项行豁免」机制对 `（一）（二）` 材料头可能误判，须验证

  *API/Type References*：
  - `backend/app/services/text_parser.py:2199` `_mark_and_split_suspected()` + `:2204` `_INNER_QN_LINE` — 串题检测。行测题号**全卷连续 1..N**，所以 `_INNER_QN_LINE` 的「块内第二题号」判据对行测天然安全；但须验证 `（一）（二）` 不会被误认为题内编号
  - `backend/app/api/v1/question_import.py:4005-4011` — 共享 dispatch。**本任务只提供函数，不接入**

  *实测证据（本任务的规格来源）*：
  - 分节词频（170 份全量）：`一、政治理论` 24 / `一、常识判断` 56 / `二、常识判断` 25 / `四、常识判断` 2 / `一、常识` 1 / `二、言语理解与表达` 55 / `一、言语理解与表达` 4 / `四、言语理解与表达` 1 / `三、数量关系` 54 / `二、数量关系` 5 / `五、判断推理` 24 / `四、判断推理` 55 / `三、判断推理` 6 / `五、科学推理` 3 / `六、科学推理` 1 / `五、资料分析` 57 / `六、资料分析` 27 / `七、资料分析` 1
  - **同一分区序号不一致的实证**：`常识判断` 出现过 `一、/二、/四、` 三种序号；`资料分析` 出现过 `五、/六、/七、` 三种 → **序号绝不能作为分区身份，只能作为呈现**
  - 材料锚点：`（一）（二）…` 全角括号独占行，364 块 / 85 份，分布 {2:1, 3:35, 4:27, 5:7, 6:7, 7:4, 10:2, 12:2}
  - 分区起始形态：`一、 政治理论：`（**`一、` 后有一个空格**，全角冒号结尾）

  **WHY Each Reference Matters**：
  - 申论 v4 的 `_route_sections` 是**同一作者、同一代码库、已被门禁验证过**的模式。行测版照抄其门槛与红线，是保证公专/申论零回归的最短路径（G6）
  - 「同一分区多序号」的实测证据是**本任务最容易踩的坑**：若按序号映射分区，`四、常识判断` 会被误判为第 4 个分区
  - `ContentCleaner` 的 Phase2 选项行豁免必须验证 —— `（一）` 若被当作选项行清洗掉，资料分析材料就丢了

  **Acceptance Criteria**：

  - [ ] `route_xingce_sections()` 以**新增**形式追加在 `text_parser.py` 末尾独立区块
  - [ ] `git diff` 显示 `extract_question_blocks` / `ContentCleaner` / `_mark_and_split_suspected` **函数体零改动**
  - [ ] 对 85 套题本：命中分节数与任务 1 探针结果**逐套相等**
  - [ ] 对 85 套答案解析：同样逐套相等（证明两份文档分节头一致 —— 这是安全网的基础）
  - [ ] 公专 30 份 docx：全部返回 `None`（≥2 锚点门槛生效）
  - [ ] 申论 A+B 组：全部返回 `None`
  - [ ] `（一）（二）` 材料锚点在 85 套题本中被识别，总数 == 364
  - [ ] 至少 3 个用例覆盖「序号不一致仍正确归类」（如 `四、常识判断` → `常识判断`）
  - [ ] 公专 G1 门禁逐项与基线一致（7 项断言）

  **QA Scenarios**：

  ```
  Scenario: 85 套题本分节 100% 命中且与探针一致（成功路径）
    Tool: Bash
    Preconditions: 任务 1 探针已产出 corpus_manifest.json
    Steps:
      1. cd D:\砺安题库\砺安题库
      2. python backend/scripts/verify_xingce_regression.py --assert-sections-match-probe "D:\砺安题库\砺安题库\题库\行测" --out tmp/g2
      3. 断言退出码 0
      4. 断言"85/85 套分节数与探针一致"
      5. 断言"材料锚点总数 == 364"
      6. 断言题本与答案解析逐套分节头序列全等
    Expected Result: 85 套全部命中；题本与答案解析分节头序列逐套全等；材料 364 块
    Failure Indicators: 任一套不一致 → 安全网地基不成立，必须修正后才能进任务 8
    Evidence: evidence/task-7-sections-85.txt

  Scenario: 公专/申论语料返回 None（失败路径 — 红线）
    Tool: Bash
    Preconditions: 无
    Steps:
      1. python -c "import sys;sys.path.insert(0,'backend');from app.services.text_parser import route_xingce_sections as R;print(R('一、 给定材料\n材料1\n二、 作答要求\n1. …'))"
      2. 断言返回 None
      3. 对 backend/tests/ 内全部公专/申论测试语料逐份调用，断言 100% 返回 None
      4. 跑公专 G1，断言 2899 块 / 污染 0 / PASS
    Expected Result: 全部返回 None；G1 七项断言逐项一致
    Failure Indicators: 任一公专/申论语料返回非 None → ≥2 锚点门槛失效，将污染既有链路，必须立刻加严门槛
    Evidence: evidence/task-7-no-regression.txt

  Scenario: 同一分区多序号仍正确归类（边界路径）
    Tool: Bash
    Preconditions: 无
    Steps:
      1. 构造用例文本 "四、 常识判断：\n1. …\n五、 资料分析：\n（一）\n材料…"
      2. 断言 sections[0].name == '常识判断'（而非 '四、常识判断'）
      3. 断言 sections[1].name == '资料分析'
      4. 构造 "一、 政治理论：\n二、 常识判断：" 断言两节均命中
      5. 构造仅 1 个锚点的文本 断言返回 None
    Expected Result: 分区名归一化正确；单锚点返回 None
    Failure Indicators: 分区名带序号前缀（说明未归一化）；单锚点未返回 None（门槛过松）
    Evidence: evidence/task-7-section-key.txt
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-7-sections-85.txt` — 85 套分节命中 + 364 材料 + 双文档分节全等
  - [ ] `evidence/task-7-no-regression.txt` — 公专/申论全 None + G1 七项
  - [ ] `evidence/task-7-section-key.txt` — 多序号归一化用例输出

  **Commit**：YES
  - Message：`feat(xingce): add route_xingce_sections with >=2-anchor safety gate`
  - Files：`backend/app/services/text_parser.py`

- [ ] 8. `_xingce_cross_validate()` — 行测分离配对安全网（本方案核心）

  **这是整套方案存在的理由**。现状：题本(110) 与答案解析(101) 被当作两个独立文档各产一份题目列表，**无配对**。而申论的三方交叉校验（题号+分值+题干指纹）在行测**只剩 1/3**——答案解析既不重复题干也无分值。若上传 2024 题本 + 2025 答案解析，**计数相等也照样全卷配错且无法察觉**。

  **What to do**：
  - 在 `text_parser.py` **新增** `xingce_cross_validate(q_blocks, a_blocks) -> {'questions': [...], 'report': {...}}`
  - **配对主键**：`question_number`（题号）。复用既有 `extract_question_numbers()`（支持 6+ 格式），**禁止新建第三套题号解析**
  - **安全网 = 分节区间对齐**（本任务的核心创新，替代申论的题干指纹）：
    | 校验 | 判据 | 不一致时 |
    |------|------|---------|
    | X-1 分节头序列全等 | 题本分节名序列 == 答案解析分节名序列 | `blocked`，禁止配对 |
    | X-2 分节区间全等 | 每个分节的 `(min_qno, max_qno, count)` 三元组逐一相等 | `blocked`，禁止配对 |
    | X-3 题号连续 | 双方题号序列均连续无跳号/无重复 | 跳号 → 该题 `answer_missing`，**禁止就近填充** |
    | X-4 计数一致 | `len(q_blocks) == len(a_blocks)` | 计数不等**不单独阻断**，但必须输出差集供人工判读 |
    | X-5 答案合理性 | 归一化后 `canonical_answer()` 结果 ∈ 合法集 | 非法则该题 `blocked` |
  - **输出结构**：`question_number` / `content` / `options` / `answer`（归一化）/ `analysis` / `kao_points`（考点，任务 10 消费）/ `section_name` / `material_text` / `confidence` / `blocked` / `block_reasons` / `need_review`
  - **考点携带**（GAP-7）：考点只存在于答案解析，**必须由本环节从 `a_blocks` 取出并挂到合并后的题上**，否则题目永远拿不到考点
  - **复用而非重写**：答案归一化调 `canonical_answer()`；选项解析调 `option_utils`；不得新写
  - `X-4` 的差集必须逐题打印双侧上下文（与任务 1 探针共用输出格式）

  **Must NOT do**：
  - ❌ **不得按顺序盲配**（前序 `_essay_cross_validate` 的注释已明确：「按序配对会把 A 卷答案贴到 B 卷题目上 —— 这类错配计数完全正常，只靠数量校验抓不住」）。必须题号 join
  - ❌ 不得在答案缺失时「就近填充」或用相邻题答案兜底
  - ❌ 不得调用 LLM 兜底（前序经验：回归须离线可复现）
  - ❌ 不得修改 `_essay_cross_validate` / `smart_match_questions_answers` 任何一行
  - ❌ 不得在本任务接入端点（接入在任务 11）
  - ❌ 不得在 `X-1`/`X-2` 失败时降级为「部分配对 + 告警」—— 必须整卷 `blocked`（对齐申论 `blocked` 语义）

  **Recommended Agent Profile**：
  - **Category**：`deep`
    - Reason：这是全方案最核心的新逻辑，需同时满足 5 条校验、与既有 8 级策略链共存、复用 4 个既有单一事实来源函数、且对 11,000 道题零错配；对边界推理要求最高
  - **Skills**：`[]`

  **Parallelization**：
  - **Can Run In Parallel**：YES
  - **Parallel Group**：Wave 2（与 7,9,10 并行；**同改 `text_parser.py`，必须追加到任务 7 的区块之后**，Wave 2 内 7→8 串行以避免编辑冲突）
  - **Blocks**：11
  - **Blocked By**：1, 2

  **References**：

  *Pattern References（必须照抄其防御性设计）*：
  - `backend/app/api/v1/question_import.py:3866-3967` `_essay_cross_validate()` — **本任务的直接模板**。其文档字符串已写明全部设计意图：
    - 「用户硬约束：题目数=正确答案段数 **仅是必要条件**，必须逐题校验，禁止计数相等但错配」
    - 「按序配对会把 A 卷答案贴到 B 卷题目上 —— 这类错配计数完全正常，只靠数量校验抓不住」
    - 「题目卷有这道题，答案卷没有 → **绝不能留空后放行**，那会让用户拿到无答案题」
  - `backend/app/api/v1/question_import.py:3940-3956` — **材料传播铁律**：「解析器只在第一题挂 material_text（省内存），但落库时每道题都要通过 group_id 指向同一份材料。故在此把整批共享的材料补齐到每一题，否则 Q2..QN 会 group_id=0 且材料丢失。**实测漏掉这一步的后果：材料只进第 1 题，其余 3 题在题库里查不到给定资料**」
  - `solve_problems_files/申论题目导入精准化方案_v4.md` §I-1..I-10 — 不变量清单，本任务的 X-1..X-5 是其行测对应物

  *API/Type References（必须复用，禁新建）*：
  - `text_parser.canonical_answer(answer)` — 唯一答案归一化入口（全角→半角、判断词→字母、去分隔符、仅保留 `[A-Z0-9]`）
  - `text_parser.extract_question_numbers()` — 唯一题号提取器（支持 6+ 格式，`question_number VARCHAR(10)` 承载）
  - `text_parser.smart_match_questions_answers()` — 8 级策略链，行测**不需要**它，但**不得删除**
  - `backend/app/services/option_utils.py` — 选项解析工具
  - `backend/app/api/v1/question_import.py:508` — `row.get('答案') or row.get('正确答案') or …` 的多键兜底范式，可用于解析 `N. 正确答案：X` 的等价变体

  *实测证据（输入形态）*：
  - 答案锚点：`{N}. 正确答案：{X}`，行首，85/85 全覆盖
  - 答案解析**不重复题干**（与申论相反 → 题干指纹校验不可用）
  - 答案解析**无分值**（与申论相反 → 分值校验不可用）
  - 答案解析**分节头与题本完全一致**（实测两者分节词表完全相同）→ X-1/X-2 可行
  - 选项变体：`A.2项`（组合题元选项）、`A.`（纯图片，文字为空）、`A.①②`
  - 多选答案形态：`故本题正确答案为AC。`（实测于 `test_realworld_formats.py:51`）

  **WHY Each Reference Matters**：
  - `_essay_cross_validate()` 是**同一代码库中已被门禁验证的分离型配对实现**。行测版必须继承其全部防御性设计（特别是「答案缺失绝不放行」与「材料传播补齐」），这两条都是前序用真实故障换来的教训
  - 「材料传播」铁律直接对应行测资料分析：4 块材料 × 364 次，若漏传播，**每套卷的材料只会进第 1 题**，其余全部 `group_id=0`
  - `canonical_answer` 是唯一归一化入口：行测答案有 `A、B、C`、`AB`、`A，B`、`AC` 等多种写法，自写正则必然漏（这正是前序 780 道多选答案被截断成单选的根因）
  - `extract_question_numbers` 明令「禁止新建第三套题号解析」—— 直接违反 G6

  **Acceptance Criteria**：

  - [ ] `xingce_cross_validate()` 以**新增**形式追加，`git diff` 显示 `_essay_cross_validate` / `smart_match_questions_answers` 零改动
  - [ ] 安徽行测试跑：题本 110 / 答案 101，输出差集题号 + 双侧上下文，与任务 1 探针结论**一致**
  - [ ] **X-1/X-2 在 85 套上全部通过**（分节头序列全等 + 分节区间全等）
  - [ ] 配对率 ≥ 0.99
  - [ ] 答案覆盖率 100%（`X-3` 下不允许有静默缺失）
  - [ ] **考点成功携带**：试点卷每题 `kao_points` 非空率 ≥ 98%
  - [ ] **材料传播正确**：资料分析块内**每一题**都拿到 `material_text`（不是只有第 1 题）
  - [ ] 负向用例：人为把 2025 答案解析配 2024 题本，断言 **X-1 或 X-2 必然触发 blocked**（这是本任务的价值证明）
  - [ ] 公专 G1 门禁逐项与基线一致
  - [ ] 行测 G2 门禁 `--compare` 通过

  **QA Scenarios**：

  ```
  Scenario: 正确配对 85 套（成功路径）
    Tool: Bash
    Preconditions: 任务 7 完成，探针可用
    Steps:
      1. python backend/scripts/verify_xingce_regression.py --cross-validate "D:\砺安题库\砺安题库\题库\行测" --out tmp/g2
      2. 断言退出码 0
      3. 断言 "X-1 分节头序列全等: 85/85 通过"
      4. 断言 "X-2 分节区间全等: 85/85 通过"
      5. 断言 配对率 >= 0.99
      6. 断言 答案覆盖率 == 100.0
      7. 断言 考点携带率 >= 98.0
      8. 断言 材料传播完整率 == 100.0（资料分析块内每题均有 material_text）
    Expected Result: 8 项断言全过
    Failure Indicators: X-1/X-2 有失败套（安全网不可靠，禁止进任务 11）；材料传播 < 100%（复现前序「材料只进第 1 题」故障）
    Evidence: evidence/task-8-cross-validate-85.txt

  Scenario: 错配年份必然被拦截（失败路径 — 核心价值证明）
    Tool: Bash
    Preconditions: 无
    Steps:
      1. python -c 载入 2025 国考地市级题本 + 2024 国考地市级答案解析，调用 xingce_cross_validate
      2. 断言 report 中 blocked_count > 0
      3. 断言 block_reasons 至少含 'section_interval_mismatch' 或 'section_sequence_mismatch'
      4. 断言返回的 questions 全部带 blocked=True（无一带答案放行）
      5. 断言总耗时 < 5 秒
    Expected Result: 错配被 X-1/X-2 精确拦截，无一带答案放行
    Failure Indicators: 任一题 blocked=False（说明存在部分盲配 → 这正是本任务要消灭的错配模式，属最严重失败）
    Evidence: evidence/task-8-mismatch-blocked.txt

  Scenario: 答案缺失绝不放行（边界路径）
    Tool: Bash
    Preconditions: 无
    Steps:
      1. 构造 q_blocks 含题号 1,2,3；a_blocks 仅含 1,3（模拟缺 2）
      2. 断言 题号 2 的 answer == '' 且 block_reasons 含 'answer_missing_for_question'
      3. 断言 题号 2 的 blocked == True
      4. 断言 题号 1 与 3 正常配对且 blocked == False
      5. 断言 report.only_in_questions == ['2']
    Expected Result: 缺失题被显式标记并阻断；其余题正常
    Failure Indicators: 题号 2 拿到了题号 3 的答案（就近填充 → 前序明令禁止的错配模式）
    Evidence: evidence/task-8-answer-missing.txt
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-8-cross-validate-85.txt` — 85 套 X-1..X-5 全部指标
  - [ ] `evidence/task-8-mismatch-blocked.txt` — 错配年份拦截证明
  - [ ] `evidence/task-8-answer-missing.txt` — 答案缺失阻断用例

  **Commit**：YES
  - Message：`feat(xingce): add section-interval cross-validation for question/answer pairing`
  - Files：`backend/app/services/text_parser.py`

  - [ ] 9. 资料分析材料锚点 — `（一）（二）` → `question_groups`

  **为什么需要**：行测资料分析是「1 段材料 + 4~5 道题」结构，实测 **85/85 全部存在、364 块**。但既有 `composite_matcher.py` 的 `data_analysis` 触发词是 **`图表`**，而行测材料锚点是**全角括号独占行 `（一）（二）`** → **既有规则完全不命中**。不补则资料分析题的材料丢失，学生答题时看不到给定资料。

  **What to do**：
  - 在 `backend/app/services/composite_matcher.py` **追加**规则（⚠️ 只追加，不改动既有 4 条规则与 `_MATERIAL_KEYWORDS`）
  - 新增规则：全角括号独占行 `（一）…（十二）` 且位于**资料分析分区内** → `group_type='data_analysis'`
  - **隔离性论证（必须写进代码注释）**：`data_analysis` 当前 **0 行**，且既有触发词是 `图表`；新规则用 `（一）` 全角括号，两条规则**不可能同时命中**同一文本 → 公专/申论零回归
  - 复用既有 `_MATERIAL_KEYWORDS`（已含 `图表`/`资料`）作为**兜底**，但优先级低于新规则
  - 材料正文边界：`(一)` 锚点行之后 → 下一个 `(二)` 锚点行之前（或下一个题号之前）
  - 落库形态（**复用既有表，不新建**）：
    - `question_groups`：`group_type='data_analysis'` / `subject='行测'` / `shared_content=材料全文` / `title='资料分析第N段'` / `source=卷名`
    - 每道小题：`question_bank.group_id=<组ID>` / `question_level=2` / `sort_order=<题号序>` / `question_number=<原题号>`
  - ⚠️ **材料图**：若材料含图片，必须走既有 `shared_content_images` + `app/services/image_filters.py`（QR/推广图过滤），**不得新建机制**

  **Must NOT do**：
  - ❌ 不得修改既有 4 条规则（`material`/`scenario`/`passage`/`range`）与 `_MATERIAL_KEYWORDS`（L141）
  - ❌ 不得修改 `composite_matcher` 的既有 `group_type` 判定逻辑（L73 / L277-280）
  - ❌ 不得新建题组表
  - ❌ 不得让新规则在非资料分析分区生效（`（一）` 在申论里也可能出现 —— 必须用分区限定）
  - ❌ 不得在每题重复存一份材料全文（前序铁律：只在组上存一份，`group_id` 关联；实测漏传播的后果是「材料只进第 1 题」）

  **Recommended Agent Profile**：
  - **Category**：`deep`
    - Reason：需在不影响既有 4 条规则的前提下追加第 5 条，并证明两条规则互斥、且在申论 `（1）` 全角括号场景下不误命中 —— 边界推理要求高
  - **Skills**：`[]`

  **Parallelization**：
  - **Can Run In Parallel**：YES
  - **Parallel Group**：Wave 2（与 7,8,10 并行；本任务改 `composite_matcher.py`，与其他任务不同文件，无冲突）
  - **Blocks**：11
  - **Blocked By**：1, 2

  **References**：

  *Pattern References（规则表的既有结构）*：
  - `backend/app/services/composite_matcher.py:32-46` — **规则集定义**：`(规则名, 正则, 静态 group_type)` 三元组列表。新规则以**完全相同的形态**追加
  - `backend/app/services/composite_matcher.py:44` — `('material', re.compile(r'^(?:材料|资料)\s*[一二三四五六七八九十\d]+[：:．.]'), 'material')`
  - `backend/app/services/composite_matcher.py:45` — `('scenario', re.compile(r'^根据以下情境'), 'scenario')`
  - `backend/app/services/composite_matcher.py:46` — `('passage', re.compile(r'^(?:阅读以下文章|阅读下面|给定资料)'), 'passage')`
  - `backend/app/services/composite_matcher.py:58-75` — 规则命中后的 `group_type` 二次判定（L73 `gtype = 'scenario' if '情境' in … else 'material'`）
  - `backend/app/services/composite_matcher.py:141` — `_MATERIAL_KEYWORDS = ['材料','情境','资料','文章','图表','案例','背景','阅读以下','给定资料']`
  - `backend/app/services/composite_matcher.py:277-280` — **`data_analysis` 的既有触发路径**：`for kw, gt in [('情境','scenario'),('图表','data_analysis'),('文章','passage'),('资料','material')]` → **行测材料含 `资料` 二字，会被误判为 `material`！** 这是必须处理的冲突
  - `backend/app/services/composite_matcher.py:210-211` — 启发式兜底：`material_kw and not is_objective`

  *API/Type References（落库目标）*：
  - `backend/app/models/models.py` `QuestionGroup`（L~950 区段）— `__tablename__='question_groups'`；`group_type String(20) default='material'`（注释已含 `data_analysis`）；`subject String(20)`；`shared_content Text`；`shared_content_images Text`（JSON 串）；`title String(200)`；`source String(50)`；`Index('idx_qgroup_subject', subject)`
  - `backend/app/api/v1/question_import.py:1934` `_get_or_create_shenlun_material_group()` — **申论的题组落库实现，行测版必须照抄其幂等与去重策略**
  - `question_bank` 列：`group_id INTEGER default 0`、`question_level INTEGER default 1`、`sort_order INTEGER default 0`、`question_number VARCHAR(10)`

  *实测证据*：
  - 材料锚点 `（一）（二）` 全角括号独占行，364 块 / 85 份，分布 {2:1, 3:35, 4:27, 5:7, 6:7, 7:4, 10:2, 12:2}
  - 材料正文含 `资料` 二字（如「2023年一季度，我国外贸进出口总额为9.89万亿元」）→ **与既有 `material` 规则的 `资料` 关键词冲突**
  - 材料块紧跟前一分区最后一题的选项之后（实测第 5 题 D 选项后直接跟 `（四）`）
  - 页边界会切断材料正文

  **WHY Each Reference Matters**：
  - `composite_matcher.py:277-280` 的 `资料→material` 映射是**真实冲突点**：行测材料正文必然含「资料」，若新规则不加分区限定，资料分析材料会被错标为普通 `material` 题组 → 前端展示成申论式材料题，形态错误
  - `_get_or_create_shenlun_material_group()` 是**已验证的题组落库范式**，含幂等与去重；行测另写一套就是 G6 违规
  - `shared_content_images` 注释已写明「材料图复用现有 `/static/questions/` 图片管线（独立题组目录），导入时**强制经过 `image_filters.py` 无关图过滤**（QR/推广图检测）」→ 必须走，不得自建

  **Acceptance Criteria**：

  - [ ] 新规则以 `(name, re.compile(...), 'data_analysis')` 形态追加到规则表
  - [ ] `git diff` 显示既有 4 条规则与 `_MATERIAL_KEYWORDS` **零改动**
  - [ ] 85 套题本：材料块总数 == **364**，且全部 `group_type='data_analysis'`
  - [ ] 资料分析题目 `group_id > 0` 且 `question_level == 2`
  - [ ] **材料传播完整率 100%**：块内每题均能通过 `group_id` 查到 `shared_content`
  - [ ] 公专 21 个既有题组（4 material + 17 scenario）**行数与内容零变化**
  - [ ] 申论 A+B 组：题组判定与迁移前完全一致
  - [ ] 公专 G1 门禁逐项一致
  - [ ] 代码注释中含「与既有 `图表` 规则互斥、`data_analysis` 原 0 行」的隔离性论证

  **QA Scenarios**：

  ```
  Scenario: 364 块材料全部正确归组（成功路径）
    Tool: Bash
    Preconditions: 任务 7 分节路由可用
    Steps:
      1. python backend/scripts/verify_xingce_regression.py --assert-materials "D:\砺安题库\砺安题库\题库\行测" --out tmp/g2
      2. 断言 材料块总数 == 364
      3. 断言 data_analysis 归组占比 == 100%（无一被判为 material）
      4. 断言资料分析题 group_id>0 占比 == 100%
      5. 断言 block 内每题经 group_id 查得到非空 shared_content（取 20 块抽样）
    Expected Result: 364 块全归 data_analysis；抽样块内每题都能查到材料
    Failure Indicators: 出现 group_type='material' 的行测题组 → 分区限定失效，资料分析被误标
    Evidence: evidence/task-9-materials-364.txt

  Scenario: 既有 21 个题组零变化（失败路径 — 回归红线）
    Tool: Bash
    Preconditions: 迁移前已快照 question_groups
    Steps:
      1. 快照 select group_type, count(*) from question_groups group by 1  → 基线 {material:4, scenario:17}
      2. 跑本任务
      3. 断言 material 仍 == 4 且 scenario 仍 == 17
      4. 断言 21 行的 id / shared_content 摘要与基线逐行一致
      5. 断言 public 21 行未被 UPDATE（比对 updated 前后）
    Expected Result: 既有题组逐字段不变
    Failure Indicators: 任一行内容变化 → 既有公专题组被污染，立即回滚
    Evidence: evidence/task-9-no-regression.txt

  Scenario: 申论全角括号不误命中（边界路径）
    Tool: Bash
    Preconditions: 无
      1. 构造申论风格文本「一、 作答要求\n（1）根据"给定资料1"…（15分）\n（2）…（20分）」并置于**非资料分析分区**
      2. 调用 composite_matcher，断言 data_analysis 归组数 == 0
      3. 断言该文本仍走原有 material/passage 判定
      4. 构造行测风格「六、 资料分析：\n（一）\n2023年一季度…\n（二）\n…」断言归为 data_analysis
    Expected Result: 申论 `（1）` 不触发新规则；行测 `（一）` 触发
    Failure Indicators: 申论被误判为 data_analysis → 分区限定不足
    Evidence: evidence/task-9-shenlun-guard.txt
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-9-materials-364.txt` — 364 块归组结果 + 传播抽样
  - [ ] `evidence/task-9-no-regression.txt` — 既有 21 题组逐字段比对
  - [ ] `evidence/task-9-shenlun-guard.txt` — 申论/行测括号用例

  **Commit**：YES
  - Message：`feat(xingce): recognise 资料分析 material blocks via full-width paren anchors`
  - Files：`backend/app/services/composite_matcher.py`

- [ ] 10. 考点抽取与层级化落库

  **What to do**：
  - 从答案解析块抽取考点：锚点 `【考点】` 后至下一个 `【考点】` 或块尾；分隔符 `[,，、;；]`（实测三逗号并存）
  - 按任务 5 产出的 `backend/data/xingce_kao_points.json` 清单做**归一化**（层级拆解 + 省份私有值剥离 + 同义归并）
  - 落库：**复用** `knowledge_point` 表（层级按任务 5 确定的方案）+ `question_knowledge` 关联表
  - 关联写库复用既有 `_link_knowledge_points()` 的约定：**幂等、不 commit、异常不阻断导入**
  - ⚠️ **双写点**：考点若也需与分区一致，须检查是否要同步写 `question_detail_category`（前序教训：`type_id` 与 `detail` 分裂导致 122 道错位）
  - 幂等迁移脚本 `backend/scripts/migrate_xingce_knowledge_points.py`（`--dry-run` / `--apply` / `--rollback`）

  **Must NOT do**：
  - ❌ 不得新建考点表
  - ❌ 不得丢弃任何已列入清单的 token
  - ❌ 不得在本任务写 `question_bank`（落库在任务 16 的导入流程；本任务只建知识点树 + 提供关联函数）
  - ❌ 不得修改 `question_classifier.classify_with_db()` 的既有判定逻辑（只能并入，不能替换）

  **Recommended Agent Profile**：
  - **Category**：`deep`
    - Reason：层级承载方案（受 `knowledge_point` 实际列结构约束）、省份私有值剥离、双写点一致性、与既有分类器共存 —— 四者耦合
  - **Skills**：`[]`

  **Parallelization**：
  - **Can Run In Parallel**：YES
  - **Parallel Group**：Wave 2（与 7,8,9 并行；本任务改考点相关文件，不与 7/8 的 `text_parser.py` 区块冲突）
  - **Blocks**：11
  - **Blocked By**：2, 5

  **References**：

  *Pattern References*：
  - `backend/app/api/v1/question_import.py:277-306` `_link_knowledge_points()` — **必须复用的关联范式**：逐题 `classifier.classify_with_db()` → `db.add(QuestionKnowledge(...))` → **不 commit** → 返回成功计数；`except Exception` 仅 `logger.warning` 不阻断
  - `solve_problems_files/申论题目导入精准化方案_v4.md` §T9 M-3 — 「`models.py` 的 `Enum(...)` 对齐实际 `VARCHAR`（实测 DB 为 `VARCHAR(5)`，model 声明 `Enum` → 漂移）」。**本任务须先核对 `knowledge_point` 是否有同类漂移**
  - `backend/app/services/question_classifier.py` — `classify_with_db()` / `detect_subcategory_enhanced()` / `SUB_CATEGORY_IDS`

  *API/Type References*：
  - `knowledge_point`（实测 126 行）— **必须先 `PRAGMA table_info`**，层级承载取决于是否有 `parent_id`/`path`/`level`
  - `question_knowledge`（实测 2,292 行）— 字段 `question_id` / `knowledge_point_id`
  - `question_detail_category` — `question_type_detail Enum(...)`（`models.py:971`）与 `xingce_subcategory Enum(...)`（`models.py:950`），前序分裂教训的相关表

  *实测证据*：
  - `【考点】` 85/85 覆盖；461 token / 16,051 实例 / 均值 121 每卷
  - 分隔符实测：`政治建设,重大会议及讲话` 用**半角逗号**
  - 层级实证：`中心理解题-关联词-转折`、`词的辨析-搭配对象`、`江苏特色-综合资料`
  - 长尾：74 个 ≤2 次，34 个 =1 次

  **WHY Each Reference Matters**：
  - `_link_knowledge_points()` 的「不 commit + 异常不阻断」是前序为大批量导入定下的关键约定。11,000 道题的考点关联必须沿用，否则一次异常就会回滚整批
  - §T9 M-3 的 Enum/VARCHAR 漂移是**本项目已发生过的真实事故**：model 声明与 DB 实际不一致。不先 `PRAGMA` 就设计层级，一定踩坑
  - 「双写点」教训来自 README 根因表第 1 条（122 道题型错位），考点若重演同一模式，用户会在错题集看到错的分类

  **Acceptance Criteria**：

  - [ ] `PRAGMA table_info(knowledge_point)` 结果记录在案，层级承载方案据此确定且**不新建表**
  - [ ] 迁移脚本 `--dry-run` 预览待插入知识点数，**不写库**
  - [ ] `--apply` 后 `select count(*) from knowledge_point` 增长数 == 清单中「是否入库=是」的行数
  - [ ] 重复 `--apply` 两次，知识点总数不变（幂等）
  - [ ] 层级验证：`中心理解题` 节点存在且有子节点 `关联词-转折` 的父指向
  - [ ] 省份私有值：`江苏特色-综合资料` **未**以省级私有名入库（或已按规格剥离归一）
  - [ ] 抽取函数对 85 套答案解析的考点抽取率 == 100%
  - [ ] 公专 126 个既有知识点**逐字段不变**
  - [ ] `question_knowledge` 既有 2,292 行不变
  - [ ] `--rollback` 后知识点数与关联数还原

  **QA Scenarios**：

  ```
  Scenario: 461 token 全部落库且层级正确（成功路径）
    Tool: Bash
    Preconditions: 任务 5 清单就绪，DB 已备份
    Steps:
      1. python backend/scripts/migrate_xingce_knowledge_points.py --dry-run  断言输出待插入数 == 清单「入库=是」行数
      2. python backend/scripts/migrate_xingce_knowledge_points.py --apply  断言退出码 0
      3. 断言 knowledge_point 增量 == 预期
      4. 断言「中心理解题」存在且其子孙链可达「关联词-转折」
      5. 连续 --apply 两次，断言总数不变
      6. 断言既有 126 点与 2292 关联行未变
    Expected Result: 461 token 全部落库；层级链正确；幂等；既有数据零变化
    Failure Indicators: 既有 126 点变化 → 污染公专考点；幂等失效
    Evidence: evidence/task-10-kao-migrate.txt

  Scenario: 省份私有值不污染全局树（边界路径）
    Tool: Bash
    Preconditions: 已 apply
    Steps:
      1. 断言 select count(*) from knowledge_point where name like '%江苏特色%' == 0（或 == 规格允许的降级标记数）
      2. 断言「综合资料」节点存在且其关联数 > 0（江苏卷考点已归一到它）
      3. 抽取江苏 2025 C 类卷，断言其资料分析题的考点包含「综合资料」而非「江苏特色-综合资料」
      4. 断言未产生 24 个互不相同的省级私有知识点
    Expected Result: 省级私有值归一到全局节点，全局树不被省级噪声污染
    Failure Indicators: knowledge_point 出现「江苏特色-综合资料」独立节点 → 归一化未生效
    Evidence: evidence/task-10-province-normalize.txt

  Scenario: 抽取覆盖 100% 且异常不阻断（失败路径演练）
    Tool: Bash
    Preconditions: 已 apply
    Steps:
      1. 对 85 套答案解析逐套抽取考点，断言每套抽取数 == 探针测得的【考点】数
      2. 断言 85/85 抽取率 == 100%
      3. 人为构造一段无【考点】的答案解析，断言抽取返回空列表而非抛异常
      4. 断言整体导入未被阻断
    Expected Result: 85 套 100% 抽取；无【考点】时静默返回空，不阻断
    Failure Indicators: 任一套抽取率 < 100%（说明分隔符或边界处理有漏）
    Evidence: evidence/task-10-extract-coverage.txt
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-10-kao-migrate.txt` — 迁移前后知识点/关联行数 + 层级链验证
  - [ ] `evidence/task-10-province-normalize.txt` — 省份私有值归一验证
  - [ ] `evidence/task-10-extract-coverage.txt` — 85 套抽取覆盖率

  **Commit**：YES
  - Message：`feat(xingce): extract and hierarchically store 461 knowledge-point tokens`
  - Files：`backend/scripts/migrate_xingce_knowledge_points.py`、`backend/app/services/text_parser.py`（考点抽取函数区块）

- [ ] 11. `POST /api/questions/import/separate-match-xingce` — 行测专用端点

  **核心设计决策：绝不改动共享 dispatch。** 现有 `separate_match_endpoint`（`question_import.py:3971`）被公专/申论/行测三科目共用，其分流逻辑在 `:4005-4011`。改动它 = 给 2,583 道公专题 + 申论链路引入回归风险。本任务**新建独立端点**，前端按科目路由，共享 dispatch **保持字节级不变**。

  **What to do**：
  - 在 `backend/app/api/v1/question_import.py` **新增**独立路由 `/separate-match-xingce`（不复用现有端点函数体）
  - 入参沿用 `separate-match` 的契约以减少前端分支：`questions_text` / `answers_text` / `paper_name` / `subject_category`
  - 流程：
    1. `extract_question_blocks()` 双侧切分（复用，不改）
    2. `route_xingce_sections()` 双侧分节（任务 7）
    3. `xingce_cross_validate()` 配对 + 5 项校验（任务 8）
    4. 分区落位：`xingce_subcategory`（任务 4 的枚举）
    5. 材料归组：任务 9 的规则
    6. 考点归一：任务 10 的清单
    7. 去重检测：复用 `_get_duplicate_info()`
    8. `blocked` 语义：存在 blocked 题 → 返回 `blocked_count`，**不生成可确认入库的预览**（对齐申论 v4 §T8）
  - 返回结构**必须与现有 `separate-match` 一致**（`status`/`match_rate`/`matched_count`/`total_questions`/`questions`/`unmatched_question_numbers`/`extra_answer_numbers`/`strategy_used`/`details`/`message`），前端无需分支；额外附 `xingce_report` 承载分节区间与校验明细
  - **鉴权**：复用 `Depends(get_current_user)` + `Depends(get_db)`
  - **状态落库**：写入 `question_import_record`（`import_status='PREVIEW'` / `progress_percent` / `current_phase`）

  **Must NOT do**：
  - ❌ **不得修改 `question_import.py:4005-4011` 的共享 dispatch**（红线）
  - ❌ 不得修改 `separate_match_endpoint` 函数体的任何一行
  - ❌ 不得新增文件上传入口（复用既有 `/import/upload`）
  - ❌ 不得在本端点内 commit 数据库（沿用既有「preview 不落库、confirm 才落库」的两阶段约定）
  - ❌ 不得返回结构与现有 `separate-match` 不一致（会迫使前端加分支，违反「前端无需分支」设计）
  - ❌ 不得把题干路径/文件名拼进任何文件路径（安全）

  **Recommended Agent Profile**：
  - **Category**：`deep`
    - Reason：需编排 6 个前序任务的产出、保证共享链路零改动、返回契约与既有一致 —— 集成复杂度高于任一单项
  - **Skills**：`[]`

  **Parallelization**：
  - **Can Run In Parallel**：NO
  - **Parallel Group**：Wave 3（与 12,13 并行；12/13 依赖本任务的部分产出，故实际 11 先落、12/13 并行）
  - **Blocks**：14, 15
  - **Blocked By**：3, 4, 7, 8, 9, 10

  **References**：

  *Pattern References（契约与鉴权的唯一权威）*：
  - `backend/app/api/v1/question_import.py:3970-4051` `separate_match_endpoint` — **返回结构模板**：11 个字段，逐一照抄；鉴权 `current_user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)`；错误处理 `raise HTTPException(400/500, detail=...)`
  - `backend/app/api/v1/question_import.py:3816-3863` `_separate_match_essay()` — **分流模式模板**：先切分 → 判科 → 分派；返回结构声明「与原 `separate_match_endpoint` 的返回结构保持一致，**前端无需分支**」
  - `backend/app/api/v1/question_import.py:454` `_get_duplicate_info()` — 去重检测复用点
  - `backend/app/api/v1/question_import.py:3300` `get_import_parse_status()` + `:4804` `get_import_records()` + `:4851` `get_import_stats()` — `question_import_record` 状态读写范式

  *API/Type References*：
  - `question_import_record` 列：`import_id / paper_id / user_id / original_filename / file_type / total_questions / success_count / failed_count / duplicate_count / import_status / preview_data(JSON) / error_messages(JSON) / import_time / complete_time / progress_percent / current_phase`
  - 实测既有行测导入记录（`import_id 1375/1376`）：`total_questions=110/101`、`success_count=110/101`、`failed_count=0`、`current_phase='DONE'`、`import_status='PREVIEW'` → 新端点须能复现并超越这一状态

  *Vite 实请求（QA 依据）*：
  - `proxy.config.ts` — `/api` → `http://localhost:8000`，WebSocket 代理
  - `vite.config.ts:8` — `DEV_PORT = 9527`

  **WHY Each Reference Matters**：
  - `_separate_match_essay()` 的「前端无需分支」是**前序已确立的设计契约**。若行测端点返回不同结构，`question_import.vue` 就得加科目分支 → 违反 Q3「只强化现有预览页」的克制原则
  - `question_import_record` 的实测行（1375/1376）证明现有链路能把行测解析到 110 块，新端点必须**在同一记录结构**上工作，否则前端轮询 `records/{id}/status` 会失效
  - `proxy.config.ts` + `vite.config.ts` 是 QA 场景「实际请求 Vite」的依据 —— G8 强制要求，不能只靠 SFC 编译通过

  **Acceptance Criteria**：

  - [ ] 新端点注册成功，`/docs` 中可见
  - [ ] `git diff` 显示 `separate_match_endpoint` 与 `:4005-4011` dispatch **零改动**（用 `git diff -U0` 逐行确认）
  - [ ] 返回结构 11 个字段与既有 `separate-match` **完全一致**（写测试断言键集合相等）
  - [ ] 安徽行测试：`POST /separate-match-xingce` 返回 `match_rate ≥ 0.99`、`blocked_count` 含 110 vs 101 差集
  - [ ] 写入 `question_import_record` 一行，`import_status='PREVIEW'`、`progress_percent=100`、`current_phase='DONE'`
  - [ ] 错配年份（2025题本+2024答案）→ `blocked_count > 0` 且**不返回可确认入库的预览**
  - [ ] 鉴权生效：无 token 返回 401/403
  - [ ] 空 `questions_text` → 400；空 `answers_text` → 400
  - [ ] 公专/申论的 `separate-match` 行为逐字节不变（对同一语料两次调用响应除时间戳外全等）
  - [ ] 公专 G1 门禁逐项一致

  **QA Scenarios**：

  ```
  Scenario: 经 Vite 代理实请求成功（成功路径 — G8 强制）
    Tool: Bash (curl) + Playwright
    Preconditions: 后端 8000 + Vite 9527 均已启动
    Steps:
      1. curl -s -o /dev/null -w "%{http_code}" http://localhost:9527/  断言 == 200（证明前端真在跑）
      2. TOKEN=$(登录获取)
      3. curl -s -X POST http://localhost:9527/api/questions/import/separate-match-xingce \
           -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
           -d '{"questions_text":"<安徽题本全文>","answers_text":"<安徽答案全文>"}' -o tmp/r.json
      4. 断言 http_code == 200
      5. python -c "import json;d=json.load(open('tmp/r.json'));ks=set(d);assert len(ks)>=11;assert d['match_rate']>=99.0;print(sorted(ks))"
      6. 断言 d 含 xingce_report 且其内含分节区间表
      7. Playwright 打开 http://localhost:9527/#/question-import，断言网络面板出现 separate-match-xingce 请求且 200
    Expected Result: 经 9527 代理实请求成功；返回 11+ 字段；浏览器端可见该请求
    Failure Indicators: curl 直连 8000 成功但经 9527 失败 → 代理配置问题（G8 禁止只测直连）
    Evidence: evidence/task-11-endpoint-vite.txt

  Scenario: 共享 dispatch 零改动（失败路径 — 红线）
    Tool: Bash
    Preconditions: 无
    Steps:
      1. git diff -U0 -- backend/app/api/v1/question_import.py > tmp/d.txt
      2. 断言 tmp/d.txt 中不含 "- " 开头且涉及 4005-4011 区间的行
      3. python -c 对同一公专语料调用 /separate-match 两次，断言响应除时间戳外全等
      4. 断言 separate_match_endpoint 的行号未变（仍为 3971）
    Expected Result: 共享链路字节级不变
    Failure Indicators: dispatch 有任何 - 行 → 立即回滚本任务
    Evidence: evidence/task-11-dispatch-untouched.txt

  Scenario: 鉴权与入参校验（失败路径）
    Tool: Bash (curl)
    Preconditions: 无
    Steps:
      1. 无 token POST → 断言 401 或 403
      2. 有 token 但 questions_text="" → 断言 400 且 detail 含 "题目文件文本为空"
      3. 有 token 但 answers_text="" → 断言 400 且 detail 含 "答案文件文本为空"
      4. 有 token 但两者均空白字符 → 断言 400
    Expected Result: 三类非法输入均被正确拒绝
    Failure Indicators: 无 token 也能成功（鉴权失效，安全问题）
    Evidence: evidence/task-11-auth-validation.txt
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-11-endpoint-vite.txt` — 经 9527 的 curl 响应 + Playwright 截图
  - [ ] `evidence/task-11-dispatch-untouched.txt` — `git diff -U0` 证明 dispatch 零改动
  - [ ] `evidence/task-11-auth-validation.txt` — 401/400 断言

  **Commit**：YES
  - Message：`feat(xingce): add dedicated separate-match-xingce endpoint (shared dispatch untouched)`
  - Files：`backend/app/api/v1/question_import.py`

  - [ ] 12. 卷级元数据注入（省份 / 年份 / 卷别）

  **为什么需要**：实测 170 份文件名的省份写法**极不可靠**（2025 年安徽/河南/山西/陕西/黑龙江**全部缺「省」字**，甘肃**全省缺「省」字**，广西用「区考」）。而 **24 个省级文件夹名干净一致** —— 文件夹名是唯一可靠的省份标识。现有 `_auto_detect_tags()` 扫文件名+正文全文，行测语料会大面积误判省份。

  **What to do**：
  - 元数据来源优先级（**显式覆盖 > 推断**）：**① 上传时传入的文件夹名/省份参数** → ② `_auto_detect_tags()` 现有推断
  - 文件名只用于提取**年份**（`20\d{2}`）与**卷别**，**禁止用于省份**
  - 卷别枚举（实测全集）：
    | 卷别 | 出现范围 |
    |------|---------|
    | 无卷别（仅网友回忆版） | 22 省 |
    | 乡镇卷 / 区级及以上卷 | 北京 2021 |
    | 县级卷 / 乡镇卷 | 广东 2023 |
    | A类 / B类 / C类 | 江苏（2023:A/B；2024/2025:A/B/C） |
    | 副省级 / 地市级 / 行政执法卷 | 国考 |
  - 文件名异常容错（**必须全部覆盖**）：`题干.pdf` 冒充题本 / `试题` vs `题` / `区考` vs 省考 / 省份名缺「省」
  - 落库：`exam_paper`（`composition_method='IMPORT'` / `paper_type='DRAFT'` / `subject_id=1`）+ `exam_paper_tag`（`exam_year` / `exam_province` / `exam_type` / `subject_category='行测'` / `is_complete=1`）
  - 复用既有 `_get_or_create_import_paper()` 的**同名同创建者查重**与 **ENDED→DRAFT 复活**逻辑（前序 P2.2 已验证）

  **Must NOT do**：
  - ❌ 不得用文件名推断省份（实测不可靠）
  - ❌ 不得修改 `_auto_detect_tags()` 既有逻辑（公专/申论在用）—— 只新增**行测覆盖入口**
  - ❌ 不得硬编码 85 套的省份/年份映射表（必须从文件夹名 + 文件名正则实时推导）
  - ❌ 不得把文件夹路径拼进任何文件读写路径（安全：只取 basename）
  - ❌ 不得新建 `exam_paper_tag`（表已存在）

  **Recommended Agent Profile**：
  - **Category**：`unspecified-high`
    - Reason：逻辑本身不复杂，但异常清单长（5 类命名异常 × 85 套需 100% 覆盖），且必须零回归地叠加到既有 `_auto_detect_tags` 之上
  - **Skills**：`[]`

  **Parallelization**：
  - **Can Run In Parallel**：YES
  - **Parallel Group**：Wave 3（与 13 并行）
  - **Blocks**：15
  - **Blocked By**：11

  **References**：

  *Pattern References（试卷与标签落库的唯一权威）*：
  - `backend/app/api/v1/question_import.py:1413-1474` `_auto_detect_tags()` — **既有检测引擎**，其输出结构（年份/省份/类型/科目/是否完整）必须沿用，只在其**前面**加显式覆盖
  - `backend/app/api/v1/question_import.py:1553` `_get_or_create_import_paper()` — **试卷查重 + ENDED→DRAFT 复活**，前序 P2.2 已验证通过
  - `backend/app/api/v1/question_import.py:1475` `_detect_complete_paper()` — 「完整试卷判定」（连续递增题号≥5 且 60% 连续 + 答案区检测）
  - `backend/app/api/v1/question_import.py:1505` `_extract_paper_name()` — 卷名提取正则 `XXXX年XX考试行测/申论/公专`

  *API/Type References（落库目标）*：
  - `exam_paper`（实测 42 行）：`paper_id / paper_name / subject_id / paper_type / question_count / composition_method / duration / total_score / difficulty`
  - `exam_paper_tag`（实测 39 行）：`exam_year / exam_province / exam_type / subject_category / is_complete`；实测既有行含 `subject_category='行测'` 且 `is_complete=0` 的失败痕迹（paper_id 14/15）→ 本任务须修正这类行
  - `solve_problems_files/历年试卷设计方案.md` §3.5 — `exam_paper_tag` 字段设计与 `is_complete` 语义原文

  *实测证据（本任务的输入规格）*：
  - 24 个文件夹名（干净）：`内蒙古行测 北京行测 吉林行测 国考行测 宁夏行测 安徽行测 山东行测 山西行测 广东行测 广西行测 江苏行测 江西行测 河北行测 河南行测 海南行测 湖北行测 湖南行测 甘肃行测 福建行测 贵州行测 辽宁行测 陕西行测 青海行测 黑龙江行测`
  - 文件名异常 5 类：① `2025年国家公务员录用考试《行测》题（地市级网友回忆版）题干.pdf` ② `2022/2023/2024年山东省…《行测》试题…` 用「试题」③ `2023/2024/2025年广西区考公务员录用考试…` 用「区考」④ 2025 年安徽/河南/山西/陕西/黑龙江 缺「省」 ⑤ 甘肃 3 个年份全缺「省」
  - 年份覆盖：内蒙古缺 2024；山东缺 2025；北京/吉林/江苏/广东/国考 缺 2021-2022

  **WHY Each Reference Matters**：
  - `_auto_detect_tags()` 是既有元数据口径的唯一权威。行测覆盖入口必须**在其之前**插入而非重写，否则公专/申论的省份判定会受影响（它们靠正文关键词而非文件夹名）
  - ENDED→DRAFT 复活是前序已验证的能力。行测 85 套重导入时会大量命中「同名试卷已存在」场景，不复用就会堆积 85 个重复试卷
  - 实测 `exam_paper_tag` 已有 2 行 `is_complete=0` 的行测失败痕迹，说明这条路径曾被触发但未成功 —— 本任务须把这 2 行修正为正确值

  **Acceptance Criteria**：

  - [ ] 85 套的省份判定 **100% 正确**（与文件夹名逐一比对，24 个值全覆盖）
  - [ ] 85 套的年份判定 **100% 正确**
  - [ ] 卷别判定：江苏 8 套 A/B/C、国考 9 套副省级/地市级/行政执法、广东 4 套含县级/乡镇、北京 4 套含乡镇/区级 —— 全部正确
  - [ ] 5 类文件名异常全部容错通过（尤其 `题干.pdf`）
  - [ ] 每套生成 `exam_paper`（`composition_method='IMPORT'` / `paper_type='DRAFT'` / `subject_id=1`）+ `exam_paper_tag`（`subject_category='行测'` / `is_complete=1`）
  - [ ] `exam_paper_tag` 既有 2 行 `is_complete=0` 的行测行被修正
  - [ ] **公专 42 个 exam_paper 与 39 个 tag 零变化**（本任务只新增行测）
  - [ ] 幂等：同套重复导入 → 试卷复用而非新建
  - [ ] 无任何路径拼接（`git grep` 证明新增代码不含 `os.path.join` + 用户输入）

  **QA Scenarios**：

  ```
  Scenario: 85 套元数据 100% 正确（成功路径）
    Tool: Bash
    Preconditions: 任务 11 端点可用
    Steps:
      1. python backend/scripts/verify_xingce_regression.py --assert-metadata "D:\砺安题库\砺安题库\题库\行测" --out tmp/g2
      2. 断言 省份判定正确率 == 100.0（85/85，与文件夹名比对）
      3. 断言 年份判定正确率 == 100.0
      4. 断言 江苏 8 套卷别 ∈ {A类,B类,C类}
      5. 断言 国考 9 套卷别 ∈ {副省级,地市级,行政执法卷}
      6. 断言 题干.pdf 那套被正确识别为「题本」角色而非答案
    Expected Result: 元数据 100% 正确；题干.pdf 异常被容错
    Failure Indicators: 任一套省份/年份错误（说明误用了文件名推断）
    Evidence: evidence/task-12-metadata-85.txt

  Scenario: 试卷幂等与既有零影响（边界路径）
    Tool: Bash
    Preconditions: 已导入 3 套试点
    Steps:
      1. 快照 select count(*) from exam_paper 与 exam_paper_tag
      2. 重复导入同一套 2 次
      3. 断言 exam_paper 增量 == 1（复用而非新建）
      4. 断言 公专 42 个 paper 的 paper_name/paper_type 逐条不变
      5. 断言 exam_paper_tag 既有 39 行逐字段不变（除被修正的 2 行 is_complete）
    Expected Result: 幂等生效；公专既有数据零影响
    Failure Indicators: 重复导入产生同名重复试卷 → 幂等失效
    Evidence: evidence/task-12-idempotent.txt

  Scenario: 路径穿越防护（安全边界）
    Tool: Bash
    Preconditions: 无
    Steps:
      1. 传入 original_filename = "../../etc/passwd"
      2. 断言 元数据提取不抛异常，省份判定返回 "未知"
      3. 断言 未在项目目录外创建任何文件
      4. 传入含空字节的 filename，断言被安全拒绝
    Expected Result: 恶意文件名被无害化处理，不产生路径穿越
    Failure Indicators: 项目目录外出现新文件（路径穿越成功，严重安全问题）
    Evidence: evidence/task-12-path-traversal.txt
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-12-metadata-85.txt` — 85 套省份/年份/卷别判定表
  - [ ] `evidence/task-12-idempotent.txt` — 幂等 + 既有数据零影响
  - [ ] `evidence/task-12-path-traversal.txt` — 路径穿越防护验证

  **Commit**：YES
  - Message：`feat(xingce): inject paper metadata from folder name (not filename)`
  - Files：`backend/app/api/v1/question_import.py`

- [ ] 13. 纯图片题切图 + `need_review` 标记

  **用户决策 Q1**：切图入库 + 人工补文字选项。**用户决策 Q2**：不达标题入库 + 标记待复核。

  **What to do**：
  - 复用既有 `[IMAGE:...]` 占位符协议**六环节**（生成→落盘→回填→过滤→安全→静态路由），**不新建机制**
  - 既有阈值调优：`_PDF_MIN_IMG_DIM = 40`（`question_import.py:866`）针对公专/申论调优；行测图形推理的图片密度与尺寸分布不同 → **必须先统计行测图片尺寸分布再定阈值**，不得盲目下调
  - 补**最大像素/像素总数上限**（GAP-13）：`_pdf_image_to_png()` 现只滤最小边，无上限 → 补上限防解压炸弹
  - 图片归属：按 `question_number` 归位，**复用 `attach_image_to_preview_question()`（`:3382`）** 与 `image_filters.py` 的无关图过滤
  - 标记规则：
    | 情形 | `need_review` | 前端表现 |
    |------|---------------|---------|
    | 选项标记存在但文字为空（纯图片选项） | 1 | 🔴 徽标 + 「选项待补文字」提示 |
    | 答案缺失 | 1 | 🔴 + 「答案缺失」 |
    | 解析缺失 | 1 | 🔴 + 「解析缺失」 |
    | `blocked` | — | 前端**禁用**「确认导入」 |
    | 资料分析材料未传播 | 1 | 🔴 + 「材料关联异常」 |

  **Must NOT do**：
  - ❌ 不得新建图片占位符协议或新的图片目录约定
  - ❌ 不得跳过 `image_filters.py` 的无关图/二维码/推广图过滤（前序 P1.5 清理过 3 题 6 图推广图）
  - ❌ 不得下调 `_PDF_MIN_IMG_DIM` 而不先统计行测尺寸分布
  - ❌ 不得把 `blocked` 题当作普通题放行（`blocked` 与 `need_review` 是**两套语义**，前者阻断、后者标红）
  - ❌ 不得让解析/答案缺失的题静默入库（必须 `need_review=1`）

  **Recommended Agent Profile**：
  - **Category**：`unspecified-high`
    - Reason：需统计行测图片尺寸分布才能定阈值（数据驱动），并补解压炸弹防护（安全），同时严格复用六环节协议
  - **Skills**：`[]`

  **Parallelization**：
  - **Can Run In Parallel**：YES
  - **Parallel Group**：Wave 3（与 12 并行）
  - **Blocks**：15
  - **Blocked By**：11

  **References**：

  *Pattern References（六环节协议的每一环）*：
  - `backend/app/api/v1/question_import.py:850` `_PDF_QN_LINE` — 题号行识别（图片归属的基准）
  - `backend/app/api/v1/question_import.py:866` `_PDF_MIN_IMG_DIM = 40` — **待调优的阈值**
  - `backend/app/api/v1/question_import.py:869` `_pdf_image_to_png(im)` — 图片转 PNG，**本任务补上限防护**
  - `backend/app/api/v1/question_import.py:1246` `_extract_images_from_pdf_page(page, page_idx)` — 按页提图
  - `backend/app/api/v1/question_import.py:1314` `_decode_pdf_image(xobj)` — 图片解码
  - `backend/app/api/v1/question_import.py:1391` `_pdf_has_images_only(buf)` — 纯图片页判定
  - `backend/app/api/v1/question_import.py:1631` `_extract_and_save_images(...)` — 落盘
  - `backend/app/api/v1/question_import.py:3382` `attach_image_to_preview_question()` — 预览期贴图（前端 `attach-image` 端点对应）
  - `backend/app/services/image_filters.py` — 无关图/二维码/推广图过滤（**11 KB，必须走**）
  - `solve_problems_files/申论题目导入精准化方案_v4.md` §7 — 「现有 `[IMAGE:...]` 占位符协议已贯通『生成→落盘→回填→过滤→安全→静态路由』6 环节，**实测 15/15 图片归属正确**；另建表会形成两套并存机制（违反去粗取精原则）」

  *API/Type References*：
  - `question_bank.need_review INTEGER default 0` — 注释「待人工复核标记：1=题型存疑待复核 0=正常」。⚠️ 注释语义是「题型存疑」，本任务扩展到「答案/解析/选项/材料缺失」→ **须同步更新注释**
  - 前端消费点（实测）：`.vtj/vue/question_import.vue` `attach-image`(L2417)；`wrong_questions.py:57/221/459` 读 `xingce_subcategory`；`question_import.py` 既有 `confidence` + `<0.5` 徽标（v4 §P3.3 已存在，无需新建）

  *实测证据*：
  - 2025 国考地市级 Q126 为纯图片选项题：`A.` / `B.` / `C.` / `D.` 四行**文字全空**，饼图为独立图片
  - 实测 `backend/app/static/questions/` 有 **~3,100 个题号目录**（432…3114）→ 行测将再增约 11,000 个目录，**目录膨胀需评估**
  - 既有 4 个待复核样本：`need_review` 分布 `{0: 2576, 1: 7}`

  **WHY Each Reference Matters**：
  - 六环节已「实测 15/15 图片归属正确」。**另建机制就是 G6 违规**，且必然出现两套并存
  - `_PDF_MIN_IMG_DIM=40` 是公专/申论调出来的值。行测图形推理的图片**普遍更小**（选项图），盲目沿用会整批漏图；盲目下调会把页眉 Logo 当题图。**必须先统计**
  - `need_review` 的注释语义（仅「题型存疑」）与本任务用途（4 类缺失）不符。不改注释会让后续维护者误判字段含义 —— 这正是「运维便利」的要求

  **Acceptance Criteria**：

  - [ ] 产出行测图片尺寸分布统计（min/median/max 边长、总像素分布）
  - [ ] `_PDF_MIN_IMG_DIM` 的新阈值**有统计依据**，且注释写明依据
  - [ ] `_pdf_image_to_png()` 补最大像素上限，且有单图超限时**跳过并记 `need_review`** 而非崩溃
  - [ ] 2025 国考地市级 Q126 切图成功，`[IMAGE:...]` 占位符正确回填，图片归属正确
  - [ ] 抽样 20 张图验证 `is_irrelevant_image` 过滤生效（0 张推广图/二维码混入）
  - [ ] 纯图片选项题：`need_review=1` + `options` 保留 A/B/C/D 键但值为空
  - [ ] 答案/解析缺失题：`need_review=1`
  - [ ] `blocked` 题：前端「确认导入」按钮禁用
  - [ ] `question_bank.need_review` 注释已更新为覆盖 4 类情形
  - [ ] 公专既有 7 条 `need_review=1` 记录未被改动
  - [ ] 评估并记录「11,000 题 → 11,000 个图片目录」的目录膨胀影响与缓解建议

  **QA Scenarios**：

  ```
  Scenario: 纯图片选项题正确切图并标记（成功路径）
    Tool: Bash
    Preconditions: 任务 11 端点可用
    Steps:
      1. 导入 2025 国考地市级，定位 Q126
      2. 断言 Q126 的 options 含 4 个键 A/B/C/D
      3. 断言 4 个值均为空字符串
      4. 断言 question_content 含 >=1 个 [IMAGE:...] 占位符
      5. 断言 need_review == 1
      6. 断言占位符指向的图片文件实际存在于 static/questions/<qid>/
      7. 断言 is_irrelevant_image 判定为 keep（非 block/suspect）
    Expected Result: 纯图片题切图成功、占位符正确、标记待复核
    Failure Indicators: 图片文件不存在（落盘失败）；推广图混入（过滤失效）
    Evidence: evidence/task-13-image-q126.txt

  Scenario: 解压炸弹被拦截（安全边界）
    Tool: Bash
    Preconditions: 无
    Steps:
      1. 构造一个内嵌超大尺寸 PNG 的 PDF（总像素超上限）
      2. 导入，断言不崩溃、进程存活
      3. 断言该题 need_review=1 且有明确原因记录
      4. 断言内存占用未失控
    Expected Result: 超限图片被跳过并标记，不影响整批导入
    Failure Indicators: 进程 OOM 崩溃（补上限前的老行为）
    Evidence: evidence/task-13-decompression-bomb.txt

  Scenario: 无关图过滤未失效（失败路径 — 回归红线）
    Tool: Bash
    Preconditions: 无
    Steps:
      1. 从公专语料导入一页含推广图的文档
      2. 断言 image_filters.py 判定为 block 或 suspect
      3. 断言该图未写入 question_content 的 [IMAGE:...] 占位符
      4. 断言公专 7 条既有 need_review=1 记录未变
      5. 断言 static/questions/ 下无新增孤儿目录
    Expected Result: 推广图被拦截；既有待复核记录不受影响
    Failure Indicators: 推广图进入占位符（前序 P1.5 清理过的 3 题 6 图复现）
    Evidence: evidence/task-13-irrelevant-filter.txt
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-13-image-q126.txt` — Q126 切图与占位符验证
  - [ ] `evidence/task-13-decompression-bomb.txt` — 超限图片拦截
  - [ ] `evidence/task-13-irrelevant-filter.txt` — 无关图过滤回归

  **Commit**：YES
  - Message：`feat(xingce): tune image thresholds and flag incomplete questions for review`
  - Files：`backend/app/api/v1/question_import.py`、`backend/app/models/models.py`（注释）

- [ ] 14. `question_import.vue` — `<script>` 强化（VTJ raw 页）

  **VTJ 铁律（违反即回归）**：该页 `"raw": true`（`.vtj/projects/linxitie.policy-exam-bank.json:437-439`）→ 设计器不覆盖，可安全手改。**但严禁改 `<template>`**（vtj.md §3.1：UI 结构变更必须回设计器）。**严禁同步 `.vtj/files/question_import.json`**（前序铁律 R-2：同步工具有损，48 方法中连 `_pollImportStatus` 都提取不到）。

  **What to do**：
  - **仅改 `.vtj/vue/question_import.vue` 的 `<script>`**（现 3640 行）
  - 分离导入分流：调用 `separate-match` 前按检测到的科目分流 —— 行测走新端点 `separate-match-xingce`，申论/公专走既有 `separate-match`（**既有分支逻辑零改动**）
  - 预览强化（消费后端已有字段，**不加新 UI 结构**）：
    - 按行测 5~7 个分区折叠分组展示（复用既有 `docs-q-card` 容器样式类，不新增 class）
    - `need_review=1` 的题显示 🔴 徽标 + 具体原因（答案缺失/解析缺失/选项待补文字/材料关联异常）
    - `blocked` 时**禁用**「确认导入」按钮
    - 考点以只读标签展示（复用既有 `docs-q-*` 样式）
  - ⚠️ **template 依赖**：若所需展示结构（分区折叠容器、原因标签）在 `<template>` 中不存在，**必须停下来请用户在 `http://localhost:9527/__vtj__/` 设计器拖拽**，不得自行改 template（这是本任务的硬边界）
  - Vite 实请求验证（G8）：`npm run dev` 后 Playwright 打开 `http://localhost:9527/#/question-import`，实际点击上传分离导入，抓网络面板确认命中 `separate-match-xingce`

  **Must NOT do**：
  - ❌ **不得修改 `<template>` 任何一行**（VTJ 设计器职责）
  - ❌ **不得同步 `.vtj/files/question_import.json`**（铁律 R-2）
  - ❌ 不得修改 `useProvider({ id, version })` 的 `version`
  - ❌ 不得移除既有 `docs-q-card-noans` / `docs-q-answer-row-warn` 告警类、`pickImage(idx,'option',opt.key)` 贴图按钮、`renderQuestionContent()`（自带 `sanitizeHtml`）
  - ❌ 不得新增 `fetch` 到未在本方案注册的端点
  - ❌ 不得以「SFC 编译通过」作为生效证据（必须实请求 9527）

  **Recommended Agent Profile**：
  - **Category**：`visual-engineering`
    - Reason：涉及 VTJ 生成页的 Vue Options API `<script>` 改造 + 预览渲染，需严格遵循 VTJ 规范并保证前端实际可见
  - **Skills**：`[]`
  - **Skills Evaluated but Omitted**：
    - `playwright`：省略 —— Playwright 是验证工具而非实现技能；本任务 QA 阶段直接使用 playwright 工具

  **Parallelization**：
  - **Can Run In Parallel**：NO
  - **Parallel Group**：Wave 4（与 15 同波但 15 依赖本任务）
  - **Blocks**：15
  - **Blocked By**：11, 12, 13

  **References**：

  *Pattern References（VTJ 规范硬约束）*：
  - `CLAUDE.md/vtj.md` §3.1 — **职责分离原则**：Claude Code 只维护 `<script>`；**不应修改 `<template>` 中复杂结构**，应提示用户回设计器
  - `CLAUDE.md/vtj.md` §3.2 — VTJ 生成代码特征：`defineComponent` + `setup()` + `useProvider({id, version})` + `reactive` + `methods`
  - `CLAUDE.md/vtj.md` §附录F — 「修改 .vue 后强制同步 DSL」← **本任务裁定：遵从 R-2 禁止同步**（见方案末尾文档冲突裁定）
  - `.vtj/vue/question_import.vue:2157` — **既有 `separate-match` 调用点**，本任务在此分流
  - `.vtj/vue/question_import.vue:774/800/1056/1523/2687/2833` — 既有调用范式（`fetchWithRetry` 封装、轮询 `records/{id}/status`）
  - `.vtj/vue/question_import.vue:2417` — 既有 `attach-image` 调用与贴图按钮
  - `.vtj/vue/question_import.vue:3382`（后端对应端点）— `attach_image_to_preview_question`

  *API/Type References*：
  - `window.__VTJ_AUTH__.getJsonHeaders()` / `getAuthHeaders()` / `apiFetch()` — 本项目**不用** `@vtj/utils` 的 `request`，用原生 `fetch` + 共享认证（vtj.md §D.2）
  - 新端点返回的 11 字段契约（与既有 `separate-match` 一致）+ 额外 `xingce_report`
  - `vite.config.ts:8` `DEV_PORT = 9527` / `:101` `strictPort: true`
  - `proxy.config.ts` — `/api` → `http://localhost:8000`

  *Test References*：
  - `solve_problems_files/Playwright迁移与VTJ_MCP验证方案.md` — 本项目既有的 Playwright + VTJ 验证方案，**复用其验证套路**

  **WHY Each Reference Matters**：
  - `vtj.md` §3.1 是「不得改 template」的**规范出处**。本任务所有展示需求必须先确认既有 template 是否有对应容器，否则就要停下来找用户 —— 这是 VTJ 项目特有的协作边界，误判会导致设计器与代码互相覆盖
  - 铁律 R-2 与 `vtj.md` 附录F **直接冲突**。选 R-2 的理由是前序会话用实证证明同步工具会丢方法（48 个里连 `_pollImportStatus` 都提不出），属已验证事实
  - `fetchWithRetry` 是既有封装，分流代码必须沿用而非新写 fetch，否则丢失重试与错误提示

  **Acceptance Criteria**：

  - [ ] `git diff -- .vtj/vue/question_import.vue` 中**无任何 `<template>` 段内的增删行**
  - [ ] `git diff` 中 `.vtj/files/question_import.json` **零改动**（R-2）
  - [ ] `useProvider` 的 `id` 与 `version` 未变
  - [ ] 行测分流生效：上传行测分离对 → 网络面板出现 `separate-match-xingce`
  - [ ] 申论/公专分流**零回归**：上传申论分离对 → 仍命中 `separate-match`（非新端点）
  - [ ] `need_review=1` 的题显示 🔴 徽标与原因
  - [ ] `blocked` 时「确认导入」按钮为 disabled
  - [ ] 考点以只读标签展示
  - [ ] **Playwright 实请求 9527 截图存档**（G8 强制，非 SFC 编译）
  - [ ] `lsp_diagnostics` 对该文件无新增 error
  - [ ] 若展示结构缺失 → **已停下来向用户提出设计器操作清单**（而非自行改 template）

  **QA Scenarios**：

  ```
  Scenario: 行测分流实际生效（成功路径 — G8 强制）
    Tool: Playwright
    Preconditions: 后端 8000 + Vite 9527 已启动；已有 1 套行测 preview 记录
    Steps:
      1. Playwright 打开 http://localhost:9527/#/question-import
      2. 断言页面标题/上传区可见（具体选择器以既有 template 为准）
      3. 触发分离导入（选择题本 + 答案解析）
      4. 打开网络面板，断言出现 POST .../separate-match-xingce 且 status 200
      5. 断言断言未出现 POST .../separate-match（非新端点）
      6. 断言预览区显示分区分组（5~7 个分区）
      7. 截图存档 evidence/task-14-xingce-routing.png
    Expected Result: 行测走新端点；预览按分区分组；截图存档
    Failure Indicators: 仍命中旧 separate-match（分流未生效）；页面报错
    Evidence: evidence/task-14-xingce-routing.png

  Scenario: 申论/公专零回归（失败路径 — 红线）
    Tool: Playwright
    Preconditions: 同上
    Steps:
      1. 上传一对申论分离文档
      2. 断言网络面板出现 POST .../separate-match（非 -xingce）
      3. 断言未出现 separate-match-xingce
      4. 断言申论预览渲染与改动前截图一致
      5. 上传公专文档，断言行为亦不变
    Expected Result: 申论/公专完全走原路径
    Failure Indicators: 任一科目被错误路由到新端点（分流逻辑污染）
    Evidence: evidence/task-14-no-regression.png

  Scenario: blocked 阻断与需复核标红（边界路径）
    Tool: Playwright
    Preconditions: 准备 1 个 blocked 卷 + 1 个含 need_review 题的卷
    Steps:
      1. 打开 blocked 卷预览，断言「确认导入」按钮 disabled
      2. 断言 blocked 原因列表可见
      3. 打开含 need_review 的卷，断言 🔴 徽标可见
      4. 断言徽标旁显示具体原因文本（答案缺失/解析缺失/选项待补文字/材料关联异常）
      5. 断言考点标签可见
      6. 截图存档
    Expected Result: blocked 阻断、需复核标红、原因与考点可见
    Failure Indicators: blocked 卷仍可确认入库（阻断失效，严重）
    Evidence: evidence/task-14-blocked-review.png
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-14-xingce-routing.png` — 行测分流实请求截图
  - [ ] `evidence/task-14-no-regression.png` — 申论/公专零回归截图
  - [ ] `evidence/task-14-blocked-review.png` — blocked 阻断 + 需复核标红截图

  **Commit**：YES
  - Message：`feat(xingce): route xingce to dedicated endpoint and surface review markers in import preview`
  - Files：`.vtj/vue/question_import.vue`

  - [ ] 15. 6 套试点导入 + 三重门禁回归

  **用户决策 Q5**：先试点 6 套验证 → 固化为回归语料 → 再全量。每套必覆盖至少一个结构/命名异常，**确保门禁语料从第一天就含方言**。

  **试点清单**：

  | # | 套 | 覆盖的变体 |
  |---|-----|-----------|
  | 1 | 国考 2025 地市级 | 文件名 `题干.pdf` 冒充题本（**唯一命名异常**）+ 6 分节（含政治理论）+ 资料分析 |
  | 2 | 国考 2025 副省级 | 三卷并行中的对照卷（题号区间应与地市级**不同**） |
  | 3 | 国考 2023 地市级 | **既有 G2 门禁基线所在卷** —— 证明改动后仍 ≥0.99 不劣化 |
  | 4 | 江苏 2025 C 类 | 卷别标记 `（C类）` + 三省中卷数最多 + `江苏特色-*` 私有考点 |
  | 5 | 甘肃 2025 | 省份名缺「省」字（验证元数据取文件夹名） |
  | 6 | 广东 2023 县级卷 | 同年双卷并存（县级卷/乡镇卷）+ `科学推理` 分区候选 |

  **What to do**：
  - 逐套走**完整用户流程**：`/question-import` 上传题本 → 上传答案解析 → 预览 → 确认入库
  - 记录每套指标：块数、配对率、答案覆盖率、解析覆盖率、考点覆盖率、分区分布、材料块数、`need_review` 数、`blocked` 数
  - **逐套人工抽检**：首题 + 末题 + 每个分区的第一题（对齐前序 G4 判据）
  - 6 套全部通过后，**固化为回归语料**：落 `{slot}.q.txt` / `{slot}.a.txt` / `{slot}.result.json` 到门禁语料目录，并加入 `verify_xingce_regression.py` 的默认集合
  - 每套跑**三重门禁**（G1 公专 + G3 申论 + G2 行测），全部逐项与基线一致

  **Must NOT do**：
  - ❌ 不得在试点阶段放宽任何校验以求「通过」
  - ❌ 不得跳过 G1 公专门禁（**G1 与基线不一致即整体不通过，无论行测多准**）
  - ❌ 不得以 pytest 全绿为判据（铁律 R-4）
  - ❌ 不得在试点未全绿时启动全量导入
  - ❌ 不得删除试点产生的数据来「重来」—— 必须先分析再决定

  **Recommended Agent Profile**：
  - **Category**：`unspecified-high`
    - Reason：需走完整用户流程 + 逐题人工抽检 + 三重门禁比对 + 语料固化，是集成验收而非编码
  - **Skills**：`[]`

  **Parallelization**：
  - **Can Run In Parallel**：NO
  - **Parallel Group**：Wave 4（依赖任务 14）
  - **Blocks**：16
  - **Blocked By**：14

  **References**：

  *Test References（判据来源）*：
  - `solve_problems_files/申论题目导入精准化方案_v4.md` §1 — **G2 行测门禁原始定义**：130 块、题号 1..130 连续、options 130/130、`smart_match` rate ≥ 0.99
  - 同文 §1 G1 公专基线 + **G4「逐字段人工抽检：每卷抽首题+末题」**
  - `backend/data/regression_baseline_before.txt`（6,232 字节）— 公专基线原文
  - `solve_problems_files/题目导入优化策略与持续改进机制.md` §4.1 — 「提交纪律：**任何解析改动必须 20/20 全过才允许提交**，防止『修 A 坏 B』」
  - `solve_problems_files/题目导入优化策略与持续改进机制.md` §5 闭环 1 — **失败样本分类学**：每个失败项必须标注「源文档固有」或「解析 bug」。前者写进「已知边界」不再追

  *实测证据（试点预期值）*：
  - 国考 2023 地市级：G2 基线 = 130 块 / options 130/130 / ≥0.99
  - 85 套题号范围 88–141，均值约 122
  - 分节数：5 节 57 份 / 6 节 27 份 / 7 节 1 份
  - 材料块：2–12 块/卷，均值 4.3
  - 考点：86–135 个/卷（广东/山东/吉林偏少）

  **WHY Each Reference Matters**：
  - G2 原始定义是**本方案的对照基准**。若试点后 G2 低于 0.99，说明本方案的改动劣化了既有行测解析能力 → 必须回退到任务 7/8 重审
  - 「失败样本分类学」是**防止无效调参的安全带**。前序明确警告：若不分类，有人会为「消灭」主观题的空解析反复放宽阈值，**污染已正确的 1900 题**。行测同样适用
  - 「20/20 全过才允许提交」是前序已确立的提交纪律，本方案的每一波都必须遵守

  **Acceptance Criteria**：

  - [ ] 6 套全部完成「上传→预览→确认入库」，无一卡在 `PREVIEW`
  - [ ] 6 套的 `question_import_record.import_status` 全为 `COMPLETED`
  - [ ] 每套指标表完整（13 项指标 × 6 套）
  - [ ] 每套人工抽检通过（首题 + 末题 + 每分区第一题）
  - [ ] **G2 ≥ 0.99**，且国考 2023 地市级仍 == 130 块 / options 130/130
  - [ ] **G1 公专逐项与基线一致**（7 项断言）
  - [ ] G3 申论不变量全通过
  - [ ] pytest 失败集合 == 基线 `16 failed / 168 passed / 52 errors`
  - [ ] 6 套已固化为回归语料，加入门禁默认集合
  - [ ] 所有失败项已按「源文档固有 / 解析 bug」分类标注
  - [ ] **前端四处可见**：`/question-bank`、`/materials/xingce`、`/student/papers`、答题页 —— Playwright 实请求 9527 截图

  **QA Scenarios**：

  ```
  Scenario: 6 套试点全部成功（成功路径）
    Tool: Bash + Playwright
    Preconditions: 任务 14 完成；三重门禁就绪
    Steps:
      1. 对 6 套逐套执行完整导入流程
      2. 断言每套 import_status == 'COMPLETED'
      3. 断言每套配对率 >= 0.99
      4. 断言每套答案覆盖率 == 100.0
      5. 断言每套考点覆盖率 >= 98.0
      6. 断言每套材料块数与探针一致
      7. 断言每套分区分布非空（无 '无' 泛滥）
      8. 生成 6×13 指标表
    Expected Result: 6 套全绿；指标表完整
    Failure Indicators: 任一套卡在 PREVIEW（复现 1375/1376 故障）；配对率 < 0.99
    Evidence: evidence/task-15-pilot-6papers.txt

  Scenario: G2 基线劣化则整体回退（失败路径 — 红线）
    Tool: Bash
    Preconditions: 至少完成国考 2023 地市级
    Steps:
      1. 断言该卷块数 == 130
      2. 断言 options 数 == 130
      3. 断言 smart_match_rate >= 0.99
      4. 若任一失败：断言已停止后续试点，并输出 git diff 供定位
    Expected Result: 三项全过
    Failure Indicators: 块数 ≠ 130 或 options ≠ 130 → 既有行测解析被劣化，必须回退任务 7/8 重审，禁止带着劣化继续
    Evidence: evidence/task-15-g2-regression.txt

  Scenario: 前端四处实际可见（成功路径 — G8 强制）
    Tool: Playwright
    Preconditions: 试点数据已入库；后端 + Vite 9527 运行中
    Steps:
      1. Playwright 打开 http://localhost:9527/#/question-bank
         筛选行测 → 断言题目列表可见且总数 > 0；断言含资料分析分区题
      2. 打开 http://localhost:9527/#/materials/xingce
         断言行测资料可见
      3. 打开 http://localhost:9527/#/student/papers
         断言试点 6 套试卷可见（年份/科目筛选可用）
      4. 进入任一试卷的答题页
         断言资料分析题显示给定材料 + 5 小题；断言图形推理题图片正常加载
         断言提交后成绩报告正确显示正确答案与解析
      5. 四个页面各截图存档
    Expected Result: 四处均可见行测试点数据；材料与图片正确渲染
    Failure Indicators: 任一处不可见（前端未生效 —— 需回到任务 14 排查）；图片 404（图片管线断链）
    Evidence: evidence/task-15-frontend-visible/*.png
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-15-pilot-6papers.txt` — 6×13 指标表 + 人工抽检记录
  - [ ] `evidence/task-15-g2-regression.txt` — G2 三项断言
  - [ ] `evidence/task-15-frontend-visible/` — 四个页面的 Playwright 截图

  **Commit**：YES
  - Message：`test(xingce): pilot 6 papers and freeze as regression corpus`
  - Files：门禁语料目录、试点配置

- [ ] 16. 全量 85 套导入

  **What to do**：
  - 按**省份分批**（24 批）而非一次性 85 套，便于定位问题与回滚
  - 每批：导入 → 三重门禁 → 指标记录 → **确认通过再进下一批**
  - 建议顺序：国考(9) → 江苏(8) → 北京(4) → 广东(4) → 其余 20 省各 3
  - 每批强制：G1 公专 + G3 申论 + G2 行测 三门禁全绿
  - 全量后总验收：题目数 > 10,000、答案覆盖 100%、解析覆盖 ≥98%、考点覆盖 ≥98%
  - **导入前强制 DB 备份**（`backend/data/question_bank.db.bak_xingce_full_<timestamp>`）
  - 事务分批：每 N 题 commit（评估 11,000 题单事务的风险），WAL 模式确认

  **Must NOT do**：
  - ❌ 不得一次性导入 85 套（无法定位失败、无法回滚）
  - ❌ 不得在任一批门禁未绿时继续下一批
  - ❌ 不得为赶进度放宽校验或跳过人工抽检
  - ❌ 不得在未备份的情况下写入
  - ❌ 不得删除任何批次数据来「重来」而不先分析

  **Recommended Agent Profile**：
  - **Category**：`unspecified-high`
    - Reason：长时批量执行 + 每批门禁把关 + 异常定位，需高强度自主监控
  - **Skills**：`[]`

  **Parallelization**：
  - **Can Run In Parallel**：NO
  - **Parallel Group**：Wave 5（与 17 并行但 17 依赖本任务）
  - **Blocks**：17, F1–F4
  - **Blocked By**：15

  **References**：

  *Test References*：
  - 任务 2 建立的门禁脚本与基线文件
  - 任务 15 固化的 6 套语料（必须包含在全量集合中）

  *API/Type References*：
  - `question_bank` 实测容量：2,583 行 / 120MB → 11,000 道行测题预计使 DB 增至约 400–500MB（含 `preview_data` JSON 与图片路径）
  - `question_import_record` 实测：1,376 行且已有 **312 条卡死** → 全量后需新增 170 行左右

  **WHY Each Reference Matters**：
  - 「20/20 全过才允许提交」的纪律在长批量场景下更重要：一次批量污染 11,000 道题的清理成本远高于试点阶段
  - 分批的真正价值是**门禁能把失败锁定在单省**，避免整批 85 套一起追查

  **Acceptance Criteria**：

  - [ ] 全量导入前已生成 DB 备份
  - [ ] 85 套全部 `COMPLETED`
  - [ ] `question_bank` 中 `subject_id=1` 数量 **> 10,000**
  - [ ] 答案覆盖率 **100%**，解析覆盖率 **≥ 98%**，考点覆盖率 **≥ 98%**
  - [ ] 24 个省份的 `exam_paper_tag.exam_province` 全部正确
  - [ ] 每批三重门禁全绿（24 批 × 3 门禁 = 72 次门禁记录）
  - [ ] 公专 2,583 道题逐字段未被改动
  - [ ] pytest 失败集合 == 基线
  - [ ] 所有失败项已分类标注
  - [ ] 导入报告落 `backend/data/audit/xingce_import_report.md`

  **QA Scenarios**：

  ```
  Scenario: 分批全量导入成功（成功路径）
    Tool: Bash
    Preconditions: 已备份；任务 15 通过
    Steps:
      1. 按 24 批执行（国考 → 江苏 → 北京 → 广东 → 其余 20 省）
      2. 每批后断言三重门禁退出码均为 0
      3. 每批记录 13 项指标
      4. 全量后断言 subject_id=1 数量 > 10000
      5. 断言答案覆盖率 == 100.0
      6. 断言解析覆盖率 >= 98.0
      7. 断言考点覆盖率 >= 98.0
      8. 断言 24 个省份 exam_paper_tag.exam_province 全部正确
    Expected Result: 85 套全部完成；4 项总指标达标；24 省元数据正确
    Failure Indicators: 任一批门禁非 0（必须停下排查，禁止继续）
    Evidence: evidence/task-16-full-import.txt

  Scenario: 单批失败不影响已通过批次（失败路径 — 可恢复性）
    Tool: Bash
    Preconditions: 已完成 ≥5 批
    Steps:
      1. 人为构造一批含损坏 PDF 的导入
      2. 断言该批失败但前 5 批数据完好
      3. 断言已通过批次的 exam_paper / exam_paper_tag 未被回滚或污染
      4. 断言公专 2583 道题仍未受影响
      5. 修复后重跑该批，断言成功且与前批共存无重复
    Expected Result: 批次隔离有效；已通过数据不受影响
    Failure Indicators: 单批失败导致整库回滚或数据错乱（无批次隔离，必须停下重新设计）
    Evidence: evidence/task-16-batch-isolation.txt

  Scenario: 公专数据零影响终检（失败路径 — 红线）
    Tool: Bash
    Preconditions: 全量完成
    Steps:
      1. 对比全量前快照，断言公专 2583 道的
         question_content/options/answer/answer_analysis/type_id/group_id/need_review 逐字段一致
      2. 断言 knowledge_point 既有 126 点未被改写
      3. 断言 question_knowledge 既有 2292 行未被删除
      4. 断言 static/questions/ 下既有非空目录未被删除
      5. 断言 DB 4 份备份仍在（Q4 未清理）
    Expected Result: 公专数据与备份逐字节不变
    Failure Indicators: 任一公专字段变化（红线违反，立即回滚并从备份恢复）
    Evidence: evidence/task-16-gongzhuan-untouched.txt
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-16-full-import.txt` — 24 批 × 13 指标 + 4 项总指标
  - [ ] `evidence/task-16-batch-isolation.txt` — 批次隔离验证
  - [ ] `evidence/task-16-gongzhuan-untouched.txt` — 公专 2583 道逐字段比对

  **Commit**：YES
  - Message：`feat(xingce): import all 85 xingce papers (24 province batches)`
  - Files：`backend/data/audit/xingce_import_report.md`

- [ ] 17. 运维文档 + 方案归档 + `vtj.md` 勘误

  **What to do**：
  - **方案归档到 `solve_problems_files/`**（用户 G2 硬要求）：
    - `行测题目导入优化方案.md` — 本方案定稿
    - `行测导入门禁与运维手册.md` — 门禁命令、常见故障、回滚流程、批量重导入指引
    - 追加 `README.md` 索引（该文件现有 49 行，是本目录的索引入口）
  - **目录分层建议落地**（基于任务 6 盘点，用户授权范围内）：
    - 本目录已有约 150 份 md **扁平无索引** → 建议按 `01-架构/` `02-模块/` `03-运维/` `04-历史归档/` 分层
    - ⚠️ **只新建索引与 README，不移动既有文件**（移动会破坏大量既有引用，如 `vtj.md` §附录E 引用的页面 ID、`README.md` 的相对链接）
  - **`vtj.md` 勘误**（两处已确认错误）：
    - §5.4 / 第七章：设计器端口 `5173` → **9527**（`vite.config.ts:8` `DEV_PORT=9527`）
    - 附录F：「每次修改 .vue 后必须同步 .vtj/files/*.json」→ 改为「`raw: true` 页面**禁止**同步（同步工具有损，前序实证 48 方法中连 `_pollImportStatus` 都提取不到）」
  - **运维手册须含**：三重门禁命令、DB 备份/回滚流程、卡死 import 记录处理（**标注需单独授权**）、OCR/MinerU 环境现状（`D:\mineru-env` 不存在；行测无需 OCR）、文本缓存清理（铁律 R-1）、新增考点/分区的扩展流程

  **Must NOT do**：
  - ❌ 不得移动或重命名 `solve_problems_files/` 下既有 150 份文件
  - ❌ 不得清理 DB 4 份备份（Q4）
  - ❌ 不得清理 312 条卡死 import 记录（业务数据，待单独授权）
  - ❌ 不得删除 `text_cache.bak_20261001_200518`（前序备份，含「全文翻倍」旧文本的证据）
  - ❌ 不得在未获用户批准时执行任务 6 盘点出的任何删除动作

  **Recommended Agent Profile**：
  - **Category**：`writing`
    - Reason：文档产出与归档，无代码逻辑；但需精确引用实测数字，不得臆造
  - **Skills**：`[]`

  **Parallelization**：
  - **Can Run In Parallel**：NO
  - **Parallel Group**：Wave 5（依赖任务 16）
  - **Blocks**：F1
  - **Blocked By**：6, 16

  **References**：

  *Pattern References（文档归档的既有惯例）*：
  - `solve_problems_files/README.md` — **本目录的索引入口**，现有 49 行，含问题背景、根因表、文档索引、修改文件清单、运维要点。新文档须挂到此索引
  - `solve_problems_files/申论题目导入精准化方案_v4.md` — **执行规格类文档的格式范本**：文档版本/取代关系/实测依据/范围声明 → 操作铁律表 → 门禁表 → 实现规格（带落点文件与行号）→ 不变量 → 测试语料 → 波次 → 已完成
  - `solve_problems_files/题目导入四大问题根因分析与解决方案.md` — **「根因 + 证据链 + 审批 + 执行记录」范式**：其「执行记录」表逐项标注 ✅/⏸/◐ 与提交说明，是运维交接的关键结构
  - `CLAUDE.md/vtj.md` — 待勘误文件

  *运维事实（手册须准确记录）*：
  - 三重门禁命令（任务 2 建立）
  - pytest 基线 `16 failed / 168 passed / 52 errors`（铁律 R-4）
  - `D:\mineru-env` **不存在**；`D:\ocr-env` 存在（Python 3.11 + Paddle 2.6.2 + PaddleOCR 2.7.0.3）
  - 本机 Python **3.13.5** → 进程内 PaddleOCR 必崩 → 必须走 `ocr_worker.py` 子进程
  - `start.py` 看门狗（3 秒重启，连续 20 次熔断）
  - `config.OCR_MAX_PAGES = 8`，超时 240s
  - Vite 9527（`strictPort: true`），后端 8000

  **WHY Each Reference Matters**：
  - `README.md` 是本目录唯一的索引入口。不挂进去的文档等于不存在 —— 前序方案已有 150 份，其中不少因未挂索引而难以发现
  - `题目导入四大问题根因分析` 的「执行记录」表结构是运维交接的现成模板：状态符号 + 提交说明 + 遗留项，让接手者一眼看出哪些没做完
  - `vtj.md` 两处错误已在本次研究中实测确认。若不勘误，后续任何会话都会按 5173 访问设计器而失败，并可能违反 R-2 去同步 DSL

  **Acceptance Criteria**：

  - [ ] `solve_problems_files/行测题目导入优化方案.md` 存在
  - [ ] `solve_problems_files/行测导入门禁与运维手册.md` 存在，含三重门禁命令 + 回滚流程 + 扩展流程
  - [ ] `solve_problems_files/README.md` 索引已追加两个新文档条目
  - [ ] 既有 150 份 md **零移动、零重命名**（`git status` 仅新增 + README 修改）
  - [ ] `vtj.md` 端口已改为 9527（§5.4 与第七章两处）
  - [ ] `vtj.md` 附录F 已改为「raw:true 页面禁止同步」
  - [ ] 运维手册中所有环境事实与实测一致（Python 3.13.5 / 9527 / 8000 / mineru-env 不存在 / pytest 基线）
  - [ ] 手册明确标注「312 条卡死 import 记录需单独授权」「DB 备份需单独授权」

  **QA Scenarios**：

  ```
  Scenario: 文档归档且既有文件零扰动（成功路径）
    Tool: Bash
    Preconditions: 任务 16 完成
    Steps:
      1. git status --porcelain  断言仅含新增 2 个 md + README.md 修改
      2. 断言 solve_problems_files 下 md 文件数 == 原数 + 2
      3. 断言 README.md 索引含两个新条目且相对链接可解析
      4. 断言 DB 4 份备份仍在
      5. 断言 text_cache.bak_20261001_200518 仍在
    Expected Result: 归档完成；既有 150 份零扰动
    Failure Indicators: 既有文件被移动/重命名（git status 显示 R/D）
    Evidence: evidence/task-17-archive.txt

  Scenario: 手册命令可复制即用（失败路径 — 防止文档失真）
    Tool: Bash
    Preconditions: 手册已写
    Steps:
      1. 从手册逐条复制 6 条命令（G1/G2/pytest/行测查询/Vite 探测/回滚）
      2. 逐条粘贴执行，断言全部退出码符合手册描述
      3. 断言 pytest 输出 == 手册记录的基线数字
      4. 断言 curl localhost:9527 返回 200
      5. 断言回滚脚本 --help 可运行
    Expected Result: 手册命令全部可直接执行且与描述一致
    Failure Indicators: 任条命令失败或输出与手册不符（文档失真，必须修正）
    Evidence: evidence/task-17-manual-executable.txt

  Scenario: vtj.md 勘误生效（边界路径）
    Tool: Bash
    Preconditions: 勘误完成
    Steps:
      1. grep -n "9527" CLAUDE.md/vtj.md  断言命中 ≥2 处
      2. grep -n "5173" CLAUDE.md/vtj.md  断言已无残留（或仅在历史说明中）
      3. grep -n "禁止同步" CLAUDE.md/vtj.md  断言附录F 含该表述
      4. 断言 vtj.md 其余章节内容未被改动（git diff 行数 < 10）
    Expected Result: 两处错误已修正；其余内容零扰动
    Failure Indicators: 5173 仍作为设计器地址出现（后续会话会访问错误端口）
    Evidence: evidence/task-17-vtj-errata.txt
  ```

  **Evidence to Capture**：
  - [ ] `evidence/task-17-archive.txt` — `git status` + 文件数比对
  - [ ] `evidence/task-17-manual-executable.txt` — 6 条命令逐条执行结果
  - [ ] `evidence/task-17-vtj-errata.txt` — 勘误前后 grep 对比

  **Commit**：YES
  - Message：`docs(xingce): archive solution + ops manual; fix vtj.md port and DSL-sync guidance`
  - Files：`solve_problems_files/行测题目导入优化方案.md`、`solve_problems_files/行测导入门禁与运维手册.md`、`solve_problems_files/README.md`、`CLAUDE.md/vtj.md`

  ---

## Final Verification Wave

> 4 路并行评审，**全部 APPROVE 后**呈现给用户，**等待用户明确批准**才能标记完成。
> **禁止在评审通过后自动推进** —— 必须等用户点头。

- [ ] F1. **方案合规审计** — `oracle`
  逐条核对方案的 Must Have / Must NOT Have 与本计划的实际产出。
  - **Must Have 核验**（逐项给证据）：行测题型主数据、分区枚举、分节路由、配对安全网、考点树、材料题组、卷级元数据、图片切图、前端强化、三重门禁、试点 6 套、全量 85 套
  - **Must NOT Have 核验**（逐项 grep 证明未触发）：共享 dispatch 零改动、`extract_question_blocks` 函数体零改动、无新建题号解析器、无新建答案归一化、无新建题型判定、无新建表、未同步 DSL JSON、`block_accepts_letter_answer` 未撤销、未触碰公专数据、未清理 DB 备份、未改 `<template>`、未以 pytest 全绿为判据、312 条记录未动
  - **证据文件核验**：`.omo/evidence/` 下每个任务的证据文件是否存在且非空
  - **VTJ 版本一致性核验**：涉及的 `.vue` 的 `useProvider({id, version})` 与 `.vtj/files/*.json` 的 `__VERSION__` 是否仍一致（且确认未同步）
  - **后端路由完整性核验**：新端点是否注册、`/docs` 可见、前端调用路径与后端注册路径逐字符匹配
  - **前端可见性核验**：Playwright 实请求 9527，四处入口截图
  - 输出：`Must Have [N/N] | Must NOT Have [N/N] | 证据 [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **代码质量评审** — `unspecified-high`
  - 跑 `python -m pytest backend/tests -q`，断言**失败集合与基线 `16 failed / 168 passed / 52 errors` 完全一致**（铁律 R-4，不要求全绿）
  - 跑 `lsp_diagnostics` 于所有改动文件，比对基线错误集（基线已知：`text_parser.py:3000` 类型不匹配、`:3920` 可能未绑定、`:4199` max 重载 —— 这些是**既有**错误，不得增加）
  - 审查新增代码：`as any`/`@ts-ignore`/`# type: ignore`、空 `except`、`except Exception: pass`、生产代码 `print`、`console.log`、注释掉的代码、未用 import
  - AI slop 检查：过度注释、过度抽象、泛化命名（`data`/`result`/`item`/`temp`）、重复逻辑
  - 幂等性审查：所有迁移脚本重复执行的安全性
  - 安全审查：路径拼接、SQL 拼接（须全参数化）、异常信息泄露（`raise HTTPException(500, detail=str(e))` 会泄露内部栈 —— 既有代码有此模式，本任务新增代码不应加剧）
  - 输出：`pytest 基线一致 [PASS/FAIL] | LSP 无新增错误 [PASS/FAIL] | 代码整洁 [N issues] | 安全 [N issues] | VERDICT`

- [ ] F3. **真实手工 QA** — `unspecified-high` + `playwright`
  从干净状态走完整用户流程，证据落 `.omo/evidence/final-qa/`。
  - 全流程：登录（teacher/admin）→ `/question-import` → 上传题本 → 上传答案解析 → 预览（分区/徽标/考点/材料）→ 确认入库 → 试卷管理可见 → 学生端 `/student/papers` 筛选行测 → 答题页作答 → 提交 → 成绩报告 → 错题集 → `/materials/xingce`
  - 边界用例：blocked 卷（按钮应禁用）、`need_review` 题（🔴 徽标）、纯图片题（图片加载 + 选项可点）、资料分析题（材料显示 + 5 小题）、多选题（多选提交与批阅）、选非题（答案正确性）
  - 跨任务集成：图片切图 → 答题页渲染 → 解析展示 三段链路联通
  - 空态：筛选无结果时的表现
  - 快速操作：连续快速切换筛选/翻页无报错
  - 控制台零报错、Network 无 4xx/5xx
  - 输出：`场景 [N/N] | 集成 [N/N] | 边界 [N tested] | 控制台 [N errors] | VERDICT`

- [ ] F4. **范围保真检查** — `deep`
  - 逐任务读「What to do」，比对 `git diff` 实际改动，验证 1:1 —— 既无缺失，也无超范围
  - **重点核查越界**：
    - 是否动了任何公专数据（`git diff` 中是否有 `question_bank` 的公专行 UPDATE 脚本）
    - 是否新建了本该复用的表/函数（搜 `CREATE TABLE`、搜新建的 `def _detect_*` / `def canonical_*`）
    - 是否顺手改了任务范围外的东西（如 `mobile_*` / `tablet_*` 页面）
    - 是否动了 `solve_problems_files/` 既有 150 份文件
  - **跨任务污染检测**：任务 N 是否触碰了任务 M 的文件（应只有共享的 `text_parser.py` / `question_import.py` 允许，且各自区块独立）
  - **未记账改动**：逐个 `git status` 条目归因，无法归因的即视为越界
  - 输出：`任务 [N/N 合规] | 越界 [CLEAN/N issues] | 跨任务污染 [CLEAN/N] | 未记账 [CLEAN/N] | VERDICT`

---

## Commit Strategy

| 组 | 提交 | 消息 | 文件 |
|---|------|------|------|
| 1 | 1 | `feat(xingce): add read-only corpus probe and diagnose 110-vs-101 discrepancy` | `backend/scripts/probe_xingce_corpus.py` |
| 1 | 2 | `test(xingce): add xingce regression gate with section-interval assertions` | `backend/scripts/verify_xingce_regression.py` + 3 基线文件 |
| 1 | 3 | `feat(db): add idempotent migration for xingce question types` | `backend/scripts/migrate_xingce_question_types.py` |
| 1 | 4 | `feat(xingce): add 科学推理 to xingce subcategory enums (3 locations)` | `models.py` / `question_import.py` / `question_classifier.py` |
| 1 | 5 | `docs(xingce): knowledge-point taxonomy spec for 461 tokens` | `solve_problems_files/行测考点词表规范.md` + `xingce_kao_points.json` |
| 1 | 6 | `docs(ops): inventory cleanup candidates (no deletion)` | `backend/data/audit/xingce_cleanup_inventory.md` |
| 2 | 7 | `feat(xingce): add route_xingce_sections with >=2-anchor safety gate` | `text_parser.py` |
| 2 | 8 | `feat(xingce): add section-interval cross-validation for question/answer pairing` | `text_parser.py` |
| 2 | 9 | `feat(xingce): recognise 资料分析 material blocks via full-width paren anchors` | `composite_matcher.py` |
| 2 | 10 | `feat(xingce): extract and hierarchically store 461 knowledge-point tokens` | `migrate_xingce_knowledge_points.py` + `text_parser.py` |
| 3 | 11 | `feat(xingce): add dedicated separate-match-xingce endpoint (shared dispatch untouched)` | `question_import.py` |
| 3 | 12 | `feat(xingce): inject paper metadata from folder name (not filename)` | `question_import.py` |
| 3 | 13 | `feat(xingce): tune image thresholds and flag incomplete questions for review` | `question_import.py` + `models.py`(注释) |
| 4 | 14 | `feat(xingce): route xingce to dedicated endpoint and surface review markers in import preview` | `.vtj/vue/question_import.vue` |
| 4 | 15 | `test(xingce): pilot 6 papers and freeze as regression corpus` | 门禁语料 + 试点配置 |
| 5 | 16 | `feat(xingce): import all 85 xingce papers (24 province batches)` | `backend/data/audit/xingce_import_report.md` |
| 5 | 17 | `docs(xingce): archive solution + ops manual; fix vtj.md port and DSL-sync guidance` | 2 新文档 + `README.md` + `vtj.md` |

**提交纪律**（继承前序）：
1. 每任务提交前，三重门禁必须全绿
2. 跨任务共享文件（`text_parser.py` / `question_import.py` / `models.py`）的**新增区块必须物理独立**，便于 `git diff` 归因与回滚
3. 禁止 `git push`（需用户明确指示）
4. Wave 2 内任务 7→8 因同改 `text_parser.py` 须串行提交

---

## Success Criteria

### Verification Commands

```bash
# ── 前置：后端 8000 + Vite 9527 ──
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9527/          # 期望 200

# G1 公专门禁（基线：30 份 / 2899 块 / 污染 0 / PASS）—— 每波必跑
python backend/scripts/verify_parser_regression.py "D:\砺安题库\砺安题库\题库\公安题目（打印）" --out tmp/g1

# G2 行测门禁（任务 2 建立）
python backend/scripts/verify_xingce_regression.py "D:\砺安题库\砺安题库\题库\行测" --out tmp/g2
python backend/scripts/verify_xingce_regression.py "D:\砺安题库\砺安题库\题库\行测" --compare tmp/g2/baseline.txt --out tmp/g2/cmp

# pytest（判据：失败集合与基线一致，不是零失败 —— 铁律 R-4）
python -m pytest backend/tests -q 2>&1 | tail -20       # 期望 16 failed / 168 passed / 52 errors

# 行测入库结果
python -c "import sqlite3;c=sqlite3.connect(r'file:D:\砺安题库\砺安题库\backend\data\question_bank.db?mode=ro',uri=True);print(c.execute('select count(*) from question_bank where subject_id=1').fetchone())"

# 答案/解析/考点覆盖率
python -c "import sqlite3;c=sqlite3.connect(r'file:D:\砺安题库\砺安题库\backend\data\question_bank.db?mode=ro',uri=True);q=c.execute('select count(*),sum(answer<>\'\'),sum(answer_analysis<>\'\'),sum(need_review) from question_bank where subject_id=1').fetchone();print(q)"

# 公专数据未受影响
python -c "import sqlite3;c=sqlite3.connect(r'file:D:\砺安题库\砺安题库\backend\data\question_bank.db?mode=ro',uri=True);print(c.execute('select count(*) from question_bank where subject_id=3').fetchone())"   # 期望 2583

# 端点实请求（经 Vite 代理，G8 强制）
curl -s -X POST http://localhost:9527/api/questions/import/separate-match-xingce -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d @tmp/payload.json
```

### Final Checklist

**方案合规**
- [ ] 所有「Must Have」均已交付并有证据
- [ ] 所有「Must NOT Have」均未被触发（F1 逐项 grep 证明）
- [ ] 共享 dispatch `question_import.py:4005-4011` 字节级未改
- [ ] `extract_question_blocks` 函数体字节级未改
- [ ] 未新建题号解析器 / 答案归一化 / 题型判定 / 表

**质量**
- [ ] G1 公专门禁 7 项断言逐项与基线一致
- [ ] G3 申论不变量全通过
- [ ] G2 行测门禁 ≥ 0.99
- [ ] pytest 失败集合 == 基线
- [ ] LSP 无新增错误（既有 3 个错误为基线）

**数据**
- [ ] 行测题目 > 10,000 道
- [ ] 答案覆盖率 100%，解析覆盖率 ≥ 98%，考点覆盖率 ≥ 98%
- [ ] 公专 2,583 道题逐字段未变
- [ ] 24 省份元数据 100% 正确
- [ ] DB 4 份备份保留；312 条卡死记录保留

**前端（G8）**
- [ ] `.vtj/vue/question_import.vue` 的 `<template>` 零改动
- [ ] `.vtj/files/question_import.json` 零改动（R-2）
- [ ] Playwright 实请求 9527 截图：题库页 / 资料页 / 试卷页 / 答题页 四处可见
- [ ] 行测分流命中新端点；申论/公专仍走原端点
- [ ] 控制台零报错

**交付**
- [ ] 方案 + 运维手册已归档 `solve_problems_files/` 并挂 `README.md` 索引
- [ ] `vtj.md` 两处错误已勘误
- [ ] F1–F4 全部 APPROVE
- [ ] **用户明确批准**

---

## 附：本方案的文档冲突裁定（需用户确认）

| 冲突 | 本方案裁定 | 建议 |
|------|-----------|------|
| `CLAUDE.md/vtj.md` 附录F 要求每次改 `.vue` 必同步 DSL JSON | **遵从铁律 R-2 禁止同步** | 修正 `vtj.md` 附录F，改写为「raw:true 页面禁止同步」 |
| `CLAUDE.md/vtj.md` §5.4 记设计器端口 5173 | **以 `vite.config.ts:8` 的 9527 为准** | 修正 `vtj.md` §5.4 与第七章 |
| `models.py` Enum 缺 `科学推理`（3 套卷实测存在） | 补入（任务 4） | — |
| 312 条卡死 import 记录（305 PREVIEW / 6 PARTIAL / 1 PARSING） | **本方案不动**（用户 Q4，**明确未授权**） | 需单独授权后清理 |
| `backend/data/` 4 份 DB 备份约 430MB | **本方案不动**（用户 Q4，**明确未授权**） | 需单独授权后清理 |
| 死代码 + 空目录（MinerU 死目录 / 0 字节 .db 占位 / 空图片目录） | ✅ **已授权执行**（用户 2026-10-03） | 见任务 6 阶段 B |
