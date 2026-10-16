# 学生端容器化与模块化 —— 实施计划

> 依据：`docs/superpowers/specs/2026-10-15-student-containerization-modularization-design.md`（v2.0）
> 分支：`feat/student-containerization`（基于 `cb63045`）
> 编制日期：2026-10-15
> 状态：**待审核**

---

## 0. 计划约定

### 0.1 阶段总览

| 阶段 | 内容 | 门禁挂点 | 前置 |
|---|---|---|---|
| **P0** | 测试基线修复 + 凭据治理 + 死代码清理 | `pytest` error = 0 | — |
| **P1** | 容器化落地（镜像 + compose + parser sidecar） | 8 门禁 + `/health` | P0 |
| **P2** | `core/` 内核抽离 | L4 / L5 | P1 |
| **P3A** | 前端 `src/` 目录分层（设备双轴） | 构建通过 + 路由可达 | P2 |
| **P3B** | 后端十域逐个搬迁 | `api_surface.json` 前后比对 | P2 |
| **P4** | 契约改造（15 处跨域写 → `contract.py`） | `check_module_boundary.py` | P3B |
| **P5** | 事件总线落地（消除 8 处跨域直调） | 跨域 import 归零 | P4 |
| **P6** | 目录清理与归档（L1 / L2） | 8 门禁 | P5 |

> P3A 独立于 P3B：前端分层只动 `src/`，后端搬运动 `models.py` 与 `main.py`，两者无文件重叠，可并行；为便于控制风险，仍按顺序执行。

### 0.2 硬性约束（贯穿全部阶段）

| # | 约束 | 依据 |
|---|---|---|
| C1 | **`.vtj/` 零改动**——`src/router/index.ts` 有 92 处 `import('$vtj/vue/<id>.vue')` 硬绑定 | 设计规格 §4.6 |
| C2 | **`raw: true` 页禁止 `vtj_sync_vue_to_dsl`**；`<template>` 变更须由用户在 `http://localhost:9527/__vtj__/` 完成；`<script>` 修改必须先 `dryRun: true` | VTJ 铁律 |
| C3 | **API 路径 `/api/v1/...` 全程冻结**，343 个端点逐条比对 | 设计规格 §5.3 |
| C4 | **`题库/`、`backend/app/static/`、`backend/data/question_bank.db`、`backend/data/gates/*.json` 禁止删除或移动** | 设计规格 §7.4 |
| C5 | **备份必须用 `sqlite3.backup()` API**，`shutil.copy2` 在 WAL 模式下被禁止；回滚须同时删除 `-wal` 与 `-shm` | `backend/README.md` |
| C6 | **41 份唯一数据库备份严禁删除**，`bak_pre_wipe_20261004_102517` 是全系统唯一存世的 10,171 道行测题副本 | 设计规格 §2.7 |
| C7 | **`src/utils/device.ts` 与 `resolveDevicePath()` 原样保留**，不得移动或改名 | 设计规格 §4.2 |
| C8 | **`mobile_*`、`tablet_*` 文件名前缀不重命名**，仅按目录归类 | 设计规格 §4.2 |
| C9 | **`backend/data/audit/` 与 `待推断题目清单_*.csv` 不是垃圾**，禁止删除 | 设计规格 §4.5 |

### 0.3 每任务通用流程

```
① 读基线：确认 api_surface.json / coupling.json 当前状态
② 实施：单任务单提交，不夹带无关改动
③ 验证：pytest + 8 门禁 + api_surface 比对（三者全过才算完成）
④ 状态回写：更新本计划对应任务的复选框
```

---

## P0 · 测试基线修复 + 凭据治理 + 死代码清理

### [ ] P0.1 修复索引同名冲突

**根因（已定位）**：`models.py` 中两张表声明了同名索引，SQLite 索引名是数据库全局的，第二张表建索引时抛 `index idx_import_status already exists`，导致 **52 个测试 error**。

| 位置 | 表 | 索引名 | 列 |
|---|---|---|---|
| `models.py:1069` | `question_import_record` | `idx_import_status` | `import_status` |
| `models.py:1319` | `material_import_record` | `idx_import_status` | `parse_status` |

**附带发现**：`scripts/migrate_study_materials.py:72` 写的是 `CREATE INDEX IF NOT EXISTS idx_import_status ON material_import_record(parse_status)`，因该名称已被占用而**静默跳过**——生产库实测 `material_import_record` 上一个索引都没有（该表当前 0 行，影响可控）。

**动作**：

1. `models.py:1319` 索引改名 `idx_import_status` → `idx_material_parse_status`（只改索引名）
2. `scripts/migrate_study_materials.py:72` 同步改名
3. 新增 `backend/migrations/fix_material_import_index.sql`，为存量库补建

**验证**：

```powershell
cd backend
python -m pytest tests -q --no-header -p no:warnings
# 期望：error 数 52 → 0；passed 不低于当前 227
```

**风险**：低。索引是派生结构不含数据；已核实除该迁移脚本外无任何代码按索引名引用。

**实测结果（2026-10-16）**：

| 指标 | 修复前 | 修复后 |
|---|---:|---:|
| error | 52 | **0** ✅ |
| passed | 227 | **265**（+38） |
| xfailed | 1 | 1 |
| failed | 17 | 31 |

failed 增加的 14 个**不是本次改动引入的回归**。原 52 个 error 的文件分布为
`test_api.py` 29 / `test_practice_unified.py` 13 / `test_quote_favorite.py` 9 /
`test_batch_parsed_import.py` 1——这些用例此前在 fixture 阶段就中断，**根本没执行到断言**。
索引修复后它们开始执行，因而暴露出既有的失效断言：

| 失效类型 | 数量 | 性质 |
|---|---:|---|
| `assert 404 == 401` / `405 == 401` | 5 | 端点已不存在或方法不匹配 |
| `assert 422 == 401` | 4 | Pydantic 入参契约已变，先触发校验而非鉴权 |
| `JSONDecodeError`（`/`、`/metrics/endpoints`） | 2 | 根端点已被 `main.py:663` 的 SPA fallback 取代，返回 HTML |
| `assert 422 == 200` / `404 == 200` / `1 == 5` | 3 | 请求体或查询参数与当前契约不符 |

**净效果**：52 个 error 归零，40 个测试由「不执行」转为「真实通过」，14 个由「不执行」转为「暴露既有缺陷」。
这 14 项属**测试期望过时**，需按当前 API 契约重写断言，不在本任务范围，已登记为 P0.4 独立任务。

---

### [ ] P0.2 凭据治理

| 子项 | 动作 | 执行方 |
|---|---|---|
| a | `.omo/plans/configure-deepseek-api.md` 中密钥替换为占位符 | 我 |
| b | `git rm --cached backend/.env`；`.gitignore` 追加 `backend/.env` | 我 |
| c | 新建 `backend/.env.example`（占位符版，入库） | 我 |
| d | `.env` 保留全部键位，**含 `DEEP_SEEK_API_KEY=`、`LLM_API_KEY=` 空字段** | 我 |
| e | 新建 `scripts/check_secrets.py`，扫描疑似密钥（`sk-[a-f0-9]{32}`、`JWT_SECRET_KEY=` 接非占位符），接入 L0 红线 | 我 |
| f | **生成新 `JWT_SECRET_KEY` 并写入 `backend/.env`** | **您** |
| g | 授权后 `git filter-repo` 清除历史中的旧密钥 | **您** |

**P0.2-f 步骤**（密钥不经过我）：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"   # 1) 生成
# 2) 填入 backend/.env 的 JWT_SECRET_KEY=
docker compose restart backend                                # 3) 重启
# 4) 全员被登出属预期，重新登录
```

**影响面**：

| 项 | 影响 | 结论 |
|---|---|---|
| `DEBUG=False` | 仅 `seed.py:453` 读取，作用是跳过自动种子数据 | 零风险 |
| `DB_PASSWORD` | 仅 `config.py:127` MySQL 分支引用，当前 `DB_TYPE=sqlite` 根本不生效 | 零风险 |
| `JWT_SECRET_KEY` 轮换 | `security.py:229/240/245` 使用；旧 token（有效期 480 分钟）与 refresh token 全部失效 | 全员登出一次，预期 |

**验证**：

```powershell
git ls-files backend/.env          # 期望：无输出
python scripts/check_secrets.py    # 期望：退出码 0
# 旧密钥签发的 token 调用受保护端点 → 期望 401
```

---

### [ ] P0.3 删除 gRPC / Canal 僵尸代码

**依据**：设计规格 §2.10.1。`grpcio` 在 `requirements.txt:46-47` 被注释，`main.py:475` 调用必然走 `main.py:490` 的 `except` 静默失败；`canal_client.py` 全仓库零引用。

**动作**：

| 删除项 | 路径 |
|---|---|
| Canal 客户端 | `app/canal_client.py` |
| gRPC 服务端 | `app/grpc_service.py` |
| protobuf 定义 | `app/exam_service.proto`、`app/exam_service_pb2.py`、`app/exam_service_pb2_grpc.py` |
| 接入代码 | `main.py:474-491`、`main.py:522-525` |
| 文档修正 | `main.py` 描述中删除「gRPC: 高性能远程调用」一行 |

**验证**：

```powershell
python -c "from app.main import app; print(len(app.routes))"   # 服务可正常启动
python scripts/gate_all.py                                      # 8 门禁全绿
```

**风险**：低。对运行/安全/性能/跨平台适配零影响或正向（详见设计规格 §2.10.1）。

---

## P1 · 容器化落地

### [ ] P1.1 后端镜像

新建 `backend/Dockerfile`（`python:3.13-slim` + `ffmpeg`/`libgl1`/`libglib2.0-0`/`curl` + `playwright install --with-deps chromium`，COPY `app` 与 `data/gates`，`HEALTHCHECK` 复用既有 `/health`）。

新建 `backend/.dockerignore`——排除 `data/`（除 gates）、`uploads/`、`static/`、`__pycache__/`、`.env`、`tests/`。

**验证**：

```powershell
docker build -t liankao/backend:test backend
docker images liankao/backend:test        # 期望体积不含 4.3 GB 题图
docker run --rm liankao/backend:test sh -c "ls app/static | wc -l"   # 期望 0
```

### [ ] P1.2 MinerU / OCR sidecar

新建 `parser/Dockerfile`（`python:3.11-slim`）+ `parser/app.py`（暴露 `POST /parse`）。

改造 `app/services/mineru_service.py`：新增 `call_parser_http()`，优先走 `PARSER_URL`；未配置或失败时**回落现有 subprocess 路径**——`is_enabled()`（`mineru_service.py:55`）的降级逻辑保持不变，开发机工作方式不受影响。

**验证**：

```powershell
docker compose up -d parser
curl -f http://localhost:8080/parse -X POST -F "file=@<扫描件.pdf>"    # HTTP 路径
# 置空 PARSER_URL 重启，再测一次                                  # subprocess 回退路径
```

**风险**：中。解析链路是导入核心，两条路径都必须验证通过。

### [ ] P1.3 compose 与环境分离

新建 `docker-compose.yml`（nginx / backend / parser，Redis 未启用则删）、`deploy/nginx.conf`、`deploy/.env.development`、`deploy/.env.school`、`deploy/.env.example`。

数据卷：`db_data`（SQLite + 归档）、`uploads`、`qimg`（4.3 GB 题图，**绝不进镜像**）。

**验证**：

```powershell
docker compose config
docker compose up -d
docker compose ps                            # 期望全部 healthy
curl -f http://localhost:8000/health         # 期望 200
```

### [ ] P1.4 备份与回滚脚本

新建 `backend/scripts/backup_db.py`（用 `sqlite3.backup()`）、`backend/scripts/restore_db.py`（覆盖主库 + 删 `-wal`/`-shm`）。

**验证**：备份 → 恢复 → `gate_all.py` 全绿。

---

## P2 · `core/` 内核抽离

### [ ] P2.1 新建三个内核文件

| 文件 | 职责 |
|---|---|
| `core/events.py` | 事件契约定义 + Redis Stream 发布/订阅 |
| `core/contracts.py` | 跨域公开契约的类型与注册 |
| `core/module_registry.py` | 域清单：路由前缀 / 表 / 事件 / 契约 |

**不改任何业务逻辑。**

### [ ] P2.2 `app/` 根文件归位

`middleware.py`、`monitoring.py`、`exceptions.py`、`cache.py`、`db_router.py` 从 `app/` 根移入 `core/`；`seed.py` 移入 `scripts/admin/`。更新全部 import。

**验证**：

```powershell
cd backend
python scripts/collect_api_surface.py     # 与基线 diff → 期望为空
python scripts/gate_all.py                # 8 门禁全绿
```

---

## P3A · 前端 `src/` 目录分层

### [ ] P3A.1 建立目录骨架

```
src/views/{student,teacher,admin,system}/<shared|pc|tablet|mobile>/
src/components/{common,mobile,domain}/
src/services/api/
```

**说明**：`teacher/` 与 `admin/` 当前为空目录，属**为后续教师端/管理端手写页面预留的入口**——这两端的全部页面（`teacher_*` 8 个、`admin_*` 11 个）目前都在冻结区 `.vtj/vue/`，`src/` 中一个都没有。不预留则届时无处安放。

### [ ] P3A.2 迁移 `src/views/`（27 页）

按**角色 × 设备**双轴归位：

| 目标目录 | 文件 | 数量 |
|---|---|---:|
| `views/student/mobile/` | `mobile_*`（**文件名前缀保留**） | 19 |
| `views/student/shared/` | `achievements` `exercise` `solution` `profile` `feedback` `help` | 6 |
| `views/system/` | `not-found` `unauthorized` | 2 |
| `views/teacher/{shared,pc,tablet,mobile}/` | 预留，当前为空 | 0 |
| `views/admin/{shared,pc,tablet,mobile}/` | 预留，当前为空 | 0 |

同步更新 `src/router/index.ts` 的 import（**只改手写页的 `@/views/*`，92 处 `$vtj/vue/*` 一字不动**）。

**约束**：
- `device.ts`、`resolveDevicePath()`、`DEVICE_ROUTE_MAP` 原样保留（C7）
- `meta: { platform }` 与 `meta: { roles }` 门控保留
- `/tablet/news` 等路由复用 `@/views/mobile_news.vue` 的写法保留——**不为平板新建重复组件**（C5 同理，避免双份维护）
- `AdminLayout.vue` / `TeacherLayout.vue` 位置已正确，不动

### [ ] P3A.3 迁移组件与服务层

`components/common/`（`HelloWorld`、`VtjErrorBoundary`）、`components/mobile/`（`MobileTabBar`）、`components/domain/`（`RecentPracticeRecords`）。

**验证**：

```powershell
npm run typecheck            # 期望 0 错误
npm run build                # 期望成功
# 启动后逐端验证：
#   PC    → http://localhost:8000/            → 应渲染 PC 页
#   手机  → http://localhost:8000/#/mobile/home → 应渲染手机端页
#   平板  → http://localhost:8000/#/tablet/home → 应渲染平板端页
git diff --stat -- .vtj/     # 期望：空
```

**风险**：中。路由 import 改错会导致 404，故必须逐端实测。

---

## P3B · 后端十域逐个搬迁

### [ ] P3B.0 搬迁前置

新建 `scripts/collect_api_surface.py`（AST 提取端点，可重复执行，产物与 `refactor_baseline/api_surface.json` 比对）。

### [ ] P3B.1 ~ P3B.10 逐域搬迁

**顺序**：按端点数升序，先小后大。

| 次序 | 域 | 模块数 | 端点 |
|---|---|---:|---:|
| 1 | `reward` | 3 | 9 |
| 2 | `content` | 3 | 13 |
| 3 | `personal` | 2 | 14 |
| 4 | `identity` | 3 | 16 |
| 5 | `growth` | 3 | 19 |
| 6 | `community` | 2 | 19 |
| 7 | `library` | 3 | 31 |
| 8 | `exam` | 6 | 54 |
| 9 | `catalog` | 6 | 78 |
| 10 | `platform` | 6 | 90 |

**每域步骤**（单任务单提交）：

1. 建 `modules/<domain>/` 目录
2. 迁 `router.py`——**保持 import 路径与 API 前缀不变**
3. 迁 `schema.py` / `models.py` / `service.py`
4. 从 `models.py` 删除迁出的模型定义
5. 更新 `main.py` 的 import
6. 采集 `api_surface.json` 并与基线 diff
7. 8 门禁全绿
8. 提交

**关键约束**：`models.py` 拆分涉及全库外键关系，必须**在单域内完成并验证**，不得跨域累积。

**验证**（每域必做）：

```powershell
cd backend
python scripts/collect_api_surface.py
git diff --stat                     # 期望：api_surface.json 无 diff
python scripts/gate_all.py          # 期望：8 门禁全绿
```

**风险**：中。`catalog`（78 端点）与 `platform`（90 端点）体量最大，安排在末尾，此时流程已成熟。

---

## P4 · 契约改造

### [ ] P4.1 建立边界检查器

新建 `backend/scripts/check_module_boundary.py`（AST 扫描），命中即失败：

- `modules/X/` 内 `from modules.Y.service import ...`
- `modules/X/` 内 `from modules.Y.models import ...`
- 跨域写入他域 ORM 表（白名单外）

接入 `gate_all.py` 的 L4 / L5。

### [ ] P4.2 改造 15 处 `check_and_grant`

按 `refactor_baseline/table_usage.json` 定位的 15 处跨域写调用点逐点改造。

示例（`goals.py:382`）：

```python
# 改造前：直接写他域表
from ...models.models import CoinRecord
CoinRecord(user_id=..., ...); db.add(...)

# 改造后：走公开契约
from ..reward.contract import grant_coins
grant_coins(db, user_id=user.id, amount=50, source="goal_completed")
```

**验证**：

```powershell
python scripts/check_module_boundary.py   # 期望退出码 0
python scripts/gate_all.py               # 期望 L4/L5 通过
```

---

## P5 · 事件总线落地

### [ ] P5.1 定义事件

`user.action.v1`、`growth.awarded.v1`、`achievement.unlocked.v1`（字段只增不删）。

### [ ] P5.2 改造 8 处跨域直调

`auth`、`wrong_questions`、`practice`、`stats`、`forum`、`quotes`、`collection`、`notes` 改为发布 `user.action`。

改造后 `growth` 域成为纯事件生产方，其余域不再 import 它。

**验证**：`refactor_baseline/coupling.json` 对比——跨域条目归零。

---

## P6 · 目录清理与归档

### [ ] P6.1 L1 删除（零风险）

| 项 | 数量/体积 |
|---|---|
| 77 份哈希冗余数据库文件 | 1,411.9 MB |
| `mineru_verify_out/` | 5 文件 |
| `backend/mineru_1787720560/` | 8 文件 |
| `backend_pid.txt`、`backend_err/out/run.log` | 4 文件 |
| `backend/_*.txt`（探测输出） | 5 文件 |
| `git_diff_qi.txt`、`frontend_run.err`/`.log` | 3 文件 |
| `src/router/index.ts.bak`、`src/.DS_Store` | 2 文件 |
| `backend/scripts/题库.db` | 0 字节 |
| `temp_pdf_images/`、`tmp/`、根 `uploads/` | 41 + 2 + 0 |
| `backend/data/` 根散落 `xingce_regression_*` / `type_repair_*.log` | ~40 文件 |
| `env.json` / `env.local.json` / `env.sit.json` / `env.uat.json` | 4 空壳 |
| `test-question-render.mjs` | 1 文件 |
| 26 个未登记的孤儿 `.vtj/files/*.json` | **删除前须确认无引用** |

### [ ] P6.2 L2 归档（不删除、不入库 Git）

| 目标 | 归档位置 |
|---|---|
| 41 份唯一备份（5,089.6 MB） | `data/archive/`，按「最近 7 天 + 每周一份」 |
| `solve_problems_files/` 134 md | `docs/{design,plans,archive}/`，同主题只留终版 |
| `backend/scripts/` 90 个 | `scripts/{gates,migrate,repair,probe,admin,verify}/` |
| 3 份重复 regroup 脚本 | 合并为 1 份 |
| AI 工具目录 6 处 + `vtj-mcp-server/` | `.agent/{skills,tools,plans}/` + `README.md` 索引 |
| `CLAUDE.md/`（目录） | `docs/ai-commands/` |
| `scripts/git-hooks/pre-commit` | 随 `.pre-commit-config.yaml` 保留，移入 `scripts/` 分类 |

**`probe/` 必须保留且保证可复跑**——它是本方案全部实测结论的唯一来源。

---

## 附录 A · 逐阶段验收判据

| 阶段 | 完成判据（全部满足） |
|---|---|
| P0 | `pytest` error = 0；`git ls-files backend/.env` 无输出；`check_secrets.py` 退出码 0；旧密钥 token 返回 401；gRPC 删除后服务正常启动 |
| P1 | `docker compose ps` 全部 healthy；`/health` 200；镜像内 `app/static` 为空；parser 的 HTTP 与 subprocess 双路径均验证通过 |
| P2 | `api_surface.json` diff 为空；8 门禁全绿 |
| P3A | `npm run typecheck` 0 错误；`npm run build` 成功；PC/手机/平板三端路由实测可达；`git diff -- .vtj/` 为空 |
| P3B | 十域逐一完成，每域 `api_surface.json` diff 为空且门禁全绿 |
| P4 | `check_module_boundary.py` 退出码 0 |
| P5 | `coupling.json` 跨域条目归零 |
| P6 | 41 份唯一备份 SHA-256 全部可校验；`backend/data` 体积下降 ≥ 1,411.9 MB；`audit/` 与 `待推断题目清单_*.csv` 完好 |

## 附录 B · 用户待办

| # | 事项 | 阶段 | 紧急度 |
|---|---|---|:-:|
| 1 | ~~DeepSeek 密钥吊销~~ | — | ✅ 已完成 |
| 2 | 生成新 `JWT_SECRET_KEY` 并写入 `backend/.env` | P0.2-f | 🔴 |
| 3 | 授权 `git filter-repo` 清除历史旧密钥 | P0.2-g | 🔴 |
| 4 | 确认 `packages/shared-store`（零引用）去留 | P6 | 🟡 |
| 5 | 确认 `linxitie.policy-exam-bank-mobile` / `-tablet` 去留 | P6 | 🟡 |
| 6 | 后续重点：教师端题目导入改造 + 三端「导入-展示-通信」数据一致性——**必须在 P3B 完成后再动** | P3B 之后 | 🟠 |

---

**计划结束。请审核。**