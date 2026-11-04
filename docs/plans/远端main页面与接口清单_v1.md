# 远端 main 页面与接口清单 v1

> 自动生成，可重复运行刷新：`python scripts/gen_inventory.py`（在仓库根执行）
> 页面：解析 `src/router/index.ts`（含嵌套 children 展开）；接口：静态解析 `backend/app/api/**` 的 `@router.<method>(...)` + `main.py` 的 `@app.<method>`
> 统计：**页面 105 条**（另有 5 条 redirect）、**接口 465 个操作**

文件列是相对本文件的链接（带行号锚点），编辑器 / GitHub 可直接点开。

## 一、页面路由（按模块）

### 管理端（14）
> `src/views/admin/**` 或 `.vtj/vue/admin_*`

| 路径 | 角色 | 组件文件 |
|---|---|---|
| `/admin` | admin | [@/layouts/AdminLayout.vue](../../src/layouts/AdminLayout.vue) |
| `/admin/backup` | admin | [$vtj/vue/admin_backup.vue](../../.vtj/vue/admin_backup.vue) |
| `/admin/dashboard` | admin | [$vtj/vue/admin_dashboard.vue](../../.vtj/vue/admin_dashboard.vue) |
| `/admin/forum` | admin | [@/views/admin/admin_forum.vue](../../src/views/admin/admin_forum.vue) |
| `/admin/help` | admin | [$vtj/vue/admin_help.vue](../../.vtj/vue/admin_help.vue) |
| `/admin/logs` | admin | [$vtj/vue/admin_logs.vue](../../.vtj/vue/admin_logs.vue) |
| `/admin/material-rules` | admin | [@/views/admin/material_rules.vue](../../src/views/admin/material_rules.vue) |
| `/admin/materials` | admin | [$vtj/vue/admin_materials.vue](../../.vtj/vue/admin_materials.vue) |
| `/admin/papers` | admin | [$vtj/vue/paper_approval.vue](../../.vtj/vue/paper_approval.vue) |
| `/admin/permissions` | admin | [$vtj/vue/admin_permissions.vue](../../.vtj/vue/admin_permissions.vue) |
| `/admin/profile` | admin | [$vtj/vue/admin_profile.vue](../../.vtj/vue/admin_profile.vue) |
| `/admin/questions` | admin | [$vtj/vue/admin_questions.vue](../../.vtj/vue/admin_questions.vue) |
| `/admin/settings` | admin | [$vtj/vue/admin_settings.vue](../../.vtj/vue/admin_settings.vue) |
| `/admin/users` | admin | [$vtj/vue/admin_users.vue](../../.vtj/vue/admin_users.vue) |

### 教师端（8）
> `src/views/teacher/**` 或 `.vtj/vue/teacher_*`

| 路径 | 角色 | 组件文件 |
|---|---|---|
| `/teacher/classes` | teacher,admin | [$vtj/vue/teacher_classes.vue](../../.vtj/vue/teacher_classes.vue) |
| `/teacher/dashboard` | teacher,admin | [$vtj/vue/teacher_dashboard.vue](../../.vtj/vue/teacher_dashboard.vue) |
| `/teacher/forum` | teacher,admin | [@/views/teacher/teacher_forum.vue](../../src/views/teacher/teacher_forum.vue) |
| `/teacher/messages` | teacher,admin | [$vtj/vue/teacher_messages.vue](../../.vtj/vue/teacher_messages.vue) |
| `/teacher/papers` | teacher,admin | [@/views/teacher/pc/TeacherPaperEditor.vue](../../src/views/teacher/pc/TeacherPaperEditor.vue) |
| `/teacher/profile` | teacher,admin | [$vtj/vue/teacher_profile.vue](../../.vtj/vue/teacher_profile.vue) |
| `/teacher/questions` | teacher,admin | [$vtj/vue/teacher_questions.vue](../../.vtj/vue/teacher_questions.vue) |
| `/teacher/scores` | teacher,admin | [@/views/teacher/pc/TeacherScoresWorkspace.vue](../../src/views/teacher/pc/TeacherScoresWorkspace.vue) |

### 手机端专用（28）
> 复用/轻量包装，守 R12

| 路径 | 角色 | 组件文件 |
|---|---|---|
| `/mobile/achievements` | student | [@/views/student/mobile/mobile_achievements.vue](../../src/views/student/mobile/mobile_achievements.vue) |
| `/mobile/answer` | student | [@/views/student/mobile/mobile_answer.vue](../../src/views/student/mobile/mobile_answer.vue) |
| `/mobile/calendar` | student | [@/views/student/mobile/mobile_calendar.vue](../../src/views/student/mobile/mobile_calendar.vue) |
| `/mobile/favorites` | student | [@/views/student/mobile/mobile_favorites.vue](../../src/views/student/mobile/mobile_favorites.vue) |
| `/mobile/feedback` | student | [@/views/student/mobile/mobile_feedback.vue](../../src/views/student/mobile/mobile_feedback.vue) |
| `/mobile/forum` | student | [$vtj/vue/mobile_forum.vue](../../.vtj/vue/mobile_forum.vue) |
| `/mobile/forum/:id` | student | [@/views/student/mobile/mobile_forum_detail.vue](../../src/views/student/mobile/mobile_forum_detail.vue) |
| `/mobile/forum/create` | student | [@/views/student/mobile/mobile_forum_create.vue](../../src/views/student/mobile/mobile_forum_create.vue) |
| `/mobile/gold-purchase` | student | [$vtj/vue/mobile_gold_purchase.vue](../../.vtj/vue/mobile_gold_purchase.vue) |
| `/mobile/help` | student | [@/views/student/mobile/mobile_help.vue](../../src/views/student/mobile/mobile_help.vue) |
| `/mobile/history` | student | [@/views/student/mobile/mobile_history.vue](../../src/views/student/mobile/mobile_history.vue) |
| `/mobile/home` | student | [$vtj/vue/mobile_home.vue](../../.vtj/vue/mobile_home.vue) |
| `/mobile/login` | student | [$vtj/vue/mobile_login.vue](../../.vtj/vue/mobile_login.vue) |
| `/mobile/materials` | student | [@/views/student/mobile/mobile_materials.vue](../../src/views/student/mobile/mobile_materials.vue) |
| `/mobile/news` | student | [@/views/student/mobile/mobile_news.vue](../../src/views/student/mobile/mobile_news.vue) |
| `/mobile/news/:id` | student | [@/views/student/mobile/mobile_news.vue](../../src/views/student/mobile/mobile_news.vue) |
| `/mobile/news/timeline` | student | [@/views/student/shared/news_timeline.vue](../../src/views/student/shared/news_timeline.vue) |
| `/mobile/notes` | student | [@/views/student/mobile/mobile_notes.vue](../../src/views/student/mobile/mobile_notes.vue) |
| `/mobile/notifications` | student | [@/views/student/mobile/mobile_notifications.vue](../../src/views/student/mobile/mobile_notifications.vue) |
| `/mobile/practice` | student | [$vtj/vue/mobile_practice.vue](../../.vtj/vue/mobile_practice.vue) |
| `/mobile/profile` | student | [$vtj/vue/mobile_profile.vue](../../.vtj/vue/mobile_profile.vue) |
| `/mobile/question-bank` | student | [$vtj/vue/mobile_question_bank.vue](../../.vtj/vue/mobile_question_bank.vue) |
| `/mobile/recruit` | student | [@/views/student/mobile/mobile_recruitment.vue](../../src/views/student/mobile/mobile_recruitment.vue) |
| `/mobile/scan` | student | [@/views/student/mobile/mobile_scan.vue](../../src/views/student/mobile/mobile_scan.vue) |
| `/mobile/score-analysis` | student | [@/views/student/mobile/mobile_score_analysis.vue](../../src/views/student/mobile/mobile_score_analysis.vue) |
| `/mobile/student-papers` | student | [@/views/student/mobile/mobile_student_papers.vue](../../src/views/student/mobile/mobile_student_papers.vue) |
| `/mobile/wrong-questions` | student | [@/views/student/mobile/mobile_wrong_questions.vue](../../src/views/student/mobile/mobile_wrong_questions.vue) |
| `/mobile/wrong-review` | student | [@/views/student/mobile/mobile_wrong_review.vue](../../src/views/student/mobile/mobile_wrong_review.vue) |

### 平板端专用（21）
> 多数是 redirect 到电脑端

| 路径 | 角色 | 组件文件 |
|---|---|---|
| `/tablet/answer` | student | [@/views/student/mobile/mobile_answer.vue](../../src/views/student/mobile/mobile_answer.vue) |
| `/tablet/calendar` | student | [@/views/student/mobile/mobile_calendar.vue](../../src/views/student/mobile/mobile_calendar.vue) |
| `/tablet/favorites` | student | [@/views/student/mobile/mobile_favorites.vue](../../src/views/student/mobile/mobile_favorites.vue) |
| `/tablet/forum` | student | [$vtj/vue/tablet_forum.vue](../../.vtj/vue/tablet_forum.vue) |
| `/tablet/forum/:id` | student | [@/views/student/mobile/mobile_forum_detail.vue](../../src/views/student/mobile/mobile_forum_detail.vue) |
| `/tablet/forum/create` | student | [@/views/student/mobile/mobile_forum_create.vue](../../src/views/student/mobile/mobile_forum_create.vue) |
| `/tablet/gold-purchase` | student | [$vtj/vue/tablet_gold_purchase.vue](../../.vtj/vue/tablet_gold_purchase.vue) |
| `/tablet/home` | student | [$vtj/vue/home_page.vue](../../.vtj/vue/home_page.vue) |
| `/tablet/login` | student | [$vtj/vue/tablet_login.vue](../../.vtj/vue/tablet_login.vue) |
| `/tablet/news` | student | [@/views/student/mobile/mobile_news.vue](../../src/views/student/mobile/mobile_news.vue) |
| `/tablet/news/:id` | student | [@/views/student/mobile/mobile_news.vue](../../src/views/student/mobile/mobile_news.vue) |
| `/tablet/news/timeline` | student | [@/views/student/shared/news_timeline.vue](../../src/views/student/shared/news_timeline.vue) |
| `/tablet/notes` | student | [@/views/student/mobile/mobile_notes.vue](../../src/views/student/mobile/mobile_notes.vue) |
| `/tablet/notifications` | student | [@/views/student/mobile/mobile_notifications.vue](../../src/views/student/mobile/mobile_notifications.vue) |
| `/tablet/practice` | student | [$vtj/vue/tablet_practice.vue](../../.vtj/vue/tablet_practice.vue) |
| `/tablet/profile` | student | [$vtj/vue/tablet_profile.vue](../../.vtj/vue/tablet_profile.vue) |
| `/tablet/question-bank` | student | [$vtj/vue/tablet_question_bank.vue](../../.vtj/vue/tablet_question_bank.vue) |
| `/tablet/recruit` | student | [@/views/student/mobile/mobile_recruitment.vue](../../src/views/student/mobile/mobile_recruitment.vue) |
| `/tablet/score-analysis` | student | [@/views/student/mobile/mobile_score_analysis.vue](../../src/views/student/mobile/mobile_score_analysis.vue) |
| `/tablet/student-papers` | student | [@/views/student/mobile/mobile_student_papers.vue](../../src/views/student/mobile/mobile_student_papers.vue) |
| `/tablet/wrong-questions` | student | [@/views/student/mobile/mobile_wrong_questions.vue](../../src/views/student/mobile/mobile_wrong_questions.vue) |

### 备考资料（资料页/详情/上传/预览）（5）
> 本模块主力页面

| 路径 | 角色 | 组件文件 |
|---|---|---|
| `/materials/detail` | student,teacher,admin | [@/views/pc/material_detail.vue](../../src/views/pc/material_detail.vue) |
| `/materials/gongzhuan` | student,teacher,admin | [$vtj/vue/materials_gongzhuan.vue](../../.vtj/vue/materials_gongzhuan.vue) |
| `/materials/shenlun` | student,teacher,admin | [$vtj/vue/materials_shenlun.vue](../../.vtj/vue/materials_shenlun.vue) |
| `/materials/upload` | student,teacher,admin | [@/views/student/material_upload.vue](../../src/views/student/material_upload.vue) |
| `/materials/xingce` | student,teacher,admin | [$vtj/vue/materials_xingce.vue](../../.vtj/vue/materials_xingce.vue) |

### 模块4 学习计划（1）
> 远端新增

| 路径 | 角色 | 组件文件 |
|---|---|---|
| `/study-plan` | student,teacher,admin | [$vtj/vue/study_plan.vue](../../.vtj/vue/study_plan.vue) |

### 模块7 联考小智（1）
> 远端新增

| 路径 | 角色 | 组件文件 |
|---|---|---|
| `/ai-assistant` | student,teacher,admin | [$vtj/vue/ai_chat.vue](../../.vtj/vue/ai_chat.vue) |

### 模块7 知识图谱（1）
> 远端新增

| 路径 | 角色 | 组件文件 |
|---|---|---|
| `/knowledge` | student,teacher,admin | [$vtj/vue/knowledge_view.vue](../../.vtj/vue/knowledge_view.vue) |

### 模块7 AI 记忆（1）
> 远端新增

| 路径 | 角色 | 组件文件 |
|---|---|---|
| `/memories` | student,teacher,admin | [$vtj/vue/memories.vue](../../.vtj/vue/memories.vue) |

### AI 错题本（问卷式）（1）
> 远端新增

| 路径 | 角色 | 组件文件 |
|---|---|---|
| `/profile-quiz` | student,teacher,admin | [$vtj/vue/profile_quiz.vue](../../.vtj/vue/profile_quiz.vue) |

### 新闻模块（2）
> 远端新增

| 路径 | 角色 | 组件文件 |
|---|---|---|
| `/news` | student,teacher,admin | [@/views/student/shared/news_timeline.vue](../../src/views/student/shared/news_timeline.vue) |
| `/news/:id` | student,teacher,admin | [@/views/student/shared/news_detail.vue](../../src/views/student/shared/news_detail.vue) |

### 社区论坛（1）

| 路径 | 角色 | 组件文件 |
|---|---|---|
| `/forum` | student,teacher,admin | [$vtj/vue/forum.vue](../../.vtj/vue/forum.vue) |

### 成长/目标（1）

| 路径 | 角色 | 组件文件 |
|---|---|---|
| `/achievements` | student,teacher,admin | [@/views/student/shared/achievements.vue](../../src/views/student/shared/achievements.vue) |

### 个人中心（1）

| 路径 | 角色 | 组件文件 |
|---|---|---|
| `/profile` | student,teacher,admin | [@/views/student/shared/profile.vue](../../src/views/student/shared/profile.vue) |

### 其它页面（首页/登录/答题等）（19）

| 路径 | 角色 | 组件文件 |
|---|---|---|
| `/` | student,teacher,admin | [$vtj/vue/question_bank.vue](../../.vtj/vue/question_bank.vue) |
| `/:pathMatch(.*)*` | — | [@/views/system/shared/not-found.vue](../../src/views/system/shared/not-found.vue) |
| `/answer` | student | [$vtj/vue/answer_page.vue](../../.vtj/vue/answer_page.vue) |
| `/exercise` | student,teacher,admin | [@/views/student/shared/exercise.vue](../../src/views/student/shared/exercise.vue) |
| `/feedback` | student,teacher,admin | [@/views/student/shared/feedback.vue](../../src/views/student/shared/feedback.vue) |
| `/help` | student,teacher,admin | [@/views/student/shared/help.vue](../../src/views/student/shared/help.vue) |
| `/home` | student,teacher,admin | [$vtj/vue/home_page.vue](../../.vtj/vue/home_page.vue) |
| `/login` | — | [$vtj/vue/login.vue](../../.vtj/vue/login.vue) |
| `/materials-preview` | student,teacher,admin | [@/views/dev/MaterialsPreview.vue](../../src/views/dev/MaterialsPreview.vue) |
| `/paper-answer` | student,teacher,admin | [$vtj/vue/paper_answer.vue](../../.vtj/vue/paper_answer.vue) |
| `/paper-result` | student,teacher,admin | [$vtj/vue/paper_result.vue](../../.vtj/vue/paper_result.vue) |
| `/question-import` | teacher,admin | [$vtj/vue/question_import.vue](../../.vtj/vue/question_import.vue) |
| `/recruit` | student,teacher,admin | [$vtj/vue/recruitment_info.vue](../../.vtj/vue/recruitment_info.vue) |
| `/scan` | — | [$vtj/vue/download_client.vue](../../.vtj/vue/download_client.vue) |
| `/smart-answer` | student | [$vtj/vue/smart_answer.vue](../../.vtj/vue/smart_answer.vue) |
| `/smart-exam` | student | [$vtj/vue/smart_exam.vue](../../.vtj/vue/smart_exam.vue) |
| `/solution` | student,teacher,admin | [@/views/student/shared/solution.vue](../../src/views/student/shared/solution.vue) |
| `/student/papers` | student,teacher,admin | [$vtj/vue/student_papers.vue](../../.vtj/vue/student_papers.vue) |
| `/unauthorized` | — | [@/views/system/shared/unauthorized.vue](../../src/views/system/shared/unauthorized.vue) |

### redirect（5）

| 旧路径 | 跳转到 |
|---|---|
| `/admin` | `/admin/dashboard` |
| `/admin` | `/admin/dashboard` |
| `/tablet/materials` | `/materials/xingce` |
| `/tablet/materials/detail` | `/materials/detail` |
| `/teacher/analytics` | `/teacher/scores` |

## 二、接口（按后端域）

### 平台域（管理端/教师端/通知/反馈/LLM/WebSocket）（`platform`，103 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/admin/announcements` | `—` | [backend/app/api/v1/platform/admin.py:648](../../backend/app/api/v1/platform/admin.py#L648) |
| `POST` | `/api/admin/announcements` | `—` | [backend/app/api/v1/platform/admin.py:678](../../backend/app/api/v1/platform/admin.py#L678) |
| `DELETE` | `/api/admin/announcements/{announcement_id}` | `—` | [backend/app/api/v1/platform/admin.py:724](../../backend/app/api/v1/platform/admin.py#L724) |
| `PUT` | `/api/admin/announcements/{announcement_id}` | `—` | [backend/app/api/v1/platform/admin.py:702](../../backend/app/api/v1/platform/admin.py#L702) |
| `GET` | `/api/admin/approval/papers` | `—` | [backend/app/api/v1/platform/admin_approval.py:64](../../backend/app/api/v1/platform/admin_approval.py#L64) |
| `GET` | `/api/admin/approval/papers/{paper_id}` | `—` | [backend/app/api/v1/platform/admin_approval.py:149](../../backend/app/api/v1/platform/admin_approval.py#L149) |
| `POST` | `/api/admin/approval/papers/{paper_id}/approve` | `—` | [backend/app/api/v1/platform/admin_approval.py:228](../../backend/app/api/v1/platform/admin_approval.py#L228) |
| `GET` | `/api/admin/approval/papers/{paper_id}/issues` | `—` | [backend/app/api/v1/platform/admin_approval.py:340](../../backend/app/api/v1/platform/admin_approval.py#L340) |
| `GET` | `/api/admin/approval/papers/{paper_id}/logs` | `—` | [backend/app/api/v1/platform/admin_approval.py:310](../../backend/app/api/v1/platform/admin_approval.py#L310) |
| `POST` | `/api/admin/approval/papers/{paper_id}/reject` | `—` | [backend/app/api/v1/platform/admin_approval.py:268](../../backend/app/api/v1/platform/admin_approval.py#L268) |
| `POST` | `/api/admin/backup` | `—` | [backend/app/api/v1/platform/admin.py:925](../../backend/app/api/v1/platform/admin.py#L925) |
| `GET` | `/api/admin/backup/stats` | `—` | [backend/app/api/v1/platform/admin.py:878](../../backend/app/api/v1/platform/admin.py#L878) |
| `GET` | `/api/admin/backups` | `—` | [backend/app/api/v1/platform/admin.py:986](../../backend/app/api/v1/platform/admin.py#L986) |
| `POST` | `/api/admin/backups/{backup_id}/restore` | `—` | [backend/app/api/v1/platform/admin.py:1011](../../backend/app/api/v1/platform/admin.py#L1011) |
| `GET` | `/api/admin/dashboard` | `—` | [backend/app/api/v1/platform/admin.py:188](../../backend/app/api/v1/platform/admin.py#L188) |
| `GET` | `/api/admin/logs` | `—` | [backend/app/api/v1/platform/admin.py:745](../../backend/app/api/v1/platform/admin.py#L745) |
| `GET` | `/api/admin/logs/errors` | `—` | [backend/app/api/v1/platform/admin.py:796](../../backend/app/api/v1/platform/admin.py#L796) |
| `GET` | `/api/admin/logs/export` | `—` | [backend/app/api/v1/platform/admin.py:822](../../backend/app/api/v1/platform/admin.py#L822) |
| `GET` | `/api/admin/news/pending` | `pending_news` | [backend/app/api/v1/platform/admin_news.py:22](../../backend/app/api/v1/platform/admin_news.py#L22) |
| `POST` | `/api/admin/news/{news_id}/review` | `review_news` | [backend/app/api/v1/platform/admin_news.py:47](../../backend/app/api/v1/platform/admin_news.py#L47) |
| `GET` | `/api/admin/permissions` | `—` | [backend/app/api/v1/platform/admin.py:1110](../../backend/app/api/v1/platform/admin.py#L1110) |
| `PUT` | `/api/admin/permissions` | `—` | [backend/app/api/v1/platform/admin.py:1148](../../backend/app/api/v1/platform/admin.py#L1148) |
| `GET` | `/api/admin/questions` | `—` | [backend/app/api/v1/platform/admin.py:489](../../backend/app/api/v1/platform/admin.py#L489) |
| `GET` | `/api/admin/questions/stats` | `—` | [backend/app/api/v1/platform/admin.py:453](../../backend/app/api/v1/platform/admin.py#L453) |
| `PUT` | `/api/admin/questions/{question_id}` | `—` | [backend/app/api/v1/platform/admin.py:561](../../backend/app/api/v1/platform/admin.py#L561) |
| `PUT` | `/api/admin/questions/{question_id}/archive` | `—` | [backend/app/api/v1/platform/admin.py:627](../../backend/app/api/v1/platform/admin.py#L627) |
| `PUT` | `/api/admin/questions/{question_id}/audit` | `—` | [backend/app/api/v1/platform/admin.py:602](../../backend/app/api/v1/platform/admin.py#L602) |
| `GET` | `/api/admin/settings` | `—` | [backend/app/api/v1/platform/admin.py:1038](../../backend/app/api/v1/platform/admin.py#L1038) |
| `PUT` | `/api/admin/settings` | `—` | [backend/app/api/v1/platform/admin.py:1055](../../backend/app/api/v1/platform/admin.py#L1055) |
| `GET` | `/api/admin/users` | `—` | [backend/app/api/v1/platform/admin.py:298](../../backend/app/api/v1/platform/admin.py#L298) |
| `POST` | `/api/admin/users` | `—` | [backend/app/api/v1/platform/admin.py:336](../../backend/app/api/v1/platform/admin.py#L336) |
| `PUT` | `/api/admin/users/{user_id}` | `—` | [backend/app/api/v1/platform/admin.py:377](../../backend/app/api/v1/platform/admin.py#L377) |
| `PUT` | `/api/admin/users/{user_id}/disable` | `—` | [backend/app/api/v1/platform/admin.py:400](../../backend/app/api/v1/platform/admin.py#L400) |
| `PUT` | `/api/admin/users/{user_id}/reset-password` | `—` | [backend/app/api/v1/platform/admin.py:425](../../backend/app/api/v1/platform/admin.py#L425) |
| `GET` | `/api/feedback/` | `_serialize_feedback` | [backend/app/api/v1/platform/feedback.py:223](../../backend/app/api/v1/platform/feedback.py#L223) |
| `POST` | `/api/feedback/` | `_serialize_feedback` | [backend/app/api/v1/platform/feedback.py:86](../../backend/app/api/v1/platform/feedback.py#L86) |
| `GET` | `/api/feedback/faq` | `_validate_attachments` | [backend/app/api/v1/platform/feedback.py:50](../../backend/app/api/v1/platform/feedback.py#L50) |
| `GET` | `/api/feedback/my` | `_serialize_feedback` | [backend/app/api/v1/platform/feedback.py:203](../../backend/app/api/v1/platform/feedback.py#L203) |
| `GET` | `/api/feedback/{feedback_id}` | `_serialize_feedback` | [backend/app/api/v1/platform/feedback.py:137](../../backend/app/api/v1/platform/feedback.py#L137) |
| `POST` | `/api/feedback/{feedback_id}/reply` | `_serialize_feedback` | [backend/app/api/v1/platform/feedback.py:171](../../backend/app/api/v1/platform/feedback.py#L171) |
| `POST` | `/api/feedback/{feedback_id}/reply` | `_serialize_feedback` | [backend/app/api/v1/platform/feedback.py:249](../../backend/app/api/v1/platform/feedback.py#L249) |
| `POST` | `/api/llm/chat` | `—` | [backend/app/api/v1/platform/llm.py:83](../../backend/app/api/v1/platform/llm.py#L83) |
| `GET` | `/api/llm/context/assemble` | `—` | [backend/app/api/v1/platform/llm.py:306](../../backend/app/api/v1/platform/llm.py#L306) |
| `GET` | `/api/llm/sessions` | `—` | [backend/app/api/v1/platform/llm.py:212](../../backend/app/api/v1/platform/llm.py#L212) |
| `POST` | `/api/llm/sessions` | `—` | [backend/app/api/v1/platform/llm.py:245](../../backend/app/api/v1/platform/llm.py#L245) |
| `DELETE` | `/api/llm/sessions/{session_id}` | `—` | [backend/app/api/v1/platform/llm.py:293](../../backend/app/api/v1/platform/llm.py#L293) |
| `GET` | `/api/llm/sessions/{session_id}/messages` | `—` | [backend/app/api/v1/platform/llm.py:266](../../backend/app/api/v1/platform/llm.py#L266) |
| `GET` | `/api/notifications/` | `—` | [backend/app/api/v1/platform/notifications.py:32](../../backend/app/api/v1/platform/notifications.py#L32) |
| `PUT` | `/api/notifications/read-all` | `—` | [backend/app/api/v1/platform/notifications.py:91](../../backend/app/api/v1/platform/notifications.py#L91) |
| `PUT` | `/api/notifications/{notification_id}/read` | `—` | [backend/app/api/v1/platform/notifications.py:70](../../backend/app/api/v1/platform/notifications.py#L70) |
| `GET` | `/api/teacher/analytics/knowledge-mastery` | `—` | [backend/app/api/v1/platform/teacher.py:2288](../../backend/app/api/v1/platform/teacher.py#L2288) |
| `GET` | `/api/teacher/analytics/overview` | `—` | [backend/app/api/v1/platform/teacher.py:2111](../../backend/app/api/v1/platform/teacher.py#L2111) |
| `GET` | `/api/teacher/analytics/question-usage` | `—` | [backend/app/api/v1/platform/teacher.py:2256](../../backend/app/api/v1/platform/teacher.py#L2256) |
| `GET` | `/api/teacher/classes` | `—` | [backend/app/api/v1/platform/teacher.py:1796](../../backend/app/api/v1/platform/teacher.py#L1796) |
| `POST` | `/api/teacher/classes` | `—` | [backend/app/api/v1/platform/teacher.py:1838](../../backend/app/api/v1/platform/teacher.py#L1838) |
| `DELETE` | `/api/teacher/classes/{class_id}` | `—` | [backend/app/api/v1/platform/teacher.py:1907](../../backend/app/api/v1/platform/teacher.py#L1907) |
| `GET` | `/api/teacher/classes/{class_id}` | `—` | [backend/app/api/v1/platform/teacher.py:1860](../../backend/app/api/v1/platform/teacher.py#L1860) |
| `POST` | `/api/teacher/classes/{class_id}/students` | `—` | [backend/app/api/v1/platform/teacher.py:1925](../../backend/app/api/v1/platform/teacher.py#L1925) |
| `DELETE` | `/api/teacher/classes/{class_id}/students/{user_id}` | `—` | [backend/app/api/v1/platform/teacher.py:1950](../../backend/app/api/v1/platform/teacher.py#L1950) |
| `GET` | `/api/teacher/dashboard` | `—` | [backend/app/api/v1/platform/teacher.py:145](../../backend/app/api/v1/platform/teacher.py#L145) |
| `GET` | `/api/teacher/knowledge-points` | `—` | [backend/app/api/v1/platform/teacher.py:307](../../backend/app/api/v1/platform/teacher.py#L307) |
| `GET` | `/api/teacher/messages` | `—` | [backend/app/api/v1/platform/teacher.py:1974](../../backend/app/api/v1/platform/teacher.py#L1974) |
| `PUT` | `/api/teacher/messages/read-all` | `—` | [backend/app/api/v1/platform/teacher.py:2090](../../backend/app/api/v1/platform/teacher.py#L2090) |
| `GET` | `/api/teacher/messages/unread-count` | `—` | [backend/app/api/v1/platform/teacher.py:2052](../../backend/app/api/v1/platform/teacher.py#L2052) |
| `PUT` | `/api/teacher/messages/{message_id}/read` | `—` | [backend/app/api/v1/platform/teacher.py:2070](../../backend/app/api/v1/platform/teacher.py#L2070) |
| `GET` | `/api/teacher/papers` | `—` | [backend/app/api/v1/platform/teacher.py:624](../../backend/app/api/v1/platform/teacher.py#L624) |
| `POST` | `/api/teacher/papers` | `—` | [backend/app/api/v1/platform/teacher.py:766](../../backend/app/api/v1/platform/teacher.py#L766) |
| `POST` | `/api/teacher/papers/auto-generate` | `—` | [backend/app/api/v1/platform/teacher.py:1233](../../backend/app/api/v1/platform/teacher.py#L1233) |
| `GET` | `/api/teacher/papers/stats` | `—` | [backend/app/api/v1/platform/teacher.py:684](../../backend/app/api/v1/platform/teacher.py#L684) |
| `DELETE` | `/api/teacher/papers/{paper_id}` | `—` | [backend/app/api/v1/platform/teacher.py:824](../../backend/app/api/v1/platform/teacher.py#L824) |
| `GET` | `/api/teacher/papers/{paper_id}` | `—` | [backend/app/api/v1/platform/teacher.py:707](../../backend/app/api/v1/platform/teacher.py#L707) |
| `PUT` | `/api/teacher/papers/{paper_id}` | `—` | [backend/app/api/v1/platform/teacher.py:800](../../backend/app/api/v1/platform/teacher.py#L800) |
| `DELETE` | `/api/teacher/papers/{paper_id}/permanent` | `—` | [backend/app/api/v1/platform/teacher.py:871](../../backend/app/api/v1/platform/teacher.py#L871) |
| `POST` | `/api/teacher/papers/{paper_id}/publish` | `—` | [backend/app/api/v1/platform/teacher.py:1362](../../backend/app/api/v1/platform/teacher.py#L1362) |
| `POST` | `/api/teacher/papers/{paper_id}/questions` | `—` | [backend/app/api/v1/platform/teacher.py:895](../../backend/app/api/v1/platform/teacher.py#L895) |
| `PUT` | `/api/teacher/papers/{paper_id}/questions/order` | `—` | [backend/app/api/v1/platform/teacher.py:976](../../backend/app/api/v1/platform/teacher.py#L976) |
| `DELETE` | `/api/teacher/papers/{paper_id}/questions/{question_id}` | `—` | [backend/app/api/v1/platform/teacher.py:939](../../backend/app/api/v1/platform/teacher.py#L939) |
| `PUT` | `/api/teacher/papers/{paper_id}/questions/{question_id}` | `—` | [backend/app/api/v1/platform/teacher.py:1004](../../backend/app/api/v1/platform/teacher.py#L1004) |
| `PUT` | `/api/teacher/papers/{paper_id}/questions/{question_id}/content` | `—` | [backend/app/api/v1/platform/teacher.py:1039](../../backend/app/api/v1/platform/teacher.py#L1039) |
| `POST` | `/api/teacher/papers/{paper_id}/questions/{question_id}/replace` | `—` | [backend/app/api/v1/platform/teacher.py:1182](../../backend/app/api/v1/platform/teacher.py#L1182) |
| `POST` | `/api/teacher/papers/{paper_id}/restore` | `—` | [backend/app/api/v1/platform/teacher.py:849](../../backend/app/api/v1/platform/teacher.py#L849) |
| `POST` | `/api/teacher/papers/{paper_id}/submit-approval` | `—` | [backend/app/api/v1/platform/teacher.py:1328](../../backend/app/api/v1/platform/teacher.py#L1328) |
| `GET` | `/api/teacher/profile` | `—` | [backend/app/api/v1/platform/teacher.py:1651](../../backend/app/api/v1/platform/teacher.py#L1651) |
| `PUT` | `/api/teacher/profile` | `—` | [backend/app/api/v1/platform/teacher.py:1702](../../backend/app/api/v1/platform/teacher.py#L1702) |
| `POST` | `/api/teacher/profile/avatar` | `—` | [backend/app/api/v1/platform/teacher.py:1722](../../backend/app/api/v1/platform/teacher.py#L1722) |
| `POST` | `/api/teacher/profile/change-password` | `—` | [backend/app/api/v1/platform/teacher.py:1779](../../backend/app/api/v1/platform/teacher.py#L1779) |
| `GET` | `/api/teacher/question-types` | `—` | [backend/app/api/v1/platform/teacher.py:276](../../backend/app/api/v1/platform/teacher.py#L276) |
| `GET` | `/api/teacher/questions` | `—` | [backend/app/api/v1/platform/teacher.py:335](../../backend/app/api/v1/platform/teacher.py#L335) |
| `POST` | `/api/teacher/questions` | `—` | [backend/app/api/v1/platform/teacher.py:413](../../backend/app/api/v1/platform/teacher.py#L413) |
| `POST` | `/api/teacher/questions/batch-delete` | `—` | [backend/app/api/v1/platform/teacher.py:523](../../backend/app/api/v1/platform/teacher.py#L523) |
| `POST` | `/api/teacher/questions/batch-reclassify` | `—` | [backend/app/api/v1/platform/teacher.py:544](../../backend/app/api/v1/platform/teacher.py#L544) |
| `DELETE` | `/api/teacher/questions/{question_id}` | `—` | [backend/app/api/v1/platform/teacher.py:505](../../backend/app/api/v1/platform/teacher.py#L505) |
| `PUT` | `/api/teacher/questions/{question_id}` | `—` | [backend/app/api/v1/platform/teacher.py:463](../../backend/app/api/v1/platform/teacher.py#L463) |
| `GET` | `/api/teacher/questions/{question_id}/images` | `—` | [backend/app/api/v1/platform/teacher.py:577](../../backend/app/api/v1/platform/teacher.py#L577) |
| `GET` | `/api/teacher/scores/class-compare` | `—` | [backend/app/api/v1/platform/teacher.py:1532](../../backend/app/api/v1/platform/teacher.py#L1532) |
| `GET` | `/api/teacher/scores/class/{class_id}` | `—` | [backend/app/api/v1/platform/teacher.py:1495](../../backend/app/api/v1/platform/teacher.py#L1495) |
| `GET` | `/api/teacher/scores/overview` | `—` | [backend/app/api/v1/platform/teacher.py:1397](../../backend/app/api/v1/platform/teacher.py#L1397) |
| `GET` | `/api/teacher/scores/question-stats/{paper_id}` | `—` | [backend/app/api/v1/platform/teacher.py:1607](../../backend/app/api/v1/platform/teacher.py#L1607) |
| `GET` | `/api/teacher/scores/student/{user_id}` | `—` | [backend/app/api/v1/platform/teacher.py:1569](../../backend/app/api/v1/platform/teacher.py#L1569) |
| `POST` | `/ws/broadcast` | `—` | [backend/app/api/v1/platform/websocket.py:425](../../backend/app/api/v1/platform/websocket.py#L425) |
| `POST` | `/ws/notify/{user_id}` | `—` | [backend/app/api/v1/platform/websocket.py:408](../../backend/app/api/v1/platform/websocket.py#L408) |
| `GET` | `/ws/online_users` | `—` | [backend/app/api/v1/platform/websocket.py:395](../../backend/app/api/v1/platform/websocket.py#L395) |
| `GET` | `/ws/room/{room_name}` | `—` | [backend/app/api/v1/platform/websocket.py:400](../../backend/app/api/v1/platform/websocket.py#L400) |

### 题库域（目录/题目/试卷/导入）（`catalog`，83 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `POST` | `/api/papers/` | `—` | [backend/app/api/v1/catalog/papers.py:69](../../backend/app/api/v1/catalog/papers.py#L69) |
| `POST` | `/api/papers/auto-generate` | `—` | [backend/app/api/v1/catalog/paper_generation.py:114](../../backend/app/api/v1/catalog/paper_generation.py#L114) |
| `GET` | `/api/papers/list` | `—` | [backend/app/api/v1/catalog/paper_generation.py:525](../../backend/app/api/v1/catalog/paper_generation.py#L525) |
| `POST` | `/api/papers/manual-generate` | `—` | [backend/app/api/v1/catalog/paper_generation.py:294](../../backend/app/api/v1/catalog/paper_generation.py#L294) |
| `GET` | `/api/papers/stats` | `—` | [backend/app/api/v1/catalog/papers.py:240](../../backend/app/api/v1/catalog/papers.py#L240) |
| `POST` | `/api/papers/template-generate` | `—` | [backend/app/api/v1/catalog/paper_generation.py:412](../../backend/app/api/v1/catalog/paper_generation.py#L412) |
| `DELETE` | `/api/papers/{paper_id}` | `—` | [backend/app/api/v1/catalog/papers.py:171](../../backend/app/api/v1/catalog/papers.py#L171) |
| `GET` | `/api/papers/{paper_id}` | `—` | [backend/app/api/v1/catalog/paper_generation.py:598](../../backend/app/api/v1/catalog/paper_generation.py#L598) |
| `GET` | `/api/papers/{paper_id}` | `—` | [backend/app/api/v1/catalog/papers.py:103](../../backend/app/api/v1/catalog/papers.py#L103) |
| `PUT` | `/api/papers/{paper_id}` | `—` | [backend/app/api/v1/catalog/paper_generation.py:670](../../backend/app/api/v1/catalog/paper_generation.py#L670) |
| `PUT` | `/api/papers/{paper_id}` | `—` | [backend/app/api/v1/catalog/papers.py:135](../../backend/app/api/v1/catalog/papers.py#L135) |
| `POST` | `/api/papers/{paper_id}/approve` | `—` | [backend/app/api/v1/catalog/papers.py:379](../../backend/app/api/v1/catalog/papers.py#L379) |
| `POST` | `/api/papers/{paper_id}/duplicate` | `—` | [backend/app/api/v1/catalog/paper_generation.py:776](../../backend/app/api/v1/catalog/paper_generation.py#L776) |
| `GET` | `/api/papers/{paper_id}/preview` | `—` | [backend/app/api/v1/catalog/papers.py:217](../../backend/app/api/v1/catalog/papers.py#L217) |
| `POST` | `/api/papers/{paper_id}/publish` | `—` | [backend/app/api/v1/catalog/paper_generation.py:710](../../backend/app/api/v1/catalog/paper_generation.py#L710) |
| `POST` | `/api/papers/{paper_id}/publish` | `—` | [backend/app/api/v1/catalog/papers.py:423](../../backend/app/api/v1/catalog/papers.py#L423) |
| `POST` | `/api/papers/{paper_id}/questions` | `—` | [backend/app/api/v1/catalog/papers.py:253](../../backend/app/api/v1/catalog/papers.py#L253) |
| `DELETE` | `/api/papers/{paper_id}/questions/{question_id}` | `—` | [backend/app/api/v1/catalog/papers.py:305](../../backend/app/api/v1/catalog/papers.py#L305) |
| `POST` | `/api/papers/{paper_id}/submit` | `—` | [backend/app/api/v1/catalog/papers.py:340](../../backend/app/api/v1/catalog/papers.py#L340) |
| `GET` | `/api/questions/` | `_normalize_options` | [backend/app/api/v1/catalog/questions.py:145](../../backend/app/api/v1/catalog/questions.py#L145) |
| `POST` | `/api/questions/` | `_normalize_options` | [backend/app/api/v1/catalog/questions.py:45](../../backend/app/api/v1/catalog/questions.py#L45) |
| `POST` | `/api/questions/batch-explanation` | `—` | [backend/app/api/v1/catalog/questions.py:1666](../../backend/app/api/v1/catalog/questions.py#L1666) |
| `POST` | `/api/questions/batch-import` | `—` | [backend/app/api/v1/catalog/questions.py:1103](../../backend/app/api/v1/catalog/questions.py#L1103) |
| `POST` | `/api/questions/batch-reclassify` | `—` | [backend/app/api/v1/catalog/questions.py:1422](../../backend/app/api/v1/catalog/questions.py#L1422) |
| `PATCH` | `/api/questions/batch-type` | `—` | [backend/app/api/v1/catalog/questions.py:1572](../../backend/app/api/v1/catalog/questions.py#L1572) |
| `GET` | `/api/questions/count-by-category` | `—` | [backend/app/api/v1/catalog/questions.py:392](../../backend/app/api/v1/catalog/questions.py#L392) |
| `GET` | `/api/questions/exercise/questions` | `—` | [backend/app/api/v1/catalog/questions.py:463](../../backend/app/api/v1/catalog/questions.py#L463) |
| `GET` | `/api/questions/favorites` | `—` | [backend/app/api/v1/catalog/question_actions.py:51](../../backend/app/api/v1/catalog/question_actions.py#L51) |
| `POST` | `/api/questions/file-import` | `—` | [backend/app/api/v1/catalog/questions.py:1281](../../backend/app/api/v1/catalog/questions.py#L1281) |
| `GET` | `/api/questions/group/{group_id}` | `—` | [backend/app/api/v1/catalog/questions.py:589](../../backend/app/api/v1/catalog/questions.py#L589) |
| `POST` | `/api/questions/group/{group_id}/images` | `—` | [backend/app/api/v1/catalog/questions.py:1063](../../backend/app/api/v1/catalog/questions.py#L1063) |
| `POST` | `/api/questions/group/{group_id}/ocr-apply` | `—` | [backend/app/api/v1/catalog/questions.py:1033](../../backend/app/api/v1/catalog/questions.py#L1033) |
| `GET` | `/api/questions/group/{group_id}/ocr-candidates` | `—` | [backend/app/api/v1/catalog/questions.py:1015](../../backend/app/api/v1/catalog/questions.py#L1015) |
| `POST` | `/api/questions/import/batch-answers` | `_process_import_async` | [backend/app/api/v1/catalog/question_import.py:1768](../../backend/app/api/v1/catalog/question_import.py#L1768) |
| `POST` | `/api/questions/import/batch-parsed` | `_process_import_async` | [backend/app/api/v1/catalog/question_import.py:1321](../../backend/app/api/v1/catalog/question_import.py#L1321) |
| `POST` | `/api/questions/import/confirm` | `_separate_match_essay` | [backend/app/api/v1/catalog/question_import.py:2550](../../backend/app/api/v1/catalog/question_import.py#L2550) |
| `POST` | `/api/questions/import/image` | `_essay_split_combined_text` | [backend/app/api/v1/catalog/question_import.py:4349](../../backend/app/api/v1/catalog/question_import.py#L4349) |
| `GET` | `/api/questions/import/mineru-health` | `_subject_from_paper_name` | [backend/app/api/v1/catalog/question_import.py:3765](../../backend/app/api/v1/catalog/question_import.py#L3765) |
| `POST` | `/api/questions/import/ocr` | `_essay_split_combined_text` | [backend/app/api/v1/catalog/question_import.py:4249](../../backend/app/api/v1/catalog/question_import.py#L4249) |
| `GET` | `/api/questions/import/ocr/status` | `_essay_split_combined_text` | [backend/app/api/v1/catalog/question_import.py:4339](../../backend/app/api/v1/catalog/question_import.py#L4339) |
| `POST` | `/api/questions/import/parse` | `_extract_image_refs_from_content` | [backend/app/api/v1/catalog/question_import.py:3787](../../backend/app/api/v1/catalog/question_import.py#L3787) |
| `GET` | `/api/questions/import/records` | `_essay_split_combined_text` | [backend/app/api/v1/catalog/question_import.py:4709](../../backend/app/api/v1/catalog/question_import.py#L4709) |
| `POST` | `/api/questions/import/records/{import_id}/attach-image` | `_resolve_confirm_subject` | [backend/app/api/v1/catalog/question_import.py:2389](../../backend/app/api/v1/catalog/question_import.py#L2389) |
| `GET` | `/api/questions/import/records/{import_id}/status` | `_resolve_confirm_subject` | [backend/app/api/v1/catalog/question_import.py:2292](../../backend/app/api/v1/catalog/question_import.py#L2292) |
| `POST` | `/api/questions/import/separate-match` | `_xingce_kao_normalize_map` | [backend/app/api/v1/catalog/question_import.py:3120](../../backend/app/api/v1/catalog/question_import.py#L3120) |
| `POST` | `/api/questions/import/separate-match-xingce` | `_xingce_folder_province` | [backend/app/api/v1/catalog/question_import.py:3450](../../backend/app/api/v1/catalog/question_import.py#L3450) |
| `POST` | `/api/questions/import/single` | `_material_match_key` | [backend/app/api/v1/catalog/question_import.py:1147](../../backend/app/api/v1/catalog/question_import.py#L1147) |
| `GET` | `/api/questions/import/stats` | `_essay_split_combined_text` | [backend/app/api/v1/catalog/question_import.py:4756](../../backend/app/api/v1/catalog/question_import.py#L4756) |
| `GET` | `/api/questions/import/taxonomy` | `—` | [backend/app/api/v1/catalog/question_import.py:4936](../../backend/app/api/v1/catalog/question_import.py#L4936) |
| `PUT` | `/api/questions/import/update-answer/{question_id}` | `_process_import_async` | [backend/app/api/v1/catalog/question_import.py:1701](../../backend/app/api/v1/catalog/question_import.py#L1701) |
| `POST` | `/api/questions/import/upload` | `_sanitize_preview_images` | [backend/app/api/v1/catalog/question_import.py:2185](../../backend/app/api/v1/catalog/question_import.py#L2185) |
| `GET` | `/api/questions/random` | `—` | [backend/app/api/v1/catalog/questions.py:304](../../backend/app/api/v1/catalog/questions.py#L304) |
| `POST` | `/api/questions/random-draw` | `—` | [backend/app/api/v1/catalog/questions.py:1224](../../backend/app/api/v1/catalog/questions.py#L1224) |
| `GET` | `/api/questions/subcategory-stats` | `—` | [backend/app/api/v1/catalog/questions.py:399](../../backend/app/api/v1/catalog/questions.py#L399) |
| `GET` | `/api/questions/unclassified` | `—` | [backend/app/api/v1/catalog/questions.py:1483](../../backend/app/api/v1/catalog/questions.py#L1483) |
| `DELETE` | `/api/questions/{question_id}` | `—` | [backend/app/api/v1/catalog/questions.py:845](../../backend/app/api/v1/catalog/questions.py#L845) |
| `GET` | `/api/questions/{question_id}` | `—` | [backend/app/api/v1/catalog/questions.py:663](../../backend/app/api/v1/catalog/questions.py#L663) |
| `PUT` | `/api/questions/{question_id}` | `—` | [backend/app/api/v1/catalog/questions.py:740](../../backend/app/api/v1/catalog/questions.py#L740) |
| `GET` | `/api/questions/{question_id}/actions` | `—` | [backend/app/api/v1/catalog/question_actions.py:243](../../backend/app/api/v1/catalog/question_actions.py#L243) |
| `PATCH` | `/api/questions/{question_id}/explanation` | `—` | [backend/app/api/v1/catalog/questions.py:1631](../../backend/app/api/v1/catalog/questions.py#L1631) |
| `POST` | `/api/questions/{question_id}/favorite` | `—` | [backend/app/api/v1/catalog/question_actions.py:21](../../backend/app/api/v1/catalog/question_actions.py#L21) |
| `POST` | `/api/questions/{question_id}/images` | `—` | [backend/app/api/v1/catalog/questions.py:887](../../backend/app/api/v1/catalog/questions.py#L887) |
| `DELETE` | `/api/questions/{question_id}/marker` | `—` | [backend/app/api/v1/catalog/question_actions.py:221](../../backend/app/api/v1/catalog/question_actions.py#L221) |
| `POST` | `/api/questions/{question_id}/marker` | `—` | [backend/app/api/v1/catalog/question_actions.py:179](../../backend/app/api/v1/catalog/question_actions.py#L179) |
| `DELETE` | `/api/questions/{question_id}/note` | `—` | [backend/app/api/v1/catalog/question_actions.py:157](../../backend/app/api/v1/catalog/question_actions.py#L157) |
| `GET` | `/api/questions/{question_id}/note` | `—` | [backend/app/api/v1/catalog/question_actions.py:134](../../backend/app/api/v1/catalog/question_actions.py#L134) |
| `POST` | `/api/questions/{question_id}/note` | `—` | [backend/app/api/v1/catalog/question_actions.py:96](../../backend/app/api/v1/catalog/question_actions.py#L96) |
| `POST` | `/api/questions/{question_id}/ocr-apply` | `—` | [backend/app/api/v1/catalog/questions.py:994](../../backend/app/api/v1/catalog/questions.py#L994) |
| `GET` | `/api/questions/{question_id}/ocr-candidates` | `—` | [backend/app/api/v1/catalog/questions.py:969](../../backend/app/api/v1/catalog/questions.py#L969) |
| `POST` | `/api/questions/{question_id}/reclassify` | `—` | [backend/app/api/v1/catalog/questions.py:1355](../../backend/app/api/v1/catalog/questions.py#L1355) |
| `PATCH` | `/api/questions/{question_id}/type` | `—` | [backend/app/api/v1/catalog/questions.py:1524](../../backend/app/api/v1/catalog/questions.py#L1524) |
| `GET` | `/api/wrong-questions/` | `_get_subcategory` | [backend/app/api/v1/catalog/wrong_questions.py:101](../../backend/app/api/v1/catalog/wrong_questions.py#L101) |
| `POST` | `/api/wrong-questions/collect` | `_get_subcategory` | [backend/app/api/v1/catalog/wrong_questions.py:168](../../backend/app/api/v1/catalog/wrong_questions.py#L168) |
| `GET` | `/api/wrong-questions/review/queue` | `—` | [backend/app/api/v1/catalog/wrong_questions.py:420](../../backend/app/api/v1/catalog/wrong_questions.py#L420) |
| `POST` | `/api/wrong-questions/review/submit` | `—` | [backend/app/api/v1/catalog/wrong_questions.py:705](../../backend/app/api/v1/catalog/wrong_questions.py#L705) |
| `GET` | `/api/wrong-questions/subcategories` | `—` | [backend/app/api/v1/catalog/wrong_questions.py:385](../../backend/app/api/v1/catalog/wrong_questions.py#L385) |
| `GET` | `/api/wrong-questions/zhanti/expiring` | `—` | [backend/app/api/v1/catalog/wrong_questions.py:576](../../backend/app/api/v1/catalog/wrong_questions.py#L576) |
| `GET` | `/api/wrong-questions/zhanti/list` | `—` | [backend/app/api/v1/catalog/wrong_questions.py:516](../../backend/app/api/v1/catalog/wrong_questions.py#L516) |
| `DELETE` | `/api/wrong-questions/{wrong_id}` | `_get_subcategory` | [backend/app/api/v1/catalog/wrong_questions.py:239](../../backend/app/api/v1/catalog/wrong_questions.py#L239) |
| `PUT` | `/api/wrong-questions/{wrong_id}/chop` | `—` | [backend/app/api/v1/catalog/wrong_questions.py:473](../../backend/app/api/v1/catalog/wrong_questions.py#L473) |
| `GET` | `/api/wrong-questions/{wrong_id}/detail` | `—` | [backend/app/api/v1/catalog/wrong_questions.py:599](../../backend/app/api/v1/catalog/wrong_questions.py#L599) |
| `PUT` | `/api/wrong-questions/{wrong_id}/mastery` | `_get_subcategory` | [backend/app/api/v1/catalog/wrong_questions.py:259](../../backend/app/api/v1/catalog/wrong_questions.py#L259) |
| `POST` | `/api/wrong-questions/{wrong_id}/unchop` | `—` | [backend/app/api/v1/catalog/wrong_questions.py:683](../../backend/app/api/v1/catalog/wrong_questions.py#L683) |

### 社区域（论坛/举报/治理）（`community`，56 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `DELETE` | `/api/forum/comments/{comment_id}` | `—` | [backend/app/api/v1/community/forum.py:1755](../../backend/app/api/v1/community/forum.py#L1755) |
| `POST` | `/api/forum/comments/{comment_id}/like` | `_apply_reaction` | [backend/app/api/v1/community/forum.py:1059](../../backend/app/api/v1/community/forum.py#L1059) |
| `PUT` | `/api/forum/comments/{comment_id}/pin` | `—` | [backend/app/api/v1/community/forum.py:1730](../../backend/app/api/v1/community/forum.py#L1730) |
| `DELETE` | `/api/forum/comments/{comment_id}/reactions` | `_serialize_sticker` | [backend/app/api/v1/community/forum.py:1246](../../backend/app/api/v1/community/forum.py#L1246) |
| `POST` | `/api/forum/comments/{comment_id}/reactions/{reaction_code}` | `_serialize_sticker` | [backend/app/api/v1/community/forum.py:1234](../../backend/app/api/v1/community/forum.py#L1234) |
| `GET` | `/api/forum/my-favorites` | `_apply_reaction` | [backend/app/api/v1/community/forum.py:755](../../backend/app/api/v1/community/forum.py#L755) |
| `GET` | `/api/forum/my-likes` | `_apply_reaction` | [backend/app/api/v1/community/forum.py:811](../../backend/app/api/v1/community/forum.py#L811) |
| `GET` | `/api/forum/my-posts` | `_can_moderate_forum` | [backend/app/api/v1/community/forum.py:1513](../../backend/app/api/v1/community/forum.py#L1513) |
| `GET` | `/api/forum/posts` | `_apply_reaction` | [backend/app/api/v1/community/forum.py:343](../../backend/app/api/v1/community/forum.py#L343) |
| `POST` | `/api/forum/posts` | `_apply_reaction` | [backend/app/api/v1/community/forum.py:509](../../backend/app/api/v1/community/forum.py#L509) |
| `DELETE` | `/api/forum/posts/{post_id}` | `_apply_reaction` | [backend/app/api/v1/community/forum.py:628](../../backend/app/api/v1/community/forum.py#L628) |
| `GET` | `/api/forum/posts/{post_id}` | `_apply_reaction` | [backend/app/api/v1/community/forum.py:451](../../backend/app/api/v1/community/forum.py#L451) |
| `PUT` | `/api/forum/posts/{post_id}` | `—` | [backend/app/api/v1/community/forum.py:1666](../../backend/app/api/v1/community/forum.py#L1666) |
| `GET` | `/api/forum/posts/{post_id}/comments` | `_apply_reaction` | [backend/app/api/v1/community/forum.py:870](../../backend/app/api/v1/community/forum.py#L870) |
| `POST` | `/api/forum/posts/{post_id}/comments` | `_apply_reaction` | [backend/app/api/v1/community/forum.py:962](../../backend/app/api/v1/community/forum.py#L962) |
| `POST` | `/api/forum/posts/{post_id}/favorite` | `_apply_reaction` | [backend/app/api/v1/community/forum.py:713](../../backend/app/api/v1/community/forum.py#L713) |
| `POST` | `/api/forum/posts/{post_id}/like` | `_apply_reaction` | [backend/app/api/v1/community/forum.py:659](../../backend/app/api/v1/community/forum.py#L659) |
| `DELETE` | `/api/forum/posts/{post_id}/reactions` | `_serialize_sticker` | [backend/app/api/v1/community/forum.py:1225](../../backend/app/api/v1/community/forum.py#L1225) |
| `POST` | `/api/forum/posts/{post_id}/reactions/{reaction_code}` | `_clear_reaction` | [backend/app/api/v1/community/forum.py:1165](../../backend/app/api/v1/community/forum.py#L1165) |
| `POST` | `/api/forum/reports` | `_can_moderate_forum` | [backend/app/api/v1/community/forum.py:1591](../../backend/app/api/v1/community/forum.py#L1591) |
| `GET` | `/api/forum/stats` | `_can_moderate_forum` | [backend/app/api/v1/community/forum.py:1555](../../backend/app/api/v1/community/forum.py#L1555) |
| `GET` | `/api/forum/stickers` | `_can_moderate_forum` | [backend/app/api/v1/community/forum.py:1272](../../backend/app/api/v1/community/forum.py#L1272) |
| `POST` | `/api/forum/stickers` | `_can_moderate_forum` | [backend/app/api/v1/community/forum.py:1292](../../backend/app/api/v1/community/forum.py#L1292) |
| `DELETE` | `/api/forum/stickers/{sticker_id}` | `_can_moderate_forum` | [backend/app/api/v1/community/forum.py:1335](../../backend/app/api/v1/community/forum.py#L1335) |
| `POST` | `/api/forum/upload` | `_can_moderate_forum` | [backend/app/api/v1/community/forum.py:1356](../../backend/app/api/v1/community/forum.py#L1356) |
| `GET` | `/api/forum/users/{user_id}/public` | `_can_moderate_forum` | [backend/app/api/v1/community/forum.py:1466](../../backend/app/api/v1/community/forum.py#L1466) |
| `GET` | `/api/practice-admin/` | `—` | [backend/app/api/v1/community/practice_admin.py:62](../../backend/app/api/v1/community/practice_admin.py#L62) |
| `GET` | `/api/practice-admin/` | `—` | [backend/app/api/v1/community/practice_admin.py:166](../../backend/app/api/v1/community/practice_admin.py#L166) |
| `POST` | `/api/practice-admin/` | `—` | [backend/app/api/v1/community/practice_admin.py:90](../../backend/app/api/v1/community/practice_admin.py#L90) |
| `POST` | `/api/practice-admin/` | `—` | [backend/app/api/v1/community/practice_admin.py:197](../../backend/app/api/v1/community/practice_admin.py#L197) |
| `DELETE` | `/api/practice-admin/{user_id}` | `—` | [backend/app/api/v1/community/practice_admin.py:138](../../backend/app/api/v1/community/practice_admin.py#L138) |
| `DELETE` | `/api/practice-admin/{user_id}` | `—` | [backend/app/api/v1/community/practice_admin.py:246](../../backend/app/api/v1/community/practice_admin.py#L246) |
| `GET` | `/api/quotes/` | `_format_obsidian_quote` | [backend/app/api/v1/community/quotes.py:237](../../backend/app/api/v1/community/quotes.py#L237) |
| `POST` | `/api/quotes/` | `—` | [backend/app/api/v1/community/quotes.py:371](../../backend/app/api/v1/community/quotes.py#L371) |
| `GET` | `/api/quotes/favorites` | `—` | [backend/app/api/v1/community/quotes.py:476](../../backend/app/api/v1/community/quotes.py#L476) |
| `POST` | `/api/quotes/obsidian/{obsidian_source}/favorite` | `—` | [backend/app/api/v1/community/quotes.py:439](../../backend/app/api/v1/community/quotes.py#L439) |
| `GET` | `/api/quotes/quote/daily` | `_format_obsidian_quote` | [backend/app/api/v1/community/quotes.py:164](../../backend/app/api/v1/community/quotes.py#L164) |
| `GET` | `/api/quotes/random` | `—` | [backend/app/api/v1/community/quotes.py:321](../../backend/app/api/v1/community/quotes.py#L321) |
| `POST` | `/api/quotes/{quote_id}/favorite` | `—` | [backend/app/api/v1/community/quotes.py:405](../../backend/app/api/v1/community/quotes.py#L405) |
| `GET` | `/api/teacher/forum/comments` | `_set_target_status` | [backend/app/api/v1/community/forum_moderation.py:381](../../backend/app/api/v1/community/forum_moderation.py#L381) |
| `DELETE` | `/api/teacher/forum/comments/{comment_id}` | `_set_target_status` | [backend/app/api/v1/community/forum_moderation.py:444](../../backend/app/api/v1/community/forum_moderation.py#L444) |
| `POST` | `/api/teacher/forum/comments/{comment_id}/hide` | `_set_target_status` | [backend/app/api/v1/community/forum_moderation.py:307](../../backend/app/api/v1/community/forum_moderation.py#L307) |
| `DELETE` | `/api/teacher/forum/comments/{comment_id}/purge` | `—` | [backend/app/api/v1/community/forum_moderation.py:682](../../backend/app/api/v1/community/forum_moderation.py#L682) |
| `POST` | `/api/teacher/forum/comments/{comment_id}/restore` | `—` | [backend/app/api/v1/community/forum_moderation.py:646](../../backend/app/api/v1/community/forum_moderation.py#L646) |
| `GET` | `/api/teacher/forum/moderation` | `_set_target_status` | [backend/app/api/v1/community/forum_moderation.py:475](../../backend/app/api/v1/community/forum_moderation.py#L475) |
| `POST` | `/api/teacher/forum/moderation/{moderation_id}/approve` | `—` | [backend/app/api/v1/community/forum_moderation.py:545](../../backend/app/api/v1/community/forum_moderation.py#L545) |
| `POST` | `/api/teacher/forum/moderation/{moderation_id}/reject` | `—` | [backend/app/api/v1/community/forum_moderation.py:565](../../backend/app/api/v1/community/forum_moderation.py#L565) |
| `GET` | `/api/teacher/forum/posts` | `_hide_post` | [backend/app/api/v1/community/forum_moderation.py:132](../../backend/app/api/v1/community/forum_moderation.py#L132) |
| `GET` | `/api/teacher/forum/posts` | `_set_target_status` | [backend/app/api/v1/community/forum_moderation.py:323](../../backend/app/api/v1/community/forum_moderation.py#L323) |
| `DELETE` | `/api/teacher/forum/posts/{post_id}` | `_set_target_status` | [backend/app/api/v1/community/forum_moderation.py:413](../../backend/app/api/v1/community/forum_moderation.py#L413) |
| `GET` | `/api/teacher/forum/posts/{post_id}/comments` | `_hide_post` | [backend/app/api/v1/community/forum_moderation.py:207](../../backend/app/api/v1/community/forum_moderation.py#L207) |
| `POST` | `/api/teacher/forum/posts/{post_id}/hide` | `_set_target_status` | [backend/app/api/v1/community/forum_moderation.py:293](../../backend/app/api/v1/community/forum_moderation.py#L293) |
| `DELETE` | `/api/teacher/forum/posts/{post_id}/purge` | `—` | [backend/app/api/v1/community/forum_moderation.py:664](../../backend/app/api/v1/community/forum_moderation.py#L664) |
| `POST` | `/api/teacher/forum/posts/{post_id}/restore` | `—` | [backend/app/api/v1/community/forum_moderation.py:628](../../backend/app/api/v1/community/forum_moderation.py#L628) |
| `GET` | `/api/teacher/forum/recycle` | `—` | [backend/app/api/v1/community/forum_moderation.py:593](../../backend/app/api/v1/community/forum_moderation.py#L593) |
| `GET` | `/api/teacher/forum/recycle/audit` | `—` | [backend/app/api/v1/community/forum_moderation.py:585](../../backend/app/api/v1/community/forum_moderation.py#L585) |

### 考试域（考试执行/成绩/练习）（`exam`，54 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `POST` | `/api/exam-records/ai/analyze` | `—` | [backend/app/api/v1/exam/exam_records.py:409](../../backend/app/api/v1/exam/exam_records.py#L409) |
| `GET` | `/api/exam-records/mock` | `—` | [backend/app/api/v1/exam/exam_records.py:77](../../backend/app/api/v1/exam/exam_records.py#L77) |
| `GET` | `/api/exam-records/self` | `—` | [backend/app/api/v1/exam/exam_records.py:27](../../backend/app/api/v1/exam/exam_records.py#L27) |
| `GET` | `/api/exam-records/stats` | `—` | [backend/app/api/v1/exam/exam_records.py:139](../../backend/app/api/v1/exam/exam_records.py#L139) |
| `GET` | `/api/exam-records/summary` | `—` | [backend/app/api/v1/exam/exam_records.py:479](../../backend/app/api/v1/exam/exam_records.py#L479) |
| `GET` | `/api/exam-records/trend` | `—` | [backend/app/api/v1/exam/exam_records.py:210](../../backend/app/api/v1/exam/exam_records.py#L210) |
| `GET` | `/api/exam-records/{record_id}/details` | `—` | [backend/app/api/v1/exam/exam_records.py:348](../../backend/app/api/v1/exam/exam_records.py#L348) |
| `GET` | `/api/exam-records/{record_id}/wrong-questions` | `—` | [backend/app/api/v1/exam/exam_records.py:263](../../backend/app/api/v1/exam/exam_records.py#L263) |
| `GET` | `/api/exams/all` | `—` | [backend/app/api/v1/exam/exams.py:559](../../backend/app/api/v1/exam/exams.py#L559) |
| `GET` | `/api/exams/list` | `—` | [backend/app/api/v1/exam/exams.py:32](../../backend/app/api/v1/exam/exams.py#L32) |
| `GET` | `/api/exams/preview/{paper_id}` | `—` | [backend/app/api/v1/exam/exams.py:651](../../backend/app/api/v1/exam/exams.py#L651) |
| `GET` | `/api/exams/records` | `—` | [backend/app/api/v1/exam/exams.py:441](../../backend/app/api/v1/exam/exams.py#L441) |
| `GET` | `/api/exams/records/{record_id}` | `—` | [backend/app/api/v1/exam/exams.py:490](../../backend/app/api/v1/exam/exams.py#L490) |
| `POST` | `/api/exams/start` | `—` | [backend/app/api/v1/exam/exams.py:595](../../backend/app/api/v1/exam/exams.py#L595) |
| `PUT` | `/api/exams/{exam_id}/progress` | `—` | [backend/app/api/v1/exam/exams.py:631](../../backend/app/api/v1/exam/exams.py#L631) |
| `POST` | `/api/exams/{exam_id}/submit` | `—` | [backend/app/api/v1/exam/exams.py:613](../../backend/app/api/v1/exam/exams.py#L613) |
| `GET` | `/api/exams/{paper_id:int}` | `—` | [backend/app/api/v1/exam/exams.py:92](../../backend/app/api/v1/exam/exams.py#L92) |
| `GET` | `/api/exams/{paper_id}/questions` | `—` | [backend/app/api/v1/exam/exams.py:128](../../backend/app/api/v1/exam/exams.py#L128) |
| `POST` | `/api/exams/{paper_id}/start` | `—` | [backend/app/api/v1/exam/exams.py:230](../../backend/app/api/v1/exam/exams.py#L230) |
| `POST` | `/api/exams/{record_id}/submit` | `—` | [backend/app/api/v1/exam/exams.py:302](../../backend/app/api/v1/exam/exams.py#L302) |
| `POST` | `/api/practice/batch-record` | `_smart_linked_record_ids` | [backend/app/api/v1/exam/practice.py:138](../../backend/app/api/v1/exam/practice.py#L138) |
| `GET` | `/api/practice/knowledge-progress` | `_fmt_dt` | [backend/app/api/v1/exam/practice.py:597](../../backend/app/api/v1/exam/practice.py#L597) |
| `GET` | `/api/practice/recent-records` | `—` | [backend/app/api/v1/exam/practice.py:706](../../backend/app/api/v1/exam/practice.py#L706) |
| `POST` | `/api/practice/record` | `_smart_linked_record_ids` | [backend/app/api/v1/exam/practice.py:74](../../backend/app/api/v1/exam/practice.py#L74) |
| `GET` | `/api/practice/records` | `_smart_linked_record_ids` | [backend/app/api/v1/exam/practice.py:204](../../backend/app/api/v1/exam/practice.py#L204) |
| `GET` | `/api/practice/stats-card` | `_smart_linked_record_ids` | [backend/app/api/v1/exam/practice.py:342](../../backend/app/api/v1/exam/practice.py#L342) |
| `GET` | `/api/practice/type-summary` | `_smart_linked_record_ids` | [backend/app/api/v1/exam/practice.py:261](../../backend/app/api/v1/exam/practice.py#L261) |
| `GET` | `/api/practice/unified-stats` | `_fmt_dt` | [backend/app/api/v1/exam/practice.py:447](../../backend/app/api/v1/exam/practice.py#L447) |
| `GET` | `/api/quick-practice/knowledge-points` | `—` | [backend/app/api/v1/exam/quick_practice.py:294](../../backend/app/api/v1/exam/quick_practice.py#L294) |
| `GET` | `/api/quick-practice/questions` | `—` | [backend/app/api/v1/exam/quick_practice.py:334](../../backend/app/api/v1/exam/quick_practice.py#L334) |
| `GET` | `/api/quick-practice/sub-categories` | `—` | [backend/app/api/v1/exam/quick_practice.py:150](../../backend/app/api/v1/exam/quick_practice.py#L150) |
| `GET` | `/api/quick-practice/subjects` | `—` | [backend/app/api/v1/exam/quick_practice.py:123](../../backend/app/api/v1/exam/quick_practice.py#L123) |
| `POST` | `/api/quick-practice/submit` | `—` | [backend/app/api/v1/exam/quick_practice.py:490](../../backend/app/api/v1/exam/quick_practice.py#L490) |
| `POST` | `/api/smart-exam/generate` | `—` | [backend/app/api/v1/exam/smart_exam.py:153](../../backend/app/api/v1/exam/smart_exam.py#L153) |
| `GET` | `/api/smart-exam/records` | `—` | [backend/app/api/v1/exam/smart_exam.py:1149](../../backend/app/api/v1/exam/smart_exam.py#L1149) |
| `DELETE` | `/api/smart-exam/records/{record_id}` | `—` | [backend/app/api/v1/exam/smart_exam.py:1262](../../backend/app/api/v1/exam/smart_exam.py#L1262) |
| `GET` | `/api/smart-exam/records/{record_id}` | `—` | [backend/app/api/v1/exam/smart_exam.py:1199](../../backend/app/api/v1/exam/smart_exam.py#L1199) |
| `POST` | `/api/smart-exam/{paper_id}/confirm` | `—` | [backend/app/api/v1/exam/smart_exam.py:711](../../backend/app/api/v1/exam/smart_exam.py#L711) |
| `GET` | `/api/smart-exam/{paper_id}/preview` | `—` | [backend/app/api/v1/exam/smart_exam.py:640](../../backend/app/api/v1/exam/smart_exam.py#L640) |
| `POST` | `/api/smart-exam/{paper_id}/replace/{question_id}` | `—` | [backend/app/api/v1/exam/smart_exam.py:426](../../backend/app/api/v1/exam/smart_exam.py#L426) |
| `POST` | `/api/smart-exam/{paper_id}/save-progress` | `—` | [backend/app/api/v1/exam/smart_exam.py:847](../../backend/app/api/v1/exam/smart_exam.py#L847) |
| `POST` | `/api/smart-exam/{paper_id}/start` | `—` | [backend/app/api/v1/exam/smart_exam.py:757](../../backend/app/api/v1/exam/smart_exam.py#L757) |
| `POST` | `/api/smart-exam/{paper_id}/submit` | `—` | [backend/app/api/v1/exam/smart_exam.py:895](../../backend/app/api/v1/exam/smart_exam.py#L895) |
| `GET` | `/api/stats/` | `ensure_daily_checkin` | [backend/app/api/v1/exam/stats.py:28](../../backend/app/api/v1/exam/stats.py#L28) |
| `GET` | `/api/stats/all-time` | `ensure_daily_checkin` | [backend/app/api/v1/exam/stats.py:213](../../backend/app/api/v1/exam/stats.py#L213) |
| `POST` | `/api/stats/auto-checkin` | `—` | [backend/app/api/v1/exam/stats.py:685](../../backend/app/api/v1/exam/stats.py#L685) |
| `GET` | `/api/stats/calendar` | `ensure_daily_checkin` | [backend/app/api/v1/exam/stats.py:370](../../backend/app/api/v1/exam/stats.py#L370) |
| `GET` | `/api/stats/dashboard` | `ensure_daily_checkin` | [backend/app/api/v1/exam/stats.py:438](../../backend/app/api/v1/exam/stats.py#L438) |
| `GET` | `/api/stats/level` | `ensure_daily_checkin` | [backend/app/api/v1/exam/stats.py:131](../../backend/app/api/v1/exam/stats.py#L131) |
| `GET` | `/api/stats/messages` | `ensure_daily_checkin` | [backend/app/api/v1/exam/stats.py:396](../../backend/app/api/v1/exam/stats.py#L396) |
| `GET` | `/api/stats/practice-trend` | `ensure_daily_checkin` | [backend/app/api/v1/exam/stats.py:534](../../backend/app/api/v1/exam/stats.py#L534) |
| `GET` | `/api/stats/type-mastery` | `ensure_daily_checkin` | [backend/app/api/v1/exam/stats.py:310](../../backend/app/api/v1/exam/stats.py#L310) |
| `GET` | `/api/stats/weekly` | `ensure_daily_checkin` | [backend/app/api/v1/exam/stats.py:140](../../backend/app/api/v1/exam/stats.py#L140) |
| `GET` | `/api/stats/weekly-checkin` | `—` | [backend/app/api/v1/exam/stats.py:725](../../backend/app/api/v1/exam/stats.py#L725) |

### 资料域（备考资料/个人库/上传/图片）（`library`，48 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/materials/` | `_grant_read_rewards` | [backend/app/api/v1/library/materials.py:76](../../backend/app/api/v1/library/materials.py#L76) |
| `POST` | `/api/materials/admin` | `_save_tmp` | [backend/app/api/v1/library/materials.py:1451](../../backend/app/api/v1/library/materials.py#L1451) |
| `DELETE` | `/api/materials/admin/batch` | `_save_tmp` | [backend/app/api/v1/library/materials.py:1613](../../backend/app/api/v1/library/materials.py#L1613) |
| `POST` | `/api/materials/admin/batch` | `_save_tmp` | [backend/app/api/v1/library/materials.py:1583](../../backend/app/api/v1/library/materials.py#L1583) |
| `POST` | `/api/materials/admin/cards/batch-image` | `_get_share` | [backend/app/api/v1/library/materials.py:519](../../backend/app/api/v1/library/materials.py#L519) |
| `GET` | `/api/materials/admin/import-records` | `_save_tmp` | [backend/app/api/v1/library/materials.py:1640](../../backend/app/api/v1/library/materials.py#L1640) |
| `POST` | `/api/materials/admin/import/upload` | `—` | [backend/app/api/v1/library/materials.py:1767](../../backend/app/api/v1/library/materials.py#L1767) |
| `POST` | `/api/materials/admin/import/{import_id}/confirm` | `—` | [backend/app/api/v1/library/materials.py:1931](../../backend/app/api/v1/library/materials.py#L1931) |
| `GET` | `/api/materials/admin/import/{import_id}/preview` | `—` | [backend/app/api/v1/library/materials.py:1909](../../backend/app/api/v1/library/materials.py#L1909) |
| `GET` | `/api/materials/admin/import/{import_id}/status` | `—` | [backend/app/api/v1/library/materials.py:1894](../../backend/app/api/v1/library/materials.py#L1894) |
| `GET` | `/api/materials/admin/list` | `_save_tmp` | [backend/app/api/v1/library/materials.py:1416](../../backend/app/api/v1/library/materials.py#L1416) |
| `GET` | `/api/materials/admin/rules` | `_save_tmp` | [backend/app/api/v1/library/materials.py:1309](../../backend/app/api/v1/library/materials.py#L1309) |
| `POST` | `/api/materials/admin/rules` | `_save_tmp` | [backend/app/api/v1/library/materials.py:1331](../../backend/app/api/v1/library/materials.py#L1331) |
| `PUT` | `/api/materials/admin/rules/{rule_id}` | `_save_tmp` | [backend/app/api/v1/library/materials.py:1356](../../backend/app/api/v1/library/materials.py#L1356) |
| `PATCH` | `/api/materials/admin/rules/{rule_id}/toggle` | `_save_tmp` | [backend/app/api/v1/library/materials.py:1394](../../backend/app/api/v1/library/materials.py#L1394) |
| `GET` | `/api/materials/admin/stats` | `_save_tmp` | [backend/app/api/v1/library/materials.py:1532](../../backend/app/api/v1/library/materials.py#L1532) |
| `POST` | `/api/materials/admin/upload/image` | `_validate_material_body` | [backend/app/api/v1/library/materials.py:876](../../backend/app/api/v1/library/materials.py#L876) |
| `DELETE` | `/api/materials/admin/{material_id}` | `_save_tmp` | [backend/app/api/v1/library/materials.py:1511](../../backend/app/api/v1/library/materials.py#L1511) |
| `PUT` | `/api/materials/admin/{material_id}` | `_save_tmp` | [backend/app/api/v1/library/materials.py:1467](../../backend/app/api/v1/library/materials.py#L1467) |
| `PUT` | `/api/materials/admin/{material_id}/status` | `_save_tmp` | [backend/app/api/v1/library/materials.py:1491](../../backend/app/api/v1/library/materials.py#L1491) |
| `GET` | `/api/materials/favorites` | `_grant_read_rewards` | [backend/app/api/v1/library/materials.py:149](../../backend/app/api/v1/library/materials.py#L149) |
| `GET` | `/api/materials/my` | `_get_share` | [backend/app/api/v1/library/materials.py:449](../../backend/app/api/v1/library/materials.py#L449) |
| `POST` | `/api/materials/my` | `_get_share` | [backend/app/api/v1/library/materials.py:310](../../backend/app/api/v1/library/materials.py#L310) |
| `POST` | `/api/materials/my/card` | `_get_share` | [backend/app/api/v1/library/materials.py:333](../../backend/app/api/v1/library/materials.py#L333) |
| `POST` | `/api/materials/my/upload` | `—` | [backend/app/api/v1/library/materials.py:2107](../../backend/app/api/v1/library/materials.py#L2107) |
| `DELETE` | `/api/materials/my/{material_id}` | `_get_share` | [backend/app/api/v1/library/materials.py:501](../../backend/app/api/v1/library/materials.py#L501) |
| `PUT` | `/api/materials/my/{material_id}` | `_get_share` | [backend/app/api/v1/library/materials.py:473](../../backend/app/api/v1/library/materials.py#L473) |
| `POST` | `/api/materials/progress` | `_mark_opened` | [backend/app/api/v1/library/materials.py:214](../../backend/app/api/v1/library/materials.py#L214) |
| `GET` | `/api/materials/progress-summary` | `_grant_read_rewards` | [backend/app/api/v1/library/materials.py:130](../../backend/app/api/v1/library/materials.py#L130) |
| `GET` | `/api/materials/shared` | `_validate_file_upload` | [backend/app/api/v1/library/materials.py:564](../../backend/app/api/v1/library/materials.py#L564) |
| `GET` | `/api/materials/taxonomy` | `_grant_read_rewards` | [backend/app/api/v1/library/materials.py:106](../../backend/app/api/v1/library/materials.py#L106) |
| `GET` | `/api/materials/{material_id}` | `_validate_file_upload` | [backend/app/api/v1/library/materials.py:696](../../backend/app/api/v1/library/materials.py#L696) |
| `POST` | `/api/materials/{material_id}/adopt` | `_validate_file_upload` | [backend/app/api/v1/library/materials.py:650](../../backend/app/api/v1/library/materials.py#L650) |
| `POST` | `/api/materials/{material_id}/favorite` | `_mark_opened` | [backend/app/api/v1/library/materials.py:254](../../backend/app/api/v1/library/materials.py#L254) |
| `POST` | `/api/materials/{material_id}/share` | `_validate_file_upload` | [backend/app/api/v1/library/materials.py:603](../../backend/app/api/v1/library/materials.py#L603) |
| `POST` | `/api/materials/{material_id}/unshare` | `_validate_file_upload` | [backend/app/api/v1/library/materials.py:630](../../backend/app/api/v1/library/materials.py#L630) |
| `GET` | `/api/media/export` | `—` | [backend/app/api/v1/library/media.py:89](../../backend/app/api/v1/library/media.py#L89) |
| `POST` | `/api/media/image` | `—` | [backend/app/api/v1/library/image_media.py:61](../../backend/app/api/v1/library/image_media.py#L61) |
| `POST` | `/api/media/import` | `—` | [backend/app/api/v1/library/media.py:62](../../backend/app/api/v1/library/media.py#L62) |
| `POST` | `/api/media/upload` | `—` | [backend/app/api/v1/library/media.py:15](../../backend/app/api/v1/library/media.py#L15) |
| `GET` | `/api/video/list` | `—` | [backend/app/api/v1/library/videos.py:34](../../backend/app/api/v1/library/videos.py#L34) |
| `POST` | `/api/video/upload` | `—` | [backend/app/api/v1/library/videos.py:81](../../backend/app/api/v1/library/videos.py#L81) |
| `POST` | `/api/video/upload/chunk` | `—` | [backend/app/api/v1/library/videos.py:202](../../backend/app/api/v1/library/videos.py#L202) |
| `POST` | `/api/video/upload/complete` | `—` | [backend/app/api/v1/library/videos.py:225](../../backend/app/api/v1/library/videos.py#L225) |
| `POST` | `/api/video/upload/init` | `—` | [backend/app/api/v1/library/videos.py:160](../../backend/app/api/v1/library/videos.py#L160) |
| `DELETE` | `/api/video/{video_id}` | `—` | [backend/app/api/v1/library/videos.py:411](../../backend/app/api/v1/library/videos.py#L411) |
| `GET` | `/api/video/{video_id}` | `—` | [backend/app/api/v1/library/videos.py:65](../../backend/app/api/v1/library/videos.py#L65) |
| `GET` | `/api/video/{video_id}/stream` | `—` | [backend/app/api/v1/library/videos.py:343](../../backend/app/api/v1/library/videos.py#L343) |

### 成长域（成就/金币/目标/学习计划）（`growth`，36 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/achievements/` | `_require_admin` | [backend/app/api/v1/growth/achievements.py:60](../../backend/app/api/v1/growth/achievements.py#L60) |
| `POST` | `/api/achievements/admin` | `—` | [backend/app/api/v1/growth/achievements.py:161](../../backend/app/api/v1/growth/achievements.py#L161) |
| `GET` | `/api/achievements/earned` | `_require_admin` | [backend/app/api/v1/growth/achievements.py:104](../../backend/app/api/v1/growth/achievements.py#L104) |
| `GET` | `/api/achievements/name-bank/status` | `—` | [backend/app/api/v1/growth/achievements.py:226](../../backend/app/api/v1/growth/achievements.py#L226) |
| `GET` | `/api/achievements/progress` | `_require_admin` | [backend/app/api/v1/growth/achievements.py:132](../../backend/app/api/v1/growth/achievements.py#L132) |
| `GET` | `/api/goals/` | `—` | [backend/app/api/v1/growth/goals.py:65](../../backend/app/api/v1/growth/goals.py#L65) |
| `POST` | `/api/goals/` | `—` | [backend/app/api/v1/growth/goals.py:111](../../backend/app/api/v1/growth/goals.py#L111) |
| `POST` | `/api/goals/batch-confirm` | `—` | [backend/app/api/v1/growth/goals.py:478](../../backend/app/api/v1/growth/goals.py#L478) |
| `GET` | `/api/goals/stats/summary` | `—` | [backend/app/api/v1/growth/goals.py:650](../../backend/app/api/v1/growth/goals.py#L650) |
| `GET` | `/api/goals/status/completed` | `—` | [backend/app/api/v1/growth/goals.py:545](../../backend/app/api/v1/growth/goals.py#L545) |
| `GET` | `/api/goals/status/pending` | `—` | [backend/app/api/v1/growth/goals.py:597](../../backend/app/api/v1/growth/goals.py#L597) |
| `DELETE` | `/api/goals/{goal_id}` | `—` | [backend/app/api/v1/growth/goals.py:201](../../backend/app/api/v1/growth/goals.py#L201) |
| `GET` | `/api/goals/{goal_id}` | `—` | [backend/app/api/v1/growth/goals.py:92](../../backend/app/api/v1/growth/goals.py#L92) |
| `PUT` | `/api/goals/{goal_id}` | `—` | [backend/app/api/v1/growth/goals.py:149](../../backend/app/api/v1/growth/goals.py#L149) |
| `POST` | `/api/goals/{goal_id}/complete` | `—` | [backend/app/api/v1/growth/goals.py:345](../../backend/app/api/v1/growth/goals.py#L345) |
| `POST` | `/api/goals/{goal_id}/confirm-complete` | `—` | [backend/app/api/v1/growth/goals.py:273](../../backend/app/api/v1/growth/goals.py#L273) |
| `POST` | `/api/goals/{goal_id}/progress` | `—` | [backend/app/api/v1/growth/goals.py:228](../../backend/app/api/v1/growth/goals.py#L228) |
| `POST` | `/api/goals/{goal_id}/undo-complete` | `—` | [backend/app/api/v1/growth/goals.py:415](../../backend/app/api/v1/growth/goals.py#L415) |
| `POST` | `/api/plan/adjust` | `_task_summary` | [backend/app/api/v1/growth/study_plan.py:228](../../backend/app/api/v1/growth/study_plan.py#L228) |
| `GET` | `/api/plan/current` | `_task_summary` | [backend/app/api/v1/growth/study_plan.py:343](../../backend/app/api/v1/growth/study_plan.py#L343) |
| `POST` | `/api/plan/generate` | `_task_summary` | [backend/app/api/v1/growth/study_plan.py:73](../../backend/app/api/v1/growth/study_plan.py#L73) |
| `GET` | `/api/plan/notifies` | `—` | [backend/app/api/v1/growth/study_plan.py:681](../../backend/app/api/v1/growth/study_plan.py#L681) |
| `POST` | `/api/plan/notify/{notify_id}/read` | `—` | [backend/app/api/v1/growth/study_plan.py:707](../../backend/app/api/v1/growth/study_plan.py#L707) |
| `POST` | `/api/plan/task/{goal_id}/claim` | `_write_milestone` | [backend/app/api/v1/growth/study_plan.py:578](../../backend/app/api/v1/growth/study_plan.py#L578) |
| `POST` | `/api/plan/task/{goal_id}/toggle` | `_task_summary` | [backend/app/api/v1/growth/study_plan.py:431](../../backend/app/api/v1/growth/study_plan.py#L431) |
| `GET` | `/api/plan/today` | `_write_milestone` | [backend/app/api/v1/growth/study_plan.py:548](../../backend/app/api/v1/growth/study_plan.py#L548) |
| `DELETE` | `/api/plan/{plan_id}` | `_task_summary` | [backend/app/api/v1/growth/study_plan.py:508](../../backend/app/api/v1/growth/study_plan.py#L508) |
| `GET` | `/api/plan/{plan_id}/tasks` | `_task_summary` | [backend/app/api/v1/growth/study_plan.py:459](../../backend/app/api/v1/growth/study_plan.py#L459) |
| `GET` | `/api/profile/` | `—` | [backend/app/api/v1/growth/profile.py:283](../../backend/app/api/v1/growth/profile.py#L283) |
| `GET` | `/api/profile/questions` | `_to_dict` | [backend/app/api/v1/growth/profile.py:245](../../backend/app/api/v1/growth/profile.py#L245) |
| `POST` | `/api/profile/upsert` | `—` | [backend/app/api/v1/growth/profile.py:292](../../backend/app/api/v1/growth/profile.py#L292) |
| `GET` | `/api/tasks/overview` | `—` | [backend/app/api/v1/growth/tasks.py:166](../../backend/app/api/v1/growth/tasks.py#L166) |
| `POST` | `/api/tasks/random/refresh` | `—` | [backend/app/api/v1/growth/tasks.py:212](../../backend/app/api/v1/growth/tasks.py#L212) |
| `POST` | `/api/tasks/{task_id}/claim` | `—` | [backend/app/api/v1/growth/tasks.py:275](../../backend/app/api/v1/growth/tasks.py#L275) |
| `POST` | `/api/v1/growth/checkin` | `—` | [backend/app/api/v1/growth/checkin.py:28](../../backend/app/api/v1/growth/checkin.py#L28) |
| `GET` | `/api/v1/growth/checkin/status` | `—` | [backend/app/api/v1/growth/checkin.py:59](../../backend/app/api/v1/growth/checkin.py#L59) |

### 内容域（新闻/招聘/日历）（`content`，16 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/calendar/exams` | `—` | [backend/app/api/v1/content/calendar.py:66](../../backend/app/api/v1/content/calendar.py#L66) |
| `GET` | `/api/calendar/latest` | `—` | [backend/app/api/v1/content/calendar.py:99](../../backend/app/api/v1/content/calendar.py#L99) |
| `GET` | `/api/news/` | `—` | [backend/app/api/v1/content/news.py:88](../../backend/app/api/v1/content/news.py#L88) |
| `GET` | `/api/news/categories` | `—` | [backend/app/api/v1/content/news.py:169](../../backend/app/api/v1/content/news.py#L169) |
| `GET` | `/api/news/digest` | `—` | [backend/app/api/v1/content/news.py:177](../../backend/app/api/v1/content/news.py#L177) |
| `GET` | `/api/news/favorites` | `—` | [backend/app/api/v1/content/news.py:377](../../backend/app/api/v1/content/news.py#L377) |
| `DELETE` | `/api/news/notes/{note_id}` | `—` | [backend/app/api/v1/content/news.py:542](../../backend/app/api/v1/content/news.py#L542) |
| `GET` | `/api/news/timeline` | `—` | [backend/app/api/v1/content/news.py:241](../../backend/app/api/v1/content/news.py#L241) |
| `GET` | `/api/news/today` | `—` | [backend/app/api/v1/content/news.py:287](../../backend/app/api/v1/content/news.py#L287) |
| `GET` | `/api/news/{news_id}` | `—` | [backend/app/api/v1/content/news.py:413](../../backend/app/api/v1/content/news.py#L413) |
| `POST` | `/api/news/{news_id}/favorite` | `—` | [backend/app/api/v1/content/news.py:358](../../backend/app/api/v1/content/news.py#L358) |
| `POST` | `/api/news/{news_id}/note` | `—` | [backend/app/api/v1/content/news.py:484](../../backend/app/api/v1/content/news.py#L484) |
| `GET` | `/api/news/{news_id}/notes` | `—` | [backend/app/api/v1/content/news.py:512](../../backend/app/api/v1/content/news.py#L512) |
| `GET` | `/api/recruitment/` | `—` | [backend/app/api/v1/content/recruitment.py:84](../../backend/app/api/v1/content/recruitment.py#L84) |
| `GET` | `/api/recruitment/categories` | `—` | [backend/app/api/v1/content/recruitment.py:178](../../backend/app/api/v1/content/recruitment.py#L178) |
| `GET` | `/api/recruitment/{recruitment_id}` | `—` | [backend/app/api/v1/content/recruitment.py:186](../../backend/app/api/v1/content/recruitment.py#L186) |

### 身份域（登录/注册/设备/二维码）（`identity`，16 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `POST` | `/api/auth/avatar` | `—` | [backend/app/api/v1/identity/auth.py:475](../../backend/app/api/v1/identity/auth.py#L475) |
| `POST` | `/api/auth/change-password` | `—` | [backend/app/api/v1/identity/auth.py:411](../../backend/app/api/v1/identity/auth.py#L411) |
| `GET` | `/api/auth/devices/` | `—` | [backend/app/api/v1/identity/devices.py:28](../../backend/app/api/v1/identity/devices.py#L28) |
| `POST` | `/api/auth/devices/revoke-all` | `—` | [backend/app/api/v1/identity/devices.py:64](../../backend/app/api/v1/identity/devices.py#L64) |
| `DELETE` | `/api/auth/devices/{device_id}` | `—` | [backend/app/api/v1/identity/devices.py:46](../../backend/app/api/v1/identity/devices.py#L46) |
| `POST` | `/api/auth/login` | `—` | [backend/app/api/v1/identity/auth.py:95](../../backend/app/api/v1/identity/auth.py#L95) |
| `POST` | `/api/auth/logout` | `—` | [backend/app/api/v1/identity/auth.py:371](../../backend/app/api/v1/identity/auth.py#L371) |
| `GET` | `/api/auth/profile` | `—` | [backend/app/api/v1/identity/auth.py:396](../../backend/app/api/v1/identity/auth.py#L396) |
| `PUT` | `/api/auth/profile` | `—` | [backend/app/api/v1/identity/auth.py:432](../../backend/app/api/v1/identity/auth.py#L432) |
| `POST` | `/api/auth/qrcode/generate` | `—` | [backend/app/api/v1/identity/auth_qrcode.py:57](../../backend/app/api/v1/identity/auth_qrcode.py#L57) |
| `POST` | `/api/auth/qrcode/{qr_uuid}/confirm` | `—` | [backend/app/api/v1/identity/auth_qrcode.py:120](../../backend/app/api/v1/identity/auth_qrcode.py#L120) |
| `GET` | `/api/auth/qrcode/{qr_uuid}/info` | `—` | [backend/app/api/v1/identity/auth_qrcode.py:107](../../backend/app/api/v1/identity/auth_qrcode.py#L107) |
| `GET` | `/api/auth/qrcode/{qr_uuid}/status` | `—` | [backend/app/api/v1/identity/auth_qrcode.py:147](../../backend/app/api/v1/identity/auth_qrcode.py#L147) |
| `POST` | `/api/auth/refresh` | `—` | [backend/app/api/v1/identity/auth.py:329](../../backend/app/api/v1/identity/auth.py#L329) |
| `POST` | `/api/auth/register` | `—` | [backend/app/api/v1/identity/auth.py:213](../../backend/app/api/v1/identity/auth.py#L213) |
| `POST` | `/api/auth/sms-login` | `—` | [backend/app/api/v1/identity/auth.py:261](../../backend/app/api/v1/identity/auth.py#L261) |

### 知识图谱（`knowledge`，14 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/knowledge/categories` | `—` | [backend/app/api/v1/knowledge.py:52](../../backend/app/api/v1/knowledge.py#L52) |
| `GET` | `/api/knowledge/graph` | `—` | [backend/app/api/v1/knowledge.py:155](../../backend/app/api/v1/knowledge.py#L155) |
| `GET` | `/api/knowledge/nodes` | `—` | [backend/app/api/v1/knowledge.py:57](../../backend/app/api/v1/knowledge.py#L57) |
| `POST` | `/api/knowledge/nodes` | `—` | [backend/app/api/v1/knowledge.py:98](../../backend/app/api/v1/knowledge.py#L98) |
| `POST` | `/api/knowledge/nodes/{node_id}/approve` | `—` | [backend/app/api/v1/knowledge.py:123](../../backend/app/api/v1/knowledge.py#L123) |
| `GET` | `/api/knowledge/nodes/{node_id}/detail` | `—` | [backend/app/api/v1/knowledge.py:214](../../backend/app/api/v1/knowledge.py#L214) |
| `POST` | `/api/knowledge/nodes/{node_id}/reject` | `—` | [backend/app/api/v1/knowledge.py:140](../../backend/app/api/v1/knowledge.py#L140) |
| `POST` | `/api/knowledge/relation` | `—` | [backend/app/api/v1/knowledge.py:275](../../backend/app/api/v1/knowledge.py#L275) |
| `POST` | `/api/knowledge/relation/suggest` | `—` | [backend/app/api/v1/knowledge.py:351](../../backend/app/api/v1/knowledge.py#L351) |
| `DELETE` | `/api/knowledge/relation/{rel_id}` | `—` | [backend/app/api/v1/knowledge.py:337](../../backend/app/api/v1/knowledge.py#L337) |
| `GET` | `/api/knowledge/relations` | `—` | [backend/app/api/v1/knowledge.py:311](../../backend/app/api/v1/knowledge.py#L311) |
| `GET` | `/api/knowledge/stats` | `—` | [backend/app/api/v1/knowledge.py:186](../../backend/app/api/v1/knowledge.py#L186) |
| `GET` | `/api/knowledge/vault` | `—` | [backend/app/api/v1/knowledge.py:402](../../backend/app/api/v1/knowledge.py#L402) |
| `POST` | `/api/knowledge/vault/import` | `—` | [backend/app/api/v1/knowledge.py:434](../../backend/app/api/v1/knowledge.py#L434) |

### 个人域（收藏/笔记）（`personal`，14 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/collection/` | `_get_subcategory` | [backend/app/api/v1/personal/collection.py:24](../../backend/app/api/v1/personal/collection.py#L24) |
| `POST` | `/api/collection/favorite` | `_get_subcategory` | [backend/app/api/v1/personal/collection.py:63](../../backend/app/api/v1/personal/collection.py#L63) |
| `GET` | `/api/collection/news-favorites` | `—` | [backend/app/api/v1/personal/collection.py:218](../../backend/app/api/v1/personal/collection.py#L218) |
| `GET` | `/api/collection/question-favorites` | `—` | [backend/app/api/v1/personal/collection.py:313](../../backend/app/api/v1/personal/collection.py#L313) |
| `GET` | `/api/collection/stats` | `—` | [backend/app/api/v1/personal/collection.py:362](../../backend/app/api/v1/personal/collection.py#L362) |
| `DELETE` | `/api/collection/{fav_id}` | `_get_subcategory` | [backend/app/api/v1/personal/collection.py:141](../../backend/app/api/v1/personal/collection.py#L141) |
| `GET` | `/api/notes/` | `_get_subcategory` | [backend/app/api/v1/personal/notes.py:26](../../backend/app/api/v1/personal/notes.py#L26) |
| `POST` | `/api/notes/` | `_get_subcategory` | [backend/app/api/v1/personal/notes.py:90](../../backend/app/api/v1/personal/notes.py#L90) |
| `GET` | `/api/notes/news` | `_build_knowledge_path` | [backend/app/api/v1/personal/notes.py:278](../../backend/app/api/v1/personal/notes.py#L278) |
| `GET` | `/api/notes/question` | `_build_knowledge_path` | [backend/app/api/v1/personal/notes.py:314](../../backend/app/api/v1/personal/notes.py#L314) |
| `GET` | `/api/notes/question/{question_id}` | `—` | [backend/app/api/v1/personal/notes.py:433](../../backend/app/api/v1/personal/notes.py#L433) |
| `GET` | `/api/notes/stats` | `—` | [backend/app/api/v1/personal/notes.py:530](../../backend/app/api/v1/personal/notes.py#L530) |
| `DELETE` | `/api/notes/{note_id}` | `_get_subcategory` | [backend/app/api/v1/personal/notes.py:227](../../backend/app/api/v1/personal/notes.py#L227) |
| `PUT` | `/api/notes/{note_id}` | `_get_subcategory` | [backend/app/api/v1/personal/notes.py:185](../../backend/app/api/v1/personal/notes.py#L185) |

### 奖励域（金币流水）（`reward`，9 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/admin/shop/products` | `—` | [backend/app/api/v1/reward/admin_shop.py:73](../../backend/app/api/v1/reward/admin_shop.py#L73) |
| `POST` | `/api/admin/shop/products` | `—` | [backend/app/api/v1/reward/admin_shop.py:103](../../backend/app/api/v1/reward/admin_shop.py#L103) |
| `DELETE` | `/api/admin/shop/products/{product_id}` | `—` | [backend/app/api/v1/reward/admin_shop.py:150](../../backend/app/api/v1/reward/admin_shop.py#L150) |
| `PUT` | `/api/admin/shop/products/{product_id}` | `—` | [backend/app/api/v1/reward/admin_shop.py:130](../../backend/app/api/v1/reward/admin_shop.py#L130) |
| `GET` | `/api/coins/overview` | `—` | [backend/app/api/v1/reward/coins.py:18](../../backend/app/api/v1/reward/coins.py#L18) |
| `GET` | `/api/coins/transactions` | `—` | [backend/app/api/v1/reward/coins.py:45](../../backend/app/api/v1/reward/coins.py#L45) |
| `POST` | `/api/shop/exchange` | `—` | [backend/app/api/v1/reward/shop.py:90](../../backend/app/api/v1/reward/shop.py#L90) |
| `GET` | `/api/shop/products` | `—` | [backend/app/api/v1/reward/shop.py:50](../../backend/app/api/v1/reward/shop.py#L50) |
| `GET` | `/api/shop/products/{product_id}` | `—` | [backend/app/api/v1/reward/shop.py:79](../../backend/app/api/v1/reward/shop.py#L79) |

### 应用级（健康检查/指标/静态）（`app-main`，7 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/health` | `create_app` | [backend/app/main.py:869](../../backend/app/main.py#L869) |
| `GET` | `/health/foundation` | `create_app` | [backend/app/main.py:880](../../backend/app/main.py#L880) |
| `GET` | `/metrics` | `create_app` | [backend/app/main.py:895](../../backend/app/main.py#L895) |
| `GET` | `/metrics/endpoints` | `create_app` | [backend/app/main.py:925](../../backend/app/main.py#L925) |
| `POST` | `/metrics/reset` | `create_app` | [backend/app/main.py:938](../../backend/app/main.py#L938) |
| `GET` | `/metrics/system` | `create_app` | [backend/app/main.py:899](../../backend/app/main.py#L899) |
| `GET` | `/{full_path:path}` | `create_app` | [backend/app/main.py:914](../../backend/app/main.py#L914) |

### Agent 路由（`agent`，6 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `POST` | `/api/agent/import-today` | `—` | [backend/app/api/v1/agent.py:137](../../backend/app/api/v1/agent.py#L137) |
| `GET` | `/api/agent/memories` | `—` | [backend/app/api/v1/agent.py:185](../../backend/app/api/v1/agent.py#L185) |
| `DELETE` | `/api/agent/memory/{memory_id}` | `—` | [backend/app/api/v1/agent.py:213](../../backend/app/api/v1/agent.py#L213) |
| `POST` | `/api/agent/run` | `—` | [backend/app/api/v1/agent.py:251](../../backend/app/api/v1/agent.py#L251) |
| `GET` | `/api/agent/tasks` | `—` | [backend/app/api/v1/agent.py:246](../../backend/app/api/v1/agent.py#L246) |
| `GET` | `/api/agent/trajectory` | `—` | [backend/app/api/v1/agent.py:233](../../backend/app/api/v1/agent.py#L233) |

### 帖子（根级旧接口）（`post`，3 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `POST` | `/api/post/import` | `—` | [backend/app/api/v1/post.py:39](../../backend/app/api/v1/post.py#L39) |
| `GET` | `/api/post/search` | `—` | [backend/app/api/v1/post.py:82](../../backend/app/api/v1/post.py#L82) |
| `GET` | `/api/post/stats` | `—` | [backend/app/api/v1/post.py:124](../../backend/app/api/v1/post.py#L124) |

## 三、代码位置索引

| 层 | 位置 | 说明 |
|---|---|---|
| 前端路由 | [src/router/index.ts](../../src/router/index.ts) | 全部页面与守卫 |
| 前端页面 | [src/views/](../../src/views/) | 手写页（admin/teacher/student/dev） |
| VTJ 页面 | [.vtj/vue/](../../.vtj/vue/) | 设计器页面（禁改 template，守 R3） |
| 后端入口 | [backend/app/main.py](../../backend/app/main.py) | 全部 `include_router` |
| 后端接口 | [backend/app/api/v1/](../../backend/app/api/v1/) | 按域分目录 |
| 数据模型 | [backend/app/models/models.py](../../backend/app/models/models.py) | 全部 ORM 模型 |
| 门禁 | [backend/scripts/gates/](../../backend/scripts/gates/) | L0–L7 + 注解前瞻检查 |

---

**基线**：远端 `main@1864593`（2026-11-04）
