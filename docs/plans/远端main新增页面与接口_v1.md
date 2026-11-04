# 远端 main 新增页面与接口 v1

> 自动生成（脚本见本次提交说明）：以 `git worktree` 检出三个快照，分别导出 `openapi()` 与路由表后取差集
> 基线：`da218d1`（2026-10-26 老 main）→ `8f03a7d`（合并前本地 main）→ `89363f5`（当前远端 main）

## 一、概览

| 快照 | 说明 | 接口操作 | 路径 | 页面（有组件） |
|---|---|---|---|---|
| `da218d1` | 2026-10-26 老 main | 349 | 311 | 92 |
| `8f03a7d` | 合并前本地 main（备考资料线） | 373 | 331 | 98 |
| `89363f5` | 当前远端 main | **462** | **414** | **105** |

| 差集 | 新增接口 | 删除接口 | 新增页面 | 删除页面 |
|---|---|---|---|---|
| 相对老 main（`da218d1`） | **113** | 0 | **15** | 2 |
| 相对合并前本地 main（`8f03a7d`） | **95** | 6 | **11** | 4 |

> 说明：相对老 main 的 113 个新接口 = 远端线新增（模块4/7、论坛治理、新闻、F3 等）+ 本地线的备考资料接口；相对合并前本地 main 的 95 个新接口 = 全部来自远端那条线。

## 二、新增页面（相对老 main，15 条）

| 路径 | 来源 | 组件文件 |
|---|---|---|
| `/admin/forum` | 远端线 | [@/views/admin/admin_forum.vue](../../src/views/admin/admin_forum.vue) |
| `/admin/material-rules` | 本地线 | [@/views/admin/material_rules.vue](../../src/views/admin/material_rules.vue) |
| `/ai-assistant` | 远端线 | [$vtj/vue/ai_chat.vue](../../.vtj/vue/ai_chat.vue) |
| `/knowledge` | 远端线 | [$vtj/vue/knowledge_view.vue](../../.vtj/vue/knowledge_view.vue) |
| `/materials-preview` | 本地线 | [@/views/dev/MaterialsPreview.vue](../../src/views/dev/MaterialsPreview.vue) |
| `/materials/detail` | 本地线 | [@/views/pc/material_detail.vue](../../src/views/pc/material_detail.vue) |
| `/materials/upload` | 本地线 | [@/views/student/material_upload.vue](../../src/views/student/material_upload.vue) |
| `/memories` | 远端线 | [$vtj/vue/memories.vue](../../.vtj/vue/memories.vue) |
| `/mobile/news/timeline` | 远端线 | [@/views/student/shared/news_timeline.vue](../../src/views/student/shared/news_timeline.vue) |
| `/news` | 远端线 | [@/views/student/shared/news_timeline.vue](../../src/views/student/shared/news_timeline.vue) |
| `/news/:id` | 远端线 | [@/views/student/shared/news_detail.vue](../../src/views/student/shared/news_detail.vue) |
| `/profile-quiz` | 远端线 | [$vtj/vue/profile_quiz.vue](../../.vtj/vue/profile_quiz.vue) |
| `/study-plan` | 远端线 | [$vtj/vue/study_plan.vue](../../.vtj/vue/study_plan.vue) |
| `/tablet/news/timeline` | 远端线 | [@/views/student/shared/news_timeline.vue](../../src/views/student/shared/news_timeline.vue) |
| `/teacher/forum` | 远端线 | [@/views/teacher/teacher_forum.vue](../../src/views/teacher/teacher_forum.vue) |

## 三、新增接口（相对老 main，113 个）

### 模块7 联考小智/知识图谱/记忆/仪表盘（28）
> 来源：远端线（模块7）

| 方法 | 路径 |
|---|---|
| `DELETE` | `/api/agent/memory/{memory_id}` |
| `DELETE` | `/api/knowledge/relation/{rel_id}` |
| `DELETE` | `/api/llm/sessions/{session_id}` |
| `GET` | `/api/agent/memories` |
| `GET` | `/api/agent/tasks` |
| `GET` | `/api/agent/trajectory` |
| `GET` | `/api/knowledge/categories` |
| `GET` | `/api/knowledge/graph` |
| `GET` | `/api/knowledge/nodes` |
| `GET` | `/api/knowledge/nodes/{node_id}/detail` |
| `GET` | `/api/knowledge/relations` |
| `GET` | `/api/knowledge/stats` |
| `GET` | `/api/knowledge/vault` |
| `GET` | `/api/llm/context/assemble` |
| `GET` | `/api/llm/sessions` |
| `GET` | `/api/llm/sessions/{session_id}/messages` |
| `GET` | `/api/profile` |
| `GET` | `/api/profile/questions` |
| `POST` | `/api/agent/import-today` |
| `POST` | `/api/agent/run` |
| `POST` | `/api/knowledge/nodes` |
| `POST` | `/api/knowledge/nodes/{node_id}/approve` |
| `POST` | `/api/knowledge/nodes/{node_id}/reject` |
| `POST` | `/api/knowledge/relation` |
| `POST` | `/api/knowledge/relation/suggest` |
| `POST` | `/api/knowledge/vault/import` |
| `POST` | `/api/llm/sessions` |
| `POST` | `/api/profile/upsert` |

### 论坛与治理（37）
> 来源：远端线（论坛/P0）

| 方法 | 路径 |
|---|---|
| `DELETE` | `/api/admin/forum/comments/{comment_id}` |
| `DELETE` | `/api/admin/forum/comments/{comment_id}/purge` |
| `DELETE` | `/api/admin/forum/posts/{post_id}` |
| `DELETE` | `/api/admin/forum/posts/{post_id}/purge` |
| `DELETE` | `/api/forum/comments/{comment_id}` |
| `DELETE` | `/api/forum/comments/{comment_id}/reactions` |
| `DELETE` | `/api/forum/posts/{post_id}/reactions` |
| `DELETE` | `/api/forum/stickers/{sticker_id}` |
| `GET` | `/api/admin/forum/comments` |
| `GET` | `/api/admin/forum/moderation` |
| `GET` | `/api/admin/forum/posts` |
| `GET` | `/api/admin/forum/recycle` |
| `GET` | `/api/admin/forum/recycle/audit` |
| `GET` | `/api/forum/my-favorites` |
| `GET` | `/api/forum/my-likes` |
| `GET` | `/api/forum/stickers` |
| `GET` | `/api/notifications` |
| `GET` | `/api/post/search` |
| `GET` | `/api/post/stats` |
| `GET` | `/api/teacher/forum/posts` |
| `GET` | `/api/teacher/forum/posts/{post_id}/comments` |
| `POST` | `/api/admin/forum/comments/{comment_id}/restore` |
| `POST` | `/api/admin/forum/moderation/{moderation_id}/approve` |
| `POST` | `/api/admin/forum/moderation/{moderation_id}/reject` |
| `POST` | `/api/admin/forum/posts/{post_id}/restore` |
| `POST` | `/api/forum/comments/{comment_id}/reactions/{reaction_code}` |
| `POST` | `/api/forum/posts/{post_id}/favorite` |
| `POST` | `/api/forum/posts/{post_id}/reactions/{reaction_code}` |
| `POST` | `/api/forum/reports` |
| `POST` | `/api/forum/stickers` |
| `POST` | `/api/post/import` |
| `POST` | `/api/teacher/forum/comments/{comment_id}/hide` |
| `POST` | `/api/teacher/forum/posts/{post_id}/hide` |
| `PUT` | `/api/forum/comments/{comment_id}/pin` |
| `PUT` | `/api/forum/posts/{post_id}` |
| `PUT` | `/api/notifications/read-all` |
| `PUT` | `/api/notifications/{notification_id}/read` |

### 模块4 学习计划/目标/番茄/日历/成就（12）
> 来源：远端线（模块4）

| 方法 | 路径 |
|---|---|
| `DELETE` | `/api/plan/{plan_id}` |
| `GET` | `/api/achievements/name-bank/status` |
| `GET` | `/api/plan/current` |
| `GET` | `/api/plan/notifies` |
| `GET` | `/api/plan/today` |
| `GET` | `/api/plan/{plan_id}/tasks` |
| `POST` | `/api/achievements/admin` |
| `POST` | `/api/plan/adjust` |
| `POST` | `/api/plan/generate` |
| `POST` | `/api/plan/notify/{notify_id}/read` |
| `POST` | `/api/plan/task/{goal_id}/claim` |
| `POST` | `/api/plan/task/{goal_id}/toggle` |

### 备考资料（library）（16）
> 来源：本地线（备考资料模块）

| 方法 | 路径 |
|---|---|
| `DELETE` | `/api/materials/my/{material_id}` |
| `GET` | `/api/materials/admin/rules` |
| `GET` | `/api/materials/my` |
| `GET` | `/api/materials/shared` |
| `GET` | `/api/materials/taxonomy` |
| `PATCH` | `/api/materials/admin/rules/{rule_id}/toggle` |
| `POST` | `/api/materials/admin/cards/batch-image` |
| `POST` | `/api/materials/admin/rules` |
| `POST` | `/api/materials/my` |
| `POST` | `/api/materials/my/card` |
| `POST` | `/api/materials/my/upload` |
| `POST` | `/api/materials/{material_id}/adopt` |
| `POST` | `/api/materials/{material_id}/share` |
| `POST` | `/api/materials/{material_id}/unshare` |
| `PUT` | `/api/materials/admin/rules/{rule_id}` |
| `PUT` | `/api/materials/my/{material_id}` |

### 练习管理员与能力包（6）
> 来源：远端线（P0）

| 方法 | 路径 |
|---|---|
| `DELETE` | `/api/admin/practice-admins/{user_id}` |
| `DELETE` | `/api/teacher/practice-admins/{user_id}` |
| `GET` | `/api/admin/practice-admins` |
| `GET` | `/api/teacher/practice-admins` |
| `POST` | `/api/admin/practice-admins` |
| `POST` | `/api/teacher/practice-admins` |

### 新闻模块（5）
> 来源：远端线（新闻）

| 方法 | 路径 |
|---|---|
| `GET` | `/api/admin/news/pending` |
| `GET` | `/api/news/categories` |
| `GET` | `/api/news/digest` |
| `GET` | `/api/news/timeline` |
| `POST` | `/api/admin/news/{news_id}/review` |

### 题库/导入/OCR（4）
> 来源：远端线 / 本地线（OCR 候选）

| 方法 | 路径 |
|---|---|
| `GET` | `/api/questions/group/{group_id}/ocr-candidates` |
| `GET` | `/api/questions/{question_id}/ocr-candidates` |
| `POST` | `/api/questions/group/{group_id}/ocr-apply` |
| `POST` | `/api/questions/{question_id}/ocr-apply` |

### 平台/反馈/通知（3）
> 来源：远端线（反馈工单）

| 方法 | 路径 |
|---|---|
| `GET` | `/api/feedback/{feedback_id}` |
| `GET` | `/api/teacher/scores/class-compare` |
| `POST` | `/api/feedback/{feedback_id}/reply` |

### 媒体资产（2）
> 来源：远端线（F3）

| 方法 | 路径 |
|---|---|
| `GET` | `/media/{asset_id}` |
| `HEAD` | `/media/{asset_id}` |

## 四、删除项（合并/下线导致）

**接口**（相对合并前本地 main）：

- `GET /api/badges/catalog`
- `GET /api/badges/my`
- `GET /api/badges/summary`
- `GET /api/badges/top`
- `GET /api/badges/wall`
- `PUT /api/badges/top`

**页面**：

- `/badge-preview`（相对合并前本地 main 已移除）
- `/badges`（相对合并前本地 main 已移除）
- `/badges-demo`（相对合并前本地 main 已移除）
- `/teacher/analytics`（相对合并前本地 main 已移除）

> 徽章展示模块是按你的要求主动下线的：`/badges`、`/badges-demo`、`/badge-preview` 三条页面 + `/api/badges/*` 六个端点（成就/金币引擎保留）。`/teacher/analytics` 是远端那条线自己调整掉的。

## 五、怎么看

- 想看**全量**清单：见 [`远端main页面与接口清单_v1.md`](远端main页面与接口清单_v1.md)
- 想看**代码位置**：全量清单里每个接口都有 `文件:行号` 链接
- 想复核本报告：三个快照分别 `git worktree add` 检出后用 `openapi()` 导出，再与当前比差集

**基线**：`89363f5`（2026-11-04）
