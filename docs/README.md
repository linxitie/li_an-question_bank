# docs/ 文档索引

> 本索引由 `solve_problems_files/README.md` 迁移而来（目录分层重构）。
> 归档规则：展示方案的同时落盘；定稿当场归档；归档即更新本索引。

### 一、系统目录结构分层说明

## 1.根目录分层
```
/ 仓库根
│
├── 【A】VTJ 应用根 ── 冻结，不可重组
│   ├── src/                 前端源码（内部按 §4.2 分层）
│   ├── .vtj/                低代码资产（92 处 import 硬绑定）
│   ├── public/              静态资源（favicon / logo）
│   ├── packages/            前端共享包（已获批准：保持根目录，不并入 deploy/）
│   ├── dist/                构建产物（已 gitignore）
│   └── package.json  vite.config.ts  proxy.config.ts  tsconfig*.json  index.html
│
├── 【B】应用后端
│   └── backend/             FastAPI + 运维脚本 + 测试 + 迁移
│
├── 【C】原始语料 ── 🚫 红线，禁动
│   └── 题库/                662 MB PDF（行测重导依赖）
│
├── 【D】文档 ── 全部收归此处
│   ├── docs/
│   │   ├── design/          方案设计（按业务域）
│   │   ├── plans/           实施计划
│   │   ├── ops/             使用/运维手册（环境 / 启动 / 拉取更新 / 数据库 / 共享 / 排错）
│   │   ├── archive/         历史版本（题目导入 v1~v9 归此）
│   │   └── ai-commands/     原 CLAUDE.md/ 目录改名而来
│   └── README.md  CHANGELOG.md
│
├── 【E】工程化
│   ├── deploy/              Dockerfile / docker-compose.yml / nginx.conf
│   │                        / .env.development / .env.school / .env.example
│   ├── parser/              MinerU + OCR sidecar（python:3.11）
│   └── tools/               开发辅助工具（bg-monitor / sfc-check / git-hooks）
│
├── 【F】AI 工具记录 ── 归并为单一目录
│   └── .agent/{skills,tools,plans}/ + README.md 索引
│
└── 构建缓存 ── 全部 gitignore
    ├── node_modules/  .worktrees/  logs/  .pytest_cache/  .playwright-mcp/
    └── .idea/  .vscode/  .sisyphus/  .omo/
```
## 2.后端分层

```
backend/
├── app/
│   ├── main.py                  ★ 唯一入口，只做装配
│   │
│   ├── core/                    平台内核 ── 零业务
│   │   ├── config.py  database.py  security.py  redis_client.py
│   │   ├── events.py            【新】事件总线契约
│   │   ├── contracts.py         【新】跨域公开契约注册
│   │   ├── module_registry.py   【新】域清单一处声明
│   │   ├── middleware.py        ← 从 app/ 根移入
│   │   ├── monitoring.py        ← 从 app/ 根移入
│   │   ├── exceptions.py        ← 从 app/ 根移入
│   │   ├── cache.py             ← 从 app/ 根移入
│   │   └── db_router.py         ← 从 app/ 根移入
│   │
│   ├── modules/                 【新】十域，各自自包含
│   │   └── <domain>/{__init__, router, schema, models, service, contract}.py
│   │
│   ├── shared/                  【新】跨域基础件 ── 非业务
│   │   └── parser/  ocr/  scraper/  image/  matcher/
│   │
│   ├── models/                  Base + 过渡期（P3 后仅留 Base）
│   ├── schemas/                 平台级共享 schema
│   ├── services/                过渡期（P2–P4 后按域迁入 modules/）
│   ├── api/v1/                  过渡期（P3 后清空）
│   │
│   ├── static/                  题图 4.3 GB ── 卷，不入 Git 不入镜像
│   └── uploads/                 702 MB ── 卷
│
├── scripts/                     运维脚本（6 类子目录，见 §7.5）
│   └── gates/  migrate/  repair/  probe/  admin/  verify/
├── tests/                       conftest.py + 用例
├── migrations/                  SQL + Python 迁移
├── data/                        SQLite + gates + audit + archive ── 卷
├── logs/                        运行日志
├── Dockerfile  .dockerignore
├── .env  .env.example
├── requirements.txt
└── README.md  REPORTS.md
```

## 3.数据目录分层
```
backend/data/                    全部不纳入 Git，容器化后为卷
├── question_bank.db             生产库 292 MB（+ -wal / -shm）
├── gates/                       门禁基线 ── 反选入库（CI 复现必需）
├── audit/                       回填/去重审计流水（14 文件：.jsonl + .csv）── 数据变更追溯凭证
├── archive/                     备份归档（41 份唯一内容，按「最近 7 天 + 每周一份」保留）
├── text_cache/                  PDF 文本提取缓存（74 文件，可重建）
├── xingce_cache/                行测探测缓存（170 文件，可重建）
├── refactor_baseline/           重构基线 JSON（6 份）── force-add 入库
└── backup_audit_report.json     备份审计报告 ── force-add 入库
```

## 4.前端目录分层
```
src/
├── router/index.ts              # 主路由表（roles + platform 双重门控）
│
├── views/
│   ├── student/                 学生端
│   │   ├── shared/              6 页（achievements exercise solution profile feedback help）
│   │   ├── pc/                  PC 专属（当前 0，主要在 .vtj）
│   │   ├── tablet/              平板专属（当前 0）
│   │   └── mobile/              ★ 19 个 mobile_* 页全部归此
│   │
│   ├── teacher/                 教师端【预留】
│   │   ├── shared/
│   │   ├── pc/                  PC 专属（当前 0；教师端 8 页在 .vtj/vue）
│   │   ├── tablet/              平板教师端（当前 0）
│   │   └── mobile/              手机教师端（当前 0）
│   │
│   ├── admin/                   管理端【预留】
│   │   ├── shared/
│   │   ├── pc/                  ★ 管理端 11 页目前在 .vtj/vue
│   │   ├── tablet/              平板管理端（当前 0）
│   │   └── mobile/              手机管理端（当前 0）
│   │
│   └── system/                  无角色归属的系统页
│       ├── not-found.vue
│       └── unauthorized.vue
│
├── components/
│   ├── common/                  HelloWorld / VtjErrorBoundary（无角色无设备归属）
│   ├── mobile/                  MobileTabBar（设备专属）
│   └── domain/                  RecentPracticeRecords（域内）
│
├── services/
│   └── api/<domain>.ts          # ★ 按十域归口，不按角色/设备
│
├── layouts/
│   ├── AdminLayout.vue          管理端（位置已正确）
│   └── TeacherLayout.vue        教师端（位置已正确）
│
└── utils/                       device.ts 等 7 个（原样保留）
```
## 5.前端模块化目录分层
```
src/
├── modules/                     # 新增：20 个模块外壳
│   ├── identity/                ##  认证 + 个人中心
│   │   ├── store.ts             # 域内状态
│   │   ├── api.ts               # 域内 HTTP 封装
│   │   ├── events.ts            # 本域发布/订阅的事件声明
│   │   └── README.md            # 域卡（见 7.4）
│   ├── catalog/                 ## 题库浏览
│   ├── practice/                ## 答题练习
│   ├── records/                 ## 练习记录
│   ├── papers/                  ## 智能组卷 + 历年试卷
│   ├── wrongbook/               ## 错题集
│   ├── notes/                   ## 笔记 + 收藏
│   ├── analytics/               ## 成绩分析
│   ├── community/               ## 论坛社区
│   ├── news/                    ## 每日新闻
│   ├── calendar/                ## 考试日历
│   ├── recruitment/             ## 招考信息
│   ├── about/                   ## 关于砺安题库
│   ├── library/                 ## 备考资料
│   ├── growth/                  ## 成就成长（枢纽）
│   ├── reward/                  ## 金币商城
|   ├── mini-exam                ## 小模考
|   ├── mock-exam                ## 模拟上机考试
|   ├── ai-assistant             ## 联考小智
│   └── checkin/                 ## 每日签到
|
├── stores/                      # 新增：全局共享层
│   ├── auth.ts                  # 登录态、当前用户、角色
│   ├── user-profile.ts          # 跨域只读的用户画像快照
│   └── event-bus.ts             # mitt 实例 + 事件常量表
├── services/
│   └── api/                     # 激活：统一 axios 实例与拦截器
│       ├── client.ts            # baseURL、超时、重试
│       ├── interceptors.ts      # 鉴权头、401 跳转、错误归一化
│       └── types.ts             # 通用响应外壳类型
├── utils/
│   └── device.ts                # 原样保留（R4）
└── router/
    └── index.ts                 # 原样保留 92 处 .vtj 动态 import（R1）
```


### 二、拉取项目并打开项目的一般步骤
## 1.打开 VS Code，按下 Ctrl+Shift+P（Mac 为 Cmd+Shift+P）打开命令面板。

## 2.输入 gitcl，选择 Git: Clone 命令。

## 3.选择 Clone from GitHub，VS Code 会引导你登录 GitHub 账户进行授权。

## 4.在仓库 URL 输入框中，粘贴 GitHub 项目的链接（就是这个项目--https://github.com/linxitie/li_an-question_bank.git）。

## 5.选择一个本地文件夹作为项目的保存位置，然后点击 Select as Repository Destination。

## 6.克隆完成后，VS Code 会询问你是否打开该项目，点击 Open 即可。

## 7. 启动系统（首次与日常）

# > 先下载项目内容："npm install"；前端依赖应在**仓库根**安装。按 7.1 → 7.6 的顺序执行，不要先跑前端再装后端。

### 7.1 环境要求与检查

| 组件 | 要求 | 检查命令 |
|---|---|---|
| Windows | 10/11 64 位 | `winver` |
| PowerShell | 5.1 及以上 | `$PSVersionTable.PSVersion` |
| Node.js | ≥ 20（本机实测 v24.14.0） | `node -v` |
| npm | ≥ 10 | `npm -v` |
| Python | ≥ 3.10（本机实测 3.13.5） | `python --version` |
| Git | 2.40 及以上 | `git --version` |
| 磁盘 | 建议 ≥ 15 GB 空闲 | `Get-PSDrive D` |

建议把仓库放在**不含空格**的路径；本项目当前路径含中文可以运行，但 PowerShell 日志可能出现编码乱码，执行前可先设 UTF-8：

```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'
```

### 7.2 克隆后确认

克隆步骤见本节 1–6。完成后在仓库根执行：

```powershell
git status
git branch -a
git log --oneline -5
```

### 7.3 启动后端（FastAPI）

**下载项目内容完毕后**

# ```powershell
# cd D:\砺安题库\砺安题库\backend
# 输入命令"python -m uvicorn app.main:app --host 0.0.0.0 --port 8000",entre即可
# ```

### 7.4 启动前端（Vite + VTJ）

**必须从仓库根启动**（`vite.config.ts` 有 `workspaceRoot` 强制校验，不能从 `backend/` 或子目录启动）：

# ```powershell
# cd D:\砺安题库\砺安题库
# npm run dev
# ```

-
- `npm run dev` 实际执行 `cross-env ENV_TYPE=local vite`，端口 **9527**，`host: '0.0.0.0'`，手机/平板可通过局域网访问。
- 打开：
  - 前端：`http://localhost:9527`
  - VTJ 设计器：`http://localhost:9527/__vtj__/`
- Vite 代理默认把 `/api` 转发到 `http://127.0.0.1:8000`；需要连别的后端时设：
  ```powershell
  $env:DEV_BACKEND_ORIGIN = "http://192.168.1.10:8000"
  npm run dev
  ```
- 后端没起来时，前端会收到 `503/502` 和 `BACKEND_UNAVAILABLE`，先回去启动 7.3，不要先怀疑前端页面。
- 端口被占用：
  ```powershell
  netstat -ano | findstr :9527
  taskkill /PID <PID> /F
  ```

### 7.5 手机端 / 平板端访问

1. 电脑和手机连同一个 Wi-Fi/局域网。
2. 在 PowerShell 执行 `ipconfig`，找到“无线局域网适配器 WLAN”的 IPv4 地址（如 `10.213.3.206`）。
3. 手机浏览器访问：`http://10.213.3.206:9527`（英文冒号）。
4. 打不开时依次检查：Windows 防火墙是否放行 Node.js；是否连错 Wi-Fi；IP 是否变化；Vite 是否仍在运行。
5. 前端页面走 9527，API 由 Vite 代理转发；一般不需要在手机上单独访问 8000。

<!-- ### 7.6 Docker 部署（可选，生产/演示）

> 实际编排文件是**仓库根**的 `docker-compose.yml`，不是 `deploy/docker-compose.yml`（后者不存在）。

```powershell
# 1. 准备环境变量（真实密钥只写在本地，不提交）
Copy-Item deploy\.env.example deploy\.env.development
# 编辑 deploy\.env.development，至少填写 JWT_SECRET_KEY

# 2. 构建前端产物（nginx 挂载仓库根 dist/）
npm run build:prod

# 3. 启动
docker compose --env-file deploy\.env.development up -d --build
docker compose ps
docker compose logs -f backend
```

- 服务：`nginx`（80）、`backend`（127.0.0.1:8000）、`parser`（127.0.0.1:8080）。
- 卷：`db_data`（SQLite + 门禁基线）、`uploads`、`qimg`（题图）、`parser_cache`（MinerU 权重）。**不要执行 `docker compose down -v`**，否则会删除数据库、上传文件和题图。
- `qimg` 卷首次需要导入 `backend/app/static/` 的题图（约 4.3 GB）；不导入会全站裂图。
- `deploy/.env.development` / `.env.school` 含真实密钥，已被 `.gitignore` 排除，禁止提交；仓库只保留 `deploy/.env.example`。
 -->
**进行项目克隆完毕之后**
# 打开自己最适合最常用的AI编码工具（推荐使用claude终端版、opencode终端版、gpt、cursor等等） ,并进行所有提前配置完毕后再进行具体项目设计（后面一一提及，大大和大大大的字体就是要特别关注的）

# 8.进行分支独立设计的提示词约束：
```
## 分支拓扑约定（必须严格遵守）

当前项目使用“模块工作域 + 子分支”的链式分支模型：

main（稳定基线）
 └── feature/<模块名>        ← 模块工作域（父分支），只接受经过测试的子分支合并
      └── feature/<模块名>/<子任务>  ← 子分支，每次只做一件优化/测试任务

## 你的当前工作域

- 你当前所在的分支：feature/<模块名>/<子任务>
- 该分支的父分支：feature/<模块名>
- 禁止直接从当前分支向 main 发起合并或 PR。
- 所有代码修改、测试、提交，都只在你当前所在的子分支中进行。

## 操作规则

1. **拉取与同步**：开始工作前，先 `git pull` 当前子分支；如果子分支尚未创建，从 `feature/<模块名>` 拉出，命名格式为 `feature/<模块名>/<子任务简述>`。
2. **只做一件事**：当前子分支只负责一个具体的优化或测试任务。不要在其中混合无关的改动。
3. **测试先行或并行**：每次提交前，至少运行与当前模块相关的测试命令（如果项目有测试套件）。如果测试失败，先修复，再提交；不要提交测试失败的代码。
4. **提交粒度**：一个逻辑变更一个提交，提交信息使用 `feat/fix/test/refactor: <简述>` 格式。
5. **合并回父分支**：当前子任务完成且测试通过后，只向 `feature/<模块名>` 发起合并/PR，不要直接向 main 操作。
6. **如果父分支有更新**：在子分支中 `git rebase feature/<模块名>`（或 merge），解决冲突后再继续，保持子分支建立在父分支最新状态之上。

## 合并顺序（链式分支专用）

如果存在多层嵌套（例如孙分支），合并顺序必须是：
- 孙分支 → 子分支 → 模块工作域 → main。
- 永远从最外层向内合并，不得跳层
```
**不同的编码AI的内置技能不同：**
# 1.Trae
利用“工作树”做隔离，提示词侧重“任务边界”
Trae 内置了工作树（Worktree） 模式，可以为每个任务自动创建独立的分支和目录，并在任务完成后通过“AI 合并”将代码合回目标分支。这意味着你不需要在提示词里让 AI 手动执行 git checkout -b，而是在 Trae 中启动任务时选择工作树模式，然后让提示词聚焦于“这个工作树里做什么”：

text
你当前在一个独立的工作树中，对应分支 feature/<模块名>/<子任务>。
你的任务：<具体优化或测试目标>。
约束：
- 只修改与该目标直接相关的文件。
- 完成后，将变更合并回父分支 feature/<模块名>，不要合并到 main。
- 如果测试失败，在当前工作树中继续修复，不要标记任务完成。

# 2.opencode
用 opencode-worktree 插件自动管理子分支
OpenCode 可以通过 opencode-worktree 插件为每个任务自动创建 agent/<task> 格式的子分支，并在退出时自动合回父分支。提示词需要让 AI 理解 agent/ 分支是“临时执行分支”，它的生命周期绑定于当前任务：

text
你正在一个由 opencode-worktree 创建的隔离工作树中，当前分支为 agent/<task>。
该分支的父分支是 feature/<模块名>。
你的任务：<目标>。
规则：
- 所有改动只提交到当前 agent 分支。
- 任务完成后，通过工作树机制合回父分支；如果合并不需要保留，直接退出即可。
- 在退出/合并前，运行相关测试并确认通过。

# 3.Claude
原生 Git 操作，提示词需明确“禁止直接碰 main”
Claude Code 具备原生 Git 提交能力，也可以被 MCP Git 工具赋予分支、rebase 等完整操作权限。它的风险在于权限较大，可能直接执行 git push origin main。因此提示词必须包含一条硬性禁止：

text
严禁直接向 main 分支执行 push、merge 或创建 PR。
你只被允许在 feature/<模块名>/<子任务> 分支上提交和推送。
完成子任务后，只向 feature/<模块名> 发起合并请求（PR 或本地 merge）。

- 其他的我没有深入使用，不太了解

---

## 9. 后期拉取分支更新后的操作步骤

> 这一节解决“别人合并了新代码/新设计，我本地怎么安全跟上”的问题。完整的多人协作规则见 `docs/plans/分支使用说明书_v1.md`，这里只给拉取前后必须执行的动作。

### 9.1 拉取前：先保证工作区干净

```powershell
cd D:\砺安题库\砺安题库
git status --short
git branch --show-current
```

- 有未提交改动时，先提交到当前功能分支；不想提交就暂存：
  ```powershell
  git stash push -u -m "wip: 拉取更新前暂存"
  git stash list
  ```
- **不要**用 `git reset --hard`、`git clean -fd` 清工作区；这会直接丢代码和未跟踪文档。
- 确认当前分支：`main` 只做同步，不直接开发；开发在 `feature/<模块>` 或 `feature/<模块>/<子任务>`。

### 9.2 拉取 main 与模块分支

**情况 A：只更新 main**

```powershell
git switch main
git fetch origin --prune
git pull --ff-only origin main
```

`--ff-only` 失败说明本地 main 与远端分叉了，不要强行 merge；先看：

```powershell
git log --oneline --left-right main...origin/main
```

把本地多出来的提交移到功能分支，或找维护者确认后再处理。

**情况 B：更新模块父分支**

```powershell
git switch feature/<模块名>
git fetch origin --prune
git merge origin/main
git push origin feature/<模块名>
```

**情况 C：更新自己的子分支（最常用）**

```powershell
git switch feature/<模块名>/<子任务>
git fetch origin --prune
git merge origin/feature/<模块名>
git merge origin/main
git push origin feature/<模块名>/<子任务>
```

先合父分支，再合 main；不要反过来。合并冲突时：

```powershell
git status
# 手工编辑冲突文件，确认没有残留 <<<<<<< ======= >>>>>>>
git add <冲突文件>
git commit
```

想放弃这次合并、回到合并前：

```powershell
git merge --abort
```

冲突处置细节（保留谁、怎么验证）见 `docs/plans/分支使用说明书_v1.md` 第 7 章。

### 9.3 拉取后：先看“变了什么”，再启动

```powershell
git log --oneline --graph --decorate -20
git diff --stat ORIG_HEAD..HEAD
git diff --name-only ORIG_HEAD..HEAD
```

# 每次完成自己模块的预期目标或者效果一定一定要合并并推送至github中否则会出现内容过多，项目冗余的情况，严重会破坏整个项目(可以手动进行分支合并和推送，也可以让AI执行命令合并推送)

### 9.3.1附加手动实现分支合并并推送
- 第一步 保存并提交自己的代码
  ### 查看自己改了哪些文件
  git status
  ### 添加并提交（注意：一定要确认没有把 .db、.env 等无用文件加进去）
  git add .
  git commit -m "feat: 完成功能设计与测试"
- 第二步 切回主干，拉取你的最新代码（极其关键）
  为了防止他推送时覆盖掉你刚写的代码，他必须先同步你的最新进度。
  ### 1. 切回主干
  git checkout main
  ### 2. 拉取你（负责人）在 GitHub 上的最新代码
  git pull origin main
- 第三步 将分支合并进主干
  ### 把 feat/my-feature 合并进当前的 main 分支
  git merge feat/my-feature
  **如果成功：终端会显示 Merge made by...。直接进入第四步。**
  **如果有冲突：终端会报错 CONFLICT。让他立刻停止，并通知你。让他用 VS Code 解决完冲突，执行 git add . 和 git commit 后再继续。**
- 第四步 推送到 GitHub
  git push origin main


### 9.4 数据库有变更时：先备份，再启动

```powershell
cd D:\砺安题库\砺安题库\backend
python scripts/admin/backup_db.py --label 拉取更新前
python start.py
```


### 9.5 前端依赖与缓存

```powershell
cd D:\砺安题库\砺安题库
npm ci
npm run dev -- --force
```

- `--force` 让 Vite 重新预构建依赖；也可以删除 `node_modules/.vite` 后重启。
- **不要随手执行 `npm run clean`**：该脚本会删除 `node_modules`、`dist`、`package-lock.json`、`pnpm-lock.yaml`，不是普通的清缓存。
- 浏览器用 `Ctrl+F5` 强刷；设计器页面同样要强刷，避免旧 chunk 缓存。

### 9.6 设计完成后的收尾（合并前）

1. **文档**：设计/方案写入 `docs/plans/` 或 `docs/superpowers/specs/`；更新 `docs/README.md` 索引；按 `AGENTS.md` 归档规则留档。
2. **计划**：把实施计划里的任务勾选、状态、验证结果更新掉；代码提交与计划状态提交分开。
3. **VTJ**：`.vtj/` 不移动、不改名、不删除；`raw: true` 页面禁止 `vtj_sync_vue_to_dsl`；`.vtj/vue/*.vue` 的 `<template>` 只能由设计器改，AI 只改 `<script>` 且先 `dryRun: true`。
4. **验证**：
   ```powershell
   cd D:\砺安题库\砺安题库
   npm run typecheck
   npm run build
   npm run test:unit

   cd backend
   python -m pytest tests -q
   python scripts/gates/gate_all.py --quick
   ```
   全量门禁用 `python scripts/gates/gate_all.py`；行测 L1 等既有 FAIL 以基线为准，**新增失败必须修复**。
5. **提交**：一个逻辑变更一个提交，提交信息用 `feat/fix/test/refactor: <简述>` 或模块前缀（如 `wrongbook: ...`）。
6. **合并顺序**：子分支 → 模块父分支 → `main`，禁止跳层，禁止直接 push `main`；合并前必须再合一次最新 `origin/main` 并重跑门禁。
7. **合并后**：删除已合并的临时分支，切回 main `git pull --ff-only`，确认远端与本地一致。

### 9.7 不要提交的东西 【必须要看和注意】

- `backend/data/question_bank.db`、`-wal`、`-shm`、`backend/data/*.bak*`、`backend/data/backups/`
- `backend/uploads/`、`backend/app/static/` 的题图、`题库/` 原始 PDF
- `.env`、`deploy/.env.development`、`deploy/.env.school`、`.obsidian_mcp.json`、`admin_token.txt`
- `node_modules/`、`dist/`、`backend/logs/`、`.vtj/logs/`、`.vtj/histories/`

---

## 10. 数据库数据的存储说明

### 10.1 默认数据库：SQLite（WAL）

| 项 | 实际值 |
|---|---|
| 类型 | SQLite，`DB_TYPE=sqlite`（默认） |
| 主库 | `backend/data/question_bank.db`（当前约 302.7 MB） |
| WAL | `backend/data/question_bank.db-wal`（当前约 5.4 MB） |
| 共享内存 | `backend/data/question_bank.db-shm` |
| 日志模式 | WAL；已提交数据可能还在 `-wal` 里，**不能只拷主库** |
| 连接串 | 由 `backend/app/core/config.py` 的 `DATABASE_URL` 生成；`start.py` 会先切到 `backend/`，所以相对路径以 `backend/` 为基准 |

`backend/data/` 不是普通缓存目录，里面同时有：

- `backups/`：`backup_db.py` 的新备份
- `audit/`：数据变更追溯凭证（R9，不是垃圾）
- `gates/`：门禁基线与 `last_run.json`
- `refactor_baseline/`：API/模型/耦合/表使用基线
- `snapshots/`、`text_cache/`、`xingce_cache/`：解析缓存与快照
- `question_bank.db.bak_*`：历史备份（R8，禁止清理）

### 10.2 大体积数据放在哪里

| 数据 | 位置 | 体量（实测口径） | 是否进 Git |
|---|---|---|---|
| 原始 PDF 语料 | `题库/` | 约 662 MB | 否（R6，禁止删除/移动） |
| 题图 | `backend/app/static/` | 约 4.3–5.5 GB | 否（R7，禁止删除；新题图已忽略） |
| 用户上传 | `backend/uploads/` | 约 0.8 GB | 否 |
| SQLite 主库 + 备份 | `backend/data/` | 主库约 300 MB，备份数十份 | 否 |
| 示例库 | `backend/data/example_db.sqlite` | 约 13 MB | 否（本地示例库，已被 `.gitignore` 忽略） |

这些数据**不通过 Git 共享**。换机器/多人协作时用移动硬盘、内网共享、`rsync` 或对象存储；Docker 部署用命名卷持久化。

####  10.3 Docker 下的数据库

`docker-compose.yml` 把数据挂到命名卷：

- `db_data:/app/data`：SQLite 主库、WAL/SHM、备份、门禁基线
- `uploads:/app/uploads`：用户上传
- `qimg:/app/app/static`：题图（约 4.3 GB，必须单独导入）
- `parser_cache:/root/.cache`：MinerU 模型权重

**不要 `docker compose down -v`**，否则上述卷会被删除。备份要在容器内执行，再把备份文件取出：

```powershell
docker compose exec backend python scripts/admin/backup_db.py --label docker
docker compose cp backend:/app/data/backups/<备份文件>.db .\backup_from_docker.db
```


### 三、项目的必须认识内容

## 1. 前端设计器
由于前端是由VTJ页面设计的，但是该网页需要额外充钱使用，所以我制定了一个D:\砺安题库\砺安题库\vtj-mcp-server的设计器；到时候使用时需要进行前端页面修改时需要进行提示词约束（后面我会将几个关键约束提示词提供）

## 2.MCP-SERVER和skills、工作流
（1）vtj-mcp-server,不再赘述
（2）playwright-MCP--用于模拟人的行为进行查看浏览器内容，可以用来让AI测试前端设计效果、也可以用来进行爬虫应对反爬机制等等
（3）superpower（skills）--主要使用模块是其brainstorm、writting-plans，它是用一套可组合的“工程纪律”技能，保证设计的可靠性、多维、多方面、全方位的思考要求。
强制让AI走完思考 → 计划 → 编码 → 验证 → 审查的完整工程闭环
（4）工作流--大家可以去多问一下其他AI（deepseek、千问、智普等等），让他们来设计针对你使用的AI设计你相应的功能模块的必须工作流，保证使用时可以按照工作流的内容设计、不至于让其胡思乱下、偷工减料、出现AI幻觉等（这个可能需要在不断地测试，摸索之后才有点头绪）
（5）大家若有其他好的skills、MCP-server、工作流或者其他的能够高效使用AI的方法都可以交流分享

## 3.我自己一般使用的约束提示词（大家参考着用吧，可以天马行空的想其他的约束词，高效能用就是好的）
全局规则：
  1.深度分析以上问题和要求，设计出完整的解决方案同时支持我可以对方案进行更深层次要求的提出，设计的方案需要考虑细节、内容下钻、方案可落地性、内容的可靠性等，
  2.将完整方案经过我的审核批准后才能进行具体设计，将解决方案呈现出来并统一存档在D:\砺安题库\砺安题库\docs\plans文件夹（这个路径需要大家复制自己保存的文件夹的路径中的\plans即可）
  3.涉及具体代码编写时请在编写的前一步多角度的思考为什么这样编写代码？这样编写代码有什么好处？这样写代码会不会存在安全问题？这样编写代码能不能为后期的运维提供便利？怎样编写代码才能将系统的未来运维管理等更加便捷？将代码编写在此文件中是否正确是否能保证修改后前端能显示出修改效果？修改的代码所处的文件是否正确，能否达到提示词所预期的效果？后端字段是否完善？后端路由是否注册和调用和接口是否完整？前端显示是否能达到预期效果？vtj版本是否一致？
  4.严格遵照VTJ中设计器--D:\砺安题库\砺安题库\vtj-mcp-server（这个路径需要大家复制自己保存的文件夹的路径中的\vtj-mcp-server即可）
  5.每次执行命令时请严格遵循该工作流D:\砺安题库\砺安题库\.opencode\skills\li-an-workflow\SKILL.md（同4和1）

## 4.用户账号和手机端、平板端的登录查看
- 1.学生账号：202516001；test123456
- 2.教师账号：ycc5678；ycc5678
- 3.管理员账号：cbrycc；cbrycc

**手机端登录**（平板端同理）
在cmd终端中输入“ipconfig”，查看“无线局域网适配器 WLAN的IPv4地址”，输入到手机浏览器中再加上“:9527”，比如我的是（10.213.3.206:9527）【英文冒号】
