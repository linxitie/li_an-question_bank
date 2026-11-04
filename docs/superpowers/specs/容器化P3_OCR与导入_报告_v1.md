# 容器化 P3 OCR 与导入_报告_v1

> 文档性质：实施记录 / 验收报告。
> 状态：P3 已完成（2026-10-30）——parser 以非 root 的 ocr profile 启动，模型离线预热，扫描件 OCR、题图回传、文本导入不受 parser 影响、parser 停止后 backend 不崩，均已实测。
> 关联方案：`docs/superpowers/specs/容器化部署方案_v2.0.md`（§13 P3）
> 分支：`feat/teacher-administrator`；P2 提交：`dc0b4fd`
> 范围：只操作 `deploy/runtime/`、本地 staging 与 parser 镜像；不改生产库、不改业务页面。

---

## 1. 结论

P3 的目标是“把扫描件解析链容器化，并证明它不会破坏已有文本导入”。

已完成：

- parser 镜像改为非 root（uid/gid 10001），只挂 `parser_cache` 模型卷，仅连 internal 网络。
- MinerU 3.4.5 与 CPU 版 torch/torchvision 锁定；模型缓存 1.0 GB / 15 文件从宿主预热进卷，离线可解析。
- 扫描件 PDF 经 parser 返回 Markdown + base64 图片；主后端把图片落盘为 `/static/questions/*.png`，预览中的相对路径消失。
- 扫描件导入实测：`engine=mineru`，8 题，题 113 的 3 张图 `GET` 返回 200 且为真实 PNG。
- 停掉 parser 后，文本型 PDF 仍 3 秒内产出 PREVIEW 12 题，backend `/health` 保持 healthy。
- `PARSER_URL` 置空后，文本型 PDF 同样产出 PREVIEW 12 题，MinerU 健康端点返回 `available=false`，不报 500。
- 相关单测 28 passed；`gate_all.py --quick` 4/4 通过。

未完成 / 已知限制（进入 P4–P6）：

- OCR 路径的材料分组仍不完善：MinerU 输出 ASCII `(一)`、且 108/111 题号会粘在上一行选项末尾，导致扫描件复合题暂时按单题组导入（文本型 PDF 不受影响）。
- 含 Chromium 的完整生产 backend 镜像仍未在弱网下构建。
- nginx 启动时只解析一次 backend 上游 IP，backend 重建换 IP 后需重启 web。
- staging 用 `--force-recreate` 前需要显式 WAL checkpoint，否则可能丢失未检查点的 PREVIEW 记录（见 §6.3）。

---

## 2. 基线

| 项 | 实测 |
|---|---|
| 分支 / P2 提交 | `feat/teacher-administrator` / `dc0b4fd` |
| staging 入口 | `http://127.0.0.1:8080` |
| backend 镜像 | `liankao-backend:staging` / `f19b10dcc78b` / 1.8 GB |
| parser 镜像 | `liankao-parser:staging` / `ecb42c37dabd` / 3.29 GB |
| web 镜像 | `liankao-web:staging` / `8a9688108ece` / 105 MB |
| 模型卷 | `liankao-staging_parser_cache` / 约 1.0 GB / 15 文件 / 属主 10001 |
| 测试 PDF | `tmp-am2025-scan.pdf`（2 页、无文本层、639,928 B）`tmp-am2025-text.pdf`（2 页、2,204 字符文本层、364,824 B） |

测试 PDF 均取自行测真实题本 `题库/行测/安徽行测/2025年安徽省公务员录用考试《行测》题（网友回忆版）题本.pdf` 第 21–22 页；扫描件由该两页 150 dpi 渲染后重新嵌入 PDF 生成。

---

## 3. 实现

### 3.1 parser 镜像（`backend/parser/Dockerfile`）

- 基础镜像 `python:3.11-slim`；apt 默认清华源，pip 默认清华源，均带重试/超时/ForceIPv4。
- 先装 **CPU 版** `torch 2.8.0+cpu` / `torchvision 0.23.0+cpu`（阿里云 wheel 镜像），避免 Linux 默认轮子拖入 cuda-toolkit/cudnn 约 2 GB。
- `mineru[core]==3.4.5`（与宿主 `C:\mineru_env` 实测版本一致）；4.x 未验证，不跟随 latest。
- 新增 `groupadd -g 10001 parser`、`useradd -u 10001`、`USER 10001:10001`；`/home/parser/.cache` 为模型卷挂载点。
- 新增 `backend/parser/mineru.json` 并 COPY 到 `/home/parser/mineru.json`，把 `models-dir.pipeline` 固定到卷内 `OpenDataLab--PDF-Extract-Kit-1.0/snapshots/master`。没有该文件时 MinerU 会先访问 modelscope.cn 列仓库文件，而 parser 仅连 internal 网络，离线必 502。

### 3.2 sidecar 图片回传（`backend/parser/app.py`）

`POST /parse` 成功响应新增 `images`：

~~~json
{"markdown": "...![](images/<sha>.jpg)...", "images": {"<sha>.jpg": "<base64>"}}
~~~

- 只收集 MinerU 输出目录下 `images/` 的直接文件；单图 ≤ 8 MB，最多 200 张。
- 读取失败只记 warning，不影响 Markdown 返回。

### 3.3 主后端图片落盘（`backend/app/services/mineru_service.py`）

- `call_parser_http_payload(buf)` 返回完整 JSON；旧的 `call_parser_http(buf)` 保留为只取 Markdown 的兼容包装。
- `_materialize_sidecar_images(payload)`：
  - 把 base64 图片写入 `question_ingest.images._STAGING_DIR`，文件名为 `{stem}_0_0.png`；
  - stem 只接受 8–64 位十六进制，否则用 sha1 前 32 位，杜绝路径穿越；
  - 把 Markdown 的 `![](images/<name>)` 替换为 `[IMAGE:{stem}_0_0]`；
  - 新增 `_as_png()`：MinerU 抽出的 JPEG 统一转成真 PNG，避免 `.png` 扩展名下实际是 JPEG、Content-Type 错配。
- sidecar 失败且 `MINERU_PYTHON` 为空时直接返回 `None`，不再尝试空路径本地子进程（旧日志中的 `PermissionError: [Errno 13] Permission denied: ''` 已消除）。

### 3.4 健康检查与依赖

- `mineru_service.health_check()` 在 `PARSER_URL` 非空时优先请求 `GET {PARSER_URL}/health`，仅当 HTTP 200 且 `ok/mineru` 为真才 `available=true`，`version=sidecar:<backend>`。
- `backend/requirements.txt` 新增 `PyPDF2>=3.0.0`：`pdf_reader.py` 在 pdfplumber 抽不出文本时显式 `import PyPDF2`，缺包会让扫描件在进入 OCR 前误报 500。
- 单元测试新增：sidecar 启用、sidecar health 成功/连接失败、图片落盘与 Markdown 替换（含 JPEG→PNG）、sidecar 失败不 spawn 本地进程。

---

## 4. 验证记录

### 4.1 启动与安全

~~~bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env.development --profile ocr up -d parser backend
~~~

| 项 | backend | parser |
|---|---|---|
| 状态 | healthy | healthy |
| 用户 | `1000:1000` | `10001:10001` |
| read_only | true | true |
| 内存 | 2,147,483,648 B | 4,294,967,296 B |
| CPU | 2.0 | 2.0 |
| pids | 512 | 512 |
| 网络 | edge / app / egress | 仅 app |

~~~text
backend -> http://parser:8080/health
{"ok":true,"mineru":true,"backend":"pipeline"}
GET /api/questions/import/mineru-health
{"available":true,"version":"sidecar:pipeline","message":"http://parser:8080/health"}
~~~

### 4.2 扫描件 OCR

- 上传 `tmp-am2025-scan.pdf`，parser 日志 `success chars=2547 images=4 dur=220.9s`。
- 主后端日志：`图片落盘 4 张`，`engine=mineru`。
- 预览结果（import_id=1644）：8 题（106,107,109,110,112,113,114,115），8 个单题组，warnings 为空。
- 题 113 含 3 个 `<img src="/static/questions/<sha>_0_0.png">`；`GET` 首图 → 200，16,421 B，返回字节为真实 PNG 头（89 50 4E 47）。

> OCR 仍会丢 108/111 并漏材料组：MinerU Markdown 使用 ASCII `(一)`，而 `text_parser._XINGCE_SET_MARKER` 只认全角 `（一）`；108/111 又被拼到上一行选项末尾。文本型 PDF 无此问题。该结构性问题记录为 P4 输入。

### 4.3 文本导入：parser 停止

~~~bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env.development stop parser
# 清空 text_cache 后上传 tmp-am2025-text.pdf
~~~

| 项 | 结果 |
|---|---|
| import_id | 1643 |
| engine | `pdfplumber` |
| 题目 / 组 | 12 题 / 4 组 |
| 材料组 | `m_0d60f94ec8005314`（5 题，515 字）、`m_99625362f2d8ee59`（5 题，627 字） |
| backend | `/health` 200 healthy，容器 health=healthy |

### 4.4 文本导入：PARSER_URL 置空

- `deploy/.env.development` 的 `PARSER_URL` 置空并 `--force-recreate backend`。
- `GET /api/questions/import/mineru-health` → `{"available":false,"version":null,"message":"MinerU 未启用或解释器路径无效"}`。
- 上传 `tmp-am2025-text.pdf` → import_id=1641，`engine=pdfplumber`，12 题，4 组，材料长度 515/627 不变。
- 结论：`PARSER_URL` 为空不影响文本型 PDF 导入。

### 4.5 测试与门禁

~~~text
cd backend && python -m pytest tests/test_mineru_service.py tests/test_mineru_timeout.py tests/test_paper_group_payload.py -q
28 passed
python scripts/gates/gate_all.py --quick
PASS L0 / L1-G / L1 / L1-H -> 4/4 通过
~~~

---

## 5. 与七条硬约束的对照

| 约束 | P3 落实 |
|---|---|
| 安全左移 / 默认不信任 | parser 非 root、read_only、cap_drop ALL、no-new-privileges；上传大小限制；图片文件名白名单 + sha1 兜底 |
| 资源与生命周期 | parser 2 CPU / 4 GB / 512 pids；内部信号量串行；healthcheck start_period 180s |
| 数据与状态 | 模型在 `parser_cache` 卷；题图写静态目录；parser 本身无状态，可随时重建 |
| 网络可控 | parser 只连 app internal 网络，不 publish 端口；backend 主动访问 |
| 交付与配置 | 模型版本、torch wheel、镜像源均可 build-arg 覆盖；模型路径外置为 `mineru.json` |
| 可观测 | parser /health、backend health、`[mineru]` 日志（耗时、图片数、回退原因） |
| 协作变更 | 改动集中在 parser 与 mineru_service；文本导入路径保持向后兼容 |

---

## 6. 运维注意事项

### 6.1 重建顺序

1. 改 parser 代码：重建 parser 镜像 → `--profile ocr up -d --force-recreate parser`。
2. 改主后端代码：重建 backend 镜像 → `--force-recreate backend`。
3. 两侧都改：先 parser 后 backend；backend 健康端点确认 `version=sidecar:pipeline`。

### 6.2 模型缓存

- 换机 / 首次部署必须先把宿主 `~/.cache/modelscope` 预热进 `parser_cache` 卷，否则离线 502。
- 卷内模型版本需与 `mineru 3.4.5` 匹配；升级 MinerU 前先验证 `mineru.json` 路径。

### 6.3 SQLite WAL 与强制重建

staging 实测：在未 checkpoint 的情况下连续上传后执行 `--force-recreate backend`，两条 PREVIEW 记录不再可见（后经重新导入复现并确认）。原因是 PREVIEW 写入仍在 WAL，容器被强制重建时未保证落盘。

操作要求：

- `--force-recreate` 前先执行 `PRAGMA wal_checkpoint(FULL)`；
- 生产发布必须走“停服务 → checkpoint → 备份 → 启动新容器”的 P5/P6 流程；
- PREVIEW 只是临时预览，不是业务数据；正式入库（CONFIRMED）后不受影响。

### 6.4 nginx 上游缓存

nginx 在启动时解析 `backend:8000` 一次；backend 重建换 IP 后需 `docker compose restart web`。P4 用 resolver + 变量 upstream 解决。

---

## 7. 回滚

| 场景 | 动作 |
|---|---|
| OCR 不可用 | 停 parser，`PARSER_URL` 置空，`--force-recreate backend`；文本导入立即恢复 |
| parser 镜像异常 | 回滚到上一镜像 tag，或删除 `--profile ocr` 启动参数 |
| 主后端异常 | 回滚 `liankao-backend:staging` 上一镜像；业务数据在宿主 bind，不随容器删除 |
| 模型卷异常 | 重建 `parser_cache` 并重新预热；不影响数据库 |

---

## 8. 下一步（P4–P6）

- **P4**：nginx resolver/变量 upstream；OCR 材料结构归一化（ASCII `(一)` → 全角、粘连题号拆分）；可选 Redis scale profile。
- **P5**：备份/恢复编排（`sqlite3.backup()`）、WAL checkpoint 钩子、日志轮转、Prometheus 指标。
- **P6**：TLS/域名、生产域名切换、含 Chromium 的完整 backend 镜像构建与发布。
