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

### [x] P0.1 修复索引同名冲突

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

### [x] P0.2 凭据治理

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

### [x] P0.3 删除 gRPC / Canal 僵尸代码

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

**实测结果（2026-10-16，提交 `c93611a`）**：

| 验证项 | 结果 |
|---|---|
| 应用可构建 | ✅ 359 条路由 |
| 关键端点 | ✅ `/health` `/metrics` `/api/coins/overview` `/api/forum/posts` 均在 |
| pytest 回归 | ✅ 与 P0.1 后完全一致：0 error / 265 passed / 31 failed |
| 门禁 | ⚠️ **7/8**，L2 失败（见下） |

**L2 失败的归因（已取证，非本次引入）**：

L2 通过 `subprocess` 调用 `verify_xingce_regression.py`，该脚本**仅** `import app.services.text_parser`，数据源为 `题库/行测` 的 85 套 PDF。本次 P0 改动的 `models.py`、`config.py`、`main.py`、`.md` 文档**均不在其依赖链上**，`text_parser.py` 与 PDF 语料亦未改动。

| 判定项 | 值 |
|---|---|
| 材料块数 | 306 == 306 ✅ |
| 材料块内题号数 | 0 == 0 ✅ |
| 材料块图片归属错位数 | 0 / 2512 == 0 ✅ |
| 材料页表格行归属正确率 | 1.0000 == 1.0 ✅ |
| **分节题号区间全等套数** | **4 / 85 ❌** |

材料守卫四项全通过，失败发生在「分节题号区间全等」这一项，属**行测 PDF 解析的既有问题**，对应设计规格 §2.5 记录的 `qnums_contiguous=63.53%` 与《行测题目导入优化方案》§7.1 记录的 T16 阻塞（30 个伪题号）。

**结论**：P0 验收判据「8 门禁全绿」**无法达成**，L2 需单独修复行测解析，与容器化/模块化重构无关。已登记为 P0.5。

---

### [x] P0.4 重写 14 个过时断言

P0.1 修复后，原本在 fixture 阶段中断的 14 个用例开始执行，暴露出**测试期望过时**（非产品缺陷）。已取证分类：

| 失效类型 | 数量 | 涉及 |
|---|---:|---|
| `assert 404 == 401` / `405 == 401` | 5 | 端点已不存在或方法不匹配 |
| `assert 422 == 401` | 4 | Pydantic 入参契约已变，先触发校验而非鉴权 |
| `JSONDecodeError` | 2 | `/` 与 `/metrics/endpoints` 已被 SPA fallback 接管，返回 HTML |
| `assert 422 == 200` / `404 == 200` / `1 == 5` | 3 | 请求体或查询参数与当前契约不符 |

涉及文件：`tests/test_api.py`（13）、`tests/test_batch_parsed_import.py`（1）。

**动作**：按当前 API 契约重写断言，**不得**为了让测试通过而修改产品代码。

**实际修订**（提交 `7f7db88`，仅改测试文件）：

- 路径订正：`/api/auth/me`→`/api/auth/profile`；`/api/exam/*`→`/api/exams/*`（实际为复数）；`/api/papers/`（无 GET）→`/api/papers/list`；`/api/questions/subjects`→`/api/quick-practice/subjects`；`/api/questions/types`→`/api/practice/type-summary`
- 登录端点为 OAuth2PasswordRequestForm，此前以 JSON 提交恒得 422，改为表单提交
- 契约订正：`/` 已被 SPA fallback 接管，返回 index.html；`/api/questions/{id}`、`/api/exams/{paper_id}` 为公开读
- 两处**真实产品缺陷**用 `strict=True` 的 xfail 记录，不掩盖也不伪装通过：
  1. `/metrics/endpoints`、`/metrics/reset` 注册于 SPA fallback 之后，被 `/{full_path:path}` 抢先匹配，返回 HTML
  2. 建卷时 `_get_or_create_import_paper` 未把 `question_count` 写入 `ExamPaper`，关联 5 题后该字段仍为 1（`question_import.py:1258` 的累加分支依赖初值非 0）

**验证**：failed 由 31 降至 **17**，14 个目标断言全部解决（12 个转为正确断言，2 个转为文档化 xfail）。

```
重写前  17 failed / 265 passed / 1 xfailed / 0 error
重写后  17 failed / 278 passed / 3 xfailed / 0 error
```

剩余 17 个为 `test_security.py` 等既有问题，不在本次范围。

**风险**：低。仅改测试文件。

---

### [x] P0.5 诊断 L2 门禁失败根因（只诊断，不改码）

**用户决策**（2026-10-16）：只诊断、不改码，产出取证报告；不纳入本次重构范围。

#### 结论：判据假阳性，不是解析器缺陷

L2 失败项「分节题号区间全等套数 4/85」的根因在**门禁 harness 自身的题号正则**，而非 `text_parser.py`。

判据实现在 `verify_xingce_regression.py:197-209`：`intervals()` 用正则
`(?m)^\s*(\d{1,3})\s*[.．、]` 在每节文本内提取题号，取 `min`/`max`，
要求题本与答案本**逐节区间完全相等**。该正则匹配的是「行首 1–3 位数字 + `.．、`」，
而不是「题号」——它会把下列非题号内容一并当作题号：

- 行首小数：`2.5万元` → 命中 `2`，`352.7%` → 命中 `352`
- 前导零：`0.`
- 资料分析材料内的数据表行首数字

一旦命中，所在分节的 `min` 被拉低、`max` 被拉高，区间立即与题本不等。

#### 取证证据

逐节实测 85 套（题本/答案本配对完整），仅替换 harness 的题号正则，`text_parser.py` 零改动：

| 判据 | 区间全等套数 |
|---|---:|
| 原判据 `^\s*(\d{1,3})\s*[.．、]` | **4 / 85** |
| 排除小数 `^\s*(\d{1,3})\s*[.．、](?!\d)` | **74 / 85** |

抽样分歧点（真实最大题号已核对，非钳制结果）：

| 套 | 节 | QB 区间 | ANS 区间 |
|---|---|---|---|
| 内蒙古 2022 | 常识判断 | [1..20] n=20 | [0..20] n=21 ← 行首 `0.` |
| 内蒙古 2022 | 资料分析 | [106..120] n=15 | [10..120] n=18 ← 行首 `10.` |
| 内蒙古 2025 | 判断推理 | [76..110] n=35 | [2..110] n=36 ← 行首 `2.` |
| 内蒙古 2025 | 资料分析 | [111..125] n=15 | [0..352] n=18 ← 行首 `0.` 与 `352.` |

以上四套在 `STRICT_RE` 下**全部对齐为 True**。

与回归报告自记的既有缺陷完全吻合：`伪题号总数: 30（行测特有：解析中「小数+单位」落在行首）`。

#### 反证：分节与解析本体均正常

若为解析器缺陷，分节切分或答案锚点必然先失配。实测均正常：

| 指标 | 实测 | 判读 |
|---|---|---|
| 分节头序列全等套数 | **85 / 85** | 分节切分完全正确 |
| 分节头命中(题本/解析) | **454 / 454** | 分节无遗漏 |
| 解析缺答案锚点文件数 | 0（PASS） | 答案锚点全部命中 |
| 题本块总数 / 答案锚点总数 | 10182 / 10255 | 两侧均完整解析 |

即：**分节与解析本体健康，仅 harness 的题号提取口径过宽。**

#### 对 L0 红线的影响

诊断全程只读。`gate_l0_redlines.py` 复跑 **7/7 全绿**，
`extract_question_blocks` 指纹保持 `len=6717` 未变，工作区 clean。

#### 正确修法（本次不执行）

修 `verify_xingce_regression.py` 的题号正则（收紧为排除小数、或改用答案锚点正则
`_LOCAL_ANSWER_RE` 反推题号），**不碰 `text_parser.py`**，因此不触发 L0 哈希红线。
该文件不在 L0 保护清单内，属低风险改动。

剩余 11 套在 `STRICT_RE` 下仍不等，需在收紧正则后另行取证。

#### 处置

按用户决策，P0.5 **不纳入本次范围**。L2 标记为「已知假阳性，另立工单」，
P0 以「除 L2 外全绿」结项，进入 P1 容器化落地。

---

## P1 · 容器化落地

### [x] P1.1 后端镜像（文件已就绪，构建验证待补）

新增 `backend/Dockerfile`（`python:3.13-slim`，提交 `5a671c5`）。

**实测驱动的事实**（非照抄计划）：

| 事实 | 实测值 | 对镜像的影响 |
|---|---|---|
| 本机 Python | 3.13.5 | 基镜像定 `python:3.13-slim` |
| `app/static/` | **94814 文件 / 4.27 GB** | R7 红线，必须排除，走 qimg 卷 |
| playwright 使用位置 | `exam_scraper.py`、`news_scraper.py`、`recruitment_scraper.py` | **生产代码在用**，chromium 必须入镜像，非仅门禁需要 |
| `/health` | `main.py:608` | HEALTHCHECK 复用，不另造端点 |
| 启动命令 | `start.py:20` = `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` | 入口脚本沿用同一组参数 |

**镜像要点**：

- 依赖单独成层（业务代码频繁改动时可命中缓存）
- 非 root 运行（`app` 用户）；`tini` 作 PID 1 保证 uvicorn 优雅退出
- `HEALTHCHECK` 复用 `main.py:608` 的 `/health`，`curl` 为 slim 镜像显式安装
- `.dockerignore` 排除 `data/*` 后放行 `data/gates`、`data/refactor_baseline`（纯 JSON 基线），
  SQLite 主库、41 份 `.bak*`、`audit/`、`snapshots/`、`text_cache/`、`xingce_cache/` 一律不入镜像

**编写过程中自查并修正的两处缺陷**：

1. 入口脚本最初**未被 `COPY`**，`chmod +x` 会在文件缺失时失败导致构建中断 —— 已补 `COPY docker-entrypoint.sh`
2. 最初声明了 `VOLUME [data, uploads, app/static]` —— 有害：`docker run` 未带 `-v` 时会生成匿名卷，
   `app/static` 为空即全站裂图（R7 后果），且匿名卷静默堆积难回收 —— 已删除，改为仅由 compose 显式挂载

**入口脚本职责**（`docker-entrypoint.sh`）：

- **R10**：仅当「主库缺失但 `-wal`/`-shm` 存在」时清理孤儿 WAL；主库存在时一律保留 `-wal`/`-shm`（那是未落盘数据的正常状态）
- R7 自检：`app/static` 为空时打印告警，提示题目图片将全部 404
- 凭据自检：`.dockerignore` 已排除 `.env*`，入口只做存在性提醒，不打印任何值
- 不做重启循环 —— 开发机的看门狗逻辑在容器里由 orchestrator 负责

#### ⚠️ 构建验证未完成（环境阻塞，非代码问题）

**本机未安装 docker**（`docker` 命令不存在），计划中的以下验证**无法执行**：

```powershell
docker build -t liankao/backend:test backend          # 未执行
docker images liankao/backend:test                   # 未执行
docker run --rm liankao/backend:test sh -c "ls app/static | wc -l"   # 未执行
```

已完成的替代静态校验（全部 PASS）：

| 校验项 | 结果 |
|---|---|
| 三个文件行尾符 | 纯 LF，CRLF=0（Windows 下 CRLF 会导致脚本 `command not found`） |
| `sh -n docker-entrypoint.sh` | PASS |
| `COPY` 目标路径存在性 | `app` / `data/gates` / `data/refactor_baseline` / `requirements.txt` / `docker-entrypoint.sh` 均存在 |
| `.gitignore` 误挡检查 | 三个新文件均未被排除 |
| `.dockerignore` 关键规则 | `app/static/`、`data/*` + `!data/gates`、`\.env`、`tests/` 均在位 |

**结论**：镜像文件已就绪且静态自洽，但**镜像体积与 `app/static` 为空两项只能在装有 docker 的环境上实测**。
P1.1 的「验证」栏保持未勾选，待具备 docker 的机器补跑后再勾。

**风险**：低（纯新增文件，未触碰任何现有代码与路由）。

### [x] P1.2 MinerU / OCR sidecar（提交 `5bc9212`）

新增 `backend/parser/{Dockerfile,app.py,requirements.txt}`；改造 `app/core/config.py` 与
`app/services/mineru_service.py`。

**改造点**：

| 文件 | 改动 |
|---|---|
| `app/core/config.py` | 新增 `PARSER_URL: str = Field("", env="PARSER_URL")`（`.env.example` 早已预留该键，但 config 中缺字段） |
| `mineru_service.py` | 新增 `_parser_url()`、`call_parser_http()`；`is_enabled()` 增加 sidecar 分支；`extract_text_sync()` 在配置了 sidecar 时优先走 HTTP |

#### 关键设计：开发机行为逐字节不变

`extract_text_sync()` 开头仅插入「若 `_parser_url()` 非空则先试 HTTP」一段；
`PARSER_URL` 未配置时该段整体跳过，走原有 subprocess 路径。
`call_parser_http()` 与既有 `extract_text_sync()` 同样遵守「绝不抛异常、失败返回 `None`」的模块契约。

`is_enabled()` 新增分支的必要性：容器内 MinerU 不在主进程（Python 3.13 装不了），
若仍只认 `MINERU_PYTHON` 文件是否存在，sidecar 模式下会被误判为不可用。

#### 实测：16 项检查，0 失败

用真实 mock HTTP 服务覆盖四条路径（非桩断言，每类都校验「确实发出过请求」）：

```
=== A. PARSER_URL 未配置：开发机行为须与改造前一致 ===
  PASS  _parser_url() 返回空串
  PASS  未配置 sidecar 时绝不发起 HTTP        hits=0

=== B. PARSER_URL 指向可用 sidecar ===
  PASS  is_enabled() 为 True（无需本地 venv）
  PASS  call_parser_http 取回 markdown         '# title\nbody text'
  PASS  extract_text_sync 走通 sidecar
  PASS  sidecar 成功后不再调子进程              hits=1

=== C. sidecar 各类异常必须静默回落 ===
  PASS  markdown 为空 → None      PASS 确实发过请求
  PASS  返回非 JSON → None        PASS 确实发过请求
  PASS  HTTP 500     → None       PASS 确实发过请求
  PASS  JSON 无 markdown 键 → None  PASS 确实发过请求

=== D. sidecar 完全不可达（连接被拒）===
  PASS  返回 None 而非抛异常
```

#### 过程中发现并修复的一次真实回归

首版在 `extract_text_sync()` 加了守卫 `if not py or not os.path.isfile(py): return None`，
意在避免容器内对不存在的解释器发起子进程。**这打挂了 1 个原本通过的测试**：

```
tests/test_mineru_service.py::TestExtractTextSync::test_success_returns_md_content
  AssertionError: assert None == '# 第1题 题干\nA. 选项'
  [mineru] 无可用解析路径：sidecar 未产出且 MINERU_PYTHON 不存在(D:\mineru-env\Scripts\python.exe)
```

该测试 mock 了 `subprocess.run`，依赖原行为——`MINERU_PYTHON` 路径不必真实存在。
守卫破坏了「行为与改造前逐字节一致」这条核心不变量，已移除。

移除后的依据：`subprocess.run` 对不存在的解释器会立刻抛 `FileNotFoundError`，
被既有 `except Exception` 捕获并返回 `None`，代价可忽略，本就无需守卫。

**回归确认**：`17 failed / 278 passed / 3 xfailed`，与 P1.2 改动前基线完全一致。

#### 侧车契约

```
POST /parse   multipart/form-data 字段 file（扫描件 PDF）
              → 200 {"markdown": "...", "chars": N}
              → 400 空文件 / 413 超限 / 502 未产出 / 503 队列满 / 504 超时 / 500 异常
GET  /health  → 200 {"ok": true, "mineru": bool}
```

镜像用 `python:3.11-slim`（MinerU 支持上限 3.12）；模型缓存挂 `/root/.cache` 卷，
避免每次重建镜像重新下载数 GB 权重。

#### ⚠️ 镜像构建验证待补

本机无 docker，`docker build -t liankao/parser:test backend/parser` 与
`docker compose up -d parser` 均**未执行**。已完成替代静态校验：三个新文件行尾符纯 LF、
`parser/app.py` 可正常导入、上述 16 项运行时行为实测通过。

**风险**：中。解析链路是导入核心。HTTP 路径与静默回退已实测，但 sidecar 镜像本身未构建过，
`mineru[core]` 能否在 `python:3.11-slim` 上装成待验证。

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

### [x] P1.4 备份与回滚脚本（提交 `d3f88d9`）

新增 `backend/scripts/backup_db.py`、`backend/scripts/restore_db.py`，落实 R10 红线。

#### 为什么必须用 `sqlite3.backup()`

实测本库现状：主库 **292.31 MB**、`-wal` **4.60 MB**、`-shm` 32 KB。
WAL 模式下已提交数据可能仍只存在于 `-wal`，`shutil.copy2` 拷到的主库是一份
**缺少最近提交且不自知的不一致快照**。只有 `sqlite3.backup()` 走 SQLite 自身读事务，
在一致时间点取快照。

#### 实测证据：备份确实捕获了 WAL 独有数据

造库后保持连接不关，使第 51 行只存在于 `-wal`：

```
备份含 51 行          实测 51
备份含 WAL 独有行      ('wal-only',)      ← shutil.copy2 做不到这一点
```

对真实主库实测：292.31 MB、`integrity ok`、268 个对象。

#### 恢复的三道安全闸

| 闸 | 行为 |
|---|---|
| 1 | 备份文件须能打开且 `integrity_check = ok`，否则拒绝 |
| 2 | 覆盖前**自动快照当前状态**，使恢复本身可回退 |
| 3 | 需显式 `--yes` 或交互确认 |
| 4 | 占用预检：目标库或侧车被占用时立即拒绝（见下） |

#### 实测中发现并修复的两个真实缺陷

**缺陷一：占用时报错不可操作，且留下无用快照。**
首版在 `-wal` 被其他进程持有时报 `[WinError 32]` 后退出 1，且已建好一份注定用不上的
`pre_restore` 快照。已加入 `_probe_lock()` 预检（改到临时名再改回，非破坏性；
比 `open()` 可靠，因 Python `open()` 默认允许多进程共享，探测不出占用），
**置于建快照之前**。修正后：

```
被占用时退出码 3        rc=3
提示『拒绝恢复』         PASS
提示先停应用             PASS
被拒时不留无用快照       backups/ 有 0 个文件
被拒后主库完好           ok
-wal 仍在（未被误删）    PASS
```

**缺陷二：报告失真。** 脚本打印「将清理 -wal/-shm」却未打印「已删除」——
因为 `_snapshot_current()` 打开并关闭连接时 SQLite 已自动 checkpoint 侧车，
显式删除循环发现文件不存在而跳过。已如实报告两种结果。

#### 决定性判据：旧 WAL 未泄漏进恢复后的库

若恢复时未清除旧 `-wal`，SQLite 会将其作为增量重放到新主库，表现为备份中不存在的行、
主键重复或库损坏。以数据层面断言（非文件是否存在）：

```
完整性 ok              ok
行数与备份完全一致      恢复后 1 vs 备份 1
无主键重复             重复 id 0 组
无备份外的多余行        多余行 0
```

> 测试过程中修正过一次**测量陷阱**：断言「`-wal` 文件不存在」是错的——
> 脚本末尾的只读 `_verify` 重开库时会新建**全新的空侧车**。这些侧车与新主库一致，
> 非旧库残留。改用数据层面判据。

#### 回环实测汇总

两套临时库回环测试，**失败项 0**（全程不触碰真实主库）：
- 基础回环：造库 → 备份 → 破坏（删行+改值）→ dry-run 不落盘 → 恢复 → 数据核对 → 拒绝非法输入
- WAL 回环：独立进程持库制造活跃 `-wal` → 跨进程备份 → 占用被拒 → 停止进程 → 恢复并清理侧车

`gate_all.py` 复跑 **7/8**，L2 仍是 P0.5 已确诊的判据假阳性，无新增回归。

**风险**：低（纯新增运维脚本，未触碰业务代码）。但 `restore_db.py` 的失败模式是数据丢失，
其四道闸与顺序约束已在代码注释中固化。

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