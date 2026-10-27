/*
 * 砺安题库 - 路由配置（三端分离）
 */
import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router';
import { detectDevice, resolveDevicePath } from '@/utils/device';
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
    component: () => import('$vtj/vue/forum.vue')
  },
  {
    path: '/recruit',
    name: 'Recruitment',
    component: () => import('$vtj/vue/recruitment_info.vue')
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
        path: 'forum',
        name: 'AdminForum',
        component: () => import('@/views/admin/admin_forum.vue'),
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
    path: '/materials/xingce',
    name: 'MaterialsXingce',
    component: () => import('$vtj/vue/materials_xingce.vue')
  },
  {
    path: '/materials/shenlun',
    name: 'MaterialsShenlun',
    component: () => import('$vtj/vue/materials_shenlun.vue')
  },
  {
    path: '/materials/gongzhuan',
    name: 'MaterialsGongzhuan',
    component: () => import('$vtj/vue/materials_gongzhuan.vue')
  },

  // ==================== 平板端路由 ====================
  {
    path: '/tablet/login',
    name: 'TabletLogin',
    component: () => import('$vtj/vue/tablet_login.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/home',
    name: 'TabletHome',
    component: () => import('$vtj/vue/tablet_home.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/question-bank',
    name: 'TabletQuestionBank',
    component: () => import('$vtj/vue/tablet_question_bank.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/practice',
    name: 'TabletPractice',
    component: () => import('$vtj/vue/tablet_practice.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/forum',
    name: 'TabletForum',
    component: () => import('$vtj/vue/tablet_forum.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/profile',
    name: 'TabletProfile',
    component: () => import('$vtj/vue/tablet_profile.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/news',
    name: 'TabletNews',
    component: () => import('@/views/student/mobile/mobile_news.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/news/:id',
    name: 'TabletNewsDetail',
    component: () => import('@/views/student/mobile/mobile_news.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/wrong-questions',
    name: 'TabletWrongQuestions',
    component: () => import('@/views/student/mobile/mobile_wrong_questions.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/favorites',
    name: 'TabletFavorites',
    component: () => import('@/views/student/mobile/mobile_favorites.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/score-analysis',
    name: 'TabletScoreAnalysis',
    component: () => import('@/views/student/mobile/mobile_score_analysis.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/student-papers',
    name: 'TabletStudentPapers',
    component: () => import('@/views/student/mobile/mobile_student_papers.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/recruit',
    name: 'TabletRecruitment',
    component: () => import('@/views/student/mobile/mobile_recruitment.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/calendar',
    name: 'TabletCalendar',
    component: () => import('@/views/student/mobile/mobile_calendar.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/materials',
    name: 'TabletMaterials',
    component: () => import('@/views/student/mobile/mobile_materials.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/gold-purchase',
    name: 'TabletGoldPurchase',
    component: () => import('$vtj/vue/tablet_gold_purchase.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/notifications',
    name: 'TabletNotifications',
    component: () => import('@/views/student/mobile/mobile_notifications.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/answer',
    name: 'TabletAnswer',
    component: () => import('@/views/student/mobile/mobile_answer.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/notes',
    name: 'TabletNotes',
    component: () => import('@/views/student/mobile/mobile_notes.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/forum/create',
    name: 'TabletForumCreate',
    component: () => import('@/views/student/mobile/mobile_forum_create.vue'),
    meta: { platform: 'tablet' }
  },
  {
    path: '/tablet/forum/:id',
    name: 'TabletForumDetail',
    component: () => import('@/views/student/tablet/tablet_forum_detail.vue'),
    meta: { platform: 'tablet' }
  },

  // ==================== 手机端路由 ====================
  {
    path: '/mobile/login',
    name: 'MobileLogin',
    component: () => import('$vtj/vue/mobile_login.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/scan',
    name: 'MobileScan',
    component: () => import('@/views/student/mobile/mobile_scan.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/news',
    name: 'MobileNews',
    component: () => import('@/views/student/mobile/mobile_news.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/news/:id',
    name: 'MobileNewsDetail',
    component: () => import('@/views/student/mobile/mobile_news.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/wrong-questions',
    name: 'MobileWrongQuestions',
    component: () => import('@/views/student/mobile/mobile_wrong_questions.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/favorites',
    name: 'MobileFavorites',
    component: () => import('@/views/student/mobile/mobile_favorites.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/wrong-review',
    name: 'MobileWrongReview',
    component: () => import('@/views/student/mobile/mobile_wrong_review.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/history',
    name: 'MobileHistory',
    component: () => import('@/views/student/mobile/mobile_history.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/score-analysis',
    name: 'MobileScoreAnalysis',
    component: () => import('@/views/student/mobile/mobile_score_analysis.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/student-papers',
    name: 'MobileStudentPapers',
    component: () => import('@/views/student/mobile/mobile_student_papers.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/recruit',
    name: 'MobileRecruitment',
    component: () => import('@/views/student/mobile/mobile_recruitment.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/calendar',
    name: 'MobileCalendar',
    component: () => import('@/views/student/mobile/mobile_calendar.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/materials',
    name: 'MobileMaterials',
    component: () => import('@/views/student/mobile/mobile_materials.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/gold-purchase',
    name: 'MobileGoldPurchase',
    component: () => import('$vtj/vue/mobile_gold_purchase.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/achievements',
    name: 'MobileAchievements',
    component: () => import('@/views/student/mobile/mobile_achievements.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/feedback',
    name: 'MobileFeedback',
    component: () => import('@/views/student/mobile/mobile_feedback.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/help',
    name: 'MobileHelp',
    component: () => import('@/views/student/mobile/mobile_help.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/home',
    name: 'MobileHome',
    component: () => import('$vtj/vue/mobile_home.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/question-bank',
    name: 'MobileQuestionBank',
    component: () => import('$vtj/vue/mobile_question_bank.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/practice',
    name: 'MobilePractice',
    component: () => import('$vtj/vue/mobile_practice.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/forum',
    name: 'MobileForum',
    component: () => import('$vtj/vue/mobile_forum.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/profile',
    name: 'MobileProfile',
    component: () => import('$vtj/vue/mobile_profile.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/notes',
    name: 'MobileNotes',
    component: () => import('@/views/student/mobile/mobile_notes.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/answer',
    name: 'MobileAnswer',
    component: () => import('@/views/student/mobile/mobile_answer.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/notifications',
    name: 'MobileNotifications',
    component: () => import('@/views/student/mobile/mobile_notifications.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/forum/create',
    name: 'MobileForumCreate',
    component: () => import('@/views/student/mobile/mobile_forum_create.vue'),
    meta: { platform: 'mobile' }
  },
  {
    path: '/mobile/forum/:id',
    name: 'MobileForumDetail',
    component: () => import('@/views/student/mobile/mobile_forum_detail.vue'),
    meta: { platform: 'mobile' }
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

  // 1) 已在设备专属路径（/tablet、/mobile）→ 校验角色：移动/平板端仅学生可访问
  //    教师/管理员（已登录且非 student）跳转提示页；未登录放行到各端登录页
  if (to.path.startsWith('/tablet') || to.path.startsWith('/mobile')) {
    const auth = (window as any).__VTJ_AUTH__;
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

  // 2) 仅「手机」访问 PC 路径 → 映射到手机端
  //    2026-10-26 用户决定：平板与电脑端使用同一套页面，因此平板不再自动跳 /tablet/*
  //    （平板版仍可通过显式 URL 访问，如 /#/tablet/login、/#/tablet/forum/4）
  //    保留原「登录页也区分设备」的行为：手机访问 /login 仍映射到 /mobile/login
  if (device === 'mobile') {
    const target = resolveDevicePath(to.path, device);
    if (target) {
      return next({ path: target, replace: true });
    }
  }

  // 3) PC 设备：公开路由直接放行（论坛允许游客浏览，互动仍由接口校验登录）
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