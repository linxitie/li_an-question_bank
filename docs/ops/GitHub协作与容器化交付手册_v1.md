# GitHub 协作与容器化交付手册 v1

> 配套文档：docs/superpowers/specs/容器化部署方案_v2.0.md
> 适用对象：项目同伴、学校运维、后续接手的开发者
> 目标：把“拉取 / 更新 / 上传 / 合并 / 发布 / 回滚”变成任何人照做都不会丢数据的固定动作。
> 日期：2026-10-30
> 状态：操作手册，已落盘；容器化部分与 v2.0 设计稿配套，尚未在真实服务器执行。

---

## 0. 一页速查

| 场景 | 命令 / 动作 | 关键提醒 |
|---|---|---|
| 第一次拿到仓库 | git clone --filter=blob:none --sparse --depth 1 https://github.com/linxitie/li_an-question_bank.git | 弱网用过滤克隆，不要全量 clone |
| 每天开工前 | git fetch origin --prune；git status；git pull --rebase origin main | 工作区必须干净 |
| 新建任务 | git switch -c feat/简短主题 main | 一任务一分支 |
| 提交 | git add 具体文件；git commit -m "type(scope): 说明" | 不 add 整个目录 |
| 上传 | git push -u origin 分支名 | 不 push main，不 force |
| 合并 | 在 GitHub 开 PR，审核后合并 | main 受保护 |
| 服务器更新 | 备份 → 拉新镜像 → up -d → 烟测 → 失败回滚 | 先备份再动 |
| 数据迁移 | sqlite3.backup() + rsync + 清单校验 | 禁用 cp / shutil.copy2 |
| 出问题 | 先停写、再备份、后排查 | 不删 -wal / -shm 单独文件 |

---

## 1. 适用范围与角色

### 1.1 三类人

| 角色 | 能做什么 | 不能做什么 |
|---|---|---|
| 开发者 | 建分支、改代码、提 PR、跑测试 | 直接 push main；提交数据库/题图/.env |
| 同伴 / 合作方 | 拉取、建分支、提 PR、按手册部署到测试机 | 改生产数据；绕过 PR 合并；上传大文件 |
| 学校运维 | 拉镜像、启停容器、备份恢复、看日志 | 改代码；直接改数据库；把 .env 发到群里 |

### 1.2 三条底线

1. **代码走 Git，数据走备份。** 数据库、题图、上传、日志、密钥永远不进 Git。
2. **main 只接受 PR。** 任何人都不要直接 push main；紧急修复也走分支 + PR。
3. **发布必须可回滚。** 每次上线记录 IMAGE_TAG、备份路径、烟测结果、回滚命令。

---

## 2. 仓库与分支模型

### 2.1 仓库地址

canonical：

~~~
https://github.com/linxitie/li_an-question_bank.git
~~~

SSH over 443（弱网首选）：

~~~
git@ssh.github.com:linxitie/li_an-question_bank.git
~~~

**注意：** 本机当前 origin 仍指向 gh-proxy.com 镜像。镜像只适合临时只读兜底，不应作为长期 origin。正式协作前按 §3.2 改回 canonical 或 SSH。

### 2.2 分支命名

| 前缀 | 用途 | 示例 |
|---|---|---|
| feat/ | 新功能 | feat/teacher-composite-question |
| fix/ | 缺陷修复 | fix/paper-answer-scroll |
| docs/ | 文档 | docs/container-v2 |
| chore/ | 构建/依赖/杂务 | chore/bump-vite |
| hotfix/ | 生产紧急修复 | hotfix/login-500 |

规则：

- 分支名用小写英文 + 连字符，不用中文、空格、日期堆叠。
- 一个分支只做一件事；跨模块大改拆分支。
- 分支从最新 main 切出，不从未合并的旧分支继续叠。

### 2.3 分支生命周期

1. 从 main 切分支。
2. 本地开发 + 小步提交。
3. push 到 origin。
4. 开 PR，描述“改了什么、为什么、怎么验证、风险”。
5. 审核通过后合并。
6. 删除远端分支；本地切回 main 并 pull。

---

## 3. 首次上手

### 3.1 安装与身份

安装 Git for Windows（或系统对应版本），然后：

~~~
git --version
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
git config --global core.autocrlf false
git config --global core.longpaths true
~~~

说明：

- core.autocrlf=false 避免 Windows 换行把整文件改成 CRLF，产生假 diff。
- core.longpaths=true 避免深层路径超长。
- 不要设置全局 url.insteadOf 指向任何公益镜像。

### 3.2 检查 remote 是否干净

~~~
git remote -v
git config --show-origin --get-regexp "url\.|http\.|remote\."
~~~

期望 origin 是：

~~~
https://github.com/linxitie/li_an-question_bank.git
~~~

若看到 gh-proxy.com、mirror.ghproxy.com、kgithub 等，改回：

~~~
git remote set-url origin https://github.com/linxitie/li_an-question_bank.git
~~~

若 GitHub 直连超时，用 SSH over 443：

~~~
git remote set-url origin git@ssh.github.com:linxitie/li_an-question_bank.git
ssh -T -p 443 git@ssh.github.com
~~~

不要把镜像写进 origin 长期使用；镜像随时可能停服。

### 3.3 克隆：优先过滤克隆

仓库 .git 约 900 MB，全量 clone 在弱网下容易超时。首次获取建议：

~~~
git clone --filter=blob:none --sparse --depth 1 https://github.com/linxitie/li_an-question_bank.git
cd li_an-question_bank
git sparse-checkout set --no-cone "/*" "!题库" "!backend/app/static" "!backend/uploads" "!backend/data"
~~~

说明：

- 过滤克隆只拉当前需要的文件，速度从“几十分钟”降到“几十秒”（实测 23.7 s、.git 约 1.1 MB）。
- 题库/、static、uploads、data 是数据，不是代码，不需要进工作区。
- 后续需要完整历史时再 git fetch --unshallow；不要一上来全量。

### 3.4 克隆后自检

~~~
git branch --show-current
git log -1 --oneline
git status --short
~~~

期望：在 main，工作区干净，最新提交可读。

### 3.5 依赖安装（仅开发者）

前端：

~~~
npm ci
~~~

后端：

~~~
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
~~~

不要提交 node_modules、.venv、dist、__pycache__。

---

## 4. 日常拉取与更新

### 4.1 开工前标准动作

~~~
git status
git fetch origin --prune
git switch main
git pull --rebase origin main
~~~

如果工作区有未提交改动：

~~~
git stash push -m "wip: 说明"
git pull --rebase origin main
git stash pop
~~~

不要在有未提交改动时硬 pull；冲突会混在一起。

### 4.2 在任务分支上跟进 main

~~~
git fetch origin
git rebase origin/main
~~~

冲突处理：

1. git status 看冲突文件。
2. 打开文件，保留正确内容，删除冲突标记。
3. git add 冲突文件。
4. git rebase --continue。
5. 重复直到完成。

放弃本次 rebase：

~~~
git rebase --abort
~~~

### 4.3 禁止的操作

| 操作 | 为什么禁止 |
|---|---|
| git push --force / --force-with-lease 到共享分支 | 会覆盖别人的提交 |
| git reset --hard 到未备份的工作区 | 未提交改动直接消失 |
| git clean -fdx | 会删掉 .env、数据库、上传等未跟踪数据 |
| 直接在 main 上 commit 后 push | 绕过 PR 与审核 |
| git pull 产生 merge commit 后继续堆提交 | 历史分叉，review 困难 |

个人分支确需改写历史时，用 --force-with-lease，并提前告知同伴；main 永远不允许。

---

## 5. 提交与上传

### 5.1 只 stage 自己的文件

~~~
git status --short
git add 具体文件1 具体文件2
git diff --cached
git commit -m "fix(paper): 修正答题页滚动索引不同步"
~~~

不要：

~~~
git add .
git add -A
~~~

原因：很容易把 .env、数据库、临时截图、探针脚本一起提交。

### 5.2 提交信息格式

~~~
type(scope): 一句话说明

- 为什么改
- 改了什么
- 怎么验证
~~~

type 取值：feat / fix / docs / chore / refactor / test / perf。

示例：

~~~
feat(container): 新增 web 镜像与 compose v2 编排

- 前端 dist 打进镜像，生产不再挂宿主机目录
- backend 数据全部 bind，down -v 不影响业务数据
- 已验证 docker compose config 通过，尚未 up
~~~

### 5.3 上传分支

第一次：

~~~
git push -u origin feat/你的分支
~~~

之后：

~~~
git push
~~~

推送前自检：

~~~
git log --oneline origin/main..HEAD
git diff --stat origin/main...HEAD
~~~

确认没有数据库、题图、.env、大文件。

### 5.4 绝不允许进入 Git 的内容

| 类型 | 示例 | 原因 |
|---|---|---|
| 数据库 | backend/data/*.db、*.db-wal、*.db-shm | 体积大、含真实数据、二进制冲突 |
| 题图 | backend/app/static/** | 7.1 GB，且是唯一资产 |
| 上传 | backend/uploads/** | 886 MB 用户数据 |
| 四库投影 | backend/data/foundation/** | 可重建，但体积大 |
| 备份 | *.bak*、backups/** | 含历史数据 |
| 密钥 | .env、.env.*、*.pem、token 文件 | 泄露即事故 |
| 依赖/产物 | node_modules、.venv、dist、__pycache__ | 可重建 |
| 临时文件 | _probe_*.py、tmp-*.png、*.log | 污染仓库 |

检查是否误提交：

~~~
git ls-files | findstr /I ".db .env .png .jpg .zip"
~~~

PowerShell：

~~~
git ls-files | Select-String -Pattern "\.db$|\.env|\.png$|\.jpg$|\.zip$"
~~~

### 5.5 已经误提交了怎么办

1. **先轮换密钥**（如果提交了 .env / token）。改写历史不能撤回已经泄露的值。
2. 通知维护者，暂停合并。
3. 用 git filter-repo 或 BFG 清理历史；不要用 git rm 只删当前文件。
4. 强推清理后的分支，通知所有同伴重新 clone。
5. 记录事故与处置。

---

## 6. 合并到 main

### 6.1 开 PR 前

- [ ] 分支从最新 main 切出，已 rebase。
- [ ] 只改本任务相关文件。
- [ ] 本地测试通过（至少相关测试 + 构建）。
- [ ] 没有数据/密钥/大文件。
- [ ] PR 描述包含：背景、改动、验证命令与结果、风险、回滚。

### 6.2 PR 描述模板

~~~
## 背景
（为什么要改，关联 issue / 用户反馈）

## 改动
- ...
- ...

## 验证
- 命令：
- 结果：

## 风险与回滚
- 风险：
- 回滚：

## 数据影响
- 是否改表/迁移：
- 是否需要备份：
~~~

### 6.3 合并方式

- 默认 squash merge 或 merge commit，由维护者按仓库习惯决定。
- 合并前必须至少 1 人审核；涉及数据库/权限/支付/考试链路需 2 人。
- 合并后删除远端分支。
- 合并后本地：

~~~
git switch main
git pull --rebase origin main
git branch -d feat/你的分支
~~~

### 6.4 冲突处理原则

1. 先理解双方意图，不盲目“保留我的”。
2. 数据库迁移、路由、权限、考试状态机的冲突，必须找原作者确认。
3. 冲突解决后重跑测试，不只看编译通过。
4. 不确定就暂停合并，开小会，不硬合。

---

## 7. 容器化交付流程（服务器侧）

> 完整设计见 docs/superpowers/specs/容器化部署方案_v2.0.md。本节只给操作顺序。

### 7.1 交付物

一次发布必须包含：

| 交付物 | 说明 |
|---|---|
| IMAGE_TAG | git commit sha 或 vX.Y.Z，禁止 latest |
| docker-compose.yml | 与 IMAGE_TAG 配套 |
| .env.example | 变量清单，不含真实值 |
| 迁移/备份说明 | 本次是否改表、备份路径 |
| 烟测清单 | 登录/取题/题图/复合题/开考/交卷 |
| 回滚命令 | 回到上一个 IMAGE_TAG |

### 7.2 服务器目录

~~~
/srv/liankao/
├── app/                 compose 与 nginx 配置
├── data/                SQLite + foundation
├── static/              题图
├── uploads/             上传
├── logs/                日志
├── backups/             备份
└── secrets/.env.production
~~~

### 7.3 更新标准动作

**Step 1 备份（必须先做）**

~~~
python - <<'PY'
import sqlite3, datetime, pathlib
src = pathlib.Path("/srv/liankao/data/question_bank.db")
dst = pathlib.Path("/srv/liankao/backups/db") / f"question_bank_{datetime.datetime.now():%Y%m%d_%H%M%S}.db"
dst.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(src) as s, sqlite3.connect(dst) as d:
    s.backup(d)
print(dst)
PY
~~~

**Step 2 拉新镜像**

~~~
cd /srv/liankao/app
export IMAGE_TAG=新的sha或版本号
docker compose --env-file /srv/liankao/secrets/.env.production pull
~~~

**Step 3 预检**

~~~
docker compose --env-file /srv/liankao/secrets/.env.production config --quiet
bash deploy/preflight.sh
~~~

preflight 至少检查：变量齐全、目录存在且可写、题图目录非空、数据库存在、磁盘余量、端口占用。

**Step 4 启动**

~~~
docker compose --env-file /srv/liankao/secrets/.env.production up -d
docker compose ps
~~~

**Step 5 烟测**

~~~
curl -fsS http://127.0.0.1/healthz
curl -fsS http://127.0.0.1/api/v1/health
~~~

人工烟测：

- [ ] 教师登录。
- [ ] 题目列表可打开。
- [ ] 题图 HTTP 200。
- [ ] 复合题材料显示，子题关联正确。
- [ ] 学生开考、答题、交卷。
- [ ] 成绩页正常。
- [ ] 导入预览可打开。

**Step 6 观察**

- 看 30 分钟日志与 5xx。
- 看磁盘、内存、容器重启次数。
- 无异常再结束变更窗口。

### 7.4 回滚

~~~
cd /srv/liankao/app
export IMAGE_TAG=上一个可用版本
docker compose --env-file /srv/liankao/secrets/.env.production up -d
~~~

如果本次改了数据库：

1. 停 backend。
2. 备份当前故障库。
3. 删除 question_bank.db、-wal、-shm（三者一起）。
4. 用发布前备份恢复。
5. 启动并校验 integrity_check。

### 7.5 禁止动作

- docker compose down -v（会删命名卷；业务数据虽在宿主，但 parser 缓存/Redis 会丢）。
- 直接改运行中容器内的文件（重启即丢，且不可追溯）。
- 在生产容器里 pip install / npm install。
- 用 latest 标签部署。
- 把 .env.production 贴到聊天、日志、issue。
- 在容器内用 sqlite3 CLI 直接改业务库。

---

## 8. 常见故障排查

| 现象 | 先查 | 处理 |
|---|---|---|
| git pull 连接超时 | git remote -v；是否有 gh-proxy/mirror | 改 canonical 或 SSH over 443；不要继续用停服镜像 |
| SSL certificate problem | 系统时间、代理、公司证书 | 更新根证书；临时 git -c http.sslVerify=false 只用于诊断，不写全局 |
| push 被拒（non-fast-forward） | 远端有新提交 | git pull --rebase，再 push；不要 force |
| 误提交大文件 | git ls-files 大小 | git rm --cached；历史清理用 filter-repo |
| 换行导致整文件 diff | core.autocrlf | 设 false，重新 checkout |
| 容器起来但题图 404 | STATIC_ROOT 是否为空、bind 路径 | 修 preflight；不要把空目录当成功 |
| SQLite database is locked | 是否多 backend、长事务 | 固定单 worker；查长事务；不要删 -wal |
| parser 启动失败 | 模型缓存、内存、网络 | 预热模型；按需启动；parser 失败不应拖垮 backend |
| 502/504 | backend 健康、nginx upstream | docker compose logs backend；查启动错误 |
| 磁盘满 | 日志、镜像、备份 | 清旧镜像/日志；备份迁异盘；扩容 |

---

## 9. 协作检查清单

### 9.1 每次提交前

- [ ] 只改本任务文件。
- [ ] 没有 .env、.db、题图、上传、备份。
- [ ] 提交信息说明“为什么”。
- [ ] 相关测试通过。
- [ ] 已 rebase 最新 main。

### 9.2 每次合并前

- [ ] PR 描述完整。
- [ ] 至少 1 人审核。
- [ ] CI/本地门禁通过。
- [ ] 数据库变更已备份并有回滚。
- [ ] 前端/后端契约一致。

### 9.3 每次发布前

- [ ] IMAGE_TAG 固定。
- [ ] 备份完成且校验。
- [ ] preflight 通过。
- [ ] 烟测清单准备。
- [ ] 回滚命令准备。
- [ ] 变更窗口与通知到位。

### 9.4 每次发布后

- [ ] 烟测全绿。
- [ ] 日志无异常。
- [ ] 记录发布时间、版本、备份路径、执行人。
- [ ] 旧镜像保留至少 5 个版本。

---

## 10. 与现有文档的关系

| 文档 | 关系 |
|---|---|
| docs/superpowers/specs/容器化部署方案_v2.0.md | 容器化的权威设计；本手册是其操作层 |
| docs/superpowers/specs/多人协作Git网络稳定方案_v1.md | 网络/镜像/bundle 的深入排查；本手册只保留结论 |
| docs/ops/整体系统使用和结构说明_v1.md | 本机启动、目录结构、SQLite 备份恢复 |
| docs/superpowers/specs/题目入库知识图谱与四库映射_v1.md | 四库数据边界；容器挂载与备份依据 |
| AGENTS.md | 工程红线；本手册不覆盖、不修改红线 |

冲突时：AGENTS.md > 容器化部署方案 v2.0 > 本手册 > 旧文档。

---

## 11. 变更记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-10-30 | v1 | 首版：Git 拉取/分支/提交/合并 + 容器化交付/回滚 + 故障排查 + 检查清单 |
