# 招考信息任务 — 隔离工作线路（Git Worktree Runbook）

> **目的**：在不干扰 `question-import-full-repair-execution`（2026-10-04 启动，仍在进行）的前提下，另开一条独立工作线路完成招考信息全部任务。
> **生成日期**：2026-10-09
> **状态**：🟡 待你书面批准后执行

---

## 〇、为什么必须隔离（实测现状）

| 项 | 主工作区实测值 | 风险 |
|---|---|---|
| 当前分支 | `fix/vite-mobile-connection` | — |
| HEAD | `c77b084` `fix(images): 修复教师端题干摘要截断图片与解析显示路径文本` | — |
| **未提交改动** | **25 项**（`.omo/` 10、`solve_problems_files/` 7、`backend/` 3、其他 5） | 我们的改动会与之混杂，git diff 审查无法区分来源 |
| 活跃会话 | `.omo/boulder.json` → `question-import-full-repair-execution`，**无 `ended_at`（进行中）** | 两个会话争抢同一 boulder 状态 |
| 端口 8000 | **已占用**（PID 31872，uvicorn） | 后端无法并行启动 |
| 端口 9527 | **已占用**（PID 40472，Vite） | 前端无法并行启动 |
| 数据库 | `backend/data/question_bank.db` **163MB**，正在被运行中的爬虫写入 | 我们的 P0 加列 + 回填 787 条会**污染**它 |

---

## 一、隔离方案：Git Worktree（项目已有先例）

项目已存在 3 个 worktree（`badge-engine-v4`、`feat-exam-optimize`、`teacher-optimization`），说明这是**本项目既定做法**。

### 1.1 隔离后资源分配（无一项共享）

| 资源 | 主工作区（题目导入会话，保持不动） | 新 worktree（本任务） | 隔离机制 |
|---|---|---|---|
| Git 分支 | `fix/vite-mobile-connection` | **`feat/recruitment-daily-refresh`** | worktree 独立分支 |
| 工作目录 | `D:\砺安题库\砺安题库` | **`D:\砺安题库\砺安题库\.worktrees\recruitment-refresh`** | 独立文件系统 |
| 未提交改动 | 25 项原地保留 | **0** | worktree 从 HEAD 拉取，不含未提交内容 |
| 后端端口 | 8000（PID 31872） | **8001** | 环境变量 `PORT` 覆盖 |
| Vite 端口 | 9527（PID 40472） | **9530** | `VITE_PORT` 环境变量 |
| 后端数据库 | `backend/data/question_bank.db`（163MB） | **worktree 自建新库** | `.gitignore:57 backend/data/*` 忽略 → 新 worktree 无库 |
| 日志 | `logs/app.log` | **worktree 独立 logs** | `logs` 在 .gitignore |
| `node_modules` | 已安装 | **worktree 独立安装** | `node_modules` 在 .gitignore |
| `.omo/boulder.json` | 已修改（会话进行中） | **worktree 独立副本**（取 HEAD 版本） | `.omo/` 被 git 跟踪，各自独立 |
| **gRPC 50051** | **正在监听**（PID 31872） | **无法绑定（主动让出）** | 见 §1.3 |

### 1.2 关键优势：数据库天然隔离

```
.gitignore:57  backend/data/*
```
`question_bank.db` 被忽略 → **新 worktree 里根本没有这个文件**。

我们 P0 阶段的「新增 `publish_date` 列 + 回填 787 条历史数据 + 排序改造」全部发生在**自己的新库**上，**对题目导入会话正在使用的 163MB 生产库零影响**。

> `backend/data/` 下 9 个被跟踪的文件（`gates/*.json`、`*_baseline.txt` 等）是门禁基线，会随 worktree 一并带过去 —— 它们是**只读基线**，正是我们要用的。

### 1.3 gRPC 50051 端口：无法隔离，但安全方向正确（已实测）

**排查结论**：

| 检查点 | 实测结果 |
|---|---|
| 端口定义位置 | `backend/app/grpc_service.py:190` `def __init__(self, host="0.0.0.0", port=50051)` |
| 单例实例化 | `grpc_service.py:454` `grpc_service = GRPCService()` —— **无参数**，故取默认值 50051 |
| 是否有配置项 | `core/config.py` 扫描 `GRPC` → **零命中**，端口完全硬编码 |
| 是否可环境变量覆盖 | ❌ **不可**。它是函数默认参数，不走 `settings` |
| 当前占用 | 主后端 PID 31872 正监听 **50051** |

**实际行为**：

1. worktree 后端启动 → `grpc_service.start()` 绑定 50051 失败
2. 但 `setup_grpc_service()` **内部已有独立 `try/except`**（`grpc_service.py` 内层），仅打 warning，**不抛出**
3. 因此 `main.py:475-491` 的外层 3 次重试逻辑**根本不会被触发**（无异常冒泡），不浪费启动时间

**安全方向正确**：**worktree 是绑定失败的一方**，主后端的 50051 **完好无损**，题目导入会话的 gRPC 不受任何影响。

**对本任务的影响：无。** 招考信息模块是纯 HTTP + SQLite，链路为
`/api/recruitment`（FastAPI HTTP）→ SQLAlchemy → SQLite
**完全不经过 gRPC**（gRPC 仅服务于 `Exam` / `QuestionBank` 服务）。

**已知副作用**：worktree 后端启动日志会出现一条
`gRPC 服务初始化失败（不影响 HTTP 服务）` 的 WARNING。
这是**预期现象，不是故障**，不得误判为启动失败。

**若将来需要 worktree 的 gRPC**（本任务不需要）：可在 worktree 分支内改
`grpc_service.py:454` 为 `grpc_service = GRPCService(port=int(os.getenv("GRPC_PORT", "50051")))`，
属分支内改动，默认值不变。**本轮不做，保持零改动。**

### 1.4 方案自检结果（本轮实测，方案定稿前完成）

> 对隔离方案中每条**承重前提**逐项实证验证，不接受"应该可以"式推断。

| # | 待验证前提 | 验证方式 | 结果 |
|---|---|---|---|
| V1 | pydantic-settings 中**环境变量优先于 `.env`**（后端端口隔离的全部依据） | 设 `PORT=8001` 后读 `settings.PORT` | ✅ **通过** —— 实测 `settings.PORT = 8001` |
| V2 | `.env` 的 `PORT=8000` 保持不动即可（零文件改动） | V1 已证明环境变量覆盖；`.env` 不需修改 | ✅ **通过** |
| V3 | Vite 代理目标可用环境变量切换 | 读 `proxy.config.ts:7` | ✅ **通过** —— `process.env.DEV_BACKEND_ORIGIN \|\| 'http://127.0.0.1:8000'` |
| V4 | Vite 端口是否硬编码（决定前端是否需改文件） | 读 `vite.config.ts:8,90,104` | ⚠️ **硬编码** `const DEV_PORT = 9527` 且有 `clientPort: DEV_PORT` → **需 1 行改动**（仅本分支） |
| V5 | 题目导入会话的数据库是否会被波及 | `git check-ignore backend/data/question_bank.db` | ✅ **通过** —— 被 `.gitignore:57 backend/data/*` 忽略，**worktree 无此文件** |
| V6 | 是否存在其他硬编码端口撞车 | 扫 `backend/app/**/*.py` 端口字面量 | ⚠️ **发现 gRPC 50051 硬编码** → 详见 §1.3，**安全方向正确，无功能影响** |
| V7 | 前端 WebSocket 是否绑定固定端口（会否绕过 Vite 端口） | 读 `src/auth.ts:226` | ✅ **通过** —— 用 `window.location.host` 拼接，**自动跟随 Vite 端口** |
| V8 | 计划文件是否会与主工作区未提交文件撞名 | 比对 25 项未提交的 `solve_problems_files/` 文件名 | ✅ **通过** —— 我方均以 `recruitment-*` 命名，无同名冲突 |

**自检结论**：V1/V2/V3/V5/V7/V8 **直接通过**；V4 需 1 行改动（已在 §二 步骤 4.2 明确）；
V6 发现一处硬编码端口（gRPC 50051），经分析**对本任务无功能影响且安全方向正确**（§1.3）。

**未发现会阻断隔离执行的缺陷。方案可执行。**

---

## 二、执行步骤（逐条含验证门禁）

### 步骤 1：创建 worktree

```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
cd D:\砺安题库\砺安题库
git worktree add .worktrees/recruitment-refresh -b feat/recruitment-daily-refresh
```

**验证门禁 1** ✅
```powershell
git worktree list                       # 应出现 5 条，新条目分支为 feat/recruitment-daily-refresh
cd .worktrees/recruitment-refresh
git branch --show-current               # 必须输出 feat/recruitment-daily-refresh
@(git status --porcelain).Count         # 必须输出 0
```

> ⚠️ 若提示分支已存在，先 `git branch -D feat/recruitment-daily-refresh` 再重试。

---

### 步骤 2：安装前端依赖（独立）

```powershell
cd D:\砺安题库\砺安题库\.worktrees\recruitment-refresh
npm ci
```

**验证门禁 2** ✅ `Test-Path node_modules/.bin/vite` → `True`

> **不用 junction 复用主目录的 `node_modules`** —— 那样两个 Vite 会共用 `node_modules/.vite` 缓存目录，产生写入竞争。

---

### 步骤 3：后端依赖确认

```powershell
cd D:\砺安题库\砺安题库\.worktrees\recruitment-refresh\backend
python -c "import importlib.util as u; print('playwright', bool(u.find_spec('playwright'))); print('stealth', bool(u.find_spec('playwright_stealth')))"
```

**验证门禁 3** ✅ 两项均为 `True`（与主环境共用全局 Python 环境，预期一致）

> 若 `playwright` 缺失：`python -m playwright install chromium`（浏览器二进制是全局缓存，已装则跳过）

---

### 步骤 4：端口隔离配置

**4.1 后端 —— 无需改文件，用环境变量**

`backend/app/core/config.py:42` 定义 `PORT: int = Field(8000, env="PORT")`，pydantic-settings 中**真实环境变量优先级高于 `.env` 文件**，因此：

```powershell
$env:PORT = "8001"
$env:DEV_BACKEND_ORIGIN = "http://127.0.0.1:8001"   # proxy.config.ts:7 已支持该变量
```

> ✅ **零文件改动**。`.env` 保持 `PORT=8000` 不动，合并回主线时不会有任何端口污染。

**4.2 Vite —— 需 1 行改动（仅本分支）**

`vite.config.ts:8` 为 `const DEV_PORT = 9527;`（硬编码），且 L104 有 `clientPort: DEV_PORT`。仅用 CLI `--port` 会导致 HMR 客户端仍指向 9527 而失效。

**改动（`vite.config.ts:8`，单行）**：
```ts
const DEV_PORT = Number(process.env.VITE_PORT) || 9527;
```

启动时：
```powershell
$env:VITE_PORT = "9530"
```

> ✅ 默认值仍为 9527，**合并回主线后行为完全不变**，不会影响主工作区。

**验证门禁 4** ✅ 启动 worktree 后端与 Vite，分别确认：
- `http://127.0.0.1:8001/docs` 返回 200
- `http://localhost:9530` 返回 200
- 主工作区 `http://localhost:8000` 与 `http://localhost:9527` **仍正常**（未被抢占）

---

### 步骤 5：数据库初始化与 M0 基线采集

```powershell
cd D:\砺安题库\砺安题库\.worktrees\recruitment-refresh\backend
New-Item -ItemType Directory -Force -Path data, logs | Out-Null
$env:PORT = "8001"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

**M0 基线采集（重构前，缺一不可）**：
```
1. 在 worktree 后端（新库）中执行一次现网 rszk 爬虫
2. 导出 (title, url, category) 三元组 → backend/data/baseline_rszk_before.json
3. M0 重构完成后重跑，导出 baseline_rszk_after.json
4. 逐行 diff —— 必须完全一致（这是 M0 的硬门槛）
```

**验证门禁 5** ✅ `baseline_rszk_after.json` 与 `before` **零差异**；不通过则 M0 回滚

---

### 步骤 6：在 worktree 中推进两份方案

| 顺序 | 计划 | 阶段 |
|---|---|---|
| ① | `recruitment-daily-refresh-fix.md` | **P0**（publish_date 列 + 真实排序 + 回填） |
| ② | `recruitment-multisource-expansion.md` | **M0**（适配器框架，rszk 行为零变化） |
| ③ | `recruitment-multisource-expansion.md` | **M1**（事业单位源 mohrss） |

全程在 worktree 内执行，主工作区**不产生任何改动**。

---

### 步骤 7：合并回主线

```powershell
cd D:\砺安题库\砺安题库
# 前置：主工作区必须干净（或已 commit），否则先收尾题目导入会话
git status --porcelain            # 必须为空或已提交
git checkout fix/vite-mobile-connection
git merge --no-ff feat/recruitment-daily-refresh
```

**验证门禁 7** ✅
- 合并无冲突
- `npm run prebuild` 通过（`verify-project-health.mjs`）
- `python scripts/gate_all.py --quick` 通过
- 六个功能模块（题库/练习/错题/成绩/论坛/备考资料）无回归

> ⚠️ **冲突即 `git merge --abort`**，人工介入，**不得强行解决**。

**合并后清理**：
```powershell
git worktree remove .worktrees/recruitment-refresh
git branch -D feat/recruitment-daily-refresh
```

---

## 三、已预判的合并冲突点

| 冲突点 | 原因 | 预置处理 |
|---|---|---|
| **`.omo/boulder.json`** | 主工作区已修改（会话进行中，10 项未提交），本分支也会改 | 合并前先把主工作区的 `.omo/` 改动提交；本分支的 `.omo/` 状态**不作为交付物**，合并时若有冲突**一律保留主线版本** |
| **`.omo/plans/*.md`** | 两边都有计划文件 | 我方文件名唯一（`recruitment-*`），无同名冲突 |
| **`solve_problems_files/*.md`** | 主工作区 7 项未提交（题目导入方案） | 我方文件名唯一，无同名冲突 |
| **`vite.config.ts:8`** | 主线可能后续也改端口 | 单行改动，默认值不变；冲突时**保留双方语义的合并**（`Number(process.env.VITE_PORT) || 9527`） |
| **`backend/.env` 的 `PORT`** | **我方不改此文件** | 已用环境变量规避，零冲突 |

---

## 四、隔离有效性验证（必须全部通过）

| # | 验证项 | 命令/方法 | 判据 |
|---|---|---|---|
| 1 | worktree 独立分支 | `git branch --show-current` | `feat/recruitment-daily-refresh` |
| 2 | worktree 无未提交改动 | `@(git status --porcelain).Count` | `0` |
| 3 | **主工作区 25 项改动原封不动** | `git status --porcelain`（在主目录执行） | 仍为 25 项，内容不变 |
| 4 | 题目导入会话不受扰动 | 主工作区 boulder `active_plan` | 仍为 `question-import-full-repair-execution`，无 `ended_at` |
| 5 | 数据库独立 | `Test-Path backend/data/question_bank.db`（worktree 内） | `False`（不存在，自建新库） |
| 6 | 主库未被污染 | 主库 `MAX(create_time)` 与文件大小 | 与开工前一致，无新列 |
| 7 | 端口并存 | 同时访问 8000 / 8001 | 均 200，互不抢占 |
| 8 | Vite 并存 | 同时访问 9527 / 9530 | 均 200，互不抢占 |
| 9 | 日志独立 | worktree 内 `logs/app.log` | 独立文件，不与主库混写 |
| 10 | boulder 独立 | worktree 内 `.omo/boulder.json` | 独立副本，可安全设置本任务 active_plan |
| **11** | **worktree gRPC 主动让出** | worktree 启动日志含 `gRPC 服务初始化失败（不影响 HTTP 服务）` | **预期现象**，非故障；worktree 的 `GET /api/recruitment` 仍 200 |
| **12** | **主后端 gRPC 完好** | `Get-NetTCPConnection -LocalPort 50051` | 仍由 PID 31872 监听，未被抢占 |
| **13** | **环境变量隔离生效** | worktree 内 `python -c "from app.core.config import settings; print(settings.PORT)"` | 输出 `8001`（已实测确认 pydantic-settings 中环境变量优先于 `.env`） |

---

## 五、风险与回滚

| 风险 | 等级 | 缓解 |
|---|---|---|
| **主工作区被误改** | **高** | 所有命令 `cd` 到 worktree 内执行；步骤 7 之前主工作区**只读**；验证项 3 每阶段复核一次 |
| **worktree 误合并入主线** | 高 | 仅在步骤 7 显式执行 `git merge`；合并前必须通过全部验收 |
| 磁盘占用翻倍 | 中 | 主库 163MB + `node_modules` 约 500MB–1GB；worktree 合并后立即 `git worktree remove` |
| `npm ci` 耗时 | 低 | 一次性 2–5 分钟 |
| Vite 端口占用 | 低 | 已确认 9530 空闲 |
| boulder 双写 | 中 | 验证项 10；合并冲突时**保留主线版本** |

### 快速回滚
```powershell
# 放弃本线路全部成果，主工作区完全不受影响
cd D:\砺安题库\砺安题库
git worktree remove --force .worktrees/recruitment-refresh
git branch -D feat/recruitment-daily-refresh
```
> 因主工作区与本线路**物理隔离**，回滚不涉及主工作区任何文件。

---

## 六、当前主工作区状态快照（回滚/比对基线）

```
分支    : fix/vite-mobile-connection
HEAD    : c77b084  fix(images): 修复教师端题干摘要截断图片与解析显示路径文本
未提交  : 25 项
  .omo/                10
  solve_problems_files/  7
  backend/              3
  其他                   5
端口    : 8000(uvicorn, PID 31872) / 9527(Vite, PID 40472)
活跃会话: question-import-full-repair-execution (started 2026-10-04, 未结束)
worktree: badge-engine-v4 / feat-exam-optimize(prunable) / teacher-optimization
```

---

> **本手册为待执行方案。未经你书面批准，不得执行 §二 中任何步骤。**
> 批准方式：回复「**批准隔离方案**」。
> 批准后我会：执行步骤 1–5 → 通过验证门禁 1–5 → 汇报 worktree 就绪状态 → 再由你决定是否 `/start-work` 启动阶段①（P0）。