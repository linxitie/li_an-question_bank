# 多人协作 Git 网络稳定方案 v1

> 状态：已定稿（2026-10-29）· 适用范围：砺安题库全部协作成员（主导人 / 同伴 / 外部评审）
> 触发事件：同伴执行 `git pull` 报
> `fatal: unable to access 'https://mirror.ghproxy.com/https://github.com/linxitie/li_an-question_bank.git/': Failed to connect to mirror.ghproxy.com port 443 after 21e81 ms: Could not connect to server`

---

## 0. 一句话结论

这不是"网络坏了"，而是**客户端 remote 指向了已停服的公益镜像**；再叠加**仓库体积 917 MB** 造成的传输超时，就被误读成网络故障。
修复 = 清掉镜像改写 + 恢复 canonical origin + 弱网改用过滤克隆 + 断网时用 bundle 交接，日常按"一任务一分支 + rebase"协作。

---

## 1. 实测证据（2026-10-29，主工作区 `D:\砺安题库\砺安题库`）

### 1.1 端点连通性（443，TCP 握手）

| 端点 | 结果 | 耗时 |
|---|---|---|
| `github.com` | OPEN | 1258 ms |
| `ssh.github.com` | OPEN | 184 ms |
| `codeload.github.com` | OPEN | 203 ms |
| `gitee.com` | OPEN | 101 ms |
| `gh-proxy.com` | OPEN | 392 ms |
| `ghfast.top` | FAIL（timeout） | 4007 ms |
| `mirror.ghproxy.com` | FAIL（DNS 解析失败："不知道这样的主机"） | 66 ms |

结论：**GitHub 直连是通的**；`mirror.ghproxy.com` 已彻底不可用（连 DNS 都不解析）；其它镜像时通时不通（`ghfast.top` 本次就挂了）。

### 1.2 本机 Git 配置

```
git config --show-origin --get-regexp 'url\.|http\.|remote\.'
  file:C:/Program Files/Git/etc/gitconfig  http.sslbackend schannel
  .git/config  remote.origin.url  https://github.com/linxitie/li_an-question_bank.git
  .git/config  http.postBuffer    524288000
  .git/config  http.lowSpeedLimit 0
  .git/config  http.lowSpeedTime  999999
```

本机**没有** `url.<base>.insteadOf` 改写、**没有** `HTTP(S)_PROXY` 环境变量、**没有** `~/.ssh/config`。
→ 说明问题出在**同伴那台机器**：要么全局 `insteadOf` 把 `https://github.com` 改写成 `https://mirror.ghproxy.com/https://github.com`，要么曾手工 `git remote set-url` 成镜像地址。

### 1.3 仓库体积（真正让链路"不稳"的原因）

| 指标 | 实测 |
|---|---|
| `.git` 目录 | **916.8 MB** |
| HEAD 跟踪文件总量 | **992.4 MB** / 5660 个文件 |
| `题库/` 目录（已跟踪） | **497.3 MB** |
| `backend/` 目录（已跟踪） | **482.4 MB** |
| 单文件最大 | `题库/公安题目（打印）/2025多省联考公安《公安专业》.pdf` **57.0 MB** |
| >5 MB 的跟踪文件 | 10 个，合计 192.3 MB |
| 过滤克隆实测 | `--filter=blob:none --sparse --depth 1` → **23.7 s、`.git` 仅 1.1 MB** |

`.gitignore` 早已包含 `backend/uploads/`（L77）与 `*.db`（L70），但 `backend/uploads/news/{732,734,1279}/*.jpg`（22.1/21.5/7.7 MB）等历史文件**仍处于已跟踪状态**——ignore 只影响新文件，不影响已被跟踪的文件。

---

## 2. 根因分层

| 层 | 根因 | 表现 |
|---|---|---|
| L1 客户端配置 | remote / `url.insteadOf` 指向 `mirror.ghproxy.com` 等公益镜像 | `Could not connect to server`，看着像断网 |
| L2 链路选择 | 只配了一条链路，没有回退 | 镜像一挂就完全不能协作 |
| L3 传输体量 | 全量 clone/fetch 需拉 ~917 MB，弱网必然超时报错 | `Connection was reset`、`early EOF`、`index-pack failed`，被误判为网络故障 |
| L4 协作流程 | 直接在各人分支上互相 push/pull、无 rebase 纪律、历史上还曾把 `backend/data/question_bank.db` 当受跟踪文件 | 冲突放大、误删运行库（2026-10-25 事故） |

---

## 3. 修复步骤（同伴按顺序执行）

### A. 定位并清除镜像改写（3 分钟）

```powershell
# 1) 看有没有把 github 改写去镜像的规则
git config --global --get-regexp 'url\..*\.insteadof'
git config --system --get-regexp 'url\..*\.insteadof'

# 2) 若有，逐条删（把 <key> 换成上一行输出的 key，例如 url.https://mirror.ghproxy.com/https://github.com.insteadof）
git config --global --unset-all url.<key>.insteadof

# 3) 看 origin 实际指向
git remote -v

# 4) 恢复 canonical
git remote set-url origin https://github.com/linxitie/li_an-question_bank.git
```

一键版（本仓库自带脚本，会打印诊断并可选修复）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/dev/git-collab-doctor.ps1        # 只诊断
powershell -ExecutionPolicy Bypass -File scripts/dev/git-collab-doctor.ps1 -Fix   # 清死镜像改写 + 复位 origin
```

### B. 验证链路

```powershell
git fetch origin --prune
git ls-remote --heads origin | Measure-Object      # 预期 29 个分支
```

失败时按顺序试：

1. **SSH over 443**（`ssh.github.com:443` 实测 184 ms，最稳）：
   ```powershell
   git remote set-url origin git@ssh.github.com:linxitie/li_an-question_bank.git
   ```
   `~/.ssh/config`：
   ```
   Host ssh.github.com
     HostName ssh.github.com
     Port 443
     User git
   ```
2. **只读镜像兜底**（只能 fetch，不能 push，且镜像随时可能停服，不要写进 remote 主配置）：
   ```powershell
   git remote add mirror https://gh-proxy.com/https://github.com/linxitie/li_an-question_bank.git
   git fetch mirror
   ```
3. **bundle 离线包**（见 D）。

### C. 弱网 / 首次获取：用过滤克隆，不要全量 clone

```powershell
# 只拿提交与树，blob 按需下载；.git 约 1 MB，实测 24 秒
git clone --filter=blob:none --sparse --depth 1 https://github.com/linxitie/li_an-question_bank.git
cd li_an-question_bank

# 只展开需要开发的目录（示例：后端 + 文档）
git sparse-checkout set backend docs scripts package.json
```

已有仓库想瘦身，不要重新 clone，用增量：

```powershell
git fetch --filter=blob:none origin --prune
git config core.fsmonitor true      # 大工作区上加速 status
```

> 注意：`题库/`（497 MB）与 `backend/uploads/`（含 4 张 >7 MB 截图）是历史遗留的跟踪大文件。
> 按 R6 只允许"停止新增"，**禁止删除本地文件**。历史瘦身（LFS/改写历史）需单独立项，见 §6。

### D. 断网 / 网络极差时的交接：bundle

```powershell
# 主导人（能联网时）
powershell -ExecutionPolicy Bypass -File scripts/dev/git-collab-doctor.ps1 -Bundle D:\share\liankao-20261029.bundle

# 同伴
git bundle verify D:\share\liankao-20261029.bundle
git fetch D:\share\liankao-20261029.bundle "refs/remotes/origin/*:refs/remotes/origin/*"
git checkout -B feat/xxx origin/main
```

bundle 是**单文件、可校验、可断点续传（网盘/微信）**，比反复 `git pull` 可靠；体量与 `.git` 同量级（约 900 MB），所以只用于"完全不通"的场景。

### E. 凭据

```powershell
git config --global credential.helper manager
```

避免每次 push 弹窗；也避免有人把 token 写进 URL（会随 `.git/config` 泄露）。

---

## 4. 日常协作规约（团队必守）

| 规则 | 说明 |
|---|---|
| 1. 一个任务一个分支 | `fix/<缺陷号>-<简述>`、`feat/<模块>-<简述>`，禁止多人共用一条分支 |
| 2. 开工先对齐 | `git checkout main && git pull --rebase origin main`，再 `git checkout -b <branch>` |
| 3. 提交前 | `git status` 自查：不得出现 `backend/data/*.db`、`backend/uploads/`、`题库/` 大文件、`.env` |
| 4. 完成即 push 分支 | 推自己的分支，由主导人合并 main；不直接 push main（除非本人就是主导人且已过门禁） |
| 5. 合并前跑门禁 | `python backend/scripts/gates/gate_all.py --quick`（4 项），改动涉及数据/API 时跑全量 |
| 6. 合并用 `--no-ff` | 保留合并提交，便于回溯与回滚 |
| 7. 分支用完即删 | 本地 + 远端一起删，`git fetch --prune` 保持远端列表干净 |
| 8. 文档双写 | 方案进 `docs/superpowers/specs/`（或 `plans/`），并在 `docs/README.md` 加索引行（AGENTS §1） |

### 历史教训（必须避免重演）

- 2026-10-25：`feat/badge-engine-v4`、`feat/teacher-optimization` 把 `backend/data/question_bank.db` 当受跟踪文件，`merge --abort` 直接删掉运行库。
  → **永不把 `*.db` 提交进仓库**；如某分支历史里带了库，先 `git rm --cached` 再合并。
- 2026-10-27：D1 修复因单点网络失败卡了 1 天。
  → 用 §3B 的三级回退 + §3D 的 bundle，任何单点故障不允许成为"停工理由"。

---

## 5. 验收清单（同伴完成后逐条打勾）

- [ ] `git config --get-regexp 'url\.'` 无残留镜像改写
- [ ] `git remote -v` 中 origin 为 `https://github.com/linxitie/li_an-question_bank.git` 或 SSH over 443
- [ ] `git fetch origin --prune` 成功，`git ls-remote --heads origin` 计数 29
- [ ] `git checkout main && git pull --rebase origin main` 后 `git status` 干净
- [ ] 能 `git push origin <自己的分支>`（不再 403：需被邀请为 collaborator）
- [ ] `powershell -ExecutionPolicy Bypass -File scripts/dev/git-collab-doctor.ps1` 第 4、5 节全绿

> 403 与本次故障是两件事：403 是**仓库写权限**（需 owner 邀请 collaborator / 或 fork+PR）；本次是**链路与配置**。

---

## 6. 后续待办（需单独立项，本次不做）

1. **仓库瘦身**：把 `题库/`（497 MB）与 `backend/uploads/` 中已跟踪的大文件迁到 Git LFS 或对象存储，或改写历史。涉及 R6（题库禁止删除）与全仓 clone 兼容，须先出方案并经用户批准。
2. **停止新增跟踪大文件**：`backend/uploads/` 已在 `.gitignore`，需 `git rm -r --cached backend/uploads` 把历史遗留的已跟踪文件解除跟踪（本地文件保留）。
3. **CI 门禁加体积闸**：提交超过 5 MB 的单个文件直接拒收。
4. **镜像策略**：不把第三方镜像写入 remote；仅在 doctor 脚本里作为临时回退。

---

## 7. 回滚

本方案只改客户端 Git 配置与新增脚本/文档，不改业务代码、不改历史、不动数据：

```powershell
# 恢复原 origin（若曾改过）
git remote set-url origin https://github.com/linxitie/li_an-question_bank.git
# 删除临时镜像 remote
git remote remove mirror
# 撤销本方案的提交
git revert <本方案提交sha>
```

`.git/config` 的改动可用 `git config --global --unset-all url.<key>.insteadof` 反向恢复（原值需自行记录）。
