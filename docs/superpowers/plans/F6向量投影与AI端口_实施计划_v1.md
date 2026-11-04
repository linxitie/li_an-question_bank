# F6 向量投影与 AI 端口实施计划 v1

> 状态：✅ 已执行（2026-10-28，Step 0–8 完成，tag `foundation-v1-f6`）
> 执行结果：见 docs/superpowers/specs/F6向量投影与AI端口_报告_20261028.md
> 依据：docs/superpowers/specs/砺安题库终态总体架构_v2.0.md §5.1/§5.3/§9.7/§13/§17
> 前置：F1 一致性内核、F2b 事件总线、F4 文档投影、F5 图投影均已完成（tag foundation-v1-f1/f2b1/f2b2/f4/f5）
> 基线：main 1df2c1c（F5 完成，工作树干净）；执行时 main 1df2c1c（F5 完成）
> 计划日期：2026-10-28

## 0. 背景

终态架构把存储分为「1 个事实源 + 4 类可重建投影」。F1/F2b 已完成一致性内核与事件同事务化，F3/F4/F5 已完成对象、文档、图三类投影。F6 是四类投影中的最后一块：向量投影，以及一个可替换的 Embedding 端口。

F6 只做最小闭环：把题目文本转成向量，写入可重建的 VectorStore，提供一个内部检索函数。它不接业务页面、不新增 HTTP API、不改变现有读路径、不把向量库当第二事实源。向量索引随时可由 question_bank 与 Embedding 端口重建。

F6 的难点不在存储，而在「没有模型就没有语义向量」。因此本计划把 Embedding 端口做成显式开关：默认关闭；提供确定性的 hash 提供者只用于离线验证与测试，并在健康信息和报告中标记 degraded；真实语义检索必须由用户提供 OpenAI 兼容的 embeddings 服务地址。系统不会在缺少模型时静默生成伪语义向量。

## 1. 实测基线（2026-10-28，只读）

| 项 | 实测值 |
|---|---|
| 生产库 | backend/data/question_bank.db（SQLite WAL） |
| question_bank | 3357 行 |
| question_content 非空 | 3357 行；总长 311749 字符，均长 92.87 |
| status=1（可见） | 3122 行 |
| status=0（隐藏） | 235 行 |
| 预期 text_questions | 3122 条（status=1 且题干非空） |
| question_bank 可用列 | question_id、subject_id、type_id、question_content、options、answer、answer_analysis、point_id、difficulty、score、status |
| 现有 VectorStore | 仅架构协议，无实现；无向量文件；无向量表 |
| 现有 EmbeddingPort | 不存在 |
| 现有 L7 | 20 项，PASS=19 WARN=1 FAIL=0（唯一 WARN 为既有 L7-10 空库审计） |
| 现有迁移 | 001 foundation 7 表、002 media_assets、003 graph projection；F6 不需要新迁移 |
| 本机 Python 包 | numpy 已安装；httpx 已安装；pymilvus 未安装；pymongo/neo4j 不参与 F6 |
| 本机 Docker | Docker CLI 存在，但 2026-10-28 实测 daemon 未运行；19530/9091 未监听；因此当前无法验证 Milvus |
| 用户环境 | 用户已在 Docker 中配置 milvusdb；实施时若 daemon 或 19530 仍不可达，真实 Milvus 冒烟按「未执行」记录 |

结论：F6 的 local 验收完全不依赖容器；Milvus 适配器同批实现，真实冒烟依赖用户启动 milvusdb 并允许安装可选 pymilvus。Embedding 的真实语义验收依赖用户提供模型服务地址；没有模型时只做 hash 确定性验证，不冒充语义检索。

## 2. 目标与非目标

### 2.1 目标

1. 新增 VectorStore 协议、local 实现与 Milvus 适配器；默认关闭（VECTOR_BACKEND=off），local/milvus 显式开启。
2. 新增 EmbeddingPort：off / hash / http 三种提供者；http 走 OpenAI 兼容 /v1/embeddings；hash 只用于离线验证。
3. 只投影一个集合 text_questions：status=1 且题干非空的题目，id 为 question_id 字符串，meta 保留 subjectId/typeId/pointId/difficulty/status/contentHash。
4. local 使用 .npy + ids.json + meta.json 文件，余弦 top-k，支持等值/集合过滤；不新增数据库表、不新增迁移。
5. Milvus 使用可选 pymilvus，集合 li_an_text_questions，FLOAT_VECTOR + JSON meta + COSINE；不可用时明确报错，不回落 local。
6. 提供离线回填脚本：默认 dry-run，--apply 才写，--reset 可全量重建，重复执行幂等。
7. 提供对账、盘点与 local/Milvus top-k 一致性脚本；对账写 foundation_reconcile_run(scope=vector) 与 JSON 报告。
8. 提供内部检索函数 search_questions，返回 top-k 命中；不注册 FastAPI 路由、不接业务页面。
9. /health/foundation 增加 vector 段；L7 20→21。
10. 所有开关关闭时，现有业务、API、.vtj 页面零影响。

### 2.2 非目标

- 不新增 HTTP API，不接学生/教师/管理端任何页面，不改 .vtj 模板、路由、API 出入参。
- 不改变 SQLite schema，不新增向量表，不新增迁移。
- 不做 image_questions、knowledge_chunks、user_mistakes 集合；F6 只做 text_questions，其余留给后续批次。
- 不做增量事件投影：题目导入/修改没有稳定的题目级 Outbox 事件；F6 采用「回填 + 可重复重建」，不伪装实时同步。
- 不下载或内置 embedding 模型；不把 hash 向量当语义向量用于生产检索。
- 不做 RAG 问答、Agent、重排、混合检索、向量压缩或索引调参。
- 不修改现有题目读接口的排序或推荐结果。
- 不要求本机 Milvus 必须运行；真实 Milvus 冒烟属可选验证，未执行必须在报告中标注。
- 不把 pymilvus 写入必需依赖；它只作为 milvus 后端的可选依赖。

## 3. 待批准决策 D1–D9

| # | 决策 | 推荐 | 备选/影响 |
|---|---|---|---|
| D1 | 默认关闭：VECTOR_BACKEND=off、EMBEDDING_ENABLED=false；local 零依赖，milvus 显式开启 | ✅ | 默认 local 会让开发机悄悄多出索引文件；默认 milvus 会逼用户先起容器。关闭最符合架构 §5.3 |
| D2 | F6 只做 text_questions 一个集合；只索引 status=1 且题干非空，预期 3122 条；其余集合后续批次 | ✅ | 一次做四个集合会扩大口径与验收面，且图片/知识点分块/错题尚无统一文本契约 |
| D3 | EmbeddingPort 支持 off/hash/http；hash 为确定性字符 n-gram，明确 degraded，只用于测试与离线验证；http 为 OpenAI 兼容 /v1/embeddings，需用户提供地址/模型/密钥 | ✅ | 只做 http 会让无模型环境无法验收；只做 hash 会制造伪语义检索 |
| D4 | local 使用 backend/data/foundation/vectors/<collection>.npy + ids.json + meta.json；L2 归一化后点积即余弦；原子替换；不建表 | ✅ | 存 JSON 会膨胀十倍；存 SQLite 会新增表且违背架构的可重建文件投影 |
| D5 | Milvus 适配器使用可选 pymilvus；集合 li_an_text_questions，COSINE + FLOAT_VECTOR + JSON meta；缺失依赖/连接失败抛 VectorStoreUnavailable，不回落 local | ✅ | 用 httpx 调 Milvus REST 可零依赖，但版本/负载格式风险更高；pymilvus 是官方 SDK，真实环境更稳 |
| D6 | 回填默认 dry-run；--apply 才写；--reset 先清空；生产语义索引必须配置真实 http embedding；无模型时只用独立临时根 + hash 做验证，不写生产索引 | ✅ | 直接写生产 hash 索引会让后续误以为检索可用；不写任何索引又无法验证闭环 |
| D7 | 对账/盘点/一致性三个脚本：scope=vector；7 天新鲜度；local 与 Milvus 抽样 100 个 query 的 top-10 重合≥95% | ✅ | 只对账 ID 数量无法发现向量/排序错误；只做一致性不做对账无法发现缺题/孤儿 |
| D8 | L7 20→21：协议/local/Milvus/Embedding/回填/对账文件缺失或 local 不可用 FAIL；milvus 不可用、对账过期、drift/孤儿 WARN；关闭时 PASS disabled | ✅ | 全部 WARN 会失去门禁意义；关闭时 FAIL 会阻断默认开发环境 |
| D9 | main 单提交 + tag foundation-v1-f6；预计 3 个工作日；不改 .vtj/API/业务表/迁移 | ✅ | 超过 40 文件再开短分支；F6 文件预计 20–26 个 |

## 4. 向量模型契约

### 4.1 集合与文档

逻辑集合名：text_questions。Milvus 物理名：li_an_text_questions（VECTOR_MILVUS_PREFIX 默认 li_an_）。

| 项 | 契约 |
|---|---|
| id | str(question_id)，Milvus VARCHAR(64) 主键；local ids.json 中同为字符串 |
| text | question_content，去除首尾空白；空串不索引 |
| vector | float32，长度 VECTOR_DIM；写入前 L2 归一化；零向量/NaN/Inf 拒绝 |
| meta.subjectId | question_bank.subject_id |
| meta.typeId | question_bank.type_id |
| meta.pointId | question_bank.point_id |
| meta.difficulty | question_bank.difficulty |
| meta.status | 固定 1（只索引可见题） |
| meta.contentHash | sha256(question_content)[:16]，用于对账发现题干变化 |
| 过滤 | where 为字段到标量或标量列表的映射，AND 语义；只支持 meta 字段等值/IN，不支持范围/模糊/逻辑或 |

### 4.2 检索语义

- 相似度统一为余弦；local 用归一化向量点积；Milvus 用 COSINE。
- top_k 默认 10，最大 100；非法值拒绝。
- 排序：score 降序；同分按 id 升序稳定排序。
- where 为空表示不过滤；过滤在打分之后、取 top-k 之前生效。
- 返回 VectorHit(id, score, meta)；不返回题干正文，避免把向量库变成第二正文源。
- 检索函数是内部函数；没有 HTTP 路由；不修改任何业务接口。

## 5. VectorStore 协议与实现

### 5.1 协议

    class VectorStore(Protocol):
        backend: str
        dim: int
        def upsert(self, collection: str, id: str, vector: list[float],
                   meta: dict) -> None: ...
        def upsert_many(self, collection: str,
                        items: list[VectorItem]) -> int: ...
        def search(self, collection: str, vector: list[float],
                   top_k: int = 10, where: dict | None = None) -> list[VectorHit]: ...
        def fetch(self, collection: str, ids: list[str]) -> dict[str, dict]: ...
        def list_ids(self, collection: str, limit: int | None = None) -> list[str]: ...
        def delete(self, collection: str, id: str) -> bool: ...
        def delete_many(self, collection: str, ids: list[str]) -> int: ...
        def count(self, collection: str) -> int: ...
        def clear(self, collection: str) -> None: ...
        def health(self) -> VectorHealth: ...

异常：VectorStoreError / VectorStoreUnavailable / VectorStoreCorrupt / InvalidVectorTarget。

集合名白名单：text_questions；后续批次扩展时再增加。集合名必须匹配 [a-z][a-z0-9_]{0,63}，防止路径穿越。向量维度必须与 store.dim 一致；不一致抛 InvalidVectorTarget 或 VectorStoreCorrupt。

### 5.2 local 实现

文件布局（backend/data/foundation/vectors/）：

    text_questions.npy       float32 N x D，已 L2 归一化
    text_questions.ids.json  ["1","2",...]，与 npy 行一一对应
    text_questions.meta.json {"1": {...}, ...}

写入：

- 读取现有三文件；按 id 合并；重复 id 以本次写入为准；新 id 追加。
- 校验每行维度、有限值、非零；批量内先去重。
- 写入顺序：meta 临时文件 → ids 临时文件 → npy 临时文件；每个临时文件 fsync 后 os.replace。npy 最后替换，失败时 ids/meta 可能领先，下一次 health 会报长度不一致，重建即可。
- 进程内使用 threading.RLock 串行化写；文档明确单写者：同一集合不要同时跑两个回填进程。
- 搜索读时按 manifest 长度校验；不一致抛 VectorStoreCorrupt，不静默截断。
- 空集合返回空列表；缺失文件视为空集合，不创建目录直到第一次写入。
- health：根目录不可写、文件损坏、维度不一致 → degraded/ok=false；空集合 → ok=true count=0。

搜索：

- 读 npy/ids/meta；矩阵与查询向量都已是单位向量，scores = matrix @ q。
- where 先构造布尔掩码；候选按 (-score, id) 排序；取前 top_k。
- 返回 meta 的浅拷贝，避免调用方修改缓存。

删除/清空：

- delete_many 从三文件同步移除；clear 删除该集合三个文件；不触碰其他集合。
- 不做软删除；向量投影可重建。

### 5.3 Milvus 实现（可选）

- 依赖：pymilvus>=2.4,<3，仅 milvus 后端需要；不写入 requirements 的必需段，只在可选段注释说明。缺失时 build_vector_store("milvus") 抛 VectorStoreUnavailable。
- 连接：MilvusClient(uri=VECTOR_MILVUS_URI, token=VECTOR_MILVUS_TOKEN)；token 为空表示无鉴权；不得把 token 写入日志/健康输出。
- 集合 schema：
    id      VARCHAR(64), primary, auto_id=false
    vector  FLOAT_VECTOR, dim=VECTOR_DIM
    meta    JSON
- 索引：AUTOINDEX，metric_type=COSINE；创建后 load_collection。
- 已存在集合：describe_collection 校验向量维度；不一致抛 VectorStoreCorrupt，不自动重建。
- upsert_many：每批 500；pymilvus upsert 保证同主键覆盖；写入前统一归一化。
- search：data=[query]，annsField=vector，limit=top_k，output_fields=["meta"]，search_params={"metric_type":"COSINE"}；where 转 Milvus 过滤表达式。
- where 转换：只允许 meta 字段名白名单；标量用 meta["field"] == value；列表用 meta["field"] in [v1,v2]；字符串值转义双引号和反斜杠；拒绝控制字符。
- fetch：按 id in [...] 查询 id/meta；list_ids：优先 query_iterator 分批枚举，兼容 pymilvus 2.4+；count：get_collection_stats 的 row_count。
- delete：按 id in [...] 删除；clear：drop_collection 后不自动重建，下一次 upsert 重建。
- health：list_collections 超时 3 秒；集合不存在视为 ok=true、count=0；连接/鉴权失败返回 ok=false/degraded=true，不抛到健康接口。
- 错误映射：连接、超时、鉴权 → VectorStoreUnavailable；维度/集合 schema 不符 → VectorStoreCorrupt；非法 id/where → InvalidVectorTarget。

### 5.4 工厂与开关

- build_vector_store(backend=None)：off → 抛 VectorStoreUnavailable("vector store disabled")；local → LocalVectorStore；milvus → MilvusVectorStore；未知后端 → 配置错误。
- reset_vector_store() 清进程内单例，供测试使用。
- VECTOR_STORE_ENABLED=false 时，工厂、回填、检索全部短路；VECTOR_BACKEND=off 等价。
- 远端不可用不回落 local；调用方必须显式处理异常。

## 6. EmbeddingPort

### 6.1 协议

    class EmbeddingPort(Protocol):
        provider: str
        dim: int
        degraded: bool
        def embed(self, texts: Sequence[str]) -> list[list[float]]: ...

异常：EmbeddingError / EmbeddingUnavailable / EmbeddingDimensionMismatch。

### 6.2 off

- EMBEDDING_ENABLED=false 或 EMBEDDING_PROVIDER=off：build_embedding_port 抛 EmbeddingUnavailable。
- 回填在 --apply 前先构建端口；未配置时直接失败并提示需要设置 EMBEDDING_PROVIDER 与地址，不写任何文件。

### 6.3 hash（仅验证/测试）

- 确定性字符 n-gram 哈希：对文本的 1/2/3 字符片段做 blake2b，映射到 VECTOR_DIM 个桶，带符号累加，最后 L2 归一化。
- 同一文本跨进程/跨平台稳定；不依赖 Python hash 随机种子。
- provider="hash"、degraded=true；health 与报告必须显示 degraded=true。
- 不得用于生产语义检索；F6 的生产路径只接受 http。

### 6.4 http（真实语义）

- OpenAI 兼容：POST {EMBEDDING_BASE_URL}/embeddings，Body 为 {"model": ..., "input": [...], "encoding_format": "float"}；有 key 时加 Authorization: Bearer。
- 按 EMBEDDING_BATCH_SIZE 分批（默认 32）；响应 data 按 index 排序；每个向量长度必须等于 VECTOR_DIM，否则 EmbeddingDimensionMismatch。
- 超时 EMBEDDING_TIMEOUT_SECONDS（默认 30）；429/5xx/网络错误 → EmbeddingUnavailable（可重试）；400/401/403 → EmbeddingError（配置或凭据错误，不重试）。
- 不记录 API key、完整请求头或题干全文到日志；错误信息只保留状态码与简短原因。
- base_url 约定包含 /v1，例如 http://127.0.0.1:8000/v1；脚本不自动探测模型。

### 6.5 工厂

- build_embedding_port(provider=None)：读 EMBEDDING_PROVIDER；off 抛不可用；hash 构造 HashEmbedding(VECTOR_DIM)；http 校验 BASE_URL/MODEL 后构造 HttpEmbedding。
- embedding_health() 只返回配置态（provider/enabled/dim/degraded），不发网络请求；健康接口不因模型服务慢而阻塞。

## 7. 回填、对账、一致性与检索

### 7.1 文档生成

backend/app/foundation/vector_builder.py：

    QUESTION_QUERY = text(
        "SELECT question_id, subject_id, type_id, question_content, point_id, "
        "difficulty, status FROM question_bank "
        "WHERE status=1 AND question_content IS NOT NULL "
        "AND TRIM(question_content) <> '' ORDER BY question_id"
    )

- build_vector_docs(session, limit=None) -> list[VectorDoc]；VectorDoc 含 id/text/meta。
- contentHash = sha256(text.encode("utf-8")).hexdigest()[:16]。
- limit 为正整数或 None；校验与 F5 一致。
- apply_docs(store, embedder, docs, batch_size=64, reset=False) -> dict：分批 embed、校验维度、upsert_many；返回 planned/embedded/written/failed。
- 单条空文本跳过；单条维度错误计入 failed 并继续；embedding 网络错误直接抛出，避免把半批坏数据写成成功。

### 7.2 回填脚本

backend/scripts/foundation/backfill_vectors.py：

- 默认 dry-run：只查 SoT 计数与样例，不调用 embedding、不写文件；输出 collection、planned、status=1 计数、样例 id。
- --apply：构建 embedding 与 vector store，按批写入；默认 upsert，不先清空。
- --reset：先 clear 再写；与 --apply 同时使用才生效。
- --collection text_questions（默认）；--limit N；--batch N（默认 64）；--backend local|milvus|auto；--provider hash|http|auto。
- --provider hash 必须显式指定，输出 warning：degraded 向量，仅供验证。
- 输出 planned/embedded/written/failed/skipped、backend、collection、dim、provider；失败退出码 1。
- 幂等：连续两次 --apply，第二次 count 不变；内容 hash 未变的题目仍会重写向量（Embedding 可能变化），这是预期。
- --reset 后的全量重建结果必须与 SoT 预期条数一致。

### 7.3 对账

backend/app/foundation/vector_reconcile.py：

- expected：build_vector_docs 的 id 与 contentHash；actual：store.list_ids + fetch 抽样 meta。
- 统计 expected_count、actual_count、missing、orphan、stale、checked、sample；stale 指 contentHash 不一致。
- inspect(session, store, collection, limit=None, sample=100) -> VectorReconcileResult；默认抽样 100 个 id 比对 hash，--full 时全量 fetch。
- record(session, run) 写 foundation_reconcile_run(scope=vector)；latest_run(session)；freshness_days(latest, now=None)。
- 报告写入 backend/data/reports/reconcile/vector_<run_id>.json；drift 时 status=drift；枚举失败 status=warn 并记录原因。
- 对账不自动修复、不删除孤儿；修复用 --reset 重建。

backend/scripts/audit/vector_inventory.py：

- 默认只读：输出 expected/actual/missing/orphan/stale、backend、collection、dim、sample。
- --full 全量比对 hash；--record 写 foundation_reconcile_run；drift 退出码 1。
- 不写向量，不写业务表。

### 7.4 local/Milvus 一致性

backend/scripts/audit/vector_parity.py：

- 从 SoT 取 N 道可见题（默认 100），用同一 embedding 端口生成 query 向量。
- 同一 query 分别向 local 与 milvus 请求 top_k（默认 10），比较 id 集合重合数。
- 单 query 重合 ≥9/10 记为一致；一致 query 占比 ≥95% 为 PASS。
- 输出每个 query 的重合数、一致率、平均重合、失败样例；报告写 backend/data/reports/reconcile/vector_parity_<ts>.json。
- 需要 local 与 milvus 都已有同一批向量；没有 Milvus 时退出码 2 并明确提示未执行，不伪造 PASS。

### 7.5 检索函数

backend/app/foundation/retrieval.py：

    def search_questions(query: str, top_k: int = 10,
                         filters: dict | None = None, *,
                         collection: str | None = None,
                         store: VectorStore | None = None,
                         embedder: EmbeddingPort | None = None) -> list[VectorHit]

- 校验 query 非空、top_k 1..VECTOR_SEARCH_TOP_K_MAX；filters 走 where 契约。
- 默认 collection=VECTOR_COLLECTION；默认 store/embedder 由工厂构造。
- 向量库关闭、embedding 关闭、远端不可用 → 抛对应异常；不返回空列表冒充成功。
- 只做内部函数；不注册路由，不在 main.py 暴露。

## 8. 健康检查与 L7

### 8.1 /health/foundation

增加 vector 段：

    vector: {
      enabled, backend, collection, dim,
      ok, degraded, count, collection_exists,
      embedding_enabled, embedding_provider, embedding_degraded,
      last_reconcile_at, drift, detail
    }

- VECTOR_STORE_ENABLED=false 或 VECTOR_BACKEND=off：enabled=false；不构造 store，不报错。
- store.health() 失败：ok=false、degraded=true，detail 只写简短原因。
- 不返回 Milvus token、API key、base_url 凭据。
- embedding_health 只读配置，不发请求；hash 时 degraded=true。

### 8.2 L7-21

- 文档头 20→21；严重度说明增加第 21 条。
- 必需文件与关键符号：
    app/foundation/stores/vector.py（VectorStore、build_vector_store）
    app/foundation/stores/local_vector.py（LocalVectorStore）
    app/foundation/stores/milvus_vector.py（MilvusVectorStore）
    app/foundation/ports/ai.py（EmbeddingPort、build_embedding_port）
    app/foundation/vector_builder.py（build_vector_docs、apply_docs）
    app/foundation/vector_reconcile.py（inspect、SCOPE = "vector"）
    app/foundation/retrieval.py（search_questions）
    app/foundation/config.py（VECTOR_BACKEND、EMBEDDING_PROVIDER）
- 缺失 → FAIL。
- VECTOR_BACKEND=local 且 local health 不可用 → FAIL；VECTOR_BACKEND=milvus 且不可用 → WARN。
- 无对账记录、超过 VECTOR_RECONCILE_MAX_AGE_DAYS、status=drift、报告 orphan>0 → WARN。
- VECTOR_BACKEND=off → PASS，detail=disabled；仍检查文件/符号存在。
- 不检查迁移/表，因为 F6 不新增表。
- 架构 §11.2 增加第 21 行，检查范围改为 6–21；README 同步。

## 9. 文件清单

新增（预计 18–22 个）：

- backend/app/foundation/ports/__init__.py
- backend/app/foundation/ports/ai.py
- backend/app/foundation/stores/vector.py
- backend/app/foundation/stores/local_vector.py
- backend/app/foundation/stores/milvus_vector.py
- backend/app/foundation/vector_builder.py
- backend/app/foundation/vector_reconcile.py
- backend/app/foundation/retrieval.py
- backend/scripts/foundation/backfill_vectors.py
- backend/scripts/audit/vector_inventory.py
- backend/scripts/audit/vector_parity.py
- backend/tests/test_vector_store_local.py
- backend/tests/test_vector_store_milvus.py
- backend/tests/test_embedding_port.py
- backend/tests/test_vector_backfill.py
- backend/tests/test_vector_reconcile.py
- backend/tests/test_vector_retrieval.py

修改：

- backend/app/foundation/config.py（VECTOR_*/EMBEDDING_* 键）
- backend/app/core/config.py（同名 Settings 键）
- backend/app/foundation/health.py（vector 段）
- backend/requirements.txt（pymilvus 仅可选注释，不加入必需安装）
- backend/scripts/gates/gate_l7_foundation.py（L7-21）
- docs/README.md（F6 计划索引/变更记录）
- docs/superpowers/specs/砺安题库终态总体架构_v2.0.md（§11.2 第 21 行）
- docs/ops/外部数据库与中间件手动下载清单_v1.md（补 Milvus/pymilvus 实测与自检）

不改：.vtj/*、src/*、src/router/index.ts、backend/migrations/*、backend/app/models/*、任何 /api/v1 路径。

## 10. Step 0–8

| Step | 内容 | 验证 | 回滚 |
|---|---|---|---|
| 0 | 基线：工作树干净；记录 SoT 3122；L7 20 项；F5 测试通过 | 全绿/仅既有 WARN | 无改动 |
| 1 | 配置键 + EmbeddingPort（off/hash/http）+ 单测 | hash 确定性、维度校验、HTTP 错误映射 | 删新增文件 |
| 2 | VectorStore 协议 + local 实现 + 单测 | upsert/search/filter/delete/clear/health/原子写 | 删 vectors 目录 |
| 3 | Milvus 适配器 + fake client 测试 | schema/搜索/过滤/维度/错误映射；无真实 Milvus 也可测 | 默认 off，不影响 |
| 4 | vector_builder + 回填脚本 | dry-run 不写；apply 计数 3122；二次 apply 幂等；--reset 重建 | 删索引文件/集合 |
| 5 | 对账 + 盘点 + 一致性脚本 | 人为删/改一条可检出 missing/stale；drift=0；parity 抽样 | 只读脚本，无副作用 |
| 6 | retrieval + health | 检索 top-k 预期；/health/foundation 有 vector 段 | 关开关 |
| 7 | L7-21 + 架构/README/下载清单 | L7 20→21；文档同步 | 回退门禁 |
| 8 | 全量验收 + 报告 + 提交/tag | A1–A16；后端全量、前端 unit/typecheck、gate_all | 关开关/删索引 |

## 11. 验收 A1–A16

| # | 验收 | 判定 |
|---|---|---|
| A1 | local upsert/search/fetch/list/delete/clear/health | 全部通过 |
| A2 | local 余弦 top-k 与排序稳定 | 手算样例一致；同分按 id 升序 |
| A3 | where 等值/集合过滤 | 过滤后只含命中 meta 的 id |
| A4 | 维度/零向量/NaN/非法集合名 | 明确拒绝，不写入坏数据 |
| A5 | hash embedding 确定性 | 同文本跨实例向量完全一致；L2 范数≈1 |
| A6 | http embedding 契约 | fake server 校验路径/鉴权/批次/维度/错误映射 |
| A7 | Milvus fake client | schema/upsert/search/filter/delete/health 映射正确 |
| A8 | 生产 SoT 回填（独立验证根） | planned=3122；hash 验证 written=3122；不写生产语义索引 |
| A9 | 回填幂等与重建 | 二次 apply count 不变；--reset 后 count=3122 |
| A10 | 对账 drift=0 | 全量 inventory status=ok；人为删/改可检出 |
| A11 | local/Milvus 一致性 | 若 Milvus 可用：100 query top-10 重合≥95%；不可用则在报告标注未执行 |
| A12 | retrieval | 返回 top-k；关闭开关抛明确异常；无 HTTP 路由 |
| A13 | 开关回滚 | VECTOR_BACKEND=off / VECTOR_STORE_ENABLED=false / EMBEDDING_ENABLED=false 业务零影响 |
| A14 | L7-21 | PASS；Milvus 缺失仅 WARN；关闭时 PASS disabled |
| A15 | 回归 | 后端全量无新增失败；前端 unit/typecheck 0；gate_all 无新增失败 |
| A16 | 报告 | 交付报告含证据、偏差、限制、回滚 |

## 12. 测试计划

- 单测 local：空集合、首次写入、追加、覆盖、删除、清空、维度不一致、零向量、NaN、非法集合名、损坏文件 health。
- 单测 local 搜索：余弦排序、top_k、where 标量/列表、空过滤、同分稳定。
- 单测 Embedding：hash 稳定/归一化/批量；http fake server 的成功、分批、排序、维度错误、401/429/500、超时；off 抛不可用。
- 单测 Milvus：fake client 记录 create/describe/upsert/search/query/delete/drop 调用；校验 COSINE、output_fields、过滤表达式、维度不匹配、连接异常映射；monkeypatch 缺 pymilvus。
- 回填：dry-run 不写；apply 3122；二次幂等；reset；limit；空题干跳过；contentHash 变化。
- 对账：missing/orphan/stale；record/latest/freshness；报告 JSON。
- 检索：hash + local 的固定 top-k；filters；关闭开关异常；无 FastAPI 路由。
- 一致性：fake local/milvus 同向量时 100 query 重合；Milvus 不可用时退出码 2。
- 回归：全量后端 pytest、前端 npm run test:unit、npm run typecheck、gate_all、L7。

## 13. 风险与回滚

| 风险 | 影响 | 缓解 |
|---|---|---|
| 无真实 embedding 模型 | 只能验证管道，不能验证语义质量 | 默认关闭；hash 明确 degraded；报告标注；用户提供 http 地址后重跑 |
| hash 被误当生产向量 | 检索结果无意义 | 脚本必须显式 --provider hash；health degraded=true；文档三处警示 |
| Milvus 版本/依赖不兼容 | 真实冒烟失败 | 可选 pymilvus>=2.4,<3；fake client 测试；失败不回落 local，报告标注 |
| 向量维度变更 | 旧索引不可用 | 维度写入 health/报告；不一致抛 Corrupt；重建索引，不自动迁移 |
| local 文件写入中断 | 三文件不一致 | npy 最后替换；读侧长度校验；health degraded；--reset 重建 |
| 大集合查询慢 | 检索延迟 | F6 仅 3122 条；local 超过 5 万或 1 GB 切 Milvus；top_k 上限 100 |
| 误把向量库当事实源 | 破坏 C1 | 只读检索；不存正文；无业务写入；可由 SoT 重建 |
| 远端不可达拖慢健康检查 | /health 变慢 | Milvus health 超时 3 秒；embedding health 不发请求 |

回滚：

- VECTOR_BACKEND=off 或 VECTOR_STORE_ENABLED=false，立即停用向量投影。
- 删除 backend/data/foundation/vectors 下对应文件，或 drop Milvus 集合；SoT 零改动。
- 关闭 EMBEDDING_ENABLED=false，不产生任何模型调用。
- 无数据库迁移需要回滚。

## 14. 工作量与提交

- 预计 3 个工作日（架构原文 2–3 天；多出的时间用于 Milvus 适配器、对账/一致性脚本与 L7-21）。
- 文件预计 20–26 个（新增 17，修改 8–9）。
- 提交：main 单提交 feat(foundation): F6 向量投影与 AI 端口；tag foundation-v1-f6；不 push。
- 交付报告：docs/superpowers/specs/F6向量投影与AI端口_报告_20261028.md。
- 归档：按 AGENTS.md 第 1 节更新 docs/README.md 索引与变更记录；solve_problems_files 不存在，不写旧目录。

## 15. 环境现状与前置

2026-10-28 实测：

- Docker CLI 存在，但 daemon 未运行；docker ps 报 npipe 连接失败；19530/9091 未监听。
- 用户称已在 Docker 中配置 milvusdb；实施时先复查 docker ps 与 19530。
- python 包：numpy=True、httpx=True、pymilvus=False。
- 生产库 3357 题，可见 3122 题；题干均长 92.87 字符。
- 本机无 embedding 模型服务地址；F6 默认不调用任何模型。

真实 Milvus 冒烟前置（可选）：

    docker ps --filter name=milvus
    curl http://127.0.0.1:19530/v2/vectordb/collections/list

若使用 milvus 后端，需要用户批准安装可选依赖：

    python -m pip install "pymilvus>=2.4,<3"

环境变量示例（密钥只由用户填写，不写入文档/代码/提交）：

    VECTOR_STORE_ENABLED=true
    VECTOR_BACKEND=milvus
    VECTOR_DIM=1024
    VECTOR_MILVUS_URI=http://127.0.0.1:19530
    VECTOR_MILVUS_TOKEN=<用户自定>
    EMBEDDING_ENABLED=true
    EMBEDDING_PROVIDER=http
    EMBEDDING_BASE_URL=<OpenAI 兼容 /v1 地址>
    EMBEDDING_MODEL=<模型名>
    EMBEDDING_API_KEY=<用户自定>

若用户暂不提供 embeddings 服务，F6 仍可按 local + hash 完成管道验证；报告明确写「语义检索未验证，生产索引未写入」。

## 16. 批准记录

- 待用户批准 D1–D9。
- 批准后从 Step 0 开始；未批准不改代码、不建表、不安装依赖。
