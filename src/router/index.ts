/*
 * 砺安题库 - 路由配置（三端分离）
 */
import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router';
import { detectDevice, resolveDevicePath } from '@/utils/device';

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
    path: '/exercise',
    name: 'Exercise',
    component: () => import('@/views/student/shared/exercise.vue'),
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
    path: '/student/papers',
    name: 'StudentPapers',
    component: () => import('$vtj/vue/student_papers.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
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
    path: '/teacher/papers',
    name: 'TeacherPapers',
    component: () => import('$vtj/vue/teacher_papers.vue'),
    meta: { roles: ['teacher', 'admin'] }
  },
  {
    path: '/teacher/scores',
    name: 'TeacherScores',
    component: () => import('$vtj/vue/teacher_scores.vue'),
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
    component: () => import('$vtj/vue/teacher_analytics.vue'),
    meta: { roles: ['teacher', 'admin'] }
  },
  {
    path: '/teacher/messages',
    name: 'TeacherMessages',
    component: () => import('$vtj/vue/teacher_messages.vue'),
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
        component: () => import('$vtj/vue/admin_users.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'questions',
        name: 'AdminQuestions',
        component: () => import('$vtj/vue/admin_questions.vue'),
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
        component: () => import('$vtj/vue/admin_materials.vue'),
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
        component: () => import('$vtj/vue/admin_permissions.vue'),
        meta: { roles: ['admin'] }
      },
      {
        path: 'papers',
        name: 'AdminPapers',
        component: () => import('$vtj/vue/paper_approval.vue'),
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
  {
    path: '/badges',
    name: 'StudentBadges',
    component: () => import('@/views/student/badges.vue'),
    meta: { title: '我的徽章', roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/badges-demo',
    name: 'BadgesDemo',
    component: () => import('@/views/dev/BadgesDemo.vue'),
    meta: { title: '徽章页演示', roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/badge-preview',
    name: 'BadgePreview',
    component: () => import('@/views/dev/BadgePreview.vue'),
    meta: { title: '徽章预览', roles: ['student', 'teacher', 'admin'] }
  },
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
  {
    path: '/materials/xingce',
    name: 'MaterialsXingce',
    component: () => import('$vtj/vue/materials_xingce.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/materials/shenlun',
    name: 'MaterialsShenlun',
    component: () => import('$vtj/vue/materials_shenlun.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/materials/gongzhuan',
    name: 'MaterialsGongzhuan',
    component: () => import('$vtj/vue/materials_gongzhuan.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },

  // ==================== 平板端路由 ====================
  {
    path: '/tablet/login',
    name: 'TabletLogin',
    component: () => import('$vtj/vue/tablet_login.vue'),
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
    component: () => import('$vtj/vue/tablet_forum.vue'),
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
    path: '/tablet/news/:id',
    name: 'TabletNewsDetail',
    component: () => import('@/views/student/mobile/mobile_news.vue'),
    meta: { platform: 'tablet', roles: ['student'] }
  },
  {
    path: '/tablet/wrong-questions',
    name: 'TabletWrongQuestions',
    component: () => import('@/views/student/mobile/mobile_wrong_questions.vue'),
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
    // 2026-11-02：平板与电脑同版 → 徽章墙直接用电脑端页面
    path: '/tablet/badges',
    redirect: '/badges'
  },
  {
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
  {
    path: '/mobile/news',
    name: 'MobileNews',
    component: () => import('@/views/student/mobile/mobile_news.vue'),
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
    component: () => import('@/views/student/mobile/mobile_wrong_questions.vue'),
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

// ==================== 路由守卫 — 三端权限控制 ====================
router.beforeEach((to, _from, next) => {
  const device = detectDevice();

  // 1) 已在设备专属路径（/tablet、/mobile）→ 先验登录，再验角色
  //    - 未登录：只放行各端登录页，其余跳转到对应端登录页并带 redirect
  //      （此前这里直接 `next()`，导致 /mobile/* 未登录也能进——已修）
  //    - 教师/管理员：跳 /unauthorized
  if (to.path.startsWith('/tablet') || to.path.startsWith('/mobile')) {
    const auth = (window as any).__VTJ_AUTH__;
    const logged = auth && typeof auth.isLoggedIn === 'function'
      ? !!auth.isLoggedIn()
      : false;
    const isLoginPage = /^\/(tablet|mobile)\/login\/?$/.test(to.path)
      || to.path === '/unauthorized';
    if (!logged) {
      if (isLoginPage) return next();
      const loginPath = to.path.startsWith('/tablet') ? '/tablet/login' : '/mobile/login';
      return next({ path: loginPath, query: { redirect: to.fullPath } });
    }
    const role = auth ? auth.getUserRole() : null;
    if (role && role !== 'student') {
      return next('/unauthorized?reason=mobile_student_only');
    }
    return next();
  }

  // 2) 移动设备（手机/平板）访问 PC 路径 → 映射到对应端
  //    关键修复：登录页也区分设备，手机访问 /login 会映射到 /mobile/login
  if (device !== 'pc') {
    const target = resolveDevicePath(to.path, device);
    if (target) {
      return next({ path: target, replace: true });
    }
  }

  // 3) PC 设备：公开路由直接放行
  // 徽章 SVG 预览页：纯静态演示、不触达任何数据，允许未登录查看
  // 徽章页演示：纯前端演示数据，允许未登录查看（供截图/预览）
  if (to.path === '/badges-demo') {
    return next();
  }

  if (to.path === '/badge-preview') {
    return next();
  }

  // 资料内容验收页：只读公开接口（/api/materials 游客可访问），允许未登录查看
  if (to.path === '/materials-preview') {
    return next();
  }

  // 上传页的演示态（?demo=1）：只渲染界面与本页内 mock 数据，不触达任何接口，
  // 便于截图与设计走查；正常访问（无 demo 参数）仍走登录 + 角色校验。
  if (to.path === '/materials/upload' && to.query.demo === '1') {
    return next();
  }

  if (to.path === '/login' || to.path === '/unauthorized') {
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

  // 检查路由元数据中的角色限制
  const allowedRoles = to.meta?.roles as string[] | undefined;
  if (allowedRoles && allowedRoles.length > 0) {
    const userRole = auth.getUserRole();

    // admin 角色可访问所有路由
    if (userRole === 'admin') {
      return next();
    }

    if (!allowedRoles.includes(userRole)) {
      return next('/unauthorized');
    }
  }

  // ===== 角色仪表盘重定向（三端分离） =====
  // 教师/管理员访问 / 或 /home 时自动跳转到对应仪表盘
  const userRole = auth.getUserRole();
  const roleDashboardMap: Record<string, string> = {
    admin: '/admin/dashboard',
    teacher: '/teacher/dashboard',
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