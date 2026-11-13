# 远端 main 页面与接口清单 v1

> 自动生成，可重复运行刷新：`python scripts/gen_inventory.py`（在仓库根执行）
> 页面：解析 `src/router/index.ts`（嵌套 children 展开）；接口：路径取自 FastAPI `openapi()`，源码位置用 AST 按 `operationId` 回填
> 统计：**页面 105 条**（另有 5 条 redirect）、**接口 462 个操作**

文件列是相对本文件的链接（带 `#L行号` 锚点），编辑器 / GitHub 可直接点开。

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

### 题库域（目录/题目/试卷/导入/OCR）（`catalog`，99 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `POST` | `/api/admin/approval/papers/{paper_id}/approve` | `approve_paper` | [backend/app/api/v1/catalog/papers.py:380](../../backend/app/api/v1/catalog/papers.py#L380) |
| `PUT` | `/api/admin/questions/{question_id}` | `update_question` | [backend/app/api/v1/catalog/questions.py:741](../../backend/app/api/v1/catalog/questions.py#L741) |
| `POST` | `/api/collection/favorite` | `toggle_favorite` | [backend/app/api/v1/catalog/question_actions.py:22](../../backend/app/api/v1/catalog/question_actions.py#L22) |
| `GET` | `/api/exam-records/{record_id}/wrong-questions` | `get_wrong_questions` | [backend/app/api/v1/catalog/wrong_questions.py:102](../../backend/app/api/v1/catalog/wrong_questions.py#L102) |
| `POST` | `/api/materials/{material_id}/favorite` | `toggle_favorite` | [backend/app/api/v1/catalog/question_actions.py:22](../../backend/app/api/v1/catalog/question_actions.py#L22) |
| `DELETE` | `/api/news/notes/{note_id}` | `delete_note` | [backend/app/api/v1/catalog/question_actions.py:158](../../backend/app/api/v1/catalog/question_actions.py#L158) |
| `POST` | `/api/news/{news_id}/favorite` | `toggle_favorite` | [backend/app/api/v1/catalog/question_actions.py:22](../../backend/app/api/v1/catalog/question_actions.py#L22) |
| `GET` | `/api/notes/question/{question_id}` | `get_question_detail` | [backend/app/api/v1/catalog/questions.py:664](../../backend/app/api/v1/catalog/questions.py#L664) |
| `DELETE` | `/api/notes/{note_id}` | `delete_note` | [backend/app/api/v1/catalog/question_actions.py:158](../../backend/app/api/v1/catalog/question_actions.py#L158) |
| `POST` | `/api/papers/` | `create_paper` | [backend/app/api/v1/catalog/papers.py:70](../../backend/app/api/v1/catalog/papers.py#L70) |
| `POST` | `/api/papers/auto-generate` | `auto_generate_paper` | [backend/app/api/v1/catalog/paper_generation.py:115](../../backend/app/api/v1/catalog/paper_generation.py#L115) |
| `GET` | `/api/papers/list` | `get_paper_list` | [backend/app/api/v1/catalog/paper_generation.py:526](../../backend/app/api/v1/catalog/paper_generation.py#L526) |
| `POST` | `/api/papers/manual-generate` | `manual_generate_paper` | [backend/app/api/v1/catalog/paper_generation.py:295](../../backend/app/api/v1/catalog/paper_generation.py#L295) |
| `GET` | `/api/papers/stats` | `get_paper_stats` | [backend/app/api/v1/catalog/papers.py:241](../../backend/app/api/v1/catalog/papers.py#L241) |
| `POST` | `/api/papers/template-generate` | `template_generate_paper` | [backend/app/api/v1/catalog/paper_generation.py:413](../../backend/app/api/v1/catalog/paper_generation.py#L413) |
| `DELETE` | `/api/papers/{paper_id}` | `delete_paper` | [backend/app/api/v1/catalog/papers.py:172](../../backend/app/api/v1/catalog/papers.py#L172) |
| `GET` | `/api/papers/{paper_id}` | `get_paper` | [backend/app/api/v1/catalog/papers.py:104](../../backend/app/api/v1/catalog/papers.py#L104) |
| `PUT` | `/api/papers/{paper_id}` | `update_paper` | [backend/app/api/v1/catalog/papers.py:136](../../backend/app/api/v1/catalog/papers.py#L136) |
| `POST` | `/api/papers/{paper_id}/approve` | `approve_paper` | [backend/app/api/v1/catalog/papers.py:380](../../backend/app/api/v1/catalog/papers.py#L380) |
| `POST` | `/api/papers/{paper_id}/duplicate` | `duplicate_paper` | [backend/app/api/v1/catalog/paper_generation.py:777](../../backend/app/api/v1/catalog/paper_generation.py#L777) |
| `GET` | `/api/papers/{paper_id}/preview` | `preview_paper` | [backend/app/api/v1/catalog/papers.py:218](../../backend/app/api/v1/catalog/papers.py#L218) |
| `POST` | `/api/papers/{paper_id}/publish` | `publish_paper` | [backend/app/api/v1/catalog/paper_generation.py:711](../../backend/app/api/v1/catalog/paper_generation.py#L711) |
| `POST` | `/api/papers/{paper_id}/questions` | `add_questions_to_paper` | [backend/app/api/v1/catalog/papers.py:254](../../backend/app/api/v1/catalog/papers.py#L254) |
| `DELETE` | `/api/papers/{paper_id}/questions/{question_id}` | `remove_question_from_paper` | [backend/app/api/v1/catalog/papers.py:306](../../backend/app/api/v1/catalog/papers.py#L306) |
| `POST` | `/api/papers/{paper_id}/submit` | `submit_for_approval` | [backend/app/api/v1/catalog/papers.py:341](../../backend/app/api/v1/catalog/papers.py#L341) |
| `GET` | `/api/questions/` | `get_questions` | [backend/app/api/v1/catalog/questions.py:146](../../backend/app/api/v1/catalog/questions.py#L146) |
| `POST` | `/api/questions/` | `create_question` | [backend/app/api/v1/catalog/questions.py:46](../../backend/app/api/v1/catalog/questions.py#L46) |
| `POST` | `/api/questions/batch-explanation` | `batch_add_explanation` | [backend/app/api/v1/catalog/questions.py:1667](../../backend/app/api/v1/catalog/questions.py#L1667) |
| `POST` | `/api/questions/batch-import` | `batch_import_questions` | [backend/app/api/v1/catalog/questions.py:1104](../../backend/app/api/v1/catalog/questions.py#L1104) |
| `POST` | `/api/questions/batch-reclassify` | `batch_reclassify` | [backend/app/api/v1/catalog/questions.py:1423](../../backend/app/api/v1/catalog/questions.py#L1423) |
| `PATCH` | `/api/questions/batch-type` | `batch_update_question_type` | [backend/app/api/v1/catalog/questions.py:1573](../../backend/app/api/v1/catalog/questions.py#L1573) |
| `GET` | `/api/questions/count-by-category` | `count_questions_by_category` | [backend/app/api/v1/catalog/questions.py:393](../../backend/app/api/v1/catalog/questions.py#L393) |
| `GET` | `/api/questions/exercise/questions` | `get_exercise_questions` | [backend/app/api/v1/catalog/questions.py:464](../../backend/app/api/v1/catalog/questions.py#L464) |
| `GET` | `/api/questions/favorites` | `list_favorites` | [backend/app/api/v1/catalog/question_actions.py:52](../../backend/app/api/v1/catalog/question_actions.py#L52) |
| `POST` | `/api/questions/file-import` | `import_questions_from_file` | [backend/app/api/v1/catalog/questions.py:1282](../../backend/app/api/v1/catalog/questions.py#L1282) |
| `GET` | `/api/questions/group/{group_id}` | `get_question_group` | [backend/app/api/v1/catalog/questions.py:590](../../backend/app/api/v1/catalog/questions.py#L590) |
| `POST` | `/api/questions/group/{group_id}/images` | `upload_group_image` | [backend/app/api/v1/catalog/questions.py:1064](../../backend/app/api/v1/catalog/questions.py#L1064) |
| `POST` | `/api/questions/group/{group_id}/ocr-apply` | `apply_group_ocr` | [backend/app/api/v1/catalog/questions.py:1034](../../backend/app/api/v1/catalog/questions.py#L1034) |
| `GET` | `/api/questions/group/{group_id}/ocr-candidates` | `get_group_ocr_candidates` | [backend/app/api/v1/catalog/questions.py:1016](../../backend/app/api/v1/catalog/questions.py#L1016) |
| `POST` | `/api/questions/import/batch-answers` | `batch_import_answers` | [backend/app/api/v1/catalog/question_import.py:1769](../../backend/app/api/v1/catalog/question_import.py#L1769) |
| `POST` | `/api/questions/import/batch-parsed` | `batch_import_parsed` | [backend/app/api/v1/catalog/question_import.py:1322](../../backend/app/api/v1/catalog/question_import.py#L1322) |
| `POST` | `/api/questions/import/confirm` | `confirm_batch_import` | [backend/app/api/v1/catalog/question_import.py:2551](../../backend/app/api/v1/catalog/question_import.py#L2551) |
| `POST` | `/api/questions/import/image` | `import_from_image` | [backend/app/api/v1/catalog/question_import.py:4350](../../backend/app/api/v1/catalog/question_import.py#L4350) |
| `GET` | `/api/questions/import/mineru-health` | `mineru_health` | [backend/app/api/v1/catalog/question_import.py:3766](../../backend/app/api/v1/catalog/question_import.py#L3766) |
| `POST` | `/api/questions/import/ocr` | `ocr_recognize` | [backend/app/api/v1/catalog/question_import.py:4250](../../backend/app/api/v1/catalog/question_import.py#L4250) |
| `GET` | `/api/questions/import/ocr/status` | `ocr_status` | [backend/app/api/v1/catalog/question_import.py:4340](../../backend/app/api/v1/catalog/question_import.py#L4340) |
| `POST` | `/api/questions/import/parse` | `unified_parse` | [backend/app/api/v1/catalog/question_import.py:3788](../../backend/app/api/v1/catalog/question_import.py#L3788) |
| `GET` | `/api/questions/import/records` | `get_import_records` | [backend/app/api/v1/catalog/question_import.py:4710](../../backend/app/api/v1/catalog/question_import.py#L4710) |
| `POST` | `/api/questions/import/records/{import_id}/attach-image` | `attach_image_to_preview_question` | [backend/app/api/v1/catalog/question_import.py:2390](../../backend/app/api/v1/catalog/question_import.py#L2390) |
| `GET` | `/api/questions/import/records/{import_id}/status` | `get_import_parse_status` | [backend/app/api/v1/catalog/question_import.py:2293](../../backend/app/api/v1/catalog/question_import.py#L2293) |
| `POST` | `/api/questions/import/separate-match` | `separate_match_endpoint` | [backend/app/api/v1/catalog/question_import.py:3121](../../backend/app/api/v1/catalog/question_import.py#L3121) |
| `POST` | `/api/questions/import/separate-match-xingce` | `separate_match_xingce_endpoint` | [backend/app/api/v1/catalog/question_import.py:3451](../../backend/app/api/v1/catalog/question_import.py#L3451) |
| `POST` | `/api/questions/import/single` | `import_single_question` | [backend/app/api/v1/catalog/question_import.py:1148](../../backend/app/api/v1/catalog/question_import.py#L1148) |
| `GET` | `/api/questions/import/stats` | `get_import_stats` | [backend/app/api/v1/catalog/question_import.py:4757](../../backend/app/api/v1/catalog/question_import.py#L4757) |
| `GET` | `/api/questions/import/taxonomy` | `get_taxonomy` | [backend/app/api/v1/catalog/question_import.py:4937](../../backend/app/api/v1/catalog/question_import.py#L4937) |
| `PUT` | `/api/questions/import/update-answer/{question_id}` | `update_question_answer` | [backend/app/api/v1/catalog/question_import.py:1702](../../backend/app/api/v1/catalog/question_import.py#L1702) |
| `POST` | `/api/questions/import/upload` | `upload_file_for_import` | [backend/app/api/v1/catalog/question_import.py:2186](../../backend/app/api/v1/catalog/question_import.py#L2186) |
| `GET` | `/api/questions/random` | `get_random_questions` | [backend/app/api/v1/catalog/questions.py:305](../../backend/app/api/v1/catalog/questions.py#L305) |
| `POST` | `/api/questions/random-draw` | `random_draw_questions` | [backend/app/api/v1/catalog/questions.py:1225](../../backend/app/api/v1/catalog/questions.py#L1225) |
| `GET` | `/api/questions/subcategory-stats` | `subcategory_stats` | [backend/app/api/v1/catalog/questions.py:400](../../backend/app/api/v1/catalog/questions.py#L400) |
| `GET` | `/api/questions/unclassified` | `get_unclassified` | [backend/app/api/v1/catalog/questions.py:1484](../../backend/app/api/v1/catalog/questions.py#L1484) |
| `DELETE` | `/api/questions/{question_id}` | `delete_question` | [backend/app/api/v1/catalog/questions.py:846](../../backend/app/api/v1/catalog/questions.py#L846) |
| `GET` | `/api/questions/{question_id}` | `get_question_detail` | [backend/app/api/v1/catalog/questions.py:664](../../backend/app/api/v1/catalog/questions.py#L664) |
| `PUT` | `/api/questions/{question_id}` | `update_question` | [backend/app/api/v1/catalog/questions.py:741](../../backend/app/api/v1/catalog/questions.py#L741) |
| `GET` | `/api/questions/{question_id}/actions` | `get_question_actions` | [backend/app/api/v1/catalog/question_actions.py:244](../../backend/app/api/v1/catalog/question_actions.py#L244) |
| `PATCH` | `/api/questions/{question_id}/explanation` | `update_question_explanation` | [backend/app/api/v1/catalog/questions.py:1632](../../backend/app/api/v1/catalog/questions.py#L1632) |
| `POST` | `/api/questions/{question_id}/favorite` | `toggle_favorite` | [backend/app/api/v1/catalog/question_actions.py:22](../../backend/app/api/v1/catalog/question_actions.py#L22) |
| `POST` | `/api/questions/{question_id}/images` | `upload_question_image` | [backend/app/api/v1/catalog/questions.py:888](../../backend/app/api/v1/catalog/questions.py#L888) |
| `DELETE` | `/api/questions/{question_id}/marker` | `remove_marker` | [backend/app/api/v1/catalog/question_actions.py:222](../../backend/app/api/v1/catalog/question_actions.py#L222) |
| `POST` | `/api/questions/{question_id}/marker` | `upsert_marker` | [backend/app/api/v1/catalog/question_actions.py:180](../../backend/app/api/v1/catalog/question_actions.py#L180) |
| `DELETE` | `/api/questions/{question_id}/note` | `delete_note` | [backend/app/api/v1/catalog/question_actions.py:158](../../backend/app/api/v1/catalog/question_actions.py#L158) |
| `GET` | `/api/questions/{question_id}/note` | `get_note` | [backend/app/api/v1/catalog/question_actions.py:135](../../backend/app/api/v1/catalog/question_actions.py#L135) |
| `POST` | `/api/questions/{question_id}/note` | `upsert_note` | [backend/app/api/v1/catalog/question_actions.py:97](../../backend/app/api/v1/catalog/question_actions.py#L97) |
| `POST` | `/api/questions/{question_id}/ocr-apply` | `apply_question_ocr` | [backend/app/api/v1/catalog/questions.py:995](../../backend/app/api/v1/catalog/questions.py#L995) |
| `GET` | `/api/questions/{question_id}/ocr-candidates` | `get_question_ocr_candidates` | [backend/app/api/v1/catalog/questions.py:970](../../backend/app/api/v1/catalog/questions.py#L970) |
| `POST` | `/api/questions/{question_id}/reclassify` | `reclassify_question` | [backend/app/api/v1/catalog/questions.py:1356](../../backend/app/api/v1/catalog/questions.py#L1356) |
| `PATCH` | `/api/questions/{question_id}/type` | `update_question_type` | [backend/app/api/v1/catalog/questions.py:1525](../../backend/app/api/v1/catalog/questions.py#L1525) |
| `GET` | `/api/smart-exam/{paper_id}/preview` | `preview_paper` | [backend/app/api/v1/catalog/papers.py:218](../../backend/app/api/v1/catalog/papers.py#L218) |
| `POST` | `/api/teacher/papers` | `create_paper` | [backend/app/api/v1/catalog/papers.py:70](../../backend/app/api/v1/catalog/papers.py#L70) |
| `POST` | `/api/teacher/papers/auto-generate` | `auto_generate_paper` | [backend/app/api/v1/catalog/paper_generation.py:115](../../backend/app/api/v1/catalog/paper_generation.py#L115) |
| `DELETE` | `/api/teacher/papers/{paper_id}` | `delete_paper` | [backend/app/api/v1/catalog/papers.py:172](../../backend/app/api/v1/catalog/papers.py#L172) |
| `PUT` | `/api/teacher/papers/{paper_id}` | `update_paper` | [backend/app/api/v1/catalog/papers.py:136](../../backend/app/api/v1/catalog/papers.py#L136) |
| `POST` | `/api/teacher/papers/{paper_id}/questions` | `add_questions_to_paper` | [backend/app/api/v1/catalog/papers.py:254](../../backend/app/api/v1/catalog/papers.py#L254) |
| `DELETE` | `/api/teacher/papers/{paper_id}/questions/{question_id}` | `remove_question_from_paper` | [backend/app/api/v1/catalog/papers.py:306](../../backend/app/api/v1/catalog/papers.py#L306) |
| `POST` | `/api/teacher/papers/{paper_id}/submit-approval` | `submit_for_approval` | [backend/app/api/v1/catalog/papers.py:341](../../backend/app/api/v1/catalog/papers.py#L341) |
| `DELETE` | `/api/teacher/questions/{question_id}` | `delete_question` | [backend/app/api/v1/catalog/questions.py:846](../../backend/app/api/v1/catalog/questions.py#L846) |
| `PUT` | `/api/teacher/questions/{question_id}` | `update_question` | [backend/app/api/v1/catalog/questions.py:741](../../backend/app/api/v1/catalog/questions.py#L741) |
| `GET` | `/api/wrong-questions` | `get_wrong_questions` | [backend/app/api/v1/catalog/wrong_questions.py:102](../../backend/app/api/v1/catalog/wrong_questions.py#L102) |
| `POST` | `/api/wrong-questions/collect` | `collect_wrong_question` | [backend/app/api/v1/catalog/wrong_questions.py:169](../../backend/app/api/v1/catalog/wrong_questions.py#L169) |
| `GET` | `/api/wrong-questions/review/queue` | `get_review_queue` | [backend/app/api/v1/catalog/wrong_questions.py:421](../../backend/app/api/v1/catalog/wrong_questions.py#L421) |
| `POST` | `/api/wrong-questions/review/submit` | `submit_review` | [backend/app/api/v1/catalog/wrong_questions.py:706](../../backend/app/api/v1/catalog/wrong_questions.py#L706) |
| `GET` | `/api/wrong-questions/subcategories` | `get_subcategories` | [backend/app/api/v1/catalog/wrong_questions.py:386](../../backend/app/api/v1/catalog/wrong_questions.py#L386) |
| `GET` | `/api/wrong-questions/zhanti/expiring` | `get_zhanti_expiring` | [backend/app/api/v1/catalog/wrong_questions.py:577](../../backend/app/api/v1/catalog/wrong_questions.py#L577) |
| `GET` | `/api/wrong-questions/zhanti/list` | `get_zhanti_list` | [backend/app/api/v1/catalog/wrong_questions.py:517](../../backend/app/api/v1/catalog/wrong_questions.py#L517) |
| `DELETE` | `/api/wrong-questions/{wrong_id}` | `delete_wrong_question` | [backend/app/api/v1/catalog/wrong_questions.py:240](../../backend/app/api/v1/catalog/wrong_questions.py#L240) |
| `PUT` | `/api/wrong-questions/{wrong_id}/chop` | `chop_question` | [backend/app/api/v1/catalog/wrong_questions.py:474](../../backend/app/api/v1/catalog/wrong_questions.py#L474) |
| `GET` | `/api/wrong-questions/{wrong_id}/detail` | `get_wrong_question_detail` | [backend/app/api/v1/catalog/wrong_questions.py:600](../../backend/app/api/v1/catalog/wrong_questions.py#L600) |
| `PUT` | `/api/wrong-questions/{wrong_id}/mastery` | `update_mastery` | [backend/app/api/v1/catalog/wrong_questions.py:260](../../backend/app/api/v1/catalog/wrong_questions.py#L260) |
| `POST` | `/api/wrong-questions/{wrong_id}/unchop` | `unchop_question` | [backend/app/api/v1/catalog/wrong_questions.py:684](../../backend/app/api/v1/catalog/wrong_questions.py#L684) |

### 平台域（管理端/教师端/通知/反馈/WebSocket）（`platform`，88 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/admin/announcements` | `list_announcements` | [backend/app/api/v1/platform/admin.py:649](../../backend/app/api/v1/platform/admin.py#L649) |
| `POST` | `/api/admin/announcements` | `create_announcement` | [backend/app/api/v1/platform/admin.py:679](../../backend/app/api/v1/platform/admin.py#L679) |
| `DELETE` | `/api/admin/announcements/{announcement_id}` | `delete_announcement` | [backend/app/api/v1/platform/admin.py:725](../../backend/app/api/v1/platform/admin.py#L725) |
| `PUT` | `/api/admin/announcements/{announcement_id}` | `update_announcement` | [backend/app/api/v1/platform/admin.py:703](../../backend/app/api/v1/platform/admin.py#L703) |
| `GET` | `/api/admin/approval/papers` | `list_approval_papers` | [backend/app/api/v1/platform/admin_approval.py:65](../../backend/app/api/v1/platform/admin_approval.py#L65) |
| `GET` | `/api/admin/approval/papers/{paper_id}` | `get_approval_detail` | [backend/app/api/v1/platform/admin_approval.py:150](../../backend/app/api/v1/platform/admin_approval.py#L150) |
| `GET` | `/api/admin/approval/papers/{paper_id}/issues` | `get_paper_issues` | [backend/app/api/v1/platform/admin_approval.py:341](../../backend/app/api/v1/platform/admin_approval.py#L341) |
| `GET` | `/api/admin/approval/papers/{paper_id}/logs` | `get_approval_logs` | [backend/app/api/v1/platform/admin_approval.py:311](../../backend/app/api/v1/platform/admin_approval.py#L311) |
| `POST` | `/api/admin/approval/papers/{paper_id}/reject` | `reject_paper` | [backend/app/api/v1/platform/admin_approval.py:269](../../backend/app/api/v1/platform/admin_approval.py#L269) |
| `POST` | `/api/admin/backup` | `create_backup` | [backend/app/api/v1/platform/admin.py:926](../../backend/app/api/v1/platform/admin.py#L926) |
| `GET` | `/api/admin/backup/stats` | `get_backup_stats` | [backend/app/api/v1/platform/admin.py:879](../../backend/app/api/v1/platform/admin.py#L879) |
| `GET` | `/api/admin/backups` | `list_backups` | [backend/app/api/v1/platform/admin.py:987](../../backend/app/api/v1/platform/admin.py#L987) |
| `POST` | `/api/admin/backups/{backup_id}/restore` | `restore_backup` | [backend/app/api/v1/platform/admin.py:1012](../../backend/app/api/v1/platform/admin.py#L1012) |
| `GET` | `/api/admin/feedback` | `list_all_feedback` | [backend/app/api/v1/platform/feedback.py:224](../../backend/app/api/v1/platform/feedback.py#L224) |
| `POST` | `/api/admin/feedback/{feedback_id}/reply` | `reply_feedback` | [backend/app/api/v1/platform/feedback.py:250](../../backend/app/api/v1/platform/feedback.py#L250) |
| `GET` | `/api/admin/logs` | `list_operation_logs` | [backend/app/api/v1/platform/admin.py:746](../../backend/app/api/v1/platform/admin.py#L746) |
| `GET` | `/api/admin/logs/errors` | `get_error_logs` | [backend/app/api/v1/platform/admin.py:797](../../backend/app/api/v1/platform/admin.py#L797) |
| `GET` | `/api/admin/logs/export` | `export_operation_logs` | [backend/app/api/v1/platform/admin.py:823](../../backend/app/api/v1/platform/admin.py#L823) |
| `GET` | `/api/admin/news/pending` | `pending_news` | [backend/app/api/v1/platform/admin_news.py:23](../../backend/app/api/v1/platform/admin_news.py#L23) |
| `POST` | `/api/admin/news/{news_id}/review` | `review_news` | [backend/app/api/v1/platform/admin_news.py:48](../../backend/app/api/v1/platform/admin_news.py#L48) |
| `GET` | `/api/admin/permissions` | `get_permissions` | [backend/app/api/v1/platform/admin.py:1111](../../backend/app/api/v1/platform/admin.py#L1111) |
| `PUT` | `/api/admin/permissions` | `update_permissions` | [backend/app/api/v1/platform/admin.py:1149](../../backend/app/api/v1/platform/admin.py#L1149) |
| `GET` | `/api/admin/questions` | `list_all_questions` | [backend/app/api/v1/platform/admin.py:490](../../backend/app/api/v1/platform/admin.py#L490) |
| `GET` | `/api/admin/questions/stats` | `get_question_stats` | [backend/app/api/v1/platform/admin.py:454](../../backend/app/api/v1/platform/admin.py#L454) |
| `PUT` | `/api/admin/questions/{question_id}/archive` | `archive_question` | [backend/app/api/v1/platform/admin.py:628](../../backend/app/api/v1/platform/admin.py#L628) |
| `PUT` | `/api/admin/questions/{question_id}/audit` | `audit_question` | [backend/app/api/v1/platform/admin.py:603](../../backend/app/api/v1/platform/admin.py#L603) |
| `GET` | `/api/admin/settings` | `get_settings` | [backend/app/api/v1/platform/admin.py:1039](../../backend/app/api/v1/platform/admin.py#L1039) |
| `PUT` | `/api/admin/settings` | `update_settings` | [backend/app/api/v1/platform/admin.py:1056](../../backend/app/api/v1/platform/admin.py#L1056) |
| `GET` | `/api/admin/users` | `list_users` | [backend/app/api/v1/platform/admin.py:299](../../backend/app/api/v1/platform/admin.py#L299) |
| `POST` | `/api/admin/users` | `create_user` | [backend/app/api/v1/platform/admin.py:337](../../backend/app/api/v1/platform/admin.py#L337) |
| `PUT` | `/api/admin/users/{user_id}` | `update_user` | [backend/app/api/v1/platform/admin.py:378](../../backend/app/api/v1/platform/admin.py#L378) |
| `PUT` | `/api/admin/users/{user_id}/disable` | `toggle_disable_user` | [backend/app/api/v1/platform/admin.py:401](../../backend/app/api/v1/platform/admin.py#L401) |
| `PUT` | `/api/admin/users/{user_id}/reset-password` | `reset_user_password` | [backend/app/api/v1/platform/admin.py:426](../../backend/app/api/v1/platform/admin.py#L426) |
| `POST` | `/api/feedback` | `submit_feedback` | [backend/app/api/v1/platform/feedback.py:87](../../backend/app/api/v1/platform/feedback.py#L87) |
| `GET` | `/api/feedback/faq` | `get_faq` | [backend/app/api/v1/platform/feedback.py:51](../../backend/app/api/v1/platform/feedback.py#L51) |
| `GET` | `/api/feedback/my` | `my_feedback` | [backend/app/api/v1/platform/feedback.py:204](../../backend/app/api/v1/platform/feedback.py#L204) |
| `GET` | `/api/feedback/{feedback_id}` | `get_feedback_detail` | [backend/app/api/v1/platform/feedback.py:138](../../backend/app/api/v1/platform/feedback.py#L138) |
| `POST` | `/api/feedback/{feedback_id}/reply` | `reply_own_feedback` | [backend/app/api/v1/platform/feedback.py:172](../../backend/app/api/v1/platform/feedback.py#L172) |
| `POST` | `/api/llm/chat` | `chat` | [backend/app/api/v1/platform/llm.py:84](../../backend/app/api/v1/platform/llm.py#L84) |
| `GET` | `/api/llm/context/assemble` | `assemble_context_api` | [backend/app/api/v1/platform/llm.py:307](../../backend/app/api/v1/platform/llm.py#L307) |
| `GET` | `/api/llm/sessions` | `list_sessions` | [backend/app/api/v1/platform/llm.py:213](../../backend/app/api/v1/platform/llm.py#L213) |
| `POST` | `/api/llm/sessions` | `create_session` | [backend/app/api/v1/platform/llm.py:246](../../backend/app/api/v1/platform/llm.py#L246) |
| `DELETE` | `/api/llm/sessions/{session_id}` | `delete_session` | [backend/app/api/v1/platform/llm.py:294](../../backend/app/api/v1/platform/llm.py#L294) |
| `GET` | `/api/llm/sessions/{session_id}/messages` | `session_messages` | [backend/app/api/v1/platform/llm.py:267](../../backend/app/api/v1/platform/llm.py#L267) |
| `GET` | `/api/notifications` | `list_notifications` | [backend/app/api/v1/platform/notifications.py:33](../../backend/app/api/v1/platform/notifications.py#L33) |
| `PUT` | `/api/notifications/read-all` | `mark_all_read` | [backend/app/api/v1/platform/notifications.py:92](../../backend/app/api/v1/platform/notifications.py#L92) |
| `PUT` | `/api/notifications/{notification_id}/read` | `mark_read` | [backend/app/api/v1/platform/notifications.py:71](../../backend/app/api/v1/platform/notifications.py#L71) |
| `GET` | `/api/teacher/analytics/knowledge-mastery` | `get_knowledge_mastery` | [backend/app/api/v1/platform/teacher.py:2289](../../backend/app/api/v1/platform/teacher.py#L2289) |
| `GET` | `/api/teacher/analytics/overview` | `get_analytics_overview` | [backend/app/api/v1/platform/teacher.py:2112](../../backend/app/api/v1/platform/teacher.py#L2112) |
| `GET` | `/api/teacher/analytics/question-usage` | `get_question_usage` | [backend/app/api/v1/platform/teacher.py:2257](../../backend/app/api/v1/platform/teacher.py#L2257) |
| `GET` | `/api/teacher/classes` | `list_teacher_classes` | [backend/app/api/v1/platform/teacher.py:1797](../../backend/app/api/v1/platform/teacher.py#L1797) |
| `POST` | `/api/teacher/classes` | `create_class` | [backend/app/api/v1/platform/teacher.py:1839](../../backend/app/api/v1/platform/teacher.py#L1839) |
| `DELETE` | `/api/teacher/classes/{class_id}` | `delete_class` | [backend/app/api/v1/platform/teacher.py:1908](../../backend/app/api/v1/platform/teacher.py#L1908) |
| `GET` | `/api/teacher/classes/{class_id}` | `get_class_detail` | [backend/app/api/v1/platform/teacher.py:1861](../../backend/app/api/v1/platform/teacher.py#L1861) |
| `POST` | `/api/teacher/classes/{class_id}/students` | `add_students_to_class` | [backend/app/api/v1/platform/teacher.py:1926](../../backend/app/api/v1/platform/teacher.py#L1926) |
| `DELETE` | `/api/teacher/classes/{class_id}/students/{user_id}` | `remove_student_from_class` | [backend/app/api/v1/platform/teacher.py:1951](../../backend/app/api/v1/platform/teacher.py#L1951) |
| `GET` | `/api/teacher/knowledge-points` | `list_knowledge_points` | [backend/app/api/v1/platform/teacher.py:308](../../backend/app/api/v1/platform/teacher.py#L308) |
| `GET` | `/api/teacher/messages` | `list_teacher_messages` | [backend/app/api/v1/platform/teacher.py:1975](../../backend/app/api/v1/platform/teacher.py#L1975) |
| `PUT` | `/api/teacher/messages/read-all` | `mark_all_read` | [backend/app/api/v1/platform/notifications.py:92](../../backend/app/api/v1/platform/notifications.py#L92) |
| `GET` | `/api/teacher/messages/unread-count` | `get_unread_count` | [backend/app/api/v1/platform/teacher.py:2053](../../backend/app/api/v1/platform/teacher.py#L2053) |
| `PUT` | `/api/teacher/messages/{message_id}/read` | `mark_message_read` | [backend/app/api/v1/platform/teacher.py:2071](../../backend/app/api/v1/platform/teacher.py#L2071) |
| `GET` | `/api/teacher/papers` | `list_teacher_papers` | [backend/app/api/v1/platform/teacher.py:625](../../backend/app/api/v1/platform/teacher.py#L625) |
| `GET` | `/api/teacher/papers/stats` | `paper_stats` | [backend/app/api/v1/platform/teacher.py:685](../../backend/app/api/v1/platform/teacher.py#L685) |
| `GET` | `/api/teacher/papers/{paper_id}` | `get_teacher_paper_detail` | [backend/app/api/v1/platform/teacher.py:708](../../backend/app/api/v1/platform/teacher.py#L708) |
| `DELETE` | `/api/teacher/papers/{paper_id}/permanent` | `permanent_delete_paper` | [backend/app/api/v1/platform/teacher.py:872](../../backend/app/api/v1/platform/teacher.py#L872) |
| `POST` | `/api/teacher/papers/{paper_id}/publish` | `publish_teacher_paper` | [backend/app/api/v1/platform/teacher.py:1363](../../backend/app/api/v1/platform/teacher.py#L1363) |
| `PUT` | `/api/teacher/papers/{paper_id}/questions/order` | `reorder_paper_questions` | [backend/app/api/v1/platform/teacher.py:977](../../backend/app/api/v1/platform/teacher.py#L977) |
| `PUT` | `/api/teacher/papers/{paper_id}/questions/{question_id}` | `update_paper_question_score` | [backend/app/api/v1/platform/teacher.py:1005](../../backend/app/api/v1/platform/teacher.py#L1005) |
| `PUT` | `/api/teacher/papers/{paper_id}/questions/{question_id}/content` | `update_paper_question_content` | [backend/app/api/v1/platform/teacher.py:1041](../../backend/app/api/v1/platform/teacher.py#L1041) |
| `POST` | `/api/teacher/papers/{paper_id}/questions/{question_id}/replace` | `replace_paper_question` | [backend/app/api/v1/platform/teacher.py:1183](../../backend/app/api/v1/platform/teacher.py#L1183) |
| `POST` | `/api/teacher/papers/{paper_id}/restore` | `restore_paper` | [backend/app/api/v1/platform/teacher.py:850](../../backend/app/api/v1/platform/teacher.py#L850) |
| `GET` | `/api/teacher/profile` | `get_teacher_profile` | [backend/app/api/v1/platform/teacher.py:1652](../../backend/app/api/v1/platform/teacher.py#L1652) |
| `PUT` | `/api/teacher/profile` | `update_teacher_profile` | [backend/app/api/v1/platform/teacher.py:1703](../../backend/app/api/v1/platform/teacher.py#L1703) |
| `GET` | `/api/teacher/question-types` | `list_question_types` | [backend/app/api/v1/platform/teacher.py:277](../../backend/app/api/v1/platform/teacher.py#L277) |
| `GET` | `/api/teacher/questions` | `list_teacher_questions` | [backend/app/api/v1/platform/teacher.py:336](../../backend/app/api/v1/platform/teacher.py#L336) |
| `POST` | `/api/teacher/questions` | `create_teacher_question` | [backend/app/api/v1/platform/teacher.py:414](../../backend/app/api/v1/platform/teacher.py#L414) |
| `POST` | `/api/teacher/questions/batch-delete` | `batch_delete_questions` | [backend/app/api/v1/platform/teacher.py:524](../../backend/app/api/v1/platform/teacher.py#L524) |
| `POST` | `/api/teacher/questions/batch-reclassify` | `batch_reclassify_questions` | [backend/app/api/v1/platform/teacher.py:545](../../backend/app/api/v1/platform/teacher.py#L545) |
| `GET` | `/api/teacher/questions/{question_id}/images` | `get_question_images` | [backend/app/api/v1/platform/teacher.py:578](../../backend/app/api/v1/platform/teacher.py#L578) |
| `GET` | `/api/teacher/scores/class-compare` | `compare_class_scores` | [backend/app/api/v1/platform/teacher.py:1533](../../backend/app/api/v1/platform/teacher.py#L1533) |
| `GET` | `/api/teacher/scores/class/{class_id}` | `get_class_scores` | [backend/app/api/v1/platform/teacher.py:1496](../../backend/app/api/v1/platform/teacher.py#L1496) |
| `GET` | `/api/teacher/scores/overview` | `get_score_overview` | [backend/app/api/v1/platform/teacher.py:1398](../../backend/app/api/v1/platform/teacher.py#L1398) |
| `GET` | `/api/teacher/scores/question-stats/{paper_id}` | `get_question_stats` | [backend/app/api/v1/platform/admin.py:454](../../backend/app/api/v1/platform/admin.py#L454) |
| `GET` | `/api/teacher/scores/student/{user_id}` | `get_student_score_detail` | [backend/app/api/v1/platform/teacher.py:1570](../../backend/app/api/v1/platform/teacher.py#L1570) |
| `POST` | `/ws/broadcast` | `broadcast_message` | [backend/app/api/v1/platform/websocket.py:426](../../backend/app/api/v1/platform/websocket.py#L426) |
| `POST` | `/ws/notify/{user_id}` | `send_user_notification` | [backend/app/api/v1/platform/websocket.py:409](../../backend/app/api/v1/platform/websocket.py#L409) |
| `GET` | `/ws/online_users` | `get_online_users` | [backend/app/api/v1/platform/websocket.py:396](../../backend/app/api/v1/platform/websocket.py#L396) |
| `GET` | `/ws/room/{room_name}` | `get_room_users` | [backend/app/api/v1/platform/websocket.py:401](../../backend/app/api/v1/platform/websocket.py#L401) |

### 社区域（论坛/举报/治理）（`community`，56 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/admin/forum/comments` | `admin_comments` | [backend/app/api/v1/community/forum_moderation.py:382](../../backend/app/api/v1/community/forum_moderation.py#L382) |
| `DELETE` | `/api/admin/forum/comments/{comment_id}` | `admin_delete_comment` | [backend/app/api/v1/community/forum_moderation.py:445](../../backend/app/api/v1/community/forum_moderation.py#L445) |
| `DELETE` | `/api/admin/forum/comments/{comment_id}/purge` | `purge_comment` | [backend/app/api/v1/community/forum_moderation.py:683](../../backend/app/api/v1/community/forum_moderation.py#L683) |
| `POST` | `/api/admin/forum/comments/{comment_id}/restore` | `restore_comment` | [backend/app/api/v1/community/forum_moderation.py:647](../../backend/app/api/v1/community/forum_moderation.py#L647) |
| `GET` | `/api/admin/forum/moderation` | `moderation_queue` | [backend/app/api/v1/community/forum_moderation.py:476](../../backend/app/api/v1/community/forum_moderation.py#L476) |
| `POST` | `/api/admin/forum/moderation/{moderation_id}/approve` | `approve_moderation` | [backend/app/api/v1/community/forum_moderation.py:546](../../backend/app/api/v1/community/forum_moderation.py#L546) |
| `POST` | `/api/admin/forum/moderation/{moderation_id}/reject` | `reject_moderation` | [backend/app/api/v1/community/forum_moderation.py:566](../../backend/app/api/v1/community/forum_moderation.py#L566) |
| `GET` | `/api/admin/forum/posts` | `admin_posts` | [backend/app/api/v1/community/forum_moderation.py:324](../../backend/app/api/v1/community/forum_moderation.py#L324) |
| `DELETE` | `/api/admin/forum/posts/{post_id}` | `admin_delete_post` | [backend/app/api/v1/community/forum_moderation.py:414](../../backend/app/api/v1/community/forum_moderation.py#L414) |
| `DELETE` | `/api/admin/forum/posts/{post_id}/purge` | `purge_post` | [backend/app/api/v1/community/forum_moderation.py:665](../../backend/app/api/v1/community/forum_moderation.py#L665) |
| `POST` | `/api/admin/forum/posts/{post_id}/restore` | `restore_post` | [backend/app/api/v1/community/forum_moderation.py:629](../../backend/app/api/v1/community/forum_moderation.py#L629) |
| `GET` | `/api/admin/forum/recycle` | `recycle_bin` | [backend/app/api/v1/community/forum_moderation.py:594](../../backend/app/api/v1/community/forum_moderation.py#L594) |
| `GET` | `/api/admin/forum/recycle/audit` | `recycle_audit` | [backend/app/api/v1/community/forum_moderation.py:586](../../backend/app/api/v1/community/forum_moderation.py#L586) |
| `GET` | `/api/admin/practice-admins` | `list_practice_admins` | [backend/app/api/v1/community/practice_admin.py:63](../../backend/app/api/v1/community/practice_admin.py#L63) |
| `POST` | `/api/admin/practice-admins` | `grant_teacher` | [backend/app/api/v1/community/practice_admin.py:91](../../backend/app/api/v1/community/practice_admin.py#L91) |
| `DELETE` | `/api/admin/practice-admins/{user_id}` | `revoke_teacher` | [backend/app/api/v1/community/practice_admin.py:139](../../backend/app/api/v1/community/practice_admin.py#L139) |
| `DELETE` | `/api/forum/comments/{comment_id}` | `delete_comment` | [backend/app/api/v1/community/forum.py:1756](../../backend/app/api/v1/community/forum.py#L1756) |
| `POST` | `/api/forum/comments/{comment_id}/like` | `toggle_comment_like` | [backend/app/api/v1/community/forum.py:1060](../../backend/app/api/v1/community/forum.py#L1060) |
| `PUT` | `/api/forum/comments/{comment_id}/pin` | `pin_comment` | [backend/app/api/v1/community/forum.py:1731](../../backend/app/api/v1/community/forum.py#L1731) |
| `DELETE` | `/api/forum/comments/{comment_id}/reactions` | `clear_comment_reaction` | [backend/app/api/v1/community/forum.py:1247](../../backend/app/api/v1/community/forum.py#L1247) |
| `POST` | `/api/forum/comments/{comment_id}/reactions/{reaction_code}` | `set_comment_reaction` | [backend/app/api/v1/community/forum.py:1235](../../backend/app/api/v1/community/forum.py#L1235) |
| `GET` | `/api/forum/my-favorites` | `get_my_favorites` | [backend/app/api/v1/community/forum.py:756](../../backend/app/api/v1/community/forum.py#L756) |
| `GET` | `/api/forum/my-likes` | `get_my_likes` | [backend/app/api/v1/community/forum.py:812](../../backend/app/api/v1/community/forum.py#L812) |
| `GET` | `/api/forum/my-posts` | `get_my_posts` | [backend/app/api/v1/community/forum.py:1514](../../backend/app/api/v1/community/forum.py#L1514) |
| `GET` | `/api/forum/posts` | `get_forum_posts` | [backend/app/api/v1/community/forum.py:344](../../backend/app/api/v1/community/forum.py#L344) |
| `POST` | `/api/forum/posts` | `create_post` | [backend/app/api/v1/community/forum.py:510](../../backend/app/api/v1/community/forum.py#L510) |
| `DELETE` | `/api/forum/posts/{post_id}` | `delete_post` | [backend/app/api/v1/community/forum.py:629](../../backend/app/api/v1/community/forum.py#L629) |
| `GET` | `/api/forum/posts/{post_id}` | `get_post_detail` | [backend/app/api/v1/community/forum.py:452](../../backend/app/api/v1/community/forum.py#L452) |
| `PUT` | `/api/forum/posts/{post_id}` | `update_post` | [backend/app/api/v1/community/forum.py:1667](../../backend/app/api/v1/community/forum.py#L1667) |
| `GET` | `/api/forum/posts/{post_id}/comments` | `get_post_comments` | [backend/app/api/v1/community/forum.py:871](../../backend/app/api/v1/community/forum.py#L871) |
| `POST` | `/api/forum/posts/{post_id}/comments` | `create_comment` | [backend/app/api/v1/community/forum.py:963](../../backend/app/api/v1/community/forum.py#L963) |
| `POST` | `/api/forum/posts/{post_id}/favorite` | `toggle_post_favorite` | [backend/app/api/v1/community/forum.py:714](../../backend/app/api/v1/community/forum.py#L714) |
| `POST` | `/api/forum/posts/{post_id}/like` | `toggle_post_like` | [backend/app/api/v1/community/forum.py:660](../../backend/app/api/v1/community/forum.py#L660) |
| `DELETE` | `/api/forum/posts/{post_id}/reactions` | `clear_post_reaction` | [backend/app/api/v1/community/forum.py:1226](../../backend/app/api/v1/community/forum.py#L1226) |
| `POST` | `/api/forum/posts/{post_id}/reactions/{reaction_code}` | `set_post_reaction` | [backend/app/api/v1/community/forum.py:1166](../../backend/app/api/v1/community/forum.py#L1166) |
| `POST` | `/api/forum/reports` | `create_forum_report` | [backend/app/api/v1/community/forum.py:1592](../../backend/app/api/v1/community/forum.py#L1592) |
| `GET` | `/api/forum/stats` | `get_forum_stats` | [backend/app/api/v1/community/forum.py:1556](../../backend/app/api/v1/community/forum.py#L1556) |
| `GET` | `/api/forum/stickers` | `list_stickers` | [backend/app/api/v1/community/forum.py:1273](../../backend/app/api/v1/community/forum.py#L1273) |
| `POST` | `/api/forum/stickers` | `upload_sticker` | [backend/app/api/v1/community/forum.py:1293](../../backend/app/api/v1/community/forum.py#L1293) |
| `DELETE` | `/api/forum/stickers/{sticker_id}` | `delete_sticker` | [backend/app/api/v1/community/forum.py:1336](../../backend/app/api/v1/community/forum.py#L1336) |
| `POST` | `/api/forum/upload` | `upload_attachment` | [backend/app/api/v1/community/forum.py:1357](../../backend/app/api/v1/community/forum.py#L1357) |
| `GET` | `/api/forum/users/{user_id}/public` | `get_user_public` | [backend/app/api/v1/community/forum.py:1467](../../backend/app/api/v1/community/forum.py#L1467) |
| `GET` | `/api/quotes` | `get_quotes` | [backend/app/api/v1/community/quotes.py:238](../../backend/app/api/v1/community/quotes.py#L238) |
| `POST` | `/api/quotes` | `create_quote` | [backend/app/api/v1/community/quotes.py:372](../../backend/app/api/v1/community/quotes.py#L372) |
| `GET` | `/api/quotes/favorites` | `get_quote_favorites` | [backend/app/api/v1/community/quotes.py:477](../../backend/app/api/v1/community/quotes.py#L477) |
| `POST` | `/api/quotes/obsidian/{obsidian_source}/favorite` | `toggle_obsidian_quote_favorite` | [backend/app/api/v1/community/quotes.py:440](../../backend/app/api/v1/community/quotes.py#L440) |
| `GET` | `/api/quotes/quote/daily` | `get_daily_quote` | [backend/app/api/v1/community/quotes.py:165](../../backend/app/api/v1/community/quotes.py#L165) |
| `GET` | `/api/quotes/random` | `get_random_quote` | [backend/app/api/v1/community/quotes.py:322](../../backend/app/api/v1/community/quotes.py#L322) |
| `POST` | `/api/quotes/{quote_id}/favorite` | `toggle_quote_favorite` | [backend/app/api/v1/community/quotes.py:406](../../backend/app/api/v1/community/quotes.py#L406) |
| `POST` | `/api/teacher/forum/comments/{comment_id}/hide` | `hide_comment` | [backend/app/api/v1/community/forum_moderation.py:308](../../backend/app/api/v1/community/forum_moderation.py#L308) |
| `GET` | `/api/teacher/forum/posts` | `teacher_posts` | [backend/app/api/v1/community/forum_moderation.py:133](../../backend/app/api/v1/community/forum_moderation.py#L133) |
| `GET` | `/api/teacher/forum/posts/{post_id}/comments` | `teacher_comments` | [backend/app/api/v1/community/forum_moderation.py:208](../../backend/app/api/v1/community/forum_moderation.py#L208) |
| `POST` | `/api/teacher/forum/posts/{post_id}/hide` | `hide_post` | [backend/app/api/v1/community/forum_moderation.py:294](../../backend/app/api/v1/community/forum_moderation.py#L294) |
| `GET` | `/api/teacher/practice-admins` | `list_student_practice_admins` | [backend/app/api/v1/community/practice_admin.py:167](../../backend/app/api/v1/community/practice_admin.py#L167) |
| `POST` | `/api/teacher/practice-admins` | `grant_student` | [backend/app/api/v1/community/practice_admin.py:198](../../backend/app/api/v1/community/practice_admin.py#L198) |
| `DELETE` | `/api/teacher/practice-admins/{user_id}` | `revoke_student` | [backend/app/api/v1/community/practice_admin.py:247](../../backend/app/api/v1/community/practice_admin.py#L247) |

### 考试域（考试执行/成绩/练习）（`exam`，54 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/admin/dashboard` | `get_dashboard` | [backend/app/api/v1/exam/stats.py:439](../../backend/app/api/v1/exam/stats.py#L439) |
| `POST` | `/api/exam-records/ai/analyze` | `ai_analyze_wrong_questions` | [backend/app/api/v1/exam/exam_records.py:410](../../backend/app/api/v1/exam/exam_records.py#L410) |
| `GET` | `/api/exam-records/mock` | `get_mock_exam_records` | [backend/app/api/v1/exam/exam_records.py:78](../../backend/app/api/v1/exam/exam_records.py#L78) |
| `GET` | `/api/exam-records/self` | `get_self_test_records` | [backend/app/api/v1/exam/exam_records.py:28](../../backend/app/api/v1/exam/exam_records.py#L28) |
| `GET` | `/api/exam-records/stats` | `get_exam_stats` | [backend/app/api/v1/exam/exam_records.py:140](../../backend/app/api/v1/exam/exam_records.py#L140) |
| `GET` | `/api/exam-records/summary` | `get_exam_summary` | [backend/app/api/v1/exam/exam_records.py:480](../../backend/app/api/v1/exam/exam_records.py#L480) |
| `GET` | `/api/exam-records/trend` | `get_exam_trend` | [backend/app/api/v1/exam/exam_records.py:211](../../backend/app/api/v1/exam/exam_records.py#L211) |
| `GET` | `/api/exam-records/{record_id}/details` | `get_exam_record_details` | [backend/app/api/v1/exam/exam_records.py:349](../../backend/app/api/v1/exam/exam_records.py#L349) |
| `GET` | `/api/exams/all` | `get_all_exam_records` | [backend/app/api/v1/exam/exams.py:560](../../backend/app/api/v1/exam/exams.py#L560) |
| `GET` | `/api/exams/list` | `get_exams_list` | [backend/app/api/v1/exam/exams.py:33](../../backend/app/api/v1/exam/exams.py#L33) |
| `GET` | `/api/exams/preview/{paper_id}` | `preview_exam` | [backend/app/api/v1/exam/exams.py:652](../../backend/app/api/v1/exam/exams.py#L652) |
| `GET` | `/api/exams/records` | `get_my_exam_records` | [backend/app/api/v1/exam/exams.py:442](../../backend/app/api/v1/exam/exams.py#L442) |
| `GET` | `/api/exams/records/{record_id}` | `get_exam_record_detail` | [backend/app/api/v1/exam/exams.py:491](../../backend/app/api/v1/exam/exams.py#L491) |
| `POST` | `/api/exams/start` | `start_exam_new` | [backend/app/api/v1/exam/exams.py:596](../../backend/app/api/v1/exam/exams.py#L596) |
| `PUT` | `/api/exams/{exam_id}/progress` | `save_exam_progress` | [backend/app/api/v1/exam/exams.py:632](../../backend/app/api/v1/exam/exams.py#L632) |
| `POST` | `/api/exams/{exam_id}/submit` | `submit_exam_new` | [backend/app/api/v1/exam/exams.py:614](../../backend/app/api/v1/exam/exams.py#L614) |
| `GET` | `/api/exams/{paper_id}` | `get_exam_detail` | [backend/app/api/v1/exam/exams.py:93](../../backend/app/api/v1/exam/exams.py#L93) |
| `GET` | `/api/exams/{paper_id}/questions` | `get_paper_questions` | [backend/app/api/v1/exam/exams.py:129](../../backend/app/api/v1/exam/exams.py#L129) |
| `POST` | `/api/exams/{paper_id}/start` | `start_exam` | [backend/app/api/v1/exam/exams.py:231](../../backend/app/api/v1/exam/exams.py#L231) |
| `POST` | `/api/exams/{record_id}/submit` | `submit_answers` | [backend/app/api/v1/exam/exams.py:303](../../backend/app/api/v1/exam/exams.py#L303) |
| `POST` | `/api/practice/batch-record` | `batch_record_practice` | [backend/app/api/v1/exam/practice.py:139](../../backend/app/api/v1/exam/practice.py#L139) |
| `GET` | `/api/practice/knowledge-progress` | `get_knowledge_progress` | [backend/app/api/v1/exam/practice.py:598](../../backend/app/api/v1/exam/practice.py#L598) |
| `GET` | `/api/practice/recent-records` | `get_recent_records` | [backend/app/api/v1/exam/practice.py:707](../../backend/app/api/v1/exam/practice.py#L707) |
| `POST` | `/api/practice/record` | `record_practice` | [backend/app/api/v1/exam/practice.py:75](../../backend/app/api/v1/exam/practice.py#L75) |
| `GET` | `/api/practice/records` | `get_practice_records` | [backend/app/api/v1/exam/practice.py:205](../../backend/app/api/v1/exam/practice.py#L205) |
| `GET` | `/api/practice/stats-card` | `get_practice_stats_card` | [backend/app/api/v1/exam/practice.py:343](../../backend/app/api/v1/exam/practice.py#L343) |
| `GET` | `/api/practice/type-summary` | `get_practice_type_summary` | [backend/app/api/v1/exam/practice.py:262](../../backend/app/api/v1/exam/practice.py#L262) |
| `GET` | `/api/practice/unified-stats` | `get_unified_practice_stats` | [backend/app/api/v1/exam/practice.py:448](../../backend/app/api/v1/exam/practice.py#L448) |
| `GET` | `/api/quick-practice/knowledge-points` | `get_knowledge_points` | [backend/app/api/v1/exam/quick_practice.py:295](../../backend/app/api/v1/exam/quick_practice.py#L295) |
| `GET` | `/api/quick-practice/questions` | `get_practice_questions` | [backend/app/api/v1/exam/quick_practice.py:335](../../backend/app/api/v1/exam/quick_practice.py#L335) |
| `GET` | `/api/quick-practice/sub-categories` | `get_sub_categories` | [backend/app/api/v1/exam/quick_practice.py:151](../../backend/app/api/v1/exam/quick_practice.py#L151) |
| `GET` | `/api/quick-practice/subjects` | `get_subjects` | [backend/app/api/v1/exam/quick_practice.py:124](../../backend/app/api/v1/exam/quick_practice.py#L124) |
| `POST` | `/api/quick-practice/submit` | `submit_practice` | [backend/app/api/v1/exam/quick_practice.py:491](../../backend/app/api/v1/exam/quick_practice.py#L491) |
| `POST` | `/api/smart-exam/generate` | `smart_generate_paper` | [backend/app/api/v1/exam/smart_exam.py:154](../../backend/app/api/v1/exam/smart_exam.py#L154) |
| `GET` | `/api/smart-exam/records` | `get_smart_exam_records` | [backend/app/api/v1/exam/smart_exam.py:1150](../../backend/app/api/v1/exam/smart_exam.py#L1150) |
| `DELETE` | `/api/smart-exam/records/{record_id}` | `delete_smart_exam_record` | [backend/app/api/v1/exam/smart_exam.py:1263](../../backend/app/api/v1/exam/smart_exam.py#L1263) |
| `GET` | `/api/smart-exam/records/{record_id}` | `get_smart_exam_record_detail` | [backend/app/api/v1/exam/smart_exam.py:1200](../../backend/app/api/v1/exam/smart_exam.py#L1200) |
| `POST` | `/api/smart-exam/{paper_id}/confirm` | `confirm_paper` | [backend/app/api/v1/exam/smart_exam.py:712](../../backend/app/api/v1/exam/smart_exam.py#L712) |
| `POST` | `/api/smart-exam/{paper_id}/replace/{question_id}` | `replace_question` | [backend/app/api/v1/exam/smart_exam.py:427](../../backend/app/api/v1/exam/smart_exam.py#L427) |
| `POST` | `/api/smart-exam/{paper_id}/save-progress` | `save_progress` | [backend/app/api/v1/exam/smart_exam.py:848](../../backend/app/api/v1/exam/smart_exam.py#L848) |
| `POST` | `/api/smart-exam/{paper_id}/start` | `start_smart_exam` | [backend/app/api/v1/exam/smart_exam.py:758](../../backend/app/api/v1/exam/smart_exam.py#L758) |
| `POST` | `/api/smart-exam/{paper_id}/submit` | `submit_smart_exam` | [backend/app/api/v1/exam/smart_exam.py:896](../../backend/app/api/v1/exam/smart_exam.py#L896) |
| `GET` | `/api/stats/` | `get_study_stats` | [backend/app/api/v1/exam/stats.py:29](../../backend/app/api/v1/exam/stats.py#L29) |
| `GET` | `/api/stats/all-time` | `get_all_time_stats` | [backend/app/api/v1/exam/stats.py:214](../../backend/app/api/v1/exam/stats.py#L214) |
| `POST` | `/api/stats/auto-checkin` | `auto_checkin` | [backend/app/api/v1/exam/stats.py:686](../../backend/app/api/v1/exam/stats.py#L686) |
| `GET` | `/api/stats/calendar` | `get_exam_calendar` | [backend/app/api/v1/exam/stats.py:371](../../backend/app/api/v1/exam/stats.py#L371) |
| `GET` | `/api/stats/dashboard` | `get_dashboard` | [backend/app/api/v1/exam/stats.py:439](../../backend/app/api/v1/exam/stats.py#L439) |
| `GET` | `/api/stats/level` | `get_level` | [backend/app/api/v1/exam/stats.py:132](../../backend/app/api/v1/exam/stats.py#L132) |
| `GET` | `/api/stats/messages` | `get_system_messages` | [backend/app/api/v1/exam/stats.py:397](../../backend/app/api/v1/exam/stats.py#L397) |
| `GET` | `/api/stats/practice-trend` | `get_practice_trend` | [backend/app/api/v1/exam/stats.py:535](../../backend/app/api/v1/exam/stats.py#L535) |
| `GET` | `/api/stats/type-mastery` | `get_type_mastery` | [backend/app/api/v1/exam/stats.py:311](../../backend/app/api/v1/exam/stats.py#L311) |
| `GET` | `/api/stats/weekly` | `get_weekly_stats` | [backend/app/api/v1/exam/stats.py:141](../../backend/app/api/v1/exam/stats.py#L141) |
| `GET` | `/api/stats/weekly-checkin` | `get_weekly_checkin` | [backend/app/api/v1/exam/stats.py:726](../../backend/app/api/v1/exam/stats.py#L726) |
| `GET` | `/api/teacher/dashboard` | `get_dashboard` | [backend/app/api/v1/exam/stats.py:439](../../backend/app/api/v1/exam/stats.py#L439) |

### 资料域（备考资料/个人库/上传/图片）（`library`，46 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/materials` | `list_materials` | [backend/app/api/v1/library/materials.py:77](../../backend/app/api/v1/library/materials.py#L77) |
| `POST` | `/api/materials/admin` | `admin_create` | [backend/app/api/v1/library/materials.py:1452](../../backend/app/api/v1/library/materials.py#L1452) |
| `DELETE` | `/api/materials/admin/batch` | `admin_batch_delete` | [backend/app/api/v1/library/materials.py:1614](../../backend/app/api/v1/library/materials.py#L1614) |
| `POST` | `/api/materials/admin/batch` | `admin_batch_create` | [backend/app/api/v1/library/materials.py:1584](../../backend/app/api/v1/library/materials.py#L1584) |
| `POST` | `/api/materials/admin/cards/batch-image` | `batch_image` | [backend/app/api/v1/library/materials.py:520](../../backend/app/api/v1/library/materials.py#L520) |
| `GET` | `/api/materials/admin/import-records` | `admin_import_records` | [backend/app/api/v1/library/materials.py:1641](../../backend/app/api/v1/library/materials.py#L1641) |
| `POST` | `/api/materials/admin/import/upload` | `import_upload` | [backend/app/api/v1/library/materials.py:1768](../../backend/app/api/v1/library/materials.py#L1768) |
| `POST` | `/api/materials/admin/import/{import_id}/confirm` | `import_confirm` | [backend/app/api/v1/library/materials.py:1932](../../backend/app/api/v1/library/materials.py#L1932) |
| `GET` | `/api/materials/admin/import/{import_id}/preview` | `import_preview` | [backend/app/api/v1/library/materials.py:1910](../../backend/app/api/v1/library/materials.py#L1910) |
| `GET` | `/api/materials/admin/import/{import_id}/status` | `import_status` | [backend/app/api/v1/library/materials.py:1895](../../backend/app/api/v1/library/materials.py#L1895) |
| `GET` | `/api/materials/admin/list` | `admin_list` | [backend/app/api/v1/library/materials.py:1417](../../backend/app/api/v1/library/materials.py#L1417) |
| `GET` | `/api/materials/admin/rules` | `admin_rule_list` | [backend/app/api/v1/library/materials.py:1310](../../backend/app/api/v1/library/materials.py#L1310) |
| `POST` | `/api/materials/admin/rules` | `admin_rule_create` | [backend/app/api/v1/library/materials.py:1332](../../backend/app/api/v1/library/materials.py#L1332) |
| `PUT` | `/api/materials/admin/rules/{rule_id}` | `admin_rule_update` | [backend/app/api/v1/library/materials.py:1357](../../backend/app/api/v1/library/materials.py#L1357) |
| `PATCH` | `/api/materials/admin/rules/{rule_id}/toggle` | `admin_rule_toggle` | [backend/app/api/v1/library/materials.py:1395](../../backend/app/api/v1/library/materials.py#L1395) |
| `GET` | `/api/materials/admin/stats` | `admin_stats` | [backend/app/api/v1/library/materials.py:1533](../../backend/app/api/v1/library/materials.py#L1533) |
| `POST` | `/api/materials/admin/upload/image` | `upload_image` | [backend/app/api/v1/library/image_media.py:62](../../backend/app/api/v1/library/image_media.py#L62) |
| `DELETE` | `/api/materials/admin/{material_id}` | `admin_delete` | [backend/app/api/v1/library/materials.py:1512](../../backend/app/api/v1/library/materials.py#L1512) |
| `PUT` | `/api/materials/admin/{material_id}` | `admin_update` | [backend/app/api/v1/library/materials.py:1468](../../backend/app/api/v1/library/materials.py#L1468) |
| `PUT` | `/api/materials/admin/{material_id}/status` | `admin_set_status` | [backend/app/api/v1/library/materials.py:1492](../../backend/app/api/v1/library/materials.py#L1492) |
| `GET` | `/api/materials/favorites` | `my_favorites` | [backend/app/api/v1/library/materials.py:150](../../backend/app/api/v1/library/materials.py#L150) |
| `GET` | `/api/materials/my` | `my_list` | [backend/app/api/v1/library/materials.py:450](../../backend/app/api/v1/library/materials.py#L450) |
| `POST` | `/api/materials/my` | `my_create` | [backend/app/api/v1/library/materials.py:311](../../backend/app/api/v1/library/materials.py#L311) |
| `POST` | `/api/materials/my/card` | `my_create_card` | [backend/app/api/v1/library/materials.py:334](../../backend/app/api/v1/library/materials.py#L334) |
| `POST` | `/api/materials/my/upload` | `my_upload` | [backend/app/api/v1/library/materials.py:2108](../../backend/app/api/v1/library/materials.py#L2108) |
| `DELETE` | `/api/materials/my/{material_id}` | `my_delete` | [backend/app/api/v1/library/materials.py:502](../../backend/app/api/v1/library/materials.py#L502) |
| `PUT` | `/api/materials/my/{material_id}` | `my_update` | [backend/app/api/v1/library/materials.py:474](../../backend/app/api/v1/library/materials.py#L474) |
| `POST` | `/api/materials/progress` | `report_progress` | [backend/app/api/v1/library/materials.py:215](../../backend/app/api/v1/library/materials.py#L215) |
| `GET` | `/api/materials/progress-summary` | `progress_summary` | [backend/app/api/v1/library/materials.py:131](../../backend/app/api/v1/library/materials.py#L131) |
| `GET` | `/api/materials/shared` | `shared_list` | [backend/app/api/v1/library/materials.py:565](../../backend/app/api/v1/library/materials.py#L565) |
| `GET` | `/api/materials/taxonomy` | `material_taxonomy` | [backend/app/api/v1/library/materials.py:107](../../backend/app/api/v1/library/materials.py#L107) |
| `GET` | `/api/materials/{material_id}` | `material_detail` | [backend/app/api/v1/library/materials.py:697](../../backend/app/api/v1/library/materials.py#L697) |
| `POST` | `/api/materials/{material_id}/adopt` | `adopt_material` | [backend/app/api/v1/library/materials.py:651](../../backend/app/api/v1/library/materials.py#L651) |
| `POST` | `/api/materials/{material_id}/share` | `share_material` | [backend/app/api/v1/library/materials.py:604](../../backend/app/api/v1/library/materials.py#L604) |
| `POST` | `/api/materials/{material_id}/unshare` | `unshare_material` | [backend/app/api/v1/library/materials.py:631](../../backend/app/api/v1/library/materials.py#L631) |
| `GET` | `/api/media/export` | `export_data` | [backend/app/api/v1/library/media.py:90](../../backend/app/api/v1/library/media.py#L90) |
| `POST` | `/api/media/import` | `import_data` | [backend/app/api/v1/library/media.py:63](../../backend/app/api/v1/library/media.py#L63) |
| `POST` | `/api/media/upload` | `upload_video` | [backend/app/api/v1/library/media.py:16](../../backend/app/api/v1/library/media.py#L16) |
| `GET` | `/api/video/list` | `get_video_list` | [backend/app/api/v1/library/videos.py:35](../../backend/app/api/v1/library/videos.py#L35) |
| `POST` | `/api/video/upload` | `upload_video` | [backend/app/api/v1/library/media.py:16](../../backend/app/api/v1/library/media.py#L16) |
| `POST` | `/api/video/upload/chunk` | `upload_chunk` | [backend/app/api/v1/library/videos.py:203](../../backend/app/api/v1/library/videos.py#L203) |
| `POST` | `/api/video/upload/complete` | `complete_chunk_upload` | [backend/app/api/v1/library/videos.py:226](../../backend/app/api/v1/library/videos.py#L226) |
| `POST` | `/api/video/upload/init` | `init_chunk_upload` | [backend/app/api/v1/library/videos.py:161](../../backend/app/api/v1/library/videos.py#L161) |
| `DELETE` | `/api/video/{video_id}` | `delete_video` | [backend/app/api/v1/library/videos.py:412](../../backend/app/api/v1/library/videos.py#L412) |
| `GET` | `/api/video/{video_id}` | `get_video_info` | [backend/app/api/v1/library/videos.py:66](../../backend/app/api/v1/library/videos.py#L66) |
| `GET` | `/api/video/{video_id}/stream` | `stream_video` | [backend/app/api/v1/library/videos.py:344](../../backend/app/api/v1/library/videos.py#L344) |

### 成长域（成就/金币/目标/学习计划）（`growth`，36 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/achievements` | `list_achievements` | [backend/app/api/v1/growth/achievements.py:61](../../backend/app/api/v1/growth/achievements.py#L61) |
| `POST` | `/api/achievements/admin` | `admin_create_achievement` | [backend/app/api/v1/growth/achievements.py:162](../../backend/app/api/v1/growth/achievements.py#L162) |
| `GET` | `/api/achievements/earned` | `earned_achievements` | [backend/app/api/v1/growth/achievements.py:105](../../backend/app/api/v1/growth/achievements.py#L105) |
| `GET` | `/api/achievements/name-bank/status` | `name_bank_status` | [backend/app/api/v1/growth/achievements.py:227](../../backend/app/api/v1/growth/achievements.py#L227) |
| `GET` | `/api/achievements/progress` | `progress_achievements` | [backend/app/api/v1/growth/achievements.py:133](../../backend/app/api/v1/growth/achievements.py#L133) |
| `GET` | `/api/goals/` | `get_my_goals` | [backend/app/api/v1/growth/goals.py:66](../../backend/app/api/v1/growth/goals.py#L66) |
| `POST` | `/api/goals/` | `create_goal` | [backend/app/api/v1/growth/goals.py:112](../../backend/app/api/v1/growth/goals.py#L112) |
| `POST` | `/api/goals/batch-confirm` | `batch_confirm_goals` | [backend/app/api/v1/growth/goals.py:479](../../backend/app/api/v1/growth/goals.py#L479) |
| `GET` | `/api/goals/stats/summary` | `get_goal_stats` | [backend/app/api/v1/growth/goals.py:651](../../backend/app/api/v1/growth/goals.py#L651) |
| `GET` | `/api/goals/status/completed` | `get_completed_goals` | [backend/app/api/v1/growth/goals.py:546](../../backend/app/api/v1/growth/goals.py#L546) |
| `GET` | `/api/goals/status/pending` | `get_pending_goals` | [backend/app/api/v1/growth/goals.py:598](../../backend/app/api/v1/growth/goals.py#L598) |
| `DELETE` | `/api/goals/{goal_id}` | `delete_goal` | [backend/app/api/v1/growth/goals.py:202](../../backend/app/api/v1/growth/goals.py#L202) |
| `GET` | `/api/goals/{goal_id}` | `get_goal_detail` | [backend/app/api/v1/growth/goals.py:93](../../backend/app/api/v1/growth/goals.py#L93) |
| `PUT` | `/api/goals/{goal_id}` | `update_goal` | [backend/app/api/v1/growth/goals.py:150](../../backend/app/api/v1/growth/goals.py#L150) |
| `POST` | `/api/goals/{goal_id}/complete` | `complete_goal` | [backend/app/api/v1/growth/goals.py:346](../../backend/app/api/v1/growth/goals.py#L346) |
| `POST` | `/api/goals/{goal_id}/confirm-complete` | `confirm_goal_complete` | [backend/app/api/v1/growth/goals.py:274](../../backend/app/api/v1/growth/goals.py#L274) |
| `POST` | `/api/goals/{goal_id}/progress` | `update_goal_progress` | [backend/app/api/v1/growth/goals.py:229](../../backend/app/api/v1/growth/goals.py#L229) |
| `POST` | `/api/goals/{goal_id}/undo-complete` | `undo_goal_complete` | [backend/app/api/v1/growth/goals.py:416](../../backend/app/api/v1/growth/goals.py#L416) |
| `POST` | `/api/plan/adjust` | `adjust_plan` | [backend/app/api/v1/growth/study_plan.py:229](../../backend/app/api/v1/growth/study_plan.py#L229) |
| `GET` | `/api/plan/current` | `current_plan` | [backend/app/api/v1/growth/study_plan.py:344](../../backend/app/api/v1/growth/study_plan.py#L344) |
| `POST` | `/api/plan/generate` | `generate_plan` | [backend/app/api/v1/growth/study_plan.py:74](../../backend/app/api/v1/growth/study_plan.py#L74) |
| `GET` | `/api/plan/notifies` | `get_notifies` | [backend/app/api/v1/growth/study_plan.py:682](../../backend/app/api/v1/growth/study_plan.py#L682) |
| `POST` | `/api/plan/notify/{notify_id}/read` | `mark_notify_read` | [backend/app/api/v1/growth/study_plan.py:708](../../backend/app/api/v1/growth/study_plan.py#L708) |
| `POST` | `/api/plan/task/{goal_id}/claim` | `claim_task_coin` | [backend/app/api/v1/growth/study_plan.py:579](../../backend/app/api/v1/growth/study_plan.py#L579) |
| `POST` | `/api/plan/task/{goal_id}/toggle` | `toggle_task` | [backend/app/api/v1/growth/study_plan.py:432](../../backend/app/api/v1/growth/study_plan.py#L432) |
| `GET` | `/api/plan/today` | `today_tasks` | [backend/app/api/v1/growth/study_plan.py:549](../../backend/app/api/v1/growth/study_plan.py#L549) |
| `DELETE` | `/api/plan/{plan_id}` | `delete_plan` | [backend/app/api/v1/growth/study_plan.py:509](../../backend/app/api/v1/growth/study_plan.py#L509) |
| `GET` | `/api/plan/{plan_id}/tasks` | `plan_tasks` | [backend/app/api/v1/growth/study_plan.py:460](../../backend/app/api/v1/growth/study_plan.py#L460) |
| `GET` | `/api/profile` | `get_profile` | [backend/app/api/v1/growth/profile.py:284](../../backend/app/api/v1/growth/profile.py#L284) |
| `GET` | `/api/profile/questions` | `get_question_templates` | [backend/app/api/v1/growth/profile.py:246](../../backend/app/api/v1/growth/profile.py#L246) |
| `POST` | `/api/profile/upsert` | `upsert_profile` | [backend/app/api/v1/growth/profile.py:293](../../backend/app/api/v1/growth/profile.py#L293) |
| `GET` | `/api/tasks/overview` | `overview` | [backend/app/api/v1/growth/tasks.py:167](../../backend/app/api/v1/growth/tasks.py#L167) |
| `POST` | `/api/tasks/random/refresh` | `refresh_random` | [backend/app/api/v1/growth/tasks.py:213](../../backend/app/api/v1/growth/tasks.py#L213) |
| `POST` | `/api/tasks/{task_id}/claim` | `claim_task` | [backend/app/api/v1/growth/tasks.py:276](../../backend/app/api/v1/growth/tasks.py#L276) |
| `POST` | `/api/v1/growth/checkin` | `do_checkin` | [backend/app/api/v1/growth/checkin.py:29](../../backend/app/api/v1/growth/checkin.py#L29) |
| `GET` | `/api/v1/growth/checkin/status` | `checkin_status` | [backend/app/api/v1/growth/checkin.py:60](../../backend/app/api/v1/growth/checkin.py#L60) |

### 身份域（登录/注册/设备/二维码）（`identity`，18 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `POST` | `/api/auth/avatar` | `upload_avatar` | [backend/app/api/v1/identity/auth.py:476](../../backend/app/api/v1/identity/auth.py#L476) |
| `POST` | `/api/auth/change-password` | `change_password` | [backend/app/api/v1/identity/auth.py:412](../../backend/app/api/v1/identity/auth.py#L412) |
| `GET` | `/api/auth/devices/` | `list_devices` | [backend/app/api/v1/identity/devices.py:29](../../backend/app/api/v1/identity/devices.py#L29) |
| `POST` | `/api/auth/devices/revoke-all` | `revoke_all_devices` | [backend/app/api/v1/identity/devices.py:65](../../backend/app/api/v1/identity/devices.py#L65) |
| `DELETE` | `/api/auth/devices/{device_id}` | `remove_device` | [backend/app/api/v1/identity/devices.py:47](../../backend/app/api/v1/identity/devices.py#L47) |
| `POST` | `/api/auth/login` | `login_for_access_token` | [backend/app/api/v1/identity/auth.py:96](../../backend/app/api/v1/identity/auth.py#L96) |
| `POST` | `/api/auth/logout` | `logout_user` | [backend/app/api/v1/identity/auth.py:372](../../backend/app/api/v1/identity/auth.py#L372) |
| `GET` | `/api/auth/profile` | `get_user_profile` | [backend/app/api/v1/identity/auth.py:397](../../backend/app/api/v1/identity/auth.py#L397) |
| `PUT` | `/api/auth/profile` | `update_user_profile` | [backend/app/api/v1/identity/auth.py:433](../../backend/app/api/v1/identity/auth.py#L433) |
| `POST` | `/api/auth/qrcode/generate` | `generate_qrcode` | [backend/app/api/v1/identity/auth_qrcode.py:58](../../backend/app/api/v1/identity/auth_qrcode.py#L58) |
| `POST` | `/api/auth/qrcode/{qr_uuid}/confirm` | `confirm_login` | [backend/app/api/v1/identity/auth_qrcode.py:121](../../backend/app/api/v1/identity/auth_qrcode.py#L121) |
| `GET` | `/api/auth/qrcode/{qr_uuid}/info` | `get_pc_info` | [backend/app/api/v1/identity/auth_qrcode.py:108](../../backend/app/api/v1/identity/auth_qrcode.py#L108) |
| `GET` | `/api/auth/qrcode/{qr_uuid}/status` | `check_status` | [backend/app/api/v1/identity/auth_qrcode.py:148](../../backend/app/api/v1/identity/auth_qrcode.py#L148) |
| `POST` | `/api/auth/refresh` | `refresh_access_token` | [backend/app/api/v1/identity/auth.py:330](../../backend/app/api/v1/identity/auth.py#L330) |
| `POST` | `/api/auth/register` | `register_user` | [backend/app/api/v1/identity/auth.py:214](../../backend/app/api/v1/identity/auth.py#L214) |
| `POST` | `/api/auth/sms-login` | `sms_login` | [backend/app/api/v1/identity/auth.py:262](../../backend/app/api/v1/identity/auth.py#L262) |
| `POST` | `/api/teacher/profile/avatar` | `upload_avatar` | [backend/app/api/v1/identity/auth.py:476](../../backend/app/api/v1/identity/auth.py#L476) |
| `POST` | `/api/teacher/profile/change-password` | `change_password` | [backend/app/api/v1/identity/auth.py:412](../../backend/app/api/v1/identity/auth.py#L412) |

### 内容域（新闻/招聘/日历）（`content`，15 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/calendar/exams` | `get_exams` | [backend/app/api/v1/content/calendar.py:67](../../backend/app/api/v1/content/calendar.py#L67) |
| `GET` | `/api/calendar/latest` | `get_latest_exam` | [backend/app/api/v1/content/calendar.py:100](../../backend/app/api/v1/content/calendar.py#L100) |
| `GET` | `/api/news` | `get_news` | [backend/app/api/v1/content/news.py:89](../../backend/app/api/v1/content/news.py#L89) |
| `GET` | `/api/news/categories` | `get_news_categories` | [backend/app/api/v1/content/news.py:170](../../backend/app/api/v1/content/news.py#L170) |
| `GET` | `/api/news/digest` | `news_digest` | [backend/app/api/v1/content/news.py:178](../../backend/app/api/v1/content/news.py#L178) |
| `GET` | `/api/news/favorites` | `get_favorites` | [backend/app/api/v1/content/news.py:378](../../backend/app/api/v1/content/news.py#L378) |
| `GET` | `/api/news/timeline` | `news_timeline` | [backend/app/api/v1/content/news.py:242](../../backend/app/api/v1/content/news.py#L242) |
| `GET` | `/api/news/today` | `get_today_news` | [backend/app/api/v1/content/news.py:288](../../backend/app/api/v1/content/news.py#L288) |
| `GET` | `/api/news/{news_id}` | `get_news_detail` | [backend/app/api/v1/content/news.py:414](../../backend/app/api/v1/content/news.py#L414) |
| `POST` | `/api/news/{news_id}/note` | `save_note` | [backend/app/api/v1/content/news.py:485](../../backend/app/api/v1/content/news.py#L485) |
| `GET` | `/api/news/{news_id}/notes` | `get_notes` | [backend/app/api/v1/content/news.py:513](../../backend/app/api/v1/content/news.py#L513) |
| `GET` | `/api/notes` | `get_notes` | [backend/app/api/v1/content/news.py:513](../../backend/app/api/v1/content/news.py#L513) |
| `GET` | `/api/recruitment` | `get_recruitment` | [backend/app/api/v1/content/recruitment.py:85](../../backend/app/api/v1/content/recruitment.py#L85) |
| `GET` | `/api/recruitment/categories` | `get_recruitment_categories` | [backend/app/api/v1/content/recruitment.py:179](../../backend/app/api/v1/content/recruitment.py#L179) |
| `GET` | `/api/recruitment/{recruitment_id}` | `get_recruitment_detail` | [backend/app/api/v1/content/recruitment.py:187](../../backend/app/api/v1/content/recruitment.py#L187) |

### 知识图谱（`knowledge`，14 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/knowledge/categories` | `list_categories` | [backend/app/api/v1/knowledge.py:53](../../backend/app/api/v1/knowledge.py#L53) |
| `GET` | `/api/knowledge/graph` | `knowledge_graph` | [backend/app/api/v1/knowledge.py:156](../../backend/app/api/v1/knowledge.py#L156) |
| `GET` | `/api/knowledge/nodes` | `list_nodes` | [backend/app/api/v1/knowledge.py:58](../../backend/app/api/v1/knowledge.py#L58) |
| `POST` | `/api/knowledge/nodes` | `submit_node` | [backend/app/api/v1/knowledge.py:99](../../backend/app/api/v1/knowledge.py#L99) |
| `POST` | `/api/knowledge/nodes/{node_id}/approve` | `approve_node` | [backend/app/api/v1/knowledge.py:124](../../backend/app/api/v1/knowledge.py#L124) |
| `GET` | `/api/knowledge/nodes/{node_id}/detail` | `node_detail` | [backend/app/api/v1/knowledge.py:215](../../backend/app/api/v1/knowledge.py#L215) |
| `POST` | `/api/knowledge/nodes/{node_id}/reject` | `reject_node` | [backend/app/api/v1/knowledge.py:141](../../backend/app/api/v1/knowledge.py#L141) |
| `POST` | `/api/knowledge/relation` | `create_relation` | [backend/app/api/v1/knowledge.py:276](../../backend/app/api/v1/knowledge.py#L276) |
| `POST` | `/api/knowledge/relation/suggest` | `suggest_relations` | [backend/app/api/v1/knowledge.py:352](../../backend/app/api/v1/knowledge.py#L352) |
| `DELETE` | `/api/knowledge/relation/{rel_id}` | `delete_relation` | [backend/app/api/v1/knowledge.py:338](../../backend/app/api/v1/knowledge.py#L338) |
| `GET` | `/api/knowledge/relations` | `list_relations` | [backend/app/api/v1/knowledge.py:312](../../backend/app/api/v1/knowledge.py#L312) |
| `GET` | `/api/knowledge/stats` | `knowledge_stats` | [backend/app/api/v1/knowledge.py:187](../../backend/app/api/v1/knowledge.py#L187) |
| `GET` | `/api/knowledge/vault` | `vault_info` | [backend/app/api/v1/knowledge.py:403](../../backend/app/api/v1/knowledge.py#L403) |
| `POST` | `/api/knowledge/vault/import` | `vault_import` | [backend/app/api/v1/knowledge.py:435](../../backend/app/api/v1/knowledge.py#L435) |

### 个人域（收藏/笔记）（`personal`，10 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/collection` | `get_collection` | [backend/app/api/v1/personal/collection.py:25](../../backend/app/api/v1/personal/collection.py#L25) |
| `GET` | `/api/collection/news-favorites` | `get_news_favorites` | [backend/app/api/v1/personal/collection.py:219](../../backend/app/api/v1/personal/collection.py#L219) |
| `GET` | `/api/collection/question-favorites` | `get_question_favorites` | [backend/app/api/v1/personal/collection.py:314](../../backend/app/api/v1/personal/collection.py#L314) |
| `GET` | `/api/collection/stats` | `get_collection_stats` | [backend/app/api/v1/personal/collection.py:363](../../backend/app/api/v1/personal/collection.py#L363) |
| `DELETE` | `/api/collection/{fav_id}` | `delete_favorite` | [backend/app/api/v1/personal/collection.py:142](../../backend/app/api/v1/personal/collection.py#L142) |
| `POST` | `/api/notes` | `create_or_update_note` | [backend/app/api/v1/personal/notes.py:91](../../backend/app/api/v1/personal/notes.py#L91) |
| `GET` | `/api/notes/news` | `get_news_notes` | [backend/app/api/v1/personal/notes.py:279](../../backend/app/api/v1/personal/notes.py#L279) |
| `GET` | `/api/notes/question` | `get_question_notes` | [backend/app/api/v1/personal/notes.py:315](../../backend/app/api/v1/personal/notes.py#L315) |
| `GET` | `/api/notes/stats` | `get_notes_stats` | [backend/app/api/v1/personal/notes.py:531](../../backend/app/api/v1/personal/notes.py#L531) |
| `PUT` | `/api/notes/{note_id}` | `update_note` | [backend/app/api/v1/personal/notes.py:186](../../backend/app/api/v1/personal/notes.py#L186) |

### 奖励域（金币流水）（`reward`，9 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/api/admin/shop/products` | `admin_list_products` | [backend/app/api/v1/reward/admin_shop.py:74](../../backend/app/api/v1/reward/admin_shop.py#L74) |
| `POST` | `/api/admin/shop/products` | `admin_create_product` | [backend/app/api/v1/reward/admin_shop.py:104](../../backend/app/api/v1/reward/admin_shop.py#L104) |
| `DELETE` | `/api/admin/shop/products/{product_id}` | `admin_delete_product` | [backend/app/api/v1/reward/admin_shop.py:151](../../backend/app/api/v1/reward/admin_shop.py#L151) |
| `PUT` | `/api/admin/shop/products/{product_id}` | `admin_update_product` | [backend/app/api/v1/reward/admin_shop.py:131](../../backend/app/api/v1/reward/admin_shop.py#L131) |
| `GET` | `/api/coins/overview` | `coins_overview` | [backend/app/api/v1/reward/coins.py:19](../../backend/app/api/v1/reward/coins.py#L19) |
| `GET` | `/api/coins/transactions` | `coins_transactions` | [backend/app/api/v1/reward/coins.py:46](../../backend/app/api/v1/reward/coins.py#L46) |
| `POST` | `/api/shop/exchange` | `exchange` | [backend/app/api/v1/reward/shop.py:91](../../backend/app/api/v1/reward/shop.py#L91) |
| `GET` | `/api/shop/products` | `list_products` | [backend/app/api/v1/reward/shop.py:51](../../backend/app/api/v1/reward/shop.py#L51) |
| `GET` | `/api/shop/products/{product_id}` | `get_product` | [backend/app/api/v1/reward/shop.py:80](../../backend/app/api/v1/reward/shop.py#L80) |

### Agent 路由（`agent`，6 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `POST` | `/api/agent/import-today` | `import_to_today` | [backend/app/api/v1/agent.py:138](../../backend/app/api/v1/agent.py#L138) |
| `GET` | `/api/agent/memories` | `agent_memories` | [backend/app/api/v1/agent.py:186](../../backend/app/api/v1/agent.py#L186) |
| `DELETE` | `/api/agent/memory/{memory_id}` | `agent_memory_delete` | [backend/app/api/v1/agent.py:214](../../backend/app/api/v1/agent.py#L214) |
| `POST` | `/api/agent/run` | `run_agent_task` | [backend/app/api/v1/agent.py:252](../../backend/app/api/v1/agent.py#L252) |
| `GET` | `/api/agent/tasks` | `list_agent_tasks` | [backend/app/api/v1/agent.py:247](../../backend/app/api/v1/agent.py#L247) |
| `GET` | `/api/agent/trajectory` | `agent_trajectory` | [backend/app/api/v1/agent.py:234](../../backend/app/api/v1/agent.py#L234) |

### 应用级（健康检查/指标/媒体代理）（`app-main`，6 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/health` | `health_check` | [backend/app/main.py:870](../../backend/app/main.py#L870) |
| `GET` | `/health/foundation` | `foundation_health` | [backend/app/main.py:881](../../backend/app/main.py#L881) |
| `GET` | `/metrics` | `get_metrics` | [backend/app/main.py:896](../../backend/app/main.py#L896) |
| `GET` | `/metrics/endpoints` | `get_endpoint_metrics` | [backend/app/main.py:926](../../backend/app/main.py#L926) |
| `POST` | `/metrics/reset` | `reset_metrics` | [backend/app/main.py:939](../../backend/app/main.py#L939) |
| `GET` | `/metrics/system` | `get_system_metrics_endpoint` | [backend/app/main.py:900](../../backend/app/main.py#L900) |

### 帖子（根级旧接口）（`post`，3 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `POST` | `/api/post/import` | `import_posts` | [backend/app/api/v1/post.py:40](../../backend/app/api/v1/post.py#L40) |
| `GET` | `/api/post/search` | `search_posts` | [backend/app/api/v1/post.py:83](../../backend/app/api/v1/post.py#L83) |
| `GET` | `/api/post/stats` | `post_stats` | [backend/app/api/v1/post.py:125](../../backend/app/api/v1/post.py#L125) |

### 媒体资产代理（`media_assets`，2 操作）

| 方法 | 路径 | 处理函数 | 代码位置 |
|---|---|---|---|
| `GET` | `/media/{asset_id}` | `get_media` | [backend/app/api/media_assets.py:105](../../backend/app/api/media_assets.py#L105) |
| `HEAD` | `/media/{asset_id}` | `get_media` | [backend/app/api/media_assets.py:105](../../backend/app/api/media_assets.py#L105) |

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

**基线**：远端 `main@6b0df0a`（2026-11-04）
