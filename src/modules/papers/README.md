# 组卷与历年试卷（papers）域卡

> 状态：**P2-17..P2-23 已实现**。教师建卷 → 提交审批 → 管理员发布 → 学生可见；学生端强制只读已发布试卷。

## 1. 负责页面清单

| 页面文件 | 路由 | 设备端 | 状态 |
|---|---|---|---|
| `.vtj/vue/student_papers.vue`（raw 手写页） | `/student-papers` | PC | ✅ store 接入 + 事件订阅（仅改 `<script>`，模板未动） |
| `src/views/student/mobile/mobile_student_papers.vue` | `/mobile/student-papers` | 手机 | ✅ store 接入 + `onMounted` 拉取 + 事件订阅 |
| 平板 | — | 平板 | 复用手机页（R12，不新建重复副本） |

## 2. 后端端点清单

| 方法 | 路径 | 归属 | 说明 |
|---|---|---|---|
| POST | `/api/papers/` | 写 | 教师建卷，固定落 `DRAFT` |
| GET | `/api/papers/{paper_id}` | 读 | 详情；学生仅 `PUBLISHED` |
| PUT | `/api/papers/{paper_id}` | 写 | 仅 `DRAFT` 可编辑 |
| POST | `/api/papers/{paper_id}/questions` | 写 | 仅 `DRAFT` 可加题 |
| DELETE | `/api/papers/{paper_id}/questions/{question_id}` | 写 | 仅 `DRAFT` 可移题 |
| POST | `/api/papers/{paper_id}/submit` | 写 | 教师提交审批：`DRAFT→PENDING` |
| POST | `/api/papers/{paper_id}/approve` | 写 | 管理员审批：`PENDING→APPROVED\|DRAFT` |
| POST | `/api/papers/{paper_id}/publish` | 写 | 管理员发布：`APPROVED→PUBLISHED` |
| GET | `/api/papers/list` | 读 | 列表；学生强制仅 `PUBLISHED` |
| POST | `/api/smart-exam/{paper_id}/submit` | 写 | 整卷提交，成功后发布 E3 `paper.completed` |

> 路径全部沿用 `api_surface.json` 冻结口径，本阶段未新增/修改任何路径。

## 3. store 状态契约

| 字段 | 类型 | 说明 | 持久化 |
|---|---|---|---|
| loading / loadingMore | boolean | 首屏 / 翻页加载 | 否 |
| error | string \| null | 最近一次错误信息 | 否 |
| initialized | boolean | 是否完成首次初始化 | 否 |
| ready（派生） | boolean | 已完成初始化且无错误 | 否 |
| items | PaperItem[] | 已加载的已发布试卷 | 否 |
| total / pageSize / loadedPages | number | 分页状态 | 否 |
| filters | { subjectId, examType, keyword } | 后端筛选参数 | 否 |
| isEmpty / hasMore（派生） | boolean | 空态 / 是否还有下一页 | 否 |

## 4. 发布事件清单

| 事件 / trigger_type | 触发时机 | 载荷 | 状态 |
|---|---|---|---|
| `paper.completed`（E3） | 智能组卷整卷提交成功后，每次整卷仅 1 次 | `paper_id / record_id / exam_record_id / total_score / max_score` | ✅ 已接入；重复提交返回既有结果且不重发 |
| `data-changed`（后端 WebSocket） | 管理员发布试卷成功后 | `{domain:'exam', type:'paper.published', id:paper_id}` | ✅ 已接入；未发布状态不推送 |

## 5. 订阅事件清单

| 事件 / trigger_type | 来源域 | 处理动作 | 状态 |
|---|---|---|---|
| `papers:data-changed` | 后端 WebSocket 桥接 | 已打开页面增量刷新（`bindRefresh`） | ✅ 已接入（加速器；页面 `onMounted` 仍全量拉取） |

## 6. 测试文件位置

| 类型 | 路径 | 状态 |
|---|---|---|
| 后端测试 | `backend/tests/test_paper_publish_flow.py` | ✅ 状态机全链路 / 越权拒绝 / 学生仅见已发布 / E3 单次 / 重复回调幂等 / 发布推送 |
| 单元测试 | `src/modules/papers/__tests__/store.spec.ts` | ✅ 列表 / 空态 / 错误 / 分页去重 / 筛选 / 事件刷新 / 重置 |
| 外壳冒烟测试 | `src/modules/__tests__/shells.spec.ts` | P1-33 覆盖 |

## 7. 三端手工验收清单

| 端 | 验收项 | 结果 |
|---|---|---|
| PC | 已发布试卷加载、筛选、搜索、预览 | 待人工验收 |
| 平板 | 复用手机页，布局与路由正常 | 待人工验收 |
| 手机 | 已发布试卷加载、点击进入答题 | 待人工验收 |
