# 快速练习知识分层：知识图谱与 Obsidian 自生长知识库 设计方案 v1

> 状态：**待审批（P0 设计定稿，未实施）**
> 日期：2026-11-05
> 分支：**main**（按要求在主干设计）
> 目标知识库：**D:/Obsidian仓库/快速练习知识分层**
> 关联：docs/superpowers/specs/题目入库知识图谱与四库映射_v1.md、docs/superpowers/specs/砺安题库终态总体架构_v2.0.md、docs/superpowers/specs/题库设计模式_v3.md、AGENTS.md
> 原则：**SQLite 是唯一事实源（SoT）；Obsidian 是设计态与治理控制台；图库是可重建投影；未经审批不写库、不改运行代码。**

---

## 0. 一页纸结论

1. **方向正确，但第一版方案有 6 处会直接做错的硬点**：把 Neo4j 当运行态默认、把父子层级当先修、把同父兄弟当并行、把“题→知识点”当实例化、把 Canvas 连线当可编译关系、把“100% 对标大纲”当既成事实。本方案逐条校正。
2. **四层是“类型”，不是“强制等深”**。科目→知识域→知识点→考点是四种节点类型；允许知识点没有考点（标记 teaching-only），但绝不允许为了凑四层而造虚假考点。这是科学分层的第一条。
3. **关系从 3 条扩展为 8 条，但每条都有准入条件**：CONTAINS、INSTANCE_OF、PREREQUISITE_OF、PARALLEL_WITH、CONTRAST_WITH、COGNITIVE_SHARED_WITH、ASSESSES、SYLLABUS_MAPS_TO。前两条是结构，后六条是学习/评价/大纲语义。
4. **Obsidian 绝对有必要，但不是运行库**。它解决的是 1000+ 节点的人工评审、证据留痕、大纲对齐、跨科关系策展与合作伙伴交接；这些是数据库和后台管理页都不擅长的事。
5. **运行态继续用现有 local SQLite GraphStore，不引入 Neo4j**。实测 GRAPH_BACKEND 默认 local，Neo4j 只是可选适配器；当前规模（3823 节点/4354 边）远未到必须上 Neo4j 的程度。上 Neo4j 需要单独 ADR 与容量证据。
6. **治理的关键不是“画图”，而是“编译”**：Obsidian 只写“策展覆盖层”，编译器产出 manifest、diff、SQL patch、graph plan；dry-run 默认，apply 前 sqlite3.backup()，失败可回滚。AI 永远只写收件箱。
7. **现有分类需要一次“基线归位”，不能直接当四层用**：495 个挂在域下的 L2、525 个 L3、只有 7 个 L4；358 个 L2 无子；21 个 L2 无域；63 组同科目重名；664 道题无知识点关系。这些必须在 P2 分批治理，不能靠脚本一键重排。
8. **“完全按照大纲”要可验证**：建立大纲条目参考层与对齐矩阵；每个节点要么有大纲条目引用，要么显式标为“本地扩展/待确认”。当前公专“基本警务能力”与官方“基本能力”存在命名偏差；行测“政治理论/科学推理”需教研确认，不能宣称大纲原生。
9. **验收以硬指标为准**：断链 0、先修环 0、层级违规 0、每条策展边有证据、题点覆盖≥95%、大纲条目覆盖≥90%、编译可重复、apply 可回滚。
10. **本轮只交付设计与审批材料，不建库、不改库、不改代码**。用户批准后再按 P1→P4 执行。

---

## 1. 需求、目标与边界

### 1.1 用户目标（原话要点）

- 管理“快速练习”的分类：**科目—知识域—知识点—考点**。
- 三类关系：**先修边**（掌握 A 是学习 B 的前提）、**并行边**（同一执法场景协同出现）、**实例化边**（考点是知识点的具体命题形态）。
- 知识分类必须**完全按照历年公安联考考试大纲**分层，科学合理。
- 评估**是否有必要在 Obsidian 做知识图谱框架视图**，用于监控分层是否合理、随时微调。
- 交付**完整的基础 Obsidian 知识库框架**，便于合作伙伴继续优化。
- 深度设计**自生长知识库**：实用、合理、科学、便捷、可视化、关系网基本遍布且联系紧密。
- 针对第一版方案深度适配系统现有配置；最终方案经用户审批后才实施；直接在 main 设计；实际知识库建在 D:/Obsidian仓库/快速练习知识分层。

### 1.2 本方案不做什么

- **不**在本轮创建 Obsidian 文件、目录、Canvas。
- **不**修改 knowledge_point / sub_categories / question_bank 任何数据。
- **不**修改 graph_builder.py / graph_query.py / API / 前端。
- **不**新增 Neo4j 依赖或迁移。
- **不**做题库业务功能改造（组卷、推荐、错题本不在本轮范围）。
- **不**承诺“当前分类已经 100% 等于大纲”；本方案交付的是可验证的对齐机制与差异台账。

### 1.3 审批门

本方案是 **QBDM 设计态 Q2 产物**。只有用户明确批准以下三件事，才进入 P1：

1. 认可第 4 章的本体与 8 条关系；
2. 认可第 9 章的“覆盖层 + 编译器 + dry-run/apply”接入方式；
3. 认可第 11 章的 P1 范围（只建库与基线导入，不改数据库、不改代码）。

---

## 2. 实测基线与第一版方案校正

### 2.1 系统实测基线（2026-11-05）

| 项 | 实测值 | 口径/来源 |
|---|---:|---|
| 科目 | 3 | 行测(1)、申论(2)、公专(3) |
| 知识域（sub_categories） | 16 | 行测 8、申论 5、公专 3 |
| knowledge_point 总数 | 1049 | level2=516、level3=526、level4=7 |
| 挂在域下的 L2 | 495 | 另 21 个 L2 的 sub_category_id 为 NULL |
| L3 | 525 | 挂在 L2 下 |
| L4 | 7 | 极少，说明“考点层”基本缺失 |
| 最大层级深度 | 2 | L2 以下最多两层 |
| 可见题 | 3410 | question_bank.status=1（全表 3632） |
| 已进 question_knowledge 的去重题 | 2923 | 无任何 qk 关系的题 664 |
| 有 sub_category 但 point 为空 | 758 | 题挂域但未挂点 |
| 题 subcat 与点 subcat 不一致 | 4 | 数据质量问题 |
| 多挂题 | 1 | 几乎不存在多知识点标注 |
| 叶子知识点 | 906 | 其中 831 个叶子无题 |
| L2 无子节点 | 358 | 含未归属则 377；占 L2 的 72% |
| 单父最多子节点 | 13 | 存在过宽容器 |
| 同科目重名 | 63 组 | 文件名必须带 ID，不能只靠标题 |
| 跨科目同名 | 5 组 | 词句理解、公文写作、政治立场与忠诚度、政治建设、其他 |
| 含“其他”节点 | 134 | 容器/垃圾命名风险 |
| “待归类-*”节点 | 3 | 公专三个域各一个 |
| 图投影节点 | 3823 | KnowledgePoint 1049 + Question 2774 |
| 图投影边 | 4354 | INSTANCE_OF 2775、PARALLEL_WITH 1046、PREREQUISITE_OF 533 |
| 孤立知识点图节点 | 374 | 没有任何图边 |
| graph backend | local（默认） | GRAPH_BACKEND=local；Neo4j 仅可选适配器 |
| 快速练习 API | 5 个核心读接口 + submit | subjects / sub-categories / knowledge-points / questions / submit |
| 现有图查询 | 不注册 HTTP 路由 | graph_query.py 文档明确不返回业务页面 |

分域实测（L2/L3/L4/可见题/L2无子/L2子树无题/L3叶子无题）：

| 科目 | 知识域 | L2 | L3 | L4 | 题 | L2无子 | L2子树无题 | L3叶子无题 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 行测 | 政治理论 | 28 | 23 | 0 | 20 | 21 | 24 | 19 |
| 行测 | 常识判断 | 41 | 31 | 0 | 12 | 34 | 36 | 26 |
| 行测 | 言语理解与表达 | 74 | 39 | 5 | 41 | 63 | 70 | 33 |
| 行测 | 数量关系 | 72 | 21 | 0 | 9 | 65 | 70 | 19 |
| 行测 | 判断推理 | 149 | 70 | 0 | 52 | 115 | 145 | 66 |
| 行测 | 资料分析 | 40 | 14 | 0 | 18 | 37 | 36 | 11 |
| 行测 | 知觉速度与准确性 | 4 | 12 | 0 | 2 | 1 | 2 | 11 |
| 行测 | 科学推理 | 24 | 19 | 2 | 0 | 19 | 24 | 17 |
| 申论 | 归纳概括 | 6 | 24 | 0 | 8 | 0 | 4 | 23 |
| 申论 | 综合分析 | 5 | 21 | 0 | 4 | 0 | 3 | 20 |
| 申论 | 提出对策 | 5 | 21 | 0 | 4 | 0 | 2 | 18 |
| 申论 | 应用文写作 | 4 | 23 | 0 | 4 | 0 | 0 | 20 |
| 申论 | 议论文写作 | 5 | 20 | 0 | 8 | 0 | 1 | 17 |
| 公专 | 职业素养 | 6 | 23 | 0 | 124 | 1 | 1 | 19 |
| 公专 | 基础知识 | 12 | 77 | 0 | 1738 | 1 | 0 | 66 |
| 公专 | 基本警务能力 | 20 | 87 | 0 | 698 | 1 | 0 | 68 |
| 合计 | 16 域 | 495 | 525 | 7 | 2742 | 358 | 418 | 453 |

> 说明：上表“题”为按域统计的可见题；总额 2742 与全库 3410 的差额来自未归属/未挂域的题，需在 P2 对账，不在本轮猜测。

### 2.2 第一版方案必须校正的 6 处

| # | 第一版说法 | 实测/问题 | 后果 | 本方案校正 |
|---|---|---|---|---|
| C1 | 题库系统底层用 Neo4j 作为运行引擎 | 实测 GRAPH_BACKEND 默认 local SQLite GraphStore；Neo4j 只是可选适配器，且当前无 Neo4j 数据 | 引入不必要的运维复杂度、双写一致性风险 | **继续 local**；Neo4j 仅在容量/算法证据充分时单独立项 |
| C2 | 父→子层级关系就是先修边 | 现有 533 条 PREREQUISITE_OF 全部由 parent_id 生成，props 标 derivation=hierarchy | AI 会把“上级分类”误当“学习前提”，路径推荐失真 | 父→子改为 **CONTAINS**；先修边必须人工审定、有依据、成 DAG |
| C3 | 同父兄弟就是并行边 | 现有 1046 条 PARALLEL_WITH 由 siblings 笛卡尔组合生成，是噪声 | 图谱变成“同班同学全连接”，关系网虚假密集 | 并行边必须人工策展；同父兄弟最多是“同域”，不是并行 |
| C4 | 题→知识点是实例化边 | 现有 2775 条 INSTANCE_OF 是 Question→KnowledgePoint | “实例化”语义错位；考点层永远建不起来 | 实例化改为 **ExamPoint→KnowledgePoint**；题→考点用 **ASSESSES** |
| C5 | Obsidian 拖拽/连线后经 MCP 同步 Neo4j | Canvas 连线不是结构化边；MCP 不是图谱编译器；Local REST API 也不是为批量写库设计 | 关系无法校验、无法回滚、无法追责 | **frontmatter 是策展源，Canvas 只做沟通**；编译器解析、校验、生成 patch |
| C6 | 现有分类已按大纲分层 | 公专库内名“基本警务能力”与官方“基本能力”不一致；行测“政治理论/科学推理”需确认；21 个无域 L2、358 个无子 L2、仅 7 个 L4 | 对外宣称“完全对标”会被教研/合作方质疑 | 建 **大纲条目参考层 + 对齐矩阵 + 差异台账**；状态分为 aligned/partial/extension/missing |

补充校正：

- **“知识点是最小教学单元、考点是最小命题形态”方向正确**，但现有 knowledge_point 把两者混在同一张表、同一套 level 里，必须靠 node_type 与判定标准拆开，不能靠 level 数字硬切。
- **“Obsidian 是设计态、Neo4j 是运行态”的二态划分不够**。实际需要三态：设计态（Obsidian）→ 编译态（manifest/patch/plan）→ 运行态（SQLite 投影）。缺了编译态，设计与运行之间就是“口头同步”。
- **“关系网基本遍布”不能理解为全连接**。科学目标是稀疏小世界：giant component ≥90%、平均度 3–6、无孤立节点、先修 DAG 无环、跨科桥 ≤30 条；不是每个点都连每个点。

### 2.3 可行性判断

- **技术可行**：现有 foundation 图投影、graph_schema、GraphStore、content_guard 的 Obsidian 导出/清单/幂等写入范式都可复用；不需要新框架。
- **真正的难点不是图数据库，而是分类归位**：1049 个节点里只有 7 个 L4，358 个 L2 无子，63 组重名，134 个“其他”。这是一次教研治理工程，必须分批、留痕、可回滚。
- **最大风险是“为了四层面造节点”**：会造成大量空考点、假先修、关系噪声。本方案用“类型而非等深”+“证据门槛”+“边预算”抑制。

---

## 3. 设计原则与不变量

### 3.1 十条原则

1. **大纲锚定**：每个学习节点必须能追溯到大纲条目，或显式标为本地扩展/待确认；不允许“来源不明”。
2. **可教学/可命题二分**：知识点回答“教什么”，考点回答“怎么考”；两者不混。
3. **单一结构父**：每个节点只有一个结构父；跨域联系走语义边，不靠重复建节点。
4. **四层是类型，不是强制等深**：允许 L3 无 L4，但必须标 teaching-only；不允许 L4 无 L3。
5. **关系必须有理由**：先修/并行/易混/跨科边必须写 rationale + evidence；无证据只能停在收件箱。
6. **结构边与学习边分离**：CONTAINS/INSTANCE_OF 是结构；PREREQUISITE_OF 是学习顺序；两者不能混。
7. **稀疏但连通**：边预算 + 小世界指标；拒绝“同父全连接”和“全图大乱连”。
8. **单一事实源 + 可重建投影**：SQLite 是 SoT；Obsidian 只写覆盖层；图库可重建。
9. **不删除，只退役**：deprecated + successor + tombstone；任何删除都不可逆，禁止。
10. **人机边界**：AI 只写收件箱和生成报告；人负责判定、签字、批准；系统负责编译、备份、执行。

### 3.2 图不变量（编译器和测试必须检查）

| 编号 | 不变量 | 违反处理 |
|---|---|---|
| G1 | 每个 L2 恰有一个 L1 父 | 编译错误 |
| G2 | 每个 L3 恰有一个 L2 父 | 编译错误 |
| G3 | 每个 L4 恰有一个 L3 父（INSTANCE_OF） | 编译错误 |
| G4 | CONTAINS ∪ INSTANCE_OF 无环 | 编译错误 |
| G5 | PREREQUISITE_OF 是 DAG | 编译错误，列出环路径 |
| G6 | PARALLEL_WITH / CONTRAST_WITH 对称、无自环、只存一次 | 自动规范化 + 警告 |
| G7 | COGNITIVE_SHARED_WITH 必须跨科目 | 编译错误 |
| G8 | ASSESSES 只能 Question→L4；L3 需标 granularity=knowledge_point | 编译警告/错误 |
| G9 | 每条策展边必须有 evidence 与 status | 编译错误（draft 边除外） |
| G10 | 退役节点仍保留，边指向退役节点要标记 | 警告 + 报告 |

---

## 4. 知识本体

### 4.1 四层 + 一个参考层

| 层 | 类型 | 定义 | 判定问题 | 现有对应 |
|---|---|---|---|---|
| L1 | Subject 科目 | 考试科目 | 是否是大纲中的独立科目？ | question_subject 3 条 |
| L2 | Domain 知识域 | 大纲的稳定一级模块 | 是否是大纲/教研公认的一级板块？ | sub_categories 16 条 |
| L3 | KnowledgePoint 知识点 | 可教学的最小单元 | 能否在 20–45 分钟讲清一个定义/流程/场景？ | knowledge_point 的 L2/L3 候选 |
| L4 | ExamPoint 考点 | 可命题的具体形态 | 能否写出题干、答案、干扰项，并稳定复用？ | knowledge_point 的 L3/L4 候选，仅 7 个明确 L4 |
| R | SyllabusItem 大纲条目 | 大纲原文条目的引用节点 | 是否能在年度大纲中定位到原文？ | 新建，放在 02-大纲 |

**关键裁定**：SyllabusItem 不是学习层级，不参与“四层”；它只用于覆盖与追溯。Scenario（情境）不是第五层，而是 L3 的一种 knowledge_kind。

### 4.2 分层判定标准（可操作，不靠感觉）

**L3 知识点准入（全部满足）**

1. 有一个可复述的核心定义、原则、流程或场景处置框架。
2. 能拆出 3–7 个构成要素/步骤/风险点。
3. 能用 20–45 分钟教学（或一节课的一个小节）。
4. 至少能衍生 2 种不同命题形态，或明确标注“仅教学、暂不命题”。
5. 不属于“其他/综合/待归类/misc”容器。
6. 名称是名词短语，不含“等”“及其他”这类开放集合。

**L4 考点准入（全部满足）**

1. 对应一个可辨识的命题决策点（辨析、计算、程序排序、法条适用、案例定性等）。
2. 能写出稳定题干模板 + 正确答案 + 2–4 个干扰项逻辑。
3. 单题 1–5 分钟可完成。
4. 只归属一个主 L3（跨领域联系走并行/易混边）。
5. 有至少 1 道真题/样题，或教研明确标注“预测考点”。

**容器/垃圾识别（不得作为 L3/L4）**

- 名称含“其他”“待归类”“综合”“misc”“待定”。
- 只有标题、没有定义/流程/题型的空壳。
- 纯导航节点（如“普通考法”“特殊问法”“变形考法”）：应改为 EP 的 exam_form 属性，而不是节点。
- 同一概念在不同科目重复出现：保留各自 L3，但加 COGNITIVE_SHARED_WITH 桥；不合并成一个跨科节点。

### 4.3 节点类型与属性

| 类型 | 必填属性 | 可选属性 | 说明 |
|---|---|---|---|
| Subject | node_id, title, code, status | description, syllabus_refs | 3 个 |
| Domain | node_id, title, subject, syllabus_group, status | description, order | 16 个；syllabus_group 用于公专“基本能力”五组等 |
| KnowledgePoint | node_id, title, subject, domain, knowledge_kind, difficulty, status, review | exam_weight, prerequisites, parallel_with, contrasts_with, cognitive_shared_with, scenario_profile, syllabus_refs, aliases | 核心层 |
| ExamPoint | node_id, title, parent_kp, exam_form, difficulty, status, review | question_types, frequency, last_exam_years, syllabus_refs, aliases | 核心层 |
| SyllabusItem | syllabus_id, year, subject, module, official_text, source, status | source_url, retrieved_at, notes | 参考层，不参与学习路径 |

knowledge_kind 枚举：

- concept：概念/原则/法条
- procedure：程序/流程/步骤
- scenario：情境处置（接处警、盘查、巡逻等）
- principle：原理/方法/公式
- skill：能力/技巧（言语、逻辑、速算等）

scenario_profile 仅 scenario 必填：

- trigger：触发情境
- legal_basis：法律依据（列表）
- steps：处置步骤（有序）
- risks：风险点/常见错误
- boundaries：权限边界/禁止事项

### 4.4 关系类型（8 条）

| 关系 | 方向 | 语义 | 基数 | 谁维护 | 证据要求 |
|---|---|---|---|---|---|
| CONTAINS | L1→L2、L2→L3 | 结构包含 | 1:N | 编译器从 parent 派生 | 结构事实，不需额外证据；跨域需说明 |
| INSTANCE_OF | L4→L3 | 考点是知识点的具体命题形态 | N:1（每个 L4 一个主 L3） | 编译器从 parent_kp 派生 | 需说明命题形态 |
| PREREQUISITE_OF | A→B | 学 A 是学 B 的前提 | DAG | 人工策展 | 必须：rationale + evidence + strength |
| PARALLEL_WITH | 对称 | 同一场景协同/共享能力 | 无向，存一次 | 人工策展 | 必须：场景或共享能力说明 |
| CONTRAST_WITH | 对称 | 易混/易错对比 | 无向，存一次 | 人工策展 | 必须：差异点 + 反例 |
| COGNITIVE_SHARED_WITH | 对称，跨科目 | 底层认知能力共享 | 稀疏，全局≤30 | 人工策展 + 评审 | 必须：能力迁移机制 + 证据 |
| ASSESSES | Question→L4（或 L3 带标记） | 题目考查考点 | N:1 | 系统从 question_knowledge 派生 | 来源、置信度、role |
| SYLLABUS_MAPS_TO | SyllabusItem→节点 | 大纲条目映射 | N:M | 人工/编译器 | 大纲原文 + 年份 |

**方向语义固定**：

- PREREQUISITE_OF：A→B 读作“A 是先修，B 是后继”。graph_query 对 B 查入边得到 A。
- INSTANCE_OF：EP→KP，读作“EP 是 KP 的一个实例”。
- ASSESSES：Question→EP，读作“这道题考查这个考点”。
- COGNITIVE_SHARED_WITH：双向，但只存一条，编译器补反向。

### 4.5 关系判定手册

**决策树**

1. 是上下级分类吗？→ CONTAINS（L1/L2/L3）或 INSTANCE_OF（L4→L3）。
2. 是“不学 A 就学不会 B”吗？→ PREREQUISITE_OF；再问 strength：hard（考试必需）/ soft（推荐）。
3. 是“同一情境一起出现/同一能力共同支撑”吗？→ PARALLEL_WITH；写清是 scenario_cooccur 还是 skill_shared。
4. 是“容易混淆、需要对比记忆”吗？→ CONTRAST_WITH；写差异点。
5. 是“跨科目底层能力迁移”吗？→ COGNITIVE_SHARED_WITH；必须跨科，且全局预算内。
6. 是“这道题考哪个点”吗？→ ASSESSES；由题目关系派生，不手写。
7. 是“大纲哪一条”吗？→ SYLLABUS_MAPS_TO；写在 02-大纲。

**反模式（编译器应拒绝或警告）**

| 反模式 | 为什么错 | 正确做法 |
|---|---|---|
| 父节点当先修 | 分类包含不等于学习顺序 | 用 CONTAINS；先修另建 |
| 同父兄弟全部并行 | 组合爆炸、噪声 | 只连真正同场景/同能力的 |
| “相关”这种无类型边 | 无法推理、无法验收 | 必须落到 8 类之一 |
| 一个考点挂多个主知识点 | 路径推荐冲突 | 一个主 L3；其余用并行/易混 |
| 跨科边当硬先修 | 学科顺序不成立 | COGNITIVE_SHARED_WITH，仅建议 |
| 为凑层造空考点 | 污染统计与推荐 | teaching-only 标记 |
| 用“其他”当容器 | 永远无法治理 | 拆解/退役 |
| 双向边存两条 | 重复计数 | 编译器规范化 |

### 4.6 粒度、深度、边预算

**粒度红线**

- 一个 L3 的 L4 数量 >15，或题量 >200，或覆盖 >3 个大纲条目 → 触发拆分评审。
- 一个 L3 没有任何定义/流程/场景，且只有 1 个 L4 → 触发合并/降级评审。
- 一个 L4 题量 >30，或混入 3 种以上无关题型 → 触发拆分。
- 一个 L4 只有 1 道题且无复用模板 → 标 single_use，不进入推荐主路径。

**深度**

- 目标 3–5 层；超过 5 层必须折叠中间容器。
- 分支可以不等深：某域 L3 有 L4，另一域 L3 只有教学卡；用 coverage_status 区分。
- 科目/域不计入“学习深度”。

**边预算（防止毛球）**

| 节点 | 入边先修 | 出边先修 | 并行 | 易混 | 跨科 |
|---|---:|---:|---:|---:|---:|
| L3 | 1–3 | 1–4 | 0–3 | 0–2 | 0–1 |
| L4 | 0–2 | 0–2 | 0–2 | 0–1 | 0 |
| 全局 | — | — | — | — | ≤30 |

- 单节点总度 >8 → 警告；>12 → 拒绝。
- 单域内部边数 >3×节点数 → 拒绝，要求拆分/降噪。
- 先修 hard 边占比 ≤40%；其余为 soft。

### 4.7 ID、文件名、别名

**ID 规则**

- Subject：sub:1、sub:2、sub:3（与现有 subject_id 对齐）。
- Domain：dom:<sub_category_id>（如 dom:14）。
- KnowledgePoint：kp:<point_id>（沿用现有 point_id）；新建节点用 kp:new-<ulid>，编译通过后由脚本分配正式 ID。
- ExamPoint：ep:<point_id>；新建用 ep:new-<ulid>。
- SyllabusItem：syl:<year>:<subject>:<seq>。
- 边：e:<rel>:<src>:<dst>（规范化排序），用于审计与去重。

**文件名规则（解决 63 组重名）**

- 知识点：kp_<6位point_id>_<标题>.md，例如 kp_000123_行政处罚的种类与设定.md。
- 考点：ep_<6位point_id>_<标题>.md。
- 域：dom_<2位id>_<名称>.md。
- 科目：sub_<id>_<名称>.md。
- 大纲条目：syl_<year>_<科目>_<序号>.md。
- 文件名中的标题只做可读性，**唯一性由 ID 保证**；重命名标题不改 ID。
- 所有 wikilink 指向文件名；frontmatter 的 node_id 才是稳定身份。

**别名**

- aliases 放同义词/旧名/简称；Dataview 与编译器都建 alias 索引。
- 跨科同名（如“词句理解”）不合并；通过 subject 与 ID 区分，必要时加 COGNITIVE_SHARED_WITH。

### 4.8 现有 DB 到目标本体的映射

| 现有对象 | 目标 | 处理 |
|---|---|---|
| question_subject 3 条 | L1 Subject | 直接映射 |
| sub_categories 16 条 | L2 Domain | 直接映射；公专“基本警务能力”加显示别名“基本能力” |
| knowledge_point.level=2 且挂在域下（495） | L3 候选 | 默认 L3；若实为命题形态，P2 降为 L4 |
| knowledge_point.level=3（525） | L4 候选或 L3 | 按 4.2 判定；不能批量一刀切 |
| knowledge_point.level=4（7） | L4 | 保留 |
| knowledge_point.level=2 且无域（21） | 待归位 | 先挂域或退役；不得留在无域状态 |
| question_knowledge | ASSESSES | 保留 SoT；映射到 L4；若只到 L3，标 granularity |
| question_bank.sub_category_id | 题的域归属 | 用于校验；不替代 qk |
| foundation_graph_* | 投影 | P3 重建；不作为策展源 |

**重要兼容策略**：P1/P2 不修改 base 表。所有策展结果写入 qp_kg_* 覆盖层；运行时通过 v_qp_kg_* 有效视图读取。只有当 P3 验收通过、用户批准后，才讨论是否把覆盖层合并回 base。这样即使设计有误，也不会破坏现有快速练习。

---

## 5. 大纲对齐设计

### 5.1 三科结构：官方 vs 库内

| 科目 | 官方/教研口径 | 库内现状 | 差异与状态 |
|---|---|---|---|
| 公专 | 职业素养、基础知识、基本能力 | 职业素养、基础知识、**基本警务能力** | 命名偏差；建议显示名“基本能力（库内名：基本警务能力）”，DB 改名单独立项 |
| 行测 | 常识判断、言语理解与表达、数量关系、判断推理、资料分析；公安联考另含知觉速度与准确性（以当年大纲为准） | 上述 5 + 政治理论 + 知觉速度与准确性 + 科学推理，共 8 | 政治理论/科学推理需教研确认；未确认前标 extension/pending |
| 申论 | 归纳概括、综合分析、提出对策、应用文写作、议论文写作 | 完全一致 5 个 | 结构对齐；内部知识点仍需归位 |

> 置信度说明：公专三块与申论五类为高置信度；行测“政治理论/科学推理”与公安联考的关系为中低置信度，必须由教研按当年大纲确认，不能由本方案替教研下结论。

### 5.2 大纲对齐矩阵

位置：02-大纲/04-对齐矩阵.md（Dataview 视图）+ 编译产物 syllabus_matrix.json。

| 字段 | 说明 |
|---|---|
| syllabus_id | 大纲条目 ID |
| year | 年份 |
| subject | 科目 |
| module | 一级模块 |
| official_text | 原文（不改写） |
| source_url / source_file | 来源 |
| mapped_nodes | 映射到的节点（wikilink） |
| coverage | 0–100% |
| status | aligned / partial / extension / missing / retired |
| owner | 教研负责人 |
| verified_at | 核对日期 |

**状态定义**

- aligned：大纲条目有明确节点，节点也有该条目引用。
- partial：只覆盖部分要素，需补节点。
- extension：库内节点是大纲外的本地扩展（如可能的“科学推理”），必须有教研签字。
- missing：大纲有、库内无。
- retired：旧大纲条目已取消，节点退役但保留。

### 5.3 差异台账（当前已知）

| # | 差异 | 影响 | P2 动作 |
|---|---|---|---|
| S1 | 公专“基本警务能力” vs “基本能力” | 对外口径不一致 | 加别名；DB 改名需单独审批 |
| S2 | 行测“政治理论”“科学推理”来源不明 | 可能被质疑“不对标大纲” | 教研确认；未确认前标 extension/pending |
| S3 | 21 个 L2 无域 | 无法归属、统计漏算 | 逐个挂域或退役 |
| S4 | 358 个 L2 无子 | 知识点层过宽、考点缺失 | 三分诊：补 L4 / 降 L4 / 退役 |
| S5 | 仅 7 个 L4 | 考点层几乎为空 | P2 分批建 L4，不批量造 |
| S6 | 63 组同科目重名 | 链接歧义、合并风险 | ID 文件名 + 别名 + 合并评审 |
| S7 | 134 个“其他” | 容器污染 | 拆解/退役，禁止新增 |
| S8 | 664 题无 qk；758 题有域无点 | 题点覆盖不足 | 归位流水线 + 人工复核 |
| S9 | 3 个“待归类-*” | 公专三域各一个垃圾桶 | 拆解到具体 L2/L3 |
| S10 | 5 组跨科同名 | 可能误合并 | 保留各自节点；必要时加认知桥 |

### 5.4 年度大纲更新流程

1. 新增 syl_<year>_* 条目卡，原文照录，标注来源与抓取日期。
2. 编译器对比上一年：新增/删除/改写，产出 syllabus_diff.md。
3. 影响分析：每个变化列出受影响节点、题、先修路径。
4. 教研评审：aligned/partial/extension/missing 四选一。
5. 更新节点 syllabus_refs；缺节点的进收件箱。
6. 编译 apply；旧条目 retired，不删除。

---

## 6. Obsidian 的必要性、定位与边界

### 6.1 三态架构

~~~text
设计态（Obsidian）                  编译态（编译器）                 运行态（系统）
┌─────────────────────┐      ┌──────────────────────┐      ┌─────────────────────┐
│ 03-科目 / 04-域      │      │ scan → validate      │      │ SQLite SoT          │
│ 05-知识点 / 06-考点  │ ───> │ diff → manifest      │ ───> │ qp_kg_* 覆盖层       │
│ 07-关系 / 02-大纲    │      │ patch → graph plan   │      │ 图投影 (local)       │
│ 00-收件箱 / 12-评审  │ <─── │ report → rollback    │ <─── │ 运行数据/题点统计    │
└─────────────────────┘      └──────────────────────┘      └─────────────────────┘
       人评审、留证据               机器校验、可回滚                 快速练习读路径
~~~

### 6.2 为什么绝对有必要

1. **1000+ 节点的人工评审需要“可读的界面”**：数据库管理页只能看表格，无法同时看定义、关系、证据、大纲原文、反例。
2. **关系需要“写作空间”**：先修/并行/易混/跨科的判定是教研判断，不是表单勾选；Markdown + wikilink 是最低摩擦的策展介质。
3. **证据必须与结论在一起**：每条边旁边就是 rationale/evidence/评审记录，Dataview 可汇总；数据库里做不到“读完就能判断”。
4. **合作伙伴交接需要“可打开的说明书”**：目录、模板、铁律、看板、Canvas 就是交接物；只给 SQL 和 API 文档，合作方无法接手。
5. **大纲对齐需要“原文级追溯”**：大纲条目卡 + 节点引用，才能回答“这条到底覆盖了没有”。
6. **本地优先、可版本化**：Markdown + Git，评审 diff 可读；不依赖在线协作服务。

### 6.3 什么时候不需要 Obsidian

- 节点少于 50、关系少于 100，且只有 1 个维护者：Excel/数据库后台足够。
- 需要毫秒级多用户并发编辑：Obsidian 不是协作服务器；应使用 Git 分支 + 评审，或专门后台。
- 需要事务写入、权限控制、审计合规：这些必须由系统/数据库承担，不是 Obsidian。

### 6.4 人机边界（硬规则）

| 角色 | 可以做什么 | 不可以做什么 |
|---|---|---|
| AI 助手 | 读全库；在 00-收件箱 写提案；生成报告；跑 dry-run | 直接改 03–07 卡片；直接 apply；删除任何文件 |
| 教研专家 | 判定内容、写 rationale/evidence、签评审 | 改编译产物、改 manifest |
| 知识工程师 | 维护模板、跑编译、处理 schema 错误 | 替教研做内容判定 |
| 学科负责人 | 批准 hard 先修、跨科桥、合并/退役 | 跳过证据门槛 |
| 系统管理员 | 备份、apply、回滚、监控 | 手工改 qp_kg_* 表绕过编译器 |

### 6.5 Neo4j 决策

**结论：当前不引入 Neo4j。**

理由：

- 实测默认 GRAPH_BACKEND=local，现有 SQLite GraphStore 已能承载 3823 节点/4354 边；快速练习图查询深度上限 5，规模小。
- Neo4j 会带来额外服务、备份、权限、监控、双写一致性成本；当前没有必须用 Cypher 的算法需求。
- 未来触发条件（任一满足再评估）：
  1. 图节点 >5 万或边 >20 万；
  2. 需要实时多跳路径、社区发现、中心性等图算法，且 SQLite 递归查询无法在 SLO 内完成；
  3. 需要多团队共享图服务与细粒度权限；
  4. 产品明确要求图可视化交互查询。
- 触发后单独立 ADR，不在本方案中预埋迁移。

---

## 7. Obsidian 知识库完整框架

### 7.1 落位与边界

- 根 vault 已是 **D:/Obsidian仓库**（根目录有 .obsidian）。因此本库是**根 vault 下的子库**，不新建嵌套 .obsidian，不把子库变成第二个 vault。
- 目标目录：**D:/Obsidian仓库/快速练习知识分层**。当前为空目录，P1 直接在此创建结构。
- 子库内所有 Dataview 查询必须写**全路径前缀**，例如 FROM "快速练习知识分层/05-知识点"，否则会扫描整个根 vault，污染结果并拖慢性能。
- 子库不存放任何密钥、连接串、真实学生数据；只放分类、关系、证据、大纲原文与统计。
- 子库可整体纳入 Git（建议单独仓库或在主仓 docs 外做镜像）；.obsidian/workspace.json 不入库。

### 7.2 目录结构（14 个目录 + 首页）

~~~text
快速练习知识分层/
├── 首页.md
├── 00-收件箱/
│   ├── 待评审提案/
│   ├── 已采纳/
│   └── 已驳回/
├── 01-入口/
│   ├── 库内铁律.md
│   ├── 角色与权限.md
│   ├── 插件与可视化配置.md
│   ├── 术语与命名手册.md
│   ├── 关系判定手册.md
│   └── 合作伙伴上手.md
├── 02-大纲/
│   ├── 00-大纲总览.md
│   ├── 01-公专大纲.md
│   ├── 02-行测大纲.md
│   ├── 03-申论大纲.md
│   ├── 04-对齐矩阵.md
│   ├── 05-差异台账.md
│   └── 条目/
│       ├── syl_2025_公专_001.md
│       └── ...
├── 03-科目/
│   ├── sub_1_行测.md
│   ├── sub_2_申论.md
│   └── sub_3_公专.md
├── 04-知识域/
│   ├── dom_01_政治理论.md
│   └── ...（16 个）
├── 05-知识点/
│   ├── kp_000101_行政处罚概述.md
│   └── ...（基线约 495 张，逐步治理）
├── 06-考点/
│   ├── ep_000001_行政处罚种类辨析.md
│   └── ...（基线 7 张，P2 扩展）
├── 07-关系/
│   ├── 00-关系总览.md
│   ├── 01-先修边.md
│   ├── 02-并行边.md
│   ├── 03-易混边.md
│   ├── 04-跨科边.md
│   ├── 05-结构边说明.md
│   ├── 06-边台账.md
│   └── 07-关系候选池.md
├── 08-视图/
│   ├── 00-总览看板.md
│   ├── 01-分层健康看板.md
│   ├── 02-先修链路.md
│   ├── 03-并行场景.md
│   ├── 04-跨科认知桥.md
│   ├── 05-大纲覆盖.md
│   ├── 06-题点覆盖.md
│   ├── 07-变更队列.md
│   ├── 08-重名与容器.md
│   ├── 09-孤立节点.md
│   └── 10-指标趋势.md
├── 09-编译产出/
│   ├── manifest.json
│   ├── edges.jsonl
│   ├── nodes.jsonl
│   ├── validation_report.md
│   ├── diff_report.md
│   ├── sql_patch.sql
│   ├── graph_plan.json
│   ├── syllabus_matrix.json
│   └── health_report.json
├── 10-模板/
│   ├── 模板_科目.md
│   ├── 模板_知识域.md
│   ├── 模板_知识点.md
│   ├── 模板_考点.md
│   ├── 模板_大纲条目.md
│   ├── 模板_收件箱提案.md
│   ├── 模板_评审记录.md
│   └── 模板_变更日志.md
├── 11-变更日志/
│   ├── 2026-11.md
│   └── changes.jsonl
├── 12-评审/
│   ├── 评审队列.md
│   ├── 评审记录/
│   └── 签字台账.md
└── 99-归档/
    ├── 退役节点/
    ├── 历史版本/
    └── 导入原始件/
~~~

### 7.3 各目录职责与禁止事项

| 目录 | 职责 | 谁写 | 禁止 |
|---|---|---|---|
| 首页.md | 导航、状态灯、本周待办、快速入口 | 知识工程师 | 写成长篇报告 |
| 00-收件箱 | 所有变更提案的唯一入口 | AI/教研/合作方 | 直接改正式卡片 |
| 01-入口 | 铁律、角色、术语、关系手册、上手 | 知识工程师 | 写临时结论 |
| 02-大纲 | 大纲原文、对齐矩阵、差异台账 | 教研 | 改写原文 |
| 03-科目 | 3 张科目卡 | 知识工程师 | 增删科目（需审批） |
| 04-知识域 | 16 张域卡 | 教研 | 擅自新增域 |
| 05-知识点 | 知识点卡（核心） | 教研 | 无证据写先修 |
| 06-考点 | 考点卡（核心） | 教研 | 为凑层造空考点 |
| 07-关系 | 语义边唯一策展源 | 教研+知识工程师 | 手改结构边 |
| 08-视图 | Dataview 看板，只读 | 知识工程师 | 把查询结果当事实源 |
| 09-编译产出 | 机器产物，只读 | 编译器 | 手改任何文件 |
| 10-模板 | 卡片模板 | 知识工程师 | 在模板里放真实数据 |
| 11-变更日志 | 人读月志 + 机读 jsonl | 编译器+知识工程师 | 删除历史 |
| 12-评审 | 队列、记录、签字 | 学科负责人 | 代签 |
| 99-归档 | 退役、历史、原始件 | 知识工程师 | 删除 |

### 7.4 首页设计

首页只放六块，保持一屏可读：

1. **状态灯**：节点数、边数、断链、先修环、待评审、题点覆盖率、大纲覆盖率；红/黄/绿。
2. **本周待办**：Dataview 查 00-收件箱 与 12-评审 中 status=pending 且 due 在 7 天内。
3. **四条主入口**：知识地图、关系治理、大纲对齐、健康看板。
4. **角色入口**：教研/知识工程师/学科负责人/合作方/管理员，各自只看自己需要的。
5. **最近变更**：11-变更日志 最近 10 条。
6. **铁律提醒**：AI 只写收件箱、不删除、不手改编译产出、数字必须实测。

---

## 8. 卡片规范与模板

### 8.1 通用 frontmatter 约定

- 所有卡片必须是 UTF-8、LF 换行、YAML frontmatter 在文件第一行。
- 字段名用 snake_case；枚举值用小写英文；日期用 YYYY-MM-DD。
- 所有 wikilink 指向**文件名**（不带路径也可，但同名必须带 ID，故实际不会歧义）。
- 不在 frontmatter 写长段落；rationale/evidence 放正文或关系文件。
- 每张卡必须有 node_id、node_type、title、status、review、owner、updated。
- status：draft / active / deprecated。
- review：draft / pending / approved / rejected。
- 只有 review=approved 的卡片参与编译；draft 卡可以存在，但不进运行图。

### 8.2 科目卡（03-科目）

~~~yaml
---
node_id: "sub:3"
node_type: Subject
title: "公安专业科目"
short_name: "公专"
code: "gongan"
status: active
review: approved
owner: "学科负责人-公专"
updated: 2026-11-05
syllabus_refs:
  - "[[syl_2025_公专_000]]"
tags:
  - 快速练习/科目
---
~~~

正文：考试定位、题型结构、分值、时长、大纲版本、与其他两科的关系。不超过 80 行。

### 8.3 知识域卡（04-知识域）

~~~yaml
---
node_id: "dom:14"
node_type: Domain
title: "基础知识"
subject: "公专"
subject_id: "sub:3"
syllabus_group: "基础知识"
order: 20
status: active
review: approved
owner: "教研-公专组"
updated: 2026-11-05
syllabus_refs:
  - "[[syl_2025_公专_010]]"
tags:
  - 快速练习/知识域
---
~~~

正文：域的范围、包含的知识点类型、不包含什么、常见误归类、与其他域的关系。不超过 120 行。

### 8.4 知识点卡（05-知识点，核心）

~~~yaml
---
node_id: "kp:000123"
node_type: KnowledgePoint
title: "行政处罚的种类与设定"
subject: "公专"
subject_id: "sub:3"
domain: "基础知识"
domain_id: "dom:14"
parent: "[[dom_14_基础知识]]"
knowledge_kind: concept
difficulty: 0.6
exam_weight: 0.8
coverage_status: has_exam_points
status: active
review: approved
owner: "教研-公专组"
updated: 2026-11-05
syllabus_refs:
  - "[[syl_2025_公专_012]]"
prerequisites:
  - "[[kp_000101_行政处罚概述]]"
parallel_with: []
contrasts_with:
  - "[[kp_000124_行政许可]]"
cognitive_shared_with: []
scenario_profile: null
aliases:
  - "行政处罚种类"
tags:
  - 快速练习/知识点
  - 快速练习/公专/基础知识
---
~~~

正文固定六段（无内容写“暂无”，不删标题）：

1. **一句话定义**：不超过 60 字。
2. **构成/流程**：3–7 条。
3. **命题形态**：这个点通常怎么考（至少 2 种，或写“仅教学”）。
4. **易错点**：至少 1 条，尽量给反例。
5. **关系理由**：先修/并行/易混/跨科各自为什么；没有就写“无”。
6. **大纲依据**：引用条目 + 原文摘录 + 年份；扩展内容写“本地扩展”。

### 8.5 考点卡（06-考点，核心）

~~~yaml
---
node_id: "ep:000001"
node_type: ExamPoint
title: "行政处罚种类的辨析"
subject: "公专"
subject_id: "sub:3"
domain: "基础知识"
domain_id: "dom:14"
parent_kp: "[[kp_000123_行政处罚的种类与设定]]"
exam_form: "概念辨析"
question_types:
  - 单选
  - 多选
difficulty: 0.65
frequency: high
last_exam_years:
  - 2024
  - 2023
coverage_status: has_questions
status: active
review: approved
owner: "教研-公专组"
updated: 2026-11-05
syllabus_refs:
  - "[[syl_2025_公专_012]]"
aliases: []
tags:
  - 快速练习/考点
---
~~~

正文固定五段：

1. **命题决策点**：考生要在哪一步做判断。
2. **题干模板**：可复用的题干骨架（不含具体数字）。
3. **正确项逻辑**：为什么对。
4. **干扰项逻辑**：2–4 个常见错误路径。
5. **真题/样题索引**：题目 ID 或来源；没有就写“预测考点”。

exam_form 枚举：概念辨析、法条适用、程序排序、计算、案例分析、材料概括、公文写作、论证评价、图形推理、资料分析、其他（其他需说明）。

### 8.6 大纲条目卡（02-大纲/条目）

~~~yaml
---
syllabus_id: "syl:2025:公专:012"
node_type: SyllabusItem
year: 2025
subject: "公专"
module: "基础知识"
official_text: "掌握行政处罚的种类与设定权限。"
source: "2025 年公安联考公安专业科目考试大纲"
source_url: ""
retrieved_at: 2026-11-05
status: active
mapped_nodes:
  - "[[kp_000123_行政处罚的种类与设定]]"
coverage: 100
owner: "教研-公专组"
updated: 2026-11-05
tags:
  - 快速练习/大纲
---
~~~

正文：原文完整段落、上下文、与上一年差异、映射说明。原文不得改写；如需解释，另起“解读”小节。

### 8.7 语义边策展文件（07-关系，唯一策展源）

**关键裁定**：语义边（先修/并行/易混/跨科）的唯一策展源是 07-关系 下的四个文件；卡片 frontmatter 里的同名列表是**只读镜像**，由编译器渲染，禁止手改。这样避免“卡片和台账两套真相”。

01-先修边.md：

~~~yaml
---
relation: PREREQUISITE_OF
version: 1
updated: 2026-11-05
edges:
  - src: "kp:000101"
    dst: "kp:000123"
    strength: hard
    rationale: "不理解行政处罚的概念与原则，无法判断种类与设定权限。"
    evidence: "2024 年真题第 12 题；大纲条目 syl:2025:公专:012"
    status: approved
    owner: "教研-公专组"
    updated: 2026-11-05
  - src: "kp:000123"
    dst: "ep:000001"
    strength: soft
    rationale: "掌握种类后才能做辨析题。"
    evidence: "教学顺序；非考试硬依赖"
    status: draft
    owner: "教研-公专组"
    updated: 2026-11-05
---
~~~

正文：本关系的判定标准、最近变更、待讨论项。文件不超过 800 行；超过则按科目拆分为 01-先修边-公专.md 等，并在总览中登记。

02-并行边.md、03-易混边.md、04-跨科边.md 同构，字段差异：

| 文件 | relation | 必填额外字段 |
|---|---|---|
| 01-先修边 | PREREQUISITE_OF | strength: hard/soft |
| 02-并行边 | PARALLEL_WITH | parallel_kind: scenario_cooccur/skill_shared；scenario（若场景） |
| 03-易混边 | CONTRAST_WITH | difference: 差异点；counter_example: 反例 |
| 04-跨科边 | COGNITIVE_SHARED_WITH | capability: 共享能力；transfer: 迁移机制；reviewers: 两科负责人 |

**去重与对称**：

- 无向边只写一次，编译器按 node_id 排序规范化；src > dst 时自动交换并记录。
- 同一对节点同一关系重复出现 → 编译错误。
- 同一对节点不同关系允许（例如既并行又易混），但要在正文说明为什么两种关系同时成立。

### 8.8 结构边（CONTAINS / INSTANCE_OF）

- CONTAINS 由卡片 parent 字段派生：L2 的 parent 指向科目卡，L3 的 parent 指向域卡。
- INSTANCE_OF 由考点卡 parent_kp 派生：每个考点一个主知识点。
- 结构边**不进入 07-关系 台账**，避免重复；05-结构边说明.md 只解释规则与例外。
- 例外（跨域挂载）必须走收件箱，由学科负责人批准，并在卡片正文写“跨域例外理由”。

### 8.9 收件箱提案卡（00-收件箱）

~~~yaml
---
proposal_id: "prop:2026-11-05-001"
proposal_type: new_node / edit_node / new_edge / edit_edge / retire_node / merge_node / split_node
status: pending
priority: high
proposer: "AI 助手"
owner: "教研-公专组"
created: 2026-11-05
due: 2026-11-12
affected_nodes:
  - "[[kp_000123_行政处罚的种类与设定]]"
evidence:
  - "2024 年真题第 12 题"
  - "大纲 syl:2025:公专:012"
risk: medium
rollback: "删除本提案对应 patch 即可；不涉及 base 表"
tags:
  - 快速练习/收件箱
---
~~~

正文固定五段（沿用 AI舆情库范式并加一段）：

1. **现状**：现在是什么，引用卡片/数据。
2. **建议**：具体改什么，给出前后对比。
3. **证据**：大纲/真题/教材/评审意见；禁止“我觉得”。
4. **影响**：受影响节点、题、路径、统计；是否改变 hard 先修。
5. **回滚**：如何撤销；是否只动覆盖层。

### 8.10 评审记录与签字台账

- 每条 hard 先修、每条跨科桥、每次合并/拆分/退役，必须有评审记录。
- 评审记录卡：proposal_id、评审人、结论（approve/reject/revise）、理由、日期、签字。
- 签字台账：汇总所有硬变更，供合作方与审计查看；不允许代签、不允许空签字。
- 评审结论只写三种：approve / reject / revise；不写“再看看”这种不可执行状态。

### 8.11 变更日志

- 人读：11-变更日志/2026-11.md，按日期倒序，每条含变更 ID、类型、节点、提案、评审人、结果。
- 机读：11-变更日志/changes.jsonl，每行一个 JSON，字段与 manifest 对齐，供编译器与看板读取。
- 两者由编译器同时生成；人手写月志时只写摘要，不手写 jsonl。
- 历史永不删除；纠错用新记录 + 指向旧记录。

### 8.12 生成块（只读区）

卡片正文可包含生成块，用 HTML 注释包住：

~~~text
<!-- AUTO:CHILDREN:BEGIN -->
（由编译器生成：子考点列表、题量、最近考查年份）
<!-- AUTO:CHILDREN:END -->

<!-- AUTO:BACKLINKS:BEGIN -->
（由编译器生成：谁把我当先修、谁与我并行、谁与我易混）
<!-- AUTO:BACKLINKS:END -->

<!-- AUTO:HEALTH:BEGIN -->
（由编译器生成：本节点健康项）
<!-- AUTO:HEALTH:END -->
~~~

规则：

- 生成块内禁止手写；编译器每次覆盖。
- 生成块外可自由写正文。
- 生成块缺失不报错；存在但格式坏 → 编译警告。
- 生成块内容不参与事实源，只用于阅读。

### 8.13 模板全文

模板放在 10-模板，新建卡片时复制。模板本身 review=template，不参与编译。模板字段与 8.2–8.9 一致；模板正文保留六段/五段标题和“暂无”占位，避免新卡缺段。

---

## 9. 治理流程：收件箱 → 评审 → 编译 → 运行

### 9.1 端到端流程

~~~text
发现缺口/错误
   ↓
AI 或人写 00-收件箱 提案（五段式）
   ↓
知识工程师初筛：格式、重复、影响面
   ↓
教研评审：内容正确性、证据充分性
   ↓
学科负责人签字：hard 先修/跨科/合并/退役
   ↓
知识工程师合并到 03–07 正式卡片与关系文件
   ↓
跑编译 dry-run：scan → validate → diff → report
   ↓
用户/管理员看报告，批准 apply
   ↓
备份 → 事务写入 qp_kg_* → 更新 manifest → 记录变更
   ↓
跑 health 与回归；失败则 rollback
~~~

### 9.2 角色与 RACI

| 活动 | 教研专家 | 知识工程师 | 学科负责人 | 系统管理员 | AI |
|---|---|---|---|---|---|
| 写提案 | C | C | I | I | R |
| 内容判定 | R | C | A | I | C |
| 格式/模板 | C | R | I | I | C |
| hard 先修批准 | C | I | R/A | I | I |
| 跨科桥批准 | C | I | R/A | I | I |
| 合并/退役批准 | C | C | R/A | I | I |
| 编译 dry-run | I | R | I | C | C |
| apply | I | C | A | R | I |
| 回滚 | I | C | A | R | I |
| 健康报告 | C | R | I | C | C |

R=执行，A=最终负责，C=被咨询，I=被通知。

### 9.3 评审 SLA 与优先级

- P0（阻断）：断链、先修环、层级违规、编译失败 → 24 小时内处理。
- P1（高）：hard 先修变更、跨科桥、合并/退役、题点覆盖大幅下降 → 3 个工作日。
- P2（中）：新增 L4、别名、难度调整 → 7 个工作日。
- P3（低）：文案、标签、看板优化 → 14 个工作日。
- 超期提案进“逾期”视图，但不自动通过；宁可积压，不可放水。

### 9.4 冲突解决

1. **同一对节点被两人判成不同关系**：先看是否可共存（并行+易混可共存）；不能共存则由学科负责人裁定，记录理由。
2. **先修方向冲突**：用“不学 A 能否学 B”反事实测试；仍不能定则降为 soft 或删除。
3. **跨科归属冲突**：节点归主科，另一科用 COGNITIVE_SHARED_WITH；不复制节点。
4. **大纲 vs 教材冲突**：以当年官方大纲为准；教材差异写入“解读”，不改原文。
5. **数据 vs 教研冲突**：数据用于提示，不代替判定；冲突进差异台账。

### 9.5 编译流水线（详细）

| 步骤 | 输入 | 输出 | 失败处理 |
|---|---|---|---|
| scan | 03–07、02 | 内存模型 + 解析错误 | 列出文件/行/字段，停止 |
| normalize | 内存模型 | ID 规范、对称边、别名索引 | 自动修复并记录 |
| validate | 规范化模型 | 错误/警告清单 | 有 error 停止；warning 可继续 |
| diff | 上次 manifest | 新增/修改/删除/移动 | 生成 diff 报告 |
| render | 模型 | 卡片镜像、生成块、看板数据 | 只写生成块 |
| compile | 模型 | nodes.jsonl、edges.jsonl、sql_patch.sql、graph_plan.json | 失败不写库 |
| dry-run | patch/plan | 影响行数、抽样、回滚点 | 默认模式 |
| apply | patch/plan | qp_kg_* 更新、manifest、changes | 事务 + 备份 |
| health | 运行态 | health_report.json | 失败告警，不自动回滚 |
| rollback | 备份 + manifest | 恢复 | 需管理员确认 |

### 9.6 CLI 约定

统一入口：python scripts/qp_kg/qp_kg.py <command>。

| 命令 | 作用 | 默认 |
|---|---|---|
| scan | 只解析，不校验 | 只读 |
| validate | 跑不变量与健康规则 | 只读 |
| diff | 与 manifest 比对 | 只读 |
| render | 生成卡片镜像与生成块 | 写 09 与生成块 |
| compile | 生成 patch/plan | 只读 |
| apply | 备份后写库 | 需 --yes |
| rollback | 回滚到指定 manifest | 需 --yes |
| health | 生成健康报告 | 只读 |
| export | 导出 nodes/edges/matrix | 只写 09 |

参数：--vault、--db、--manifest、--out、--subject、--dry-run、--yes、--verbose。所有命令支持 --json 输出，便于 CI。

### 9.7 apply 的安全约束

1. 只写 qp_kg_* 与 foundation_graph_* 投影；不写 base 表。
2. apply 前必须 sqlite3.backup() 到 backups/qp_kg/<timestamp>.db（R10）。
3. 单事务；任何一行失败整体回滚。
4. 写前校验 manifest 版本；并发修改 → 拒绝，要求重新 diff。
5. 写后校验行数、校验和、抽样；不一致 → 自动回滚并告警。
6. 记录操作者、时间、提案 ID、manifest 哈希到 changes.jsonl。
7. 禁止 AI 直接 apply；只能生成 dry-run 报告。

## 10. 可视化设计

### 10.1 四层可视化分工

| 层 | 工具 | 用途 | 是否验收依据 |
|---|---|---|---|
| 总览/统计 | Dataview 看板 | 数量、覆盖率、健康灯、队列 | 是（数字来自编译产物） |
| 结构/链路 | Canvas 策展图 | 给教研/合作方讲解、评审、培训 | 否（只做沟通） |
| 关系/子图 | Mermaid（由 edges.jsonl 生成） | 按关系类型看局部拓扑、贴文档 | 是（生成物可追溯） |
| 探索 | Obsidian 原生关系图谱 | 个人探索、发现意外连接 | 否（噪声大，不做验收） |

**硬规则**：Canvas 上的一条线不等于一条边；只有 07-关系 里的 edge 才进编译。Canvas 可以画“示意线”，但必须标“示意”，且每季度清理一次。

### 10.2 Dataview 看板清单

| 文件 | 回答的问题 | 主要数据源 | 刷新 |
|---|---|---|---|
| 00-总览看板 | 现在多大、健康吗、本周做什么 | manifest、health、收件箱 | 每次编译 |
| 01-分层健康看板 | H1–H13 哪些红 | health_report.json | 每次编译 |
| 02-先修链路 | 哪些 hard 先修、最长链、根/叶 | 01-先修边 | 每日 |
| 03-并行场景 | 哪些点在同一执法场景 | 02-并行边 + scenario_profile | 每日 |
| 04-跨科认知桥 | 30 条桥是否超预算、谁批准 | 04-跨科边 | 每周 |
| 05-大纲覆盖 | 哪些大纲条目 missing/partial | 大纲条目 + 对齐矩阵 | 每次大纲更新 |
| 06-题点覆盖 | 哪些 L4 无题、哪些题无点 | qp_kg + question 统计 | 每日 |
| 07-变更队列 | 哪些提案逾期、卡在谁 | 00-收件箱 + 12-评审 | 每日 |
| 08-重名与容器 | 哪些重名、哪些“其他” | 05/06 卡片 | 每周 |
| 09-孤立节点 | 哪些点没有任何语义边/题 | edges + 题统计 | 每周 |
| 10-指标趋势 | 覆盖率/孤立率/边密度在变好还是变坏 | 月度快照 | 每月 |

### 10.3 Dataview 查询样例

以下查询均写全路径前缀；实际 DQL 使用双引号，不使用反引号。示例中的字段与第 8 章 frontmatter 一致。

**待评审提案（按优先级与截止日）**

~~~dataview
TABLE proposal_type AS 类型, priority AS 优先级, owner AS 负责人, due AS 截止
FROM "快速练习知识分层/00-收件箱"
WHERE status = "pending"
SORT priority ASC, due ASC
~~~

**无考点的知识点（教学型候选）**

~~~dataview
TABLE domain AS 知识域, knowledge_kind AS 类型, review AS 评审, updated AS 更新
FROM "快速练习知识分层/05-知识点"
WHERE coverage_status = "teaching_only" AND status = "active"
SORT domain ASC, title ASC
~~~

**先修边中 hard 且未批准（不该存在，发现即阻断）**

~~~dataview
TABLE WITHOUT ID file.link AS 文件
FROM "快速练习知识分层/07-关系"
WHERE relation = "PREREQUISITE_OF"
~~~

> 说明：边明细在 YAML 的 edges 数组里，Dataview 对数组内对象的表格化能力有限；上例用于发现文件，真正的边明细由 09-编译产出/edges.jsonl 与 06-边台账 展示。看板不承担编译器职责。

**跨科桥预算**

~~~dataview
TABLE length(edges) AS 边数
FROM "快速练习知识分层/07-关系"
WHERE relation = "COGNITIVE_SHARED_WITH"
~~~

**最近变更**

~~~dataview
TABLE change_type AS 类型, target AS 对象, actor AS 操作者, created AS 时间
FROM "快速练习知识分层/11-变更日志"
SORT created DESC
LIMIT 20
~~~

### 10.4 Canvas 策展图（4 张）

| Canvas | 内容 | 节点数上限 | 维护人 | 更新时机 |
|---|---|---:|---|---|
| 00-全景.canvas | 3 科目 + 16 域 + 每域 1–3 个代表点；不铺全量 | 60 | 知识工程师 | 每月 |
| 01-公专执法链路.canvas | 接处警→盘查→继续盘问→强制措施→处罚→救济；法条挂载 | 40 | 公专教研 | 每季度 |
| 02-三科认知共享.canvas | 5–10 条跨科桥及证据 | 30 | 两科负责人 | 每季度 |
| 03-治理闭环.canvas | 收件箱→评审→编译→apply→health→回滚 | 20 | 知识工程师 | 流程变更时 |

**Canvas 规范**

- 节点文本必须写全路径：快速练习知识分层/05-知识点/kp_000123_行政处罚的种类与设定.md，不能只写“行政处罚”。
- 连线标签写关系类型 + 状态，例如“PREREQUISITE_OF / approved / hard”。
- 颜色图例：红实线=先修，蓝虚线=并行，紫点线=易混，绿粗线=跨科，灰细线=包含，橙虚线=实例化。
- Canvas 里不放长段落；长解释链接到卡片。
- 每张 Canvas 第一屏放“本图不是事实源”的提示。

### 10.5 Mermaid 生成

编译器从 edges.jsonl 生成：

- 09-编译产出/mermaid/先修链.md
- 09-编译产出/mermaid/并行场景.md
- 09-编译产出/mermaid/跨科桥.md

规则：

- 只画 status=approved 的边；draft 边用灰色虚线并标 draft。
- 按 domain 分子图；节点标签用标题，不用 ID。
- 单图节点 >80 时按科目/域拆分，避免不可读。
- Mermaid 是生成物，禁止手改；需要改关系去改 07-关系。

### 10.6 原生关系图谱设置

- 颜色组：按 subject 分三色；按 node_type 分形状/大小（科目大、域中、点小）。
- 过滤：默认隐藏 deprecated、draft；只看当前科目。
- 深度：本地图默认 2 跳，避免毛球。
- 用途：个人探索与发现候选；发现的候选必须回填收件箱，不能直接当结论。
- 验收：不以原生图谱截图作为“关系完整”的证据。

### 10.7 插件与配置

最小插件集：

| 插件 | 必需 | 用途 | 风险控制 |
|---|---|---|---|
| Dataview | 是 | 看板 | 查询必须全路径前缀；限制结果行数 |
| Templater | 是 | 模板变量、日期、ID | 模板不执行外部命令 |
| Canvas | 核心 | 策展图 | 只做沟通 |
| Excalidraw | 可选 | 手绘图 | 不作为事实源 |
| ChartsView | 可选 | 趋势图 | 图表必须标“真实/示例” |
| Local REST API | 可选 | 只写收件箱 | 只监听 127.0.0.1；Token 不入库；禁止批量写正式卡 |

配置原则：

- 关闭“自动更新内部链接”之外的自动改写；避免批量重命名破坏 wikilink。
- 文件恢复：开启核心“文件恢复”，快照保留 30 天。
- 禁止安装会全库改写的插件；新插件须在 01-入口/插件与可视化配置.md 登记。
- .obsidian/workspace.json、cache 不入 Git；app.json、graph.json、插件配置入 Git（不含 Token）。

### 10.8 图表与数字纪律

- 任何看板数字必须标“数据时间 + 来源文件”；禁止手填。
- 示例数据必须显式标“示例”，不能与真实数据混排。
- 图表只展示编译产物中的数字；需要新指标先加编译器，再加图。
- 不用“看起来很多”描述关系密度；用平均度、孤立率、连通分量。

---

## 11. 自生长机制（I1–I12）

“自生长”不是 AI 自动改库，而是**有入口、有校验、有评审、有回滚的持续演化**。以下 12 条机制共同构成闭环。

| # | 机制 | 触发 | 机器做什么 | 人做什么 | 产出 |
|---|---|---|---|---|---|
| I1 | 缺口提案 | 题点覆盖下降、孤立节点、断链 | 生成提案卡到 00-收件箱 | 初筛、定优先级 | 提案 |
| I2 | 编译即校验 | 每次合并/定时 | 跑 H1–H13，阻断 error | 处理红项 | 健康报告 |
| I3 | 大纲年度 diff | 新大纲发布 | 对比条目，列出新增/删除/改写 | 判定 aligned/extension/missing | 差异台账 |
| I4 | 题→点反哺 | 新题入库/错题统计 | 找无 L4 的题、无题的 L4 | 归位/建点/退役 | 覆盖报告 |
| I5 | 难度与权重校准 | 每月 | 汇总正确率、耗时（只读） | 决定是否调 difficulty/exam_weight | 校准建议 |
| I6 | 关系候选推荐 | 每周 | 共现/同错/同材 pattern 推荐 | 逐条判定，不批量采纳 | 候选池 |
| I7 | 重名/别名治理 | 每周 | 列重名、疑似同义 | 合并/保留/加别名 | 治理清单 |
| I8 | 退役与继任 | 大纲删除/合并 | 标 deprecated + successor | 批准退役 | 退役记录 |
| I9 | 版本快照 | 每次 apply | manifest + 备份 + changes | 抽查 | 可回滚版本 |
| I10 | 合作方扩展 | 新科目/新域 | 模板/校验/编译自动适配 | 审批扩展 | 扩展包 |
| I11 | 指标趋势 | 每月 | 生成趋势快照 | 复盘 | 月报 |
| I12 | 知识债台账 | 持续 | 汇总所有红/黄项与逾期 | 排期偿还 | 债务清单 |

### 11.1 I1 缺口提案的生成规则

- 题无点：question_bank 可见题没有 approved 的 ASSESSES → 提案“归位或新建 L4”。
- 点无题：approved L4 题量为 0 且超过 90 天 → 提案“补题/降级/退役”。
- 点无父/无域：结构不完整 → P0 提案。
- 边无证据：approved 边缺 rationale/evidence → P0 提案。
- 大纲 missing：条目无映射 → P1 提案。
- 重名/容器：命中命名规则 → P2 提案。
- 跨科候选：两科同错率/同材料模式 → P3 候选，不自动建边。

### 11.2 I2 编译即校验的强制点

- 本地编辑时：Templater 保存后不自动编译；由知识工程师手动跑 validate。
- 合并到正式卡后： pre-commit 钩子跑 scan + validate（只读），失败禁止提交。
- 定时任务：每日 02:00 跑 health（只读），结果写 09，不写库。
- apply 前：必须 validate 全绿 + diff 已审 + 备份成功。

### 11.3 I3 大纲年度 diff 的产物

- syllabus_diff.md：新增/删除/改写三张表，每条带旧文/新文/影响节点。
- impact.json：受影响节点、题、先修路径、覆盖率变化。
- 评审包：每条变化一个勾选项，教研签字后才合并。
- 历史：旧条目 retired，不删除；新条目新 ID。

### 11.4 I4 题点反哺的边界

- 只读统计；不自动改题的知识点关系。
- 归位建议必须给证据（题干关键词、解析、教材页码）。
- 批量归位 >50 题必须分批，每批抽样 10% 人工复核。
- 题点关系仍以 question_knowledge 为 SoT；qp_kg 只做“应该挂哪里”的建议。

### 11.5 I5 难度校准的边界

- 数据来源：答题正确率、平均耗时、区分度；只读。
- 只生成建议，不自动写 difficulty/exam_weight。
- 样本 <30 的题不参与校准；避免小样本噪声。
- 校准记录进 changes.jsonl，可追溯。

### 11.6 I6 关系候选推荐的边界

- 候选来源：同题共现、同错率、同材料、同法条、同场景。
- 只进 07-关系/07-关系候选池.md，status=candidate。
- 人工逐条判定；禁止“一键全部采纳”。
- 每条候选必须写“为什么可能是关系”和“反例风险”。

### 11.7 I7 重名与别名治理

- 重名不等于重复：先看定义、题、父节点。
- 真重复：合并，保留主 ID，旧 ID 标 merged_into。
- 假重复：加 aliases，文件名加 ID 区分。
- 跨科同名：不合并，加 COGNITIVE_SHARED_WITH 或仅保留同名不同 ID。
- 合并必须评审 + 可回滚；禁止脚本直接删。

### 11.8 I8 退役与继任

- 退役条件：大纲删除、内容被合并、长期无题且无教学价值、重复。
- 退役动作：status=deprecated，写 deprecated_reason、successor、retired_at；不删除文件。
- 边处理：指向退役节点的边保留但标 deprecated_target；新边禁止指向退役节点。
- 运行图：默认排除 deprecated；需要历史查询时 include_deprecated=true。

### 11.9 I9 版本快照

- 每次 apply 生成 manifest 版本号（日期+序号，如 2026-11-05.1）。
- 备份文件、manifest、changes 三者绑定；回滚按版本号。
- 保留最近 30 个版本 + 每月 1 个长期版本；不清理唯一备份（R8 精神）。
- 回滚演练每季度一次，确保真的能回。

### 11.10 I10 合作方扩展

- 新科目：复制科目/域/点/考点模板，跑 scan/validate；不改代码。
- 新关系类型：不允许合作方自行加；必须走 ADR + 编译器升级。
- 新看板：可自行加 Dataview，但必须全路径前缀、只读。
- 新插件：登记后使用；不得引入全库改写类插件。
- 扩展包：新增目录 + 模板 + 校验规则 + 回归样例，放在 99-归档/导入原始件 或独立分支。

### 11.11 I11 指标趋势

- 每月 1 日生成快照：节点数、边数、覆盖率、孤立率、平均度、先修 hard 占比、跨科桥数。
- 趋势图只展示 12 个月；异常波动（>20%）必须写解释。
- 指标定义变化时，旧快照保留，新快照用新定义并标注版本。

### 11.12 I12 知识债台账

- 所有红/黄项、逾期提案、未签字硬变更、缺证据边，统一进债务台账。
- 每条债有 owner、due、impact、偿还计划；不允许“无主债”。
- 每月复盘一次；债务不下降则暂停新增功能，先还债。

---

## 12. 编译器与系统接入

### 12.1 目标链路

~~~text
Obsidian 卡片/关系
   ↓ scan/parse
内存模型（nodes/edges/syllabus）
   ↓ validate（G1–G10 + H1–H13）
规范化模型 + 错误清单
   ↓ diff/render/compile
manifest + nodes.jsonl + edges.jsonl + sql_patch.sql + graph_plan.json
   ↓ dry-run（默认）
影响报告（行数、抽样、回滚点）
   ↓ apply（需批准）
SQLite qp_kg_* 覆盖层 + foundation_graph_* 投影
   ↓ 有效视图
快速练习 API / 图查询 / 看板
~~~

### 12.2 覆盖层表设计

所有表加前缀 qp_kg_，与业务表隔离；P1/P2 不修改 base 表。

**qp_kg_node**

| 字段 | 类型 | 说明 |
|---|---|---|
| node_id | TEXT PK | kp:/ep:/dom:/sub: |
| node_type | TEXT | Subject/Domain/KnowledgePoint/ExamPoint |
| title | TEXT | 标题 |
| subject_id | TEXT | sub:1/2/3 |
| domain_id | TEXT | dom:xx，L3 必填 |
| parent_id | TEXT | 结构父 |
| knowledge_kind | TEXT | concept/procedure/scenario/principle/skill |
| exam_form | TEXT | 考点命题形态 |
| difficulty | REAL | 0–1 |
| exam_weight | REAL | 0–1 |
| coverage_status | TEXT | has_exam_points/teaching_only/has_questions/missing |
| status | TEXT | active/deprecated |
| review | TEXT | draft/pending/approved/rejected |
| props_json | TEXT | 扩展属性（scenario_profile 等） |
| source_file | TEXT | 相对 vault 路径 |
| source_hash | TEXT | 文件内容 sha256 |
| manifest_version | TEXT | 来源版本 |
| updated_at | TEXT | ISO 时间 |

**qp_kg_edge**

| 字段 | 类型 | 说明 |
|---|---|---|
| edge_id | TEXT PK | e:<rel>:<src>:<dst>，规范化排序 |
| rel | TEXT | 8 类之一 |
| src_id | TEXT | 起点 |
| dst_id | TEXT | 终点 |
| strength | TEXT | hard/soft（先修） |
| parallel_kind | TEXT | scenario_cooccur/skill_shared |
| rationale | TEXT | 理由 |
| evidence | TEXT | 证据 |
| status | TEXT | draft/approved/rejected |
| owner | TEXT | 负责人 |
| source_file | TEXT | 关系文件 |
| source_hash | TEXT | 内容哈希 |
| manifest_version | TEXT | 版本 |
| updated_at | TEXT | 时间 |

**qp_kg_syllabus**

| 字段 | 类型 | 说明 |
|---|---|---|
| syllabus_id | TEXT PK | syl:<year>:<subject>:<seq> |
| year | INTEGER | 年份 |
| subject_id | TEXT | 科目 |
| module | TEXT | 一级模块 |
| official_text | TEXT | 原文 |
| source | TEXT | 来源 |
| coverage | INTEGER | 0–100 |
| status | TEXT | aligned/partial/extension/missing/retired |
| updated_at | TEXT | 时间 |

**qp_kg_manifest**

| 字段 | 类型 | 说明 |
|---|---|---|
| version | TEXT PK | 2026-11-05.1 |
| created_at | TEXT | 时间 |
| vault_hash | TEXT | 全库哈希 |
| node_count | INTEGER | 节点数 |
| edge_count | INTEGER | 边数 |
| approved_by | TEXT | 批准人 |
| note | TEXT | 说明 |

**qp_kg_change**

| 字段 | 类型 | 说明 |
|---|---|---|
| change_id | TEXT PK | chg:... |
| version | TEXT | 版本 |
| change_type | TEXT | add/edit/retire/merge/split |
| target | TEXT | 节点/边 |
| proposal_id | TEXT | 提案 |
| actor | TEXT | 操作者 |
| created_at | TEXT | 时间 |
| detail_json | TEXT | 前后对比 |

**qp_kg_health**

| 字段 | 类型 | 说明 |
|---|---|---|
| run_id | TEXT | 运行 ID |
| metric | TEXT | H1–H13 |
| value | REAL | 值 |
| threshold | TEXT | 阈值 |
| status | TEXT | green/yellow/red |
| detail | TEXT | 明细 |
| created_at | TEXT | 时间 |

### 12.3 有效视图

- v_qp_kg_knowledge_point：approved、active 的知识点，带题量、子考点数、域/科目名。
- v_qp_kg_exam_point：approved、active 的考点，带题量、父知识点。
- v_qp_kg_edge_approved：approved 边，按 8 类分开或加 rel 过滤。
- v_qp_kg_point_question_count：点/考点的题量。
- v_qp_kg_domain_coverage：域下知识点/考点/题量/覆盖率。
- v_qp_kg_health_latest：最新一次健康结果。
- 视图只读；业务代码不得写视图。

### 12.4 graph_builder v2

目标：保留现有 GraphStore 与 key 规则，修正语义。用 feature flag 控制，默认关闭，P3 验收后开启。

**节点**

- 不再只用 KnowledgePoint/Question 两种 label；保留 label 兼容，但加 props.nodeType = Subject/Domain/KnowledgePoint/ExamPoint/Question。
- key 继续用现有数字 ID 字符串，避免破坏 F5 消费者；domain/subject 用 sub_category_id/subject_id。
- props 增加：title、subject、domain、nodeType、coverage_status、manifest_version。
- 只投影 approved + active；draft/deprecated 默认不投影。

**边**

| 边 | 来源 | 说明 |
|---|---|---|
| CONTAINS | 结构父 | L1→L2、L2→L3；props derivation=structure |
| INSTANCE_OF | 考点 parent_kp | EP→KP；不再用于题 |
| PREREQUISITE_OF | 07-关系/先修边 | 仅 approved；props strength/rationale/evidence |
| PARALLEL_WITH | 07-关系/并行边 | 仅 approved；不再自动生成 siblings |
| CONTRAST_WITH | 07-关系/易混边 | 仅 approved |
| COGNITIVE_SHARED_WITH | 07-关系/跨科边 | 仅 approved，跨科校验 |
| ASSESSES | question_knowledge + 映射 | Question→EP；若只到 KP，props granularity=knowledge_point |

**明确移除**

- 删除“parent→child 即 PREREQUISITE_OF”的自动生成。
- 删除“同父兄弟两两 PARALLEL_WITH”的自动生成。
- 删除“Question→KnowledgePoint 的 INSTANCE_OF”；改为 ASSESSES。

**兼容策略**

- graph_builder v2 与 v1 并存，通过环境变量 QP_KG_GRAPH_V2=false/true 切换。
- v2 写新投影前先备份 foundation_graph_*；失败回滚。
- F5 现有消费者只读 node/edge 基本字段；新增 props 不破坏。
- 旧数据不删，先 build 新 plan 到临时表/临时库，验收后替换。

### 12.5 graph_query v2

新增方法（旧方法保留但标记 deprecated）：

| 方法 | 语义 | 方向 |
|---|---|---|
| prerequisites_curated(point_id, depth) | 只沿 approved PREREQUISITE_OF 取祖先 | in |
| successors_curated(point_id, depth) | 取后继 | out |
| parallel_curated(point_id) | 只取 approved PARALLEL_WITH | both |
| contrasts(point_id) | 易混 | both |
| cognitive_bridges(subject_id) | 跨科桥 | both |
| instances_of(point_id) | 考点实例 | in（EP→KP） |
| questions_of_exam_point(ep_id) | 题 | in（Question→EP） |
| questions_of_point(kp_id, include_descendants) | 题（兼容旧） | in |

规则：

- 默认过滤 deprecated；需要历史时 include_deprecated=true。
- 深度上限沿用 GRAPH_QUERY_MAX_DEPTH=5；超过截断并标记 truncated。
- 返回结构带 rel/strength/rationale，前端可解释“为什么推荐”。
- 不注册 HTTP 路由（与现状一致）；由服务层调用。

### 12.6 快速练习 API 兼容

- P1/P2 不改任何 /api/quick-practice/* 端点；现有 5 个读接口 + submit 保持契约。
- 数据仍读 base 表；qp_kg 覆盖层先不介入读路径，避免“设计未验收就影响线上”。
- P3 可选：新增 includeCoverage=true 参数，返回 coverage_status/题量；默认关闭。
- P3 可选：新增 /api/quick-practice/coverage 只读端点；需 API 变更评审。
- 任何端点变更必须更新 api_surface.json 基线并跑契约测试（R11）。

### 12.7 代码落位

~~~text
backend/app/services/qp_kg/
├── __init__.py
├── obsidian.py        # vault 路径、读写、manifest、哈希、幂等
├── parser.py          # frontmatter/关系文件解析
├── validator.py       # G1–G10、H1–H13
├── compiler.py        # 规范化、diff、patch、plan
├── graph_plan.py      # graph_builder v2 的 plan 生成
└── health.py          # 健康指标

scripts/qp_kg/qp_kg.py  # CLI 入口

backend/tests/qp_kg/
├── test_parser.py
├── test_validator.py
├── test_compiler.py
├── test_graph_plan.py
└── fixtures/golden_vault/
~~~

约束：

- 单文件 ≤800 行；函数 ≤60 行；一个组件一个文件。
- 只用标准库 + 现有依赖；不新增图数据库驱动。
- 不直接 import content_guard（避免耦合）；复用其 manifest/幂等/安全路径模式，或在 utils 抽公共函数。
- 所有写操作先 dry-run；apply 只能由 CLI 显式 --yes 触发。

### 12.8 与 content_guard 的关系

content_guard 已经验证了“导出投影 + manifest + 幂等写 + 安全路径”的范式；qp_kg 复用其思想，不复制其业务：

| content_guard | qp_kg |
|---|---|
| 敏感词库 → Markdown 投影 | 知识图谱 → Markdown 策展 |
| 单向导出，回写走待审队列 | 双向：卡片策展 → 编译写覆盖层 |
| MANIFEST_REL=99-系统/导出清单.json | 09-编译产出/manifest.json |
| export_all(db, vault, dry_run) | compile/apply/rollback |
| 禁止 Agent 删除 | 同样禁止 |

### 12.9 安全与权限

- 路径安全：所有 vault 路径必须 resolve 后仍在 vault 根内；拒绝 ..、绝对路径、符号链接逃逸。
- 文件安全：不执行卡片中的任何代码/命令；模板不调用外部进程。
- 密钥：库内禁止密钥/Token/连接串；Local REST API Token 只放本机环境变量。
- 权限：AI 只写 00-收件箱；apply 仅管理员；评审仅授权角色。
- 删除：任何情况下不物理删除；退役/归档代替。
- 审计：每次 apply 记录 actor/时间/提案/哈希；日志保留 ≥1 年。

### 12.10 测试策略

| 层 | 测什么 | 方式 |
|---|---|---|
| parser | frontmatter、wikilink、关系文件、坏 YAML | 单测 + golden vault |
| validator | G1–G10、H1–H13、环、对称、证据缺失 | 单测 + 属性测试（随机图） |
| compiler | 规范化、diff、patch、幂等 | 单测 + 两次编译哈希一致 |
| graph_plan | 边类型、无 siblings、无 hierarchy-as-prereq | 单测 + 快照 |
| apply/rollback | 备份、事务、失败回滚 | 集成测试（临时库） |
| API 契约 | 343 端点不变；快速练习 6 端点 | 现有基线比对 |
| 性能 | 1000 节点扫描/编译 <30s | 基准测试 |

### 12.11 可观测性

- CLI 输出结构化 JSON；退出码 0/1/2（成功/校验失败/运行错误）。
- 日志：时间、命令、vault、db、manifest、耗时、错误数。
- 指标：扫描节点数、边数、错误数、警告数、apply 行数、耗时。
- P1 不新增 HTTP 监控端点；P3 可选加只读 /api/admin/qp-kg/health（需评审）。

## 13. 健康度指标与验收

### 13.1 H1–H13 指标定义

| # | 指标 | 计算 | 阈值 | 级别 | 基线/说明 |
|---|---|---|---|---|---|
| H1 | 断链 | 无法解析的 wikilink 数 / 总 wikilink 数 | 断链数 = 0 | 红 | P1 首跑测量；模板/改名是主要来源 |
| H2 | 孤立率 | approved L3/L4 中，无语义边且无题的点 / 总数 | ≤2% | 红/黄 | v1 图投影有 374 个知识点节点无任何边；语义孤立 P1 实测 |
| H3 | 层级违规 | L2 无科目、L3 无域、L4 无父 KP、深度>5 的数量 | 0 | 红 | 已知 21 个 L2 无域 |
| H4 | 先修环 | PREREQUISITE_OF 中的环数 | 0 | 红 | v1 层级边是树，无环；新增策展边 P1 后检查 |
| H5 | 证据缺失 | approved 语义边缺 rationale 或 evidence 的数量 | 0 | 红 | 现有自动边无 rationale，v2 不继承 |
| H6 | 粒度异常 | L3 的 L4>15 或题>200；L4 题>30；L4 混 3 种以上题型 | 0 个未评审异常 | 黄 | 已知单父最多 13 子；P1 全量算 |
| H7 | 大纲覆盖 | (aligned+partial) / 有效大纲条目 | ≥90% | 红/黄 | 目前无结构化大纲条目，P1 导入后测 |
| H8 | 题点覆盖 | 有 approved EP（或标 KP 粒度）的可见题 / 3410 | ≥95% | 红 | 原始 qk 去重 2923/3410=85.7%；approved 覆盖更低，需治理 |
| H9 | 命名规范 | approved 中的容器名（其他/待归类/综合）数；node_id/文件名重复数 | 容器 0；重复 0 | 红/黄 | 已知 134 个“其他”、3 个“待归类”、63 组同科目重名（标题重名允许，ID 不允许） |
| H10 | 版本漂移 | source_hash 与 manifest 不一致的卡片数 | 0 | 红 | 手工改卡未编译即漂移 |
| H11 | 跨科预算 | approved COGNITIVE_SHARED_WITH 边数 | ≤30 | 黄 | 当前 0；超预算拒绝 |
| H12 | 度分布/连通 | 语义图平均度、最大度、最大连通分量占比 | 平均 3–6；最大≤12；giant≥90% | 黄 | v1 全图平均度约 2.28（含题节点）；v2 按语义图算 |
| H13 | 退役引用 | active 边指向 deprecated 节点的数量 | 0（或全部标 deprecated_target） | 黄 | 当前 0；退役流程启用后检查 |

### 13.2 当前基线判断（诚实版）

| 项 | 当前 | 判断 |
|---|---|---|
| 结构完整性 | 21 个 L2 无域；358 个 L2 无子；仅 7 个 L4 | 红 |
| 先修语义 | 533 条层级边被当先修；无人工 rationale | 红（语义错误） |
| 并行语义 | 1046 条兄弟边；组合噪声 | 红（语义错误） |
| 实例化语义 | 2775 条题→点 INSTANCE_OF；考点层几乎为空 | 红（语义错位） |
| 题点覆盖 | 2923/3410 有 qk；664 题无关系；758 题有域无点 | 黄/红 |
| 大纲对齐 | 16 域大体对齐；无条目级映射；公专命名偏差 | 黄 |
| 命名 | 134 个“其他”；3 个“待归类”；63 组重名 | 红 |
| 图规模 | 3823 节点/4354 边；374 知识点孤立 | 黄 |
| 可视化 | 根 vault 有 Dataview/Canvas/图表插件；子库为空 | 待建 |
| 编译/回滚 | 无 | 红（本方案补齐） |

> 结论：当前不是“微调”，而是“结构保留 + 语义重建 + 治理补课”。这也是为什么 P1 只建库、P2 才动覆盖层、P3 才动运行图。

### 13.3 验收门（P1–P4）

**P1 验收**

- 目录、首页、14 个目录、模板、铁律、角色卡全部到位。
- 3 科目 + 16 域 + 1049 知识点 + 7 考点卡片全部生成，scan 解析成功率 100%。
- 每张卡有 node_id/title/status/review/owner/updated；无断链。
- 09-编译产出 生成 manifest v0、nodes.jsonl、health_report.json（基线）。
- **不写数据库、不改代码、不改 base 表**；仅新增 vault 文件与编译脚本（脚本可先不 apply）。
- 用户抽查 ≥30 张卡，确认字段/正文骨架/关系占位可用。

**P2 验收**

- H1/H3/H4/H5 = 0；H9 容器 = 0（或全部标 deprecated）；H2 ≤2%。
- 21 个无域 L2 全部归位或退役；358 个无子 L2 全部分诊（补 L4/降 L4/退役/教学型），有台账。
- 63 组重名全部处理（合并/别名/保留说明）；134 个“其他”全部拆解或退役。
- 7 个 L4 保留并补全；新增 L4 全部有题干模板或真题。
- 先修 hard 边全部有 rationale/evidence/签字；并行/易混/跨科全部有证据。
- H7 ≥90%，H8 ≥95%（或有用户批准的豁免清单）。
- 所有变更只写 qp_kg_*；base 表零变更；每批 apply 有备份与回滚点。

**P3 验收**

- graph_builder v2 在临时库生成：节点类型正确、无 siblings 并行、无 hierarchy 先修、ASSESSES 正确。
- graph_query v2 单测覆盖 8 类关系；深度/过滤/退役行为正确。
- 快速练习 6 个端点契约不变；343 端点基线比对通过。
- apply/rollback 演练成功：备份→apply→抽样→rollback→校验一致。
- 性能：1000 节点 scan+compile <30s；图查询 P95 <100ms（本地）。
- 用户批准后才把 QP_KG_GRAPH_V2 默认改为 true。

**P4 验收**

- 合作方按 01-入口/合作伙伴上手.md 独立完成：新建一个知识点、一条先修边、跑 scan/validate/dry-run。
- 培训 2 场（教研 1 场、合作方 1 场），录屏/文档归档。
- 30 天护航：每周健康报告、问题清单、修复记录。
- 交接签字：目录、模板、编译器、备份、回滚、指标全部可独立运行。

### 13.4 回归与监控

- 每次 apply 后自动跑：H1–H5 + API 契约 + 图查询抽样。
- 每周一生成健康周报；红色项必须有人认领。
- 每月复盘指标趋势；连续两月恶化则暂停新增，先还债。
- 每季度回滚演练一次；每半年审一次大纲与关系预算。

---

## 14. 实施路线、风险与拍板

### 14.1 路线图

| 阶段 | 范围 | 主要产出 | 门禁 | 预估 | 负责 |
|---|---|---|---|---|---|
| P0 | 设计定稿与审批 | 本方案 + 归档 + README 索引 | 用户批准 D1–D10 | 1–2 天 | 架构/文档 |
| P1 | 建库与基线导入（只读） | 目录/首页/模板/铁律；3+16+1049+7 卡；scan/validate 基线；manifest v0 | P1 验收；base 零变更 | 3–5 天 | 知识工程师 |
| P2 | 治理与覆盖层 | 归位/拆解/合并/补 L4/建边；qp_kg_*；每批 apply+回滚点 | P2 验收；H1–H5 绿 | 2–4 周 | 教研+知识工程师 |
| P3 | 运行图 v2 | graph_builder/query v2；flag；测试；演练 | P3 验收；契约不变 | 1–2 周 | 后端+架构 |
| P4 | 交接与护航 | 培训、手册、30 天周报、签字 | P4 验收 | 1 周 + 30 天 | 全员 |

> 时间为工作量级估算，不是承诺；P2 取决于教研评审吞吐，宁可延长，不可放水。

### 14.2 关键路径

P0 批准 → P1 建库 → P2 归位（最慢）→ P2 建边/评审 → P3 图 v2 → P4 交接。

**最慢环节不是写代码，是 358 个无子 L2 + 134 个“其他” + 63 组重名的教研判定。** 必须提前排班，按域分批，每批有负责人和截止日。

### 14.3 风险登记

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | 为凑四层造空考点 | 高 | 高（污染推荐） | 类型而非等深；L4 准入；teaching_only |
| R2 | 教研评审瓶颈 | 高 | 高（延期） | 分批、每批 50–80 项、SLA、优先级 |
| R3 | 关系噪声反弹 | 中 | 高 | 边预算、证据门槛、禁止自动兄弟边 |
| R4 | Obsidian 插件/版本漂移 | 中 | 中 | 最小插件集、配置入 Git、版本登记 |
| R5 | 路径/编码问题（中文、空格） | 中 | 中 | UTF-8、正斜杠、路径校验、Windows 实测 |
| R6 | 误删/误改数据 | 低 | 高 | 不删除、备份、事务、回滚演练 |
| R7 | AI 越权改正式卡 | 中 | 高 | AI 只写收件箱；权限与审计 |
| R8 | 合作方另起一套 | 中 | 中 | 交接手册、模板、扩展规则、联合评审 |
| R9 | 覆盖层与 base 漂移 | 中 | 高 | 单一 SoT、版本哈希、定期对账 |
| R10 | 大纲年度变化未跟上 | 中 | 中 | 年度 diff 流程、责任人、到期提醒 |

### 14.4 需要用户拍板的 10 件事（D1–D10）

| # | 决策 | 建议 | 不批准的后果 |
|---|---|---|---|
| D1 | 四层是“类型”而非“强制等深”，允许 teaching_only | 批准 | 会被迫造大量空考点 |
| D2 | 采用 8 条关系（含易混/跨科/大纲映射） | 批准 | 关系表达不足，或退回“相关”大杂烩 |
| D3 | 当前不引入 Neo4j，继续 local GraphStore | 批准 | 增加运维与双写风险 |
| D4 | 策展写 qp_kg_* 覆盖层，P1/P2 不改 base 表 | 批准 | 设计未验收就影响线上 |
| D5 | P1 只建库与只读导入，不 apply、不改代码 | 批准 | 范围失控、风险前置 |
| D6 | 公专“基本警务能力”先加显示别名“基本能力”，DB 改名单独立项 | 批准 | 对外口径不一致 |
| D7 | 行测“政治理论/科学推理”暂标 extension/pending，待教研确认 | 批准 | 被质疑“不对标大纲” |
| D8 | 358 个无子 L2 按“补 L4/降 L4/退役/教学型”四分诊 | 批准 | 无法收敛，考点层建不起来 |
| D9 | 跨科认知桥全局上限 30 条 | 批准 | 跨科边泛滥，失去稀疏性 |
| D10 | Obsidian 子库结构、Git 管理、AI 只写收件箱 | 批准 | 协作边界不清，易误改 |

> 建议一次批准 D1–D10；若有异议，请指出编号与理由，我按您的意见改方案，不进入实施。

### 14.5 交付物清单

1. 本设计文档（docs/superpowers/specs + solve_problems_files 归档）。
2. docs/README.md 索引更新。
3. P1 的 Obsidian 子库（目录、首页、模板、铁律、基线卡、看板骨架）。
4. 编译器 CLI 与单测（scan/validate/diff/compile/apply/rollback/health）。
5. qp_kg_* 覆盖层 DDL 与有效视图。
6. graph_builder/query v2 代码与测试（P3）。
7. 健康报告、差异台账、评审记录、培训材料。
8. 合作伙伴上手手册与扩展指南。

### 14.6 下一步

- 您审批 D1–D10（可逐条）。
- 批准后我进入 P1：只在 D:/Obsidian仓库/快速练习知识分层 建库与只读导入，不写数据库、不改代码。
- P1 完成后给您抽查包（目录截图/卡片样例/health 基线），再决定是否进入 P2。

---

## 附录 A：模板全文（可直接复制）

### A.1 知识点模板

~~~markdown
---
node_id: "kp:000000"
node_type: KnowledgePoint
title: "待填写"
subject: "公专"
subject_id: "sub:3"
domain: "待填写"
domain_id: "dom:00"
parent: "[[dom_00_待填写]]"
knowledge_kind: concept
difficulty: 0.5
exam_weight: 0.5
coverage_status: teaching_only
status: draft
review: draft
owner: "待填写"
updated: 2026-11-05
syllabus_refs: []
prerequisites: []
parallel_with: []
contrasts_with: []
cognitive_shared_with: []
scenario_profile: null
aliases: []
tags:
  - 快速练习/知识点
---

## 一句话定义

暂无。

## 构成/流程

暂无。

## 命题形态

暂无。

## 易错点

暂无。

## 关系理由

暂无。

## 大纲依据

暂无。

<!-- AUTO:CHILDREN:BEGIN -->
<!-- AUTO:CHILDREN:END -->

<!-- AUTO:BACKLINKS:BEGIN -->
<!-- AUTO:BACKLINKS:END -->

<!-- AUTO:HEALTH:BEGIN -->
<!-- AUTO:HEALTH:END -->
~~~

### A.2 考点模板

~~~markdown
---
node_id: "ep:000000"
node_type: ExamPoint
title: "待填写"
subject: "公专"
subject_id: "sub:3"
domain: "待填写"
domain_id: "dom:00"
parent_kp: "[[kp_000000_待填写]]"
exam_form: "概念辨析"
question_types: []
difficulty: 0.5
frequency: medium
last_exam_years: []
coverage_status: missing
status: draft
review: draft
owner: "待填写"
updated: 2026-11-05
syllabus_refs: []
aliases: []
tags:
  - 快速练习/考点
---

## 命题决策点

暂无。

## 题干模板

暂无。

## 正确项逻辑

暂无。

## 干扰项逻辑

暂无。

## 真题/样题索引

暂无。
~~~

### A.3 收件箱提案模板

~~~markdown
---
proposal_id: "prop:YYYY-MM-DD-000"
proposal_type: new_edge
status: pending
priority: P2
proposer: "待填写"
owner: "待填写"
created: 2026-11-05
due: 2026-11-12
affected_nodes: []
evidence: []
risk: low
rollback: "仅覆盖层，删除对应 patch 即可"
tags:
  - 快速练习/收件箱
---

## 现状

暂无。

## 建议

暂无。

## 证据

暂无。

## 影响

暂无。

## 回滚

暂无。
~~~

### A.4 先修边模板

~~~markdown
---
relation: PREREQUISITE_OF
version: 1
updated: 2026-11-05
edges:
  - src: "kp:000000"
    dst: "kp:000001"
    strength: soft
    rationale: "待填写：不学 A 为什么学不会 B。"
    evidence: "待填写：真题/大纲/教材/评审意见。"
    status: draft
    owner: "待填写"
    updated: 2026-11-05
---

## 判定说明

待填写。

## 待讨论

待填写。
~~~

## 附录 B：字段速查

| 字段 | 适用 | 可选值/格式 |
|---|---|---|
| node_type | 全部 | Subject/Domain/KnowledgePoint/ExamPoint/SyllabusItem |
| status | 全部 | draft/active/deprecated |
| review | 全部 | draft/pending/approved/rejected |
| knowledge_kind | 知识点 | concept/procedure/scenario/principle/skill |
| exam_form | 考点 | 概念辨析/法条适用/程序排序/计算/案例分析/材料概括/公文写作/论证评价/图形推理/资料分析/其他 |
| coverage_status | 点/考点 | has_exam_points/teaching_only/has_questions/missing |
| strength | 先修边 | hard/soft |
| parallel_kind | 并行边 | scenario_cooccur/skill_shared |
| 大纲状态 | 大纲 | aligned/partial/extension/missing/retired |
| 提案状态 | 收件箱 | pending/approved/rejected/revise |
| 优先级 | 收件箱 | P0/P1/P2/P3 |

## 附录 C：术语表

| 术语 | 含义 |
|---|---|
| SoT | Source of Truth，唯一事实源；本项目为 SQLite |
| 设计态 | Obsidian 中的策展卡片与关系 |
| 编译态 | manifest/patch/plan 等机器产物 |
| 运行态 | qp_kg_* 覆盖层与 foundation_graph_* 投影 |
| CONTAINS | 结构包含 |
| INSTANCE_OF | 考点→知识点的实例化 |
| PREREQUISITE_OF | 先修 |
| PARALLEL_WITH | 并行 |
| CONTRAST_WITH | 易混 |
| COGNITIVE_SHARED_WITH | 跨科认知共享 |
| ASSESSES | 题→考点 |
| SYLLABUS_MAPS_TO | 大纲条目→节点 |
| teaching_only | 只教学、暂无考点的知识点 |
| hard/soft | 考试硬先修/学习建议先修 |
| giant component | 最大连通分量 |
| 覆盖层 | qp_kg_* 表，不改 base |
| manifest | 一次编译的版本清单与哈希 |

## 附录 D：实测索引（可复核）

| 事实 | 位置 |
|---|---|
| 科目模型 | backend/app/models/models.py:119 |
| 知识点模型 | backend/app/models/models.py:152 |
| 子科目模型 | backend/app/models/models.py:1845 |
| 题-知识点模型 | backend/app/models/models.py:1865 |
| QuestionBank 的 point/sub_category | backend/app/models/models.py:181-198 |
| 快速练习注释 | backend/app/models/models.py:1841 |
| 图构建 | backend/app/foundation/graph_builder.py（178 行） |
| 图查询 | backend/app/foundation/graph_query.py（106 行） |
| 图配置 | backend/app/foundation/config.py |
| 图 schema | backend/app/foundation/graph_schema.py |
| 快速练习 API | backend/app/api/v1/exam/quick_practice.py:77、:351-378 |
| content_guard 范式 | backend/app/services/content_guard/obsidian.py |
| 四库映射原则 | docs/superpowers/specs/题目入库知识图谱与四库映射_v1.md |
| 文档索引 | docs/README.md |
| 现有 vault 根 | D:/Obsidian仓库/.obsidian |
| 目标子库 | D:/Obsidian仓库/快速练习知识分层 |

## 附录 E：第一版方案对照

| 第一版 | 本方案 | 原因 |
|---|---|---|
| 树转图，Neo4j 运行态 | 图化但 local 运行态，Neo4j 可选 | 实测默认 local；规模不需要 |
| 3 条边 | 8 条边 | 补齐易混/跨科/题评价/大纲映射 |
| 父→子先修 | 父→子 CONTAINS；先修人工策展 | 分类不等于学习顺序 |
| 兄弟并行 | 人工并行 | 兄弟笛卡尔是噪声 |
| 题→点实例化 | 考点→点 INSTANCE_OF；题→考点 ASSESSES | 语义归位 |
| Obsidian 拖拽同步 | frontmatter/关系文件 + 编译器 | 可校验、可回滚 |
| 目录 7 区 | 14 区 + 首页 | 增加大纲/评审/编译/归档 |
| 只做看板 | 看板 + Canvas + Mermaid + 编译器 | 可视化与治理闭环 |
| 100% 对标大纲 | 可验证对齐 + 差异台账 | 现状有命名/来源差异 |

## 附录 F：审批签字表

| 角色 | 姓名 | 结论（批准/修改/驳回） | 意见 | 日期 |
|---|---|---|---|---|
| 用户/项目负责人 |  |  |  |  |
| 学科负责人-行测 |  |  |  |  |
| 学科负责人-申论 |  |  |  |  |
| 学科负责人-公专 |  |  |  |  |
| 技术负责人 |  |  |  |  |
| 知识工程师 |  |  |  |  |

> 签字只代表认可本方案范围与门禁，不代表放弃后续逐批评审；每批 apply 仍需按第 9 章流程批准。



