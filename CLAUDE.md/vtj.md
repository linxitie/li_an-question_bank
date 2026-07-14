# 砺安题库 — VTJ 前端开发规范与架构文档

> 基于 [VTJ.PRO 官方文档](https://www.vtj.pro/guide/) 与项目实际代码整理，适用于 Claude Code 在本项目中的开发工作。

---

## 第一章：VTJ 概述

### 1.1 VTJ.PRO 是什么

VTJ.PRO 是给专业开发者的 **AI 低代码引擎**，核心理念是 **"设计即代码，代码即设计"**。

- 生成的是**标准 Vue 3 + TypeScript 项目**，无私有运行时、无平台专属标记
- 提供**双向代码转换**：拖拽 → Vue SFC 出码，已有 Vue 项目 → 反向解析为 DSL 回到设计器
- 支持 AI 辅助：自然语言生成页面、设计稿转组件、报错自动修复

### 1.2 核心原则

| 原则 | 说明 |
|------|------|
| 绝不锁代码 | 生成标准 Vue 3 项目，随时可脱离 VTJ 继续维护 |
| 双向代码转换 | 设计器 ↔ DSL JSON ↔ Vue SFC，真正的编译闭环 |
| AI 是副驾驶 | AI 用于少写重复代码，不是多学一个新系统 |
| 工程化第一优先级 | Vue 3 / Vite / TypeScript / Pinia / ESLint / Docker 部署 |

### 1.3 本项目架构概览

```
用户浏览器
  │
  ├── Vue 3 SPA (Vite + TypeScript)
  │   ├── VTJ 生成页面 (.vtj/vue/*.vue)     ← 低代码设计器产出
  │   ├── 手写页面 (src/views/*.vue)         ← 自定义页面
  │   ├── VTJ Provider (@vtj/web)           ← 运行时引擎
  │   ├── Vue Router + Pinia                 ← 路由与状态
  │   └── window.__VTJ_AUTH__               ← 共享认证模块
  │
  ├── Vite Proxy (proxy.config.ts)
  │
  └── Python 后端 (FastAPI, port 8000)
      ├── REST API (/api/auth/, /api/questions/, ...)
      ├── WebSocket (/ws)
      ├── gRPC Service
      └── SQLite / MySQL
```

---

## 第二章：前端 JSON DSL 体系（核心）

### 2.1 什么是 DSL

DSL（Domain Specific Language）是 VTJ 的**中间表示层**，用 JSON 完整描述一个 Vue 组件的所有信息。它是 VTJ "设计即代码"能力的技术基础——设计器的拖拽操作最终都落为 DSL JSON，而 DSL JSON 又可以被编译为标准 Vue SFC 或被运行时直接渲染。

### 2.2 DSL 双向转换闭环

VTJ 的 DSL 支持三个方向的转换，形成完整闭环：

```
                    ┌─── generator() ───→  Vue SFC 文件 (.vue)
                    │    (@vtj/coder)       ↓
                  DSL JSON              Vite 编译 → 浏览器
                    │    (@vtj/parser)      ↑
                    └─── parseVue() ────  Vue SFC 源码
                    
                    ┌─── createRenderer() ───→  Vue 组件实例 (运行时)
                    │    (@vtj/renderer)
                  DSL JSON
```

| 方向 | 函数/模块 | 来源 | 说明 |
|------|----------|------|------|
| **出码** | `generator(dsl, componentMap, deps, platform)` | `@vtj/coder` | DSL JSON → Vue SFC 源码字符串 |
| **逆向** | `parseVue({id, name, source, project})` | `@vtj/parser` | Vue SFC 源码 → DSL JSON（7 阶段解析） |
| **运行时** | `createRenderer({Vue, dsl, components, apis})` | `@vtj/renderer` | DSL JSON → 可渲染 Vue 组件实例 |

**parseVue 7 阶段解析流程：**

1. **parseSFC** — 使用 `@vue/compiler-sfc` 拆分 `<template>` / `<script>` / `<style>`
2. **parseStyle** — 合并样式块，提取 CSS 规则
3. **parseScripts** — 提取 state/watch/lifeCycles/computed/methods/props/emits/inject/dataSources
4. **parseTemplate** — 模板 → AST → 节点树（nodes）、插槽（slots）、上下文引用
5. **DSL 构建** — 整合为 BlockSchema 对象
6. **patchCode** — 代码格式化、平台特定替换、成员访问修正
7. **BlockModel.toDsl()** — 最终 DSL 输出

### 2.3 BlockSchema 完整结构

每个 VTJ 组件（页面或区块）在 DSL 层面都是一个 `BlockSchema` 对象：

```json
{
  "id": "mjvdqdu1",              // 组件唯一标识
  "name": "QuestionBank",        // 组件名称
  "__VTJ_BLOCK__": true,         // VTJ 区块标记
  "__VERSION__": "1778918346107",// 版本时间戳
  
  "state": { /* 响应式数据 */ },
  "methods": { /* 方法定义 */ },
  "computed": { /* 计算属性 */ },
  "props": [ /* 组件属性声明 */ ],
  "emits": [ /* 自定义事件声明 */ ],
  "inject": [ /* 依赖注入声明 */ ],
  "watch": [ /* 侦听器 */ ],
  "lifeCycles": { /* 生命周期钩子 */ },
  "dataSources": { /* 数据源定义 */ },
  
  "nodes": [ /* 模板节点树（递归结构） */ ],
  "css": "...",                  // 样式字符串
  "slots": [ /* 插槽定义 */ ],
  "expose": [ /* expose 声明 */ ],
  "locked": false                // 设计器锁定标记
}
```

### 2.4 DSL 节点（Node）字段详解

`nodes[]` 是递归的树结构，每个节点描述模板中一个元素：

```json
{
  "id": "26qsjvefdo5",                  // 节点唯一标识
  "name": "button",                     // HTML 标签名 或 组件名
  "from": "",                           // 组件来源（见下表）
  "props": { /* 属性绑定 */ },
  "events": { /* 事件绑定 */ },
  "children": "...",                    // 子内容（字符串/表达式/节点数组）
  "directives": [ /* 指令数组 */ ],
  "locked": false,                      // 设计器中是否锁定
  "invisible": false                    // 设计器中是否隐藏
}
```

**`from` 字段取值：**

| 值 | 含义 | 示例 |
|----|------|------|
| `""` | 原生 HTML 元素 | `div`, `span`, `button`, `main`, `section` |
| `"element-plus"` | Element Plus 组件库 | `ElButton`, `ElInput`, `ElMessage` |
| `"@vtj/ui"` | VTJ 内置 UI 组件 | `XIcon` |
| `{ id: "ijvdn7sw", type: "Schema" }` | 引用另一个 Block | `NavBar`（引用 NavBar 区块的 Schema） |

**`props` 动态绑定示例（JSExpression）：**

```json
{
  "class": {
    "type": "JSExpression",
    "value": "[\n  'action-btn',\n  { active: this.state.activeTopAction === this.context.item.key }\n]"
  }
}
```

**`events` 绑定示例：**

```json
{
  "click": {
    "name": "click",
    "handler": {
      "type": "JSExpression",
      "value": "this.handleTopAction(this.context.item.key)"
    },
    "modifiers": {}
  }
}
```

**`children` 的三种形式：**

```json
// 1. 静态文本
"children": "按钮文字"

// 2. JS 表达式（动态内容）
"children": {
  "type": "JSExpression",
  "value": "this.context.item.name"
}

// 3. 子节点数组
"children": [
  { "id": "...", "name": "span", ... },
  { "id": "...", "name": "XIcon", "from": "@vtj/ui", ... }
]
```

**`directives` 指令数组：**

```json
// v-for 指令
{
  "id": "26sjjvefe1h",
  "name": "vFor",
  "value": { "type": "JSExpression", "value": "this.topActions.value" },
  "iterator": { "item": "item", "index": "index" }
}

// v-if 指令
{
  "id": "26sijvefe1h",
  "name": "vIf",
  "value": { "type": "JSExpression", "value": "this.context.item.tag" }
}
```

### 2.5 JSExpression 与 JSFunction

DSL 中有两种动态代码表示：

| 类型 | 用途 | 结构 | 示例 |
|------|------|------|------|
| `JSExpression` | 表达式值 | `{ type: "JSExpression", value: "..." }` | `"this.state.count + 1"` |
| `JSFunction` | 函数体 | `{ type: "JSFunction", value: "..." }` | `"() => { this.state.count++ }"` |

### 2.6 数据源（dataSources）

DSL 支持两种数据源类型：

```json
{
  "userData": {
    "type": "api",           // "api" 或 "mock"
    "ref": "getUserInfo",    // API 引用名
    "transform": {           // 数据转换函数
      "type": "JSFunction",
      "value": "function(data) { return data.user }"
    }
  }
}
```

### 2.7 实际项目 DSL 示例分析

#### 示例一：QuestionBank（题库页）— `.vtj/files/mjvdqdu1.json`

**state 定义：**
```json
{
  "practiceLog": { "type": "JSExpression", "value": "({ today: 38, week: 256, total: 1289 })" },
  "searchQuery": { "type": "JSExpression", "value": "''" },
  "activeCategory": { "type": "JSExpression", "value": "'xc'" },
  "activeTopAction": { "type": "JSExpression", "value": "'quick'" }
}
```

**computed 示例（topActions 数据列表）：**
```javascript
() => {
  return [
    { key: 'quick', name: '快速练习', icon: '⚡', tag: 'NEW' },
    { key: 'history', name: '历年试卷', icon: '📋' },
    { key: 'smart', name: '智能组卷', icon: '🤖' },
    { key: 'ai', name: '联考小智', icon: '🧠', tag: 'AI' }
  ];
}
```

**节点树结构（简化示意）：**
```
div.question-bank
├── NavBar (from: { id: "ijvdn7sw", type: "Schema" })  ← 引用其他 Block
└── main.qb-main
    ├── section.qb-top
    │   ├── div.qb-actions
    │   │   └── div.action-scroll
    │   │       └── button.action-btn (vFor="this.topActions.value")
    │   │           ├── span.action-icon (children: JSExpression)
    │   │           ├── span.action-name (children: JSExpression)
    │   │           └── span.action-tag (vIf="this.context.item.tag")
    │   └── div.qb-sub-actions
    │       └── button.sub-btn (@click="this.handleSubAction('mini')")
    │           ├── XIcon (from: "@vtj/ui", icon: this.$libs.VtjIcons.Timer)
    │           └── span ("小模考")
    └── section.qb-body ...
```

#### 示例二：Login（登录页）— `.vtj/files/login.json`

**state 定义（嵌套表单对象）：**
```json
{
  "activeTab": "login",
  "loginMode": "password",
  "message": "",
  "msgType": "error",
  "loading": false,
  "loginForm": { "username": "", "password": "", "showPassword": false },
  "smsLoginForm": { "username": "", "phone": "", "code": "", "countdown": 0 },
  "registerForm": { "username": "", "password": "", "phone": "", "code": "", "role": "student", "showPassword": false, "countdown": 0 }
}
```

**methods 声明（含异步方法）：**
```json
{
  "switchTab": { "type": "method", "params": ["tab"] },
  "handleLogin": { "type": "asyncMethod" },
  "handleRegister": { "type": "asyncMethod" },
  "sendSmsCode": { "type": "method", "params": ["formType"] }
}
```

**lifeCycles：**
```json
{
  "mounted": { "type": "method" }
}
```

---

## 第三章：VTJ 前端编写规则

### 3.1 职责分离原则

| 角色 | 职责 | 操作范围 |
|------|------|----------|
| **VTJ 设计器** | 页面布局、组件拖拽、样式调整 | 维护 `<template>` 结构和 DSL 节点树 |
| **Claude Code** | 业务逻辑、API 对接、数据交互 | 维护 `<script>` 部分（方法、状态、API 调用） |

**关键规则：**
- Claude Code **不应修改** `<template>` 中的复杂结构——应提示用户回到 VTJ 设计器调整
- Claude Code **不应修改** `.vtj/` 目录下的 JSON 文件（那是设计器的领域）
- 新增按钮/表单等 UI 元素 → 通过设计器拖拽，Claude 只处理事件回调函数

### 3.2 VTJ 生成代码的特征

本项目 VTJ 生成的 `.vue` 文件使用 **Vue 3 Options API**（`defineComponent`），遵循以下模式：

```vue
<template>
  <!-- VTJ 生成的模板，含 :class、v-for、v-if、@click 等指令 -->
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive } from 'vue';
import { XIcon } from '@vtj/ui';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'ComponentName',
  components: { XIcon },
  setup(props) {
    const provider = useProvider({ id: 'componentId', version: 'timestamp' });
    const state = reactive({ /* 局部状态 */ });
    return { state, props, provider };
  },
  data() { return { /* 额外数据 */ }; },
  methods: {
    async handleAction() {
      // 使用 provider 或 fetch 调用 API
    }
  },
  mounted() { /* 初始化逻辑 */ }
});
</script>

<style lang="css" scoped>
/* 组件样式 */
</style>
```

**关键约定：**
- 使用 `useProvider({ id, version })` 获取 VTJ 运行时上下文
- 使用 `@vtj/ui` 的 `XIcon` 组件渲染图标
- 使用 `@vtj/icons`（通过 `this.$libs.VtjIcons.*`）获取图标定义
- 认证通过 `window.__VTJ_AUTH__` 全局模块
- 消息提示使用 ElementPlus `ElMessage`

### 3.3 项目目录结构约定

```
项目根目录/
├── .vtj/                          # VTJ 设计器元数据（由设计器维护）
│   ├── router.js                  # VTJ 自动生成的路由（本项目仅含 smartRecommend）
│   ├── files/                     # 每个页面/区块的 DSL JSON
│   │   ├── mjvdqdu1.json          #   QuestionBank 题库页 DSL
│   │   ├── login.json             #   Login 登录页 DSL
│   │   └── ...                    #   其他页面 DSL
│   ├── vue/                       # VTJ 出码生成的 Vue SFC 文件
│   │   ├── mjvdqdu1.vue           #   QuestionBank 题库页
│   │   ├── login.vue              #   Login 登录页
│   │   ├── smartRecommend.vue     #   智能推荐
│   │   └── ...
│   ├── materials/                 # 物料目录（组件库描述）
│   │   └── linxitie.policy-exam-bank.json
│   └── projects/                  # 项目配置
│       └── linxitie.policy-exam-bank.json
├── src/                           # 手写源码
│   ├── main.ts                    # 应用入口（Provider 初始化）
│   ├── App.vue                    # 根组件（Suspense 包装）
│   ├── auth.ts                    # 共享认证模块（window.__VTJ_AUTH__）
│   ├── router/index.ts            # 路由配置（混合 VTJ + 手写页面）
│   ├── views/                     # 手写页面
│   │   ├── exercise.vue
│   │   ├── solution.vue
│   │   └── ...
│   ├── components/                # 手写组件
│   └── style/                     # 全局样式
├── backend/                       # Python FastAPI 后端
├── vite.config.ts                 # Vite 配置（VTJ 插件）
├── proxy.config.ts                # API 代理配置
├── tsconfig.json                  # TypeScript 配置（排除 .vtj）
└── package.json                   # NPM 配置（含 VTJ 项目 ID）
```

### 3.4 组件结构模式

**模式一：VTJ 生成页面（Options API）**

VTJ 生成的 `.vue` 文件使用 `defineComponent` + `setup()` 返回 `useProvider` 上下文。Claude Code 主要在其 `methods` 和 `mounted` 中补充业务逻辑。

**模式二：手写页面（Composition API `<script setup>`）**

`src/views/` 下的手写页面可自由使用 `<script setup lang="ts">` 语法。

### 3.5 样式编写规则

- 使用 `<style scoped>` 确保样式隔离
- 支持 Less / Sass / Scss 预处理器
- VTJ 生成页面中，CSS 同时存在于 DSL JSON 的 `css` 字段和 `.vue` 文件的 `<style>` 块
- 本项目使用纯 CSS，设计令牌（颜色、圆角、阴影）在 CSS 中直接硬编码

### 3.6 开发工作流

```
用户需求
  │
  ├── 涉及 UI 结构变更？
  │   └── YES → 用户在 VTJ 设计器（http://localhost:5173/__vtj__/）拖拽修改
  │             → 设计器保存 → 更新 .vtj/files/*.json
  │             → 出码 → 更新 .vtj/vue/*.vue
  │             → Claude 在 <script> 中补充业务逻辑
  │
  └── 仅涉及逻辑/API？
      └── YES → Claude 直接修改 .vue 文件的 <script> 部分
```

---

## 第四章：前后端通信原理

### 4.1 @vtj/utils request 工具

VTJ 提供基于 Axios 封装的 HTTP 客户端 `request`，位于 `@vtj/utils`。

**功能特性：**
- 🚀 基于 Promise 的 API
- 🔁 请求/响应拦截器
- 🚫 请求取消功能
- ⏳ 加载状态管理（showLoading/hideLoading）
- 📊 响应验证（validSuccess/validate）
- 🛠️ 可定制错误处理（showError/failMessage）
- 🔄 特定情况自动重试
- 📦 支持 form/json/data 三种数据格式

### 4.2 基本用法

```typescript
import { request } from '@vtj/utils';

// GET 请求
const response = await request({ url: '/api/data' });

// POST 请求
const response = await request({
  method: 'post',
  url: '/api/items',
  data: itemData
});

// Path 参数
const response = await request({
  url: '/api/user/:id',
  params: { id: '123' }
});

// POST + Query params
const response = await request({
  url: '/api/user/:id',
  method: 'post',
  data: itemData,
  params: { id: '123' },
  query: { name: '名称' }
});

// JSON 格式提交
request({
  type: 'post',
  url: '/api/json',
  settings: { type: 'json' },
  data: jsonData
});

// 文件上传
request({
  type: 'post',
  url: '/api/file',
  settings: { type: 'data' },
  data: { file: File }
});
```

### 4.3 请求设置（settings）

| 选项 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `type` | `'form' \| 'json' \| 'data'` | `'form'` | 请求负载格式 |
| `injectHeaders` | `boolean` | `false` | 注入自定义请求头 |
| `loading` | `boolean` | `false` | 启用加载状态 |
| `failMessage` | `boolean` | `true` | 显示错误消息 |
| `originResponse` | `boolean` | `false` | 返回原始 Axios 响应 |
| `validSuccess` | `boolean` | `true` | 验证响应是否成功 |
| `validate` | `(res) => boolean` | — | 自定义校验方法 |
| `showError` | `(msg, e) => void` | — | 自定义失败提示 |
| `showLoading` | `() => void` | — | 显示 loading 回调 |
| `hideLoading` | `() => void` | — | 隐藏 loading 回调 |

### 4.4 创建类型化 API（createApi / createApis）

```typescript
import { createApi, createApis } from '@vtj/utils';

// 单个 API
const getUser = createApi<{ id: string }, User>('/user/:id');
const user = await getUser({ profile: 'profile' }, { params: { id: '123' } });

// 批量 API
const api = createApis({
  getPosts: '/posts',
  createPost: { method: 'post', url: '/posts' },
  updatePost: { method: 'patch', url: '/posts/:id' }
});
await api.getPosts();
await api.createPost({ title: '新文章' });
```

### 4.5 useApi（Vue 组合式 API）

```vue
<script setup>
import { useApi } from '@vtj/utils';
import { getUser } from './api';

const { data, error, loading } = useApi(
  getUser({ id: '123' }),
  (res) => res.data       // 可选的数据提取函数
);
</script>

<template>
  <div v-if="loading">加载中...</div>
  <div v-else-if="error">错误: {{ error.message }}</div>
  <div v-else>{{ data }}</div>
</template>
```

### 4.6 全局配置（request.setConfig）

```typescript
import { request } from '@vtj/utils';
import { ElNotification, ElLoading } from 'element-plus';

let _loading: any = null;

request.setConfig({
  settings: {
    type: 'form',
    validSuccess: true,
    originResponse: false,
    loading: true,
    validate: (res: any) => {
      return res.data?.code === 0 || !!res.data?.success;
    },
    failMessage: true,
    showError: (msg: string) => {
      ElNotification({ title: '错误', message: msg || '未知错误', type: 'error' });
    },
    showLoading: () => {
      _loading = ElLoading.service({
        lock: true,
        text: 'Loading',
        background: 'rgba(0, 0, 0, 0.7)'
      });
    },
    hideLoading: () => {
      _loading?.close();
      _loading = null;
    }
  }
});
```

### 4.7 请求拦截器

```typescript
// 添加请求拦截器
const removeInterceptor = request.useRequest((config) => {
  config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// 移除拦截器
removeInterceptor();
```

### 4.8 请求取消

```typescript
// 取消特定请求
request.cancel('request-id', '用户取消操作');

// 取消所有待处理请求
request.cancel();
```

### 4.9 Provider 与 API 的关系

Provider 自动管理 API 生命周期：

- **`createSchemaApis()`** — 根据项目配置中的 API 定义自动创建请求方法
- **`createMock()`** — 为 API 创建 Mock 函数
- **`adapter`** — 统一请求适配器，负责实际的 HTTP 通信

在 VTJ 生成的组件中，可通过 `useProvider()` 获取 `provider.apis` 直接调用：

```typescript
const provider = useProvider();
provider.apis.getUserInfo().then(data => console.log(data));
```

### 4.10 本项目实践

本项目未使用 `@vtj/utils` 的 request 工具，而是采用**原生 `fetch()` + 共享认证模块**的模式：

**认证模块（`src/auth.ts`）：**
```typescript
// window.__VTJ_AUTH__ 提供：
// - login(username, password) / logout()
// - isLoggedIn() / ensureAuth()
// - getAuthHeaders() / getJsonHeaders()
// - getUsername() / refreshToken()
```

**API 调用模式（VTJ 生成的 .vue 组件中）：**
```typescript
async handleLogin() {
  const headers = window.__VTJ_AUTH__.getJsonHeaders();
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers,
    body: JSON.stringify(this.state.loginForm)
  });
  const data = await response.json();
  if (data.code === 0) {
    window.__VTJ_AUTH__.login(data.data.token);
    ElMessage.success('登录成功');
  }
}
```

**Vite 代理配置（`proxy.config.ts`）：**
- 开发环境下 `/api` 请求代理到 `http://localhost:8000`
- 解决跨域问题

---

## 第五章：VTJ 前端加载链路

### 5.1 整体加载时序

VTJ 应用从启动到页面渲染经过以下阶段：

```
Vite 启动
  │
  ├── 阶段一：Vite 插件初始化
  │   createDevTools() → 注入 VTJ 编译器、热重载、设计器路由
  │
  ├── 阶段二：main.ts 执行
  │   createApp → createAdapter → LocalService → createProvider → onReady
  │
  ├── 阶段三：Provider 加载链
  │   project.json 加载 → 依赖动态 import → 物料资源 → 路由初始化
  │
  ├── 阶段四：异步边界
  │   Suspense 包裹 <router-view> → 等待异步组件解析
  │
  ├── 阶段五：DSL 渲染（两条路径）
  │   路径A（出码路径）：DSL JSON → generator() → .vue 文件 → Vite 编译 → 浏览器
  │   路径B（运行时路径）：DSL JSON → createRenderer() → Vue 组件实例 → 浏览器
  │
  └── 阶段六：路由导航
       用户访问 URL → Vue Router 匹配 → 异步加载页面组件 → 渲染
```

### 5.2 路径A：设计时出码路径

这是本项目主要使用的路径——VTJ 设计器保存后，DSL 被编译为 `.vue` 文件：

```
用户在 VTJ 设计器中拖拽
  │
  ▼
.vtj/files/*.json (DSL 更新)
  │
  ▼
generator(dsl, componentMap, dependencies, 'web')
  │ @vtj/coder
  ▼
.vtj/vue/*.vue (标准 Vue SFC)
  │
  ▼
Vite 开发服务器编译 (createDevTools 插件处理 $vtj/ 别名)
  │
  ▼
浏览器加载渲染
```

**generator 参数：**
```typescript
generator(
  dsl: BlockSchema,                          // 页面 DSL
  componentMap: Map<string, MaterialDescription>, // 组件物料映射
  dependencies: Dependencie[] = [],           // 第三方依赖
  platform: PlatformType = 'web',            // 目标平台
  formatterDisabled?: boolean                // 禁用 Prettier 格式化
): Promise<string> // 返回 Vue SFC 源码字符串
```

### 5.3 路径B：运行时渲染路径

部分场景下（如动态加载远程组件），DSL 在运行时被直接渲染：

```
DSL JSON (从 Service 加载)
  │
  ▼
provider.createDslRenderer(dsl, { mode, components })
  │
  ▼
createRenderer({ Vue, dsl, components, apis, loader })
  │ @vtj/renderer
  ▼
Vue defineComponent → 挂载渲染
```

### 5.4 阶段一：Vite 开发服务器启动

`vite.config.ts` 中的 `createDevTools()` 插件提供：
- 实时设计器预览（`http://localhost:5173/__vtj__/`）
- `$vtj/` 路径别名解析（映射到 `.vtj/` 目录）
- 低代码组件编译（将 DSL 编译为 Vue SFC）
- 热重载支持

```typescript
// vite.config.ts
import { createViteConfig } from '@vtj/cli';
import { createDevTools } from '@vtj/pro/vite';
import proxy from './proxy.config';

export default createViteConfig({
  proxy,
  plugins: [createDevTools({})]
});
```

**进阶配置：**
```typescript
// 二级目录部署 → 同步 staticBase
createDevTools({ staticBase: '/sub/' })

// 生产环境务必移除 createDevTools 插件
```

### 5.5 阶段二：main.ts 初始化

```typescript
// src/main.ts (当前项目代码)
import { createProvider, LocalService, createModules, NodeEnv,
         autoUpdate, ContextMode, notify, loading, createAdapter,
         createServiceRequest, IconsPlugin, Startup } from '@vtj/web';

const app = createApp(App);

// 1. 创建适配器（桥接 VTJ 与宿主应用）
const adapter = createAdapter({ loading, notify, Startup, useTitle });

// 2. 实例化服务（开发环境：LocalService）
const service = new LocalService(createServiceRequest(notify));

// 3. 创建 Provider
const { provider, onReady } = createProvider({
  nodeEnv: process.env.NODE_ENV as NodeEnv,
  mode: ContextMode.Raw,           // Raw = 源码模式（直接使用 .vue 文件）
  modules: createModules(),
  adapter,
  service,
  router,
  dependencies: {                  // 依赖声明
    Vue: () => import('vue'),
    VueRouter: () => import('vue-router'),
    Pinia: () => import('pinia'),
    VueI18n: () => import('vue-i18n')
  },
  project: { id: vtj?.id || name },
  enableStaticRoute: true
});

// 4. 等待 Provider 就绪后挂载
onReady(async () => {
  app.use(router);
  app.use(provider);           // Provider 作为 Vue 插件安装
  app.use(IconsPlugin);
  app.mount('#app');
});

// 5. 生产环境自动更新
if (process.env.NODE_ENV === 'production') {
  autoUpdate();
}
```

**初始化关键点：**

| 步骤 | 组件 | 说明 |
|------|------|------|
| 1 | `createAdapter` | 桥接 VTJ 通知/加载/启动/标题等接口到宿主应用 |
| 2 | `LocalService` | 开发环境从本地 `.vtj/` 目录读取 DSL；生产环境需换 `RemoteService` |
| 3 | `createProvider` | 核心：注入依赖、服务、路由，返回 `provider` 和 `onReady` |
| 4 | `onReady` | 确保所有异步依赖就绪后才挂载 Vue 应用 |
| 5 | `ContextMode.Raw` | 本项目使用源码模式——直接加载已出码的 Vue SFC |

**ContextMode 三种模式：**

| 模式 | 说明 |
|------|------|
| `ContextMode.Design` | 设计模式（在 VTJ 设计器中使用） |
| `ContextMode.Raw` | 源码模式（本项目使用——直接加载 .vue 文件） |
| `ContextMode.Preview` | 预览模式 |

### 5.6 阶段三：Provider.load() 加载链

当 Provider 初始化时，内部执行以下加载序列：

```
Provider.load(project)
  │
  ├── 1. 加载项目配置 (ProjectSchema)
  │     从 Service 读取 projects/*.json
  │     解析页面列表、区块列表、依赖、API 定义
  │
  ├── 2. 动态加载依赖 (dependencies)
  │     逐个 import() Vue/VueRouter/Pinia/VueI18n
  │     注册为 $libs 全局变量
  │
  ├── 3. 加载物料资源 (materials)
  │     从 /node_modules/@vtj/materials/dist/ 加载物料
  │     materialPath 确保正确加载（History 模式需特殊配置）
  │
  ├── 4. 初始化路由 (initRouter)
  │     解析项目页面列表 → 动态添加路由
  │     enableStaticRoute: true → 合并静态路由
  │     .vtj/router.js 中的路由也在此阶段注册
  │
  ├── 5. 安装 Vue 插件
  │     自动安装 ElementPlus、Pinia、VueI18n 等
  │     设置全局错误处理器（设计模式下）
  │
  └── 6. 创建 API（createSchemaApis）
        根据项目配置中的 API 定义创建请求方法
        挂载到 provider.apis
```

### 5.7 阶段四：Suspense 异步边界

VTJ 组件是异步加载的，因此 `App.vue` 必须用 `<Suspense>` 包裹：

```vue
<template>
  <Suspense>
    <router-view></router-view>
  </Suspense>
</template>

<script lang="ts" setup>
import { Suspense } from 'vue';
</script>
```

**Suspense 的作用：**
- 处理异步组件的加载状态
- 捕获异步加载中的错误
- 管理异步组件生命周期

### 5.8 阶段五：createRenderer 七步内部流程

当 VTJ 在运行时渲染 DSL（路径B），`createRenderer` 执行以下七步：

```
createRenderer({ Vue, dsl, components, apis })
  │
  ├── Step 1: 初始化上下文 (Context)
  │   new Context({ mode, dsl, attrs: { $components, $libs, $apis } })
  │
  ├── Step 2: 创建 Vue 组件
  │   Vue.defineComponent → 定义 props、setup、render 选项
  │
  ├── Step 3: 响应式系统集成
  │   context.state = createState(Vue, dsl.state, context)     → reactive()
  │   createComputed(Vue, dsl.computed, context)                → computed()
  │   createMethods(dsl.methods, context)
  │
  ├── Step 4: 依赖注入处理
  │   createInject(Vue, dsl.inject, context)                    → inject()
  │
  ├── Step 5: 数据源初始化
  │   createDataSources(dsl.dataSources, context)
  │   支持 mock 和 api 两种类型，自动数据转换
  │
  ├── Step 6: 生命周期管理
  │   createLifeCycles(dsl.lifeCycles, context)
  │   设置侦听器：Vue.watch(source, handler, { deep, immediate })
  │
  └── Step 7: 渲染逻辑
      render() {
        const nodes = dsl.nodes || [];
        if (nodes.length === 1) return nodeRender(nodes[0], context, Vue, loader, nodes);
        return nodes.map(child => nodeRender(child, context, Vue, loader, nodes));
      }
```

**关键辅助函数：**

| 函数 | 作用 |
|------|------|
| `createProps(dsl.props, context)` | 解析 props 定义（字符串/对象形式），自动解析 JS 表达式默认值 |
| `createState(Vue, dsl.state, context)` | 使用 `Vue.reactive` 创建响应式对象 |
| `createComputed(Vue, dsl.computed, context)` | 使用 `Vue.computed` 包装计算逻辑 |
| `createDataSources(dsl.dataSources, context)` | 初始化数据源（mock/api），自动数据转换 |
| `setWatches()` | `Vue.watch(source, handler, { deep, immediate })` |

### 5.9 阶段六：路由导航与页面切换

本项目路由配置（`src/router/index.ts`）混合 VTJ 页面和手写页面：

```typescript
const routes = [
  { path: '/',          component: () => import('$vtj/vue/mjvdqdu1.vue') },      // VTJ 页面
  { path: '/home',      component: () => import('$vtj/vue/jjvdntly.vue') },      // VTJ 页面
  { path: '/answer',    component: () => import('$vtj/vue/ujvdv5fe.vue') },      // VTJ 页面
  { path: '/login',     component: () => import('$vtj/vue/login.vue') },         // VTJ 页面
  { path: '/exercise',  component: () => import('@/views/exercise.vue') },       // 手写页面
  { path: '/solution',  component: () => import('@/views/solution.vue') },       // 手写页面
  { path: '/unauthorized', component: () => import('@/views/unauthorized.vue') },
  { path: '/:pathMatch(.*)*', component: () => import('@/views/not-found.vue') } // 404
];
```

- `$vtj/` 是 VTJ Vite 插件注入的别名，指向 `.vtj/` 目录
- 使用 `createWebHashHistory`（Hash 模式）
- `.vtj/router.js` 中的路由也会被 Provider 自动注册

### 5.10 生产环境 vs 开发环境差异

| 方面 | 开发环境 | 生产环境 |
|------|----------|----------|
| Service | `LocalService`（从本地 `.vtj/` 读取） | 需实现 `RemoteService` 接口 |
| Vite 插件 | `createDevTools()` 启用 | **必须移除** `createDevTools()` |
| 物料 | 本地 `node_modules` | 部署到 CDN |
| 更新 | 热重载 | `autoUpdate()` 自动检测新版本 |
| 设计器 | `http://localhost:5173/__vtj__/` | 不可访问 |
| 错误处理 | 设计模式全局错误处理器 | 标准 Vue 错误处理 |

---

## 第六章：项目集成参考

### 6.1 依赖包说明

| 包名 | 类型 | 用途 |
|------|------|------|
| `@vtj/cli` | devDependencies | Vite 配置工厂（`createViteConfig`） |
| `@vtj/pro` | devDependencies | 设计器开发工具（`createDevTools`） |
| `@vtj/web` | dependencies | 运行时核心（`createProvider`/`LocalService`/`createModules`） |
| `@vtj/renderer` | dependencies | DSL 渲染器（`createRenderer`/`useProvider`） |
| `@vtj/ui` | dependencies | VTJ 内置 UI 组件（`XIcon` 等） |
| `@vtj/icons` | dependencies | 图标库 |
| `@vtj/utils` | dependencies | 工具库（`request`/`createApi`/`useApi`） |
| `@vtj/coder` | — | 代码生成器（`generator` — DSL→Vue） |
| `@vtj/parser` | — | 代码解析器（`parseVue` — Vue→DSL） |
| `@vtj/charts` | — | 图表组件 |

### 6.2 Vite 配置详解

```typescript
// vite.config.ts
import { createViteConfig } from '@vtj/cli';
import { createDevTools } from '@vtj/pro/vite';
import proxy from './proxy.config';

export default createViteConfig({
  proxy,                      // API 代理配置
  plugins: [
    createDevTools({
      // staticBase: '/sub/'  // 二级目录部署时设置
    })
  ]
});
```

### 6.3 main.ts 改造要点

1. **核心功能导入**：从 `@vtj/web` 引入 createProvider/LocalService/createModules/NodeEnv
2. **样式引入**：`import '@vtj/web/src/index.scss'`
3. **服务实例化**：开发 `LocalService` / 生产 `RemoteService`
4. **提供者创建**：配置 nodeEnv、mode（本项目用 `ContextMode.Raw`）、modules、adapter、service、router、dependencies
5. **异步初始化**：`onReady` 确保所有依赖就绪后再挂载
6. **ContextMode.Raw**：源码模式，直接使用已出码的 `.vue` 文件

### 6.4 TypeScript 配置

```json
{
  "exclude": [".vtj"]
}
```

排除原因：`.vtj` 目录包含运行时生成的临时文件、设计器元数据、编译中间产物，不应受 TS 检查。

### 6.5 Suspense 异步支持

```vue
<template>
  <Suspense>
    <router-view></router-view>
  </Suspense>
</template>
```

VTJ 生成的组件是异步加载的，`<Suspense>` 提供加载状态处理、错误边界捕获和异步生命周期管理。

---

## 附录A：Provider API 速查

### Provider 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `mode` | `ContextMode` | 运行模式（Design/Raw/Preview） |
| `globals` | `Record<string, any>` | 全局变量 |
| `adapter` | `ProvideAdapter` | 适配器接口 |
| `apis` | `Record<string, Function>` | API 方法集合 |
| `dependencies` | `Record<string, () => Promise<any>>` | 依赖加载器 |
| `service` | `Service` | 核心服务 |
| `project` | `ProjectSchema` | 当前项目配置 |
| `components` | `Record<string, any>` | 组件集合 |

### Provider 方法

| 方法 | 说明 |
|------|------|
| `load(project: ProjectSchema)` | 加载项目配置 |
| `install(app: App)` | 安装到 Vue 应用 |
| `getFile(id: string)` | 获取文件（页面或区块） |
| `getPage(id: string)` | 获取页面文件 |
| `getDsl(id: string)` | 获取区块 DSL |
| `createDslRenderer(dsl, opts?)` | 创建 DSL 渲染器 |
| `getRenderComponent(id, output?)` | 获取可渲染组件 |
| `defineUrlSchemaComponent(url, name?)` | 定义基于 URL 的异步组件 |
| `createMock(func)` | 创建 Mock 函数 |
| `createSchemaApis()` | 自动创建 API 方法 |

---

## 附录B：Engine 设计器引擎速查

### EngineOptions 配置

| 配置项 | 类型 | 必需 | 说明 |
|--------|------|------|------|
| `container` | `MaybeRef<HTMLElement>` | ✅ | 设计器渲染容器 |
| `service` | `Service` | ✅ | 文件服务接口 |
| `project` | `Partial<ProjectSchema>` | — | 项目信息 |
| `dependencies` | `Record<string, () => Promise<any>>` | — | 项目依赖 |
| `materials` | `Record<string, () => Promise<any>>` | — | 项目物料 |
| `materialPath` | `string` | — | 内置物料路径 |
| `globals` | `Record<string, any>` | — | 全局变量 |
| `adapter` | `Partial<ProvideAdapter>` | — | 设计器画布适配 |
| `install` | `(app, engine?) => void` | — | 初始化回调 |
| `remote` | `string \| null` | — | 远程服务地址 |
| `openApi` | `OpenApi` | — | OpenAPI 服务 |
| `enhance` | `boolean \| EnhanceConfig` | — | 应用增强 |

### 核心方法

| 方法 | 说明 |
|------|------|
| `openFile(fileId?)` | 打开指定文件（默认首页） |
| `saveCurrentFile()` | 保存当前文件 |
| `publish()` | 发布整个项目 |
| `genSource()` | 生成项目源代码 |
| `initHistory(block)` | 初始化区块历史记录 |
| `dispose()` | 销毁引擎并清理资源 |

### 事件系统

| 事件 | 触发时机 | 参数 |
|------|----------|------|
| `EVENT_PROJECT_CHANGE` | 项目信息变更 | `ProjectModelEvent` |
| `EVENT_BLOCK_CHANGE` | 区块内容变更 | `BlockModel` |
| `EVENT_HISTORY_CHANGE` | 历史记录变更 | `HistoryModelEvent` |
| `EVENT_PROJECT_PUBLISH` | 项目发布 | — |
| `SAVE_BLOCK_FILE_FINISH` | 文件保存完成 | `ProjectModelEvent` |

---

## 附录C：createRenderer 速查

### CreateRendererOptions

| 参数 | 类型 | 说明 |
|------|------|------|
| `Vue` | `any` | Vue 实例（默认全局 Vue） |
| `mode` | `ContextMode` | 上下文模式（默认 Runtime） |
| `dsl` | `BlockSchema` | 块定义 DSL |
| `components` | `Record<string, any>` | 可用组件 |
| `libs` | `Record<string, any>` | 第三方库 |
| `apis` | `Record<string, any>` | API 集合 |
| `loader` | `BlockLoader` | 块加载器 |
| `window` | `Window` | 目标窗口对象 |

### 七步渲染流程

```
1. new Context({ mode, dsl, attrs })
2. Vue.defineComponent → props/setup/render
3. createState → reactive / createComputed → computed / createMethods
4. createInject → inject
5. createDataSources → mock/api + transform
6. createLifeCycles + setWatches → watch(deep, immediate)
7. render() → nodeRender 递归渲染所有节点
```

---

## 第七章：常见问题排查

### 7.1 页面不显示最新修改内容

**症状**：修改了 `.vtj/vue/*.vue` 文件中的业务逻辑，但浏览器中页面行为无变化。

**排查步骤**：

1. **检查 JSON DSL 是否过时覆盖**：VTJ 的 `createDevTools` 插件可能在 JSON 文件变更时自动重新生成 `.vue` 文件。检查对应 `.vtj/files/*.json` 的 `__VERSION__` 是否与 `.vue` 中 `useProvider({ version })` 一致。

2. **清理 Vite 缓存**：
   ```bash
   rm -rf node_modules/.vite/
   ```
   然后重启 `npm run dev`。

3. **检查 `raw` 标记**：在 `.vtj/projects/linxitie.policy-exam-bank.json` 中，手写修改较多的页面应标记 `"raw": true`，防止 VTJ 设计器覆盖：
   ```json
   { "id": "mjvdqdu1", "raw": true, ... }
   ```
   当前已标记 `raw: true` 的页面：`ujvdv5fe`、`mjvdqdu1`、`login`、`questionImport`、`jjvdntly`。

4. **验证路由 ID 有效性**：AppNavigation 中使用了页面 ID 作为路由路径。确认 ID 在项目配置的 `pages[]` 中存在，否则导航到 `/page/xxx` 会 404。

5. **检查 Provider 版本号一致性**：
   - JSON DSL 中 `"__VERSION__": "1778918968644"`
   - VUE 中 `useProvider({ id: 'xxx', version: '1778918968644' })`
   - 两者必须一致，否则 Provider 可能忽略 .vue 中的逻辑。

6. **浏览器强刷**：Ctrl+Shift+R 跳过浏览器缓存。

### 7.2 导航 404 问题

**已知问题**：AppNavigation（`8jv82kin.vue`）初始版本使用了已失效的页面 ID。修复方法：

```javascript
// ❌ 错误（旧 ID）
{ name: 'home', route: '/page/9jvcm4zp' }

// ✅ 正确（当前项目配置中的实际 ID）
{ name: 'home', route: '/page/jjvdntly' }
```

项目配置中有效的页面 ID 列表：
| 页面名称 | 页面 ID | 路由路径 |
|----------|---------|----------|
| 首页 | `jjvdntly` | `/home` 或 `/page/jjvdntly` |
| 题库 | `mjvdqdu1` | `/` 或 `/page/mjvdqdu1` |
| 关于 | `njvdr28b` | `/page/njvdr28b` |
| 论坛 | `ojvdrg4v` | `/page/ojvdrg4v` |
| 下载客户端 | `pjvds138` | `/page/pjvds138` |
| 错题集 | `rjvduc4b` | `/page/rjvduc4b` |
| 成绩分析 | `sjvdul3v` | `/page/sjvdul3v` |
| 金币购 | `tjvdux1w` | `/page/tjvdux1w` |
| 答题 | `ujvdv5fe` | `/answer` 或 `/page/ujvdv5fe` |
| 题目导入 | `questionImport` | `/question-import` |
| 登录 | `login` | `/login` |

### 7.3 JSON-VUE 同步机制

**核心原则**：本项目使用 `ContextMode.Raw` 模式，浏览器直接加载 `.vtj/vue/*.vue` 文件，不通过 JSON DSL 运行时渲染。

**但 VTJ 设计器在保存时，会从 JSON DSL 重新生成 .vue 文件。** 如果 JSON 中 methods 为空或过时，生成的 .vue 将丢失所有手写业务逻辑。

**防护措施**：
1. 将手写页面标记 `"raw": true`（参见 §7.1 步骤3）
2. **每次修改 .vue 的 methods/state/lifeCycles 后，同步更新对应 .vtj/files/*.json**（参见 §3.6 开发工作流）
3. 修改 .vue 中的 `<template>` 结构应通过 VTJ 设计器操作，Claude Code 只修改 `<script>` 部分

---

## 附录D：已知问题与注意事项

### D.1 VTJ 版本与运行环境

- `@vtj/web` 使用 `ContextMode.Raw` — 直接加载 .vue 文件，不运行时编译 JSON
- `@vtj/pro/vite` 的 `createDevTools` 插件在开发模式下工作，生产环境需移除
- `enableStaticRoute: true` — Provider 自动为项目配置中每个页面注册 `/page/{id}` 路由
- `.vtj/router.js` 中定义的路由也会被 Provider 注册，但需确保语法正确

### D.2 认证通信模式

本项目**不使用** `@vtj/utils` 的 `request` 工具，而是采用原生 `fetch()` + 共享认证模块：
- `window.__VTJ_AUTH__.apiFetch(url, options)` — 自动附加 Authorization 头
- `window.__VTJ_AUTH__.getJsonHeaders()` — 获取 JSON Content-Type 头 + Auth
- `window.__VTJ_AUTH__.getAuthHeaders()` — 仅获取 Authorization 头

### D.3 前后端分离部署

- 开发环境：Vite Dev Server (port 5173) → proxy → FastAPI (port 8000)
- 代理配置：`/api` → `http://localhost:8000`，启用 WebSocket 代理
- 前端使用 Hash 路由模式 (`createWebHashHistory`)

### D.4 已修复的阻断性问题

| 问题 | 状态 | 修复日期 |
|------|------|----------|
| AppNavigation 使用失效页面 ID（5个链接全部 404） | ✅ 已修复 | 2025-06 |
| `.vtj/router.js` 语法错误（`component;` → `component:`） | ✅ 已修复 | 2025-06 |
| AnswerPage (ujvdv5fe) 版本号不一致 | ✅ 已修复 | 2025-06 |
| 5 个核心页面 JSON DSL 不同步 | ✅ 已修复 | 2025-06 |
| 6 个页面使用硬编码模拟数据（零 API 调用） | ⚠️ 部分修复 | 2025-06 |
| 论坛 API 端点 `/api/forum/posts` 缺失 | ✅ 已修复 | 2025-06 |

---

## 附录E：页面-API 对照表

### VTJ 生成页面

| 页面 | .vue 文件 | 路径 | API 调用 | 数据来源 |
|------|-----------|------|----------|----------|
| QuestionBank (题库) | `mjvdqdu1.vue` | `/` | `GET /api/questions/subcategory-stats`, `GET /api/practice/records` | ✅ API |
| HomePage (首页) | `jjvdntly.vue` | `/home` | `GET /api/recruitment` | ✅ API |
| Login (登录) | `login.vue` | `/login` | `POST /api/auth/login`, `/register`, `/sms-login` | ✅ API |
| AnswerPage (答题) | `ujvdv5fe.vue` | `/answer` | `GET /api/questions/random`, `POST /api/practice/record`, `POST /api/stats/auto-checkin` | ✅ API |
| QuestionImport (导入) | `questionImport.vue` | `/question-import` | 7 个导入相关端点 | ✅ API |
| WrongQuestionSet (错题) | `rjvduc4b.vue` | `/page/rjvduc4b` | `GET /api/questions/` | ✅ API |
| SignInCard (签到) | `wjve09k1.vue` | (首页区块) | `POST /api/stats/auto-checkin`, `GET /api/stats/dashboard`, `GET /api/stats/weekly-checkin` | ✅ API |
| PersonalGoalCard (目标) | `cjv83bou.vue` | (首页区块) | `GET /api/goals/`, `POST /api/goals/` | ✅ API |
| ExamCalendar (日历) | `gjv83ley.vue` | (首页区块) | `GET /api/calendar/exams` | ✅ API |
| QuoteBanner (金句) | `11jve6eq7.vue` | (首页区块) | `GET /api/news` | ✅ API |
| RecruitmentInfo (招考) | `hjv83oby.vue` | (首页区块) | `GET /api/recruitment` | ✅ API |
| ScoreAnalysis (成绩) | `sjvdul3v.vue` | `/page/sjvdul3v` | `GET /api/stats/dashboard`, `GET /api/stats/practice-trend` | ✅ API |
| Forum (论坛) | `ojvdrg4v.vue` | `/page/ojvdrg4v` | `GET /api/forum/posts` | ✅ API |
| GoldPurchase (金币) | `tjvdux1w.vue` | `/page/tjvdux1w` | — | ❌ 模拟数据 |
| DownloadClient (下载) | `pjvds138.vue` | `/page/pjvds138` | — | ❌ 静态内容 |
| StudyMaterials (资料) | `ijv83t8x.vue` | (首页区块) | — | ❌ 模拟数据 |
| About (关于) | `njvdr28b.vue` | `/page/njvdr28b` | — | ❌ 静态内容 |
| SmartRecommend | `smartRecommend.vue` | `/smartRecommend` | `provider.call(...)` | ⚠️ 死代码（路由已修复） |

### 区块组件（无独立路由）

| 区块 | .vue 文件 | 用途 | API 调用 |
|------|-----------|------|----------|
| NavBar | `ijvdn7sw.vue` | 页面导航栏 | 仅 auth 状态检查 |
| AppNavigation | `8jv82kin.vue` | 公共导航栏 | 仅 auth 状态检查 |
| CountdownTimer | `kjvdoyca.vue` | 联考倒计时 | — |
| SignInStatus | `ajv83813.vue` | 签到情况 | `provider.call('signIn')` |
| DailyQuote | `ejv83etn.vue` | 申论金句展示 | — |
| GoalCard | `zjve4pgr.vue` | 个人小目标 | —（待连接） |

### 后端端点未连接清单（待开发）

| 模块 | 未连接端点 | 优先级 |
|------|-----------|--------|
| 考试/试卷 | 全部 `/api/exams/*` 和 `/api/papers/*`（15+ 端点） | 🔴 高 |
| 题目交互 | `/api/questions/{id}/favorite`, `/note`, `/marker`（8 端点） | 🟡 中 |
| LLM | `POST /api/llm/chat` | 🟡 中 |
| 媒体/视频 | 全部 `/api/media/*`, `/api/video/*`（8+ 端点） | 🟢 低 |
| WebSocket | 全部 `/ws/*`（4 端点） | 🟢 低 |
| 金币系统 | 后端 TODO：待创建 | 🟢 低 |

---

## 附录F：开发工作流补充（§3.6 增强）

### 修改 .vue 后的强制同步步骤

每次 Claude Code 修改 VTJ 生成页面的 `<script>` 部分（methods/state/lifeCycles/computed）后，**必须**同步更新对应的 `.vtj/files/*.json`：

1. **方法同步**：在 JSON 的 `methods` 中添加方法声明（`type` + `params`），不需要完整函数体
2. **状态同步**：在 JSON 的 `state` 中更新字段列表和初始值
3. **生命周期同步**：在 JSON 的 `lifeCycles` 中添加 `mounted`/`beforeUnmount` 声明
4. **版本同步**：保持 JSON 的 `__VERSION__` 与 .vue 中 `useProvider({ version })` 一致

```
修改 .vtj/vue/xxx.vue 的 <script>
  │
  ├── 步骤1：提取修改的 methods/state/lifeCycles 签名
  ├── 步骤2：更新 .vtj/files/xxx.json 对应字段
  ├── 步骤3：确认 __VERSION__ 一致
  └── 步骤4：清理 Vite 缓存 + 重启验证
```

### 新增页面到路由的步骤

```
VTJ 设计器创建页面 → .vtj/files/*.json + .vtj/vue/*.vue
  │
  ├── 步骤1：在 src/router/index.ts 添加路由条目
  │   { path: '/new-page', component: () => import('$vtj/vue/xxx.vue') }
  │
  └── 步骤2：在导航组件中添加链接（使用正确的页面 ID）
      { name: 'newpage', title: '新页面', route: '/page/<page-id>' }
```

---

> 本文档基于 [VTJ.PRO 官方文档](https://www.vtj.pro/guide/) 与砺安题库项目实际代码整理，随项目演进持续更新。
