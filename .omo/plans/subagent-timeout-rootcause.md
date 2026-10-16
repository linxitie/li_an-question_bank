# 修复子代理超时 / 零输出 / 后台无效运行

## TL;DR

> **Quick Summary**: 全部 10 个子代理和 9 个类别被钉死在一个已下线的模型 `opencode/deepseek-v4-flash-free` 上，导致每次子代理调用必在 ~12 秒后报 `Unexpected server error` 且零输出。修复方式是按"轻/重"重新分层分配已实测存活的模型、拉高超时阈值、把明文密钥迁到环境变量，并补齐模型存活自检脚本与后台任务看护三层防护。
>
> **Deliverables**:
> - `oh-my-openagent.json` 全量模型重分配（轻活 → `step-5-preview-free`，重活 → `space-bunny-free`）
> - `opencode.json` fallback 链重建 + `timeoutMs` 60000 → 300000 + 显式 provider 超时 + API Key 环境变量化
> - `scripts/check-model-liveness.ps1` — 模型存活批量自检
> - `scripts/watch-bg-task.ps1` — 后台任务看护（硬超时 + 心跳 + 退出码）
> - `docs/background-tasks.md` — 后台任务使用规范
>
> **Estimated Effort**: Short
> **Parallel Execution**: YES — 3 waves
> **Critical Path**: Task 1（备份） → Task 5/6（配置重写） → Task 7（端到端实测）

---

## Context

### Original Request
用户报告两个症状，要求分析根因并完全解决，且要求拆成多个小问题逐个突破：
1. 每次调用子代理都出现「调用超时、零输出、零生产」
2. 后台使用时「无效运行、不进行下一步任务要求，一直处于无效状态」

### Interview Summary
**已确认决策**：
- D1 模型分配：**全量分层**。轻活 → `step-5-preview-free`(29.1s)，重活 → `space-bunny-free`(23.8s，当前主模型)
- D2 超时：插件 `timeoutMs` `60000` → `300000`
- D3 范围：改配置 + 存活自检脚本 + 后台任务看护
- D4 API Key：迁移到环境变量 `{env:DEEPSEEK_API_KEY}`
- D5 后台看护形态：**三层全上**（配置超时 + 看护脚本 + 规范文档）
- D6 脚本位置：`~/.config/opencode/`，不进业务仓库

**Research Findings（全部为实测，非推断）**：
- 实测方式：`opencode run -m <model> "reply with exactly: PONG"`
- 存活：`space-bunny-free`(23.8s)、`nemotron-3.5-lightning-free`(24.5s)、`big-pickle`(28.4s)、`nemotron-3-ultra-free`(28.4s)、`step-5-preview-free`(29.1s)、`longcat-2.5-preview-free`(40.2s)、`ling-3.1-flash-free`(55.3s)、`mimo-v2.6-flash-free`(61.3s)
- 死亡：`mimo-v2.5-free`(10.2s)、`fledge-alpha-free`(10.4s)、**`deepseek-v4-flash-free`(12.6s)**、`exo-free`(19.5s)、`muse-spark-1.3-contributor-free`(21.4s)、`ling-3.0-flash-fin-free`(94.5s)
- opencode 版本：`1.18.35`，Shell：Windows PowerShell 5.1
- 官方文档确认：`{env:VAR}` 变量替换受支持；**原生 provider timeout 默认本就是 300000ms**，所以真正砍人的是插件的 60s
- `auth.json` 已存在 `deepseek` 凭证条目 → 配置里的明文 key 属重复存储

### Metis Review
**SKIPPED（附带发现，本身即证据）**：调用 Metis 时它挂死 30 分钟未返回。原因与 P1/P2 完全同源——`metis` 代理指向死模型，其 `fallback_models` 也指向同一死模型，导致「主模型失败 → fallback 再失败 → 重试不收敛 → 永不返回」。这是用户症状 2 的**现场复现**，构成独立于配置分析的第 7 条证据。

---

## Work Objectives

### Core Objective
让每一次 `task()` 子代理调用都能返回有效输出，让每一次后台任务都能在有界时间内返回明确结果，不再出现零输出或无限挂起。

### Concrete Deliverables
- `C:\Users\21499\.config\opencode\oh-my-openagent.json` — 19 处模型引用全部替换为实测存活模型
- `C:\Users\21499\.config\opencode\opencode.json` — fallback 链重建、超时阈值、provider 超时、密钥环境变量化
- `C:\Users\21499\.config\opencode\scripts\check-model-liveness.ps1` — 新建
- `C:\Users\21499\.config\opencode\scripts\watch-bg-task.ps1` — 新建
- `C:\Users\21499\.config\opencode\docs\background-tasks.md` — 新建

### Definition of Done
- [ ] `opencode run -m opencode/step-5-preview-free` 在 60 秒内返回非空输出
- [ ] 真实 `task()` 子代理调用（`subagent_type="explore"`）返回非空结果
- [ ] 配置文件中不含任何明文 `sk-` 字符串
- [ ] `check-model-liveness.ps1` 能输出 8 活 / 6 死的分类名单
- [ ] `watch-bg-task.ps1` 对死模型能在硬超时内退出并返回非 0 退出码

### Must Have
- 所有被引用的模型必须**经过 `opencode run` 实测存活验证**，不得凭目录列表判断
- `oh-my-openagent.json` 中每一个 agent 和 category 都必须被显式覆盖，不留遗漏
- fallback 链的**每一个**成员都必须是实测存活模型
- 超时阈值必须 ≥ 实测最慢延迟的 5 倍（最慢 94.5s → 至少 300000ms）
- 变更前必须完成配置备份，且备份可用 `ConvertFrom-Json` 解析验证

### Must NOT Have (Guardrails)
- **禁止改动业务仓库**：`D:\砺安题库\砺安题库\backend`、`src`、`packages`、`dist`、`scripts`、`tools` 等一律零改动
- **禁止在计划文件、脚本、日志、提交记录中出现明文 API Key**
- **禁止使用 `opencode models` 输出或 `models.json` 缓存来判定模型存活**（已证明双向不可信）
- **禁止把 `timeoutMs` 设为 `0` 或关闭超时**（会放大后台挂死问题，与用户诉求相反）
- **禁止一次性重写整个配置文件**而不做备份（配置写坏会导致 opencode 下次启动直接不可用）
- **禁止引入未经用户确认的第三方依赖或插件**

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — 全部验证由 agent 执行。

### Test Decision
- **Infrastructure exists**: N/A（配置/脚本任务，无单元测试框架）
- **Automated tests**: 无单元测试；采用**实证验证**（empirical verification）
- **Framework**: PowerShell 5.1 + `opencode run` CLI
- **验证哲学**：配置类任务的唯一可信证据是「跑一次看结果」，断言必须基于真实 stdout，不能基于「配置看起来对」

### QA Policy
每个任务必须包含 agent 可执行的验证场景，证据保存到 `C:\Users\21499\.config\opencode\.evidence\`。

- **配置任务**：改完后 `Get-Content | ConvertFrom-Json` 解析验证 + `opencode run` 真实调用
- **脚本任务**：`powershell -File <script>` 真实执行 + 退出码断言
- **子代理任务**：真实发起 `task()` 调用并断言返回非空

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (基础设施 — 互不依赖，可完全并行):
├── Task 1: 配置备份与基线快照        [quick]
├── Task 2: 模型存活自检脚本          [quick]
├── Task 3: 后台任务看护脚本          [quick]
└── Task 4: 后台任务使用规范文档      [writing]

Wave 2 (配置重写 — 两个不同文件，可并行；均依赖 Task 1 的备份):
├── Task 5: oh-my-openagent.json 模型分层重写  [quick]
└── Task 6: opencode.json 全量重写            [quick]

Wave 3 (端到端实证验证 — 依赖 Wave 2 全部完成):
└── Task 7: 子代理与后台任务端到端实测  [unspecified-high]

Wave FINAL (4 路并行审查):
├── Task F1: 计划合规审计        [oracle]
├── Task F2: 配置质量与密钥审查   [unspecified-high]
├── Task F3: 真实 QA 复现验证     [unspecified-high]
└── Task F4: 范围保真检查         [deep]
-> 汇总结果 -> 等待用户明确确认
```

### Dependency Matrix

| Task | 依赖 | 被依赖 | Wave |
|---|---|---|---|
| 1 | — | 5, 6 | 1 |
| 2 | — | 7 | 1 |
| 3 | — | — | 1 |
| 4 | — | — | 1 |
| 5 | 1 | 7 | 2 |
| 6 | 1 | 7 | 2 |
| 7 | 2, 5, 6 | F1-F4 | 3 |

### Agent Dispatch Summary

- **Wave 1**: **4** — T1 → `quick`, T2 → `quick`, T3 → `quick`, T4 → `writing`
- **Wave 2**: **2** — T5 → `quick`, T6 → `quick`
- **Wave 3**: **1** — T7 → `unspecified-high`
- **FINAL**: **4** — F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

> Wave 2 只有 2 个任务属**依赖强制**，非拆分不足：Task 5 与 Task 6 虽为不同文件，但都是对 opencode 核心配置的破坏性重写，串行执行可在中途失败时立即回滚，避免同时损坏导致无法定位。

---

## TODOs

- [x] 1. 配置备份与基线快照

  **What to do**:
  - 创建备份目录 `C:\Users\21499\.config\opencode\backup\2026-10-10\`
  - 备份 `opencode.json` 与 `oh-my-openagent.json` 两个文件（保留原文件名）
  - 备份 `oh-my-openagent.json.bak-20260814` 也一并归档，避免混淆新旧基线
  - 生成一份 `BASELINE.md`，记录：opencode 版本（`1.18.35`）、PowerShell 版本、当前 19 处死模型引用的完整清单（原样列出 agent 名 + category 名 + 模型 ID）、当前实测存活名单（8 个）
  - 对每个备份文件执行 `ConvertFrom-Json` 解析验证，确认备份可用而非损坏

  **Must NOT do**:
  - 不得修改任何配置文件内容（本任务只读 + 复制）
  - 不得在 `BASELINE.md` 中写入明文 API Key（opencode.json 第 22 行的 key 需脱敏为 `sk-1a80***`）

  **Recommended Agent Profile**:
  - **Category**: `quick` — 纯文件复制 + 一份 Markdown 记录，无逻辑复杂度
  - **Skills**: 无需加载。纯文件操作，不涉及代码库导航或 UI

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (与 Task 2/3/4 并行，均不触碰配置内容)
  - **Blocks**: Task 5, Task 6
  - **Blocked By**: None

  **References**:
  - `C:\Users\21499\.config\opencode\opencode.json:1-34` — 待备份目标之一；第 22 行含明文 key，脱敏时注意
  - `C:\Users\21499\.config\opencode\oh-my-openagent.json:1-116` — 待备份目标之二；19 处 `opencode/deepseek-v4-flash-free` 引用分布在此
  - `.omo/drafts/subagent-timeout-rootcause.md` — 已实测的存活/死亡名单，直接抄入 `BASELINE.md`，**不要重新实测**

  **Acceptance Criteria**:
  - [ ] `backup\2026-10-10\opencode.json` 存在且 `Get-Content backup\2026-10-10\opencode.json -Raw | ConvertFrom-Json` 无异常抛出
  - [ ] `backup\2026-10-10\oh-my-openagent.json` 存在且同上解析通过
  - [ ] `BASELINE.md` 存在，包含 19 处死模型引用清单与 8 个存活模型名单
  - [ ] `Select-String -Path BASELINE.md -Pattern 'sk-[a-f0-9]{20,}'` 返回 0 条（密钥未泄漏到文档）

  **QA Scenarios**:
  ```
  Scenario: 备份完整且可解析
    Tool: Bash (PowerShell)
    Preconditions: C:\Users\21499\.config\opencode\ 存在
    Steps:
      1. 执行 Test-Path "C:\Users\21499\.config\opencode\backup\2026-10-10\opencode.json" -PathType Leaf
      2. 执行 Get-Content "C:\Users\21499\.config\opencode\backup\2026-10-10\opencode.json" -Raw | ConvertFrom-Json
      3. 同样验证 oh-my-openagent.json 备份
      4. 执行 Select-String -Path "C:\Users\21499\.config\opencode\backup\2026-10-10\BASELINE.md" -Pattern 'sk-[a-f0-9]{20,}'
    Expected Result: 步骤 1 返回 True；步骤 2/3 无错误输出且可访问 .plugin 属性；步骤 4 返回 0 行
    Failure Indicators: 备份文件缺失、ConvertFrom-Json 抛 ParseException、BASELINE.md 出现完整 sk- 开头的 32 位密钥
    Evidence: C:\Users\21499\.config\opencode\.evidence\task-1-backup.txt

  Scenario: 阴性 — 确认备份内容与原文件逐字节一致
    Tool: Bash (PowerShell)
    Preconditions: 备份已完成
    Steps:
      1. 执行 (Get-FileHash "C:\Users\21499\.config\opencode\opencode.json").Hash -eq (Get-FileHash "C:\Users\21499\.config\opencode\backup\2026-10-10\opencode.json").Hash
      2. 对 oh-my-openagent.json 执行同样比对
    Expected Result: 两次比对均返回 True
    Failure Indicators: 任一比对返回 False，说明备份过程损坏或漏拷贝
    Evidence: C:\Users\21499\.config\opencode\.evidence\task-1-hash.txt
  ```

  **Commit**: NO — 本任务位于 `C:\Users\21499\.config\opencode\`，不属于业务仓库，不做 git 提交

- [x] 2. 模型存活批量自检脚本

  **What to do**:
  - 新建 `C:\Users\21499\.config\opencode\scripts\check-model-liveness.ps1`
  - 参数设计：
    - `-Models` 可选，默认为空；为空时自动拉取 `opencode models` 输出中所有 `opencode/*` 条目
    - `-TimeoutSec` 默认 `120`（单模型硬超时，覆盖实测最慢 94.5s）
    - `-OutFile` 默认 `C:\Users\21499\.config\opencode\.evidence\model-liveness-<yyyyMMdd-HHmmss>.txt`
  - 核心逻辑：对每个候选模型执行 `opencode run -m <model> "reply with exactly: PONG"`，用 `Stopwatch` 计时
  - 判定规则（三态，**不可只判成败**）：
    - `ALIVE` — stdout 含 `PONG`
    - `DEAD` — 进程退出或输出含 `Unexpected server error` / `UnknownError`
    - `TIMEOUT` — 超过 `-TimeoutSec` 未返回（对应 `ling-3.0-flash-fin-free` 94.5s 那一类）
  - 输出格式：每行 `<状态> <模型ID> <耗时ms>`，末尾汇总 `ALIVE=N DEAD=N TIMEOUT=N`
  - 进程调用必须用 `Start-Process` + `WaitForExit(ms)` 或 job 轮询，**禁止**直接 `opencode run` 裸调用（否则脚本自身会被慢模型拖死，重演用户的挂死问题）
  - 脚本自身也必须设定总时长上限并在超时时优雅退出，不要无限循环
  - 写入 UTF-8 编码

  **Must NOT do**:
  - 不得把密钥、token、任何凭证写入脚本或输出文件
  - 不得用 `opencode models` 的返回结果直接当作「存活」结论（已证明该列表 11 个里有 3 个是死的）
  - 不得修改 `opencode.json` 或 `oh-my-openagent.json`（本任务只产出脚本，不动配置）
  - 不得触碰业务仓库 `D:\砺安题库\砺安题库\` 下的任何文件

  **Recommended Agent Profile**:
  - **Category**: `quick` — 单文件 PowerShell 脚本，逻辑直接（循环 + 计时 + 断言）
  - **Skills**: 无需加载。不涉及前端/代码库导航

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (与 Task 1/3/4 并行；只新建 scripts/ 目录下的文件，与 Task 1 的 backup/ 目录、Task 4 的 docs/ 目录互不重叠)
  - **Blocks**: Task 7
  - **Blocked By**: None

  **References**:
  - `.omo/drafts/subagent-timeout-rootcause.md` 的实测名单表 — 三态判定规则的实证依据；已知 ALIVE 8 个 / DEAD 6 个
  - `C:\Users\21499\.config\opencode\opencode.json:1-34` — 只读参考，确认不要误改
  - 官方文档 https://opencode.ai/docs/config/ — `timeout`/`chunkTimeout` 可设 `false` 的语义，本脚本的 `-TimeoutSec` 语义与之对齐

  **Acceptance Criteria**:
  - [ ] `powershell -File C:\Users\21499\.config\opencode\scripts\check-model-liveness.ps1 -Models "opencode/deepseek-v4-flash-free","opencode/space-bunny-free" -TimeoutSec 120` 退出码为 0
  - [ ] 上述调用输出恰好两行：一行 `DEAD ... deepseek-v4-flash-free`，一行 `ALIVE ... space-bunny-free`
  - [ ] 输出末尾汇总行为 `ALIVE=1 DEAD=1 TIMEOUT=0`
  - [ ] 对 `opencode/ling-3.0-flash-fin-free` 运行时，能在 `-TimeoutSec` 内终止并标记为 `TIMEOUT`，脚本本身不挂死
  - [ ] 脚本在 `-Models` 传入空值（自动模式）时不会因某个模型卡死而整体卡死

  **QA Scenarios**:
  ```
  Scenario: 混合存活的两个模型被正确三态分类
    Tool: Bash (PowerShell)
    Preconditions: 脚本已创建；opencode CLI 在 PATH 中
    Steps:
      1. 执行 powershell -File "C:\Users\21499\.config\opencode\scripts\check-model-liveness.ps1" -Models "opencode/deepseek-v4-flash-free","opencode/space-bunny-free" -TimeoutSec 120
      2. 捕获 $LASTEXITCODE
      3. 将 stdout 逐行匹配 '^(ALIVE|DEAD|TIMEOUT) '
      4. 匹配 'ALIVE=1 DEAD=1 TIMEOUT=0'
    Expected Result: 步骤2 退出码 0；步骤3 命中 2 行，第一行以 DEAD 开头且含 deepseek-v4-flash-free，第二行以 ALIVE 开头且含 space-bunny-free；步骤4 汇总行完全匹配
    Failure Indicators: deepseek-v4-flash-free 被标为 ALIVE（说明误判，模型实际已死）；退出码非 0；汇总计数与实际行数不符
    Evidence: C:\Users\21499\.config\opencode\.evidence\task-2-classify.txt

  Scenario: 阴性 — 慢模型触发超时而非拖死脚本
    Tool: Bash (PowerShell)
    Preconditions: 脚本已创建
    Steps:
      1. 记录 $sw = [Diagnostics.Stopwatch]::StartNew()
      2. 执行 powershell -File "...check-model-liveness.ps1" -Models "opencode/ling-3.0-flash-fin-free" -TimeoutSec 45
      3. 记录 $sw.Stop() 并输出 $sw.ElapsedMilliseconds
      4. 断言输出含 'TIMEOUT opencode/ling-3.0-flash-fin-free'
    Expected Result: 步骤3 总耗时 < 90000ms（45s 超时 + 开销余量）；步骤4 匹配成功；脚本正常返回而非无限挂起
    Failure Indicators: 总耗时 > 180000ms 说明脚本自身的超时机制失效、重演用户原始 bug；输出无 TIMEOUT 标记
    Evidence: C:\Users\21499\.config\opencode\.evidence\task-2-timeout.txt
  ```

  **Commit**: NO — 同 Task 1，位于个人配置目录，不做 git 提交

- [x] 3. 后台任务看护脚本

  **What to do**:
  - 新建 `C:\Users\21499\.config\opencode\scripts\watch-bg-task.ps1`
  - 定位：解决用户症状 2「后台一直无效状态」。让每个后台调用都有**硬超时 + 心跳日志 + 退出码校验**，挂死能被立即发现而非无限等待
  - 参数设计：
    - `-Command`（必填）要执行的命令字符串
    - `-TimeoutSec` 默认 `300`（与 Task 6 配置的 300000ms 对齐）
    - `-HeartbeatSec` 默认 `15`，每 15 秒向日志写一行心跳（含已耗时）
    - `-LogFile` 默认 `C:\Users\21499\.config\opencode\.evidence\bg-task-<yyyyMMdd-HHmmss>.log`
  - 核心逻辑：
    1. 启动目标命令为后台进程
    2. 循环：每隔 `-HeartbeatSec` 检查一次；已超时则**强制终止进程树**并以退出码 `124` 退出（124 是 GNU timeout 约定的超时码）
    3. 进程自然结束则回传其真实退出码
  - 日志每行带时间戳，区分 `[START]` / `[HEARTBEAT]` / `[EXIT]` / `[TIMEOUT]` 四类事件
  - 关键：**必须终止整个进程树**。Windows 上 `opencode` 会派生子进程，只杀父进程会导致孤儿进程继续占用，属"无效运行"的另一种形态
  - 进程启动同样要用 `Start-Process`，禁止裸调用

  **Must NOT do**:
  - 不得在任何路径下无限等待（必须有 `-TimeoutSec` 上限，默认 300 秒）
  - 不得写入任何凭证
  - 不得修改配置文件（本任务只产出脚本）
  - 不得触碰业务仓库

  **Recommended Agent Profile**:
  - **Category**: `quick` — 单文件脚本，但涉及进程树管理，逻辑比 Task 2 略重
  - **Skills**: 无需加载。纯 PowerShell 进程控制

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (与 Task 1/2/4 并行；同属 scripts/ 目录但不同文件名，无写冲突)
  - **Blocks**: 无
  - **Blocked By**: None

  **References**:
  - `.omo/drafts/subagent-timeout-rootcause.md` — `ling-3.0-flash-fin-free` 94.5s 超时实测，是「慢模型拖死」的直接证据，决定了 `-TimeoutSec` 默认值应 ≥ 300
  - 本次会话中 Metis 调用挂死 1800000ms 未返回 — 这是症状 2 的现场复现，脚本需确保同类场景可在 `-TimeoutSec` 内收敛

  **Acceptance Criteria**:
  - [ ] `powershell -File C:\Users\21499\.config\opencode\scripts\watch-bg-task.ps1 -Command "ping -n 10 127.0.0.1" -TimeoutSec 300 -HeartbeatSec 2` 退出码为 0，日志含 `[START]` 与 `[EXIT]`
  - [ ] `powershell -File ...watch-bg-task.ps1 -Command "Start-Sleep -Seconds 600" -TimeoutSec 20 -HeartbeatSec 5` 在 < 60000ms 内退出，退出码为 `124`，日志含至少 2 条 `[HEARTBEAT]` 与 1 条 `[TIMEOUT]`
  - [ ] 超时场景结束后，系统中不存在残留的 `powershell` 子进程（验证进程树被正确清理）
  - [ ] 日志文件按 `[时间戳] [事件类型] [内容]` 格式输出，可用 `Select-String -Pattern '\[HEARTBEAT\]'` 检索

  **QA Scenarios**:
  ```
  Scenario: 正常命令完整跑完并回传退出码
    Tool: Bash (PowerShell)
    Preconditions: 脚本已创建
    Steps:
      1. 执行 powershell -File "C:\Users\21499\.config\opencode\scripts\watch-bg-task.ps1" -Command "ping -n 6 127.0.0.1" -TimeoutSec 120 -HeartbeatSec 2
      2. 捕获 $LASTEXITCODE，断言等于 0
      3. 读取生成的 .log 文件
      4. 断言日志含 '[START]'、含 '[EXIT]'、含 '[EXIT] code=0'
    Expected Result: 退出码 0；日志三处断言全部命中；总耗时接近 ping 实际耗时（约 5 秒）而非超时上限
    Failure Indicators: 退出码非 0；日志缺 [EXIT]；脚本在命令早已结束后仍继续等待（心跳未停止）
    Evidence: C:\Users\21499\.config\opencode\.evidence\task-3-normal.txt

  Scenario: 阴性 — 挂死命令被强制收敛且无进程残留
    Tool: Bash (PowerShell)
    Preconditions: 脚本已创建
    Steps:
      1. 记录 $sw=[Diagnostics.Stopwatch]::StartNew()
      2. 执行 powershell -File "...watch-bg-task.ps1" -Command "Start-Sleep -Seconds 600" -TimeoutSec 20 -HeartbeatSec 5
      3. 记录 $sw.Stop()，输出耗时
      4. 捕获退出码，断言等于 124
      5. 执行 Get-Process powershell -ErrorAction SilentlyContinue 统计子进程数
      6. 读取日志，断言含 '[TIMEOUT]' 且 '[HEARTBEAT]' 出现次数 >= 2
    Expected Result: 步骤3 耗时在 20000~45000ms 之间；步骤4 退出码 124；步骤6 全部断言命中；步骤5 无因本次调用新增的残留进程
    Failure Indicators: 耗时接近 600000ms（说明未超时，等了 Start-Sleep 跑完）；退出码不是 124；日志无 [TIMEOUT]；残留孤儿进程
    Evidence: C:\Users\21499\.config\opencode\.evidence\task-3-timeout.txt
  ```

  **Commit**: NO — 同前，配置目录不做 git 提交

- [x] 4. 后台任务使用规范文档

  **What to do**:
  - 新建 `C:\Users\21499\.config\opencode\docs\background-tasks.md`
  - 目的：从使用侧根治症状 2。配置层的超时是最后一道防线，规范层才是第一道
  - 必须覆盖的内容：
    1. **为什么会有这个问题** — 简述免费模型 23~94s 的真实延迟，以及超时阈值与延迟的关系（附本次实测数据表）
    2. **后台任务三条硬规则**：
       - 每个后台任务必须有界（明确说明要查什么、查到什么程度算完成），禁止开放式"探索一下"
       - 每个后台任务必须回传非空结构化输出（文件路径 / 行号 / 结论），禁止只回一句"已完成"
       - 后台任务数 ≥ 3 个时才使用并行；1~2 个直接同步调用，避免后台机制本身成为延迟来源
    3. **失败诊断速查表** — 症状 → 可能原因 → 处置：
       - 「超时+零输出」→ 模型已下线，查自检名单
       - 「挂死不推进」→ 重试不收敛，立即 Ctrl+C 并查 fallback 链
       - 「结果不全」→ 任务无界，收紧范围重跑
    4. **可用模型名单（附实测日期）** — 8 个 ALIVE 模型 + 延迟，注明「opencode 免费模型会轮换，用 `check-model-liveness.ps1` 重新验证，不要凭本文档直接采信」
    5. **禁止行为**：禁止凭 `opencode models` 输出判定存活；禁止把慢模型用于 1~2 步的轻活
  - 文档必须标注实测日期 `2026-10-10` 与 opencode 版本 `1.18.35`，并声明名单有时效性

  **Must NOT do**:
  - 不得在文档中写入任何模型密钥或 API Key
  - 不得把文档路径放到业务仓库 `D:\砺安题库\砺安题库\` 下
  - 不得声称修复后延迟会变快（本次修复只消除失败与挂死，不改变模型固有延迟）—— 避免误导

  **Recommended Agent Profile**:
  - **Category**: `writing` — 纯文档产出，无代码逻辑
  - **Skills**: 无需加载

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (与 Task 1/2/3 并行；新建 docs/ 目录，与其他任务写入路径无重叠)
  - **Blocks**: 无
  - **Blocked By**: None

  **References**:
  - `.omo/drafts/subagent-timeout-rootcause.md` — 全部实测数据的唯一来源（8 活/6 死名单、各自延迟、Metis 挂死事件），直接引用，**不要重新跑测试**
  - `C:\Users\21499\.config\opencode\opencode.json:4-15` — 当前 60s `timeoutMs` 的出处，规范文档解释超时时引用此值

  **Acceptance Criteria**:
  - [ ] `C:\Users\21499\.config\opencode\docs\background-tasks.md` 存在且字数 > 800
  - [ ] `Select-String -Path <file> -Pattern 'sk-[a-f0-9]{20,}'` 返回 0 行
  - [ ] 文档含"三条硬规则"完整小节，且每条均可被独立引用
  - [ ] 文档含失败诊断速查表，至少 3 条症状
  - [ ] 文档明确标注实测日期 2026-10-10 与 opencode 1.18.35
  - [ ] 文档含 `check-model-liveness.ps1` 的引用路径

  **QA Scenarios**:
  ```
  Scenario: 文档要素完整且无密钥泄漏
    Tool: Bash (PowerShell)
    Preconditions: 文档已创建
    Steps:
      1. 执行 (Get-Item "<file>").Length 并确认 > 800 字符
      2. 执行 Select-String -Path "<file>" -Pattern 'sk-[a-f0-9]{20,}'，断言 0 行
      3. 执行 Select-String -Path "<file>" -Pattern '硬规则'，断言命中
      4. 执行 Select-String -Path "<file>" -Pattern 'check-model-liveness\.ps1'，断言命中
      5. 执行 Select-String -Path "<file>" -Pattern '2026-10-10'，断言命中
    Expected Result: 步骤1 长度达标；步骤2 零命中；步骤3/4/5 各至少 1 命中
    Failure Indicators: 出现完整 sk- 密钥；缺少硬规则小节；缺少自检脚本引用；缺少时效性声明
    Evidence: C:\Users\21499\.config\opencode\.evidence\task-4-doc.txt

  Scenario: 阴性 — 文档不得作出无法兑现的性能承诺
    Tool: Bash (PowerShell)
    Preconditions: 文档已创建
    Steps:
      1. 执行 Select-String -Path "<file>" -Pattern '变快|提速|加速|性能提升'
      2. 逐条人工核对命中处上下文，确认是否属于「承诺延迟会降低」的误导性表述
    Expected Result: 零命中，或命中处上下文均明确说明「本次修复只消除失败与挂死，不改变模型固有延迟」
    Failure Indicators: 存在承诺延迟降低的表述而未加限定说明，构成对用户的误导
    Evidence: C:\Users\21499\.config\opencode\.evidence\task-4-doc-claims.txt
  ```

  **Commit**: NO — 配置目录不做 git 提交

- [x] 5. oh-my-openagent.json 模型分层重写

  **What to do**:
  - 修改 `C:\Users\21499\.config\opencode\oh-my-openagent.json`，把全部 **19 处** `opencode/deepseek-v4-flash-free` 替换为分层模型
  - **轻活层 → `opencode/step-5-preview-free`**（实测 29.1s）：
    - agents: `atlas`、`explore`、`librarian`、`sisyphus-junior`、`multimodal-looker`
    - categories: `quick`、`unspecified-low`
  - **重活层 → `opencode/space-bunny-free`**（实测 23.8s，当前主模型，判断力最稳）：
    - agents: `oracle`、`metis`、`momus`、`prometheus`、`sisyphus`
    - categories: `deep`、`ultrabrain`、`artistry`、`writing`、`visual-engineering`、`unspecified-high`
  - **`fallback_models` 同步改造**（这是被漏掉的第二层保险，当前全部指向死模型）：
    - 每个 `fallback_models` 数组改为 `[{"model": "<与主模型不同的另一个存活模型>"}]`
    - 轻活层主模型 `step-5-preview-free` → fallback `big-pickle`（实测 28.4s）
    - 重活层主模型 `space-bunny-free` → fallback `nemotron-3.5-lightning-free`（实测 24.5s）
  - 保持 JSON 结构与缩进风格不变；仅替换 model 值与 fallback 数组内容，不新增/删除任何 key
  - **当前只有 `metis`、`momus`、`prometheus` 三个 agent 有 `fallback_models`**，其余 agent 无此字段 —— 保持这一现状，不要给其他 agent 补加

  **Must NOT do**:
  - **禁止引入任何未在存活名单内的模型**（尤其禁止重新写回 `deepseek-v4-flash-free`）
  - 禁止修改 agent/category 的**键名**（`oracle` 不能写成 `Oracle`，大小写敏感）
  - 禁止删除 `fallback_models` 字段来「简化」——那会移除一层保险
  - 禁止修改 `$schema` 行
  - 禁止触碰业务仓库

  **Recommended Agent Profile**:
  - **Category**: `quick` — 机械替换 19 处字符串值，无算法复杂度；但**精确性要求极高**，故不用 `deep`
  - **Skills**: 无需加载

  **Parallelization**:
  - **Can Run In Parallel**: YES（与 Task 6 并行）
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 7
  - **Blocked By**: Task 1（必须先有备份才能改）

  **References**:
  - `C:\Users\21499\.config\opencode\oh-my-openagent.json:4-48` — agents 段，10 个 agent 定义
  - `C:\Users\21499\.config\opencode\oh-my-openagent.json:50-115` — categories 段，9 个 category 定义
  - `C:\Users\21499\.config\opencode\oh-my-openagent.json:14-18` — `metis.fallback_models` 当前指向死模型，是 P2 的直接证据
  - `C:\Users\21499\.config\opencode\backup\2026-10-10\oh-my-openagent.json` — 回滚点
  - `.omo/drafts/subagent-timeout-rootcause.md` — 8 个存活模型的实测延迟，决定 fallback 选择

  **Acceptance Criteria**:
  - [ ] `Get-Content oh-my-openagent.json -Raw | ConvertFrom-Json` 解析成功无异常
  - [ ] `Select-String -Path oh-my-openagent.json -Pattern 'deepseek-v4-flash-free'` 返回 **0 行**
  - [ ] `Select-String -Path oh-my-openagent.json -Pattern 'step-5-preview-free' | Measure-Object` 计数 = 7（5 个轻活 agent + 2 个轻活 category）
  - [ ] `Select-String -Path oh-my-openagent.json -Pattern 'space-bunny-free' | Measure-Object` 计数 = 14（7 个重活 agent + 7 个重活 category）
  - [ ] agent 数量仍为 10、category 数量仍为 9（用 `$j.agents.PSObject.Properties.Count` 与 `$j.categories.PSObject.Properties.Count` 断言）
  - [ ] `fallback_models` 中不含任何死模型（对 3 个 fallback 数组逐一断言）

  **QA Scenarios**:
  ```
  Scenario: 死模型被彻底清除且结构完好
    Tool: Bash (PowerShell)
    Preconditions: Task 1 备份已完成
    Steps:
      1. 执行 $j = Get-Content "C:\Users\21499\.config\opencode\oh-my-openagent.json" -Raw | ConvertFrom-Json
      2. 断言 $j.agents.PSObject.Properties.Count -eq 10
      3. 断言 $j.categories.PSObject.Properties.Count -eq 9
      4. 执行 Select-String -Path "<file>" -Pattern 'deepseek-v4-flash-free'，断言 0 行
      5. 遍历 $j.agents 与 $j.categories 的所有 model 值 + 所有 fallback_models 值，与存活名单 {space-bunny-free, step-5-preview-free, big-pickle, nemotron-3.5-lightning-free, nemotron-3-ultra-free, longcat-2.5-preview-free, ling-3.1-flash-free, mimo-v2.6-flash-free, nemotron-3.5-lightning-free} 求交集
      6. 断言交集为空集（步骤5的差集为空）
    Expected Result: 步骤1 解析成功；步骤2=10；步骤3=9；步骤4 零命中；步骤5/6 所有模型值均属存活名单
    Failure Indicators: 步骤4 仍有命中（死模型残留）；agent/category 数量变化（误删 key）；任一模型值不在存活名单内
    Evidence: C:\Users\21499\.config\opencode\.evidence\task-5-verify.txt

  Scenario: 阴性 — fallback 链中不得残留死模型
    Tool: Bash (PowerShell)
    Preconditions: 配置已改
    Steps:
      1. 执行 $j = Get-Content "<file>" -Raw | ConvertFrom-Json
      2. 遍历 @('metis','momus','prometheus')，输出每个 agent 的 fallback_models[0].model
      3. 断言 metis.fallback_models[0].model -eq 'nemotron-3.5-lightning-free'
      4. 断言 momus.fallback_models[0].model -eq 'nemotron-3.5-lightning-free'
      5. 断言 prometheus.fallback_models[0].model -eq 'nemotron-3.5-lightning-free'
      6. 断言 $j.metis.fallback_models[0].model -ne $j.metis.model（主备不得相同）
    Expected Result: 步骤3/4/5 均为 True；步骤6 为 True；无任何 fallback 指向 deepseek-v4-flash-free
    Failure Indicators: 步骤6 为 False（主备同模型，等于没有备份）；任一 fallback 仍是死模型
    Evidence: C:\Users\21499\.config\opencode\.evidence\task-5-fallback.txt
  ```

  **Commit**: NO — 个人配置目录，不做 git 提交

- [x] 6. opencode.json 全量重写

  **What to do**:
  - 修改 `C:\Users\21499\.config\opencode\opencode.json`，一次性完成 4 项变更：
  - **变更 1 — API Key 环境变量化（P6）**：
    - 第 22 行 `"apiKey": "<已吊销-勿复用-新密钥填入 .env 的 DEEP_SEEK_API_KEY>"` → `"apiKey": "{env:DEEPSEEK_API_KEY}"`
    - **同一次改动中，必须把真实 key 写入 Windows 用户环境变量** `DEEPSEEK_API_KEY`（用 `[Environment]::SetEnvironmentVariable('DEEPSEEK_API_KEY', '<原key>', 'User')`）
    - 若 `auth.json` 中已有可用的 `deepseek` 凭证，则确认其有效后可不再重复注入环境变量；两处并存时以 auth.json 为准，本变更的核心诉求是**配置文件里不留明文**
  - **变更 2 — fallback 链重建（P2）**：
    - 现有链 `[fledge-alpha-free(死), nemotron-3.5-lightning-free(活), mimo-v2.5-free(死)]` → `[space-bunny-free, nemotron-3.5-lightning-free, step-5-preview-free]`
    - 全部三个成员均为实测存活；把最快的放首位减少首跳失败
  - **变更 3 — 超时阈值（P3）**：
    - `experimental.modelFallbackChain.timeoutMs`: `60000` → `300000`
  - **变更 4 — 显式 provider 超时（后台看护第 1 层，D5）**：
    - 在 `provider.opencode.options` 下新增 `"timeout": 300000, "headerTimeout": 300000, "chunkTimeout": 120000`
    - `headerTimeout` 覆盖「等响应头」，`chunkTimeout` 覆盖「流式块间隔」—— 二者能让卡死的连接**自行退出**，而不是无限挂着
    - 注意：`provider.opencode` 在原文件中并不存在，**需新建该节点**；这是官方文档明确支持的配置项
  - 保持 `plugin`、`$schema`、`provider.deepseek` 其余字段不变

  **Must NOT do**:
  - **禁止在改完后仍留下任何明文 `sk-` 字符串**（用 `Select-String` 强制断言）
  - 禁止把 `timeoutMs` 设为 `0` 或 `false`（用户明确否决；会导致后台无限挂死，与诉求相反）
  - 禁止删除 `provider.deepseek` 节点或改动其 `baseURL`
  - 禁止改动 `plugin` 数组（`opencode-model-fallback-chain` 需保留）
  - 禁止触碰业务仓库

  **Recommended Agent Profile**:
  - **Category**: `quick` — 单文件 4 项定点修改，但涉及凭证与超时语义，准确性要求高
  - **Skills**: 无需加载

  **Parallelization**:
  - **Can Run In Parallel**: YES（与 Task 5 并行，操作不同文件）
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 7
  - **Blocked By**: Task 1

  **References**:
  - `C:\Users\21499\.config\opencode\opencode.json:4-15` — `experimental.modelFallbackChain` 块，变更 2/3 的目标
  - `C:\Users\21499\.config\opencode\opencode.json:16-33` — `provider` 块，变更 1/4 的目标；第 22 行为明文 key
  - 官方文档 https://opencode.ai/docs/config/ — 确认 `{env:VAR}` 语法可用（已验证）；确认 `provider.<id>.options.timeout/headerTimeout/chunkTimeout` 均为合法字段且默认 300000、可设 `false`
  - `C:\Users\21499\.local\share\opencode\auth.json` — 已含 `deepseek` 条目，变更 1 需先确认其可用性（**读取时不要打印 key 内容**）
  - `C:\Users\21499\.config\opencode\backup\2026-10-10\opencode.json` — 回滚点

  **Acceptance Criteria**:
  - [ ] `Get-Content opencode.json -Raw | ConvertFrom-Json` 解析成功
  - [ ] `Select-String -Path opencode.json -Pattern 'sk-[a-f0-9]{20,}'` 返回 **0 行**
  - [ ] `$j.provider.deepseek.options.apiKey` 值恰为字符串 `{env:DEEPSEEK_API_KEY}`（含花括号）
  - [ ] `$j.experimental.modelFallbackChain.timeoutMs` 等于 `300000`
  - [ ] fallback 链三个成员全部属于存活名单，且**不含** `fledge-alpha-free` 与 `mimo-v2.5-free`
  - [ ] `$j.provider.opencode.options.timeout` = 300000、`headerTimeout` = 300000、`chunkTimeout` = 120000
  - [ ] `[Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')` 非空（若走 auth.json 路线则此项可豁免，需在证据中说明）
  - [ ] 改完后 `opencode run -m opencode/step-5-preview-free "reply with exactly: PONG"` 仍能正常返回（确认没把 opencode 改坏）

  **QA Scenarios**:
  ```
  Scenario: 配置合法、密钥已脱敏、超时已提升
    Tool: Bash (PowerShell)
    Preconditions: Task 1 备份已完成
    Steps:
      1. 执行 $j = Get-Content "C:\Users\21499\.config\opencode\opencode.json" -Raw | ConvertFrom-Json
      2. 断言 $j.experimental.modelFallbackChain.timeoutMs -eq 300000
      3. 断言 $j.provider.opencode.options.timeout -eq 300000 -and $j.provider.opencode.options.headerTimeout -eq 300000
      4. 执行 Select-String -Path "<file>" -Pattern 'sk-[a-f0-9]{20,}'，断言 0 行
      5. 断言 $j.provider.deepseek.options.apiKey -eq '{env:DEEPSEEK_API_KEY}'
      6. 遍历 $j.experimental.modelFallbackChain.chains[0]，断言不含 fledge-alpha-free 与 mimo-v2.5-free
    Expected Result: 步骤1 解析成功；步骤2/3/5 均为 True；步骤4 零命中；步骤6 断言通过
    Failure Indicators: 步骤4 出现明文密钥；步骤2 仍为 60000；步骤3 provider.opencode 节点缺失导致 $null 比较失败；步骤6 链中仍有死模型
    Evidence: C:\Users\21499\.config\opencode\.evidence\task-6-config.txt

  Scenario: 阴性 — 改动未破坏 opencode 可用性
    Tool: Bash (PowerShell)
    Preconditions: 配置已改
    Steps:
      1. 记录 $sw=[Diagnostics.Stopwatch]::StartNew()
      2. 执行 opencode run -m opencode/step-5-preview-free "reply with exactly: PONG"
      3. 记录耗时与输出
      4. 断言输出含 'PONG'，且耗时 < 120000ms
    Expected Result: 步骤4 全部通过；说明配置语法正确且 opencode 仍能正常启动加载配置
    Failure Indicators: 出现 JSON 解析错误、配置加载报错、或 UnknownError（说明 opencode.json 被改坏）
    Evidence: C:\Users\21499\.config\opencode\.evidence\task-6-smoke.txt
  ```

  **Commit**: NO — 同前

- [x] 7. 子代理与后台任务端到端实证验证

  **What to do**:
  - 这是整个计划的**验收关卡**。前 6 个任务只是"配置看起来对"，本任务要证明"实际真的能用"
  - 依次执行以下实测，任一失败即视为修复未完成：
  - **验证 A — 真实子代理调用**：发起一次真实 `task(subagent_type="explore")` 调用，prompt 要求其查找仓库中 `backend` 目录下的一个已知文件路径，断言返回内容**非空且包含该路径**
    - 这是对用户症状 1「调用超时、零输出、零生产」的直接回归测试
    - 必须断言返回值非空 —— 修复前该调用会在 ~12s 后返回空或报错
  - **验证 B — 全部 8 个存活模型复检**：跑 `check-model-liveness.ps1 -Models <8个存活模型> -TimeoutSec 120`，断言 `DEAD=0`
  - **验证 C — 死模型确认仍然失败**：跑同一脚本测 `deepseek-v4-flash-free`，断言其为 `DEAD`（证明脚本能识别死模型，而非一律放行）
  - **验证 D — 后台任务收敛**：用 `watch-bg-task.ps1` 包裹一次真实的 `opencode run`，断言在 `-TimeoutSec` 内以 0 或 124 退出，日志含 `[EXIT]` 或 `[TIMEOUT]`
  - **验证 E — 密钥脱敏终检**：对 `~/.config/opencode/` 下所有 `.json` 与 `.md` 与 `.ps1` 全量扫描 `sk-[a-f0-9]{20,}`，断言 0 命中
  - **验证 F — 业务仓库零改动**：在业务仓库执行 `git status --porcelain`，断言输出中不含 `backend/`、`src/`、`packages/`、`dist/` 任何路径
  - 将 A~F 的完整输出汇总写入 `C:\Users\21499\.config\opencode\.evidence\final-e2e.txt`

  **Must NOT do**:
  - 禁止为了让验证通过而放宽断言（例如把"非空输出"改成"有响应即可"）
  - 禁止在验证过程中修改任何配置文件来"让测试通过"——验证失败就应回到 Wave 2 修配置，而非放宽标准
  - 禁止跳过验证 A（它是唯一能直接证明用户症状已消除的测试）
  - 禁止触碰业务仓库（验证 F 仅为**读取** git 状态）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high` — 需编排 6 组验证、正确解读输出、判断是配置问题还是脚本问题，且不能偷懒放宽断言
  - **Skills**: 无需加载额外 skill；若验证 A 需读代码库结构，可加载 `explore-codebase`（user 作用域）

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3（单独执行，作为总验收）
  - **Blocks**: F1, F2, F3, F4
  - **Blocked By**: Task 2, Task 5, Task 6

  **References**:
  - `C:\Users\21499\.config\opencode\scripts\check-model-liveness.ps1` — 验证 B/C 的执行入口
  - `C:\Users\21499\.config\opencode\scripts\watch-bg-task.ps1` — 验证 D 的执行入口
  - `C:\Users\21499\.config\opencode\oh-my-openagent.json` — 验证 A 所依赖的模型配置
  - `.omo/drafts/subagent-timeout-rootcause.md` — 8 存活/6 死亡基线，验证 B/C 的期望值来源
  - 本次会话中 Metis 挂死 1800000ms 的记录 — 验证 D 的超时上限设计依据

  **Acceptance Criteria**:
  - [ ] 验证 A 返回**非空**结果且包含目标文件路径（子代理真正可用）
  - [ ] 验证 B 输出 `ALIVE=8 DEAD=0 TIMEOUT=0`
  - [ ] 验证 C 输出含 `DEAD opencode/deepseek-v4-flash-free`
  - [ ] 验证 D 在 `TimeoutSec` 内收敛，日志同时含心跳与终态事件
  - [ ] 验证 E 在 `~/.config/opencode/` 全量扫描后 0 命中 `sk-[a-f0-9]{20,}`
  - [ ] 验证 F `git status --porcelain` 输出不含业务代码路径
  - [ ] `final-e2e.txt` 存在且含 A~F 六段结果

  **QA Scenarios**:
  ```
  Scenario: 端到端全链路可用（对应用户症状 1 的直接回归）
    Tool: Task tool（真实发起子代理调用）+ Bash
    Preconditions: Wave 2 全部完成，opencode 已重启加载新配置
    Steps:
      1. 发起 task(subagent_type="explore")，prompt: "在当前仓库中查找 backend 目录的结构，列出其中任意 3 个 .py 文件的完整路径"
      2. 断言返回内容长度 > 0
      3. 断言返回内容包含 '.py' 与完整路径形态（含目录分隔符）
      4. 记录本次调用耗时
      5. 执行 check-model-liveness.ps1 -Models "<8个存活模型>" -TimeoutSec 120
      6. 断言输出含 'ALIVE=8 DEAD=0'
    Expected Result: 步骤2/3 通过；步骤5 汇总行显示 8 存活 0 死亡；步骤4 耗时落在 30~180s 区间（远大于修复前的 12s 失败）
    Failure Indicators: 子代理返回空（症状 1 未消除）；返回 "Unexpected server error"；DEAD 计数不为 0
    Evidence: C:\Users\21499\.config\opencode\.evidence\final-e2e.txt 的 A 段与 B 段

  Scenario: 阴性 — 死模型仍被正确识别 + 业务仓库零污染
    Tool: Bash (PowerShell)
    Preconditions: 同上
    Steps:
      1. 执行 check-model-liveness.ps1 -Models "opencode/deepseek-v4-flash-free" -TimeoutSec 60
      2. 断言输出含 'DEAD opencode/deepseek-v4-flash-free'
      3. 在 D:\砺安题库\砺安题库 执行 git status --porcelain
      4. 断言输出中不含 'backend/'、'src/'、'packages/'、'dist/'
      5. 执行 Get-ChildItem "C:\Users\21499\.config\opencode" -Recurse -Include *.json,*.md,*.ps1 | Select-String -Pattern 'sk-[a-f0-9]{20,}'
      6. 断言步骤5 返回 0 行
    Expected Result: 步骤2 通过（脚本能识别死模型）；步骤4 通过（业务代码零改动）；步骤6 零命中（密钥已彻底脱敏）
    Failure Indicators: 死模型被误判为 ALIVE；git status 出现业务代码改动；任一配置/文档/脚本中仍留有明文密钥
    Evidence: C:\Users\21499\.config\opencode\.evidence\final-e2e.txt 的 C/F/E 段
  ```

  **Commit**: NO — 验证任务不产生需提交的配置变更

---

## Final Verification Wave

> 4 个审查 agent 并行执行，全部必须 APPROVE。汇总结果呈现给用户并获得明确确认后，才能判定完成。
>
> **禁止在验证后自动推进。必须等待用户明确批准。**

- [ ] F1. **计划合规审计** — `oracle`
  通读本计划。逐条核对每个 "Must Have"：5 个已实测存活模型是否都被引用、死模型是否零残留、timeoutMs 是否为 300000、密钥是否脱敏。逐条核对每个 "Must NOT Have"：业务仓库零改动（`git status --porcelain`）、无明文密钥、无 `timeoutMs=0`。确认 `.omo/evidence/` 下证据文件真实存在且内容非空。
  输出：`Must Have [N/N] | Must NOT Have [N/N] | 证据文件 [N/N 存在] | VERDICT: APPROVE/REJECT`

- [ ] F2. **配置质量与密钥审查** — `unspecified-high`
  审查 `~/.config/opencode/` 下全部变更文件：JSON 语法有效性（`ConvertFrom-Json` 全量解析）、密钥脱敏彻底性、fallback 链成员全部存活、`provider.opencode` 新增节点字段是否合法（对照官方文档）、`timeout/headerTimeout/chunkTimeout` 取值是否自洽。检查两个 PowerShell 脚本：是否都有超时上限、是否都正确处理进程树、是否存在无限循环风险、是否输出编码正确。
  输出：`JSON [N/N 解析通过] | 密钥 [N处脱敏] | fallback链 [N/N 存活] | 脚本超时保护 [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F3. **真实 QA 复现验证** — `unspecified-high`
  从干净状态独立复现两个原始症状的修复效果：① 真实发起子代理调用，确认非空返回；② 用 `watch-bg-task.ps1` 跑真实后台任务，确认在有界时间内收敛。特别验证边界：模型极慢时是否按预期走 TIMEOUT 路径而非挂死；连续多次调用是否稳定。
  输出：`子代理 [N/N 非空返回] | 后台收敛 [N/N] | 边界(慢模型走TIMEOUT) [PASS/FAIL] | 稳定性(连续3次) [PASS/FAIL] | VERDICT: APPROVE/REJECT`

- [ ] F4. **范围保真检查** — `deep`
  逐任务核对："What to do" 描述的内容是否全部落地、有无超范围的新增（例如是否擅自给无 `fallback_models` 的 agent 补加了字段、是否动了业务仓库、是否改了无关配置）。检查跨任务污染：Task 5 与 Task 6 是否只动了各自目标文件。特别核查 F2 提到的「只有 metis/momus/prometheus 有 fallback_models」这一现状是否被擅自改变。
  输出：`任务 [N/7 合规] | 超范围改动 [CLEAN/N处] | 跨任务污染 [CLEAN/N处] | VERDICT: APPROVE/REJECT`

---

## Commit Strategy

**本计划所有任务均不提交到 git。**

理由：全部变更位于 `C:\Users\21499\.config\opencode\`（用户个人 opencode 配置目录），不属于业务仓库 `D:\砺安题库\砺安题库`。该目录不是 git 仓库，强行提交会引入与业务无关的环境配置。

**业务仓库要求保持零改动**，由 Task 7 验证 F 与 F4 双重把关。

---

## Success Criteria

### Verification Commands
```powershell
# 1. 死模型已从配置中彻底清除
Select-String -Path "$env:USERPROFILE\.config\opencode\oh-my-openagent.json" -Pattern 'deepseek-v4-flash-free'
# 期望: 0 行

# 2. 配置 JSON 合法
Get-Content "$env:USERPROFILE\.config\opencode\opencode.json" -Raw | ConvertFrom-Json
# 期望: 无异常抛出

# 3. 超时阈值已提升
(Get-Content "$env:USERPROFILE\.config\opencode\opencode.json" -Raw | ConvertFrom-Json).experimental.modelFallbackChain.timeoutMs
# 期望: 300000

# 4. 明文密钥已清除
Get-ChildItem "$env:USERPROFILE\.config\opencode" -Recurse -Include *.json,*.md,*.ps1 | Select-String -Pattern 'sk-[a-f0-9]{20,}'
# 期望: 0 行

# 5. 模型存活自检
powershell -File "$env:USERPROFILE\.config\opencode\scripts\check-model-liveness.ps1" -Models "opencode/space-bunny-free","opencode/step-5-preview-free" -TimeoutSec 120
# 期望: ALIVE=2 DEAD=0 TIMEOUT=0

# 6. 后台任务收敛
powershell -File "$env:USERPROFILE\.config\opencode\scripts\watch-bg-task.ps1" -Command "Start-Sleep -Seconds 600" -TimeoutSec 20 -HeartbeatSec 5
# 期望: 退出码 124，耗时 < 60 秒

# 7. 业务仓库零改动
git -C "D:\砺安题库\砺安题库" status --porcelain
# 期望: 输出不含 backend/ src/ packages/ dist/
```

### Final Checklist
- [ ] 19 处死模型引用全部替换，且无一是未实测的新模型
- [ ] 双层 fallback（插件链 + oh-my fallback_models）全部成员实测存活
- [ ] `timeoutMs` = 300000，provider 超时三项已显式配置
- [ ] 配置文件与文档中无任何明文密钥
- [ ] 子代理调用实测返回非空内容（症状 1 消除）
- [ ] 后台任务在有界时间内收敛（症状 2 消除）
- [ ] 自检脚本与看护脚本均已就位并通过各自 QA 场景
- [ ] 业务仓库零改动
- [ ] F1~F4 全部 APPROVE，且用户已明确确认

---

## 交付后使用说明

修复生效需要**重启 opencode 会话**（配置在启动时加载）。

重启后建议按以下顺序自检：
1. 跑一次 `check-model-liveness.ps1` 确认免费模型轮换情况
2. 发起一次子代理调用确认非空返回
3. 若 opencode 官方再次轮换免费模型导致某个模型下线，重跑自检脚本并按存活名单更新 `oh-my-openagent.json`

---

## Out of Scope（明确不做）

- 不修改业务仓库任何文件（backend / src / packages / dist / scripts / tools）
- 不升级 opencode 版本
- 不引入新的第三方插件或依赖
- 不配置付费模型（当前全部基于 opencode 免费层）
- 不重构 oh-my-openagent 插件自身（它是外部包，改动会在升级时丢失）
- 不解决 `Failed to fetch models.dev` 网络问题本身（已确认为环境侧超时，属上游问题；通过自检名单规避而非修复网络）

---