/*
 * 砺安题库 - 路由配置（三端分离）
 */
import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  // ==================== 公共路由 ====================
  {
    path: '/login',
    name: 'Login',
    component: () => import('$vtj/vue/login.vue')
  },
  {
    path: '/forum',
    name: 'Forum',
    component: () => import('$vtj/vue/forum.vue')
  },
  {
    path: '/unauthorized',
    name: 'Unauthorized',
    component: () => import('@/views/unauthorized.vue')
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
    component: () => import('@/views/exercise.vue'),
    meta: { roles: ['student', 'teacher', 'admin'] }
  },
  {
    path: '/solution',
    name: 'Solution',
    component: () => import('@/views/solution.vue'),
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
      }
    ]
  },,
  {
    path: '/materials/xingce',
    name: 'MaterialsXingce',
    component: () => import('$vtj/vue/materials_xingce.vue')
  }

  // ==================== 兜底路由 ====================
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/not-found.vue')
  }
];

const router = createRouter({
  history: createWebHashHistory(),
  routes
});

// ==================== 路由守卫 — 三端权限控制 ====================
router.beforeEach((to, _from, next) => {
  // 公开路由：登录页和未授权页直接放行
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