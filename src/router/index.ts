/*
 * 砺安题库 - 路由配置（三端分离）
 */
import {
  createRouter,
  createWebHashHistory,
  type RouteRecordRaw
} from 'vue-router';
import { detectDevice, resolveDevicePath } from '@/utils/device';
import { reloadForChunkError } from '@/utils/chunkRecovery';
import { canAccess } from './access';

const routes: RouteRecordRaw[] = [
  // ==================== 公共路由 ====================
  {
    path: '/login',
    name: 'Login',
    component: () => import('$vtj/vue/login.vue')
  },
  {
    path: '/scan',
    name: 'ScanLogin',
    component: () => import('$vtj/vue/download_client.vue')
  },
  {
    path: '/forum',
    name: 'Forum',
    component: () => import('$vtj/vue/forum.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/recruit',
    name: 'Recruitment',
    component: () => import('$vtj/vue/recruitment_info.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/recruitment/radar',
    name: 'RecruitmentRadar',
    component: () => import('@/views/student/shared/recruitment_radar.vue'),
    meta: { platform: 'pc', roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/unauthorized',
    name: 'Unauthorized',
    component: () => import('@/views/system/shared/unauthorized.vue')
  },

  // ==================== 学生端路由 ====================
  {
    path: '/',
    name: 'Home',
    component: () => import('$vtj/vue/question_bank.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/home',
    name: 'HomePage',
    component: () => import('$vtj/vue/home_page.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/daily-news',
    name: 'DailyNews',
    component: () => import('@/views/student/shared/daily_news.vue'),
    meta: { platform: 'pc', roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/quotes',
    name: 'QuotesBrowser',
    component: () => import('@/views/student/shared/quotes_browser.vue'),
    meta: { platform: 'pc', roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/quotes/favorites',
    name: 'QuoteFavorites',
    component: () => import('@/views/student/shared/quote_favorites.vue'),
    meta: { platform: 'pc', roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/favorites',
    redirect: '/news/favorites'
  },
  {
    path: '/news',
    name: 'NewsTimeline',
    component: () => import('@/views/student/shared/news_timeline.vue'),
    meta: { platform: 'pc', roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/news/favorites',
    name: 'NewsFavorites',
    component: () => import('@/views/student/shared/news_favorites.vue'),
    meta: { platform: 'pc', roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/news/:id',
    name: 'NewsDetail',
    component: () => import('@/views/student/shared/news_detail.vue'),
    meta: { platform: 'pc', roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/exercise',
    name: 'Exercise',
    component: () => import('@/views/student/shared/exercise.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    // 练习中心（手写页）：统一「快速练习 / 自定义刷题」的考点选择与练习蓝图
    path: '/practice-center',
    name: 'PracticeCenter',
    component: () => import('@/views/student/shared/practice_center.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    // 收件箱（手写页，v9 M4）：复习提醒/任务/系统通知统一归档，与右下角铃铛共享 /api/notifications
    path: '/inbox',
    name: 'Inbox',
    component: () => import('@/views/student/shared/Inbox.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/solution',
    name: 'Solution',
    component: () => import('@/views/student/shared/solution.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/answer',
    name: 'AnswerPage',
    component: () => import('$vtj/vue/answer_page.vue'),
    meta: { roles: ['student'] }
  },
  {
    path: '/smart-exam',
    name: 'SmartExam',
    component: () => import('$vtj/vue/smart_exam.vue'),
    meta: { roles: ['student'] }
  },
  {
    path: '/smart-answer',
    name: 'SmartAnswer',
    component: () => import('$vtj/vue/smart_answer.vue'),
    meta: { roles: ['student'] }
  },
  {
    path: '/ai-assistant',
    name: 'AiAssistant',
    component: () => import('$vtj/vue/ai_chat.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  // 联考小智工作台：流式对话 + 工具调用执行（新增页，旧 ai_chat 保留）
  {
    path: '/ai-studio',
    name: 'AiStudio',
    component: () => import('@/views/student/pc/ai_studio.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/study-plan',
    name: 'StudyPlan',
    component: () => import('$vtj/vue/study_plan.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/profile-quiz',
    name: 'ProfileQuiz',
    component: () => import('$vtj/vue/profile_quiz.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/knowledge',
    name: 'KnowledgeView',
    component: () => import('$vtj/vue/knowledge_view.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  // 错题集（PC）：页面一直存在但此前没有注册路由，属孤儿页；
  // 遗忘曲线复习提醒卡（DueReviewCard）挂在该页，必须可达。
  {
    path: '/wrong-questions',
    name: 'WrongQuestions',
    component: () => import('$vtj/vue/wrong_questions.vue'),
    meta: { roles: ['student'] }
  },
  {
    path: '/memories',
    name: 'MemoriesView',
    component: () => import('$vtj/vue/memories.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/student/papers',
    name: 'StudentPapers',
    component: () => import('$vtj/vue/student_papers.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    // M3.5（2026-11-05）：我的知识图谱（手写页，不改 .vtj 模板）
    path: '/student/knowledge/graph',
    name: 'StudentKnowledgeGraph',
    component: () => import('@/views/student/pc/knowledge_graph.vue'),
    meta: { roles: ['student', 'teacher', 'admin'], title: '我的知识图谱' }
  },
  {
    // 金币购 M1.5（2026-11-05）：我的兑换（手写页，放在 src/views，不改 .vtj 模板）
    path: '/student/shop/exchanges',
    name: 'StudentShopExchanges',
    component: () => import('@/views/student/pc/shop_exchanges.vue'),
    meta: { roles: ['student', 'teacher', 'admin'], title: '我的兑换' }
  },
  {
    path: '/paper-answer',
    name: 'PaperAnswer',
    component: () => import('$vtj/vue/paper_answer.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/paper-result',
    name: 'PaperResult',
    component: () => import('$vtj/vue/paper_result.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },

  // ==================== 学生端「我的」模块 ====================
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('@/views/student/shared/profile.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/achievements',
    name: 'Achievements',
    component: () => import('@/views/student/shared/achievements.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/feedback',
    name: 'Feedback',
    component: () => import('@/views/student/shared/feedback.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/help',
    name: 'Help',
    component: () => import('@/views/student/shared/help.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },

  // ==================== 教师端路由 ====================
  {
    path: '/question-import',
    name: 'QuestionImport',
    component: () => import('$vtj/vue/question_import.vue'),
    meta: { roles: ['teacher', 'admin'] }
  },
  {
    path: '/teacher/dashboard',
    name: 'TeacherDashboard',
    component: () => import('$vtj/vue/teacher_dashboard.vue'),
    meta: { roles: ['teacher', 'admin'] }
  },
  {
    path: '/teacher/questions',
    name: 'TeacherQuestions',
    component: () => import('$vtj/vue/teacher_questions.vue'),
    meta: { roles: ['teacher', 'admin'] }
  },
  {
    // 考点复核（手写页）：低置信考点分配的人工确认/驳回，写回 point_assign_audit
    path: '/teacher/point-review',
    name: 'TeacherPointReview',
    component: () => import('@/views/teacher/pc/PointReview.vue'),
    meta: { roles: ['teacher', 'admin'] }
  },
  {
    // 内容修复中心（手写页，v9 M7）：导入后自动体检出的缺口（缺图/缺横线/缺选项/缺答案/缺解析/缺材料），
    // 按类分组、逐题定位，点「定位题目补录」跳到题目管理并用 ?question_id= 深链打开待修字段。
    path: '/teacher/content-repair',
    name: 'TeacherContentRepair',
    component: () => import('@/views/teacher/pc/ContentRepair.vue'),
    meta: { roles: ['teacher', 'admin'] }
  },
  {
    path: '/teacher/papers',
    name: 'TeacherPapers',
    // P5：旧 raw 页左栏固定 50 条、无预览解析；改为手写双栏工作台。
    // 旧文件 teacher_papers.vue 保留，仅作设计器回滚参考，路由不再指向它。
    component: () => import('@/views/teacher/pc/TeacherPaperEditor.vue'),
    meta: { roles: ['teacher', 'admin'] }
  },
  {
    path: '/teacher/scores',
    name: 'TeacherScores',
    // P4：原 teacher_scores 仅 276 行、无班级/全校与知识点分析；
    // 合并「数据分析」后改为手写驾驶舱，旧 SQL 级页面保留文件仅作回滚参考。
    component: () => import('@/views/teacher/pc/TeacherScoresWorkspace.vue'),
    meta: { roles: ['teacher', 'admin'] }
  },
  {
    path: '/teacher/classes',
    name: 'TeacherClasses',
    component: () => import('$vtj/vue/teacher_classes.vue'),
    meta: { roles: ['teacher', 'admin'] }
  },
  {
    path: '/teacher/analytics',
    name: 'TeacherAnalytics',
    // P4：数据分析已合并进成绩管理，旧书签一律 302 到新驾驶舱，避免两套口径。
    redirect: '/teacher/scores',
    meta: { roles: ['teacher', 'admin'] }
  },
  {
    path: '/teacher/messages',
    name: 'TeacherMessages',
    component: () => import('$vtj/vue/teacher_messages.vue'),
    meta: { roles: ['teacher', 'admin'] }
  },
  {
    path: '/teacher/forum',
    name: 'TeacherForum',
    component: () => import('@/views/teacher/teacher_forum.vue'),
    meta: { roles: ['teacher', 'admin'] }
  },
  {
    path: '/teacher/profile',
    name: 'TeacherProfile',
    component: () => import('$vtj/vue/teacher_profile.vue'),
    meta: { roles: ['teacher', 'admin'] }
  },

  // ==================== 管理员端路由 ====================
  {
    path: '/admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { roles: ['admin'] },
    children: [
      {
        path: '',
        redirect: '/admin/dashboard'
      },
      {
        path: 'dashboard',
        name: 'AdminDashboard',
        component: () => import('$vtj/vue/admin_dashboard.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'users',
        name: 'AdminUsers',
        component: () => import('@/views/admin/pc/AdminUsersWorkspace.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'questions',
        name: 'AdminQuestions',
        component: () => import('$vtj/vue/admin_questions.vue'),
        meta: { roles: ['admin'] }
      },
      {
        // 2026-11-05：金币商城挂到 AdminLayout 下，保证左侧导航常驻
        path: 'shop',
        name: 'AdminShop',
        component: () => import('$vtj/vue/admin_shop.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'settings',
        name: 'AdminSettings',
        component: () => import('$vtj/vue/admin_settings.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'logs',
        name: 'AdminLogs',
        component: () => import('$vtj/vue/admin_logs.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'material-rules',
        name: 'AdminMaterialRules',
        component: () => import('@/views/admin/material_rules.vue'),
        meta: { title: '分类规则', roles: ['admin'] }
      },
      {
        path: 'materials',
        name: 'AdminMaterials',
        // A4（2026-11-07）：换成手写页，6 类筛选 / 发布者 / 上传时间 / 预览 / 上架即审批
        component: () => import('@/views/admin/materials.vue'),
        meta: { title: '资料管理', roles: ['admin'] }
      },
      // S4（2026-11-12）：旧版资料页**路由已下线**（原 `materials/legacy` + `$vtj/vue/admin_materials.vue`）。
      // 下线前提：S3（xlsx 卡片智能导入）与 S2（富文本正文/卡片正反面）已搬进新版页，
      // 覆盖度审计见 `docs/plans/旧版资料页_覆盖度审计与清理方案_v1.md` §2/§10/§11。
      // 守 R1：`.vtj/vue/admin_materials.vue` **文件保留**（不删不改），只是不再挂路由；
      // 页面计数 105 → 104（L6 与 test_route_roles 两处已同步）。
      // 若需临时找回：把这条路由（path/name/component/meta）加回来即可，页面文件还在。
      {
        // A0（2026-11-07）：管理端画风组件库预览页 —— E1/E2 改造的视觉基准。
        // 新增 1 条页面路由 → L6/L7 的页面计数 104 → 105（两处门禁已同步）。
        path: 'dev/style',
        name: 'AdminDevStyle',
        component: () => import('@/views/admin/dev/StylePreview.vue'),
        meta: { title: '画风组件库', roles: ['admin'] }
      },
      {
        // 试卷审批页下线（2026-11-07，试卷收敛方案 P4=A）：旧书签不 404，redirect 到资料管理并带上类型筛选。
        // 该条无 component → **不计入页面路由数**，因此 L6/L7 不受影响。
        path: 'papers',
        redirect: '/admin/materials?type=paper'
      },
      {
        path: 'quotes',
        name: 'AdminQuotes',
        component: () => import('@/views/admin/quotes_review.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'profile',
        name: 'AdminProfile',
        component: () => import('$vtj/vue/admin_profile.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'backup',
        name: 'AdminBackup',
        component: () => import('$vtj/vue/admin_backup.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'permissions',
        name: 'AdminPermissions',
        // 旧书签保留：权限模板已并入用户与权限工作台
        redirect: '/admin/users?tab=templates'
      },
      {
        path: 'forum',
        name: 'AdminForum',
        component: () => import('@/views/admin/admin_forum.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'feedback',
        name: 'AdminFeedback',
        component: () => import('@/views/admin/admin_feedback.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'help',
        name: 'AdminHelp',
        component: () => import('$vtj/vue/admin_help.vue'),
        meta: { roles: ['admin'] }
      }
    ]
  },

  // ==================== 备考资料（学生端公开页） ====================
  // 2026-11-04：徽章展示模块下线（用户要求推远端前删除），/badges、/badges-demo、
  // /badge-preview 三条路由随页面文件一并移除；成就/金币引擎不受影响。
  {
    path: '/materials/upload',
    name: 'MaterialUpload',
    component: () => import('@/views/student/material_upload.vue'),
    meta: { title: '创建卡片', roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/materials-preview',
    name: 'MaterialsPreview',
    component: () => import('@/views/dev/MaterialsPreview.vue'),
    meta: { title: '资料内容验收', roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/materials/detail',
    name: 'MaterialDetail',
    component: () => import('@/views/pc/material_detail.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  // L2（2026-11-08）：学生「备考资料」改用**手写页**（src/views/student/materials.vue）。
  // 为什么换 component 而不是改 `.vtj/vue/materials_*.vue`：R3 禁止 AI 改 .vtj 模板，
  // 且 `.vtj/files/*.json` 的 DSL 与真实模板不同步，改模板会被设计器回存覆盖。
  // 三条路由**条数不变**（L6/L7 的 105 不动），旧页仍保留在仓库 → 回滚=把这行改回去。
  {
    path: '/materials/xingce',
    name: 'MaterialsXingce',
    component: () => import('@/views/student/materials.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/materials/shenlun',
    name: 'MaterialsShenlun',
    component: () => import('@/views/student/materials.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/materials/gongzhuan',
    name: 'MaterialsGongzhuan',
    component: () => import('@/views/student/materials.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },

  // ==================== 平板端路由 ====================
  {
    path: '/tablet/login',
    name: 'TabletLogin',
    component: () => import('$vtj/vue/tablet_login.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  // ---- 模块4/7 补齐：平板端复用同一组件（R12）----
  {
    path: '/tablet/profile-quiz',
    name: 'TabletProfileQuiz',
    component: () => import('$vtj/vue/profile_quiz.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/study-plan',
    name: 'TabletStudyPlan',
    component: () => import('$vtj/vue/study_plan.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/ai-assistant',
    name: 'TabletAiAssistant',
    component: () => import('$vtj/vue/ai_chat.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/signin',
    name: 'TabletSignin',
    component: () => import('$vtj/vue/signin_card.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/knowledge-graph',
    name: 'TabletKnowledgeGraph',
    component: () => import('@/views/student/pc/knowledge_graph.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    // 2026-11-02：平板与电脑使用同一套页面（你的要求），首页直接复用电脑首页组件。
    // 注意：不能 redirect 到 /home —— device.ts（R4 原样保留）会把平板访问的 /home 映射回
    // /tablet/home，redirect 会形成死循环；所以这里只换 component，路径保持 /tablet/home。
    path: '/tablet/home',
    name: 'TabletHome',
    component: () => import('$vtj/vue/home_page.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/question-bank',
    name: 'TabletQuestionBank',
    component: () => import('$vtj/vue/tablet_question_bank.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/practice',
    name: 'TabletPractice',
    component: () => import('$vtj/vue/tablet_practice.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/forum',
    name: 'TabletForum',
    // 2026-10-30（用户决定 A）：平板与 PC 共用同一套论坛页，避免两套布局维护
    component: () => import('$vtj/vue/forum.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/profile',
    name: 'TabletProfile',
    component: () => import('$vtj/vue/tablet_profile.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/news',
    name: 'TabletNews',
    component: () => import('@/views/student/mobile/mobile_news.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/news/favorites',
    name: 'TabletNewsFavorites',
    component: () => import('@/views/student/shared/news_favorites.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/news/timeline',
    name: 'TabletNewsTimeline',
    component: () => import('@/views/student/shared/news_timeline.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/news/:id',
    name: 'TabletNewsDetail',
    component: () => import('@/views/student/mobile/mobile_news.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/quotes',
    name: 'TabletQuotes',
    component: () => import('@/views/student/shared/quotes_browser.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/quotes/favorites',
    name: 'TabletQuoteFavorites',
    component: () => import('@/views/student/shared/quote_favorites.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/wrong-questions',
    name: 'TabletWrongQuestions',
    component: () =>
      import('@/views/student/mobile/mobile_wrong_questions.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/favorites',
    name: 'TabletFavorites',
    component: () => import('@/views/student/mobile/mobile_favorites.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/score-analysis',
    name: 'TabletScoreAnalysis',
    component: () => import('@/views/student/mobile/mobile_score_analysis.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/student-papers',
    name: 'TabletStudentPapers',
    component: () => import('@/views/student/mobile/mobile_student_papers.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/recruit',
    name: 'TabletRecruitment',
    component: () => import('@/views/student/mobile/mobile_recruitment.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/recruitment/radar',
    name: 'TabletRecruitmentRadar',
    component: () => import('@/views/student/shared/recruitment_radar.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/calendar',
    name: 'TabletCalendar',
    component: () => import('@/views/student/mobile/mobile_calendar.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    // 2026-11-02：平板与电脑同版 → 旧地址一律 302 到电脑端页面（redirect 不带 component，
    // 因此不再计入「页面路由数」；门禁数字已同步 101 → 98）
    path: '/tablet/materials',
    redirect: '/materials/xingce'
  },
  {
    // 2026-11-04：徽章展示模块下线 → /tablet/badges 重定向一并移除
    // 2026-11-02：平板与电脑同版 → 详情页直接用电脑端整页
    path: '/tablet/materials/detail',
    redirect: '/materials/detail'
  },
  {
    path: '/tablet/gold-purchase',
    name: 'TabletGoldPurchase',
    component: () => import('$vtj/vue/tablet_gold_purchase.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/notifications',
    name: 'TabletNotifications',
    component: () => import('@/views/student/mobile/mobile_notifications.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/answer',
    name: 'TabletAnswer',
    component: () => import('@/views/student/mobile/mobile_answer.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/notes',
    name: 'TabletNotes',
    component: () => import('@/views/student/mobile/mobile_notes.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/forum/create',
    name: 'TabletForumCreate',
    component: () => import('@/views/student/mobile/mobile_forum_create.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/forum/:id',
    name: 'TabletForumDetail',
    component: () => import('@/views/student/mobile/mobile_forum_detail.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },

  // ==================== 手机端路由 ====================
  {
    path: '/mobile/login',
    name: 'MobileLogin',
    component: () => import('$vtj/vue/mobile_login.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/scan',
    name: 'MobileScan',
    component: () => import('@/views/student/mobile/mobile_scan.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  // ---- 模块4/7 补齐：手机端复用 PC 页面（R12：不复制页面，靠 platform 区分）----
  {
    path: '/mobile/profile-quiz',
    name: 'MobileProfileQuiz',
    component: () => import('$vtj/vue/profile_quiz.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/study-plan',
    name: 'MobileStudyPlan',
    component: () => import('$vtj/vue/study_plan.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/ai-assistant',
    name: 'MobileAiAssistant',
    component: () => import('$vtj/vue/ai_chat.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/signin',
    name: 'MobileSignin',
    component: () => import('$vtj/vue/signin_card.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/knowledge-graph',
    name: 'MobileKnowledgeGraph',
    component: () => import('@/views/student/pc/knowledge_graph.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/news',
    name: 'MobileNews',
    component: () => import('@/views/student/mobile/mobile_news.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/quotes',
    name: 'MobileQuotes',
    component: () => import('@/views/student/shared/quotes_browser.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/quotes/favorites',
    name: 'MobileQuoteFavorites',
    component: () => import('@/views/student/shared/quote_favorites.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/news/timeline',
    name: 'MobileNewsTimeline',
    component: () => import('@/views/student/shared/news_timeline.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/news/:id',
    name: 'MobileNewsDetail',
    component: () => import('@/views/student/mobile/mobile_news.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/wrong-questions',
    name: 'MobileWrongQuestions',
    component: () =>
      import('@/views/student/mobile/mobile_wrong_questions.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/favorites',
    name: 'MobileFavorites',
    component: () => import('@/views/student/mobile/mobile_favorites.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/wrong-review',
    name: 'MobileWrongReview',
    component: () => import('@/views/student/mobile/mobile_wrong_review.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/history',
    name: 'MobileHistory',
    component: () => import('@/views/student/mobile/mobile_history.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/score-analysis',
    name: 'MobileScoreAnalysis',
    component: () => import('@/views/student/mobile/mobile_score_analysis.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/student-papers',
    name: 'MobileStudentPapers',
    component: () => import('@/views/student/mobile/mobile_student_papers.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/recruit',
    name: 'MobileRecruitment',
    component: () => import('@/views/student/mobile/mobile_recruitment.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/recruitment/radar',
    name: 'MobileRecruitmentRadar',
    component: () =>
      import('@/views/student/mobile/mobile_recruitment_radar.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/calendar',
    name: 'MobileCalendar',
    component: () => import('@/views/student/mobile/mobile_calendar.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/materials',
    name: 'MobileMaterials',
    component: () => import('@/views/student/mobile/mobile_materials.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/gold-purchase',
    name: 'MobileGoldPurchase',
    component: () => import('$vtj/vue/mobile_gold_purchase.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/achievements',
    name: 'MobileAchievements',
    component: () => import('@/views/student/mobile/mobile_achievements.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/feedback',
    name: 'MobileFeedback',
    component: () => import('@/views/student/mobile/mobile_feedback.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/help',
    name: 'MobileHelp',
    component: () => import('@/views/student/mobile/mobile_help.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/home',
    name: 'MobileHome',
    component: () => import('$vtj/vue/mobile_home.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/question-bank',
    name: 'MobileQuestionBank',
    component: () => import('$vtj/vue/mobile_question_bank.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/practice',
    name: 'MobilePractice',
    component: () => import('$vtj/vue/mobile_practice.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/forum',
    name: 'MobileForum',
    component: () => import('$vtj/vue/mobile_forum.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/profile',
    name: 'MobileProfile',
    component: () => import('$vtj/vue/mobile_profile.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/notes',
    name: 'MobileNotes',
    component: () => import('@/views/student/mobile/mobile_notes.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/answer',
    name: 'MobileAnswer',
    component: () => import('@/views/student/mobile/mobile_answer.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    // D6（2026-11-15）：手机端结果页 —— 以前答完试直接跳 PC 的 /paper-result（桌面版式）
    path: '/mobile/paper-result',
    name: 'MobilePaperResult',
    component: () => import('@/views/student/mobile/mobile_paper_result.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/notifications',
    name: 'MobileNotifications',
    component: () => import('@/views/student/mobile/mobile_notifications.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/forum/create',
    name: 'MobileForumCreate',
    component: () => import('@/views/student/mobile/mobile_forum_create.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },
  {
    path: '/mobile/forum/:id',
    name: 'MobileForumDetail',
    component: () => import('@/views/student/mobile/mobile_forum_detail.vue'),
    meta: { platform: 'mobile', roles: ['student'] }
  },

  // ==================== 兜底路由 ====================
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/system/shared/not-found.vue')
  }
];

const router = createRouter({
  history: createWebHashHistory(),
  routes
});

// 2026-11-14：懒加载模块失败（dev server 重启/浏览器缓存损坏）时自动重载一次，
// 避免停在「模块加载失败」页面反复手动刷新。
router.onError((error) => {
  if (reloadForChunkError()) return;
  console.error('[router] 页面模块加载失败:', error);
});

// ==================== 路由守卫 — 三端权限控制 ====================
/**
 * 内容模块的 PC → 移动/平板路由映射。
 *
 * `resolveDevicePath()`（R4 文件）只覆盖首页/登录/题库等旧路由，不能修改；
 * 新闻、金句、招考是后加模块，必须在这里补齐，否则手机访问 /news 会渲染 PC 的
 * news_timeline.vue，而不是 /mobile/news 的 mobile_news.vue。
 */
function resolveContentDevicePath(
  path: string,
  device: 'mobile' | 'tablet'
): string | null {
  const prefix = device === 'tablet' ? '/tablet' : '/mobile';
  const exact: Record<string, string> = {
    '/news': `${prefix}/news`,
    '/news/favorites':
      device === 'tablet' ? '/tablet/news/favorites' : '/mobile/favorites',
    '/quotes': `${prefix}/quotes`,
    '/quotes/favorites': `${prefix}/quotes/favorites`,
    '/recruit': `${prefix}/recruit`,
    '/recruitment/radar': `${prefix}/recruitment/radar`,
    '/favorites':
      device === 'tablet' ? '/tablet/favorites' : '/mobile/favorites'
  };
  if (exact[path]) return exact[path];
  if (path.startsWith('/news/') && path !== '/news/favorites') {
    return `${prefix}/news/${path.slice('/news/'.length)}`;
  }
  return null;
}

router.beforeEach((to, _from, next) => {
  const detected = detectDevice();
  // 兼容手机浏览器的“桌面模式”/旧 WebView：UA 被判为 pc 时，仍按视口宽度回到移动布局
  const device: 'pc' | 'mobile' | 'tablet' =
    detected === 'pc' && window.innerWidth <= 1024
      ? window.innerWidth >= 768
        ? 'tablet'
        : 'mobile'
      : detected;

  // 1) 已在设备专属路径（/tablet、/mobile）→ 先验登录，再验角色
  //    - 未登录：只放行各端登录页，其余跳转到对应端登录页并带 redirect
  //      （此前这里直接 `next()`，导致 /mobile/* 未登录也能进——已修）
  //    - 教师/管理员：跳 /unauthorized
  if (to.path.startsWith('/tablet') || to.path.startsWith('/mobile')) {
    const auth = (window as any).__VTJ_AUTH__;
    const logged =
      auth && typeof auth.isLoggedIn === 'function'
        ? !!auth.isLoggedIn()
        : false;
    const isLoginPage =
      /^\/(tablet|mobile)\/login\/?$/.test(to.path) ||
      to.path === '/unauthorized';
    if (!logged) {
      if (isLoginPage) return next();
      const loginPath = to.path.startsWith('/tablet')
        ? '/tablet/login'
        : '/mobile/login';
      return next({ path: loginPath, query: { redirect: to.fullPath } });
    }
    const role = auth ? auth.getUserRole() : null;
    if (role && role !== 'student') {
      return next('/unauthorized?reason=mobile_student_only');
    }
    if (role) {
      const permissions = auth?.getPermissions ? auth.getPermissions() : [];
      if (!canAccess(to.meta as any, role, permissions)) {
        return next('/unauthorized');
      }
    }
    return next();
  }

  // 2) 手机/平板访问内容模块的 PC 路径 → 映射到对应端
  //    旧 resolveDevicePath 仅覆盖旧路由；新闻/金句/招考在此补齐。
  if (device === 'mobile' || device === 'tablet') {
    const mapped = resolveContentDevicePath(to.path, device);
    if (mapped) {
      return next({ path: mapped, replace: true });
    }
    const target = resolveDevicePath(to.path, device);
    if (target) {
      return next({ path: target, replace: true });
    }
  }

  // 3) PC 设备：公开路由直接放行（论坛允许游客浏览，互动仍由接口校验登录）
  // 资料内容验收页：只读公开接口（/api/materials 游客可访问），允许未登录查看
  if (to.path === '/materials-preview') {
    return next();
  }

  // 上传页的演示态（?demo=1）：只渲染界面与本页内 mock 数据，不触达任何接口，
  // 便于截图与设计走查；正常访问（无 demo 参数）仍走登录 + 角色校验。
  if (to.path === '/materials/upload' && to.query.demo === '1') {
    return next();
  }

  if (
    to.path === '/login' ||
    to.path === '/unauthorized' ||
    to.path === '/forum'
  ) {
    return next();
  }

  const auth = (window as any).__VTJ_AUTH__;
  if (!auth) {
    // auth 模块尚未初始化，放行（VTJ Provider 加载中）
    return next();
  }

  const isLoggedIn = auth.isLoggedIn();

  // 未登录 → 跳转登录页
  if (!isLoggedIn) {
    return next(`/login?redirect=${encodeURIComponent(to.fullPath)}`);
  }

  // 检查路由元数据中的角色与权限限制
  const currentRole = auth.getUserRole();
  const currentPermissions = auth.getPermissions ? auth.getPermissions() : [];
  if (!canAccess(to.meta as any, currentRole, currentPermissions)) {
    return next('/unauthorized');
  }

  // ===== 角色仪表盘重定向（三端分离） =====
  // 教师/管理员访问 / 或 /home 时自动跳转到对应仪表盘
  const userRole = auth.getUserRole();
  const roleDashboardMap: Record<string, string> = {
    admin: '/admin/dashboard',
    teacher: '/teacher/dashboard'
  };
  if (
    userRole &&
    roleDashboardMap[userRole] &&
    (to.path === '/' || to.path === '/home')
  ) {
    return next({ path: roleDashboardMap[userRole], replace: true });
  }

  next();
});

export default router;
