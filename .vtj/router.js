{
  path: '/answer',
  component: () => import('./vue/answer_page.vue')
},
{
  path: '/smart_recommend',
  component: () => import('./vue/smart_recommend.vue')
},
{
  path: '/daily-news',
  component: () => import('./vue/daily_news.vue')
},
{
  path: '/smart-exam',
  component: () => import('./vue/smart_exam.vue')
},
{
  path: '/smart-answer',
  component: () => import('./vue/smart_answer.vue')
},
{
  path: '/tablet/login',
  component: () => import('./vue/tablet_login.vue'),
  meta: { platform: 'tablet' }
},
{
  path: '/tablet/home',
  component: () => import('./vue/tablet_home.vue'),
  meta: { platform: 'tablet' }
},
{
  path: '/tablet/question-bank',
  component: () => import('./vue/tablet_question_bank.vue'),
  meta: { platform: 'tablet' }
},
{
  path: '/tablet/practice',
  component: () => import('./vue/tablet_practice.vue'),
  meta: { platform: 'tablet' }
},
{
  path: '/tablet/forum',
  component: () => import('./vue/tablet_forum.vue'),
  meta: { platform: 'tablet' }
},
{
  path: '/tablet/profile',
  component: () => import('./vue/tablet_profile.vue'),
  meta: { platform: 'tablet' }
},
{
  path: '/mobile/login',
  component: () => import('./vue/mobile_login.vue'),
  meta: { platform: 'mobile' }
},
{
  path: '/mobile/home',
  component: () => import('./vue/mobile_home.vue'),
  meta: { platform: 'mobile' }
},
{
  path: '/mobile/question-bank',
  component: () => import('./vue/mobile_question_bank.vue'),
  meta: { platform: 'mobile' }
},
{
  path: '/mobile/practice',
  component: () => import('./vue/mobile_practice.vue'),
  meta: { platform: 'mobile' }
},
{
  path: '/mobile/forum',
  component: () => import('./vue/mobile_forum.vue'),
  meta: { platform: 'mobile' }
},
{
  path: '/mobile/profile',
  component: () => import('./vue/mobile_profile.vue'),
  meta: { platform: 'mobile' }
}