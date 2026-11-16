# AI 真功能：实施与验收记录 v1

> 模块 4/7「AI 演示态 → 真功能」的落地归档。实施与静态验收已完成；真实 LLM 调用与前端运行时未验证（见 §6）。

## 1. 元信息

| 项 | 内容 |
|---|---|
| 文档版本 | v1 |
| 日期 | 2026-11-04 |
| 作者 | dsh / AI（多智能体协作） |
| 状态 | ✅ 已实施并静态验收（真实运行时未验证） |
| 父分支 | `feature/ai-assistant`（已快进到 `origin/main` `d3f4049`） |
| 实施分支 | `feature/ai-assistant-ai-real` |
| 模块 | 模块 4/7：AI 演示态 → 真功能 |

## 2. 需求与边界

### 2.1 需求（用户选项 A）

1. **作文批改**：`/study-plan` 页的作文批改从静态示例改为真实 LLM 评分与点评。
2. **模拟面试**：AI 按场景真实出题，并对用户作答给出真实评分与反馈。
3. **AI 学习教练**：建议/金句基于用户**真实今日计划**生成，而非固定文案。

### 2.2 明确不做

- **不新增后端端点**（守 R11：`/api/v1/...` 路径冻结，343 端点基线）。
- **不改 `.vtj/` 页面的 `<template>`**（守 R3：模板由设计器拖拽或用户逐次授权）。
- **不改变会话式聊天语义**：`/api/llm/chat` 原有落库行为默认不变。
- **不删除旧 mock**：任一步失败自动回退演示结果，保证页面不空转。

## 3. 方案与契约

### 3.1 零新增端点（守 R11）

复用既有 `POST /api/llm/chat`。批改 / 出题 / 评分 / 金句都走同一端点，靠 `scene` 字段区分 system prompt 与输出契约。

### 3.2 `persist` 一次性通道（add-only）

| 字段 | 类型 | 默认 | 语义 |
|---|---|---|---|
| `persist` | `bool` | `True` | `True` = 旧行为（落会话、写消息、抽记忆）；`False` = 一次性分支：不落会话、不写消息、不抽记忆 |

- 默认 `True`，对既有调用方零破坏（add-only 契约）。
- `False` 分支在端点内提前返回，不触碰数据库。

### 3.3 三场景 JSON 契约（`SCENE_SYSTEM_PROMPTS`）

| scene | 用途 | 输出要求 |
|---|---|---|
| `essay` | 作文批改 | 严格 JSON：总分、分项分、点评、改进建议 |
| `interview` | 模拟面试出题/评分 | 严格 JSON：题目（出题）或评分+反馈（评分） |
| `coach` | 学习教练建议 | 严格 JSON：基于今日计划的建议金句 |

三场景 system prompt 均强制"只输出 JSON"；前端用 `parseAiJson` 解析，坏 JSON 走 fallback。

### 3.4 前端只改 `<script>`（守 R3）

两个 `.vtj/vue` 页面仅改脚本层：状态（`grading`/`coachQuote`）、方法（真调用 + 解析 + 兜底）、生命周期（`onMounted`）。`<template>` 结构、类名、文案节点零改动，设计器回存安全。

## 4. 改动清单

| 文件 | 改动 |
|---|---|
| `backend/app/services/llm_client.py` | +28 行（L42–69）：`SCENE_SYSTEM_PROMPTS` 新增 essay/interview/coach 三场景，严格 JSON 输出；文件 185 → 213 行 |
| `backend/app/api/v1/platform/llm.py` | +19 行：L31 `Scene` 加 3 场景；L41 新增 `persist: bool = Field(True, ...)`；L94–111 一次性分支（不落会话/不写消息/不抽记忆）；文件 341 → 360 行 |
| `backend/tests/test_ai_features.py` | 新建 54 行：5 个测试（add-only 契约、prompt JSON 关键字、`persist=false` 不碰 DB） |
| `.vtj/vue/study_plan.vue` | script 内 `gradeEssay` 改 async 真批改 + `parseAiJson`/`normalizeEssayResult`/`fallbackEssayResult`；essay 状态加 `grading`；+90 行 |
| `.vtj/vue/ai_chat.vue` | script 内 `coachQuote` 改 ref + `loadCoachSuggestion`（真实今日计划 → coach 场景）、`nextQuestion`/`submitAnswer` 改 async 真出题/真评分（`window.prompt` 收作答，fallback 保留）、`callAiOneShot`/`parseAiJson` helper、`onMounted` 调用；+97 行 |

## 5. 验收证据

| 项 | 命令 | 结果 |
|---|---|---|
| 语法编译 | `python -m py_compile backend/app/api/v1/platform/llm.py backend/app/services/llm_client.py backend/tests/test_ai_features.py` | exit 0 |
| 单测 | `cd backend; python -m pytest tests/test_ai_features.py -q` | **5 passed, 124 warnings in 0.07s** |
| VTJ 版本一致 | `python scripts/vtj_version_sync.py --check` | 设计器页面 70 个一致、0 失败（跳过 10 个非设计器页，含 `study_plan`） |
| 前端契约 L5 | `python backend/scripts/gates/gate_l5_frontend_contract.py` | PASS（5 个必需标识符存在，0 处 RC-2 违规） |
| 红线 L0 | `python backend/scripts/gates/gate_l0_redlines.py` | 全部通过 7/7（含凭据扫描 6230 文件） |

- 124 warnings 为仓库既有 pydantic / SQLAlchemy 弃用告警，非本次引入。
- `persist=false` 分支逻辑由 pytest + monkeypatch 覆盖（断言不触碰 DB）。

## 6. 已知限制与未验证项

1. **教练卡片统计仍是模板硬编码**：12.5h / 78% / 328 题 / 🔥7 天在 `<template>` 内，R3 禁改模板 → 本轮只让「今日建议金句」真实化；统计接真数据需用户在设计器拖拽或逐次授权。
2. **模拟面试面板无作答输入框**（模板限制）→ 用 `window.prompt` 兜底收集作答文字；正式输入框需设计器改造或授权。
3. **真实 LLM 调用未验证**：本 clone 无 `.env`、无数据库、无 `node_modules`，无法发真实请求；`persist=false` 仅以 monkeypatch 证明分支逻辑。
4. **未跑全量回归**：全量 pytest 会挂起（仓库既有问题），未跑 vitest / typecheck（无 `node_modules`）。

## 7. 回滚方式

| 场景 | 操作 |
|---|---|
| 后端回滚 | `git revert <实施提交>`：撤销 3 场景 prompt + `persist` 字段 + 测试；`persist` 默认 `True`，旧调用方无需改动 |
| 前端回滚 | 直接回退两个 `.vtj/vue` 的 script；**不做任何回滚也会自动降级**——真调用失败即走 `fallbackEssayResult` / 旧 mock 文案 |
| 风险面 | 零新增端点、零表结构变更、零模板改动 → 回滚不涉及数据迁移 |

## 8. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1 | 2026-11-04 | 首次归档：模块 4/7 AI 演示态转真功能实施 + 静态验收证据 + 4 条已知限制 |
