# 成就成长（growth）域卡

> 由 scripts/scaffold-module.mjs 生成（P1-13）。当前状态：**已实现**（P2-51~56）。
> 本域是成就枢纽：**禁止 import 任何业务域**，只允许经事件总线消费后端行为事件。

## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| `src/views/student/shared/achievements.vue` | `/achievements` | PC / 三端响应式 | 已接入 store |
| `src/views/student/mobile/mobile_achievements.vue` | `/mobile/achievements` | 手机 | 已接入 store |

## 2. 后端端点清单

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| GET | `/api/achievements` | growth/achievements | 成就墙（分类 + 已获得 + 实时进度） |
| GET | `/api/achievements/earned` | growth/achievements | 已获得成就列表 |
| GET | `/api/achievements/progress` | growth/achievements | 未获得成就实时进度 |
| GET | `/api/goals/` | growth/goals | 学习目标列表 |
| GET | `/api/tasks/overview` | growth/tasks | 每日 / 随机 / 周常任务总览 |

> `/api/achievements*`、`/api/goals*`、`/api/tasks*` 均挂在根路径，`api.ts`
> 通过 `baseURL: ''` 覆盖统一客户端前缀，不新建 axios 实例。

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading | boolean | 是否正在加载 | 否 |
| error | string \| null | 最近一次错误信息 | 否 |
| initialized | boolean | 是否完成首次初始化 | 否 |
| wall | AchievementWall \| null | 成就墙原始快照 | 否 |
| goals | GoalItem[] | 学习目标 | 否 |
| taskOverview | TaskOverview \| null | 任务中心快照 | 否 |
| lastUnlocked | AchievementItem[] | 最近一次增量刷新新解锁的成就 | 否 |
| ready（派生） | boolean | 已完成初始化且无错误 | 否 |
| achievementGroups（派生） | AchievementGroup[] | 按分类分组 + 组内/单条进度百分比 | 否 |
| goalsWithProgress（派生） | GoalItem[] | 目标进度百分比 | 否 |
| dailyTasks / randomTasks / weeklyTasks（派生） | DecoratedTask[] | 任务进度百分比 | 否 |
| taskGroups（派生） | TaskGroup[] | 三类任务分组 | 否 |

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| `growth:achievement-unlocked` | 增量刷新发现成就由未获得变为已获得 | `{ achievementId, title, unlockedAt }` | 已接入 |

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| `wrong-questions:changed` | 错题集 / 练习提交 | 成就页仅增量刷新成就墙 | 已接入 |

后端 E1–E10 共 11 个 trigger_type 值由 `achievement_judge` 消费：
`practice.submit` / `practice.record.created` / `paper.completed` /
`wrong.reviewed` / `note.created` / `favorite.added` / `forum.posted` /
`news.read` / `material.opened` / `shop.purchased` / `checkin.done`。

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 后端判据 / 奖励 / 消费者 | `backend/tests/test_achievement_judge.py` | 已创建 |
| 前端单元测试 | `src/modules/growth/__tests__/store.spec.ts` | 已创建 |
| 外壳冒烟测试 | `src/modules/__tests__/shells.spec.ts` | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | 成就墙可进入、分类与进度正确 | 待人工验收 |
| 平板 | 布局与路由正常 | 待人工验收 |
| 手机 | 独立壳层返回键、成就墙加载正常 | 待人工验收 |
