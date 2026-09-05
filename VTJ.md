# 砺安题库 - VTJ 项目架构记忆点

> 项目ID: `linxitie.policy-exam-bank` | 平台: web | 版本: 2.0.0

## 项目概览

- **项目名称**: 砺安题库（公安联考题库系统）
- **技术栈**: VTJ.PRO + Vue 3 + Element Plus + FastAPI
- **VTJ 项目仓库**: https://gitee.com/newgateway/vtj
- **VTJ 官网**: https://vtj.pro

## 三端分离架构

| 端 | 角色 | 路由前缀 | 仪表盘 |
|---|---|---|---|
| 学生端 | student | `/` `/home` | 无（首页） |
| 教师端 | teacher | `/teacher/*` | `/teacher/dashboard` |
| 管理员端 | admin | `/admin/*` | `/admin/dashboard` |

## 页面清单（31个）

### 公共页面
| ID | 路由 | 说明 | raw |
|---|---|---|---|
| login | `/login` | 用户登录 | ✅ |
| forum | `/forum` | 论坛 | ✅ |
| home_page | `/home` | 首页 | ✅ |
| question_bank | `/` | 题库主页 | ✅ |
| about | `/page/about` | 关于砺安题库 | ❌ |
| download_client | `/page/download_client` | 下载客户端 | ❌ |

### 学生端页面
| ID | 路由 | 说明 | needLogin |
|---|---|---|---|
| answer_page | `/answer` | 答题 | ❌ |
| smart_exam | `/smart-exam` | 智能组卷 | ✅ |
| smart_answer | `/smart-answer` | 智能组卷答题 | ✅ |
| student_papers | `/student/papers` | 历年试卷 | ✅ |
| paper_answer | `/paper-answer` | 试卷答题 | ✅ |
| paper_result | `/paper-result` | 试卷结果 | ✅ |
| wrong_questions | `/page/wrong_questions` | 错题集 | ❌ |
| notes | `/page/notes` | 笔记 | ✅ |
| favorites | `/page/favorites` | 收藏 | ✅ |
| score_analysis | `/page/score_analysis` | 成绩分析 | ❌ |
| gold_purchase | `/page/gold_purchase` | 金币购 | ❌ |
| daily_news | `/page/daily_news` | 每日新闻 | ❌ |
| exam_calendar | `/page/exam_calendar` | 考试日历 | ❌ |
| recruitment_info | `/page/recruitment_info` | 招考信息 | ❌ |

### 教师端页面
| ID | 路由 | 说明 |
|---|---|---|
| teacher_dashboard | `/teacher/dashboard` | 教师工作台 |
| teacher_questions | `/teacher/questions` | 题目管理 |
| teacher_papers | `/teacher/papers` | 试卷管理 |
| teacher_scores | `/teacher/scores` | 成绩管理 |
| question_import | `/question-import` | 题目导入 |

### 管理员端页面
| ID | 路由 | 说明 |
|---|---|---|
| admin_dashboard | `/admin/dashboard` | 系统总览 |
| admin_users | `/admin/users` | 用户管理 |
| admin_questions | `/admin/questions` | 题库管理 |
| admin_settings | `/admin/settings` | 系统设置 |
| admin_logs | `/admin/logs` | 日志审计 |
| admin_backup | `/admin/backup` | 数据备份 |
| admin_permissions | `/admin/permissions` | 权限管理 |
| paper_approval | `/admin/papers` | 试卷审批 |

## 区块组件（15个）

### 公共组件
- `app_navigation` - 公共导航栏
- `navbar` - 导航栏
- `countdown_timer` - 联考倒计时

### 首页模块
- `signin_status` - 签到情况
- `personal_goal` - 个人小目标
- `daily_quote` - 申论金句展示
- `countdown_block` - 联考倒计时
- `exam_calendar` - 考试日历
- `recruitment_info` - 招考信息
- `study_materials` - 备考资料
- `footer_info` - 底部协议

### 首页区块
- `exam_calendar_block` - 考试日历
- `signin_card` - 签到打卡
- `quote_banner` - 申论金句展示

### 公共区块
- `goal_card` - 个人小目标

## VTJ 关键约定

1. **raw: true 页面** - 由开发者维护，VTJ 设计器不会覆盖
2. **修改 script 后必须同步** - `vtj_sync_vue_to_dsl` 更新 `.vtj/files/*.json`
3. **路由组件引用** - 使用 `$vtj/vue/<id>.vue` 路径
4. **认证模块** - `src/auth.ts` 挂载到 `window.__VTJ_AUTH__`

## 后端 API 模块（30个路由）

| 模块 | 路径 | 说明 |
|---|---|---|
| auth | `/api/auth/*` | 认证登录 |
| questions | `/api/questions/*` | 题库管理 |
| papers | `/api/papers/*` | 试卷管理 |
| paper_generation | `/api/paper-generation/*` | 智能组卷 |
| exams | `/api/exam/*` | 考试执行 |
| exam_records | `/api/exam-records/*` | 成绩记录 |
| wrong_questions | `/api/wrong-questions/*` | 错题集 |
| collection | `/api/collection/*` | 收藏管理 |
| notes | `/api/notes/*` | 笔记管理 |
| practice | `/api/practice/*` | 刷题练习 |
| quick_practice | `/api/quick-practice/*` | 快速练习 |
| smart_exam | `/api/smart-exam/*` | 智能组卷 |
| question_import | `/api/question-import/*` | 题目导入 |
| question_actions | `/api/question-actions/*` | 题目操作 |
| goals | `/api/goals/*` | 学习目标 |
| stats | `/api/stats/*` | 统计数据 |
| forum | `/api/forum/*` | 论坛 |
| news | `/api/news/*` | 新闻 |
| recruitment | `/api/recruitment/*` | 招考信息 |
| calendar | `/api/calendar/*` | 考试日历 |
| quotes | `/api/quotes/*` | 申论金句 |
| videos | `/api/videos/*` | 视频资源 |
| media | `/api/media/*` | 媒体资源 |
| llm | `/api/llm/*` | 大模型接口 |
| websocket | WebSocket | 实时通信 |
| admin | `/api/admin/*` | 管理员端 |
| admin_approval | `/api/admin/approval/*` | 试卷审批 |
| teacher | `/api/teacher/*` | 教师端 |

## 数据库核心表

| 表名 | 说明 |
|---|---|
| sys_user | 用户信息（三端角色） |
| question_bank | 题库主表 |
| question_subject | 科目分类 |
| question_type | 题型表 |
| knowledge_point | 知识点 |
| exam_paper | 试卷主表 |
| exam_record | 考试记录 |
| exam_answer_detail | 答题详情 |
| score_analysis | 成绩分析 |
| practice_record | 刷题记录 |
| smart_exam_record | 智能组卷记录 |
| wrong_question_personal | 个人错题集 |
| forum_post | 论坛帖子 |
| daily_checkin | 每日签到 |
| coin_record | 金币记录 |
| study_goal | 学习目标 |
| video_resource | 视频资源 |

## 子科目分类体系

### 行测 (subject_id=1)
政治理论、常识判断、言语理解与表达、数量关系、判断推理、资料分析、知觉速度与准确性

### 申论 (subject_id=2)
归纳概括、综合分析、提出对策、应用文写作、议论文写作

### 公专 (subject_id=3)
职业素养、基础知识、基本警务能力、法律知识、业务能力

## 文件结构

```
src/
├── main.ts          # 入口（VTJ Provider 初始化）
├── auth.ts          # 共享认证模块
├── App.vue          # 根组件
├── router/index.ts  # 静态路由（三端分离）
├── views/           # 手写页面（exercise/solution/unauthorized/not-found）
├── vtj/vue/         # VTJ 生成的 Vue 文件引用
└── components/      # 公共组件

.vtj/
├── files/           # DSL JSON 定义文件（97个）
├── vue/             # VTJ 生成的 Vue 文件
├── router.js        # VTJ 自动生成的路由
└── projects/        # 项目配置
```
