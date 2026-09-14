<!-- 平板端练习页 - VTJ规范版 -->
<template>
  <div class="tablet-practice-page">
    <!-- 顶部导航 -->
    <header class="top-nav">
      <div class="nav-left">
        <div class="logo">
          <XIcon :icon="Medal" :size="28" color="#1A365D"></XIcon>
          <span class="logo-text">砺安题库</span>
        </div>
      </div>
      <div class="nav-center">
        <h1 class="page-title">练习中心</h1>
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
        <!-- 学习统计 -->
        <div class="stats-card">
          <div class="card-header">
            <h3 class="card-title">
              <XIcon :icon="DataLine" :size="18" color="#1A365D"></XIcon>
              今日学习
            </h3>
          </div>
          <div class="stats-grid">
            <div class="stat-item">
              <div class="stat-icon">
                <XIcon :icon="TrendCharts" :size="24" color="#10b981"></XIcon>
              </div>
              <span class="stat-value">{{ todayCount }}</span>
              <span class="stat-label">做题数</span>
            </div>
            <div class="stat-item">
              <div class="stat-icon">
                <XIcon :icon="CircleCheck" :size="24" color="#1A365D"></XIcon>
              </div>
              <span class="stat-value">{{ accuracy }}%</span>
              <span class="stat-label">正确率</span>
            </div>
            <div class="stat-item">
              <div class="stat-icon">
                <XIcon :icon="Clock" :size="24" color="#d4a843"></XIcon>
              </div>
              <span class="stat-value">{{ studyTime }}</span>
              <span class="stat-label">学习时长</span>
            </div>
            <div class="stat-item">
              <div class="stat-icon">
                <XIcon :icon="Aim" :size="24" color="#8b5cf6"></XIcon>
              </div>
              <span class="stat-value">{{ dailyGoalPercent }}%</span>
              <span class="stat-label">目标完成</span>
            </div>
          </div>
        </div>

        <!-- 今日目标 -->
        <div class="goal-card">
          <div class="card-header">
            <h3 class="card-title">
              <XIcon :icon="Aim" :size="18" color="#1A365D"></XIcon>
              今日目标
            </h3>
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
        </div>
      </aside>

      <!-- 中间内容区 -->
      <section class="center-content">
        <!-- 快捷入口 -->
        <div class="quick-actions">
          <div class="action-card" @click="goToQuickPractice">
            <div class="action-icon quick">
              <XIcon :icon="EditPen" :size="32" color="#ffffff"></XIcon>
            </div>
            <div class="action-info">
              <span class="action-name">快速练习</span>
              <span class="action-desc">随机10题，快速巩固</span>
            </div>
            <XIcon :icon="ArrowRight" :size="20" color="#8899aa"></XIcon>
          </div>
          <div class="action-card" @click="goToWeakPractice">
            <div class="action-icon weak">
              <XIcon :icon="Warning" :size="32" color="#ffffff"></XIcon>
            </div>
            <div class="action-info">
              <span class="action-name">薄弱攻克</span>
              <span class="action-desc">针对错题强化训练</span>
            </div>
            <XIcon :icon="ArrowRight" :size="20" color="#8899aa"></XIcon>
          </div>
          <div class="action-card" @click="goToSmartPractice">
            <div class="action-icon smart">
              <XIcon :icon="Cpu" :size="32" color="#ffffff"></XIcon>
            </div>
            <div class="action-info">
              <span class="action-name">智能练习</span>
              <span class="action-desc">AI个性化推荐</span>
            </div>
            <XIcon :icon="ArrowRight" :size="20" color="#8899aa"></XIcon>
          </div>
          <div class="action-card" @click="goToMockExam">
            <div class="action-icon mock">
              <XIcon :icon="Trophy" :size="32" color="#ffffff"></XIcon>
            </div>
            <div class="action-info">
              <span class="action-name">模拟考试</span>
              <span class="action-desc">实战环境模拟</span>
            </div>
            <XIcon :icon="ArrowRight" :size="20" color="#8899aa"></XIcon>
          </div>
        </div>

        <!-- 最近练习 -->
        <div class="recent-section">
          <div class="section-header">
            <h2 class="section-title">
              <XIcon :icon="Clock" :size="20" color="#1A365D"></XIcon>
              最近练习
            </h2>
            <span class="section-action">查看全部</span>
          </div>
          <div class="recent-list">
            <div 
              v-for="(item, index) in recentList" 
              :key="index"
              class="recent-item"
              @click="continuePractice(item)"
            >
              <div class="recent-icon" :style="{ background: item.iconBg }">
                <XIcon :icon="item.icon" :size="24" color="#ffffff"></XIcon>
              </div>
              <div class="recent-info">
                <span class="recent-name">{{ item.name }}</span>
                <span class="recent-desc">{{ item.desc }}</span>
              </div>
              <div class="recent-progress">
                <div class="progress-bar small">
                  <div class="progress-fill" :style="{ width: item.progress + '%' }"></div>
                </div>
                <span class="progress-text">{{ item.progress }}%</span>
              </div>
              <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
            </div>
          </div>
        </div>
      </section>

      <!-- 右侧面板 -->
      <aside class="right-panel">
        <!-- 学习日历 -->
        <div class="calendar-card">
          <div class="card-header">
            <h3 class="card-title">
              <XIcon :icon="Calendar" :size="18" color="#1A365D"></XIcon>
              学习日历
            </h3>
          </div>
          <div class="calendar-grid">
            <div class="calendar-header">
              <span class="calendar-month">2026年9月</span>
            </div>
            <div class="calendar-weekdays">
              <span>日</span>
              <span>一</span>
              <span>二</span>
              <span>三</span>
              <span>四</span>
              <span>五</span>
              <span>六</span>
            </div>
            <div class="calendar-days">
              <div v-for="i in 30" :key="i" :class="['calendar-day', { active: i <= 8, today: i === 8 }]">
                {{ i }}
              </div>
            </div>
          </div>
          <div class="calendar-legend">
            <span class="legend-item">
              <span class="legend-dot active"></span>
              已学习
            </span>
            <span class="legend-item">
              <span class="legend-dot today"></span>
              今天
            </span>
          </div>
        </div>

        <!-- 考试倒计时 -->
        <div class="countdown-card">
          <div class="card-header">
            <h3 class="card-title">
              <XIcon :icon="Timer" :size="18" color="#1A365D"></XIcon>
              考试倒计时
            </h3>
          </div>
          <div class="countdown-list">
            <div class="countdown-item">
              <div class="countdown-info">
                <span class="countdown-name">公安联考</span>
                <span class="countdown-date">12月15日</span>
              </div>
              <div class="countdown-days">
                <span class="days-value">45</span>
                <span class="days-label">天</span>
              </div>
            </div>
            <div class="countdown-item">
              <div class="countdown-info">
                <span class="countdown-name">国考笔试</span>
                <span class="countdown-date">1月10日</span>
              </div>
              <div class="countdown-days">
                <span class="days-value">71</span>
                <span class="days-label">天</span>
              </div>
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
  Bell,
  Setting,
  UserFilled,
  DataLine,
  TrendCharts,
  CircleCheck,
  Clock,
  Aim,
  EditPen,
  Warning,
  Cpu,
  Trophy,
  ArrowRight,
  Calendar,
  Timer,
  Refresh
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'TabletPractice',
  components: {
    XIcon
  },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'tablet_practice', version: '1788919369989' });
    
    // 统计数据
    const todayCount = ref(18);
    const accuracy = ref(70.2);
    const studyTime = ref('1.8h');
    const dailyGoal = ref(40);
    const dailyCompleted = ref(30);
    const dailyGoalPercent = computed(() => Math.round((dailyCompleted.value / dailyGoal.value) * 100));
    
    // 最近练习
    const recentList = ref([
      {
        id: 1,
        name: '2025年行测真题精选',
        desc: '正确率 75% | 用时 45分钟',
        icon: EditPen,
        iconBg: 'linear-gradient(135deg, #1A365D 0%, #2a5298 100%)',
        progress: 75
      },
      {
        id: 2,
        name: '申论写作练习',
        desc: '完成 3/5 题',
        icon: Reading,
        iconBg: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
        progress: 60
      },
      {
        id: 3,
        name: '公安基础知识',
        desc: '正确率 82% | 用时 30分钟',
        icon: Cpu,
        iconBg: 'linear-gradient(135deg, #d4a843 0%, #b8941f 100%)',
        progress: 82
      }
    ]);
    
    // 加载真实统计数据（/api/stats/）
    onMounted(async () => {
      try {
        const auth = window.__VTJ_AUTH__;
        if (auth && auth.isLoggedIn()) {
          const res = await fetch('/api/stats/', { headers: auth.getAuthHeaders() });
          if (res.ok) {
            const data = await res.json();
            todayCount.value = data.todayQuestions || 0;
            accuracy.value = data.accuracyRate || 0;
            studyTime.value = (data.totalStudyHours || 0) + 'h';
            dailyCompleted.value = data.todayQuestions || 0;
          }
        }
      } catch (error) {
        console.error('加载数据失败:', error);
      }
    });

    // 方法
    const goToNotifications = () => router.push('/notifications');
    const goToSettings = () => router.push('/settings');
    const goToProfile = () => router.push('/profile');
    
    const goToQuickPractice = () => router.push('/practice/quick');
    const goToWeakPractice = () => router.push('/practice/weak');
    const goToSmartPractice = () => router.push('/practice/smart');
    const goToMockExam = () => router.push('/mock-exam');
    
    const continuePractice = (item: any) => {
      router.push(`/practice/${item.id}`);
    };
    
    return {
      todayCount,
      accuracy,
      studyTime,
      dailyGoal,
      dailyCompleted,
      dailyGoalPercent,
      recentList,
      goToNotifications,
      goToSettings,
      goToProfile,
      goToQuickPractice,
      goToWeakPractice,
      goToSmartPractice,
      goToMockExam,
      continuePractice,
      Medal,
      Bell,
      Setting,
      UserFilled,
      DataLine,
      TrendCharts,
      CircleCheck,
      Clock,
      Aim,
      EditPen,
      Warning,
      Cpu,
      Trophy,
      ArrowRight,
      Calendar,
      Timer,
      Refresh
    };
  }
});
</script>

<style lang="css" scoped>
.tablet-practice-page {
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
  grid-template-columns: 300px 1fr 280px;
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

.stats-card,
.goal-card {
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 8px;
  background: #f8f9fc;
  border-radius: 10px;
}

.stat-icon {
  width: 40px;
  height: 40px;
  background: #ffffff;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 8px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.08);
}

.stat-value {
  font-size: 18px;
  font-weight: 700;
  color: #1A365D;
  margin-bottom: 2px;
}

.stat-label {
  font-size: 11px;
  color: #8899aa;
}

.goal-progress {
  margin-top: 0;
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

.progress-bar.small {
  height: 6px;
}

/* 中间内容区 */
.center-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.quick-actions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.action-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-card:hover {
  box-shadow: 0 4px 16px rgba(26, 54, 95, 0.1);
  transform: translateY(-2px);
}

.action-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.action-icon.quick {
  background: linear-gradient(135deg, #1A365D 0%, #2a5298 100%);
}

.action-icon.weak {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
}

.action-icon.smart {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

.action-icon.mock {
  background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
}

.action-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.action-name {
  font-size: 16px;
  font-weight: 600;
  color: #1a2b5f;
}

.action-desc {
  font-size: 13px;
  color: #8899aa;
}

.recent-section {
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

.recent-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.recent-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: #f8f9fc;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.recent-item:hover {
  background: #f0f2f5;
}

.recent-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.recent-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.recent-name {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
}

.recent-desc {
  font-size: 12px;
  color: #8899aa;
}

.recent-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 100px;
}

.progress-text {
  font-size: 12px;
  font-weight: 600;
  color: #1A365D;
}

/* 右侧面板 */
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.calendar-card,
.countdown-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.calendar-grid {
  margin-bottom: 12px;
}

.calendar-header {
  text-align: center;
  margin-bottom: 12px;
}

.calendar-month {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
}

.calendar-weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
  margin-bottom: 8px;
}

.calendar-weekdays span {
  text-align: center;
  font-size: 12px;
  color: #8899aa;
}

.calendar-days {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
}

.calendar-day {
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #5a6488;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.calendar-day:hover {
  background: #f5f7fa;
}

.calendar-day.active {
  background: #1A365D;
  color: #ffffff;
}

.calendar-day.today {
  background: #c41e3a;
  color: #ffffff;
}

.calendar-legend {
  display: flex;
  gap: 16px;
  justify-content: center;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #8899aa;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}

.legend-dot.active {
  background: #1A365D;
}

.legend-dot.today {
  background: #c41e3a;
}

.countdown-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.countdown-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #f8f9fc;
  border-radius: 8px;
}

.countdown-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.countdown-name {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
}

.countdown-date {
  font-size: 12px;
  color: #8899aa;
}

.countdown-days {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.days-value {
  font-size: 24px;
  font-weight: 700;
  color: #c41e3a;
}

.days-label {
  font-size: 12px;
  color: #8899aa;
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
