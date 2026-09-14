<!-- 平板端题库页 - VTJ规范版 -->
<template>
  <div class="tablet-question-bank-page">
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
        <!-- 顶部操作 -->
        <div class="action-card">
          <div class="action-item" @click="goToQuickPractice">
            <XIcon :icon="EditPen" :size="24" color="#1A365D"></XIcon>
            <div class="action-info">
              <span class="action-name">快速练习</span>
              <span class="action-desc">随机10题</span>
            </div>
            <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
          </div>
          <div class="action-item" @click="goToSmartExam">
            <XIcon :icon="Cpu" :size="24" color="#10b981"></XIcon>
            <div class="action-info">
              <span class="action-name">智能组卷</span>
              <span class="action-desc">AI推荐</span>
            </div>
            <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
          </div>
          <div class="action-item" @click="goToLiankaoAI">
            <XIcon :icon="QuestionFilled" :size="24" color="#1890ff"></XIcon>
            <div class="action-info">
              <span class="action-name">联考小智</span>
              <span class="action-desc">开发中</span>
            </div>
            <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
          </div>
          <div class="action-item" @click="goToWrongQuestions">
            <XIcon :icon="Warning" :size="24" color="#f59e0b"></XIcon>
            <div class="action-info">
              <span class="action-name">错题本</span>
              <span class="action-desc">薄弱攻克</span>
            </div>
            <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
          </div>
          <div class="action-item" @click="goToMockExam">
            <XIcon :icon="Trophy" :size="24" color="#8b5cf6"></XIcon>
            <div class="action-info">
              <span class="action-name">模拟考试</span>
              <span class="action-desc">实战演练</span>
            </div>
            <XIcon :icon="ArrowRight" :size="16" color="#8899aa"></XIcon>
          </div>
        </div>

        <!-- 分类筛选 -->
        <div class="category-card">
          <div class="card-header">
            <h3 class="card-title">
              <XIcon :icon="Grid" :size="18" color="#1A365D"></XIcon>
              题目分类
            </h3>
          </div>
          <div class="category-list">
            <div 
              v-for="(cat, index) in categories" 
              :key="index"
              :class="['category-item', { active: activeCategory === cat.key }]"
              @click="selectCategory(cat.key)"
            >
              <XIcon :icon="cat.icon" :size="18" color="currentColor"></XIcon>
              <span class="category-name">{{ cat.name }}</span>
              <span class="category-count">{{ cat.count }}</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- 中间内容区 -->
      <section class="center-content">
        <!-- 顶部筛选 -->
        <div class="filter-bar">
          <div class="filter-tabs">
            <div 
              v-for="(tab, index) in filterTabs" 
              :key="index"
              :class="['filter-tab', { active: activeFilter === tab.key }]"
              @click="selectFilter(tab.key)"
            >
              {{ tab.name }}
            </div>
          </div>
          <div class="filter-actions">
            <XIcon :icon="Sort" :size="18" color="#8899aa" class="sort-btn"></XIcon>
            <XIcon :icon="Grid" :size="18" color="#8899aa" class="view-btn" @click="toggleView"></XIcon>
          </div>
        </div>

        <!-- 题目列表 -->
        <div :class="['question-grid', { 'list-view': isListView }]">
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
        </div>

        <!-- 分页 -->
        <div class="pagination">
          <span class="page-info">共 {{ filteredQuestions.length }} 题</span>
          <div class="page-buttons">
            <button class="page-btn" disabled>上一页</button>
            <button class="page-btn active">1</button>
            <button class="page-btn">2</button>
            <button class="page-btn">3</button>
            <button class="page-btn">下一页</button>
          </div>
        </div>
      </section>

      <!-- 右侧面板 -->
      <aside class="right-panel">
        <!-- 学习统计 -->
        <div class="stats-card">
          <div class="card-header">
            <h3 class="card-title">
              <XIcon :icon="DataLine" :size="18" color="#1A365D"></XIcon>
              学习统计
            </h3>
          </div>
          <div class="stats-grid">
            <div class="stat-item">
              <span class="stat-value">{{ todayCount }}</span>
              <span class="stat-label">今日做题</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ accuracy }}%</span>
              <span class="stat-label">正确率</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ totalQuestions }}</span>
              <span class="stat-label">总做题</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ streakDays }}</span>
              <span class="stat-label">连续天数</span>
            </div>
          </div>
        </div>

        <!-- 最近练习 -->
        <div class="recent-card">
          <div class="card-header">
            <h3 class="card-title">
              <XIcon :icon="Clock" :size="18" color="#1A365D"></XIcon>
              最近练习
            </h3>
            <span class="card-action">查看全部</span>
          </div>
          <div class="recent-list">
            <div 
              v-for="(item, index) in recentList" 
              :key="index"
              class="recent-item"
              @click="continuePractice(item)"
            >
              <div class="recent-info">
                <span class="recent-name">{{ item.name }}</span>
                <span class="recent-desc">{{ item.desc }}</span>
              </div>
              <XIcon :icon="ArrowRight" :size="14" color="#8899aa"></XIcon>
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
import { ElMessage } from 'element-plus';
import {
  Medal,
  Search,
  Bell,
  Setting,
  UserFilled,
  ArrowRight,
  EditPen,
  Cpu,
  Warning,
  Trophy,
  Grid,
  Sort,
  Document,
  Timer,
  User,
  Star,
  StarFilled,
  DataLine,
  Clock,
  CircleCheck,
  Refresh,
  HomeFilled,
  Reading,
  Edit,
  ChatLineRound,
  QuestionFilled
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'TabletQuestionBank',
  components: {
    XIcon
  },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'tablet_question_bank', version: '1788919369989' });
    
    // 搜索
    const searchQuery = ref('');
    
    // 视图模式
    const isListView = ref(false);
    
    // 当前筛选
    const activeFilter = ref('all');
    const filterTabs = ref([
      { key: 'all', name: '全部' },
      { key: 'new', name: '最新' },
      { key: 'hot', name: '热门' },
      { key: 'collect', name: '收藏' }
    ]);
    
    // 分类
    const activeCategory = ref('all');
    const categories = ref([
      { key: 'all', name: '全部题目', icon: Grid, count: 1289 },
      { key: 'xc', name: '行政职业能力', icon: EditPen, count: 456 },
      { key: 'sw', name: '申论', icon: Reading, count: 234 },
      { key: 'jy', name: '公安专业科目', icon: Cpu, count: 345 },
      { key: 'zl', name: '政治理论', icon: Document, count: 156 },
      { key: 'fl', name: '法律基础', icon: Document, count: 98 }
    ]);
    
    // 统计数据
    const todayCount = ref(18);
    const accuracy = ref(70.2);
    const totalQuestions = ref(1289);
    const streakDays = ref(15);
    
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
    
    // 最近练习
    const recentList = ref([
      { id: 1, name: '2025年行测真题精选', desc: '正确率 75%' },
      { id: 2, name: '申论写作练习', desc: '完成 3/5 题' },
      { id: 3, name: '公安基础知识', desc: '正确率 82%' }
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
    
    // 加载真实题库数据（已发布试卷，替换下方演示数据）
    onMounted(async () => {
      try {
        const auth = window.__VTJ_AUTH__;
        if (auth && auth.isLoggedIn()) {
          const res = await fetch('/api/papers/list?page=1&page_size=10', { headers: auth.getAuthHeaders() });
          if (res.ok) {
            const data = await res.json();
            if (data.items && data.items.length) {
              const subjectMap: Record<number, string> = { 1: 'xc', 2: 'sw', 3: 'jy' };
              const subjectName: Record<number, string> = { 1: '行测', 2: '申论', 3: '公专' };
              const typeMap: Record<string, string> = { SIMULATION: '模拟卷', PRACTICE: '练习卷', FORMAL: '真题卷' };
              questions.value = data.items.map((p: any) => ({
                id: p.paper_id,
                title: p.paper_name,
                type: typeMap[p.exam_type] || '试卷',
                typeColor: '#1A365D',
                difficulty: p.difficulty || 3,
                count: p.question_count || 0,
                time: p.duration || 0,
                popular: 0,
                tags: [subjectName[p.subject_id] || '题库'],
                category: subjectMap[p.subject_id] || 'all'
              }));
            }
          }
        }
      } catch (error) {
        console.error('加载题库失败:', error);
      }
    });

    // 方法
    const goToNotifications = () => router.push('/notifications');
    const goToSettings = () => router.push('/settings');
    const goToProfile = () => router.push('/profile');
    
    const goToQuickPractice = () => router.push('/practice/quick');
    const goToSmartExam = () => router.push('/smart-exam');
    const goToLiankaoAI = () => {
      // 联考小智：功能还在开发中
      ElMessage.info('联考小智功能还在开发中，敬请期待！');
    };
    const goToWrongQuestions = () => router.push('/wrong-questions');
    const goToMockExam = () => router.push('/mock-exam');
    
    const selectCategory = (key: string) => {
      activeCategory.value = key;
    };
    
    const selectFilter = (key: string) => {
      activeFilter.value = key;
    };
    
    const toggleView = () => {
      isListView.value = !isListView.value;
    };
    
    const startPractice = (question: any) => {
      router.push(`/practice/${question.id}`);
    };
    
    const continuePractice = (item: any) => {
      router.push(`/practice/${item.id}`);
    };
    
    return {
      searchQuery,
      isListView,
      activeFilter,
      filterTabs,
      activeCategory,
      categories,
      todayCount,
      accuracy,
      totalQuestions,
      streakDays,
      filteredQuestions,
      recentList,
      goToNotifications,
      goToSettings,
      goToProfile,
      goToQuickPractice,
      goToSmartExam,
      goToLiankaoAI,
      goToWrongQuestions,
      goToMockExam,
      selectCategory,
      selectFilter,
      toggleView,
      startPractice,
      continuePractice,
      Medal,
      Search,
      Bell,
      Setting,
      UserFilled,
      ArrowRight,
      EditPen,
      Cpu,
      Warning,
      Trophy,
      Grid,
      Sort,
      Document,
      Timer,
      User,
      Star,
      StarFilled,
      DataLine,
      Clock,
      CircleCheck,
      Refresh,
      HomeFilled,
      Reading,
      Edit,
      ChatLineRound,
      QuestionFilled
    };
  }
});
</script>

<style lang="css" scoped>
.tablet-question-bank-page {
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

.action-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.action-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.action-item:hover {
  background: #f8f9fc;
}

.action-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.action-name {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
}

.action-desc {
  font-size: 12px;
  color: #8899aa;
}

.category-card {
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

.category-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.category-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  color: #5a6488;
}

.category-item:hover {
  background: #f8f9fc;
  color: #1A365D;
}

.category-item.active {
  background: #1A365D;
  color: #ffffff;
}

.category-name {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
}

.category-count {
  font-size: 12px;
  color: #8899aa;
}

.category-item.active .category-count {
  color: rgba(255, 255, 255, 0.8);
}

/* 中间内容区 */
.center-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #ffffff;
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.filter-tabs {
  display: flex;
  gap: 12px;
}

.filter-tab {
  padding: 6px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #5a6488;
  cursor: pointer;
  transition: all 0.2s ease;
}

.filter-tab:hover {
  background: #f5f7fa;
}

.filter-tab.active {
  background: #1A365D;
  color: #ffffff;
}

.filter-actions {
  display: flex;
  gap: 12px;
}

.sort-btn,
.view-btn {
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  transition: background 0.2s ease;
}

.sort-btn:hover,
.view-btn:hover {
  background: #f5f7fa;
}

.question-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.question-grid.list-view {
  grid-template-columns: 1fr;
}

.question-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
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

.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #ffffff;
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.page-info {
  font-size: 13px;
  color: #8899aa;
}

.page-buttons {
  display: flex;
  gap: 8px;
}

.page-btn {
  padding: 6px 12px;
  border: 1px solid #e8ecf1;
  border-radius: 6px;
  background: #ffffff;
  font-size: 13px;
  color: #5a6488;
  cursor: pointer;
  transition: all 0.2s ease;
}

.page-btn:hover:not(:disabled) {
  border-color: #1A365D;
  color: #1A365D;
}

.page-btn.active {
  background: #1A365D;
  border-color: #1A365D;
  color: #ffffff;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 右侧面板 */
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.stats-card,
.recent-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.stat-item {
  text-align: center;
  padding: 12px;
  background: #f8f9fc;
  border-radius: 8px;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 700;
  color: #1A365D;
  margin-bottom: 4px;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: #8899aa;
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
  padding: 10px;
  background: #f8f9fc;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.recent-item:hover {
  background: #f0f2f5;
}

.recent-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.recent-name {
  font-size: 14px;
  font-weight: 500;
  color: #1a2b5f;
}

.recent-desc {
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
