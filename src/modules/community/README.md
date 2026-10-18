# 论坛社区（community）域卡

> 状态：**P2-28 ~ P2-31 已实现**。覆盖帖子列表/详情/发帖/回帖/点赞、金句列表与收藏。
> E6 `forum.posted` 由后端按 post id 幂等上报；前端仅登记契约。

## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| `.vtj/vue/forum.vue`（raw 手写页，仅 `<script>`） | `/forum` | PC | ✅ store 接入 + `mounted` 拉取（模板/DSL 未动） |
| `src/views/student/mobile/mobile_forum_create.vue` | `/mobile/forum/create`、`/tablet/forum/create` | 手机 / 平板 | ✅ `store.createPost` 接入 |
| `src/views/student/mobile/mobile_forum_detail.vue` | `/mobile/forum/:id`、`/tablet/forum/:id` | 手机 / 平板 | ✅ 详情 / 评论 / 点赞走 store |

## 2. 后端端点清单

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| GET | `/api/forum/posts` | `community/forum.py` | 帖子列表（`share_type` / `limit` / `offset`） |
| GET | `/api/forum/posts/{post_id}` | `community/forum.py` | 帖子详情（含完整正文） |
| POST | `/api/forum/posts` | `community/forum.py` | 发帖（Form：title/content/share_type/tags/attachments） |
| DELETE | `/api/forum/posts/{post_id}` | `community/forum.py` | 软删除（本人或管理员） |
| POST | `/api/forum/posts/{post_id}/like` | `community/forum.py` | 帖子点赞切换 |
| GET | `/api/forum/posts/{post_id}/comments` | `community/forum.py` | 评论列表 |
| POST | `/api/forum/posts/{post_id}/comments` | `community/forum.py` | 回帖（Form：content/parent_comment_id） |
| POST | `/api/forum/comments/{comment_id}/like` | `community/forum.py` | 评论点赞切换 |
| GET | `/api/forum/my-posts` | `community/forum.py` | 我的帖子 |
| GET | `/api/forum/stats` | `community/forum.py` | 论坛统计 |
| GET | `/api/forum/users/{user_id}/public` | `community/forum.py` | 用户公开信息 |
| GET | `/api/quotes` | `community/quotes.py` | 金句列表（需登录） |
| GET | `/api/quotes/random` | `community/quotes.py` | 随机金句 |
| GET | `/api/quotes/quote/daily` | `community/quotes.py` | 每日金句 |
| POST | `/api/quotes/{quote_id}/favorite` | `community/quotes.py` | 数据库金句收藏切换 |
| POST | `/api/quotes/obsidian/{obsidian_source}/favorite` | `community/quotes.py` | Obsidian 金句收藏切换 |
| GET | `/api/quotes/favorites` | `community/quotes.py` | 我的金句收藏 |

> 路径全部沿用 `api_surface.json` 冻结口径；`/api/v1` 前缀未改，api.ts 显式置空 baseURL。

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading / error / initialized | 公共骨架 | 加载 / 错误 / 首次初始化 | 否 |
| ready（派生） | boolean | 已完成初始化且无错误 | 否 |
| posts / total / page / pageSize / shareType | 列表状态 | 论坛帖子分页 | 否 |
| hasMore / offset（派生） | boolean / number | offset 游标与是否还有下一页 | 否 |
| myPosts / myPostsTotal | array / number | 「我的帖子」卡片数据 | 否 |
| detail / detailLoading | Post \| null / boolean | 帖子详情 | 否 |
| comments / commentsTotal | array / number | 评论列表 | 否 |
| stats | object \| null | 论坛统计 | 否 |
| quotes / quotesTotal / quotesPage / quotesCategory | 金句列表状态 | 金句分页与分类 | 否 |
| quoteFavorites / quoteFavoritesTotal / dailyQuote | array / number / Quote | 收藏与每日金句 | 否 |
| submitting | boolean | 写操作进行中（重复提交防护） | 否 |

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| `forum.posted`（E6，后端） | 发帖创建成功；历史帖子首条回帖 | `{ post_id, action: 'created' \| 'commented' }` | ✅ 已接入；按 post id 幂等，点赞/删除不上报 |

前端事件总线：本域不发布事件（无跨域消费方）。

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| （无） | — | — | — |

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 后端模块测试 | `backend/tests/test_community_module.py` | ✅ 发帖幂等 / 回帖不重复 / 点赞不发 / 金句常量不回归 |
| 前端单元测试 | `src/modules/community/__tests__/store.spec.ts` | ✅ 分页 / 空态 / 错误 / 发帖失败提示 / 重复提交防护 |
| 外壳冒烟测试 | `src/modules/__tests__/shells.spec.ts` | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | 论坛列表、详情、发帖、评论、点赞、我的帖子 | 待人工验收 |
| 平板 | 复用手机发帖/详情页，布局与路由正常 | 待人工验收 |
| 手机 | 发帖、详情、评论、点赞正常 | 待人工验收 |

## 附：raw 页面约束

`.vtj/vue/forum.vue` 为 `raw: true`，本阶段仅修改 `<script>`（store 接入、`mounted` 拉取），
未改 `<template>`、未调用 `vtj_sync_vue_to_dsl`。受 Options API 提取器限制，
`vtj_check_consistency` 可能报 `methods_extra_in_dsl`，属已知限制。
