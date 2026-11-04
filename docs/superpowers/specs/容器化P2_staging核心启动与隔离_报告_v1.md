# 容器化 P2 staging 核心启动与数据隔离_报告_v1

> 文档性质：实施记录 / 验收报告。
> 状态：P2 已完成（2026-10-30）——staging 使用独立数据库、静态与上传副本，web/backend 双容器启动，核心链路、复合题材料、开考/交卷、down/up 持久化均已实测。
> 关联方案：`docs/superpowers/specs/容器化部署方案_v2.0.md`（§13 P2）
> 分支：`feat/teacher-administrator`；P1 提交：`d4415b0`
> 范围：只操作 `deploy/runtime/` 与本地 staging 环境；不写生产库、不搬生产数据、不改业务代码。

---

## 1. 结论

P2 的目标是“在 staging 用独立数据把部署态容器完整跑通”，不是切换生产。

已完成：

- staging 数据库用 `sqlite3.Connection.backup()` 从生产库复制，未使用文件拷贝（AGENTS R10）。
- staging 静态与上传复制为独立副本，不再指向生产 `backend/app/static`。
- web + backend 双容器启动 healthy；数据库、静态、上传全部为宿主 bind，容器重建不丢数据。
- 登录、题目列表、题图、复合题材料、开考、交卷全部通过。
- `docker compose down`（**不加 `-v`**）后重新 `up`，业务数据仍在，复合题试卷仍可读。
- 容器非 root、read_only、cap_drop、no-new-privileges、CPU/内存/pids limits 均实测生效。
- 数据计数与生产库逐项一致（见 §4.5）。

未完成（按方案进入 P3–P6）：

- 含 Chromium 的完整生产 backend 镜像；
- parser/OCR profile、TLS、备份/恢复编排、CI、生产切换；
- staging 测试账号密码仍是本地测试值（仅 staging 库，生产未动）。

---

## 2. 基线

| 项 | 实测 |
|---|---|
| 分支 / P1 提交 | `feat/teacher-administrator` / `d4415b0` |
| staging 项目名 | `liankao-staging` |
| staging 入口 | `http://127.0.0.1:8080` |
| 生产主库 | `backend/data/question_bank.db` |
| staging 主库 | `deploy/runtime/data/question_bank.db` |
| staging 静态 | `deploy/runtime/static`（独立副本） |
| staging 上传 | `deploy/runtime/uploads`（独立副本） |
| 容器 | backend `liankao-backend:staging`；web `liankao-web:staging` |

---

## 3. staging 数据准备

### 3.1 数据库

~~~text
源：backend/data/question_bank.db
目标：deploy/runtime/data/question_bank.db
方式：sqlite3.Connection.backup()
大小：58,130,432 bytes
sha256：c06a4144d22f3be1c29630f61a10f4a830697ed372993ca04bfe75c0fc6fb8a9
integrity_check：ok
~~~

复制后清理了临时 `-wal` / `-shm`，避免把源库未检查点内容带进 staging。

### 3.2 静态与上传

- `backend/app/static` → `deploy/runtime/static`：robocopy `/E /MT:16`，questions 文件数 **151,457**；robocopy 返回 `1`（成功，有复制）。
- `backend/uploads` → `deploy/runtime/uploads`：文件数 **5,960**；返回 `1`。
- `deploy/.env.development` 已改为：
  - `DATA_ROOT=./runtime/data`
  - `STATIC_ROOT=./runtime/static`
  - `UPLOAD_ROOT=./runtime/uploads`
  - `IMAGE_TAG=staging`；`INSTALL_PLAYWRIGHT_BROWSERS=0`

### 3.3 隔离证据

- 创建 `deploy/runtime/static/images/__staging_marker__.txt`，内容 `staging-isolated`。
- 生产同路径不存在。
- 经 web 访问 `/static/images/__staging_marker__.txt` → 200，body 为 `staging-isolated`。
- 验证后已删除 marker，避免把测试文件留在 staging。

---

## 4. 验证记录

### 4.1 启动与安全

~~~bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env.development up -d --no-build
~~~

| 项 | backend | web |
|---|---|---|
| 状态 | healthy | healthy |
| 用户 | `1000:1000` | `101`（nginx-unprivileged） |
| read_only | true | true |
| CapDrop | `["ALL"]` | `["ALL"]` |
| no-new-privileges | true | true |
| 内存 | 2,147,483,648 B | 134,217,728 B |
| CPU | 2.0 | 0.5 |
| pids | 512 | 128 |

### 4.2 核心链路

| 项 | 结果 |
|---|---|
| web 健康 | `GET /healthz` → 200 `ok` |
| backend 健康 | 容器内 `/health` → 200 healthy |
| 登录 | `POST /api/auth/login` → 200，返回 access_token |
| 题目列表 | `GET /api/questions/?page=1&page_size=3` → 200，total=3268 |
| 普通试卷 | `GET /api/exams/51/questions` → 200，100 题 |
| 题图 | `GET /static/questions/251c9b25_42_0.png` → 200，16,397 B，PNG |
| 开考 | `POST /api/exams/51/start`（P1 已验；P2 以复合题卷复验，见 4.3） |

### 4.3 复合题材料与整组

为在 staging 验证复合题，临时创建一份仅 staging 可见的试卷：

~~~text
paper_id=59
paper_name=P2烟测-复合题完整性
paper_type=PUBLISHED
question_count=5
qids=4004,4005,4006,4007,4008（全部属于 group 33）
~~~

结果：

| 项 | 结果 |
|---|---|
| `GET /api/exams/59/questions` | 200，5 题 |
| 组字段 | 5 题全部 `group_id=33`，`question_level=1` |
| 组材料 | `shared_content` 长度 411，`shared_content_images` 3 个 |
| 开考 | `POST /api/exams/59/start` → 200，record_id=4 |
| 交卷 | `POST /api/exams/4/submit`（空答案）→ 200，success=true |

说明：卷 59 与 record 4 在验收后已删除，staging 的 `exam_paper` 恢复 42、`exam_record` 恢复 1；没有把测试卷留在库中。

### 4.4 down/up 持久化

~~~bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env.development down
# 确认 deploy/runtime/data/question_bank.db 仍为 58,130,432 bytes
docker compose -f deploy/docker-compose.yml --env-file deploy/.env.development up -d --no-build
~~~

- `down` 未加 `-v`，网络与容器重建，bind 数据未动。
- 重新 `up` 后 backend/web 均 healthy。
- 重新登录后 `GET /api/exams/59/questions` 仍 200、5 题，组字段仍在。
- 说明“容器会消失、数据必须有家”在 staging 成立。

### 4.5 数据计数一致性

| 表 | 生产 | staging |
|---|---:|---:|
| `question_bank` | 3,489 | 3,489 |
| `question_groups` | 38 | 38 |
| `exam_paper` | 42 | 42 |
| `exam_record` | 1 | 1 |
| `media_assets` | 937 | 937 |
| `sys_user` | 13 | 13 |

差异说明：staging 的 `sys_user` 中仅 202516001 的密码被重置为本地测试值，用于登录烟测；生产库未执行该操作，生产数据未改。

---

## 5. 问题与修正

### 5.1 新建 PUBLISHED 试卷在运行中的容器里 404

现象：

~~~text
POST/GET /api/exams/59/questions → 404
{"detail":"试卷不存在或未发布"}
~~~

但容器内 `sqlite3` 查询确认 `exam_paper.paper_id=59`、`paper_type=PUBLISHED`、5 条关系均存在。

定位与修正：

- 该卷是用宿主机 `sqlite3` 在 backend 运行期间直接写入 bind 挂载数据库的。
- Docker Desktop 的 bind mount 对运行中容器的文件缓存/SQLite 读快照没有立即刷新；重启 backend 后同一请求返回 200。
- 结论：**staging 若直接改宿主侧 SQLite，写后必须重启 backend 再验证**；生产创建/发布试卷走 API，不存在该路径。
- 已在删卷后重启 backend 一次，确保当前 staging 与清理后的数据库一致。

### 5.2 测试数据清理

- 删除 `paper_question_relation` 中 `paper_id=59` 的 5 条；
- 删除 `exam_paper` 中 `paper_id=59`；
- 删除 `exam_record` 中 `record_id=4`；`exam_answer_detail` / `score_analysis` 中该记录原本为 0 条；
- 删除临时脚本 `backend/_make_p2_paper.py`、`deploy/runtime/p2_group2.py`、`deploy/runtime/p2_probe3.py`、`deploy/runtime/p2_final.py`；
- 删除隔离 marker。

---

## 6. 红线与约束对照

| 约束 | P2 落地 |
|---|---|
| 安全左移 / 最小权限 | backend uid/gid 1000；web uid 101；read_only、cap_drop ALL、no-new-privileges |
| 资源与生命周期 | limits 实测：backend 2 CPU / 2 GiB / 512 pids；web 0.5 CPU / 128 MiB / 128 pids |
| 数据与状态 | DB/static/uploads/logs 全宿主 bind；`down` 不加 `-v`，数据保留 |
| 网络可控 | web 仅 edge；backend edge/app/egress |
| 不可变镜像 | web 镜像内含 dist；不挂宿主 dist |
| 可观测性 | 健康检查、日志轮转沿用 P1；Prometheus/告警留 P5 |
| 协作变更 | `deploy/runtime/`、`deploy/.env.development` 均被 .gitignore 排除，不入库 |

AGENTS 红线：

- R7：static 仅复制，不删不搬生产题图；
- R10：staging 主库用 `sqlite3.backup()`，未用 `cp` / `shutil.copy2`；
- R11：未改任何 `/api/v1` 路径；
- 未改 `.vtj/`、未动 `raw: true` 页面。

---

## 7. 回滚

1. 停 staging：`docker compose -f deploy/docker-compose.yml --env-file deploy/.env.development down`（**不要加 `-v`**）。
2. 删除 `deploy/runtime/` 即丢弃 staging 数据；生产数据不在其中。
3. 恢复生产启动走原 `backend` 进程或旧编排，不依赖 staging 目录。

---

## 8. 下一步（P3）

- parser 非 root 与 OCR profile 启动；
- 用 `题库/行测/安徽行测` 真实 PDF 做扫描件导入烟测；
- 验证文本导入、预览、确认、题组材料、图片落盘；
- 验证 `PARSER_URL` 为空时文本导入不受影响；
- 继续保留 staging 独立数据，不在生产库做导入烟测。
