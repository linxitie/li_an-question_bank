# F4 文档投影与 DocumentStore 实施计划 v1

> 状态：已执行（2026-10-27，Step 0–8 完成，待提交 tag foundation-v1-f4）
> 依据：docs/superpowers/specs/砺安题库终态总体架构_v2.0.md §5.1/§9.5/§13
> 前置：F3 对象存储（foundation-v1-f3）、F2b-1/F2b-2 事件与补发（foundation-v1-f2b1/f2b2）均已完成
> 基线：main f0d9ea5（端口统一 9527 之后）

## 0. 背景

终态架构把存储分为「1 个事实源 + 4 类可重建投影」。F1 已落地 Outbox/Dispatcher/对账，F2/F2b 已把业务事件同事务化并支持断线补发，F3 已落地对象存储与媒体资产。
F4 只做文档投影：让试卷资源、导入快照、论坛内容进入可重建的文档集合，为后续资料阅读、富文本展示与 Agent 检索提供只读缝；不改变任何现有 HTTP 读路径，不把文档库变成第二事实源。

## 1. 实测基线（2026-10-27，只读）

| 项 | 实测值 |
|---|---|
| 生产库 | backend/data/question_bank.db（SQLite WAL） |
| exam_paper | 38 行 |
| question_bank | 3357 行 |
| question_import_record | 1632 行；preview_data 最大 3,409,295 字节，平均 16,136 字节 |
| material_import_record | 0 行 |
| forum_post | 5 行；content 最大 48 字符 |
| forum_comment | 1 行 |
| file_resource | 0 行 |
| 现有文档投影 | 不存在；backend/data/foundation/docs 不存在 |
| 现有 foundation 表 | 7 张（schema.py TABLE_SPECS） |
| 现有 L7 | 18 项，PASS=17 WARN=1 FAIL=0 |
| 全量后端 | 755 passed / 4 skipped / 2 xfailed（端口修复后） |

结论：数据量很小，回填可在秒级完成；真正需要设计的是「写路径只经 Outbox、读路径仍走 SoT、故障可降级」。

## 2. 目标与非目标

### 2.1 目标

1. 新增 DocumentStore 协议与 local 实现；Mongo 适配器同批实现但默认不启用。
2. 定义 3 个文档集合：exam_resources、import_snapshots、forum_contents；agent_sessions 不在本期。
3. 历史数据可回填、可重复执行、可对账；回填不改 SoT。
4. 管理员题目导入、资料导入、论坛发帖/评论/删除、试卷发布/更新通过 Outbox 事件触发文档投影。
5. 文档库不可用时，业务写入与导入照常成功，事件积压并在恢复后补写。
6. 双读校验只记日志，不切换真实读路径；任何不一致不阻断业务。

### 2.2 非目标

- 不做全文检索、聚合查询、分页排序；查询仍走 SoT。
- 不新增 HTTP API，不暴露文档库；F4 只提供内部函数。
- 不新增业务表或迁移；不改 models；不改 .vtj 模板与路由。
- 不把论坛/导入/试卷的读路径切到文档库；切换属于后续阶段。
- 不实现 agent_sessions，不接 F5/F6。
- 不要求本机安装 MongoDB；真实 Mongo 冒烟属可选验证并如实标注。

## 3. 待批准决策 D1–D9

| # | 决策 | 推荐 | 备选/影响 |
|---|---|---|---|
| D1 | F4 默认 local；Mongo 适配器代码同批实现但 DOC_STORE_BACKEND 默认 local | ✅ | 只做 local 会留下后端缺口的假完成 |
| D2 | 集合仅 exam_resources / import_snapshots / forum_contents | ✅ | 加 agent_sessions 会扩大范围且无数据 |
| D3 | 所有文档写只经 Outbox 事件；业务层不得直接写 DocumentStore | ✅ | 直接写属双写，违反架构 §12 R-10 |
| D4 | 现有读路径一律不动；双读校验只写日志/报告 | ✅ | 切换读路径会引入不可回滚风险 |
| D5 | 回填脚本默认 dry-run，--apply 才写；记录 foundation_backfill_state | ✅ | 默认写库易污染生产 |
| D6 | 单文档上限 8 MiB；超限跳过并记错误，不截断 | ✅ | 截断会产生不可察觉的数据损坏 |
| D7 | pymongo 作为可选依赖；不写入必需 requirements；缺失时明确 DocumentStoreUnavailable | ✅ | 强制安装会逼用户先装 Mongo |
| D8 | L7 18→19；local 目录/健康/对账缺失 FAIL，Mongo 不可用仅 WARN | ✅ | 全部 WARN 会失去门禁意义 |
| D9 | main 单提交 + tag foundation-v1-f4；预计 4 个工作日 | ✅ | 超过 40 文件再开短分支 |

## 4. 数据契约

### 4.1 通用规则

- 文档根字段：@context、@id、@type、version、updatedAt、source、payload。
- @id 使用稳定 URN：urn:li-an:<collection>:<key>；key 做 URL 安全编码，禁止 / 与 ..。
- version 为单调整数：回填为 1，增量取 Outbox 的 aggregate_ver；旧 version 不覆盖新 version。
- 文档只存投影字段，不存密码、token、手机号等敏感字段。
- 单文档序列化后超过 DOC_STORE_MAX_BYTES（默认 8 MiB）直接失败，由 Outbox 重试并最终 dead letter，不写半截文件。

### 4.2 exam_resources

key = paper_id；来源 exam_paper + paper_question_relation + question_bank。

    {
      "@context": {"@vocab": "https://li-an.local/schema/"},
      "@id": "urn:li-an:exam_resources:38",
      "@type": "ExamPaper",
      "version": 1,
      "updatedAt": "2026-10-27T16:00:00+08:00",
      "source": {"table": "exam_paper", "id": 38},
      "payload": {
        "paperId": 38, "name": "...", "code": "...", "subjectId": 1,
        "compositionMethod": "...", "duration": 120, "totalScore": 100,
        "difficulty": 3, "questionCount": 100, "examType": "...",
        "description": "...", "knowledgeRange": "...",
        "settings": {"shuffleQuestions": 0, "shuffleOptions": 0, "maxAttempts": 1},
        "questionRefs": [{"questionId": 1, "score": 1.0}]
      }
    }

questionRefs 只存 id 与分值，不复制题干/选项；题目内容仍从 SoT 读。

### 4.3 import_snapshots

key = question_import_record:<import_id> 或 material_import_record:<import_id>；来源对应导入表。

    {
      "@context": {"@vocab": "https://li-an.local/schema/"},
      "@id": "urn:li-an:import_snapshots:question_import_record%3A1632",
      "@type": "ImportSnapshot",
      "version": 1,
      "updatedAt": "2026-10-27T16:00:00+08:00",
      "source": {"table": "question_import_record", "id": 1632},
      "payload": {
        "sourceTable": "question_import_record", "importId": 1632,
        "status": "PREVIEW", "originalFilename": "...", "fileType": "WORD",
        "totalQuestions": 100, "successCount": 0, "failedCount": 0,
        "duplicateCount": 0, "previewData": {}, "errorMessages": [],
        "importTime": "...", "completeTime": null, "progressPercent": 100,
        "currentPhase": "preview_ready"
      }
    }

material_import_record 的 payload 存 fileName/fileType/fileSize/parseMode/parseStatus/parseResult/errorMessage；parseResult 含 _tmp 临时路径时不写快照，等最终成功/失败状态再写。

### 4.4 forum_contents

key = post_id；来源 forum_post + forum_comment（status=1）。

    {
      "@context": {"@vocab": "https://li-an.local/schema/"},
      "@id": "urn:li-an:forum_contents:5",
      "@type": "ForumThread",
      "version": 3,
      "updatedAt": "2026-10-27T16:00:00+08:00",
      "source": {"table": "forum_post", "id": 5},
      "payload": {
        "postId": 5, "authorId": 1, "title": "...", "content": "...",
        "shareType": "EXPERIENCE", "tags": "...", "status": "NORMAL",
        "stats": {"likeCount": 0, "commentCount": 1, "viewCount": 10},
        "attachments": [],
        "comments": [{"commentId": 1, "userId": 2, "parentCommentId": null,
                      "content": "...", "likeCount": 0, "createTime": "..."}]
      }
    }

帖子软删除后仍写文档但 status=DELETED，便于后续读模型过滤；F4 不提供公开读接口。

## 5. 适配器与配置

### 5.1 DocumentStore 协议

    class DocumentStore(Protocol):
        backend: str
        def upsert(self, collection: str, key: str, doc: dict, *, version: int) -> None: ...
        def get(self, collection: str, key: str) -> dict | None: ...
        def delete(self, collection: str, key: str) -> None: ...
        def health(self) -> StoreHealth: ...

### 5.2 local 实现

- 根目录 backend/data/foundation/docs/<collection>/<sha256(key)[:2]>/<sha256(key)>.json。
- 文件名用 key 的 sha256，避免中文、冒号、斜杠与 Windows 保留名；文档内保存原始 key。
- 写临时文件 + os.replace 原子替换；失败清理临时文件并抛 DocumentStoreUnavailable。
- upsert 先读现有 version，新 version 不大于旧 version 时直接返回（幂等/乱序守卫）。
- get 解析失败抛 DocumentStoreCorrupt，不返回空对象冒充成功。

### 5.3 Mongo 实现（可选）

- 使用 pymongo 延迟导入；未安装抛 DocumentStoreUnavailable("pymongo 未安装")。
- 连接串 MONGO_URI、库 DOC_STORE_MONGO_DB、集合前缀 DOC_STORE_MONGO_PREFIX（默认空）。
- upsert 以 _id=key 写入，附带 version；用 version 条件更新，旧版本不覆盖。
- 超时 3 秒；连接失败不得阻塞业务，只让 Outbox 重试。

### 5.4 配置键

| 键 | 默认 | 说明 |
|---|---|---|
| DOC_STORE_ENABLED | true | 总开关；false 时投影跳过、读路径零影响 |
| DOC_STORE_BACKEND | local | local / mongo / off |
| DOC_STORE_ROOT | ./data/foundation/docs | local 根，相对 backend/ |
| DOC_STORE_MAX_BYTES | 8388608 | 单文档上限 |
| DOC_STORE_MONGO_URI | 空 | 仅 mongo 后端需要 |
| DOC_STORE_MONGO_DB | li_an_foundation | Mongo 库名 |
| DOC_STORE_MONGO_PREFIX | 空 | 集合前缀，便于多环境隔离 |
| DOC_STORE_RECONCILE_MAX_AGE_DAYS | 7 | L7 对账新鲜度 |

## 6. 写路径（只经 Outbox）

### 6.1 新增事件

| event_name | aggregate_type | 触发点 | payload |
|---|---|---|---|
| exam.paper.snapshot | exam_paper | 试卷发布/更新 | paper_id |
| question.import.snapshot | question_import_record | 导入进入 PREVIEW/COMPLETED/FAILED | import_id, status |
| material.import.snapshot | material_import_record | 解析 success/failed/consumed | import_id, status |
| forum.content.changed | forum_post | 发帖/删帖/评论新增 | post_id, action |

事件与业务行同一 Session，使用 foundation.outbox.emit；禁止在 commit 之后直接写文档。dedupe_key 采用 event_name + aggregate_id + status/action + 业务更新时间，避免重复投影。

### 6.2 投影处理器

新增 backend/app/foundation/document_projection.py：

- 注册 4 个 handler 到 Dispatcher 的 handlers 字典。
- handler 在 Dispatcher 事务内从 SoT 读取最新行，生成 JSON-LD，调用 DocumentStore.upsert。
- 行不存在或状态不允许投影时写日志并返回，不视为失败。
- 文档库不可用时抛异常，由 Dispatcher 走 attempts + 退避 + dead letter；业务写入已提交，不受影响。
- 不做跨域读，不做 N+1：单事件只查该聚合所需行。

### 6.3 业务接入点

- 题目导入：catalog/question_import.py 的 batch_import_parsed、_process_import_async（PREVIEW/FAILED 落库处）、upload_file_for_import（PARSING 不投，避免无意义中间态）。
- 资料导入：library/materials.py 的 import_upload 同步成功/失败分支与 _ocr_job 完成/失败分支。
- 论坛：community/forum.py 的 create_post、delete_post、create_comment；评论删除本期无接口，不编造。
- 试卷：catalog/papers.py 的发布/更新成功路径；只在已有事务内 emit。

## 7. 读路径与双读校验

- F4 不新增 HTTP；内部函数 document_read.get_exam_resource(paper_id) 等只允许 foundation 内部使用。
- document_shadow.py 提供 compare(collection,key)：从 SoT 重新生成文档，与 DocumentStore.get 做规范化 JSON 比较。
- 不一致写 data/reports/foundation/document_shadow.jsonl，字段含 collection/key/soT_hash/store_hash/at；只日志，不抛错。
- 抽样脚本 scripts/audit/document_shadow_sample.py 默认 100 条、只读；--write-report 才落报告。

## 8. 回填与对账

### 8.1 回填脚本

backend/scripts/foundation/backfill_documents.py：

- 默认 dry-run：只统计每集合将写多少、跳过多少、最大文档字节。
- --apply 才写；按 id 升序，batch 200；每批后提交 cursor 到 foundation_backfill_state。
- --collection exam_resources|import_snapshots|forum_contents|all；--limit N 用于抽样。
- 幂等：同 version 不重写；重复执行输出 changed=0。
- 失败不中断全局，记录 failed 列表并退出码 1；超 8 MiB 记 skipped_too_large。

### 8.2 对账

backend/app/foundation/document_reconcile.py：

- 统计 SoT 行数与文档数，差集列 missing/orphan。
- 抽样 500 条重算 sha256，统计 mismatched。
- 结果写 foundation_reconcile_run（scope=document）与 data/reports/reconcile/document_<run_id>.json。
- 对账失败不删除文档；orphan 默认只报告。

## 9. 健康检查与 L7

- /health/foundation 增加 document 段：enabled、backend、ok、degraded、docs_root、last_reconcile_at、drift。
- L7-19 检查：DocumentStore 可实例化且 health 可用；最近一次 document 对账不超过 7 天；drift=0；Mongo 不可用只 WARN。
- 架构 §11.2 增加第 19 行，检查范围改为 6–19。

## 10. 文件清单

新增：

- backend/app/foundation/stores/document.py（协议、异常、工厂）
- backend/app/foundation/stores/local_document.py
- backend/app/foundation/stores/mongo_document.py（可选依赖）
- backend/app/foundation/document_schema.py（JSON-LD 生成/校验/规范化）
- backend/app/foundation/document_projection.py（4 个 handler）
- backend/app/foundation/document_reconcile.py
- backend/app/foundation/document_shadow.py
- backend/scripts/foundation/backfill_documents.py
- backend/scripts/audit/document_inventory.py
- backend/scripts/audit/document_shadow_sample.py
- backend/tests/test_document_store.py
- backend/tests/test_document_projection.py
- backend/tests/test_document_reconcile.py
- backend/tests/test_document_backfill.py
- backend/tests/test_document_events.py

修改：

- backend/app/foundation/config.py（8 个 DOC_STORE 键）
- backend/app/foundation/health.py（document 段）
- backend/app/services/event_handlers.py 或 app/main.py 的 Dispatcher handlers 注册
- backend/app/api/v1/catalog/question_import.py（3 处 emit）
- backend/app/api/v1/catalog/papers.py（发布/更新 emit）
- backend/app/api/v1/library/materials.py（同步/异步完成 emit）
- backend/app/api/v1/community/forum.py（发帖/删帖/评论 emit）
- backend/scripts/gates/gate_l7_foundation.py（L7-19）
- .gitignore（backend/data/foundation/docs 若未覆盖）
- docs/README.md、架构 §11.2、本计划执行记录

## 11. Step 0–8

| Step | 内容 | 验证 | 回滚 |
|---|---|---|---|
| 0 | 基线：git status 干净、全量 pytest、L7、记录 6 表计数 | 全绿/仅既有 WARN | 无改动 |
| 1 | 协议 + local 实现 + 单测 | test_document_store 全过；路径穿越/超限/旧版本用例 | 删新增文件 |
| 2 | 配置 + health + 工厂 | 默认 local；mongo 缺 pymongo 明确 unavailable | 开关 false |
| 3 | JSON-LD 生成/校验 | 3 集合样例通过；敏感字段扫描为空 | 删 schema |
| 4 | 回填 + 对账 + 报告 | dry-run 计数准确；apply 后 1632+38+5 条；二次 changed=0 | 删 docs 根即可重建 |
| 5 | 4 个事件 + handlers + 业务接入 | 导入/论坛/试卷写后事件 pending→dispatched；文档更新 | 关 DOC_STORE_ENABLED |
| 6 | 双读日志 + 抽样脚本 | 人为改坏一份文档可检出，业务读不受影响 | 停用抽样 |
| 7 | L7-19 + 文档 + README | L7 PASS/WARN 符合预期；架构同步 | 回退门禁 |
| 8 | 全量验收 + 报告 + 提交/tag | A1–A18；后端全量、前端 typecheck/unit、gate_all | 开关 false |

## 12. 验收 A1–A18

| # | 验收 | 判定 |
|---|---|---|
| A1 | local upsert/get/delete/health | 全部通过；key 不允许 ../ 与盘符 |
| A2 | 版本单调 | 旧 version 不覆盖；重复写幂等 |
| A3 | 三类文档字段与 SoT 一致 | 抽样 500 条，零字段差异 |
| A4 | 回填幂等 | 第二次 apply changed=0，行数不变 |
| A5 | 文档库不可用时导入仍成功 | 业务 200；Outbox pending 增加；恢复后补写 |
| A6 | 恢复后自动补写 | 重启 Dispatcher 后 pending→dispatched，文档出现 |
| A7 | 论坛发帖/评论/删除 | 文档 version 递增，status 正确 |
| A8 | 试卷发布/更新 | exam_resources 文档更新，questionRefs 与关系表一致 |
| A9 | 无双写 | 全仓 grep 业务层不直接 import DocumentStore 写方法 |
| A10 | 无新表/迁移 | 迁移清单无新增；schema 7 表不变 |
| A11 | 超限文档 | 8 MiB 以上跳过并记 failed，不写半截 |
| A12 | 双读只日志 | 故意改坏文档后业务读仍成功，日志有 mismatch |
| A13 | 对账 drift=0 | 回填后 document reconcile drift=0 |
| A14 | L7-19 | PASS；Mongo 缺失仅 WARN |
| A15 | 回归 | 后端全量无新增失败；前端 unit/typecheck 0 |
| A16 | 回滚 | DOC_STORE_ENABLED=false 后业务/测试零影响 |
| A17 | 红线 | 无 .vtj 模板改动、无 /api/v1 路径变化 |
| A18 | 报告 | 交付报告含证据/限制/回滚 |

## 13. 测试计划

- 单测：local 原子写、路径安全、版本、超限、损坏文件；mongo 缺失依赖映射；JSON-LD 生成。
- 集成：sqlite 内存库 + 临时 docs 根；Outbox emit→Dispatcher.run_once→文档出现。
- 故障：DocumentStore.upsert 抛错→attempts 增加；停止后恢复→补写；业务行仍存在。
- 回填：dry-run 不写；apply 幂等；limit/collection 过滤。
- 对账：删除一份文档→missing=1；多写一份→orphan=1；改字段→mismatch=1。
- 回归：全量后端 pytest、前端 npm run test:unit、npm run typecheck、gate_all。
- 真实 Mongo：默认跳过；用户安装并设置 DOC_STORE_MONGO_URI 后运行 smoke，报告如实标注是否执行。

## 14. 风险与回滚

| 风险 | 影响 | 缓解 |
|---|---|---|
| 导入快照含 3.4 MB preview_data | 文档体积大 | 8 MiB 上限；本地单文件；不复制题目正文 |
| Mongo 未安装 | mongo 后端不可用 | 默认 local；pymongo 可选；不可用明确失败 |
| 事件积压 | 文档滞后 | 对账报告 lag；Dispatcher 重试；不影响业务 |
| 文档写失败导致事件 dead | 投影缺失 | dead letter + 回填脚本可重建 |
| 业务层误直接写文档 | 双写不一致 | L7-19/评审/grep；只暴露 projection 写方法 |
| 回填覆盖新文档 | 数据倒退 | version 单调；回填 version=1 不覆盖高版本 |

回滚：DOC_STORE_ENABLED=false 立即停写；删除 backend/data/foundation/docs 可全量重建；不改 SoT、不改 API、不改表结构。

## 15. 工作量与提交

- 预计 4 个工作日（比架构原文 2 天多，因新增 Outbox 事件接入与双读/对账）。
- 文件预计 30–36 个（新增 15–18，修改 12–15）。
- 提交：main 单提交 feat(foundation): F4 文档投影与 DocumentStore；tag foundation-v1-f4；不 push。
- 交付报告：docs/superpowers/specs/F4文档投影与DocumentStore_报告_20261027.md。

## 16. 批准记录

用户已于 2026-10-27 批准 D1–D9，Step 0–8 按本计划执行完毕。

## 17. 执行记录（2026-10-27）

### 17.1 结果

- Step 0–8 全部执行；D1–D9 未偏离。
- 新增 18 个文件（含计划与报告）、修改 15 个文件（含架构 L7 章节同步）；无新表、无迁移、无新依赖、无 .vtj 模板改动。
- 文档回填 1675 条：exam_resources 38、import_snapshots 1632、forum_contents 5；二次 apply 全 0。
- 全量对账 run_id=e51a7408f9c44eb9：checked 1675、missing 0、mismatched 0、orphan 0。
- 双读抽样 500 条：mismatch 0、error 0。
- L7 19 项：18 PASS / 1 既有 WARN / 0 FAIL。
- 后端全量 789 passed / 4 skipped / 2 xfailed；前端 354 passed、typecheck 0。

### 17.2 与计划的差异

1. 事件 payload 只带聚合标识（source_table/import_id、paper_id、post_id），未实现 §6.1 的 status/action 字段与 dedupe_key。幂等改由 foundation_inbox claim + 文档 version 保证；同一聚合连续事件会各写一次，最终内容正确。
2. 新增 tests/test_batch_parsed_import.py 与 tests/test_gate_l3.py 的临时库建表步骤：F4 起导入事务会写 foundation_outbox，旧 fixture 只有业务表会报 no such table。
3. 未实现独立 document_read 内部函数；现有读路径零改动，双读由 document_shadow 直接调用 schema builder，等价满足 D4。

### 17.3 已知限制

- 未安装/未冒烟真实 MongoDB；Mongo 适配器只经缺 URI 单测与代码评审。
- A5/A6 为服务级覆盖，未做真实 HTTP 导入 + 文档库故障注入 + Dispatcher 重启端到端。
- A7/A8 以 schema/projection 单测与调用点接入为准，未逐条跑三端 UI。

### 17.4 回滚

- DOC_STORE_ENABLED=false 停写；删除 backend/data/foundation/docs 可重建；无表/迁移/依赖回滚。
- 代码回滚为单提交 revert。

### 17.5 交付物

- 报告：docs/superpowers/specs/F4文档投影与DocumentStore_报告_20261027.md
- 配置：DOC_STORE_ENABLED/BACKEND/ROOT/MAX_BYTES/MONGO_*/RECONCILE_MAX_AGE_DAYS
- 运维脚本：backfill_documents.py、document_inventory.py、document_shadow_sample.py

