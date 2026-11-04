# 容器化 P4：OCR 归一化、nginx 动态解析与 TLS 验收报告 v1

> 状态：✅ 已完成（2026-10-31）。P4 只改部署编排、OCR 文本归一化与前端代理配置，未改 `.vtj` 模板、未改业务数据语义。
> 依据：用户 m06537 授权自动执行 P4→P5→P6；方案见 `docs/superpowers/specs/容器化部署方案_v2.0.md`，计划见 `docs/superpowers/plans/容器化P4-P6实施计划_v1.md`。

## 1. 结论

P4 解决两个已实测的残留问题：

1. **扫描件 OCR 丢题/材料分组散乱**：MinerU Markdown 使用 ASCII `(一)`，且题号会粘在上一行句末；新增 `normalize_ocr_markdown()` 后，真实 2 页扫描件从 8 题/8 个单题组恢复为 **10 题（106–115）/ 2 组×5 题**。
2. **backend 重建后 nginx 502**：`deploy/nginx.conf` 由固定 upstream 改为 Docker DNS + 变量 `proxy_pass`；人为占用旧 IP 并让 backend 换到新 IP 后，不重启 web 仍返回 200。
3. 附带交付 staging 可选 TLS overlay：自签证书下 `https://127.0.0.1:8443/healthz` 与 `/api/...` 均 200。

## 2. 基线

- 分支：`feat/teacher-administrator`
- 上一阶段提交：P3 `154dc52`
- staging：`deploy/runtime/{data,static,uploads,logs}`，独立 DB/static/uploads，生产库未动
- 镜像（staging）：web `e7a4d6c1292a` 105MB；backend `3da5d3025ba2` 1.8GB（无 Chromium）；parser `ecb42c37dabd` 3.29GB
- 扫描素材：`题库/行测/安徽行测/2025年安徽省公务员录用考试《行测》题（网友回忆版）题本.pdf` 第 21–22 页，150dpi 渲染为无文本层 PDF

## 3. 实现

### 3.1 OCR 文本归一化（BE / DATA）

文件：`backend/app/services/text_parser.py`

- 新增 `_ASCII_SET_MARKER`：行首 ASCII `(一)`…`(十)` → 全角 `（一）`，只匹配独占一行的材料序号，避免误伤正文括号。
- 新增 `_OCR_GLUED_QNUM`：把粘在中文/句末标点后的 2–3 位题号（如 `…1.79个百分点108.2023年…`）断成新行；正向断言只允许中文、引号、括号或年份开头，避免切小数。
- 新增 `_OCR_QNUM_YEAR_GAP`：行首 `106.2021年` 补空格为 `106. 2021年`。
- 原因：`_QNUM_LINE_START = re.compile(r'(?m)^[ \t]*(\d{1,3})[ \t]*[.．、](?!\d)')` 会把 `106.2021` 当小数，材料会挂到错误题号。
- 新增 `normalize_ocr_markdown(text: str) -> str`，只对 `engine == 'mineru'` 生效，可重复调用（幂等）。

文件：`backend/app/services/question_ingest/pdf_reader.py`

- 缓存命中时若 `_cache_scope == 'mineru'` 先归一化；`_finish(text, engine)` 在 `engine == 'mineru'` 时归一化后再写入 text_cache。旧缓存无需清空。

测试：`backend/tests/test_ocr_markdown_normalization.py`

- 使用真实 OCR 片段覆盖 106–115、`(一)(二)`、108 粘 `1.79个百分点`、111 粘 `55.46%。`；断言 10 题、108/111 存在、两组各 5 题、`1.79`/`93.37` 不被切、幂等。
- `cd backend && python -m pytest tests/test_ocr_markdown_normalization.py tests/test_xingce_material_sets.py -q --disable-warnings` → **9 passed**。

### 3.2 nginx 动态解析（OPS）

文件：`deploy/nginx.conf`

- 删除 `upstream backend_upstream { server backend:8000; keepalive 32; }`；server 内新增 `resolver 127.0.0.11 valid=10s ipv6=off;` 与 `set $backend http://backend:8000;`。
- `/api/` 与 `^~ /static/` 两处改为 `proxy_pass $backend;`。
- 代价：失去 upstream keepalive；单后端场景可接受。
- 保留 `Host $http_host`、`X-Forwarded-Host`、`X-Forwarded-Port`、`location ^~ /static/`、SPA fallback。

### 3.3 可选 TLS（OPS，staging 验证）

- 新增 `deploy/nginx.tls.conf`：保留 8080，新增 `listen 8443 ssl`、TLSv1.2/1.3、证书路径 `/etc/nginx/certs/{server.crt,server.key}`。
- 新增 `deploy/docker-compose.tls.yml`：web 增加 `${HTTPS_PORT:-8443}:8443`，挂载 `nginx.tls.conf` 与 `certs/` 只读。
- 新增 `deploy/gen-self-signed-cert.sh`：仅 staging 自签；Git Bash 下对 openssl 使用 `MSYS_NO_PATHCONV=1` 避免 `-subj` 被转成 Windows 路径。
- 新增 `deploy/certs/README.md`；`.gitignore` 忽略 `deploy/certs/*.{crt,key,pem}`，证书不入 Git。
- 生产优先由学校网关终止 TLS；overlay 只作为内网/验收兜底。

## 4. 验收证据

| 项 | 结果 |
|---|---|
| 扫描件 OCR 题数 | import_id=1645，**10 题**，success_count=10，failed=0，耗时 282.8s |
| 题号连续性 | `[106,107,108,109,110,111,112,113,114,115]`，P3 丢失的 108/111 已恢复 |
| 材料分组 | 2 组×5 题：106–110 材料 511 字，111–115 材料 621 字 |
| 图片落盘/可访问 | 题 113 的 3 张图落盘到 staging static；示例 `7a9b330d…_0_0.png` GET **200 / 16,651 B** |
| web/backend/parser | 三容器 healthy；backend 非 root 1000:1000，parser 10001:10001 |
| nginx 基本链路 | `/healthz` 200，`/api/questions/?page=1&page_size=1` 200，`/static/questions/251c9b25_42_0.png` 200/16,397 B |
| nginx 动态解析 | 旧 backend edge IP 172.18.0.2 被占用，backend 重连后变为 172.18.0.4；不重启 web，`/healthz` 与 `/api/...` 仍 200 |
| TLS | `curl -k https://127.0.0.1:8443/healthz` → 200；HTTPS `/api/...` → 200；HTTP 8080 仍 200 |
| 资源 | OCR 期间 parser 峰值约 1.75 GiB / 4 GiB、CPU ~200%，未触 OOM；backend 271 MiB / 2 GiB |
| 测试 | P4 专项 9 passed；P3 既有 MinerU/复合题测试未回归（见 §5） |

## 5. 回归与门禁

- `cd backend && python -m pytest tests/test_ocr_markdown_normalization.py tests/test_xingce_material_sets.py -q --disable-warnings` → 9 passed。
- `cd backend && python scripts/gates/gate_all.py --quick` → **4/4 通过**（L0 4.2s / L1-G 0.3s / L1 8.1s / L1-H 0.4s）。
- `bash -n deploy/*.sh` 通过；`docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.tls.yml --env-file deploy/.env.development config --quiet` 通过。
- 未执行 GitHub Actions；CI 文件在 P5 交付并在本地做 YAML 解析。
- 镜像漏洞扫描：`aquasec/trivy` 两次均失败——默认 `mirror.gcr.io` TLS handshake timeout；切 `--db-repository ghcr.io/aquasec/trivy-db` 被 GHCR 拒绝（DENIED）。本阶段**未取得漏洞扫描结果**，不能声明镜像无高危漏洞。

## 6. 约束与风险

- **R7**：未删除/移动 `backend/app/static/`；staging 使用独立 static 副本。
- **R10**：未用 `cp/copy2` 备份主库；P4 只做 checkpoint，P5 提供 `sqlite3.backup()` 编排。
- **R11**：未改 `/api/v1/...` 路径。
- 已知限制：含 Chromium 的生产 backend 镜像仍未在弱网下完整构建；TLS 证书生产需学校提供；nginx 变量 proxy 每次请求走 Docker DNS；trivy 漏洞库下载受网络限制，镜像扫描未完成，P6/上线前须在可联网环境补扫。
- OCR 归一化只处理 ASCII 材料序号与强信号粘连题号；若未来版面出现其他粘连形式，需补测试再扩展正则。

## 7. 回滚

- 回滚 OCR：移除 `pdf_reader.py` 的 `normalize_ocr_markdown` 调用即可恢复旧文本；数据未变。
- 回滚 nginx：恢复固定 `upstream` 与 `proxy_pass http://backend_upstream;`，或重建上一版 web 镜像。
- 回滚 TLS：不叠加 `deploy/docker-compose.tls.yml` 即可。
- 回滚不涉及数据库与题目数据。

## 8. 下一步（P5/P6）

- P5：`deploy/checkpoint.sh`、`backup.sh`、`restore.sh`、`inspect.sh`、CI、恢复演练。
- P6：production env 模板、`release.sh`、学校服务器切换 Runbook。

## 9. 关键文件

- `backend/app/services/text_parser.py`（`_ASCII_SET_MARKER` / `_OCR_GLUED_QNUM` / `_OCR_QNUM_YEAR_GAP` / `normalize_ocr_markdown`）
- `backend/app/services/question_ingest/pdf_reader.py`（mineru 缓存与 `_finish` 归一化）
- `backend/tests/test_ocr_markdown_normalization.py`
- `deploy/nginx.conf`、`deploy/nginx.tls.conf`、`deploy/docker-compose.tls.yml`、`deploy/gen-self-signed-cert.sh`、`deploy/certs/README.md`
- `docs/superpowers/plans/容器化P4-P6实施计划_v1.md`