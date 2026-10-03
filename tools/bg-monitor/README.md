# 后台任务展示器

实时追踪后台代理 / subagent 运行状态，强制落实 **5 分钟接管规则**。

## 为什么需要它

`CLAUDE.md/Opencode执行命令工作流.md` 要求：后台代理超过 5 分钟无响应须立即接管。
但后台任务本身**不可见**，只能干等或反复轮询 `background_output`，既浪费上下文又容易错过超时窗口。

本工具把「当前主会话派生的所有子代理」列成一张表，用**空闲时长**（而非总时长）
作为卡死判据，一眼看出谁该被接管。

## 快速使用

```bash
# 启动看板（默认 http://127.0.0.1:8799，浏览器打开即可）
python tools/bg-monitor/monitor.py

# 终端打印一次（适合接入 CI 或让 Agent 自查）
python tools/bg-monitor/monitor.py --once

# 查看全部历史子代理（默认折叠 30 分钟以上未活动的）
python tools/bg-monitor/monitor.py --once --all

# 自定义端口 / 活跃窗口
python tools/bg-monitor/monitor.py --port 9000 --window 600
```

## 判定规则

| 空闲时长 | 状态 | 含义与动作 |
|---|---|---|
| < 2 分钟 | 🟢 正常 | 正在产出，继续等待 |
| 2–5 分钟 | 🟡 关注 | 接近阈值，准备接管 |
| ≥ 5 分钟 | 🔴 超时 | **主代理必须立即接管或重启，禁止继续干等** |

> 关键：用 **idle**（距最后一条活动）而非 **elapsed**（总时长）判定。
> 一个任务可以跑很久但一直在产出，只有「空闲超阈值」才真正意味着卡死。

## 工作原理

- 数据源：`%USERPROFILE%\.local\share\opencode\opencode.db`
- 以 SQLite **只读模式**（`mode=ro`）打开，绝不写入，避免与运行中的 OpenCode 抢锁
- `session.parent_id == 主会话 id` 精确识别当前派生的子代理
- 仅展示 `ACTIVE_WINDOW`（默认 1800s）内有活动的会话，其余折叠为「历史」
- 仅监听 `127.0.0.1`，不对外暴露

## 集成到工作流

本工具使「5 分钟规则」可被**自动检查**，建议在每轮派发后台任务后：

```bash
python tools/bg-monitor/monitor.py --once
```

若输出出现 `[stall]`，立即用 `task(task_id=<session_id>)` 复用该会话追问，
或直接以主代理身份接管，避免超时浪费。

## 注意

- 本工具是**开发辅助**，不参与产品构建，不影响 `vite build` 与后端服务
- 数据库体积可能达数 GB，本工具只做 `SELECT` 且带 `LIMIT`，不会全表扫描
- 若 OpenCode 正在写入，`mode=ro` 仍可能读到稍旧快照，属正常，不影响判活