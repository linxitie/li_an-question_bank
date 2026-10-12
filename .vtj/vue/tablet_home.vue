<!-- 平板端首页 - VTJ规范版 -->
<template>
  <div class="tablet-home-page">
    <!-- 顶部导航 -->
    <header class="top-nav">
      <div class="nav-left">
        <div class="logo">
          <XIcon :icon="Medal" :size="28" color="#1A365D"></XIcon>
          <span class="logo-text">砺安题库</span>
        </div>
      </div>
      <div class="nav-center">
        <div class="search-box">
          <XIcon :icon="Search" :size="18" color="#8899aa"></XIcon>
          <input type="text" v-model="searchQuery" placeholder="搜索题目、知识点..." />
        </div>
      </div>
      <div class="nav-right">
        <XIcon :icon="Bell" :size="22" color="#1A365D" class="nav-icon" @click="goToNotifications"></XIcon>
        <XIcon :icon="Setting" :size="22" color="#1A365D" class="nav-icon" @click="goToSettings"></XIcon>
        <div class="user-avatar" @click="goToProfile">
          <XIcon :icon="UserFilled" :size="24" color="#ffffff"></XIcon>
        </div>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 左侧面板 -->
      <aside class="left-panel">
        <!-- 用户信息 -->
        <div class="user-card">
          <div class="user-avatar-large">
            <XIcon :icon="UserFilled" :size="40" color="#ffffff"></XIcon>
          </div>
          <h2 class="user-name">{{ userName }}</h2>
          <p class="user-role">公安联考备考学员</p>
          <div class="user-stats">
            <div class="stat-item">
              <span class="stat-value">{{ streakDays }}</span>
              <span class="stat-label">连续天数</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ totalQuestions }}</span>
              <span class="stat-label">总做题</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ accuracy }}%</span>
              <span class="stat-label">正确率</span>
            </div>
          </div>
        </div>

        <!-- 今日目标 -->
        <div class="goal-card">
          <div class="goal-header">
            <XIcon :icon="Aim" :size="20" color="#1A365D"></XIcon>
            <span class="goal-title">今日目标</span>
          </div>
          <div class="goal-progress">
            <div class="progress-info">
              <span>已完成 {{ dailyCompleted }}/{{ dailyGoal }} 题</span>
              <span class="progress-percent">{{ dailyGoalPercent }}%</span>
            </div>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: dailyGoalPercent + '%' }"></div>
            </div>
          </div>
          <div class="goal-actions">
            <button class="goal-btn" @click="startQuickPractice">
              <XIcon :icon="VideoPlay" :size="16" color="#ffffff"></XIcon>
              开始练习
            </button>
          </div>
        </div>

        <!-- 考试日历 -->
        <div class="calendar-card">
          <div class="calendar-header">
            <XIcon :icon="Calendar" :size="20" color="#1A365D"></XIcon>
            <span class="calendar-title">考试日历</span>
          </div>
          <div class="calendar-list">
            <div class="calendar-item" v-for="(exam, index) in upcomingExams" :key="index">
              <div class="exam-date">
                <span class="exam-month">{{ exam.month }}</span>
                <span class="exam-day">{{ exam.day }}</span>
              </div>
              <div class="exam-info">
                <span class="exam-name">{{ exam.name }}</span>
                <span class="exam-countdown">还有 {{ exam.daysLeft }} 天</span>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <!-- 中间内容区 -->
      <section class="center-content">
        <!-- 学习趋势 -->
        <div class="trend-card">
          <div class="card-header">
            <h2 class="card-title">
              <XIcon :icon="DataLine" :size="20" color="#1A365D"></XIcon>
              本周学习趋势
            </h2>
            <span class="card-action" @click="viewMoreTrend">
              详细数据
              <XIcon :icon="ArrowRight" :size="14" color="#1890ff"></XIcon>
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
        </div>

        <!-- 每日金句 -->
        <div class="quote-card">
          <XIcon :icon="ChatDotRound" :size="24" color="#f59e0b" class="quote-icon"></XIcon>
          <p class="quote-text">{{ dailyQuote }}</p>
          <p class="quote-author">—— {{ quoteAuthor }}</p>
        </div>

        <!-- 快捷功能 -->
        <div class="quick-actions">
          <div class="action-card" @click="goToSmartExam">
            <div class="action-icon">
              <XIcon :icon="Cpu" :size="32" color="#1A365D"></XIcon>
            </div>
            <span class="action-name">智能组卷</span>
            <span class="action-desc">AI智能出题</span>
          </div>
          <div class="action-card" @click="goToQuestionBank">
            <div class="action-icon">
              <XIcon :icon="Reading" :size="32" color="#10b981"></XIcon>
            </div>
            <span class="action-name">题库练习</span>
            <span class="action-desc">海量题库</span>
          </div>
          <div class="action-card" @click="goToWrongQuestions">
            <div class="action-icon">
              <XIcon :icon="Warning" :size="32" color="#f59e0b"></XIcon>
            </div>
            <span class="action-name">错题本</span>
            <span class="action-desc">攻克薄弱</span>
          </div>
          <div class="action-card" @click="goToMockExam">
            <div class="action-icon">
              <XIcon :icon="Timer" :size="32" color="#8b5cf6"></XIcon>
            </div>
            <span class="action-name">模拟考试</span>
            <span class="action-desc">实战演练</span>
          </div>
        </div>
      </section>

      <!-- 右侧面板 -->
      <aside class="right-panel">
        <!-- 每日新闻 -->
        <div class="news-card">
          <div class="card-header">
            <h2 class="card-title">
              <XIcon :icon="Document" :size="20" color="#1A365D"></XIcon>
              每日新闻
            </h2>
            <span class="card-action" @click="viewAllNews">查看全部</span>
          </div>
          <div class="news-list">
            <div class="news-item" v-for="(news, index) in newsList" :key="index" @click="viewNews(news)">
              <XIcon :icon="Right" :size="12" color="#1A365D"></XIcon>
              <span class="news-title">{{ news.title }}</span>
            </div>
          </div>
        </div>

        <!-- 招考信息 -->
        <div class="recruit-card">
          <div class="card-header">
            <h2 class="card-title">
              <XIcon :icon="Suitcase" :size="20" color="#c41e3a"></XIcon>
              招考信息
            </h2>
            <span class="card-action" @click="viewAllRecruit">查看全部</span>
          </div>
          <div class="recruit-list">
            <div class="recruit-item" v-for="(recruit, index) in recruitList" :key="index" @click="viewRecruit(recruit)">
              <span class="recruit-status" :style="{ background: recruit.statusColor + '18', color: recruit.statusColor }">{{ recruit.status }}</span>
              <span class="recruit-title">{{ recruit.title }}</span>
            </div>
          </div>
        </div>
      </aside>
    </main>

    <!-- 底部状态栏 -->
    <footer class="bottom-bar">
      <div class="bar-left">
        <span class="online-status">
          <XIcon :icon="CircleCheck" :size="14" color="#10b981"></XIcon>
          在线
        </span>
        <span class="sync-status">
          <XIcon :icon="Refresh" :size="14" color="#1890ff"></XIcon>
          数据已同步
        </span>
      </div>
      <div class="bar-right">
        <span class="version">v1.0.0</span>
      </div>
    </footer>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { XIcon } from '@vtj/ui';
import {
  Medal,
  Search,
  Bell,
  Setting,
  UserFilled,
  Aim,
  VideoPlay,
  Calendar,
  DataLine,
  ArrowRight,
  ChatDotRound,
  Cpu,
  Reading,
  Warning,
  Timer,
  Document,
  Right,
  Suitcase,
  CircleCheck,
  Refresh
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';
import { createRecruitmentRefresher } from '@/utils/recruitmentRefresh';

export default defineComponent({
  name: 'TabletHome',
  components: {
    XIcon
  },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'tablet_home', version: '1788919369989' });
    
    // 搜索
    const searchQuery = ref('');

    // 用户数据
    const userName = ref('同学');
    const streakDays = ref(15);
    const totalQuestions = ref(1289);
    const dailyGoal = ref(40);
    const dailyCompleted = ref(30);
    const dailyGoalPercent = computed(() => Math.round((dailyCompleted.value / dailyGoal.value) * 100));
    const accuracy = ref(70.2);

    // 周数据
    const weekData = ref([
      { label: '周一', count: 15 },
      { label: '周二', count: 22 },
      { label: '周三', count: 18 },
      { label: '周四', count: 25 },
      { label: '周五', count: 20 },
      { label: '周六', count: 12 },
      { label: '周日', count: 8 }
    ]);

    const maxCount = computed(() => Math.max(...weekData.value.map(d => d.count)));

    // 每日金句
    const dailyQuote = ref('学而不思则罔，思而不学则殆。');
    const quoteAuthor = ref('《论语·为政》');

    // 新闻列表
    const newsList = ref([
      { title: '公安联考报名时间确定', id: 1 },
      { title: '行测新增政治理论模块', id: 2 },
      { title: '申论命题方向调整', id: 3 }
    ]);

    // 招考信息（初始为空，由统一刷新内核填充真实数据；
    // 此前内置的 3 条硬编码假数据会在接口失败时长期展示为"真实招考信息"，已移除）
    const recruitList = ref<any[]>([]);

    // 考试日历
    const upcomingExams = ref([
      { month: '12月', day: '15', name: '公安联考', daysLeft: 45 },
      { month: '1月', day: '10', name: '国考笔试', daysLeft: 71 },
      { month: '3月', day: '1', name: '省考笔试', daysLeft: 130 }
    ]);

    // 加载用户数据
    onMounted(async () => {
      try {
        const auth = window.__VTJ_AUTH__;
        if (auth && auth.isLoggedIn()) {
          const uname = auth.getUsername();
          if (uname) userName.value = uname;
          // 学习统计（/api/stats/ 返回今日刷题量等）
          const res = await fetch('/api/stats/', { headers: auth.getAuthHeaders() });
          if (res.ok) {
            const data = await res.json();
            dailyCompleted.value = data.todayQuestions || 0;
          }
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
        // 招考信息（公开接口）改由统一刷新内核负责，见 loadRecruitment
        // 考试日历（真实接口 /api/calendar/exams，替换原静态 /api/stats/calendar）
        const cRes = await fetch('/api/calendar/exams?limit=3');
        if (cRes.ok) {
          const c = await cRes.json();
          if (c.items && c.items.length) {
            const now = Date.now();
            upcomingExams.value = c.items.map((it: any) => {
              const d = it.exam_date || '';
              const target = d ? new Date(d).getTime() : now;
              return {
                month: (it.month || (d.slice(5, 7))) + '月',
                day: it.day || d.slice(8, 10),
                name: it.title,
                daysLeft: Math.max(0, Math.ceil((target - now) / 86400000))
              };
            });
          }
        }
      } catch (error) {
        console.error('加载数据失败:', error);
      }
    });

    // ===== 招考信息：统一刷新内核 =====
    // 平板端招考数据此前只在 onMounted 取一次，且用裸 fetch（不带认证、不破缓存）。
    // 现统一走内核：首屏 + 后端广播 + 可见性/聚焦 + 跨日 + 15 分钟轮询 + 登录态 + 手动。
    let recruitRefresher: any = null;
    const recruitMeta = ref<any>(null);

    const loadRecruitment = async (ctx: any) => {
      const opts: any = { cache: 'no-store' };
      if (ctx && ctx.signal) opts.signal = ctx.signal;
      const auth = (window as any).__VTJ_AUTH__;
      const url = '/api/recruitment?_ts=' + ((ctx && ctx.ts) || Date.now());
      const r = auth && auth.apiFetch ? await auth.apiFetch(url, opts) : await fetch(url, opts);
      if (!r.ok) return;
      const data = await r.json();
      if (data && data.items) {
        const flat: any[] = [];
        Object.values(data.items).forEach((arr: any) => { if (Array.isArray(arr)) flat.push(...arr); });
        recruitList.value = flat.slice(0, 3).map((it: any) => ({
          title: it.title, status: it.status_label, statusColor: it.status_color, id: it.id
        }));
        recruitMeta.value = data.meta || null;
      }
    };

    onMounted(() => {
      recruitRefresher = createRecruitmentRefresher({
        fetchFn: (ctx: any) => loadRecruitment(ctx),
        pollMs: 15 * 60 * 1000,
      });
    });

    onBeforeUnmount(() => {
      if (recruitRefresher) { recruitRefresher.destroy(); recruitRefresher = null; }
    });

    // 导航方法
    const goToNotifications = () => router.push('/tablet/notifications');
    const goToSettings = () => router.push('/tablet/profile');
    const goToProfile = () => router.push('/tablet/profile');
    const viewMoreTrend = () => {};
    const viewAllNews = () => router.push('/tablet/news');
    const viewNews = (news: any) => router.push(`/tablet/news/${news.id}`);
    const viewAllRecruit = () => router.push('/tablet/recruit');
    const viewRecruit = (recruit: any) => router.push('/tablet/recruit');
    const startQuickPractice = () => router.push('/tablet/answer');
    const goToSmartExam = () => router.push('/smart-exam');
    const goToQuestionBank = () => router.push('/tablet/question-bank');
    const goToWrongQuestions = () => router.push('/tablet/wrong-questions');
    const goToMockExam = () => router.push('/tablet/answer');

    return {
      searchQuery,
      userName,
      streakDays,
      totalQuestions,
      dailyGoal,
      dailyCompleted,
      dailyGoalPercent,
      accuracy,
      weekData,
      maxCount,
      dailyQuote,
      quoteAuthor,
      newsList,
      recruitList,
    recruitMeta,
    loadRecruitment,
      upcomingExams,
      goToNotifications,
      goToSettings,
      goToProfile,
      viewMoreTrend,
      viewAllNews,
      viewNews,
      viewAllRecruit,
      viewRecruit,
      startQuickPractice,
      goToSmartExam,
      goToQuestionBank,
      goToWrongQuestions,
      goToMockExam,
      Medal,
      Search,
      Bell,
      Setting,
      UserFilled,
      Aim,
      VideoPlay,
      Calendar,
      DataLine,
      ArrowRight,
      ChatDotRound,
      Cpu,
      Reading,
      Warning,
      Timer,
      Document,
      Right,
      Suitcase,
      CircleCheck,
      Refresh
    };
  }
});
</script>

<style lang="css" scoped>
.tablet-home-page {
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
  height: 64px;
  padding: 0 24px;
  background: #ffffff;
  border-bottom: 1px solid #f0f2f5;
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-left {
  display: flex;
  align-items: center;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-text {
  font-size: 20px;
  font-weight: 800;
  color: #1A365D;
}

.nav-center {
  flex: 1;
  max-width: 400px;
  margin: 0 24px;
}

.search-box {
  display: flex;
  align-items: center;
  background: #f5f7fa;
  border: 1px solid #e8ecf1;
  border-radius: 8px;
  padding: 0 12px;
  transition: all 0.3s ease;
}

.search-box:focus-within {
  border-color: #1A365D;
  background: #ffffff;
}

.search-box input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 10px 8px;
  font-size: 14px;
  color: #1a2b5f;
  outline: none;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.nav-icon {
  cursor: pointer;
  transition: opacity 0.2s;
}

.nav-icon:hover {
  opacity: 0.7;
}

.user-avatar {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #1A365D 0%, #2a5298 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

/* 主内容区 */
.main-content {
  flex: 1;
  display: grid;
  grid-template-columns: 280px 1fr 300px;
  gap: 20px;
  padding: 20px;
  overflow: hidden;
}

/* 左侧面板 */
.left-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.user-card {
  background: linear-gradient(135deg, #1A365D 0%, #2a5298 100%);
  border-radius: 16px;
  padding: 24px;
  color: #ffffff;
  text-align: center;
}

.user-avatar-large {
  width: 80px;
  height: 80px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}

.user-name {
  font-size: 20px;
  font-weight: 700;
  margin: 0 0 4px;
}

.user-role {
  font-size: 13px;
  opacity: 0.8;
  margin: 0 0 20px;
}

.user-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.stat-item {
  text-align: center;
}

.stat-item .stat-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
}

.stat-item .stat-label {
  display: block;
  font-size: 11px;
  opacity: 0.8;
  margin-top: 4px;
}

.goal-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.goal-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.goal-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
}

.goal-progress {
  margin-bottom: 16px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #5a6488;
  margin-bottom: 8px;
}

.progress-percent {
  font-weight: 600;
  color: #1A365D;
}

.progress-bar {
  height: 8px;
  background: #f0f2f5;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #1A365D 0%, #2a5298 100%);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.goal-actions {
  display: flex;
  justify-content: center;
}

.goal-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  background: linear-gradient(135deg, #1A365D 0%, #2a5298 100%);
  color: #ffffff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.goal-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(26, 54, 95, 0.3);
}

.calendar-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.calendar-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.calendar-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
}

.calendar-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.calendar-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  background: #f8f9fc;
  border-radius: 8px;
}

.exam-date {
  text-align: center;
  min-width: 48px;
}

.exam-month {
  display: block;
  font-size: 11px;
  color: #8899aa;
}

.exam-day {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #1A365D;
}

.exam-info {
  flex: 1;
}

.exam-name {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
}

.exam-countdown {
  display: block;
  font-size: 12px;
  color: #8899aa;
  margin-top: 2px;
}

/* 中间内容区 */
.center-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.trend-card,
.quote-card,
.quick-actions {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: #1a2b5f;
  margin: 0;
}

.card-action {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #1890ff;
  cursor: pointer;
}

.trend-chart {
  height: 150px;
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
  font-size: 11px;
  color: #5a6488;
  margin-bottom: 4px;
}

.bar {
  width: 32px;
  background: linear-gradient(180deg, #1A365D 0%, #2a5298 100%);
  border-radius: 4px 4px 0 0;
  min-height: 4px;
  transition: height 0.3s ease;
}

.bar-label {
  font-size: 12px;
  color: #5a6488;
  margin-top: 6px;
}

.quote-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  background: linear-gradient(135deg, #fff9e6 0%, #fff3cc 100%);
}

.quote-icon {
  margin-bottom: 12px;
}

.quote-text {
  font-size: 16px;
  font-weight: 600;
  color: #1A365D;
  line-height: 1.6;
  margin: 0 0 8px;
}

.quote-author {
  font-size: 13px;
  color: #5a6488;
  margin: 0;
}

.quick-actions {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.action-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 12px;
  background: #f8f9fc;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-card:hover {
  background: #f0f2f5;
  transform: translateY(-2px);
}

.action-icon {
  width: 56px;
  height: 56px;
  background: #ffffff;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.08);
}

.action-name {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
  margin-bottom: 4px;
}

.action-desc {
  font-size: 12px;
  color: #8899aa;
}

/* 右侧面板 */
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.news-card,
.recruit-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.news-list,
.recruit-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.news-item,
.recruit-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  background: #f8f9fc;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.news-item:hover,
.recruit-item:hover {
  background: #f0f2f5;
}

.news-title,
.recruit-title {
  flex: 1;
  font-size: 13px;
  color: #1a2b5f;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recruit-status {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

/* 底部状态栏 */
.bottom-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 40px;
  padding: 0 24px;
  background: #ffffff;
  border-top: 1px solid #f0f2f5;
}

.bar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.online-status,
.sync-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #5a6488;
}

.version {
  font-size: 12px;
  color: #8899aa;
}

/* 响应式 */
@media (max-width: 767px) {
  .main-content {
    grid-template-columns: 1fr;
  }
  
  .left-panel,
  .right-panel {
    display: none;
  }
}
</style>
