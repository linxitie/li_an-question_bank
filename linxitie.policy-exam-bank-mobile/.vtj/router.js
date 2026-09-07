{
  path: '/',
  component: () => import('./vue/layout.vue'),
  children: [
    {
      path: '',
      redirect: '/home'
    },
    {
      path: 'home',
      component: () => import('./vue/home_page.vue')
    },
    {
      path: 'questions',
      component: () => import('./vue/question_bank.vue')
    },
    {
      path: 'practice',
      component: () => import('./vue/practice_page.vue')
    },
    {
      path: 'forum',
      component: () => import('./vue/forum_page.vue')
    },
    {
      path: 'profile',
      component: () => import('./vue/profile_page.vue')
    }
  ]
}
