# 笔记与收藏（notes）域卡

> 状态：**已实现**（P2-24~27 笔记+收藏域改造完成）。

> P2-24 ~ P2-27 已落地。本域覆盖笔记 CRUD 与收藏增删查，三端页面共用同一 store。

## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| `.vtj/vue/notes.vue`（raw，仅 script 接入） | `/notes` | PC | 已接入 |
| `.vtj/vue/favorites.vue`（raw，仅 script 接入） | `/favorites` | PC | 已接入 |
| `src/views/student/mobile/mobile_notes.vue` | `/mobile/notes`、`/tablet/notes` | 手机 / 平板 | 已接入 |
| `src/views/student/mobile/mobile_favorites.vue` | `/mobile/favorites`、`/tablet/favorites` | 手机 / 平板 | 已接入 |

## 2. 后端端点清单

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| GET | `/api/notes` | `personal/notes.py` | 笔记列表（note_type=all/question/news） |
| GET | `/api/notes/stats` | `personal/notes.py` | 笔记数量统计 |
| GET | `/api/notes/news` | `personal/notes.py` | 新闻笔记列表 |
| GET | `/api/notes/question` | `personal/notes.py` | 典题笔记列表 |
| GET | `/api/notes/question/{question_id}` | `personal/notes.py` | 题目详情（笔记弹层） |
| POST | `/api/notes` | `personal/notes.py` | 创建/更新笔记（按 type+id 唯一） |
| PUT | `/api/notes/{note_id}` | `personal/notes.py` | 更新笔记 |
| DELETE | `/api/notes/{note_id}` | `personal/notes.py` | 删除笔记 |
| GET | `/api/collection` | `personal/collection.py` | 收藏列表 |
| GET | `/api/collection/stats` | `personal/collection.py` | 收藏数量统计 |
| GET | `/api/collection/news-favorites` | `personal/collection.py` | 新闻/金句收藏 |
| GET | `/api/collection/question-favorites` | `personal/collection.py` | 典题收藏 |
| POST | `/api/collection/favorite` | `personal/collection.py` | 添加/取消收藏（切换） |
| DELETE | `/api/collection/{fav_id}` | `personal/collection.py` | 删除收藏（q_ / n_ 复合 ID） |

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading | boolean | 是否正在加载 | 否 |
| error | string \| null | 最近一次错误信息 | 否 |
| initialized | boolean | 是否完成首次初始化 | 否 |
| ready（派生） | boolean | 已完成初始化且无错误 | 否 |
| notes / notesTotal | NoteItem[] / number | 笔记列表与总数 | 否 |
| stats / collectionStats | object \| null | 两类统计 | 否 |
| newsFavorites / questionFavorites | array | 两类收藏 | 否 |
| submitting | boolean | 写操作进行中（防重复提交） | 否 |

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| `note.created`（后端） | 笔记新建成功后 | 无 | 已接入（仅创建分支，更新/删除不发） |
| `favorite.added`（后端） | 收藏新建成功后 | 无 | 已接入（典题/新闻共用，取消收藏不发） |

前端事件总线：本域不发布事件（无跨域消费方）。

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| （无） | — | — | — |

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 前端单元测试 | `src/modules/notes/__tests__/store.spec.ts` | 已创建 |
| 后端模块测试 | `backend/tests/test_notes_collection_module.py` | 已创建 |
| 外壳冒烟测试 | `src/modules/__tests__/shells.spec.ts` | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | 笔记/收藏列表可加载，分页与取消收藏正常 | 待人工验收 |
| 平板 | 复用手机页，列表与取消收藏正常 | 待人工验收 |
| 手机 | 列表、详情弹层、编辑保存、删除、取消收藏正常 | 待人工验收 |

## 附：raw 页面约束

`.vtj/vue/notes.vue` 与 `.vtj/vue/favorites.vue` 的 `raw: true`，本次仅改 `<script>`，
未改 `<template>`、未同步 DSL。`vtj_check_consistency` 对 raw 页面会报
`methods_extra_in_dsl`（提取器不识 Options API），未改动的 raw 页面同样如此，属已知限制。
