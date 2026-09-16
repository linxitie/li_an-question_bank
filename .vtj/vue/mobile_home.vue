<!-- 手机端首页 - VTJ规范版 -->
<template>
  <div class="mobile-home-page">
    <!-- 顶部导航 -->
    <header class="top-nav">
      <div class="nav-left">
        <XIcon :icon="ArrowLeft" :size="22" color="#1A365D" class="nav-back" @click="goBack"></XIcon>
      </div>
      <h1 class="nav-title">砺安题库</h1>
      <div class="nav-right">
        <XIcon :icon="Bell" :size="22" color="#1A365D" class="nav-icon" @click="goToNotifications"></XIcon>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 用户信息卡片 -->
      <section class="user-card">
        <div class="user-greeting">
          <span class="greeting-text">
            <XIcon :icon="Sunny" :size="18" color="#ffffff"></XIcon>
            早上好，{{ userName }}！
          </span>
          <span class="streak-badge">
            <XIcon :icon="Lightning" :size="14" color="#ffffff"></XIcon>
            连续学习 {{ streakDays }} 天
          </span>
        </div>
        <div class="daily-goal">
          <div class="goal-info">
            <span class="goal-label">今日目标：{{ dailyGoal }}题</span>
            <span class="goal-progress">{{ dailyGoalPercent }}% ({{ dailyCompleted }}/{{ dailyGoal }})</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: dailyGoalPercent + '%' }"></div>
          </div>
        </div>
      </section>

      <!-- 统计卡片 -->
      <section class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon">
            <XIcon :icon="EditPen" :size="24" color="#1A365D"></XIcon>
          </div>
          <div class="stat-value">{{ todayCount }}</div>
          <div class="stat-label">今日做题</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">
            <XIcon :icon="DataLine" :size="24" color="#1A365D"></XIcon>
          </div>
          <div class="stat-value">{{ weekCount }}</div>
          <div class="stat-label">本周做题</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">
            <XIcon :icon="TrendCharts" :size="24" color="#10b981"></XIcon>
          </div>
          <div class="stat-value">{{ accuracy }}%</div>
          <div class="stat-label">正确率</div>
        </div>
        <div class="stat-card">
          <div class="stat-icon">
            <XIcon :icon="Timer" :size="24" color="#f59e0b"></XIcon>
          </div>
          <div class="stat-value">{{ studyHours }}h</div>
          <div class="stat-label">学习时长</div>
        </div>
      </section>

      <!-- 学习趋势 -->
      <section class="trend-section">
        <div class="section-header">
          <h2 class="section-title">
            <XIcon :icon="DataAnalysis" :size="20" color="#1A365D"></XIcon>
            本周学习趋势
          </h2>
          <span class="section-action" @click="viewMoreTrend">
            7天
            <XIcon :icon="ArrowDown" :size="14" color="#1890ff"></XIcon>
          </span>
        </div>
        <div class="trend-chart">
          <div class="chart-bars">
            <div class="bar-item" v-for="(day, index) in weekData" :key="index">
              <div class="bar-value">{{ day.count }}</div>
              <div class="bar" :style="{ height: (day.count / maxCount * 100) + '%' }"></div>
              <div class="bar-label">{{ day.label }}</div>
            </div>
          </div>
        </div>
      </section>

      <!-- 每日金句 -->
      <section class="quote-section">
        <div class="quote-card">
          <XIcon :icon="ChatDotRound" :size="24" color="#f59e0b" class="quote-icon"></XIcon>
          <p class="quote-text">{{ dailyQuote }}</p>
          <p class="quote-author">—— {{ quoteAuthor }}</p>
        </div>
      </section>

      <!-- 每日新闻 -->
      <section class="news-section">
        <div class="section-header">
          <h2 class="section-title">
            <XIcon :icon="Document" :size="20" color="#1A365D"></XIcon>
            每日新闻
          </h2>
          <span class="section-action" @click="viewAllNews">
            查看全部
            <XIcon :icon="ArrowRight" :size="14" color="#1890ff"></XIcon>
          </span>
        </div>
        <div class="news-list">
          <div class="news-item" v-for="(news, index) in newsList" :key="index" @click="viewNews(news)">
            <XIcon :icon="Right" :size="12" color="#1A365D"></XIcon>
            <span class="news-title">{{ news.title }}</span>
          </div>
        </div>
      </section>
    </main>

    <!-- 底部Tab栏 -->
    <nav class="bottom-tab-bar">
      <div :class="['tab-item', { active: activeTab === 'home' }]" @click="switchTab('home')">
        <XIcon :icon="HomeFilled" :size="22" :color="activeTab === 'home' ? '#1A365D' : '#a0a4b8'"></XIcon>
        <span class="tab-label">首页</span>
      </div>
      <div :class="['tab-item', { active: activeTab === 'question' }]" @click="switchTab('question')">
        <XIcon :icon="Reading" :size="22" :color="activeTab === 'question' ? '#1A365D' : '#a0a4b8'"></XIcon>
        <span class="tab-label">题库</span>
      </div>
      <div :class="['tab-item', { active: activeTab === 'practice' }]" @click="switchTab('practice')">
        <XIcon :icon="Edit" :size="22" :color="activeTab === 'practice' ? '#1A365D' : '#a0a4b8'"></XIcon>
        <span class="tab-label">练习</span>
      </div>
      <div :class="['tab-item', { active: activeTab === 'forum' }]" @click="switchTab('forum')">
        <XIcon :icon="ChatLineRound" :size="22" :color="activeTab === 'forum' ? '#1A365D' : '#a0a4b8'"></XIcon>
        <span class="tab-label">论坛</span>
      </div>
      <div :class="['tab-item', { active: activeTab === 'profile' }]" @click="switchTab('profile')">
        <XIcon :icon="User" :size="22" :color="activeTab === 'profile' ? '#1A365D' : '#a0a4b8'"></XIcon>
        <span class="tab-label">我的</span>
      </div>
    </nav>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { XIcon } from '@vtj/ui';
import {
  ArrowLeft,
  ArrowRight,
  ArrowDown,
  Bell,
  Sunny,
  Lightning,
  EditPen,
  DataLine,
  TrendCharts,
  Timer,
  DataAnalysis,
  ChatDotRound,
  Document,
  Right,
  HomeFilled,
  Reading,
  Edit,
  ChatLineRound,
  User
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'MobileHome',
  components: {
    XIcon
  },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'mobile_home', version: '1788919369989' });
    
    // 当前Tab
    const activeTab = ref('home');

    // 用户数据
    const userName = ref('同学');
    const streakDays = ref(15);
    const dailyGoal = ref(40);
    const dailyCompleted = ref(30);
    const dailyGoalPercent = computed(() => Math.round((dailyCompleted.value / dailyGoal.value) * 100));

    // 统计数据
    const todayCount = ref(18);
    const weekCount = ref(120);
    const accuracy = ref(70.2);
    const studyHours = ref(1.8);

    // 周数据
    const weekData = ref([
      { label: '一', count: 15 },
      { label: '二', count: 22 },
      { label: '三', count: 18 },
      { label: '四', count: 25 },
      { label: '五', count: 20 },
      { label: '六', count: 12 },
      { label: '日', count: 8 }
    ]);

    // 最大值用于计算柱状图高度
    const maxCount = computed(() => Math.max(...weekData.value.map(d => d.count)));

    // 每日金句
    const dailyQuote = ref('学而不思则罔，思而不学则殆。');
    const quoteAuthor = ref('《论语·为政》');

    // 新闻列表
    const newsList = ref([
      { title: '公安联考报名时间确定，12月开始报名', id: 1 },
      { title: '行测新增政治理论模块，占比提升至15%', id: 2 },
      { title: '申论命题方向调整，重点考察实务能力', id: 3 }
    ]);

    // 统一数据加载（供 onMounted / 切回前台刷新 / 未来 WebSocket 推送复用）
    const loadData = async () => {
      try {
        const auth = window.__VTJ_AUTH__;
        if (auth && auth.isLoggedIn()) {
          const uname = auth.getUsername();
          if (uname) userName.value = uname;
          // 学习统计（/api/stats/ 返回今日/本周刷题量、正确率、学习时长、连续签到等）
          const res = await fetch('/api/stats/', { headers: auth.getAuthHeaders() });
          if (res.ok) {
            const data = await res.json();
            todayCount.value = data.todayQuestions || 0;
            weekCount.value = data.weeklyQuestions || 0;
            accuracy.value = data.accuracyRate || 0;
            studyHours.value = data.totalStudyHours || 0;
            streakDays.value = data.streak || 0;
          }
          // 练习趋势（周图表数据，替换硬编码）
          const tRes = await fetch('/api/stats/practice-trend?days=7', { headers: auth.getAuthHeaders() });
          if (tRes.ok) {
            const tData = await tRes.json();
            if (tData.trend && tData.trend.length) {
              const dayLabels = ['日', '一', '二', '三', '四', '五', '六'];
              weekData.value = tData.trend.map((d: any) => ({
                label: dayLabels[new Date(d.date).getDay()] || '',
                count: d.questionsDone || 0
              }));
            }
          }
          // 学习目标（今日目标，替换硬编码）
          try {
            const gRes = await fetch('/api/goals/stats/summary', { headers: auth.getAuthHeaders() });
            if (gRes.ok) {
              const gData = await gRes.json();
              dailyGoal.value = gData.total_goals || 40;
              dailyCompleted.value = gData.completed_goals || 0;
            }
          } catch (e) { /* 目标接口失败不影响主流程 */ }
        }
        // 每日金句（公开接口）
        const qRes = await fetch('/api/quotes/quote/daily');
        if (qRes.ok) {
          const q = await qRes.json();
          if (q.content) {
            dailyQuote.value = q.content;
            quoteAuthor.value = q.source || q.author || '';
          }
        }
        // 每日新闻（公开接口）
        const nRes = await fetch('/api/news?limit=5');
        if (nRes.ok) {
          const n = await nRes.json();
          if (n.items && n.items.length) {
            newsList.value = n.items.map((it: any) => ({ title: it.title, id: it.id }));
          }
        }
      } catch (error) {
        console.error('加载数据失败:', error);
      }
    };

    onMounted(() => {
      loadData();
      // 页面从后台切回前台时自动刷新（三端数据同步）
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') loadData();
      });
      // 后端 WebSocket 广播 sync 事件时刷新（实时同步）
      window.addEventListener('__VTJ_SYNC__', loadData);
    });

    // 导航方法
    const goBack = () => {
      router.back();
    };

    const goToNotifications = () => {
      router.push('/mobile/notifications');
    };

    const viewMoreTrend = () => {
      // 查看更多趋势
    };

    const viewAllNews = () => {
      router.push('/mobile/news');
    };

    const viewNews = (news: any) => {
      router.push(`/mobile/news/${news.id}`);
    };

    const switchTab = (tab: string) => {
      activeTab.value = tab;
      const tabRoutes: Record<string, string> = {
        home: '/mobile/home',
        question: '/mobile/question-bank',
        practice: '/mobile/practice',
        forum: '/mobile/forum',
        profile: '/mobile/profile'
      };
      router.push(tabRoutes[tab] || '/');
    };

    return {
      activeTab,
      userName,
      streakDays,
      dailyGoal,
      dailyCompleted,
      dailyGoalPercent,
      todayCount,
      weekCount,
      accuracy,
      studyHours,
      weekData,
      maxCount,
      dailyQuote,
      quoteAuthor,
      newsList,
      goBack,
      goToNotifications,
      viewMoreTrend,
      viewAllNews,
      viewNews,
      switchTab,
      ArrowLeft,
      ArrowRight,
      ArrowDown,
      Bell,
      Sunny,
  Lightning,
      EditPen,
      DataLine,
      TrendCharts,
      Timer,
      DataAnalysis,
      ChatDotRound,
      Document,
      Right,
      HomeFilled,
      Reading,
      Edit,
      ChatLineRound,
      User
    };
  }
});
</script>

<style lang="css" scoped>
.mobile-home-page {
  min-height: 100vh;
  background: #f5f7fa;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  display: flex;
  flex-direction: column;
}

/* 顶部导航 */
.top-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 16px;
  background: #ffffff;
  border-bottom: 1px solid #f0f2f5;
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-left,
.nav-right {
  width: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nav-back,
.nav-icon {
  cursor: pointer;
  transition: opacity 0.2s;
}

.nav-back:hover,
.nav-icon:hover {
  opacity: 0.7;
}

.nav-title {
  font-size: 18px;
  font-weight: 700;
  color: #1A365D;
  margin: 0;
}

/* 主内容区 */
.main-content {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  padding-bottom: 80px;
}

/* 用户信息卡片 */
.user-card {
  background: linear-gradient(135deg, #1A365D 0%, #2a5298 100%);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 16px;
  color: #ffffff;
}

.user-greeting {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.greeting-text {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 16px;
  font-weight: 600;
}

.streak-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.2);
  padding: 4px 10px;
  border-radius: 20px;
}

.daily-goal {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 12px;
}

.goal-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
}

.goal-label {
  opacity: 0.9;
}

.goal-progress {
  font-weight: 600;
}

.progress-bar {
  height: 6px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #ffffff;
  border-radius: 3px;
  transition: width 0.3s ease;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.stat-icon {
  margin-bottom: 8px;
  display: flex;
  justify-content: center;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #1A365D;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 12px;
  color: #5a6488;
}

/* 学习趋势 */
.trend-section {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 700;
  color: #1A365D;
  margin: 0;
}

.section-action {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #1890ff;
  cursor: pointer;
}

.trend-chart {
  height: 120px;
  display: flex;
  align-items: flex-end;
}

.chart-bars {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  width: 100%;
  height: 100%;
}

.bar-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.bar-value {
  font-size: 10px;
  color: #5a6488;
  margin-bottom: 4px;
}

.bar {
  width: 24px;
  background: linear-gradient(180deg, #1A365D 0%, #2a5298 100%);
  border-radius: 4px 4px 0 0;
  min-height: 4px;
  transition: height 0.3s ease;
}

.bar-label {
  font-size: 11px;
  color: #5a6488;
  margin-top: 6px;
}

/* 每日金句 */
.quote-section {
  margin-bottom: 16px;
}

.quote-card {
  background: linear-gradient(135deg, #fff9e6 0%, #fff3cc 100%);
  border-radius: 12px;
  padding: 20px;
  position: relative;
}

.quote-icon {
  margin-bottom: 8px;
}

.quote-text {
  font-size: 15px;
  font-weight: 600;
  color: #1A365D;
  line-height: 1.6;
  margin: 0 0 8px;
}

.quote-author {
  font-size: 12px;
  color: #5a6488;
  margin: 0;
  text-align: right;
}

/* 每日新闻 */
.news-section {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.news-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.news-item {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 8px 0;
  border-bottom: 1px solid #f0f2f5;
}

.news-item:last-child {
  border-bottom: none;
}

.news-title {
  font-size: 14px;
  color: #1a2b5f;
  line-height: 1.4;
}

/* 底部Tab栏 */
.bottom-tab-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 60px;
  background: #ffffff;
  display: flex;
  justify-content: space-around;
  align-items: center;
  border-top: 1px solid #f0f2f5;
  padding-bottom: env(safe-area-inset-bottom, 0);
  z-index: 100;
}

.tab-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  height: 100%;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-item.active {
  color: #1A365D;
}

.tab-item:not(.active) {
  color: #a0a4b8;
}

.tab-label {
  font-size: 10px;
  font-weight: 500;
  margin-top: 2px;
}

@media (max-width: 375px) {
  .main-content {
    padding: 12px;
  }
  
  .user-card {
    padding: 16px;
  }
  
  .stats-grid {
    gap: 8px;
  }
  
  .stat-card {
    padding: 12px;
  }
  
  .stat-value {
    font-size: 18px;
  }
}

@supports(padding-bottom: env(safe-area-inset-bottom)) {
  .bottom-tab-bar {
    height: calc(60px + env(safe-area-inset-bottom));
  }
}
</style>
