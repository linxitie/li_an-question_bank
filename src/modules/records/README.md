# 练习记录（records）域卡

> 状态：**P2-09..P2-12 已实现**。记录由 ③ 答题练习写入，本域只读展示、筛选与统计，不参与判分。

## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| `src/views/student/mobile/mobile_history.vue` | `/mobile/history` | 手机 | ✅ 已接入 records store |
| PC 练习记录页 | — | PC | ⏳ 待建（`src/views/student/pc/` 与 `.vtj/vue/` 均无记录页；按 P2-11 不新建 `.vtj` 页） |
| 平板练习记录页 | — | 平板 | ⏳ 待建（按 R12 复用手机页，不新建重复副本） |

## 2. 后端端点清单

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| GET | `/api/practice/records` | ③ 写入 / ④ 读取 | 练习记录列表，参数 `limit`(1-50) / `offset` / `subject_id`，返回 `total/items/daily_stats` |
| GET | `/api/stats/` | ⑧ 统计 | 记录侧汇总：`totalQuestions` / `accuracyRate` / `totalStudyHours` |
| GET | `/api/stats/practice-trend` | ⑧ 统计 | 练习趋势，参数 `days`(7-30) |
| GET | `/api/exam-records/*` | ④ 读取 | 成绩记录 8 个端点，均为只读；本域不新增/修改路径，无删除端点（`api_surface.json` 冻结） |

> `PracticeRecord` 无独立详情端点；列表项已携带 `question_content` / `user_answer` / `correct_answer`，
> `fetchRecordsDetail()` 通过分页查找实现。

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading | boolean | 是否正在加载首页 | 否 |
| loadingMore | boolean | 是否正在加载下一页 | 否 |
| error | string \| null | 最近一次错误信息 | 否 |
| initialized | boolean | 是否完成首次初始化 | 否 |
| ready（派生） | boolean | 已完成初始化且无错误 | 否 |
| records | RecordsItem[] | 已加载记录 | 否 |
| filteredRecords（派生） | RecordsItem[] | 应用筛选后的记录 | 否 |
| dailyStats | RecordsDailyStat[] | 每日统计 | 否 |
| total | number | 后端记录总数 | 否 |
| offset / pageSize | number | 游标分页状态 | 否 |
| filters | RecordsFilters | 学科（后端）+ 对错/来源/关键字（已加载数据） | 否 |
| stats | RecordsStats \| null | 统计概览 | 否 |
| trend / trendDays | RecordsTrendPoint[] / number | 练习趋势 | 否 |
| isEmpty / hasMore（派生） | boolean | 空态 / 是否还有下一页 | 否 |

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| `practice.record.created`（E2） | 练习记录创建成功后（③ 提交判分落库后由 `practice_grading` 发布） | `session_id/source/total/correct/record_ids/time_spent/practice_date` | ✅ 已接入；同会话重复提交不重复发布 |

> 实现归属说明：④ 的 `/api/exam-records` 全部为只读端点，没有创建路径。
> E2 的实际发布点落在唯一写入方 `backend/app/services/practice_grading.py`（③ 提交服务，事务提交后发布），
> 列表/详情/统计等只读端点一律不发事件。

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| `wrong-questions:changed` | ③ 答题练习 | 已打开的记录页增量刷新（`recordsStore.bindRecordsRefresh`） | ✅ 已接入（加速器；页面 `onMounted` 仍全量拉取） |

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 后端测试 | `backend/tests/test_exam_records_module.py` | ✅ E2 发布 / 会话去重 / 只读端点不发事件 / 路由面 |
| 单元测试 | `src/modules/records/__tests__/store.spec.ts` | ✅ 列表 / 空态 / 错误 / 游标分页 / 筛选 / 事件刷新 |
| 外壳冒烟测试 | `src/modules/__tests__/shells.spec.ts` | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | 入口可进入，未开发提示正确 | 未验收（PC 记录页待建） |
| 平板 | 布局与路由正常，未开发提示正确 | 未验收（复用手机页待接入） |
| 手机 | 列表 / 统计 / 趋势加载，加载更多，提交后刷新 | 待人工验收 |

