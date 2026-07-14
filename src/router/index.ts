import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  // ==================== 公共路由 ====================
  {
    path: '/login',
    name: 'Login',
    component: () => import('$vtj/vue/login.vue')
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

  // ==================== 管理员端路由 ====================
  {
    path: '/admin/dashboard',
    name: 'AdminDashboard',
    component: () => import('$vtj/vue/admin_dashboard.vue'),
    meta: { roles: ['admin'] }
  },
  {
    path: '/admin/users',
    name: 'AdminUsers',
    component: () => import('$vtj/vue/admin_users.vue'),
    meta: { roles: ['admin'] }
  },
  {
    path: '/admin/questions',
    name: 'AdminQuestions',
    component: () => import('$vtj/vue/admin_questions.vue'),
    meta: { roles: ['admin'] }
  },
  {
    path: '/admin/settings',
    name: 'AdminSettings',
    component: () => import('$vtj/vue/admin_settings.vue'),
    meta: { roles: ['admin'] }
  },
  {
    path: '/admin/logs',
    name: 'AdminLogs',
    component: () => import('$vtj/vue/admin_logs.vue'),
    meta: { roles: ['admin'] }
  },
  {
    path: '/admin/backup',
    name: 'AdminBackup',
    component: () => import('$vtj/vue/admin_backup.vue'),
    meta: { roles: ['admin'] }
  },
  {
    path: '/admin/permissions',
    name: 'AdminPermissions',
    component: () => import('$vtj/vue/admin_permissions.vue'),
    meta: { roles: ['admin'] }
  },

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

  next();
});

export default router;
