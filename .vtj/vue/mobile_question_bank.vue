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
            <span class="chip-count">{{ cat.count }}</span>
          </div>
        </div>
      </section>

      <!-- 历年试卷列表：首屏直接呈现，无需二次点击。
           顶部操作区原有「历年试卷」按钮与本区块内容完全重复，已移除；
           本标题即该功能的唯一可达入口。 -->
      <section class="question-list">
        <div class="list-header">
          <span class="list-title">历年试卷</span>
          <span class="list-sub">点击直接开始作答</span>
        </div>
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
                :color="i <= question.difficulty ? '#f59e0b' : '#e8ecf1'"
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
        <p>{{ emptyText }}</p>
      </div>
    </main>

    <!-- 底部Tab栏 -->
    <!-- 底部Tab栏：统一使用单一真源组件 src/components/MobileTabBar.vue -->
    <!-- 决策 D2：底栏已移除「题库」tab，本页作为练习页下钻的二级页面，归属「练习」高亮 -->
    <MobileTabBar active="practice" />
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, computed, onMounted, onBeforeUnmount } from 'vue';
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
  Trophy
} from '@vtj/icons';
import MobileTabBar from '@/components/MobileTabBar.vue';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'MobileQuestionBank',
  components: {
    XIcon,
    MobileTabBar
  },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'mobile_question_bank', version: '1788919369989' });

    // 搜索
    const showSearch = ref(false);
    const searchQuery = ref('');
    
    // 顶部操作
    // 已移除「快速练习」：它与下方三大科目分类入口职责重叠，
    // 科目化练习统一走「练习」页的科目/子科目/知识点下钻。
    // 首屏没有任何「被选中」的操作项：所有按钮都是跳转或提示，
    // 高亮其中之一会造成误导（原实现默认高亮「历年试卷」）。
    const activeTopAction = ref('');
    // 「历年试卷」按钮已移除：其内容就是下方首屏直出的试卷列表，
    // 再摆一个跳转按钮属于重复入口，故只保留智能组卷/联考小智/错题本/模拟考试。
    const topActions = ref([
      { key: 'smart', name: '智能组卷', icon: Cpu, tag: 'AI' },
      { key: 'ai', name: '联考小智', icon: Cpu, tag: '开发中' },
      { key: 'wrong', name: '错题本', icon: Warning, tag: '' },
      { key: 'mock', name: '模拟考试', icon: Trophy, tag: '' }
    ]);
    
    // 分类
    // key 必须与下方 fetchPapers 的 subjectMap 保持一致（xc/sw/jy），
    // 否则点击该分类会筛不到任何内容，表现为「没有找到相关题目」。
    // 政治理论 / 法律基础不再单列：二者在行测、公专的知识点下钻中已包含。
    const activeCategory = ref('all');
    const categories = ref([
      { key: 'all', name: '全部', count: 0 },
      { key: 'xc', name: '行测', count: 0 },
      { key: 'sw', name: '申论', count: 0 },
      { key: 'jy', name: '公专', count: 0 }
    ]);

    // 加载三科题量统计（真实数据来源：/api/questions/subcategory-stats）
    const loadSubjectStats = async () => {
      const auth = window.__VTJ_AUTH__;
      if (!auth) return;
      try {
        const res = await fetch('/api/questions/subcategory-stats?_t=' + Date.now(), {
          headers: auth.getAuthHeaders ? auth.getAuthHeaders() : {},
          cache: 'no-cache'
        });
        if (!res.ok) return;
        const data = await res.json();
        const sum = (arr) => (arr || []).reduce((acc, item) => acc + (item.count || 0), 0);
        const map = { xc: sum(data.xingce), sw: sum(data.shenlun), jy: sum(data.gongzhuan) };
        categories.value = categories.value.map((c) =>
          c.key === 'all'
            ? { ...c, count: data.total || 0 }
            : { ...c, count: map[c.key] || 0 }
        );
      } catch (error) {
        console.warn('加载科目题量统计失败:', error);
      }
    };
    
    // 题目列表
    const questions = ref([]);
    
    // 空态文案：本区块是「历年试卷」列表，为空通常是「还没有已发布的试卷」
    // （get_paper_list 对普通用户只返回已发布试卷），
    // 而非「搜索没匹配到」。原文案「没有找到相关题目」会让用户误以为题库为空。
    const emptyText = computed(() => {
      if (searchQuery.value) return '没有找到相关试卷';
      if (activeCategory.value !== 'all') return '该科目下暂无已发布试卷';
      return '暂无已发布试卷';
    });

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
    // 提取为具名方法，供 onMounted 与三端同步监听复用
    const loadPaperList = async () => {
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
    };

    onMounted(async () => {
      window.addEventListener('__VTJ_SYNC__', onVTJSync);
      // 科目题量统计与试卷列表并行加载
      loadSubjectStats();
      await loadPaperList();
    });

    // ===== 三端实时同步：题目导入后刷新题量统计与试卷列表 =====
    // 后端导入完成会广播 sync 事件，auth.ts 转发为 __VTJ_SYNC__。
    // 只关心题库范围的事件；防抖 1.5s，避免批量导入时连续请求。
    let syncTimer: any = null;
    const onVTJSync = (e: any) => {
      const d = e && e.detail && e.detail.data;
      if (!d || d.scope !== 'question_bank') return;
      if (syncTimer) clearTimeout(syncTimer);
      syncTimer = setTimeout(() => {
        syncTimer = null;
        loadSubjectStats();
        loadPaperList();
      }, 1500);
    };
    const offVTJSync = () => {
      if (syncTimer) {
        clearTimeout(syncTimer);
        syncTimer = null;
      }
      window.removeEventListener('__VTJ_SYNC__', onVTJSync);
    };

    onBeforeUnmount(offVTJSync);

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
        router.push('/mobile/wrong-questions');
      } else if (key === 'mock') {
        ElMessage.info('模拟考试功能请在电脑端使用');
      }
    };
    
    const selectCategory = (key: string) => {
      activeCategory.value = key;
    };
    
    const startPractice = (question: any) => {
      router.push('/mobile/answer');
    };

    return {
      showSearch,
      searchQuery,
      activeTopAction,
      topActions,
      activeCategory,
      categories,
      filteredQuestions,
      emptyText,
      goBack,
      toggleSearch,
      handleSearch,
      clearSearch,
      selectTopAction,
      selectCategory,
      startPractice,
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
      Trophy
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

/* 分类 chip 上的真实题量（来自 /api/questions/subcategory-stats） */
.chip-count {
  display: inline-block;
  margin-left: 4px;
  font-size: 11px;
  opacity: 0.75;
}
.category-chip.active .chip-count {
  opacity: 0.9;
}

/* 历年试卷区块标题 */
.list-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding: 0 4px 10px;
}
.list-title {
  font-size: 16px;
  font-weight: 700;
  color: #1A365D;
}
.list-sub {
  font-size: 12px;
  color: #8899aa;
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

/* 底部Tab栏样式已收敛到单一真源组件 src/components/MobileTabBar.vue */

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
