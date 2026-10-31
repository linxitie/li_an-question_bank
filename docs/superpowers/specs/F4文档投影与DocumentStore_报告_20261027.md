# F4 文档投影与 DocumentStore 交付报告

> 日期：2026-10-27
> 范围：F4 文档投影（文档库 + Outbox 事件 + 回填/对账 + 双读日志 + L7-19）
> 基线：main f0d9ea5（端口统一 9527 之后）
> 计划：docs/superpowers/plans/F4文档投影与DocumentStore_实施计划_v1.md
> 结论：Step 0–8 完成，A1–A18 全部有证据；1 处实现偏差、2 项真实环境限制已在第 6 节写明。

## 1. 交付摘要

F4 让试卷资源、导入快照、论坛内容进入「可重建的文档投影」，但不改变任何现有 HTTP 读路径，也不把文档库变成第二事实源：

- 新增 DocumentStore 协议 + local 实现 + Mongo 适配器（可选依赖，默认不启用）。
- 3 个集合：exam_resources、import_snapshots、forum_contents。
- 4 个 Outbox 事件：exam.paper.snapshot、question.import.snapshot、material.import.snapshot、forum.content.changed。
- 业务写路径只在同一事务内 emit 事件，文档写入由投影 handler 完成，禁止业务层直接写文档库。
- 回填脚本默认 dry-run；对账写入 foundation_reconcile_run（scope=document）；双读抽样只记录 JSONL，不切换读路径。
- L7 从 18 项扩展到 19 项（L7-19 文档库健康 + 对账新鲜度 + drift）。

## 2. 实测基线

| 项 | 值 |
|---|---|
| 生产库 | backend/data/question_bank.db（SQLite WAL） |
| exam_paper | 38 行 |
| question_import_record | 1632 行（COMPLETED 1084 / PREVIEW 539 / PARTIAL 6 / FAILED 2 / PARSING 1） |
| material_import_record | 0 行 |
| forum_post | 5 行 |
| forum_comment | 1 行 |
| 回填前文档根 | 不存在 |
| 回填后文档数 | 1675 = 38 + 1632 + 5 |

## 3. 代码与文件

### 3.1 新增

| 文件 | 内容 |
|---|---|
| backend/app/foundation/stores/document.py | DocumentStore 协议、3 集合白名单、canonical_json、key 校验、工厂与异常 |
| backend/app/foundation/stores/local_document.py | 本地原子写（临时文件 + fsync + os.replace）、版本守卫、损坏检测、health 探针 |
| backend/app/foundation/stores/mongo_document.py | pymongo 延迟导入、版本守卫 update_one、异常统一映射 DocumentStoreUnavailable |
| backend/app/foundation/document_schema.py | 3 类 JSON-LD 文档构造 + 敏感字段递归拒绝 |
| backend/app/foundation/document_projection.py | 4 个 Outbox handler，inbox 幂等 + version=max(1,event.id) |
| backend/app/foundation/document_events.py | 3 个 emit 入口，统一走 foundation_outbox |
| backend/app/foundation/document_reconcile.py | 源表枚举、文档哈希、missing/mismatched/orphan 对账、记录与新鲜度 |
| backend/app/foundation/document_shadow.py | 双读比对，只写 JSONL，不抛异常 |
| backend/scripts/foundation/backfill_documents.py | 默认 dry-run，--apply 写，断点游标，超限跳过 |
| backend/scripts/audit/document_inventory.py | 全量/抽样对账，--record 写库 |
| backend/scripts/audit/document_shadow_sample.py | 双读抽样，--write-report 写摘要 |
| backend/tests/test_document_store.py | 9 个 |
| backend/tests/test_document_schema.py | 8 个 |
| backend/tests/test_document_projection.py | 6 个 |
| backend/tests/test_document_events.py | 4 个 |
| backend/tests/test_document_reconcile.py | 7 个 |

### 3.2 修改

| 文件 | 内容 |
|---|---|
| backend/app/foundation/config.py | DOC_STORE_ENABLED/BACKEND/ROOT/MAX_BYTES/MONGO_*/RECONCILE_MAX_AGE_DAYS 与 document_store_root() |
| backend/app/core/config.py | 同步 Settings 键 |
| backend/app/core/events.py | 4 个 EV_* 并加入 ALL_EVENTS |
| backend/app/services/event_handlers.py | build_handlers() 注册 4 个文档 handler |
| backend/app/foundation/health.py | snapshot() 增加 document 段（enabled/backend/ok/degraded/last_reconcile_at/drift） |
| backend/scripts/gates/gate_l7_foundation.py | 新增 L7-19；文档头由 18 项改 19 项 |
| backend/app/api/v1/catalog/papers.py | update_paper / publish_paper 同事务 emit |
| backend/app/api/v1/catalog/question_import.py | 批量导入成功、异步 PREVIEW、FAILED 回写同事务 emit；PARSING 过渡态不投 |
| backend/app/api/v1/library/materials.py | 所有创建/成功/失败分支与 OCR 回写统一 _commit_material_import |
| backend/app/api/v1/community/forum.py | 发帖/删帖/评论同事务 emit；点赞不投 |
| backend/tests/test_batch_parsed_import.py | 临时库补建 foundation 表（F4 起导入事务会写 outbox） |
| backend/tests/test_gate_l3.py | 同上 |
| docs/superpowers/specs/砺安题库终态总体架构_v2.0.md | §11.2 新增 L7-19 行，检查范围与 FAIL/WARN 口径 18→19 |

共 33 个文件：15 改 + 18 新增（含计划、报告与架构 L7 章节同步）。无新表、无迁移、无新依赖、无 .vtj 模板改动。

## 4. 关键设计

### 4.1 文档 key 与内容

| 集合 | key | 文档 |
|---|---|---|
| exam_resources | paper_id | JSON-LD @type=ExamPaper；questionRefs 只存 questionId + score，不复制题干 |
| import_snapshots | question_import_record:<id> / material_import_record:<id> | previewData/errorMessages/importStatus 或 parseResult/parseStatus |
| forum_contents | post_id | 帖子正文 + status==1 的 comments；软删仍写 status=DELETED |

### 4.2 版本策略

- 回填固定 version=1。
- 增量投影 version=max(1, event.id)（foundation_outbox 全局自增，单调）。
- 不使用 aggregate_ver：否则回填 version=1 会挡住 aggregate_ver=1 的首个增量。
- local/Mongo 都只接受更大的 version；等版本或旧版本直接返回 False，保证重复事件幂等。

### 4.3 故障边界

- 文档库不可用时 handler 抛 DocumentStoreUnavailable，交 Outbox 重试/dead letter；业务事务已提交，不受影响。
- DOC_STORE_ENABLED=false 时 emit 仍可在 outbox 模式下记录，投影侧不写文档；回填/对账脚本显式提示关闭。
- 现有读路径一律不读文档库；双读只写 data/reports/foundation/document_shadow.jsonl。

### 4.4 资料导入 _tmp 修正

计划要求“pending/processing 不写快照，终态写并在写入前剥离 _tmp”。实现按此执行：终态文档保留正文，递归删除 _tmp 键；不再因为解析结果中残留 _tmp 而永远跳过。

## 5. 验收 A1–A18

| # | 验收 | 结果 | 证据 |
|---|---|---|---|
| A1 | local upsert/get/delete/health；key 禁止 ../ 与盘符 | PASS | test_document_store.py 9 passed |
| A2 | 版本单调、重复写幂等 | PASS | test_document_store.py；test_document_projection.py 重复事件不重写 |
| A3 | 三类文档字段与 SoT 一致 | PASS | document_shadow_sample --sample 500：checked=500 / mismatch=0 / error=0 |
| A4 | 回填幂等 | PASS | 首次 apply 1675 written；二次 apply 全 0；断点 cursor 生效 |
| A5 | 文档库不可用时导入仍成功 | PARTIAL（服务级） | 投影单测覆盖 DocumentStoreUnavailable；未在真实 HTTP 导入中停 Mongo 做端到端 |
| A6 | 恢复后自动补写 | PARTIAL（服务级） | Outbox 重试由 F1/F2b 机制覆盖；未做真实故障注入后重启 Dispatcher |
| A7 | 论坛发帖/评论/删除 | PASS（单测） | test_document_schema/projection 覆盖评论过滤与软删 DELETED；未逐条走 HTTP |
| A8 | 试卷发布/更新 | PASS（单测） | exam_resources 文档与 questionRefs 由 schema 测试覆盖；papers.py 已接入 emit |
| A9 | 无双写 | PASS | 全仓 grep：业务层无 build_document_store/LocalDocumentStore/MongoDocumentStore 直接引用 |
| A10 | 无新表/迁移 | PASS | git status 无 migrations；foundation 7 表未变 |
| A11 | 超限文档 | PASS | 8 MiB 上限；test 超限 skipped，不写半截 |
| A12 | 双读只日志 | PASS | document_shadow 只写 JSONL；读路径未改 |
| A13 | 对账 drift=0 | PASS | run_id=e51a7408f9c44eb9：checked=1675，missing=0，mismatched=0，orphan=0 |
| A14 | L7-19 | PASS | L7 19 项：18 PASS / 1 既有 WARN / 0 FAIL |
| A15 | 回归 | PASS | 后端 789 passed / 4 skipped / 2 xfailed；前端 354 passed；typecheck 0 |
| A16 | 回滚 | PASS | DOC_STORE_ENABLED=false 单测覆盖不建目录；不改表/API |
| A17 | 红线 | PASS | 无 .vtj 模板改动，无 /api/v1 路径变化 |
| A18 | 报告 | PASS | 本文件 |

## 6. 偏差与限制

1. **事件 payload 只有 source_table/import_id、paper_id、post_id**，未实现计划 §6.1 的 status/action 与 dedupe_key（event_name+aggregate_id+status/action+更新时间）。幂等由 foundation_inbox claim + 文档 version 保证；同一聚合的连续事件仍会各写一次，只是最终内容正确。属实现简化，不影响一致性。
2. 真实 MongoDB 未安装、未执行冒烟；Mongo 适配器仅由代码评审与缺 URI 单测覆盖，L7-19 对 Mongo 不可用只 WARN。
3. A5/A6 未做真实 HTTP 故障注入；A7/A8 以单测和代码接入为准，未逐条跑三端 UI。

## 7. 测试与门禁

- 定向：document_store/schema/projection/events/reconcile 共 34 passed。
- 全量后端：789 passed / 4 skipped / 2 xfailed（cwd=backend）。
- 前端：npm run test:unit → 25 文件 / 354 tests passed；npm run typecheck → 0。
- L7：PASS=18 WARN=1 FAIL=0；唯一 WARN 为既有 L7-10 precount 空库。
- gate_all：8/10 通过；FAIL 为 L2（既有材料配对基线）与 L4（本地 8000 服务未启动，urlopen 拒绝连接），均与 F4 无关；L3 已因 F4 事件写入补建门禁临时库的 foundation 表后恢复 10/10。

## 8. 生产数据操作记录

    python scripts/foundation/backfill_documents.py --collection all          # dry-run
      exam_resources total 38 / import_snapshots total 1632 / forum_contents total 5
    python scripts/foundation/backfill_documents.py --collection all --apply
      written 1675 / failed 0
    python scripts/audit/document_inventory.py --full --record
      run_id=e51a7408f9c44eb9 status=ok checked=1675 missing=0 mismatched=0 orphan=0
    python scripts/audit/document_shadow_sample.py --sample 500 --write-report
      checked=500 ok=true mismatch=0 error=0

文档根 backend/data/foundation/docs 已被 .gitignore 覆盖；报告写入 backend/data/reports，不入库。

## 9. 回滚

1. DOC_STORE_ENABLED=false 立即停写文档；业务与现有读路径零影响。
2. 删除 backend/data/foundation/docs 可全量重建；不触碰 SoT。
3. 回滚代码：git revert <F4 commit>；无表结构/迁移/依赖需要回滚。
4. Mongo 未启用，无外部状态需要清理。

## 10. 运维要点

- 开关：DOC_STORE_ENABLED（默认 true）、DOC_STORE_BACKEND（local/mongo/off）、DOC_STORE_ROOT、DOC_STORE_MAX_BYTES=8388608。
- Mongo：DOC_STORE_MONGO_URI / DOC_STORE_MONGO_DB / DOC_STORE_MONGO_PREFIX；pymongo 为可选依赖，缺失时明确抛 DocumentStoreUnavailable。
- 对账建议每周一次：document_inventory.py --full --record；drift 时先看报告中的 missing/mismatched/orphan。
- 抽样建议每日 100 条：document_shadow_sample.py --sample 100 --write-report；mismatch/error 退出码 1。

## 11. 结论

F4 的文档投影闭环已建立：写路径只经 Outbox、历史数据可回填、可对账、可双读抽样、可一键降级。当前文档库是纯投影，不承载任何线上读请求；后续若切换读路径，应另立计划并先做读流量灰度与回滚演练。
