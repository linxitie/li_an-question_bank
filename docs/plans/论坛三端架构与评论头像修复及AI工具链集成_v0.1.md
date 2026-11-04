# 论坛三端架构、评论头像修复与 AI 工具链集成方案 v0.1

> 状态：已批准，执行中（2026-10-22）
> 日期：2026-10-22
> 仓库：`D:\AAA项目文件\砺安题库\li_an-question_bank`
> 当前分支：`main` @ `1d897d1`，29 个未提交改动
> 基线测试：前端 17 passed；后端 27 passed（2026-10-22 实测）

## 0. 审批摘要

本方案只做三件事：

1. 把论坛三端、三角色、后端接口、权限与图中目标架构的差距梳理清楚。
2. 修复 PC 与平板回复页评论头像不显示；后端字段已经存在，根因在前端模板。
3. 安装并验证 vtj-mcp-server、Playwright MCP、superpowers（`brainstorming`、`writing-plans`）。

图中尚未实现的私信、好友、独立通知服务、独立审核服务，本轮只给演进建议，不写业务代码。

需要用户拍板的事项：

| 编号 | 需要确认 | 推荐选项 |
|---|---|---|
| D1 | `li-an-workflow` 技能文件缺失，是否授权我按现有规则新建 | 新建，先给草稿再启用 |
| D2 | 29 个未提交改动如何隔离到分支 | 先在 `feature/forum-5-fixes` 提交现有论坛改动 |
| D3 | `.vtj/vue/forum.vue` 是 `raw:true`，PC 评论头像必须改 `<template>` | 一次性授权用 `vtj_write_vue_template`，dryRun 后写入并备份 |
| D4 | 头像修复范围 | PC 评论 + 平板/手机详情；平板列表真实头像作为可选项 |
| D5 | MCP 配置放哪里 | vtj 放项目配置，Playwright 与 superpowers 放全局配置 |
| D6 | superpowers 自动流程是否全开 | 只使用 `brainstorming`、`writing-plans`，不让它自动建 worktree |
| D7 | 架构图中未实现模块是否本轮实现 | 本轮只出演进建议，不实现 |
| D8 | 是否允许安装依赖、写 `node_modules`/锁文件 | 允许，安装后立即验证并记录版本 |

未确认前不执行：不切分支、不改业务代码、不装依赖、不改全局配置。

## 1. 现状取证

### 1.1 三端页面与路由

| 端 | 列表路由 | 列表页面 | 详情 | 发帖 | 路由守卫 |
|---|---|---|---|---|---|
| PC | `/forum` | `.vtj/vue/forum.vue` | 页内弹层，不是独立路由 | 页内弹窗 | 允许游客；互动接口要求登录 |
| 平板 | `/tablet/forum` | `.vtj/vue/tablet_forum.vue` | `/tablet/forum/:id` → `src/views/student/mobile/mobile_forum_detail.vue` | `/tablet/forum/create` → `mobile_forum_create.vue` | `/tablet/*` 仅学生；教师/管理员跳 `/unauthorized` |
| 手机 | `/mobile/forum` | `.vtj/vue/mobile_forum.vue` | `/mobile/forum/:id` → `mobile_forum_detail.vue` | `/mobile/forum/create` → `mobile_forum_create.vue` | `/mobile/*` 仅学生；教师/管理员跳 `/unauthorized` |

关键结论：

- 平板没有独立详情页，直接复用手机手写详情页；平板列表页则是 `.vtj` 页面。
- PC 论坛详情是页内弹层，评论列表也在 `forum.vue` 内。
- 路由使用 `createWebHashHistory()`，实际访问地址是 `http://localhost:5173/#/forum` 这类 hash 形式。
- 三个 `.vtj` 论坛页面 `forum`、`tablet_forum`、`mobile_forum` 在项目配置中均为 `raw: true`。按 R2，禁止对它们执行 `vtj_sync_vue_to_dsl`；按 R3，`<template>` 调整必须由用户在 VTJ 设计器完成，或一次性授权 AI 使用 `vtj_write_vue_template`。

### 1.2 后端接口与权限

文件：`backend/app/api/v1/community/forum.py`，前缀 `/api/forum`。

| 能力 | 接口 | 权限 | 现状 |
|---|---|---|---|
| 帖子列表 | `GET /api/forum/posts` | `get_optional_user` | 游客可读 |
| 帖子详情 | `GET /api/forum/posts/{id}` | `get_optional_user` | 游客可读 |
| 评论列表 | `GET /api/forum/posts/{id}/comments` | `get_optional_user` | 游客可读 |
| 发帖 | `POST /api/forum/posts` | `get_current_user` | 任意登录用户 |
| 评论/回复 | `POST /api/forum/posts/{id}/comments` | `get_current_user` | 任意登录用户 |
| 点赞/表情 | 相关 POST 接口 | `get_current_user` | 任意登录用户 |
| 删除 | `DELETE` 相关接口 | 作者或 `role_level >= 2` | 管理员可删 |

后端用户摘要 `_user_brief()` 已经返回：

```json
{
  "id": 3,
  "nickname": "202516001",
  "avatar": "/uploads/avatars/avatar_3_aca778e0.jpg",
  "avatarFrame": null,
  "signature": null,
  "userType": "student"
}
```

评论序列化 `_serialize_comment()` 已带 `user` 字段；评论列表接口也批量加载了用户。也就是说，**头像数据链路在后端是通的，缺口在前端渲染**。

`/uploads` 已在 `backend/app/main.py:593` 挂载；Vite 开发代理也包含 `/uploads`。数据库用户 3 的头像文件路径真实存在。

### 1.3 三角色与图中目标架构的差距

| 图中能力 | 实际实现 | 差距 |
|---|---|---|
| 学生专区 | PC `/forum` + 平板/手机 `/tablet|mobile/forum` | 已实现 |
| 教师专区 | PC 教师仪表盘存在；论坛与学生共用同一套帖子/评论接口 | 没有教师专属版块、教师发帖身份标识、教师巡版/处置台 |
| 管理员专区 | PC 管理端存在；论坛删除允许 `role_level >= 2` | 未发现独立的管理员论坛管理页；审核动作主要是删除 + 敏感词日志 |
| 私信消息 | 未发现论坛私信模型/接口 | 未实现 |
| 添加好友/好友交流 | 未发现好友关系模型/接口 | 未实现 |
| 论坛专属问题反馈窗口 | 未发现独立反馈模型/接口；只能用普通发帖表达 | 未实现 |
| 系统内容审核服务 | `sensitive_filter` + `_log_violation` + `SysOperationLog` | 是应用内过滤与日志，不是独立审核服务 |
| 消息通知 | `mobile_notifications.vue` 调用 `/api/stats/messages` | 未发现独立通知表/通知服务；论坛回复不会生成站内通知 |

另有一个需要确认的产品问题：`/tablet/*`、`/mobile/*` 当前只允许学生访问，教师和管理员会被重定向到 `/unauthorized`。如果图中“教师专区/管理员专区”也要在平板或手机上使用，需要改路由守卫；本轮不擅自改。

### 1.4 头像链路与根因

数据链路：

```text
sys_user.avatar
  → forum.py::_user_brief()
  → forum.py::_serialize_comment()
  → GET /api/forum/posts/{id}/comments
  → src/modules/community/api.ts::ForumCommentItem.user.avatar
  → src/modules/community/store.ts::loadComments()
  → 页面模板
```

断点：

| 页面 | 位置 | 现状 | 结果 |
|---|---|---|---|
| PC `forum.vue` | 评论 `297-299` | 只渲染 `<span class="avatar-text-sm">{{ nickname.charAt(0) }}</span>` | 昵称以 `202516001` 开头时显示“2” |
| PC `forum.vue` | 子评论 `325-326` | 同上 | 子评论同样显示“2” |
| 平板详情 `mobile_forum_detail.vue` | `20-22`、`69-71`、`97-99` | 已有 `<img v-if="user.avatar">`，但没有 `@error` 回退 | 头像 404 时出现破图/空框 |
| 手机详情 `mobile_forum_detail.vue` | 同上 | 同上 | 同上 |
| 平板列表 `tablet_forum.vue` | `102-104`、`199-201` | 只用渐变背景 + `User` 图标 | 列表不显示真实头像 |
| 手机列表 `mobile_forum.vue` | 约 `223-225` | 已有 `avatarFailed` 处理 | 列表已有回退 |

PC 根因不是接口没返回头像，而是评论模板从未读取 `comment.user.avatar`。这是本次修复的主目标。

## 2. 目标与范围

### 2.1 本轮范围

- 产出论坛三端架构说明与目标差距文档。
- PC 评论、子评论显示真实头像；头像为空或加载失败时显示可读的文字回退，不再显示“2”。
- 平板/手机详情页评论、子评论增加图片加载失败回退。
- 安装并验证 vtj-mcp-server、Playwright MCP、superpowers 两个技能。
- 补齐或由用户提供 `li-an-workflow` 技能。
- 按新分支拓扑隔离现有脏工作树。

### 2.2 本轮不做

- 不实现私信、好友、独立通知服务、独立审核服务。
- 不新增论坛版块/角色专区字段。
- 不修改教师/管理员在平板/手机上的访问策略，除非用户明确要求。
- 不重构论坛 store/API，不改变评论排序、点赞、敏感词逻辑。
- 不对 `.vtj` 页面执行 `vtj_sync_vue_to_dsl`。

## 3. 方案 A：论坛架构梳理

### 3.1 交付物

新增 `docs/plans/论坛三端架构与评论头像修复及AI工具链集成_v0.1.md`（本文件），归档副本放 `solve_problems_files/`，并更新 `docs/README.md` 与 `solve_problems_files/README.md` 索引。

文档中明确区分：

- 已实现：三端路由、页面复用、公开读接口、登录写接口、删除权限、敏感词日志、上传目录挂载。
- 部分实现：管理员删除、移动端通知入口、教师/管理员 PC 仪表盘。
- 未实现：私信、好友、独立通知、独立审核、论坛专属反馈窗口、教师巡版台。

### 3.2 目标架构建议（只给演进方向，不在本轮落地）

分三期，避免一次性大改：

1. 期一：身份与展示
   - 帖子/评论增加 `userType` 徽标（学生/教师/管理员）。
   - 增加 `audience` 字段（`all`/`student`/`teacher`），默认 `all`，后端列表按角色过滤。
   - 管理端增加论坛管理页：帖子/评论检索、隐藏、删除、敏感词命中记录。

2. 期二：反馈闭环
   - 新增 `forum_feedback` 模型，关联帖子/评论/题目/练习记录。
   - 状态机：`pending` → `processing` → `resolved`/`rejected`。
   - 教师/管理员处理台；学生端“我的反馈”列表。

3. 期三：消息与社交
   - 通知服务独立：outbox 表 + 事件消费者，论坛回复/审核结果写通知。
   - 私信、好友关系独立模块，不复用论坛帖子表。
   - 审核服务独立：敏感词、图片审核、人工复核队列。

这些都需要单独方案、单独分支、单独审批；本文件只作为架构基线。

## 4. 方案 B：评论头像修复

### 4.1 后端

不改接口字段。现有 `_user_brief()` 已返回 `avatar`、`avatarFrame`、`nickname`、`userType`。

只补测试，防止回归：

- 在 `backend/tests/test_forum_posting.py` 增加断言：创建带 `avatar` 的用户，发帖/评论后，`GET` 评论列表返回的 `user.avatar` 与数据库一致。
- 覆盖主评论与子评论两条路径。
- 不新增数据库字段，不做迁移。

### 4.2 前端公共工具

新增 `src/modules/community/avatar.ts`：

```ts
export function avatarInitial(name?: string | null): string {
  const text = (name || '').trim();
  if (!text) return '友';
  const han = text.match(/[\u4e00-\u9fa5]/);
  if (han) return han[0];
  const letter = text.match(/[A-Za-z]/);
  if (letter) return letter[0].toUpperCase();
  return '友';
}
```

目的：

- 昵称是 `202516001` 这类纯数字时，不再把“2”当头像文字。
- 中文昵称取第一个汉字；英文取首字母；空值用“友”。
- PC 与手机/平板详情共用同一规则，避免三处各写一套。

新增 `src/modules/community/__tests__/avatar.spec.ts`，覆盖：

- `202516001` → `友`
- `张三` → `张`
- `2025张三` → `张`
- `alice` → `A`
- 空值/空白 → `友`

### 4.3 PC `forum.vue`

这是本次唯一需要改 `.vtj` 模板的地方。`forum` 页面 `raw: true`，所以必须先满足 D3。

模板改动（评论）：

```vue
<div class="comment-avatar" @click.stop="viewUser(comment.user?.id)">
  <img
    v-if="comment.user?.avatar && !avatarFailed['comment-' + comment.id]"
    :src="comment.user.avatar"
    class="avatar-img-sm"
    alt=""
    @error="markAvatarFailed('comment-' + comment.id)"
  />
  <span v-else class="avatar-text-sm">{{ avatarInitial(comment.user?.nickname) }}</span>
</div>
```

子评论同理，key 换成 `reply-`：

```vue
<img
  v-if="child.user?.avatar && !avatarFailed['reply-' + child.id]"
  :src="child.user.avatar"
  class="avatar-img-sm"
  alt=""
  @error="markAvatarFailed('reply-' + child.id)"
/>
<span v-else class="avatar-text-sm">{{ avatarInitial(child.user?.nickname) }}</span>
```

脚本改动：

```ts
import { avatarInitial } from '@/modules/community/avatar';

const avatarFailed = reactive<Record<string, boolean>>({});
const markAvatarFailed = (key: string) => {
  avatarFailed[key] = true;
};
```

样式改动：

```css
.avatar-img-sm {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 8px;
}
```

说明：

- `comment.user?.avatar` 为空时直接用文字回退，不请求空 URL。
- 图片 404 时 `@error` 把对应 key 置为 `true`，Vue 重新渲染为文字回退。
- `alt=""` 是刻意设置：头像旁边已有昵称文本，避免屏幕阅读器重复朗读。
- 不改评论数据结构、不改排序、不改点赞逻辑。
- 可选一并修复：帖子列表/详情头像的 `onAvatarError` 目前只隐藏 `img`，会留下空框。建议用同一 `avatarFailed` 机制，key 为 `post-{id}`、`current-post`，让 404 时显示文字回退。此项不改变接口，风险低，但会增加两处模板改动；是否纳入见 D4。

### 4.4 平板/手机详情 `mobile_forum_detail.vue`

该文件是手写页，不受 R3 模板限制，可直接改。

改动：

1. 引入 `avatarInitial`，替换原有 `initial()` 的纯 `slice(0, 1)`。
2. 新增 `avatarFailed` 映射与 `markAvatarFailed()`。
3. 三处头像 `img` 增加失败判断与 `@error`：
   - 帖子作者头像：key `post-{id}`
   - 主评论头像：key `comment-{id}`
   - 子评论头像：key `reply-{id}`

示例：

```vue
<img
  v-if="c.user && c.user.avatar && !avatarFailed['comment-' + c.id]"
  :src="c.user.avatar"
  alt=""
  @error="markAvatarFailed('comment-' + c.id)"
/>
<span v-else>{{ avatarInitial(c.user && c.user.nickname) }}</span>
```

这样平板详情与手机详情同时受益，因为平板详情复用了这个页面。

### 4.5 平板列表 `tablet_forum.vue`（可选）

当前列表用渐变 + `User` 图标，不显示真实头像。若要显示：

- 模板改为 `<img v-if="post.avatar && !avatarFailed[...]" ...>`，否则保留渐变图标。
- 需要确认平板列表数据源是否已经带 `avatar` 字段；`tablet_forum.vue` 当前使用 `post.avatarBg` 等展示字段，可能没有透传后端 `user.avatar`。
- 该页也是 `raw: true`，需要 D3 同等的模板授权。

建议作为 P2 可选，不与“回复页头像”混在一个子任务里。若用户要求“平板列表也必须真实头像”，则单独开 `feature/forum-tablet-avatar-list` 子分支。

### 4.6 验收标准

- PC 帖子详情评论列表：每条评论左侧显示真实头像；子评论同样显示。
- 头像 URL 为空：显示昵称首字（中文优先），不显示数字“2”。
- 头像 404：自动回退文字，不出现破图。
- 平板/手机详情：同上。
- 游客可正常看到头像（评论接口公开）。
- 不改变评论内容、排序、点赞数、回复关系。
- 后端接口响应字段不变，老客户端不受影响。

## 5. 方案 C：AI 工具链安装与使用

### 5.1 先补齐 `li-an-workflow`

当前缺失：

```text
D:\AAA项目文件\砺安题库\li_an-question_bank\.opencode\skills\li-an-workflow\SKILL.md
```

`.opencode/` 已被 `.gitignore` 忽略；`.agents/skills` 下有 40 个 mattpocock 技能，但没有 `li-an-workflow`。

两种处理：

- 方案 C1-A（推荐）：用户提供原 `li-an-workflow/SKILL.md`，我按原文件安装。
- 方案 C1-B：用户授权我新建，内容至少包含：
  - 先读 `AGENTS.md`、`docs/plans/`、分支说明书。
  - 方案先行、审批后执行、文档归档。
  - `feature/<模块>/<子任务>` 分支拓扑与合并门禁。
  - VTJ R1-R3、`raw:true` 页面禁止 sync。
  - 代码质量、安全、可维护性、后端字段、路由、前端展示检查表。
  - 测试与验收证据要求。

在技能补齐前，本方案只能作为“待审批文档”，不能进入实施。

### 5.2 vtj-mcp-server

现状：

- 项目 `.mcp.json` 已有 vtj 配置，但 `vtj-mcp-server/node_modules` 不存在。
- `package.json` 已有 `mcp:setup`、`mcp:start`、`mcp:test`。
- VTJ 版本：`@vtj/web` 等 `0.16.35`，`@vtj/cli` `0.12.19`。
- vtj-mcp-server 版本 `1.0.0`，ESM。

安装：

```powershell
npm run mcp:setup
npm run mcp:test
```

验收：

- `mcp:test` 能列出工具，记录实际工具数量。
- 至少验证 `vtj_get_project_info`、`vtj_get_routing_info`、`vtj_read_vue`、`vtj_write_vue_script`、`vtj_write_vue_template`（dryRun）可用。
- 不执行 `vtj_sync_vue_to_dsl`，因为三个论坛页都是 `raw: true`。

opencode 配置（项目根 `opencode.json`，若当前版本不加载则改用 `.opencode/opencode.json`）：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "vtj": {
      "type": "local",
      "command": ["node", "vtj-mcp-server/vtj-mcp-server.js"],
      "enabled": true
    }
  }
}
```

若 opencode 启动 MCP 时工作目录不是项目根，回退到包装脚本 `scripts/run-vtj-mcp.cmd`：

```bat
@echo off
cd /d "%~dp0.."
node vtj-mcp-server\vtj-mcp-server.js
```

配置改为：

```json
"command": ["cmd", "/c", "scripts\\run-vtj-mcp.cmd"]
```

### 5.3 Playwright MCP

官方配置：

```json
{
  "mcp": {
    "playwright": {
      "type": "local",
      "command": ["npx", "-y", "@playwright/mcp@latest", "--headless"],
      "enabled": true
    }
  }
}
```

说明：

- 本机已有 Playwright 浏览器缓存：`C:\Users\31127\AppData\Local\ms-playwright`（chromium-1228/1234）。
- `--headless` 适合自动截图与断言；需要观察交互时临时去掉。
- 安装后重启 opencode，确认工具列表出现 `browser_navigate`、`browser_snapshot`、`browser_take_screenshot` 等。
- 用 `http://localhost:5173/#/forum` 验证，注意 hash 路由。

### 5.4 superpowers

官方仓库：`github.com/obra/superpowers`。

当前 opencode `1.19.3` 是 V1 配置，使用 `plugin` 键。全局配置：

`C:\Users\31127\.config\opencode\opencode.json`

在现有 `plugin` 数组中追加：

```json
"superpowers@git+https://github.com/obra/superpowers.git"
```

完整示例：

```json
"plugin": [
  "opencode-antigravity-auth@latest",
  "oh-my-opencode-slim@latest",
  "superpowers@git+https://github.com/obra/superpowers.git"
]
```

注意：

- V2 才使用 `plugins` 键；当前 V1 不要混用。
- 真实技能名是 `brainstorming`、`writing-plans`，不是用户写的 `brainstorm`、`writting-plans`。
- 安装后必须重启 opencode，当前会话不会自动获得新技能。
- 若 Windows 上 git 插件安装失败，回退：
  ```powershell
  npm install superpowers@git+https://github.com/obra/superpowers.git --prefix "$HOME\.config\opencode"
  ```
  然后把 `plugin` 改为本地 `node_modules/superpowers` 路径。
- 全局配置里已有 API key（Context7、provider），修改前先备份，不把该文件提交到仓库。

### 5.5 工作流优先级

superpowers 注入的行为不能覆盖项目红线。建议优先级：

```text
用户本轮明确指令
  > AGENTS.md 的 R1-R3 与安全红线
  > li-an-workflow
  > superpowers 技能
  > 通用最佳实践
```

使用策略：

- 只用 `brainstorming` 做方案发散，用 `writing-plans` 写计划。
- 不让 superpowers 自动创建 worktree；分支由本项目拓扑控制。
- 不让 superpowers 自动执行“subagent-driven-development”式并行写代码，除非用户明确同意。
- 任何技能生成的计划，仍要落到 `docs/plans/` 并经用户审批。

## 6. 分支与提交方案

### 6.1 当前问题

- 当前在 `main`，29 个未提交改动，包含论坛 5 项修复、文档、测试、VTJ 页面等。
- 本地 `feat/forum-personalization` 与 `main` 指向同一提交，没有独有提交，不能承载新工作。
- 直接在新分支上继续堆改动，会把“已有 5 项修复”和“本次头像修复”混在一起，无法单独回滚。

### 6.2 推荐分支图

```text
main (1d897d1)
├── feature/forum
│   ├── feature/forum-5-fixes        # 收纳现有 29 个改动中的论坛 5 项修复
│   ├── feature/forum-architecture   # 本架构文档
│   └── feature/forum-comment-avatar       # 本次头像修复
└── feature/dev-tooling
    └── feature/dev-tooling-ai   # MCP + superpowers + 文档
```

说明：

- 现有 `feat/forum-personalization` 保留不动，作为历史分支，不删除、不重置。
- 所有子分支从对应父分支切出，不直接改 `main`。
- 子分支完成后先合并到父分支；父分支验收通过后，再由用户决定是否合并 `main`。
- 工具链配置属于独立工作域，不混进论坛业务分支。

### 6.3 脏工作树处理

推荐步骤（审批后执行）：

1. 备份：
   ```powershell
   git -C "D:\AAA项目文件\砺安题库\li_an-question_bank" diff > "D:\AAA项目文件\砺安题库\li_an-question_bank\forum-working-tree.patch"
   git -C "D:\AAA项目文件\砺安题库\li_an-question_bank" status --porcelain > "D:\AAA项目文件\砺安题库\li_an-question_bank\forum-working-tree-status.txt"
   ```
   注意：`git diff` 不含未跟踪文件；未跟踪文件另列清单。
2. 切出 `feature/forum-5-fixes`，把现有 5 项修复相关文件分批提交：
   - 后端：`forum.py`、`auth.py`、`models.py`、`schemas.py`、`main.py`
   - 前端：`forum.vue`、`mobile_forum.vue`、`tablet_forum.vue`、`mobile_forum_detail.vue`、`mobile_forum_create.vue`、`profile.vue`、`router/index.ts`、`community/store.ts`、`community/api.ts`
   - 测试：`test_forum_posting.py`、`store.spec.ts`、`reactions.spec.ts`
   - 组件：`src/components/forum/`
   - 文档：`docs/plans/论坛5项问题修复_v0.1_实施计划.md`
3. 不属于论坛 5 项修复的改动（`.vtj/materials`、`.vtj/projects`、`package-lock.json`、其他文档）单独判断：
   - 与本次无关的，保留未提交或另开分支；
   - 不强行打包进论坛分支。
4. 从 `feature/forum` 切出 `feature/forum-comment-avatar`，只做头像修复。
5. 从 `main` 切出 `feature/dev-tooling`，再切 `feature/dev-tooling-ai`，只做工具链配置与文档。

若用户不想提交现有脏改动，备选方案是 `git stash push -u` 后切分支；但这会把未跟踪文件一起藏起来，恢复时容易冲突，不如显式分支提交可控。推荐前者。

### 6.4 提交拆分

| 分支 | 提交 | 内容 |
|---|---|---|
| `feature/forum-5-fixes` | `feat(forum): 完成论坛5项问题修复` | 现有 5 项修复 + 回归测试 |
| `feature/forum-architecture` | `docs(forum): 梳理三端架构与目标差距` | 本方案 + 索引 |
| `feature/forum-comment-avatar` | `fix(forum): 评论头像展示真实头像并增加失败回退` | avatar.ts、avatar.spec.ts、forum.vue、mobile_forum_detail.vue、后端测试 |
| `feature/dev-tooling-ai` | `chore(tooling): 接入 VTJ/Playwright MCP 与 superpowers` | 配置、安装说明、验证记录 |

每个提交前跑对应测试；不以“代码写完”代替测试通过。

## 7. 验证方案

### 7.1 基线（已实测）

```powershell
npx vitest run src/modules/community/__tests__/store.spec.ts src/modules/community/__tests__/reactions.spec.ts
# 2 files / 17 tests passed

cd backend
python -m pytest tests/test_forum_posting.py tests/test_community_module.py -q
# 27 passed
```

### 7.2 头像修复后

前端：

```powershell
npx vitest run src/modules/community/__tests__/avatar.spec.ts src/modules/community/__tests__/store.spec.ts src/modules/community/__tests__/reactions.spec.ts
```

后端：

```powershell
cd backend
python -m pytest tests/test_forum_posting.py tests/test_community_module.py -q
```

类型检查：

```powershell
npm run typecheck
```

若 `typecheck` 存在历史基线错误，记录改动前后错误数量，不把历史错误算到本次提交；不新增错误。

### 7.3 浏览器验收（Playwright MCP）

前置：

```powershell
# 终端 1
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 终端 2
npm run dev
```

地址：

```text
http://localhost:5173/#/forum
http://localhost:5173/#/tablet/forum
```

PC 用例：

1. 以游客打开 `#/forum`，等待帖子列表。
2. 点击第一条有评论的帖子，打开详情弹层。
3. 断言评论头像 `img` 存在，`src` 包含 `/uploads/avatars/`，`naturalWidth > 0`。
4. 断言页面不再出现以纯数字“2”作为评论头像的文字。
5. 拦截 `/uploads/**` 返回 404，刷新，断言回退为中文首字/“友”，不是破图。

平板用例：

1. 视口设为 1024×768。
2. 打开 `#/tablet/forum`，点击帖子进入 `#/tablet/forum/{id}`。
3. 断言评论头像加载成功；再模拟 404，断言文字回退。

截图归档到临时目录，不提交到仓库。

### 7.4 手工验收

- 用户用真实学生账号在 PC 和平板各看一条有回复的帖子。
- 确认头像与个人资料页一致；清缓存/换浏览器后仍一致。
- 确认评论内容、点赞数、回复关系未变化。

## 8. 风险与回滚

| 风险 | 影响 | 缓解 |
|---|---|---|
| R3：`forum.vue` 是 `raw:true` | 改模板可能违反项目红线 | D3 明确授权；`vtj_write_vue_template` 先 dryRun，写入前自动备份 `.bak` |
| 误跑 `vtj_sync_vue_to_dsl` | 手写方法丢失，设计器回存覆盖 | 三个论坛页禁止 sync；命令清单中不包含该工具 |
| 脏工作树混入头像提交 | 无法单独回滚 | 先按 6.3 拆分支提交 |
| 头像 URL 404 | 破图/空框 | `@error` 映射 + 文字回退；测试拦截 404 |
| 纯数字昵称 | 回退仍显示“2” | `avatarInitial()` 跳过数字，回退“友” |
| superpowers 自动流程覆盖项目规则 | 分支/审批失控 | 只启用两个技能；优先级写死；不让它自动建 worktree |
| Playwright MCP 首次下载失败 | 无法自动验收 | 浏览器已缓存；失败时退回 `npx playwright` 脚本 + 手工截图 |
| vtj MCP 工作目录不对 | 找不到 `.vtj` | 项目配置 + `scripts/run-vtj-mcp.cmd` 包装脚本 |
| `npm run mcp:setup` 改锁文件 | 依赖漂移 | 安装后检查 `git diff`，只保留必要变更；记录版本 |
| 全局配置含密钥 | 泄露 | 全局配置不提交；修改前备份；文档不粘贴密钥 |

回滚：

- 代码：`git revert` 对应提交，不 `reset --hard`。
- VTJ 模板：使用 `vtj_write_vue_template` 生成的 `.bak` 或 `git checkout -- .vtj/vue/forum.vue`（仅限未提交时）。
- 工具链：从配置数组移除插件/MCP 条目，重启 opencode；`vtj-mcp-server/node_modules` 可直接删除。
- 分支：不删除父分支；子分支回滚用 revert，不强制推送。

## 9. 实施顺序（审批通过后）

1. D1 确认工作流文件；D2 确认脏工作树处理；D3/D4 确认模板授权与头像范围；D5/D6 确认安装位置与 superpowers 策略；D7/D8 确认范围与依赖安装。
2. 建分支、提交现有 5 项修复，跑基线测试。
3. 写架构文档并归档，更新索引。
4. 实现 `avatar.ts` + 单元测试。
5. 改 PC 评论模板（按 D3 授权方式）+ 平板/手机详情页。
6. 跑前端/后端测试，Playwright 截图验收。
7. 安装并验证 vtj/Playwright/superpowers；重启 opencode；记录工具与技能清单。
8. 合并子分支到父分支，输出验收记录；等待用户决定是否合并 `main`。

## 10. 已确认决策（2026-10-22）

- D1：授权新建 li-an-workflow 技能，先起草再启用。
- D2：先把现有论坛 5 项修复提交到 eature/forum-5-fixes，再开头像子分支。
- D3：授权 AI 修改 PC orum.vue 的 <template>；必须先 dryRun，写入前备份。
- D4：本轮修 PC 评论 + 平板/手机详情；平板列表真实头像作为后续可选子任务。
- D5：vtj MCP 放项目配置，Playwright MCP 与 superpowers 放全局配置。
- D6：superpowers 只使用 rainstorming、writing-plans，不让它自动建 worktree。
- D7：私信/好友/通知/独立审核本轮只出演进建议，不实现。
- D8：允许安装依赖、写 tj-mcp-server/node_modules、修改全局 opencode.json。

分支命名说明：Git 不允许 eature/forum 与 eature/forum/xxx 同时作为 ref 存在，因此父分支保持 eature/forum，子分支使用 eature/forum-xxx。
