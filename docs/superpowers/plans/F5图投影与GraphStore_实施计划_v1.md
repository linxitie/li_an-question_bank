# F5 图投影与 GraphStore 实施计划 v1

> 状态：已批准并执行（2026-10-27，Step 0–8 完成，tag foundation-v1-f5）
> 依据：docs/superpowers/specs/砺安题库终态总体架构_v2.0.md §5.1/§5.2/§9.6/§13
> 前置：F1 一致性内核、F2b 事件同事务化、F4 文档投影均已完成（tag foundation-v1-f1/f2b1/f2b2/f4）
> 基线：main c66d14c（F4 完成，工作树干净）

## 0. 背景

终态架构把存储分为「1 个事实源 + 4 类可重建投影」。F4 已完成文档投影；F5 只做图投影，让知识点层级、题目与知识点的关联进入可重建图存储，为后续检索、推荐与 Agent 提供只读关系缝。

F5 不改变任何现有 HTTP 读路径，不把图数据库变成第二事实源，不把图查询结果直接暴露给业务页面。图数据全部可由 knowledge_point、question_knowledge、question_bank 的 SoT 行重新生成。

## 1. 实测基线（2026-10-27，只读）

| 项 | 实测值 |
|---|---|
| 生产库 | backend/data/question_bank.db（SQLite WAL） |
| knowledge_point | 1049 行；其中 status=1 为 518 行，status=0 为 531 行 |
| knowledge_point 层级边 | parent_id<>0 共 533 行；无父节点缺失、无自指 |
| knowledge_point 同父兄弟对 | 按 parent_id 分组，C(n,2) 合计 1046 对 |
| question_bank | 3357 行 |
| question_knowledge | 2775 行；distinct question_id=2774；无重复 (question_id,knowledge_point_id)；无孤儿 |
| 图节点预期 | 知识点 1049 + 已关联题目 2774 = 3823 |
| 图边预期 | 层级 533 + 兄弟 1046 + 题目关联 2775 = 4354 |
| 现有图投影 | 不存在；无 foundation_graph_node/edge 表 |
| 现有迁移 | 001 foundation 7 表、002 media_assets；无 003 |
| 现有 L7 | 19 项，PASS=18 WARN=1 FAIL=0（唯一 WARN 为既有空库审计） |
| 现有 store | Document/Object 已实现；GraphStore 仅架构协议，无实现 |
| 本机 Docker | 镜像已有 mongodb、neo4j:5-community、minio、redis、postgres；无 Milvus 镜像；无运行中容器；无数据卷；6379 仅由宿主机 Redis 服务监听；27017/7687/19530 未监听 |

结论：图数据量很小（3823 节点/4354 边），local 实现足以覆盖开发与验收；Neo4j 适配器同批实现但默认不启用。真实 Neo4j 冒烟依赖用户启动容器并设置密码，未启动时以 fake HTTP server 验证协议，报告中如实标注。

## 2. 目标与非目标

### 2.1 目标

1. 新增 GraphStore 协议、local 实现与 Neo4j 适配器；默认 GRAPH_BACKEND=local。
2. 用迁移 003 新增 foundation_graph_node / foundation_graph_edge 两张投影表，不改任何既有表。
3. 定义并实现三类关系：PREREQUISITE_OF、PARALLEL_WITH、INSTANCE_OF。
4. 从 SoT 全量回填图投影；回填可 dry-run、可重复执行、可重建。
5. 提供只读遍历内部函数（不新增 HTTP API）。
6. 对账节点/边计数与抽样遍历，结果写 foundation_reconcile_run(scope=graph) 与报告。
7. /health/foundation 增加 graph 段；L7 增加第 20 项。
8. Neo4j 不可用时明确 degraded，不静默回落 local。

### 2.2 非目标

- 不新增 HTTP API，不把图查询接到任何业务页面。
- 不改 .vtj 模板、路由、现有 API 出入参。
- 不改 knowledge_point / question_knowledge / question_bank 表结构。
- 不做 Cypher 透传，不把 Neo4j 查询语言暴露给业务层。
- 不做图算法（最短路径、PageRank、社区发现）与推荐排序。
- 不做增量事件接入：当前 knowledge_point/question_knowledge 没有 HTTP 写入口，题目导入的关联写入也没有对应 Outbox 事件；F5 采用「回填 + 可重复重建」，不伪装实时同步。题目导入后需要刷新图时运行重建脚本。
- 不实现 F6 向量投影与 Embedding 端口。
- 不要求本机 Neo4j 必须运行；真实冒烟属可选验证。

## 3. 待批准决策 D1–D9

| # | 决策 | 推荐 | 备选/影响 |
|---|---|---|---|
| D1 | 默认 local；Neo4j 适配器同批实现但 GRAPH_BACKEND 默认 local | ✅ | 只做 local 会留下后端缺口的假完成；默认 neo4j 会逼用户先起容器 |
| D2 | 图模型 = 知识点节点 + 已关联题目节点 + 三类边；保留 status 属性，查询默认过滤 status=1 | ✅ | 只投影 active 会让回填结果随状态变化而漂移；不保留 status 则无法过滤隐藏内容 |
| D3 | PREREQUISITE_OF 由 parent_id 派生（父→子）；PARALLEL_WITH 由同父兄弟两两配对派生；INSTANCE_OF 来自 question_knowledge | ✅ | 当前库没有显式先修/并行表；不派生则三类关系无法落地，需在报告中明确这是约定 |
| D4 | local 图存储使用主库新增 foundation_graph_node/edge 两表 + 迁移 003 | ✅ | 用独立 graph.db 会多一个游离数据文件；文件 JSON 邻接表不利于递归查询 |
| D5 | F5 为「回填 + 可重建」投影，不新增 Outbox 事件、不做增量 handler | ✅ | 加事件需要改导入写路径并新增事件契约，超出 F5 范围；重建脚本可覆盖 |
| D6 | 只读遍历只做内部函数，不暴露 HTTP | ✅ | 暴露 HTTP 会提前固化未审批的图查询契约 |
| D7 | Neo4j 通过 httpx 调 HTTP transactional endpoint，不新增 neo4j 驱动依赖；真实 Neo4j 冒烟可选 | ✅ | 引入 neo4j 驱动会新增依赖与版本约束；HTTP 足够覆盖 upsert/neighbors/health |
| D8 | L7 19→20；图表/local 不可用 FAIL，Neo4j 不可用、对账过期、drift/孤儿 WARN | ✅ | 全部 WARN 会失去门禁意义 |
| D9 | main 单提交 + tag foundation-v1-f5；预计 3 个工作日 | ✅ | 超过 40 文件再开短分支 |

## 4. 图模型契约

### 4.1 节点

| label | key | props | 来源 |
|---|---|---|---|
| KnowledgePoint | str(point_id) | pointId, name, subjectId, subCategoryId, parentId, level, sortOrder, status | knowledge_point |
| Question | str(question_id) | questionId, subjectId, typeId, status, difficulty | question_bank 中出现在 question_knowledge 的题目 |

约定：

- 节点 key 一律字符串；不把中文名当 key。
- 节点保留 status；查询函数默认只返回 status=1 的节点。
- 题目节点只覆盖 question_knowledge 中出现的题目（2774），不覆盖未关联题目的 583 道题；这样 INSTANCE_OF 边与关联表严格一一对应。
- 不复制题干、选项、答案、解析；图只服务关系检索。

### 4.2 边

| rel | src | dst | 派生规则 | 预期边数 |
|---|---|---|---|---|
| PREREQUISITE_OF | KnowledgePoint 父 | KnowledgePoint 子 | parent_id<>0 且父行存在 | 533 |
| PARALLEL_WITH | KnowledgePoint 较小 id | KnowledgePoint 较大 id | 同一 parent_id<>0 下的兄弟两两配对，规范化方向避免重复 | 1046 |
| INSTANCE_OF | Question | KnowledgePoint | question_knowledge 每行一条 | 2775 |

约定：

- PREREQUISITE_OF 是层级派生：父节点是子节点的前置分类。它不是人工审核过的教学先修关系；报告与文档必须写明这一点。
- PARALLEL_WITH 是同一父节点下的兄弟关系，不代表难度相同或可互换；只用于「同层扩展」检索。
- 根知识点（parent_id=0）之间不生成 PARALLEL_WITH，避免 516 个根节点两两组合爆炸。
- 边 props 至少含 derivation 字段（hierarchy/siblings/question_knowledge），便于审计。
- 所有边可重建；图存储中没有业务写入。

### 4.3 只读遍历语义

- prerequisites(point_id, depth=3)：沿 PREREQUISITE_OF 反向（子→父）取祖先，默认 depth 上限 5。
- parallel_points(point_id)：沿 PARALLEL_WITH 双向取同父兄弟。
- questions_of_point(point_id, limit=50)：沿 INSTANCE_OF 反向（知识点→题目）取题目节点。
- neighbors(label, key, rel, depth=1, direction=out)：通用只读遍历，direction 支持 out/in/both。
- 所有函数默认 include_hidden=false；遍历可以经过隐藏节点，但默认不返回隐藏节点。调用方需要完整树时显式 include_hidden=true。

## 5. GraphStore 协议与实现

### 5.1 协议

    class GraphStore(Protocol):
        backend: str
        def upsert_node(self, label: str, key: str, props: dict, *, version: int) -> bool: ...
        def upsert_edge(self, rel: str, src: tuple[str, str], dst: tuple[str, str], props: dict) -> None: ...
        def delete_node(self, label: str, key: str) -> None: ...
        def delete_edge(self, rel: str, src: tuple[str, str], dst: tuple[str, str]) -> None: ...
        def neighbors(self, label: str, key: str, rel: str, depth: int = 1,
                      direction: str = "out") -> list[dict]: ...
        def counts(self) -> dict: ...
        def clear(self) -> None: ...
        def health(self) -> StoreHealth: ...

异常：GraphStoreError / GraphStoreUnavailable / GraphStoreCorrupt / InvalidGraphTarget。

label 白名单：KnowledgePoint、Question。rel 白名单：PREREQUISITE_OF、PARALLEL_WITH、INSTANCE_OF。白名单之外的 label/rel 直接拒绝，避免 Cypher/SQL 注入。

### 5.2 local 实现

- 表在主库：foundation_graph_node(label,key,props,version,updated_at) 与 foundation_graph_edge(rel,src_label,src_key,dst_label,dst_key,props)。
- 主键：node(label,key)；edge(rel,src_label,src_key,dst_label,dst_key)。
- 索引：edge(src_label,src_key)、edge(dst_label,dst_key)。
- upsert_node 使用 INSERT ... ON CONFLICT DO UPDATE，excluded.version 小于现有 version 时保留旧值；返回是否真正写入。
- 每次调用新开 sqlite3 连接，busy_timeout=30000；写操作单事务提交。
- neighbors 用 Python BFS 逐层查边，避免递归 CTE 的循环路径与方言问题；深度上限 5。
- delete_node 同时删除该节点作为 src/dst 的边。
- clear 只清空两张图投影表，不触碰 foundation 7 表与业务表。
- health 执行 SELECT 1 并返回表是否存在；表缺失时 degraded=true，detail 明确。

### 5.3 Neo4j 实现（可选）

- 配置 GRAPH_NEO4J_URI（默认 http://localhost:7474）、USER、PASSWORD、DATABASE（默认 neo4j）。
- 通过 httpx POST {uri}/db/{database}/tx/commit，Body 为 statements 数组；Basic Auth。
- 所有节点额外带 LiAnNode 公共标签，便于 clear 时只删本投影：
  MERGE (n:LiAnNode:KnowledgePoint {key:$key}) SET n += $props, n.version=$version
- 关系类型来自白名单；MERGE 保证重复回填不产生重复边。
- clear 执行 MATCH (n:LiAnNode) DETACH DELETE n，只删本投影节点。
- health 执行 RETURN 1；连接失败、401/403、5xx 统一映射 GraphStoreUnavailable，不回落 local。
- 超时 3 秒；连接失败不阻塞业务，因为 F5 没有业务写路径依赖图。

### 5.4 工厂与开关

- build_graph_store(backend=None)：off → 抛 GraphStoreUnavailable("graph store disabled")；local → LocalGraphStore；neo4j → Neo4jGraphStore；未知后端 → 抛配置错误。
- reset_graph_store() 清进程内单例，供测试使用。
- GRAPH_STORE_ENABLED=false 时投影脚本与查询函数直接返回空/明确 disabled，现有业务零影响。

## 6. 配置键

| 键 | 默认 | 说明 |
|---|---|---|
| GRAPH_STORE_ENABLED | true | 总开关；false 时图投影与查询短路 |
| GRAPH_BACKEND | local | off / local / neo4j |
| GRAPH_NEO4J_URI | http://localhost:7474 | Neo4j HTTP 端点 |
| GRAPH_NEO4J_USER | neo4j | Basic Auth 用户 |
| GRAPH_NEO4J_PASSWORD | 空 | 仅 neo4j 后端需要；不得写入代码或文档 |
| GRAPH_NEO4J_DATABASE | neo4j | 数据库名 |
| GRAPH_QUERY_MAX_DEPTH | 5 | 遍历深度上限 |
| GRAPH_RECONCILE_MAX_AGE_DAYS | 7 | L7 对账新鲜度 |

同时写入 backend/app/foundation/config.py 与 backend/app/core/config.py，保持脚本与 Settings 同源。

## 7. 回填、对账与只读查询

### 7.1 回填脚本

backend/scripts/foundation/backfill_graph.py：

- 默认 dry-run：只统计节点/边数量与样例，不写库。
- --apply 才写；默认先 clear 已知图投影再全量写入，保证删除的 SoT 行不会残留。
- --no-reset 时只做 upsert，用于增量补写。
- --backend local|neo4j|auto；auto 读 GRAPH_BACKEND。
- --limit N 用于抽样；--batch 默认 500。
- 输出 nodes_by_label、edges_by_rel、written、failed；失败继续并退出码 1。
- 幂等：连续两次 --apply，第二次节点/边计数不变。

### 7.2 对账

backend/app/foundation/graph_reconcile.py：

- 期望节点/边由 SoT 重新计算；实际来自 GraphStore.counts() 与 keys 枚举。
- 统计 missing/orphan/mismatched；节点属性不一致计入 mismatched。
- 抽样 100 个知识点，比较「SoT 递归 CTE 祖先集合」与「GraphStore prerequisites」是否一致。
- 结果写 foundation_reconcile_run(scope=graph) 与 backend/data/reports/reconcile/graph_<run_id>.json。
- 对账失败不删除图；orphan 默认只报告。
- drifted>0 时 status=drift；枚举异常 status=warn 并记录原因。

backend/scripts/audit/graph_inventory.py：

- 默认只读，输出节点/边计数、按 label/rel 分布、抽样一致性。
- --full 全量比较 keys；--record 写 foundation_reconcile_run；drift 退出码 1。

### 7.3 只读查询

backend/app/foundation/graph_query.py：

- prerequisites(session, store, point_id, depth=3, include_hidden=False)
- parallel_points(store, point_id, include_hidden=False)
- questions_of_point(store, point_id, limit=50, include_hidden=False)
- neighbors(store, label, key, rel, depth=1, direction="out")
- 只做内部函数；不注册 FastAPI 路由，不在 main.py 暴露。

## 8. 健康检查与 L7

- /health/foundation 增加 graph 段：enabled、backend、ok、degraded、node_count、edge_count、last_reconcile_at、drift、detail。
- 图存储不可用时 graph.ok=false、degraded=true，不影响其他段。
- L7-20 检查：
  - 迁移 003 存在且 checksum 稳定；两张图表和两个索引存在，缺失 FAIL。
  - GraphStore 协议/local/Neo4j 适配器/构建器/回填/对账/查询文件存在，关键函数可导入，缺失 FAIL。
  - local health 不可用 FAIL；neo4j 不可用 WARN。
  - 无 graph 对账记录、超过 7 天、status=drift、孤儿>0 均 WARN。
- 文档头改为 20 项；架构 §11.2 增加第 20 行，检查范围改为 6–20。

## 9. 文件清单

新增：

- backend/migrations/20261027_003_graph_projection.sql
- backend/app/foundation/graph_schema.py（表结构/DDL 读取/校验）
- backend/app/foundation/stores/graph.py（协议/异常/工厂/白名单）
- backend/app/foundation/stores/local_graph.py
- backend/app/foundation/stores/neo4j_graph.py
- backend/app/foundation/graph_builder.py（节点/边生成与计数）
- backend/app/foundation/graph_reconcile.py
- backend/app/foundation/graph_query.py
- backend/scripts/foundation/backfill_graph.py
- backend/scripts/audit/graph_inventory.py
- backend/tests/test_graph_store.py
- backend/tests/test_graph_builder.py
- backend/tests/test_graph_reconcile.py
- backend/tests/test_graph_backfill.py
- backend/tests/test_graph_neo4j.py（fake HTTP server）

修改：

- backend/app/foundation/config.py（8 个 GRAPH_* 键）
- backend/app/core/config.py（同名 Settings 键）
- backend/app/foundation/health.py（graph 段）
- backend/scripts/migrate/apply.py（登记 003，verify 增加图表）
- backend/scripts/gates/gate_l7_foundation.py（L7-20）
- docs/README.md、架构 §11.2、本计划执行记录
- docs/ops/外部数据库与中间件手动下载清单_v1.md（补本机实测：Neo4j 镜像已拉取但容器未启动）

预计 24–30 个文件（新增 15，修改 9–15）。

## 10. Step 0–8

| Step | 内容 | 验证 | 回滚 |
|---|---|---|---|
| 0 | 基线：确认工作树干净、记录 SoT 计数、L7 19 项、F4 测试通过 | 全绿/仅既有 WARN | 无改动 |
| 1 | 迁移 003 + graph_schema + apply.py verify | 建表幂等；verify OK；二次 apply changed=0 | 删表/回退迁移 |
| 2 | 协议 + local 实现 + 单测 | test_graph_store 全过；版本/删除/遍历/健康 | 删新增文件 |
| 3 | graph_builder + 计数 | 节点 3823、边 4354；三类关系计数与 SoT 一致 | 删 builder |
| 4 | 回填 + 对账 + 审计脚本 | dry-run 准确；apply 后 drift=0；二次 apply 计数不变 | 清空图投影即可重建 |
| 5 | Neo4j 适配器 + fake HTTP 测试 | upsert/neighbors/health/错误映射；无真实 Neo4j 也可测 | 默认 local，不影响 |
| 6 | graph_query + health | 查询函数返回预期；/health/foundation 有 graph 段 | 关 GRAPH_STORE_ENABLED |
| 7 | L7-20 + 文档 + README | L7 19→20；架构/README 同步 | 回退门禁 |
| 8 | 全量验收 + 报告 + 提交/tag | A1–A16；后端全量、前端 unit/typecheck、gate_all | 关开关 |

## 11. 验收 A1–A16

| # | 验收 | 判定 |
|---|---|---|
| A1 | local upsert_node/upsert_edge/delete_node/delete_edge/health | 全部通过 |
| A2 | 节点版本单调 | 旧 version 不覆盖；重复写幂等 |
| A3 | 节点/边计数与 SoT 一致 | 知识点 1049 + 题目 2774 = 3823；层级 533 + 兄弟 1046 + 关联 2775 = 4354 |
| A4 | 回填幂等 | 第二次 apply 计数不变；dry-run 不写库 |
| A5 | PREREQUISITE_OF 遍历 | 子节点能取到父/祖父；depth 上限生效 |
| A6 | PARALLEL_WITH 遍历 | 同父兄弟双向可取；根节点无兄弟边 |
| A7 | INSTANCE_OF 遍历 | 知识点能取到关联题目；limit 生效 |
| A8 | 递归 CTE 与图查询一致 | 抽样 100 个知识点，祖先集合零差异 |
| A9 | 对账 drift=0 | 全量 inventory 后 status=ok；人为删节点可检出 missing |
| A10 | Neo4j fake server | MERGE/Cypher/健康/401/5xx 映射正确 |
| A11 | 真实 Neo4j（可选） | 用户启动容器并配置密码后跑 smoke；未执行须在报告标注 |
| A12 | 开关回滚 | GRAPH_STORE_ENABLED=false / GRAPH_BACKEND=off 后业务与测试零影响 |
| A13 | 红线 | 无 .vtj 模板改动、无 /api/v1 路径变化、无业务表结构改动 |
| A14 | L7-20 | PASS；Neo4j 缺失仅 WARN |
| A15 | 回归 | 后端全量无新增失败；前端 unit/typecheck 0 |
| A16 | 报告 | 交付报告含证据、偏差、限制、回滚 |

## 12. 测试计划

- 单测：local 原子写、版本守卫、删除级联、BFS 深度、非法 label/rel、表缺失健康。
- 构建：三类节点/边计数；重复边去重；根节点不生成兄弟边；question 只取已关联题目。
- 回填：dry-run 不写；apply 清空重建；二次 apply 幂等；limit/batch。
- 对账：删节点→missing；多写节点→orphan；改属性→mismatch；抽样祖先不一致。
- Neo4j：本地 fake HTTP server 校验 Basic Auth、Cypher 语句、MERGE 参数、错误映射；无真实 Neo4j 默认跳过真实冒烟。
- 回归：全量后端 pytest、前端 npm run test:unit、npm run typecheck、gate_all、L7。
- 真实 Neo4j：默认跳过；用户启动容器并设置 GRAPH_NEO4J_PASSWORD 后运行。

## 13. 风险与回滚

| 风险 | 影响 | 缓解 |
|---|---|---|
| 层级被误当教学先修 | 关系语义被高估 | 报告中明确 derivation=hierarchy，不是人工审核先修 |
| 兄弟对数量随知识点增长爆炸 | 边数膨胀 | 只对 parent_id<>0 的兄弟配对；当前 1046 条；超过 5 万条时告警并考虑只保留相邻兄弟 |
| 图投影过期 | 检索结果旧 | 重建脚本 + 对账报告；F5 不承诺实时 |
| Neo4j 未启动 | 真实冒烟缺失 | 默认 local；fake HTTP 测试；报告标注未执行 |
| 图写入放大 SQLite 锁 | 业务变慢 | 回填离线执行；每批 500；WAL/busy_timeout |
| 业务误连图库 | 破坏 C1 | 只暴露内部函数；无 HTTP；L7 检查契约 |
| 清空重建误删 | 图丢失 | clear 只删图投影；SoT 不动；可重建 |

回滚：

- GRAPH_STORE_ENABLED=false 或 GRAPH_BACKEND=off，立即停用图投影。
- 删除 foundation_graph_node/edge 两表或清空数据即可；SoT 零改动。
- Neo4j 侧 MATCH (n:LiAnNode) DETACH DELETE n 只删本投影。

## 14. 工作量与提交

- 预计 3 个工作日（架构原文 2 天；多出的 1 天用于 Neo4j HTTP 适配器、对账抽样与 L7-20）。
- 文件预计 24–30 个（新增 15，修改 9–15）。
- 提交：main 单提交 feat(foundation): F5 图投影与 GraphStore；tag foundation-v1-f5；不 push。
- 交付报告：docs/superpowers/specs/F5图投影与GraphStore_报告_20261027.md。

## 15. 环境现状与前置

本机实测（2026-10-27 19:05）：

- Docker daemon 29.8.2 可用。
- 镜像已有 mongodb/mongodb-community-server:latest、neo4j:5-community、cgr.dev/chainguard/minio:latest、redis:latest、postgres:15-alpine。
- 无 Milvus 镜像；F6 前需要用户另行拉取。
- docker ps -a 只有 redis 容器（Exited 0）；无运行中容器；docker volume ls 为空。
- 27017/7687/19530/9000/5432 均未监听；6379 由宿主机 Redis 服务监听。

F5 的 local 验收不依赖任何容器。真实 Neo4j 冒烟前置（可选）：

    docker run -d --name lian-neo4j -p 7474:7474 -p 7687:7687 \
      -e NEO4J_AUTH=neo4j/<用户自定密码> neo4j:5-community

密码由用户本人设置并通过环境变量 GRAPH_NEO4J_PASSWORD 注入；不得写入代码、文档或提交信息。容器启动后设置：

    GRAPH_BACKEND=neo4j
    GRAPH_NEO4J_URI=http://localhost:7474
    GRAPH_NEO4J_USER=neo4j
    GRAPH_NEO4J_PASSWORD=<用户自定密码>

若用户暂不启动 Neo4j，F5 仍可按 local + fake HTTP 完成，报告标注「真实 Neo4j 未执行」。

## 16. 批准记录

- 2026-10-27：用户回复「批准」，D1–D9 全部生效；随后按 Step 0–8 执行。
- 未安装新依赖、未启动容器；Neo4j 适配器以本地 fake HTTP 服务验证，真实 Neo4j 冒烟未执行。

## 17. 执行记录（2026-10-27）

### 17.1 代码与迁移

| 项 | 结果 |
|---|---|
| 迁移 | `backend/migrations/20261027_003_graph_projection.sql`，sha256 前缀 525ffc8225f505ad；创建 `foundation_graph_node` / `foundation_graph_edge` 与 2 个索引 |
| GraphStore 协议 | `app/foundation/stores/graph.py`：2 类节点、3 类关系、版本守卫、工厂与异常 |
| local 实现 | `app/foundation/stores/local_graph.py`：SQLite 原子 upsert、BFS、删除级联、health |
| Neo4j 适配器 | `app/foundation/stores/neo4j_graph.py`：httpx + HTTP transactional endpoint，无 neo4j 驱动依赖 |
| 构图/查询/对账 | `graph_builder.py`、`graph_query.py`、`graph_reconcile.py`；只读内部函数，无 HTTP |
| 脚本 | `scripts/foundation/backfill_graph.py`（默认 dry-run，`--apply --reset` 重建）、`scripts/audit/graph_inventory.py`（`--full --record`） |
| 健康与门禁 | `/health/foundation` 增加 graph 段；L7 19→20；迁移执行器登记 003 并校验 checksum |

### 17.2 生产回填与对账

    python scripts/foundation/backfill_graph.py --apply --reset
      planned: KnowledgePoint=1049, Question=2774; PREREQUISITE_OF=533, PARALLEL_WITH=1046, INSTANCE_OF=2775
      written: nodes=3823, edges=4354, skipped=0

    python scripts/foundation/backfill_graph.py --apply
      nodes_written=0 nodes_skipped=3823 edges_written=4354 edges_skipped=0

    python scripts/audit/graph_inventory.py --full --record
      run_id=ac79a8836136480c status=ok checked=8177 missing=0 mismatched=0 orphan=0
      sampled=100 sample_mismatch=0

    python scripts/migrate/apply.py --verify
      verify: OK

计数与计划基线完全一致：节点 3823 = 知识点 1049 + 已关联题目 2774；边 4354 = 层级 533 + 兄弟 1046 + 实例化 2775。

### 17.3 测试与门禁

- 定向：5 个图测试文件 20 passed；Neo4j fake HTTP 契约测试 9 passed。
- L7：PASS=19 WARN=1 FAIL=0；唯一 WARN 为既有 L7-10 precount 空库；L7-20 详情 `backend=local enabled=True local=ok nodes=3823 edges=4354`。
- 全量后端、前端 unit/typecheck、gate_all 结果见交付报告 §7。

### 17.4 偏差与限制

1. Neo4j 适配器未对真实容器冒烟；仅 fake HTTP 契约测试，`GRAPH_BACKEND=neo4j` 属可选路径。
2. 图投影不做增量事件，题目导入后需运行重建脚本；与计划 §2.2 一致。
3. `PARALLEL_WITH` 与 `PREREQUISITE_OF` 均为派生关系，derivation 已写入边属性，不代表人工审核的教学先修。
4. 重复 `--apply` 不提升节点 version，节点全部 skipped；边无 version，MERGE 会计入 edges_written 但不会重复；完整重建仍必须 `--reset`。
