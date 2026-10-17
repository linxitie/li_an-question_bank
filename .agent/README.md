# AI 工具目录索引

本目录聚合项目自有工具。归位原则：**零引用或仅文档引用者可移动，
活动工具链保持原位**——移动活动目录会立即破坏正在运行的会话。

## 已归位

| 路径 | 说明 |
|---|---|
| `.agent/tools/bg-monitor/` | 后台监控（原 `tools/bg-monitor/`） |
| `.agent/tools/sfc-check/` | SFC 校验（原 `tools/sfc-check/`） |

## 保持原位的活动工具链（实测依据）

| 目录 | 不可移动的原因（实测） |
|---|---|
| `vtj-mcp-server/` | 本会话的 VTJ MCP 工具由该目录的 node 进程**实时提供**（实测 PID 21112 占用）；`git mv` 直接 `Permission denied`。`package.json:32-34` 的 `mcp:setup/start/test` 三个脚本硬引用其路径 |
| `.agents/skills/` | 本仓库 24 个 skill 的加载入口（`ask-matt`、`diagnose`、`vtj-frontend` 等） |
| `.omo/` | OH-MY-OPENCODE 运行时会话数据；`run-continuation/` 在 `.gitignore` 内 |
| `.opencode/` | OpenCode 插件与 skills 运行时 |
| `.claude/` | Claude Code 运行时（`.gitignore` 内） |

## 迁移原则（供后续整理参考）

1. 移动前先实测引用面：`git grep` 全仓搜目录名，确认无硬引用
2. 活动进程占用目录禁止移动（Windows 下 `Permission denied` 即此信号）
3. 移动后必须做功能验证（如 bg-monitor 的 import 测试）
