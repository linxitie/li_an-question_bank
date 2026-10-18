# 成绩分析（analytics）域卡

> 状态：**已实现**（P2-57~P2-62）。本域只读，无成就入边；E13 向 ⑤ 提供薄弱点读能力。
> 方向是 ⑤ 读 ⑧（后端复用 `weakpoint_reader` 服务），不是 ⑧ 写 ⑤。

## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| `.vtj/vue/score_analysis.vue`（仅改 `<script>`） | `/page/score_analysis` | PC | ✅ store 接入 + mounted 拉取 |
| `src/views/student/mobile/mobile_score_analysis.vue` | `/mobile/score-analysis` | 手机 | ✅ store 接入 + `onMounted` 拉取 |
| 平板 | — | 平板 | 复用手机页（R12，不新建重复副本） |

## 2. 后端端点清单

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| GET | `/api/exam-records/trend` | exam_records | 得分趋势（`exam_type` / `limit`） |
| GET | `/api/stats/type-mastery` | exam/stats | 题型/知识点掌握度 |
| GET | `/api/stats/dashboard` | exam/stats | 综合概览，含 `weakPoints` 薄弱点数组 |
| GET | `/api/papers/list?recommend=true` | catalog/paper_generation | E13 推荐位：按薄弱考点筛选；无薄弱点时退化为全量 |

> `/api/stats` 11 个既有端点路径与响应外壳未变；`weakPoints` 是 dashboard 的附加字段。
> `weakpoint_reader.py` 不 import 任何 `app.api.*` 模块。

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading | boolean | 是否正在加载 | 否 |
| error | string \| null | 最近一次错误信息 | 否 |
| initialized | boolean | 是否完成首次初始化 | 否 |
| trend | ScoreTrend | 得分趋势快照 | 否 |
| mastery | KnowledgeMasteryItem[] | 知识点掌握度 | 否 |
| weakPoints | WeakPoint[] | 薄弱点（考点/正确率/题量） | 否 |
| ready（派生） | boolean | 已完成初始化且无错误 | 否 |
| hasWeakPoints（派生） | boolean | 是否存在薄弱点 | 否 |
| weakPointNames（派生） | string[] | 薄弱考点名称 | 否 |
| weakestPoint（派生） | WeakPoint \| null | 正确率最低的考点 | 否 |
| masteryAverage（派生） | number | 按题量加权的掌握度 | 否 |
| trendDelta（派生） | number | 末次与首次正确率差值 | 否 |
| isEmpty（派生） | boolean | 三块数据均为空 | 否 |

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| — | 本域只读，不发布任何事件 | — | 已声明 |

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| — | 本域不订阅前端事件；页面进入即 API 全量拉取 | — | 已声明 |

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 后端 | `backend/tests/test_analytics_module.py` | ✅ 薄弱点结构 / dashboard 输出 / E13 筛选与退化 |
| 前端单元测试 | `src/modules/analytics/__tests__/store.spec.ts` | ✅ 加载 / 空态 / 错误态 / 分区加载 / reset |
| 外壳冒烟测试 | `src/modules/__tests__/shells.spec.ts` | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | 趋势、掌握度、薄弱点展示正常 | 待人工验收 |
| 平板 | 复用手机页，布局与路由正常 | 待人工验收 |
| 手机 | 三 tab 数据加载与图表正常 | 待人工验收 |
