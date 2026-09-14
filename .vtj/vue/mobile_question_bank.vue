<!-- 手机端题库页 - VTJ规范版 -->
<template>
  <div class="mobile-question-bank-page">
    <!-- 顶部导航 -->
    <header class="top-nav">
      <div class="nav-left">
        <XIcon :icon="ArrowLeft" :size="22" color="#1A365D" class="nav-back" @click="goBack"></XIcon>
      </div>
      <h1 class="nav-title">题库练习</h1>
      <div class="nav-right">
        <XIcon :icon="Search" :size="22" color="#1A365D" class="nav-icon" @click="toggleSearch"></XIcon>
      </div>
    </header>

    <!-- 搜索栏（可折叠） -->
    <div v-if="showSearch" class="search-bar">
      <div class="search-input-wrapper">
        <XIcon :icon="Search" :size="18" color="#8899aa"></XIcon>
        <input 
          v-model="searchQuery" 
          type="text" 
          placeholder="搜索题目、知识点..." 
          @input="handleSearch"
        />
        <XIcon 
          v-if="searchQuery" 
          :icon="CircleCloseFilled" 
          :size="18" 
          color="#8899aa" 
          class="clear-btn" 
          @click="clearSearch"
        ></XIcon>
      </div>
    </div>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 顶部操作区 -->
      <section class="top-actions">
        <div class="action-scroll">
          <div 
            v-for="(action, index) in topActions" 
            :key="index"
            :class="['action-btn', { active: activeTopAction === action.key }]"
            @click="selectTopAction(action.key)"
          >
            <XIcon :icon="action.icon" :size="20" color="currentColor"></XIcon>
            <span class="action-name">{{ action.name }}</span>
            <span v-if="action.tag" class="action-tag">{{ action.tag }}</span>
          </div>
        </div>
      </section>

      <!-- 分类筛选 -->
      <section class="category-filter">
        <div class="category-scroll">
          <div 
            v-for="(cat, index) in categories" 
            :key="index"
            :class="['category-chip', { active: activeCategory === cat.key }]"
            @click="selectCategory(cat.key)"
          >
            {{ cat.name }}
          </div>
        </div>
      </section>

      <!-- 题目列表 -->
      <section class="question-list">
        <div 
          v-for="(question, index) in filteredQuestions" 
          :key="index"
          class="question-card"
          @click="startPractice(question)"
        >
          <div class="question-header">
            <span class="question-type" :style="{ background: question.typeColor + '18', color: question.typeColor }">
              {{ question.type }}
            </span>
            <span class="question-difficulty">
              <XIcon 
                v-for="i in 5" 
                :key="i" 
                :icon="i <= question.difficulty ? StarFilled : Star" 
                :size="12" 
                :color="i <= question.difficulty ? '#d4a843' : '#e8ecf1'"
              ></XIcon>
            </span>
          </div>
          <h3 class="question-title">{{ question.title }}</h3>
          <div class="question-meta">
            <span class="meta-item">
              <XIcon :icon="Document" :size="14" color="#8899aa"></XIcon>
              {{ question.count }}题
            </span>
            <span class="meta-item">
              <XIcon :icon="Timer" :size="14" color="#8899aa"></XIcon>
              {{ question.time }}分钟
            </span>
            <span class="meta-item">
              <XIcon :icon="User" :size="14" color="#8899aa"></XIcon>
              {{ question.popular }}人练习
            </span>
          </div>
          <div class="question-tags">
            <span v-for="(tag, tIndex) in question.tags" :key="tIndex" class="tag">
              {{ tag }}
            </span>
          </div>
        </div>
      </section>

      <!-- 空状态 -->
      <div v-if="filteredQuestions.length === 0" class="empty-state">
        <XIcon :icon="Search" :size="48" color="#e8ecf1"></XIcon>
        <p>没有找到相关题目</p>
      </div>
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
import { defineComponent, ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { XIcon } from '@vtj/ui';
import { ElMessage } from 'element-plus';
import {
  ArrowLeft,
  ArrowRight,
  Search,
  CircleCloseFilled,
  Document,
  Timer,
  User,
  Star,
  StarFilled,
  HomeFilled,
  Reading,
  Edit,
  ChatLineRound,
  Cpu,
  Clock,
  Warning,
  Trophy,
  EditPen
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'MobileQuestionBank',
  components: {
    XIcon
  },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'mobile_question_bank', version: '1788919369989' });
    
    // 当前Tab
    const activeTab = ref('question');
    
    // 搜索
    const showSearch = ref(false);
    const searchQuery = ref('');
    
    // 顶部操作
    const activeTopAction = ref('quick');
    const topActions = ref([
      { key: 'quick', name: '快速练习', icon: EditPen, tag: 'NEW' },
      { key: 'history', name: '历年试卷', icon: Clock, tag: '' },
      { key: 'smart', name: '智能组卷', icon: Cpu, tag: 'AI' },
      { key: 'ai', name: '联考小智', icon: Cpu, tag: '开发中' },
      { key: 'wrong', name: '错题本', icon: Warning, tag: '' },
      { key: 'mock', name: '模拟考试', icon: Trophy, tag: '' }
    ]);
    
    // 分类
    const activeCategory = ref('all');
    const categories = ref([
      { key: 'all', name: '全部' },
      { key: 'xc', name: '行政职业能力' },
      { key: 'sw', name: '申论' },
      { key: 'jy', name: '公安专业科目' },
      { key: 'zl', name: '政治理论' },
      { key: 'fl', name: '法律基础' }
    ]);
    
    // 题目列表
    const questions = ref([
      {
        id: 1,
        title: '2025年公安联考行测真题精选',
        type: '单选题',
        typeColor: '#1A365D',
        difficulty: 3,
        count: 50,
        time: 60,
        popular: 2345,
        tags: ['行测', '真题', '高频'],
        category: 'xc'
      },
      {
        id: 2,
        title: '申论写作：如何写好策论文',
        type: '主观题',
        typeColor: '#10b981',
        difficulty: 4,
        count: 20,
        time: 120,
        popular: 1892,
        tags: ['申论', '写作', '技巧'],
        category: 'sw'
      },
      {
        id: 3,
        title: '公安基础知识：人民警察法',
        type: '多选题',
        typeColor: '#d4a843',
        difficulty: 2,
        count: 30,
        time: 45,
        popular: 1567,
        tags: ['公安', '法律', '重点'],
        category: 'jy'
      },
      {
        id: 4,
        title: '政治理论：习近平新时代中国特色社会主义思想',
        type: '单选题',
        typeColor: '#1A365D',
        difficulty: 3,
        count: 40,
        time: 50,
        popular: 2100,
        tags: ['政治', '必考', '新大纲'],
        category: 'zl'
      },
      {
        id: 5,
        title: '法律基础：宪法修正案解读',
        type: '判断题',
        typeColor: '#8b5cf6',
        difficulty: 2,
        count: 25,
        time: 30,
        popular: 1234,
        tags: ['法律', '宪法', '基础'],
        category: 'fl'
      },
      {
        id: 6,
        title: '2024年国考行测真题完整版',
        type: '单选题',
        typeColor: '#1A365D',
        difficulty: 4,
        count: 100,
        time: 120,
        popular: 3456,
        tags: ['国考', '真题', '完整'],
        category: 'xc'
      }
    ]);
    
    // 过滤题目
    const filteredQuestions = computed(() => {
      let result = questions.value;
      
      if (activeCategory.value !== 'all') {
        result = result.filter(q => q.category === activeCategory.value);
      }
      
      if (searchQuery.value) {
        const query = searchQuery.value.toLowerCase();
        result = result.filter(q => 
          q.title.toLowerCase().includes(query) ||
          q.tags.some(tag => tag.toLowerCase().includes(query))
        );
      }
      
      return result;
    });
    
    // 方法
    const goBack = () => router.back();
    
    const toggleSearch = () => {
      showSearch.value = !showSearch.value;
      if (!showSearch.value) {
        searchQuery.value = '';
      }
    };
    
    const handleSearch = () => {};
    
    const clearSearch = () => {
      searchQuery.value = '';
    };
    
    const selectTopAction = (key: string) => {
      activeTopAction.value = key;
      if (key === 'smart') {
        router.push('/smart-exam');
      } else if (key === 'ai') {
        // 联考小智：功能还在开发中
        ElMessage.info('联考小智功能还在开发中，敬请期待！');
      } else if (key === 'wrong') {
        router.push('/wrong-questions');
      } else if (key === 'mock') {
        router.push('/mock-exam');
      }
    };
    
    const selectCategory = (key: string) => {
      activeCategory.value = key;
    };
    
    const startPractice = (question: any) => {
      router.push(`/practice/${question.id}`);
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
      showSearch,
      searchQuery,
      activeTopAction,
      topActions,
      activeCategory,
      categories,
      filteredQuestions,
      goBack,
      toggleSearch,
      handleSearch,
      clearSearch,
      selectTopAction,
      selectCategory,
      startPractice,
      switchTab,
      ArrowLeft,
      ArrowRight,
      Search,
      CircleCloseFilled,
      Document,
      Timer,
      User,
      Star,
      StarFilled,
      HomeFilled,
      Reading,
      Edit,
      ChatLineRound,
      Cpu,
  Clock,
      Warning,
      Trophy,
      EditPen
    };
  }
});
</script>

<style lang="css" scoped>
.mobile-question-bank-page {
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

/* 搜索栏 */
.search-bar {
  padding: 12px 16px;
  background: #ffffff;
  border-bottom: 1px solid #f0f2f5;
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  background: #f5f7fa;
  border: 1px solid #e8ecf1;
  border-radius: 8px;
  padding: 0 12px;
}

.search-input-wrapper input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 10px 8px;
  font-size: 14px;
  color: #1a2b5f;
  outline: none;
}

.clear-btn {
  cursor: pointer;
}

/* 主内容区 */
.main-content {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  padding-bottom: 80px;
}

/* 顶部操作区 */
.top-actions {
  margin-bottom: 16px;
}

.action-scroll {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 8px;
  -webkit-overflow-scrolling: touch;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #ffffff;
  border: 1px solid #e8ecf1;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.action-btn.active {
  background: linear-gradient(135deg, #1A365D 0%, #2a5298 100%);
  border-color: #1A365D;
  color: #ffffff;
}

.action-btn:hover:not(.active) {
  border-color: #1A365D;
}

.action-name {
  font-size: 14px;
  font-weight: 600;
}

.action-tag {
  font-size: 10px;
  background: #c41e3a;
  color: #ffffff;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 600;
}

/* 分类筛选 */
.category-filter {
  margin-bottom: 16px;
}

.category-scroll {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 8px;
  -webkit-overflow-scrolling: touch;
}

.category-chip {
  padding: 8px 16px;
  background: #ffffff;
  border: 1px solid #e8ecf1;
  border-radius: 20px;
  font-size: 13px;
  color: #5a6488;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.category-chip.active {
  background: #1A365D;
  border-color: #1A365D;
  color: #ffffff;
}

.category-chip:hover:not(.active) {
  border-color: #1A365D;
  color: #1A365D;
}

/* 题目列表 */
.question-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.question-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
  transition: all 0.3s ease;
}

.question-card:hover {
  box-shadow: 0 4px 16px rgba(26, 54, 95, 0.1);
  transform: translateY(-2px);
}

.question-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.question-type {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 600;
}

.question-difficulty {
  display: flex;
  gap: 2px;
}

.question-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0 0 12px;
  line-height: 1.4;
}

.question-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #8899aa;
}

.question-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tag {
  padding: 4px 10px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 11px;
  color: #5a6488;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-state p {
  font-size: 14px;
  color: #8899aa;
  margin: 16px 0 0;
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
  .action-btn {
    padding: 10px 12px;
  }
  
  .action-name {
    font-size: 13px;
  }
  
  .question-title {
    font-size: 15px;
  }
}
</style>
