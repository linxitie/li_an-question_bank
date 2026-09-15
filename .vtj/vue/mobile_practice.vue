<!-- 手机端练习页 - VTJ规范版 -->
<template>
  <div class="mobile-practice-page">
    <!-- 顶部导航 -->
    <header class="top-nav">
      <div class="nav-left">
        <XIcon :icon="ArrowLeft" :size="22" color="#1A365D" class="nav-back" @click="goBack"></XIcon>
      </div>
      <h1 class="nav-title">练习中心</h1>
      <div class="nav-right">
        <XIcon :icon="Timer" :size="22" color="#1A365D" class="nav-icon"></XIcon>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 学习统计 -->
      <section class="stats-section">
        <div class="stats-card">
          <div class="stat-item">
            <div class="stat-icon">
              <XIcon :icon="TrendCharts" :size="24" color="#10b981"></XIcon>
            </div>
            <div class="stat-info">
              <span class="stat-value">{{ todayCount }}</span>
              <span class="stat-label">今日做题</span>
            </div>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <div class="stat-icon">
              <XIcon :icon="CircleCheck" :size="24" color="#1A365D"></XIcon>
            </div>
            <div class="stat-info">
              <span class="stat-value">{{ accuracy }}%</span>
              <span class="stat-label">正确率</span>
            </div>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <div class="stat-icon">
              <XIcon :icon="Clock" :size="24" color="#f59e0b"></XIcon>
            </div>
            <div class="stat-info">
              <span class="stat-value">{{ studyTime }}</span>
              <span class="stat-label">学习时长</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 快捷入口 -->
      <section class="quick-actions">
        <div class="action-card" @click="goToQuickPractice">
          <div class="action-icon quick">
            <XIcon :icon="EditPen" :size="32" color="#ffffff"></XIcon>
          </div>
          <span class="action-name">快速练习</span>
          <span class="action-desc">随机10题</span>
        </div>
        <div class="action-card" @click="goToWeakPractice">
          <div class="action-icon weak">
            <XIcon :icon="Warning" :size="32" color="#ffffff"></XIcon>
          </div>
          <span class="action-name">薄弱攻克</span>
          <span class="action-desc">错题强化</span>
        </div>
        <div class="action-card" @click="goToSmartPractice">
          <div class="action-icon smart">
            <XIcon :icon="Cpu" :size="32" color="#ffffff"></XIcon>
          </div>
          <span class="action-name">智能练习</span>
          <span class="action-desc">AI推荐</span>
        </div>
        <div class="action-card" @click="goToMockExam">
          <div class="action-icon mock">
            <XIcon :icon="Trophy" :size="32" color="#ffffff"></XIcon>
          </div>
          <span class="action-name">模拟考试</span>
          <span class="action-desc">实战演练</span>
        </div>
      </section>

      <!-- 最近练习 -->
      <section class="recent-section">
        <div class="section-header">
          <h2 class="section-title">
            <XIcon :icon="Clock" :size="20" color="#1A365D"></XIcon>
            最近练习
          </h2>
          <span class="section-action" @click="viewAllRecent">查看全部</span>
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
            <div class="recent-action">
              <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
            </div>
          </div>
        </div>
      </section>

      <!-- 今日目标 -->
      <section class="goal-section">
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
  Timer,
  TrendCharts,
  CircleCheck,
  Clock,
  EditPen,
  Warning,
  Cpu,
  Trophy,
  Aim,
  HomeFilled,
  Reading,
  Edit,
  ChatLineRound,
  User
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'MobilePractice',
  components: {
    XIcon
  },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'mobile_practice', version: '1788919369989' });
    
    // 当前Tab
    const activeTab = ref('practice');
    
    // 统计数据
    const todayCount = ref(18);
    const accuracy = ref(70.2);
    const studyTime = ref('1.8h');
    
    // 今日目标
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
        iconBg: 'linear-gradient(135deg, #1A365D 0%, #2a5298 100%)'
      },
      {
        id: 2,
        name: '申论写作练习',
        desc: '完成 3/5 题',
        icon: Reading,
        iconBg: 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
      },
      {
        id: 3,
        name: '公安基础知识',
        desc: '正确率 82% | 用时 30分钟',
        icon: Cpu,
        iconBg: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
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
    const goBack = () => router.back();
    
    const goToQuickPractice = () => {
      router.push('/practice/quick');
    };
    
    const goToWeakPractice = () => {
      router.push('/practice/weak');
    };
    
    const goToSmartPractice = () => {
      router.push('/practice/smart');
    };
    
    const goToMockExam = () => {
      router.push('/mock-exam');
    };
    
    const viewAllRecent = () => {
      router.push('/practice/history');
    };
    
    const continuePractice = (item: any) => {
      router.push(`/practice/${item.id}`);
    };
    
    const switchTab = (tab: string) => {
      activeTab.value = tab;
      const tabRoutes: Record<string, string> = {
        home: '/',
        question: '/question-bank',
        practice: '/practice',
        forum: '/forum',
        profile: '/profile'
      };
      router.push(tabRoutes[tab] || '/');
    };
    
    return {
      activeTab,
      todayCount,
      accuracy,
      studyTime,
      dailyGoal,
      dailyCompleted,
      dailyGoalPercent,
      recentList,
      goBack,
      goToQuickPractice,
      goToWeakPractice,
      goToSmartPractice,
      goToMockExam,
      viewAllRecent,
      continuePractice,
      switchTab,
      ArrowLeft,
      ArrowRight,
      Timer,
      TrendCharts,
      CircleCheck,
      Clock,
      EditPen,
      Warning,
      Cpu,
      Trophy,
      Aim,
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
.mobile-practice-page {
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

/* 学习统计 */
.stats-section {
  margin-bottom: 20px;
}

.stats-card {
  display: flex;
  align-items: center;
  justify-content: space-around;
  background: #ffffff;
  border-radius: 16px;
  padding: 20px 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  background: #f5f7fa;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #1A365D;
}

.stat-label {
  font-size: 12px;
  color: #8899aa;
}

.stat-divider {
  width: 1px;
  height: 40px;
  background: #f0f2f5;
}

/* 快捷入口 */
.quick-actions {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.action-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 12px;
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(26, 54, 95, 0.1);
}

.action-icon {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
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

.action-name {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  margin-bottom: 4px;
}

.action-desc {
  font-size: 12px;
  color: #8899aa;
}

/* 最近练习 */
.recent-section {
  margin-bottom: 20px;
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
  gap: 12px;
  padding: 16px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
  transition: all 0.3s ease;
}

.recent-item:hover {
  box-shadow: 0 4px 16px rgba(26, 54, 95, 0.1);
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

/* 今日目标 */
.goal-section {
  margin-bottom: 20px;
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
  margin-bottom: 0;
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
  .stats-card {
    padding: 16px 12px;
  }
  
  .stat-icon {
    width: 40px;
    height: 40px;
  }
  
  .stat-value {
    font-size: 18px;
  }
  
  .action-card {
    padding: 16px 8px;
  }
  
  .action-icon {
    width: 56px;
    height: 56px;
  }
}
</style>
