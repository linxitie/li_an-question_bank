<!-- 手机端我的页 - VTJ规范版 -->
<template>
  <div class="mobile-profile-page">
    <!-- 顶部导航 -->
    <header class="top-nav">
      <div class="nav-left">
        <XIcon :icon="ArrowLeft" :size="22" color="#1A365D" class="nav-back" @click="goBack"></XIcon>
      </div>
      <h1 class="nav-title">我的</h1>
      <div class="nav-right">
        <XIcon :icon="Setting" :size="22" color="#1A365D" class="nav-icon" @click="goToSettings"></XIcon>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 用户信息卡片 -->
      <section class="user-card">
        <div class="user-avatar">
          <XIcon :icon="UserFilled" :size="40" color="#ffffff"></XIcon>
        </div>
        <div class="user-info">
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
      </section>

      <!-- 学习数据 -->
      <section class="data-section">
        <div class="section-header">
          <h2 class="section-title">
            <XIcon :icon="DataLine" :size="20" color="#1A365D"></XIcon>
            学习数据
          </h2>
        </div>
        <div class="data-grid">
          <div class="data-card" @click="goToWrongQuestions">
            <XIcon :icon="Warning" :size="24" color="#f59e0b"></XIcon>
            <span class="data-value">{{ wrongCount }}</span>
            <span class="data-label">错题本</span>
          </div>
          <div class="data-card" @click="goToCollection">
            <XIcon :icon="Star" :size="24" color="#f59e0b"></XIcon>
            <span class="data-value">{{ collectionCount }}</span>
            <span class="data-label">收藏</span>
          </div>
          <div class="data-card" @click="goToHistory">
            <XIcon :icon="Clock" :size="24" color="#1A365D"></XIcon>
            <span class="data-value">{{ historyCount }}</span>
            <span class="data-label">历史记录</span>
          </div>
          <div class="data-card" @click="goToNotes">
            <XIcon :icon="Notebook" :size="24" color="#10b981"></XIcon>
            <span class="data-value">{{ notesCount }}</span>
            <span class="data-label">笔记</span>
          </div>
        </div>
      </section>

      <!-- 功能列表 -->
      <section class="menu-section">
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
      </section>

      <!-- 退出登录 -->
      <section class="logout-section">
        <button class="logout-btn" @click="handleLogout">
          <XIcon :icon="SwitchButton" :size="18" color="#c41e3a"></XIcon>
          退出登录
        </button>
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
import { defineComponent, ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { XIcon } from '@vtj/ui';
import {
  ArrowLeft,
  ArrowRight,
  Setting,
  UserFilled,
  DataLine,
  Warning,
  Star,
  Clock,
  Notebook,
  Trophy,
  Download,
  ChatDotRound,
  QuestionFilled,
  InfoFilled,
  SwitchButton,
  HomeFilled,
  Reading,
  Edit,
  ChatLineRound,
  User
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'MobileProfile',
  components: {
    XIcon
  },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'mobile_profile', version: '1788919369989' });
    
    // 当前Tab
    const activeTab = ref('profile');
    
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

          // 计数（错题/收藏/笔记）
          try {
            const [wq, coll, note] = await Promise.all([
              auth.apiFetch('/api/wrong-questions?page=1&page_size=1'),
              auth.apiFetch('/api/collection?page=1&page_size=1'),
              auth.apiFetch('/api/notes'),
            ]);
            const wqData = await wq.json();
            const collData = await coll.json();
            const noteData = await note.json();
            wrongCount.value = wqData.total || 0;
            collectionCount.value = collData.total || 0;
            notesCount.value = noteData.total || 0;
          } catch (e) {
            console.error('加载计数失败:', e);
          }
        }
      } catch (error) {
        console.error('加载数据失败:', error);
      }
    });
    
    // 方法
    const goBack = () => router.back();
    
    const goToSettings = () => router.push('/profile');
    
    const goToWrongQuestions = () => router.push('/mobile/wrong-questions');
    const goToCollection = () => router.push('/mobile/favorites');
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
      userName,
      streakDays,
      totalQuestions,
      accuracy,
      wrongCount,
      collectionCount,
      historyCount,
      notesCount,
      goBack,
      goToSettings,
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
      switchTab,
      ArrowLeft,
      ArrowRight,
      Setting,
      UserFilled,
      DataLine,
      Warning,
      Star,
      Clock,
      Notebook,
      Trophy,
      Download,
      ChatDotRound,
      QuestionFilled,
      InfoFilled,
      SwitchButton,
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
.mobile-profile-page {
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
  padding: 24px;
  color: #ffffff;
  margin-bottom: 20px;
}

.user-avatar {
  width: 80px;
  height: 80px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}

.user-info {
  text-align: center;
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

/* 学习数据 */
.data-section {
  margin-bottom: 20px;
}

.section-header {
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

.data-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.data-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 20px 16px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.data-card:hover {
  box-shadow: 0 4px 16px rgba(26, 54, 95, 0.1);
  transform: translateY(-2px);
}

.data-value {
  font-size: 24px;
  font-weight: 700;
  color: #1a2b5f;
}

.data-label {
  font-size: 13px;
  color: #8899aa;
}

/* 功能列表 */
.menu-section {
  margin-bottom: 20px;
}

.menu-list {
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  overflow: hidden;
}

.menu-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid #f0f2f5;
  cursor: pointer;
  transition: background 0.2s ease;
}

.menu-item:last-child {
  border-bottom: none;
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

/* 退出登录 */
.logout-section {
  margin-top: 20px;
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
  .user-card {
    padding: 20px 16px;
  }
  
  .user-avatar {
    width: 64px;
    height: 64px;
  }
  
  .user-name {
    font-size: 20px;
  }
  
  .stat-item .stat-value {
    font-size: 20px;
  }
  
  .data-card {
    padding: 16px 12px;
  }
  
  .data-value {
    font-size: 20px;
  }
}
</style>
