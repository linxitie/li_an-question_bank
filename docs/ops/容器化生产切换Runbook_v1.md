# 容器化生产切换 Runbook v1

> 适用版本：`docs/superpowers/specs/容器化部署方案_v2.0.md` P6；目标拓扑 = `web` + `backend` 两容器，SQLite 与四库数据全部在宿主 bind 目录，parser 仅在需要 OCR 时以 `ocr` profile 启动。
> 本文是操作手册，不替代方案与报告；任何步骤失败都先停止，不要执行 `docker compose down -v`。

## 1. 适用场景与边界

| 场景 | 是否适用 | 说明 |
|---|---|---|
| 学校服务器首次部署 | ✅ | 从现有单机目录迁移到 `/srv/liankao` |
| 版本发布/回滚 | ✅ | 用 `deploy/release.sh`，失败自动回上一 tag |
| 开发机日常改代码 | ❌ | 继续用现有 Vite + uvicorn，不容器化 |
| PostgreSQL/Redis 集群化 | ❌ | 当前系统 SQLite 单写者，Redis 仅多 worker 时才需要 |

硬边界：

1. SQLite 是唯一事实源，不放进容器层，不挂 named volume 承载业务数据。
2. `backend/app/static`、`backend/uploads`、`backend/data/foundation` 都是状态，必须有宿主目录与备份。
3. 容器镜像不可变；配置通过 `deploy/.env.production` 外置。
4. 生产禁止 `docker compose down -v`、禁止删除 `data/*.bak*`、禁止把真实密钥写进 Git。

## 2. 切换前检查（T-1 天）

- [ ] 服务器 Docker Engine ≥ 24、Compose v2 可用；`docker info` 正常。
- [ ] 磁盘：`/srv` 至少预留「现有数据 × 2 + 20 GB」；当前实测生产库 58 MB、题图约 7.1 GB、uploads 约 886 MB。
- [ ] 端口：`HTTP_PORT`（默认 8080）未被占用；若由学校网关反代，仅需本机回环/内网可达。
- [ ] 域名与证书由学校网关负责；本 compose 默认 `TLS_MODE=gateway`，不在容器内终止 TLS。
- [ ] 由用户本人生成 `JWT_SECRET_KEY`（`openssl rand -base64 48`），不经过 AI、不写入文档。
- [ ] 确认最近一次全量备份可读：`deploy/inspect.sh` 无 FAIL；备份年龄 < 48h。
- [ ] 通知使用方维护窗口；考试进行中禁止切换。

## 3. 目录与权限

```bash
sudo mkdir -p /srv/liankao/{data,static,uploads,logs/backend}
sudo chown -R 1000:1000 /srv/liankao
sudo chmod 750 /srv/liankao
```

- `APP_UID/APP_GID` 默认 1000，必须与目录属主一致；否则 backend 无法写 SQLite/WAL、日志与上传。
- `static` 是题图只读为主，但导入会写入新图，仍需可写。
- 不建议把 `/srv/liankao` 放在 NFS/CIFS：SQLite WAL 依赖本地文件锁。

## 4. 数据迁移

### 4.1 冻结写入

1. 通知停止导入/组卷/考试。
2. 停旧服务（不要删旧目录）：`systemctl stop liankao` 或停旧 uvicorn。
3. 确认无进程占用旧库：`lsof question_bank.db`（Linux）或资源监视器（Windows）。

### 4.2 数据库（必须用 sqlite3.backup）

```bash
python - <<'PY'
import sqlite3
src = sqlite3.connect('/path/to/question_bank.db')
dst = sqlite3.connect('/srv/liankao/data/question_bank.db')
with dst:
    src.backup(dst)
dst.execute('PRAGMA journal_mode=WAL')
print(dst.execute('PRAGMA integrity_check').fetchone())
PY
```

禁止直接 `cp`/`scp` 主库了事：WAL 模式下会丢已提交事务。复制后确认 `-wal`/`-shm` 不存在或已被 checkpoint。

### 4.3 静态与上传

```bash
rsync -a --info=progress2 /path/to/backend/app/static/ /srv/liankao/static/
rsync -a --info=progress2 /path/to/backend/uploads/ /srv/liankao/uploads/
```

迁移后核对文件数：题图约 151,457 个、uploads 约 5,960 个（以现场实测为准）。

### 4.4 四库目录（若已启用）

`data/foundation/{objects,docs,vectors}` 一并 rsync；这些是可重建投影，但重建耗时，首次迁移建议带上。

## 5. 配置

```bash
cp deploy/.env.production.example deploy/.env.production
chmod 600 deploy/.env.production
# 编辑：IMAGE_TAG、JWT_SECRET_KEY、SCHOOL_DOMAIN、DATA_ROOT/STATIC_ROOT/UPLOAD_ROOT/LOG_ROOT
```

必填项：

| 变量 | 生产值示例 | 说明 |
|---|---|---|
| `IMAGE_TAG` | `20261031-1` | 禁止 `latest`/`CHANGE_ME*` |
| `JWT_SECRET_KEY` | 用户本人生成 | 长度 ≥32，preflight 拒绝占位符 |
| `DATA_ROOT` | `/srv/liankao/data` | 绝对路径 |
| `STATIC_ROOT` | `/srv/liankao/static` | 绝对路径 |
| `UPLOAD_ROOT` | `/srv/liankao/uploads` | 绝对路径 |
| `LOG_ROOT` | `/srv/liankao/logs` | backend 日志写 `logs/backend` |
| `HTTP_PORT` | `8080` | 学校网关反代目标 |
| `TLS_MODE` | `gateway` | 容器内不终止 TLS |
| `PARSER_URL` | 空或 `http://parser:8080` | 仅 OCR 时需要 |

预检：

```bash
bash deploy/preflight.sh
# 或只校验配置，不备份/不启动：
ENV_FILE=.env.production bash deploy/release.sh --dry-run
```

## 6. 首次启动

```bash
# 拉取已发布镜像（推荐）
docker compose -f deploy/docker-compose.yml --env-file deploy/.env.production pull web backend
docker compose -f deploy/docker-compose.yml --env-file deploy/.env.production up -d --no-build web backend

# 或本地构建（无 registry 时）
docker compose -f deploy/docker-compose.yml --env-file deploy/.env.production build web backend
docker compose -f deploy/docker-compose.yml --env-file deploy/.env.production up -d --no-build web backend
```

首次启动必须确认：

- `docker compose ps`：web/backend 均 `healthy`。
- `curl http://127.0.0.1:8080/healthz` → `ok`。
- `curl http://127.0.0.1:8080/health` → `status=healthy`。
- `curl 'http://127.0.0.1:8080/api/questions/?page=1&page_size=1'` → 200。
- 日志无 `ModuleNotFoundError`、无 SQLite `database is locked`。

## 7. 验收烟测（必须逐项勾选）

- [ ] 教师登录，题目管理能打开复合题，题组材料与子题同屏。
- [ ] 学生登录，试卷列表可见已发布试卷。
- [ ] 打开一份含复合题的试卷，组材料只在组首题出现且可折叠/吸顶。
- [ ] 题图（`/static/questions/...`、`/static/question-groups/...`）返回 200 且非裂图。
- [ ] 开考 → 答题 → 交卷全链路 200；成绩/记录可查。
- [ ] 智能组卷命中题组时整组带入，题数超配时有显式提示。
- [ ] 重启 backend 后重新登录，数据仍在（验证 bind 挂载与 WAL）。
- [ ] `deploy/inspect.sh` 0 FAIL；日志目录有轮转。

## 8. DNS 与网关切换

1. 先在本机用 `curl -H 'Host: exam.example.edu.cn' http://127.0.0.1:8080/healthz` 验证 Host 透传。
2. 学校网关反代到 `http://<服务器内网IP>:8080`，保留 `Host`、`X-Forwarded-Proto`、`X-Forwarded-For`。
3. 上传大小限制 ≥200 MB（`client_max_body_size 200m`），超时 ≥900s（OCR/大文件导入）。
4. DNS TTL 调低到 5 分钟后再切；切换后观察 30 分钟。

## 9. 观察期（24 小时）

- 每小时：`deploy/inspect.sh`，关注容器重启次数、`/health`、磁盘、错误日志。
- 重点日志：`/srv/liankao/logs/backend/`、`docker logs <backend>`；检索 `ERROR`、`database is locked`、`502`。
- 观察 SQLite 体积与 WAL：`ls -lh question_bank.db*`；WAL 持续增长说明长事务或 checkpoint 不足。
- 观察 parser（若启用）内存峰值，OCR 单次可到 1.7 GB 以上，限制为 4 GB。

## 10. 发布与回滚

### 10.1 常规发布

```bash
ENV_FILE=.env.production bash deploy/release.sh --tag 20261101-1
```

脚本顺序：preflight → WAL checkpoint → 备份（label `release-<tag>`）→ pull/build → `up -d` → healthy → smoke；失败自动用上一 tag 回滚并再烟测。

### 10.2 手动回滚

```bash
# 镜像回滚
IMAGE_TAG=<上一版本> docker compose -f deploy/docker-compose.yml --env-file deploy/.env.production up -d --no-build web backend

# 数据回滚（仅在数据损坏时）
ENV_FILE=.env.production bash deploy/restore.sh --latest --yes
```

`restore.sh` 会先做覆盖前快照，再停 backend、恢复、起 backend、等 healthy、打印四表计数。

### 10.3 RTO / RPO（目标值，需在演练中实测）

| 指标 | 目标 | 依据 |
|---|---|---|
| RPO | ≤ 24h（日常）；发布前为 0（强制备份） | `inspect.sh` 默认 48h 告警；`release.sh` 每次发布前备份 |
| RTO（镜像回滚） | ≤ 10 分钟 | 仅重建容器，不动数据 |
| RTO（数据恢复） | ≤ 60 分钟 | 58 MB 库 + 覆盖前快照；不含 7 GB 静态复制 |
| 静态资产恢复 | 视备份介质，小时级 | `backup.sh --assets` 可选，默认只备份 DB |

## 11. 禁止事项

1. ❌ `docker compose down -v`：会删 named volume；业务数据虽在 bind，但 parser 缓存/未来卷会丢。
2. ❌ 直接 `cp question_bank.db` 做备份或迁移。
3. ❌ 在生产 `--force-recreate` 前不 checkpoint：WAL 中 PREVIEW/事务可能丢。
4. ❌ 把 `.env.production`、证书私钥、真实 JWT 提交 Git 或贴进聊天。
5. ❌ 在考试进行中发布或恢复数据。
6. ❌ 用 `latest` tag 发布；回滚将失去确定性。

## 12. 故障速查

| 现象 | 优先检查 | 处置 |
|---|---|---|
| web 502 | backend 是否 healthy、nginx 日志 | 等 healthy；仍 502 重启 web（DNS 缓存） |
| 登录 500 | `passlib`/`bcrypt` 版本、JWT 配置 | 镜像需含 `bcrypt>=4.0,<5`；检查 `.env.production` |
| 题图 404 | `STATIC_ROOT` 是否正确、挂载是否只读 | 核对 bind 路径与文件数；不要指向空目录 |
| `database is locked` | 是否有第二个 writer/备份占用 | 停重复进程；备份走 `backup.sh`；检查 WAL |
| OCR 超时 | parser healthy、模型卷、内存 | `docker compose --profile ocr ps`；4 GB 限制是否被 OOM kill |
| 磁盘满 | 日志/备份/预览缓存 | 清旧备份需人工确认；不要删 `*.bak*` 与 `audit/` |

## 13. 交付清单

- [ ] `deploy/.env.production`（600，未入库）
- [ ] `/srv/liankao/{data,static,uploads,logs}` 权限正确
- [ ] 首次备份 + `latest.json` 可读
- [ ] `deploy/inspect.sh` 0 FAIL
- [ ] 烟测清单全部勾选
- [ ] 回滚演练记录（镜像 tag + 数据恢复各一次）
- [ ] 交接：域名、证书续期、备份保留周期、值班联系人
