# 考试日历（calendar）域卡

> P2-63 ~ P2-65 已完成：**已实现**（列表 / 省份筛选 / 月份分组派生 / 空态）。
> 本域**无事件进出**：不发布、不订阅前端事件，也不上报行为 trigger_type。

## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| `.vtj/vue/exam_calendar.vue`（raw 手写页） | `/page/exam_calendar` | PC | P2 已实现 api + store；raw 页仅允许改 `<script>`，本阶段未改动，**页面接入待 P3 验收确认** |
| `src/views/student/mobile/mobile_calendar.vue`（手写） | `/mobile/calendar`、`/tablet/calendar` | 手机 / 平板 | 已接入 store + `onMounted` 拉取（模板零改动） |

## 2. 后端端点清单

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| GET | `/api/calendar/exams` | `content/calendar.py` | 考试日历列表（`limit` 1–50、`offset` 分页、`province` 筛选） |
| GET | `/api/calendar/latest` | `content/calendar.py` | 最新一条考试信息（是否更新判断） |

> 路径沿用 `api_surface.json` 冻结口径；与客户端默认 baseURL `/api/v1` 不同，api.ts 显式置空 baseURL。

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading | boolean | 是否正在加载 | 否 |
| error | string \| null | 最近一次错误信息 | 否 |
| initialized | boolean | 是否完成首次初始化 | 否 |
| ready（派生） | boolean | 已完成初始化且无错误 | 否 |
| items | ExamCalendarItem[] | 当前列表 | 否 |
| total | number | 后端返回总数 | 否 |
| hasMore | boolean | 是否还有下一页 | 否 |
| province | string | 当前省份筛选（空为全部） | 否 |
| isEmpty（派生） | boolean | 加载完成且确实没有数据 | 否 |
| monthGroups（派生） | CalendarMonthGroup[] | 按月份升序分组；缺失月份用 `exam_date` 回退，「日期待定」沉底 | 否 |

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| （无） | — | 本域不发布前端事件，也不上报 trigger_type | — |

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| （无） | — | 本域不订阅任何事件，页面 `onMounted` 主动拉取 | — |

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 前端单元测试 | `src/modules/calendar/__tests__/store.spec.ts` | 已创建（列表 / 分组 / 空态 / 错误 / 取消 / 零事件） |
| 外壳冒烟测试 | `src/modules/__tests__/shells.spec.ts` | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | `/page/exam_calendar` 页面接入 store | 待 P3 验收（raw 页未动） |
| 平板 | `/tablet/calendar` 复用手机页，列表 / 分组正常 | 待人工验收 |
| 手机 | `/mobile/calendar` 列表、展开详情、空态正常 | 待人工验收 |

## 附：raw 页面约束

`.vtj/vue/exam_calendar.vue` 为 `raw: true`，本阶段仅完成 api + store，未改其 `<template>` / `<script>`，
也未调用 `vtj_sync_vue_to_dsl`。页面接入策略见 P3 验收安排。
