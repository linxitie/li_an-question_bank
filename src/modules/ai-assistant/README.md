# 联考小智（ai-assistant）域卡

> 模块⑦「联考小智」：大模型备考助手（心理调整 / 疑难解答 / 提升建议）。
> 已实现：后端 `/api/llm/*` 五端点 + 前端聊天页 + 会话管理 store；三端入口为题库页「联考小智」按钮。

## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| `.vtj/vue/ai_chat.vue`（聊天页） | `/ai-assistant` | PC/平板/手机 | 已实现 |
| `.vtj/vue/question_bank.vue`（入口按钮） | `/` | PC/平板/手机 | 已实现（跳转聊天页） |

## 2. 后端端点清单

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| POST | `/api/llm/chat` | platform/llm.py | 发消息（多轮上下文，失败回滚悬空消息） |
| GET | `/api/llm/sessions` | platform/llm.py | 我的会话列表 |
| POST | `/api/llm/sessions` | platform/llm.py | 新建会话 |
| GET | `/api/llm/sessions/{id}/messages` | platform/llm.py | 会话历史消息 |
| DELETE | `/api/llm/sessions/{id}` | platform/llm.py | 删除会话（软删） |

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading | boolean | 是否正在加载 | 否 |
| error | string \| null | 最近一次错误信息 | 否 |
| initialized | boolean | 是否完成首次初始化 | 否 |
| ready（派生） | boolean | 已完成初始化且无错误 | 否 |
| sessions | ChatSessionItem[] | 会话列表 | 否 |
| activeSessionId | number \| null | 当前会话 | 否 |
| messages | ChatMessageItem[] | 当前会话消息 | 否 |

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| `ai-assistant:sessions-updated` | 会话列表刷新 | { total } | 已登记 |
| `ai.assistant.ask` | 用户提问（行为上报） | — | 已登记 |

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| （无） | — | — | 未接入 |

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 单元测试 | src/modules/ai-assistant/__tests__/ | 待创建 |
| 外壳冒烟测试 | src/modules/__tests__/shells.spec.ts | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | 题库页「联考小智」→ 聊天页，可多轮对话、建会话、查历史、删会话 | 待验收 |
| 平板 | 布局与路由正常，可对话 | 待验收 |
| 手机 | 布局与路由正常，可对话 | 待验收 |
