# 招考信息（recruitment）域卡

> P2-66 ~ P2-68 已完成：**已实现**（分类列表 / 分类筛选 / 详情 / 空态）。
> 本域**无事件进出**：不发布、不订阅前端事件，也不上报行为 trigger_type。

## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| `.vtj/vue/recruitment_info.vue`（raw 手写页） | `/page/recruitment_info` | PC | P2 已实现 api + store；raw 页仅允许改 `<script>`，本阶段未改动，**页面接入待 P3 验收确认** |
| `src/views/student/mobile/mobile_recruitment.vue`（手写） | `/mobile/wrong-questions`、`/tablet/wrong-questions`（现有路由复用） | 手机 / 平板 | 已接入 store，保留统一刷新内核（模板零改动） |

## 2. 后端端点清单

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| GET | `/api/recruitment` | `content/recruitment.py` | 招考列表；按分类分组返回 `items: Record<分类, 条目[]>`，每类 `limit` 1–50 |
| GET | `/api/recruitment/categories` | `content/recruitment.py` | 招考分类列表 |
| GET | `/api/recruitment/{id}` | `content/recruitment.py` | 招考详情（含 HTML 正文 / 联系方式；累加 `view_count`） |

> 路径沿用 `api_surface.json` 冻结口径；与客户端默认 baseURL `/api/v1` 不同，api.ts 显式置空 baseURL。

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading | boolean | 是否正在加载 | 否 |
| error | string \| null | 最近一次错误信息 | 否 |
| initialized | boolean | 是否完成首次初始化 | 否 |
| ready（派生） | boolean | 已完成初始化且无错误 | 否 |
| categories | string[] | 后端分类顺序 | 否 |
| items | Record<string, RecruitmentItem[]> | 按分类分组的条目 | 否 |
| activeCategory | string | 当前分类（本地筛选） | 否 |
| meta | RecruitmentMeta \| null | 更新时间 / 数据源等元信息 | 否 |
| detail / detailLoading | RecruitmentItem \| null / boolean | 当前打开的详情 | 否 |
| currentItems（派生） | RecruitmentItem[] | 当前分类下的条目 | 否 |
| isEmpty（派生） | boolean | 加载完成且当前分类无数据 | 否 |
| total / categoryCount（派生） | number | 条目总数 / 分类数 | 否 |

> 后端按分类各返回 `limit` 条，不提供 offset 分页；分类 Tab 即筛选维度，**无客户端分页**。

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| （无） | — | 本域不发布前端事件，也不上报 trigger_type | — |

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| （无） | — | 本域不订阅事件总线；页面沿用 `src/utils/recruitmentRefresh` 的 `__VTJ_SYNC__` 刷新内核（非事件总线契约） | — |

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 前端单元测试 | `src/modules/recruitment/__tests__/store.spec.ts` | 已创建（分类 / 筛选 / 详情 / 空态 / 错误 / 取消 / 零事件） |
| 外壳冒烟测试 | `src/modules/__tests__/shells.spec.ts` | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | `/page/recruitment_info` 页面接入 store | 待 P3 验收（raw 页未动） |
| 平板 | 复用手机页，分类 Tab 与列表正常 | 待人工验收 |
| 手机 | 分类切换、展开详情、空态正常 | 待人工验收 |

## 附：raw 页面约束

`.vtj/vue/recruitment_info.vue` 为 `raw: true`，本阶段仅完成 api + store，未改其 `<template>` / `<script>`，
也未调用 `vtj_sync_vue_to_dsl`。页面接入策略见 P3 验收安排。
