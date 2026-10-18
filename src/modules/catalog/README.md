# 题库浏览（catalog）域卡

> P2-71 ~ P2-75 已完成：**已实现**（题目列表 / 筛选 / 详情，只读）。
> ⑱⑲⑳（联考小智 / 院校联考机考系统 / 小模考）**未开发，入口归 ②**，仅保留提示。

## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| `.vtj/vue/question_bank.vue`（raw，仅改 `<script>`） | `/page/question_bank` | PC | 已接入 store（`mounted` 拉取列表） |
| `.vtj/vue/tablet_question_bank.vue`（raw） | 平板题库路由 | 平板 | 复用现有页面，**不新建副本**（R12）；本阶段未改脚本 |
| `.vtj/vue/mobile_question_bank.vue`（raw） | 手机题库路由 | 手机 | 复用现有页面，**不新建副本**（R12）；本阶段未改脚本 |

> ⑱ 联考小智 / ⑲ 院校联考机考系统 / ⑳ 小模考：三个入口均**未开发**、归属本域登记，
> 页面中仅保留提示，无 `emitEvent`、无新增端点调用、无文件所有权声明（P2-74 核对）。

## 2. 后端端点清单

> 仅登记本域实际使用的**只读**端点；`questions.py` 冻结口径为 21 个端点 / 1 个 router 实例，
> P2-72 复核结果为 **removed=0 / modified=0**，本阶段未修改任何后端代码。

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| GET | `/api/questions/` | catalog/questions.py | 题目列表；支持 `subject_id` / `type_id` / `point_id` / `difficulty`(1-5) / `audit_status` / `year` / `keyword` / `page` / `page_size`(1-100)；固定只返回 `status=1` |
| GET | `/api/questions/{question_id}` | catalog/questions.py | 题目详情；只读返回，副作用仅为 `exam_frequency += 1`，不发布用户行为事件 |

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading | boolean | 是否正在加载 | 否 |
| error | string \| null | 最近一次错误信息 | 否 |
| initialized | boolean | 是否完成首次初始化 | 否 |
| ready（派生） | boolean | 已完成初始化且无错误 | 否 |
| filters | CatalogFilters | 当前筛选（科目 / 题型 / 知识点 / 难度 / 审核状态 / 年份 / 关键词） | 否 |
| items | CatalogQuestion[] | 当前页题目列表 | 否 |
| total / page / pageSize | number | 服务端分页状态（pageSize 上限 100） | 否 |
| selected | CatalogQuestion \| null | 当前打开的题目详情 | 否 |
| isEmpty / totalPages / hasPrevPage / hasNextPage（派生） | — | 空态与分页派生值 | 否 |

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| （无） | — | 本域无成就入边，不发布前端事件 | — |
| （无） | — | 不调用 `record_user_action()`，无 trigger_type 上报 | — |
| （无） | — | ⑱⑲⑳ 未开发，不发布任何事件 | — |

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| （无） | — | 本域不订阅任何事件 | — |

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 后端单测 | `backend/tests/test_catalog_module.py` | 已创建（筛选 / 分页 / 详情 / 参数校验 / 软删除过滤） |
| 前端单测 | `src/modules/catalog/__tests__/store.spec.ts` | 已创建（加载 / 空态 / 错误 / 分页 / 详情） |
| 外壳冒烟测试 | `src/modules/__tests__/shells.spec.ts` | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | 题库页进入正常，`mounted` 成功拉取第一页列表；⑱⑲⑳ 仍提示未开发 | 待验收 |
| 平板 | 复用现有平板题库页，路由与布局正常；未新建副本 | 待验收 |
| 手机 | 复用现有手机题库页，路由与布局正常；未新建副本 | 待验收 |

## 附：「功能还未开发」说明

本域只读浏览（列表 / 筛选 / 详情）已在 P2 阶段实现；三端入口提示待后续页面模板改造时移除。
⑱⑲⑳ 三个入口**仍未开发**，文案与交互保持原样，后续需求必须走独立 spec → plan → implement。
