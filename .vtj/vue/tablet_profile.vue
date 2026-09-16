<!-- 平板端我的页 - VTJ规范版 -->
<template>
  <div class="tablet-profile-page">
    <!-- 顶部导航 -->
    <header class="top-nav">
      <div class="nav-left">
        <div class="logo">
          <XIcon :icon="Medal" :size="28" color="#1A365D"></XIcon>
          <span class="logo-text">砺安题库</span>
        </div>
      </div>
      <div class="nav-center">
        <h1 class="page-title">个人中心</h1>
      </div>
      <div class="nav-right">
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
            <XIcon :icon="UserFilled" :size="48" color="#ffffff"></XIcon>
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

        <!-- 功能菜单 -->
        <div class="menu-card">
          <div class="menu-list">
            <div class="menu-item" @click="goToAchievements">
              <div class="menu-icon">
                <XIcon :icon="Trophy" :size="20" color="#f59e0b"></XIcon>
              </div>
              <span class="menu-name">我的成就</span>
              <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
            </div>
            <div class="menu-item" @click="goToDownloads">
              <div class="menu-icon">
                <XIcon :icon="Download" :size="20" color="#1A365D"></XIcon>
              </div>
              <span class="menu-name">离线下载</span>
              <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
            </div>
            <div class="menu-item" @click="goToFeedback">
              <div class="menu-icon">
                <XIcon :icon="ChatDotRound" :size="20" color="#10b981"></XIcon>
              </div>
              <span class="menu-name">意见反馈</span>
              <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
            </div>
            <div class="menu-item" @click="goToHelp">
              <div class="menu-icon">
                <XIcon :icon="QuestionFilled" :size="20" color="#8b5cf6"></XIcon>
              </div>
              <span class="menu-name">帮助中心</span>
              <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
            </div>
            <div class="menu-item" @click="goToAbout">
              <div class="menu-icon">
                <XIcon :icon="InfoFilled" :size="20" color="#8899aa"></XIcon>
              </div>
              <span class="menu-name">关于砺安题库</span>
              <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
            </div>
          </div>
        </div>

        <!-- 退出登录 -->
        <button class="logout-btn" @click="handleLogout">
          <XIcon :icon="SwitchButton" :size="18" color="#c41e3a"></XIcon>
          退出登录
        </button>
      </aside>

      <!-- 中间内容区 -->
      <section class="center-content">
        <!-- 学习数据 -->
        <div class="data-section">
          <div class="section-header">
            <h2 class="section-title">
              <XIcon :icon="DataLine" :size="20" color="#1A365D"></XIcon>
              学习数据
            </h2>
          </div>
          <div class="data-grid">
            <div class="data-card" @click="goToWrongQuestions">
              <div class="data-icon">
                <XIcon :icon="Warning" :size="24" color="#f59e0b"></XIcon>
              </div>
              <span class="data-value">{{ wrongCount }}</span>
              <span class="data-label">错题本</span>
            </div>
            <div class="data-card" @click="goToCollection">
              <div class="data-icon">
                <XIcon :icon="Star" :size="24" color="#f59e0b"></XIcon>
              </div>
              <span class="data-value">{{ collectionCount }}</span>
              <span class="data-label">收藏</span>
            </div>
            <div class="data-card" @click="goToHistory">
              <div class="data-icon">
                <XIcon :icon="Clock" :size="24" color="#1A365D"></XIcon>
              </div>
              <span class="data-value">{{ historyCount }}</span>
              <span class="data-label">历史记录</span>
            </div>
            <div class="data-card" @click="goToNotes">
              <div class="data-icon">
                <XIcon :icon="Notebook" :size="24" color="#10b981"></XIcon>
              </div>
              <span class="data-value">{{ notesCount }}</span>
              <span class="data-label">笔记</span>
            </div>
          </div>
        </div>

        <!-- 学习趋势 -->
        <div class="trend-section">
          <div class="section-header">
            <h2 class="section-title">
              <XIcon :icon="TrendCharts" :size="20" color="#1A365D"></XIcon>
              学习趋势
            </h2>
            <span class="section-action">近30天</span>
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
      </section>

      <!-- 右侧面板 -->
      <aside class="right-panel">
        <!-- 考试日历 -->
        <div class="calendar-card">
          <div class="card-header">
            <h3 class="card-title">
              <XIcon :icon="Calendar" :size="18" color="#1A365D"></XIcon>
              考试日历
            </h3>
          </div>
          <div class="exam-list">
            <div 
              v-for="(exam, index) in upcomingExams" 
              :key="index"
              class="exam-item"
            >
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

        <!-- 成就徽章 -->
        <div class="badge-card">
          <div class="card-header">
            <h3 class="card-title">
              <XIcon :icon="Medal" :size="18" color="#f59e0b"></XIcon>
              成就徽章
            </h3>
            <span class="card-action">查看全部</span>
          </div>
          <div class="badge-list">
            <div 
              v-for="(badge, index) in badges" 
              :key="index"
              class="badge-item"
            >
              <div class="badge-icon" :style="{ background: badge.bg }">
                <XIcon :icon="badge.icon" :size="24" color="#ffffff"></XIcon>
              </div>
              <span class="badge-name">{{ badge.name }}</span>
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
import { defineComponent, ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { XIcon } from '@vtj/ui';
import {
  Medal,
  Setting,
  UserFilled,
  ArrowRight,
  Trophy,
  Download,
  ChatDotRound,
  QuestionFilled,
  InfoFilled,
  SwitchButton,
  DataLine,
  Warning,
  Star,
  Clock,
  Notebook,
  TrendCharts,
  Calendar,
  CircleCheck,
  Refresh,
  Lightning,
  EditPen
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'TabletProfile',
  components: {
    XIcon
  },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'tablet_profile', version: '1788919369989' });
    
    // 用户数据
    const userName = ref('同学');
    const streakDays = ref(15);
    const totalQuestions = ref(1289);
    const accuracy = ref(70.2);
    
    // 学习数据
    const wrongCount = ref(45);
    const collectionCount = ref(128);
    const historyCount = ref(567);
    const notesCount = ref(32);
    
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
    
    // 考试日历
    const upcomingExams = ref([
      { month: '12月', day: '15', name: '公安联考', daysLeft: 45 },
      { month: '1月', day: '10', name: '国考笔试', daysLeft: 71 },
      { month: '3月', day: '1', name: '省考笔试', daysLeft: 130 }
    ]);
    
    // 成就徽章
    const badges = ref([
      { name: '连续7天', icon: Lightning, bg: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)' },
      { name: '做题100', icon: EditPen, bg: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' },
      { name: '正确率80%', icon: CircleCheck, bg: 'linear-gradient(135deg, #1A365D 0%, #2a5298 100%)' }
    ]);
    
    // 加载用户数据
    onMounted(async () => {
      try {
        const auth = window.__VTJ_AUTH__;
        if (auth && auth.isLoggedIn()) {
          const uname = auth.getUsername();
          if (uname) userName.value = uname;
          // 学习统计
          const res = await auth.apiFetch('/api/stats/');
          const data = await res.json();
          totalQuestions.value = data.totalQuestions || 0;
          accuracy.value = data.accuracyRate || 0;
          streakDays.value = data.streak || 0;
          historyCount.value = data.totalQuestions || 0;

          // 计数 + 趋势 + 徽章
          try {
            const [wq, coll, note, trend, badges] = await Promise.all([
              auth.apiFetch('/api/wrong-questions?page=1&page_size=1'),
              auth.apiFetch('/api/collection?page=1&page_size=1'),
              auth.apiFetch('/api/notes'),
              auth.apiFetch('/api/stats/practice-trend?days=7'),
              auth.apiFetch('/api/achievements/earned'),
            ]);
            const wqData = await wq.json();
            const collData = await coll.json();
            const noteData = await note.json();
            wrongCount.value = wqData.total || 0;
            collectionCount.value = collData.total || 0;
            notesCount.value = noteData.total || 0;

            const trendData = await trend.json();
            const t = trendData.trend || [];
            weekData.value = t.map((d: any) => ({
              label: (d.date || '').slice(5),
              count: d.questionsDone || 0,
            }));
            if (weekData.value.length === 0) {
              weekData.value = [{ label: '周一', count: 0 }, { label: '周二', count: 0 }, { label: '周三', count: 0 }, { label: '周四', count: 0 }, { label: '周五', count: 0 }, { label: '周六', count: 0 }, { label: '周日', count: 0 }];
            }

            const badgeData = await badges.json();
            const earned = badgeData.items || [];
            const iconMap: Record<string, any> = { '🔥': Lightning, '📝': EditPen, '✅': CircleCheck, '🏆': Medal, '⭐': Star, '📚': Notebook };
            badges.value = earned.slice(0, 6).map((b: any) => ({
              name: b.name,
              icon: iconMap[b.icon] || Medal,
              bg: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
            }));
          } catch (e) {
            console.error('加载平板详情失败:', e);
          }
        }
      } catch (error) {
        console.error('加载数据失败:', error);
      }
    });
    
    // 方法
    const goToSettings = () => router.push('/profile');
    const goToProfile = () => router.push('/profile');
    
    const goToWrongQuestions = () => router.push('/tablet/wrong-questions');
    const goToCollection = () => router.push('/tablet/favorites');
    const goToHistory = () => router.push('/profile');
    const goToNotes = () => router.push('/page/notes');
    
    const goToAchievements = () => router.push('/achievements');
    const goToDownloads = () => router.push('/page/download_client');
    const goToFeedback = () => router.push('/feedback');
    const goToHelp = () => router.push('/help');
    const goToAbout = () => router.push('/page/about');
    
    const handleLogout = () => {
      if (window.__VTJ_AUTH__) window.__VTJ_AUTH__.logout();
      router.push('/login');
    };
    
    return {
      userName,
      streakDays,
      totalQuestions,
      accuracy,
      wrongCount,
      collectionCount,
      historyCount,
      notesCount,
      weekData,
      maxCount,
      upcomingExams,
      badges,
      goToSettings,
      goToProfile,
      goToWrongQuestions,
      goToCollection,
      goToHistory,
      goToNotes,
      goToAchievements,
      goToDownloads,
      goToFeedback,
      goToHelp,
      goToAbout,
      handleLogout,
      Medal,
      Setting,
      UserFilled,
      ArrowRight,
      Trophy,
      Download,
      ChatDotRound,
      QuestionFilled,
      InfoFilled,
      SwitchButton,
      DataLine,
      Warning,
      Star,
      Clock,
      Notebook,
      TrendCharts,
      Calendar,
      CircleCheck,
      Refresh,
      Lightning,
      EditPen
    };
  }
});
</script>

<style lang="css" scoped>
.tablet-profile-page {
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
  display: flex;
  justify-content: center;
}

.page-title {
  font-size: 18px;
  font-weight: 700;
  color: #1A365D;
  margin: 0;
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
  grid-template-columns: 300px 1fr 300px;
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
  width: 100px;
  height: 100px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}

.user-name {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 4px;
}

.user-role {
  font-size: 14px;
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
  font-size: 22px;
  font-weight: 700;
}

.stat-item .stat-label {
  display: block;
  font-size: 12px;
  opacity: 0.8;
  margin-top: 4px;
}

.menu-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 8px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.menu-list {
  display: flex;
  flex-direction: column;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.menu-item:hover {
  background: #f8f9fc;
}

.menu-icon {
  width: 36px;
  height: 36px;
  background: #f5f7fa;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.menu-name {
  flex: 1;
  font-size: 15px;
  font-weight: 500;
  color: #1a2b5f;
}

.logout-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px;
  background: #ffffff;
  border: 1px solid #ffccc7;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  color: #c41e3a;
  cursor: pointer;
  transition: all 0.3s ease;
}

.logout-btn:hover {
  background: #fff2f0;
}

/* 中间内容区 */
.center-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.data-section,
.trend-section {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
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
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: #1a2b5f;
  margin: 0;
}

.section-action {
  font-size: 13px;
  color: #1890ff;
  cursor: pointer;
}

.data-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.data-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 12px;
  background: #f8f9fc;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.data-card:hover {
  background: #f0f2f5;
  transform: translateY(-2px);
}

.data-icon {
  width: 48px;
  height: 48px;
  background: #ffffff;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.08);
}

.data-value {
  font-size: 24px;
  font-weight: 700;
  color: #1a2b5f;
  margin-bottom: 4px;
}

.data-label {
  font-size: 13px;
  color: #8899aa;
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

/* 右侧面板 */
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.calendar-card,
.badge-card {
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
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0;
}

.card-action {
  font-size: 12px;
  color: #1890ff;
  cursor: pointer;
}

.exam-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.exam-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
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

.badge-list {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.badge-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.badge-icon {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.badge-name {
  font-size: 11px;
  color: #5a6488;
  text-align: center;
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
