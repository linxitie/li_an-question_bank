# 错题集（wrongbook）域卡

> 状态：**P2-13..P2-16 已实现**。错题由 ③ 答题练习（E12）写入，本域负责列表、掌握度流转、重练与斩题。

## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| `.vtj/vue/wrong_questions.vue`（raw 手写页） | `/wrong-questions` | PC | ✅ store 接入 + 事件订阅（仅改 `<script>`，模板未动） |
| `src/views/student/mobile/mobile_wrong_questions.vue` | `/mobile/wrong-questions` | 手机 | ✅ store 接入 + 事件订阅 |
| `src/views/student/mobile/mobile_wrong_review.vue` | `/mobile/wrong-review` | 手机 | ✅ 队列/提交走本域 api，提交后发布事件 |
| 平板 | — | 平板 | 复用手机页（R12，不新建重复副本） |

## 2. 后端端点清单

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| GET | `/api/wrong-questions` | 读 | 列表，参数 `subject_id` / `collection_type` / `page` / `page_size` |
| GET | `/api/wrong-questions/{wrong_id}/detail` | 读 | 错题完整详情（只读） |
| GET | `/api/wrong-questions/subcategories` | 读 | 子科目统计 |
| GET | `/api/wrong-questions/review/queue` | 读 | 重练队列，参数 `mode` / `subject_id` / `subcategory` / `limit` |
| GET | `/api/wrong-questions/zhanti/list` | 读 | 斩题列表（含倒计时） |
| GET | `/api/wrong-questions/zhanti/expiring` | 读 | 2 天内过期提醒 |
| PUT | `/api/wrong-questions/{wrong_id}/mastery` | 写 | 掌握度流转（`UNMASTERED` / `PARTIAL` / `MASTERED`） |
| PUT | `/api/wrong-questions/{wrong_id}/chop` | 写 | 斩题（消灭错题，10 天后自动删除） |
| POST | `/api/wrong-questions/{wrong_id}/unchop` | 写 | 取消斩题恢复错题 |
| POST | `/api/wrong-questions/review/submit` | 写 | 批量重练判分（答对 3 次自动斩题） |
| POST | `/api/wrong-questions/collect` | 写 | 收录错题（错误次数累加逻辑保持） |
| DELETE | `/api/wrong-questions/{wrong_id}` | 写 | 软删除（`status=0`） |

> 路径全部沿用 `api_surface.json` 冻结口径，本阶段未新增/修改任何路径。

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading / loadingMore | boolean | 首屏 / 翻页加载 | 否 |
| error | string \| null | 最近一次错误信息 | 否 |
| initialized | boolean | 是否完成首次初始化 | 否 |
| ready（派生） | boolean | 已完成初始化且无错误 | 否 |
| items | WrongQuestionItem[] | 已加载错题 | 否 |
| visibleItems（派生） | WrongQuestionItem[] | 应用掌握度/关键字筛选后的错题 | 否 |
| total / pageSize / loadedPages | number | 分页状态 | 否 |
| filters | { subjectId, masteryLevel, keyword } | 学科走后端参数，掌握度/关键字本地过滤 | 否 |
| isEmpty / hasMore（派生） | boolean | 空态 / 是否还有下一页 | 否 |

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| `wrong-questions:changed` | 掌握度流转 / 斩题成功后（前端 store） | `{ action: 'mastered' \| 'removed' \| 'reviewed', source: 'wrongbook' }` | ✅ 已接入 |
| `wrong.reviewed`（E4） | 后端掌握度流转或斩题成功、且该错题首次流转时 | `wrong_id / question_id / subject_id / mastery_level / error_count / action` | ✅ 已接入；同一错题幂等重放不发 |

> E4 去重键为 `(user_id, wrong_id)`：同一错题第二次流转（含斩题后再次标记掌握）不再发事件；
> 只读端点（列表 / 详情 / 队列 / 斩题列表）一律不发。

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| `wrong-questions:changed` | ③ 答题练习 / 本域 | 已打开的错题页增量拉取（`bindRefresh`，同轮重复事件合并为一次） | ✅ 已接入（加速器；页面 `onMounted` 仍全量拉取） |

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 后端测试 | `backend/tests/test_wrongbook_module.py` | ✅ E4 发布 / 幂等重放 / 只读不发 / 斩题去重 / E12 答错入库可见 |
| 单元测试 | `src/modules/wrongbook/__tests__/store.spec.ts` | ✅ 列表 / 空态 / 错误 / 分页 / 筛选保持 / 事件幂等 / 流转 / 重练跳转 |
| 外壳冒烟测试 | `src/modules/__tests__/shells.spec.ts` | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | 错题列表加载、斩题、复习提交、斩题倒计时 | 待人工验收 |
| 平板 | 复用手机页，布局与路由正常 | 待人工验收 |
| 手机 | 分类筛选、斩题、恢复、复习提交后返回列表刷新 | 待人工验收 |
