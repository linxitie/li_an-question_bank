# F5 图投影与 GraphStore 交付报告

> 日期：2026-10-27
> 范围：F5 图投影（GraphStore + 迁移 003 + 回填/对账 + 只读查询 + L7-20）
> 基线：main c66d14c（F4 完成）
> 计划：docs/superpowers/plans/F5图投影与GraphStore_实施计划_v1.md
> 结论：Step 0–8 完成，A1–A16 均有证据；真实 Neo4j 冒烟未执行，已在第 6 节写明。

## 1. 交付摘要

F5 把知识点层级、同父兄弟关系、题目与知识点关联写入「可重建的图投影」，不改变任何现有 HTTP 读路径，也不把图库变成第二事实源：

- 新增 GraphStore 协议 + local 实现 + Neo4j HTTP 适配器；默认 GRAPH_BACKEND=local。
- 迁移 003 新增 foundation_graph_node / foundation_graph_edge 与 2 个索引，不改任何既有表。
- 3 类关系：PREREQUISITE_OF（父→子，层级派生）、PARALLEL_WITH（同父兄弟两两配对）、INSTANCE_OF（题目→知识点）。
- 回填脚本默认 dry-run，支持 --apply --reset 全量重建；对账写 foundation_reconcile_run(scope=graph)。
- /health/foundation 增加 graph 段；L7 从 19 项扩展到 20 项。
- 只暴露内部只读函数，不新增 HTTP API，不接业务页面。

## 2. 实测基线

| 项 | 值 |
|---|---|
| 生产库 | backend/data/question_bank.db（SQLite WAL） |
| knowledge_point | 1049 行（status=1 518 / status=0 531） |
| 层级边 | parent_id<>0 共 533 行 |
| 同父兄弟对 | 1046 对 |
| question_knowledge | 2775 行；distinct question_id=2774；无重复/孤儿 |
| 图节点预期 | 1049 + 2774 = 3823 |
| 图边预期 | 533 + 1046 + 2775 = 4354 |
| 回填前图投影 | 不存在 |
| 回填后图投影 | 节点 3823 / 边 4354 |

## 3. 代码与文件

### 3.1 新增

| 文件 | 内容 |
|---|---|
| backend/migrations/20261027_003_graph_projection.sql | 两张图投影表 + ix_graph_edge_src / ix_graph_edge_dst |
| backend/app/foundation/graph_schema.py | 图投影 DDL 读取、建表与校验 |
| backend/app/foundation/stores/graph.py | GraphStore 协议、2 类节点/3 类关系白名单、版本守卫、工厂与异常 |
| backend/app/foundation/stores/local_graph.py | SQLite 原子 upsert、BFS、删除级联、counts/health |
| backend/app/foundation/stores/neo4j_graph.py | httpx 调 Neo4j HTTP transactional endpoint，无 neo4j 驱动依赖 |
| backend/app/foundation/graph_builder.py | 从 SoT 构建节点/边计划，派生三类关系 |
| backend/app/foundation/graph_query.py | prerequisites / parallel_points / questions_of_point / neighbors |
| backend/app/foundation/graph_reconcile.py | 全量/抽样对账、报告、记录与新鲜度 |
| backend/scripts/foundation/backfill_graph.py | 默认 dry-run；--apply 写入；--reset 重建 |
| backend/scripts/audit/graph_inventory.py | 全量/抽样对账；--record 写库；drift 退出码 1 |
| backend/tests/test_graph_store.py | local CRUD、版本守卫、BFS、校验器、缺表健康 |
| backend/tests/test_graph_builder.py | 节点/边计数、兄弟方向、幂等、reset、limit |
| backend/tests/test_graph_query.py | 隐藏节点、limit、深度、不可用降级 |
| backend/tests/test_graph_reconcile.py | missing/orphan/mismatched/sample、记录与新鲜度 |
| backend/tests/test_graph_health.py | disabled/ok/degraded 不抛异常 |
| backend/tests/test_neo4j_graph.py | fake HTTP：Basic Auth、Cypher/参数、版本守卫、401/5xx/Cypher 错误、health、counts |

### 3.2 修改

| 文件 | 内容 |
|---|---|
| backend/app/foundation/config.py | GRAPH_STORE_ENABLED/BACKEND/NEO4J_*/QUERY_MAX_DEPTH/RECONCILE_MAX_AGE_DAYS |
| backend/app/core/config.py | 同步 Settings 键 |
| backend/app/foundation/health.py | snapshot 增加 graph 段（enabled/backend/ok/degraded/last_reconcile/drift） |
| backend/scripts/migrate/apply.py | 登记 003、--verify 校验 graph schema |
| backend/scripts/gates/gate_l7_foundation.py | 新增 L7-20；文档头 19→20 |
| docs/superpowers/specs/砺安题库终态总体架构_v2.0.md | §11.2 新增 L7-20 并同步 FAIL/WARN 口径 |
| docs/README.md | F5 计划状态、报告索引、变更记录 |

共 25 个文件：7 改 + 18 新增（含迁移、6 个测试、计划与报告）。无新依赖、无 .vtj 改动、无 /api/v1 路径变化、无业务表结构改动。

## 4. 关键设计

### 4.1 节点与关系

| 类型 | key | 属性 |
|---|---|---|
| KnowledgePoint | point_id | pointId/name/subjectId/subCategoryId/parentId/level/sortOrder/status |
| Question | question_id | questionId/subjectId/typeId/status/difficulty |
| PREREQUISITE_OF | 父→子 | derivation=hierarchy |
| PARALLEL_WITH | 同父兄弟小 id→大 id | derivation=sibling |
| INSTANCE_OF | Question→KnowledgePoint | derivation=question_knowledge |

根知识点不生成 PARALLEL_WITH；只保留 status 字段，查询默认只返回 status=1 的节点。

### 4.2 版本与重建

- 回填固定 version=1。
- 节点 local/Neo4j 只接受更大的 version；等版本重复写返回 skipped。
- 边没有 version，upsert 使用 MERGE，重复写不会产生重复边，但会计入 edges_written。
- 因此重复 --apply 节点跳过、边重写但计数稳定；完整重建仍用 --apply --reset。

### 4.3 故障边界

- GRAPH_STORE_ENABLED=false 时不构图、不查询，业务零影响。
- local 图存储不可用 L7 FAIL；Neo4j 不可用只 WARN，且不静默回落 local。
- 图查询是内部函数，GraphStoreUnavailable 时返回空列表；不改变任何业务读路径。

## 5. 验收 A1–A16

| # | 验收 | 结果 | 证据 |
|---|---|---|---|
| A1 | local upsert/get/delete/health；非法 label/rel/key 拒绝 | PASS | test_graph_store.py 全部通过 |
| A2 | 版本单调、重复写幂等 | PASS | test_graph_store.py 同版本 False、version=2 更新 |
| A3 | 三类节点/边计数与 SoT 一致 | PASS | 生产回填 3823 节点 / 4354 边，与基线一致 |
| A4 | 回填幂等、dry-run 不写 | PASS | 生产二次 apply：nodes_written=0 / nodes_skipped=3823，边 MERGE 重写 4354，节点/边计数不变；脚本默认 dry-run |
| A5 | PREREQUISITE_OF 遍历与深度上限 | PASS | test_graph_query.py / local BFS |
| A6 | PARALLEL_WITH 双向、根不生成兄弟边 | PASS | test_graph_builder.py / test_graph_query.py |
| A7 | INSTANCE_OF 遍历与 limit | PASS | test_graph_query.py |
| A8 | 递归 CTE 与图查询一致 | PASS | graph_inventory --full：sampled=100 sample_mismatch=0 |
| A9 | 对账 drift=0，可检出人为偏差 | PASS | 二次 apply 后 run_id=ac79a8836136480c status=ok；单测覆盖 missing/orphan/mismatched |
| A10 | Neo4j fake server 契约 | PASS | test_neo4j_graph.py 9 passed：Auth/Cypher/参数/401/5xx/Cypher 错误/health/counts |
| A11 | 真实 Neo4j 冒烟 | PARTIAL | 未启动容器，未执行；适配器仅 fake HTTP 验证 |
| A12 | 开关回滚 | PASS | test_graph_health.py disabled；GRAPH_STORE_ENABLED=false 不查询 |
| A13 | 红线 | PASS | git status：无 .vtj、无 /api/v1 路径、无业务表改动 |
| A14 | L7-20 | PASS | L7 20 项：19 PASS / 1 既有 WARN / 0 FAIL |
| A15 | 回归 | PASS | 后端 818 passed / 4 skipped / 2 xfailed；前端 354 passed；typecheck 0 |
| A16 | 报告 | PASS | 本文件 |

## 6. 偏差与限制

1. 真实 Neo4j 未执行。适配器由 9 个 fake HTTP 用例覆盖协议与错误映射；GRAPH_BACKEND=neo4j 仍属可选路径，L7 对 Neo4j 不可用只 WARN。
2. 不做增量事件。knowledge_point / question_knowledge 没有 HTTP 写入口，题目导入关联也无对应 Outbox 事件；F5 采用「回填 + 可重置重建」，题目导入后需运行 backfill_graph.py --apply --reset。
3. PREREQUISITE_OF 由 parent_id 派生，PARALLEL_WITH 由同父兄弟派生，均不代表人工审核的教学先修；边属性 derivation 已标注来源。
4. 全量对账 checked=8177 是期望节点 3823 + 期望边 4354，不是 8177 个节点。
5. 图投影表虽在主库，但只存可重建投影，不承载业务读请求；后续若接读路径应另立计划并做灰度。

## 7. 测试与门禁

- 图专项：test_graph_store / builder / query / reconcile / health 共 20 passed。
- Neo4j fake HTTP：test_neo4j_graph.py 9 passed。
- 全量后端：818 passed / 4 skipped / 2 xfailed（cwd=backend，含 test_neo4j_graph.py 9 项）。
- 前端：npm run test:unit → 25 文件 / 354 tests passed；npm run typecheck → 0。
- L7：PASS=19 WARN=1 FAIL=0；唯一 WARN 为既有 L7-10 precount 空库；L7-20 PASS（backend=local enabled=True local=ok nodes=3823 edges=4354）。
- gate_all：8/10 通过；FAIL 为 L2（既有材料配对基线：材料页表格行归属正确率 1.0、匹配配对 FAIL）与 L4（本地 8000 服务未启动，urlopen 拒绝连接），均与 F5 无关；L3、L5、L6、L7 全部 PASS。

## 8. 生产数据操作记录

    python scripts/foundation/backfill_graph.py --apply --reset
      planned: KnowledgePoint=1049, Question=2774
               PREREQUISITE_OF=533, PARALLEL_WITH=1046, INSTANCE_OF=2775
      written: nodes=3823, edges=4354, skipped=0

    python scripts/foundation/backfill_graph.py --apply        # 二次 apply 验证幂等
      nodes_written=0 nodes_skipped=3823 edges_written=4354 edges_skipped=0

    python scripts/audit/graph_inventory.py --full --record
      run_id=ac79a8836136480c status=ok checked=8177
      missing=0 mismatched=0 orphan=0 sampled=100 sample_mismatch=0

    python scripts/migrate/apply.py --verify
      verify: OK

报告写入 backend/data/reports/reconcile/graph_b0166144d52b4f09.json；数据目录已被 .gitignore 覆盖。

## 9. 回滚

1. GRAPH_STORE_ENABLED=false 或 GRAPH_BACKEND=off 立即停用图投影。
2. 删除 foundation_graph_node / foundation_graph_edge 两表即可，SoT 零改动；重新执行迁移与回填可恢复。
3. Neo4j 侧只删 LiAnNode 标记：MATCH (n:LiAnNode) DETACH DELETE n。
4. 回滚代码：git revert <F5 commit>；无新依赖，无需卸载。

## 10. 运维要点

- 开关：GRAPH_STORE_ENABLED（默认 true）、GRAPH_BACKEND（local/neo4j/off）。
- Neo4j：GRAPH_NEO4J_URI / USER / PASSWORD / DATABASE；密码只由用户环境变量注入。
- 重建：python scripts/foundation/backfill_graph.py --apply --reset。
- 对账建议每周一次：python scripts/audit/graph_inventory.py --full --record；drift 时先看 report 的 missing/mismatched/orphan。
- 深度上限：GRAPH_QUERY_MAX_DEPTH=5；单次查询不得越过该值。

## 11. 结论

F5 的图投影闭环已建立：SoT 可重建、回填可重置、结果可对账、查询只读且不暴露 HTTP。当前图库是纯投影，不承载线上读请求；Neo4j 为可选后端，真实环境冒烟留待用户启动容器后补做。
