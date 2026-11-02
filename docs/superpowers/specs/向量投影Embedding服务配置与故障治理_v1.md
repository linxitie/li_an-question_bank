# 向量投影 Embedding 服务配置与故障治理 方案 v1

- 日期：2026-11-02
- 触发：合作同伴按 `EMBEDDING_BASE_URL=https://api.deepseek.com/v1` + `EMBEDDING_MODEL=deepseek-embedding` 配置后，回填/检索报
  `embedding_error EmbeddingError embeddings 请求被拒绝: HTTP 404`
- 结论：**配置确实读到了，但 DeepSeek 官方不提供 `/embeddings` 接口**，把对话模型的服务地址当成了向量服务地址。DeepSeek 只有 chat 能力，没有 embedding 模型（模型清单里也没有 `deepseek-embedding`）。

## 1. 证据（本机实测，2026-11-02）

| 探测 | 结果 |
|---|---|
| `POST https://api.deepseek.com/v1/embeddings`（有效 key，model=deepseek-embedding） | **HTTP 404** |
| `GET https://api.deepseek.com/models` | 仅 `["deepseek-flash","deepseek-v4-pro"]`，无任何 embedding 模型 |
| 错误文案来源 | `backend/app/foundation/ports/ai.py:171` `raise EmbeddingError(f"embeddings 请求被拒绝: HTTP {response.status_code} ...")`；`embedding_error` 前缀由调用方（回填脚本/上层封装）添加 |
| 端点拼接 | `HttpEmbedding.endpoint` = `base_url.rstrip("/") + "/embeddings"`（`backend/app/foundation/ports/ai.py:137-140`），因此 `https://api.deepseek.com/v1` → `https://api.deepseek.com/v1/embeddings` |
| 维度校验 | `backend/app/foundation/stores/vector.py:119-123` `normalize_vector`：`len(vector) != dim` 直接抛 `InvalidVectorTarget` |

所以这不是「配置没生效」，而是**配置本身指向了一个不存在的接口**；DeepSeek 的 key 对 embedding 没有任何用处。

## 2. 可选方案（按优先级）

| 方案 | 适用 | 配置要点 | 备注 |
|---|---|---|---|
| **A. 硅基流动 SiliconFlow（推荐，国内直连）** | 想尽快跑通、有免费额度 | `https://api.siliconflow.cn/v1` + `BAAI/bge-m3`（原生 1024 维） | OpenAI 兼容 `/v1/embeddings`；中文效果好 |
| B. 阿里云百炼 DashScope 兼容模式 | 已有阿里云账号 | `https://dashscope.aliyuncs.com/compatible-mode/v1` + `text-embedding-v3`（默认 1024） | 需开通百炼并创建 API-KEY |
| C. 智谱 BigModel | 已有智谱账号 | `https://open.bigmodel.cn/api/paas/v4` + `embedding-3`（2048/1024/512） | 维度需与 `EMBEDDING_DIM` 对齐 |
| **D. 本地 Ollama（离线，零费用）** | 内网/断网、不想外发题目 | `http://127.0.0.1:11434/v1` + `bge-m3`，`EMBEDDING_API_KEY=ollama`（任意占位） | 需本机 `ollama pull bge-m3`（约 1.2 GB 内存占用） |
| E. 暂停向量能力 | 暂时不做语义检索 | `EMBEDDING_ENABLED=false`、`EMBEDDING_PROVIDER=off`、`VECTOR_BACKEND=off` | 功能降级但不报错；等真实服务就绪再开 |

> 不要用「换个假的模型名让请求成功」这类做法：`EMBEDDING_DIM` 与模型真实维度不一致时，`normalize_vector` 会直接失败，或把错误向量写进索引。

## 3. 照做的配置（以方案 A 为例）

```dotenv
# backend/.env 或仓库根 .env（config.py 的 env_file 两处都读）
EMBEDDING_ENABLED=true
EMBEDDING_PROVIDER=http
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_API_KEY=sk-你自己填
EMBEDDING_DIM=1024
VECTOR_DIM=1024
EMBEDDING_TIMEOUT_SECONDS=30
EMBEDDING_BATCH_SIZE=32
VECTOR_STORE_ENABLED=true
VECTOR_BACKEND=local
```

要点：

1. `EMBEDDING_BASE_URL` 只写到 `/v1`，**不要**自己再拼 `/embeddings`（代码会拼；若已写到 `/embeddings` 也能识别并原样使用）。
2. `EMBEDDING_DIM` 必须等于模型原生维度，且 `EMBEDDING_DIM == VECTOR_DIM`。
3. 改完必须重启后端（`.env` 不触发 `--reload`）。
4. **切换 provider / 改维度后必须重建索引**，否则旧向量与新维度混存：
   ```bash
   python backend/scripts/foundation/backfill_vectors.py --apply --reset
   ```

### 3.1 三步自检（同伴可直接复制）

```bash
# ① 服务是否提供 /embeddings（应返回 data[0].embedding）
curl -s -X POST "https://api.siliconflow.cn/v1/embeddings" \
  -H "Authorization: Bearer $EMBEDDING_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"BAAI/bge-m3","input":["ping"]}' | head -c 200

# ② 本项目的端口解析是否正确（在 backend/ 下执行）
python -c "from app.foundation.ports.ai import build_embedding_port; p=build_embedding_port(); print(type(p).__name__, p.dim, getattr(p,'endpoint','-')); v=p.embed(['ping']); print('实际维度', len(v[0]))"

# ③ 索引重建（仓库根执行；默认 dry-run，--apply 才写）
python backend/scripts/foundation/backfill_vectors.py
python backend/scripts/foundation/backfill_vectors.py --apply --reset
```

## 4. 我方需要加固的 4 处（本次未实施，待批准）

| # | 改动 | 价值 |
|---|---|---|
| 1 | 新增 `backend/scripts/check_embedding.py`：打印解析后的 endpoint/model/dim，发 1 条 `ping` 探针，按 404/401/429/维度不符给出处置建议 | 同伴一条命令自证，不用猜「配置读没读到」 |
| 2 | `backend/app/foundation/ports/ai.py`：404 时文案改为「该服务未提供 `/embeddings` 接口（DeepSeek 官方不支持 embedding），请更换为 OpenAI 兼容的 embedding 服务」，并额外兼容服务端拒绝 `encoding_format` 时去掉该字段重试一次 | 错误可执行，不再误导为「配置没读到」 |
| 3 | 启动 guardrail：`EMBEDDING_PROVIDER=http` 且 `EMBEDDING_BASE_URL` 命中 `api.deepseek.com`，启动日志 WARN 并在 `/health/foundation` 的 `vector.embedding` 段返回 `ok=false, reason=provider_has_no_embeddings`（惰性探活 + 60s 缓存） | 部署即暴露，不等到回填才炸 |
| 4 | 文档：`docs/ops/向量投影与Embedding配置_v1.md`（三套可用服务的配置样例 + 维度表 + 重建步骤） | 同伴自助 |

> 另外建议（独立小改）：构建戳目前取 `HEAD`，文档提交也会让版本不一致提示冒出来；后续可改为由构建时生成的 `build-info.json` 提供，只有代码变更才改。当前保持现状，文档提交后重新 build 即可。

## 5. 验收标准

- `python backend/scripts/check_embedding.py` 返回 `ok=true`、`dim` 与 `EMBEDDING_DIM`/`VECTOR_DIM` 一致。
- `backfill_vectors.py --apply --reset` 成功且条数与 `expected_records` 一致。
- 向量检索接口返回 `distance` 合理、无 `InvalidVectorTarget`。
- `GET /health/foundation` 的 `vector.embedding` 段显示 `provider=http`、`ok=true`。

## 6. 回滚

- 配置层：`git checkout -- backend/.env`（若已纳入版本管理则改用备份），或改回 `EMBEDDING_ENABLED=false` / `VECTOR_BACKEND=off`。
- 索引层：`rm -rf backend/data/foundation/vectors`（本地后端）后重新回填；Milvus 侧删除 `li_an_text_questions` 集合。
- 代码层：本次仅为方案，未改代码；若实施后需回滚，按上述 4 处逐个还原即可（无 DB 迁移、无新表）。
