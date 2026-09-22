<!-- 手机端练习页 - 重构版（三科目 + 知识点下钻 + 一屏适配） -->
<template>
  <div class="mobile-practice-page">
    <!-- 顶部导航 -->
    <header class="top-nav">
      <div class="nav-left" @click="handleBack">
        <XIcon :icon="ArrowLeft" :size="20" color="#1A365D" class="nav-back"></XIcon>
      </div>
      <h1 class="nav-title">练习中心</h1>
      <div class="nav-right"></div>
    </header>

    <!-- 三科目 Tab（图标 + 文字 + 进度） -->
    <section class="subject-tabs">
      <div
        v-for="s in subjects"
        :key="s.subject_id"
        :class="['subject-card', { active: activeSubject === s.subject_id }]"
        @click="switchSubject(s.subject_id)"
      >
        <XIcon
          :icon="(subjectMeta[s.subject_id] && subjectMeta[s.subject_id].icon) || TrendCharts"
          :size="24"
          :color="(subjectMeta[s.subject_id] && subjectMeta[s.subject_id].color) || '#3B82F6'"
        ></XIcon>
        <span class="subject-name">{{ s.subject_name }}</span>
        <span class="subject-progress">{{ subjectProgress(s.subject_id) }}%</span>
      </div>
    </section>

    <!-- 当前科目概览 -->
    <section class="subject-overview" v-if="currentSubject">
      <div class="overview-row">
        <span class="overview-text">{{ currentSubject.subject_name }} · 已练 {{ currentDone }}/{{ currentTotal }} 题</span>
        <span class="overview-pct">{{ currentProgress }}%</span>
      </div>
      <div class="progress-bar">
        <div
          class="progress-fill"
          :style="{ width: currentProgress + '%', background: (subjectMeta[currentSubject.subject_id] && subjectMeta[currentSubject.subject_id].color) || '#1A365D' }"
        ></div>
      </div>
    </section>

    <!-- 主内容区（可滚动） -->
    <main class="scroll-area">
      <!-- 状态0：子科目列表 -->
      <div v-if="viewState === 'subModules'">
        <div
          v-for="sc in subModules"
          :key="sc.id"
          class="sub-module-card"
          @click="openSubModule(sc)"
        >
          <div class="sub-header">
            <span class="sub-name">{{ sc.name }}</span>
            <span class="sub-stat">{{ sc.done_count }}/{{ sc.total_questions }} · {{ sc.accuracy ?? 0 }}%</span>
          </div>
          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{ width: calcPct(sc.done_count, sc.total_questions) + '%', background: progressColor(calcPct(sc.done_count, sc.total_questions)) }"
            ></div>
          </div>
        </div>
        <div v-if="loadError" class="empty-state">
          <span class="empty-title">加载失败</span>
          <span class="empty-desc">请检查网络后重试</span>
          <button class="retry-btn" @click="switchSubject(activeSubject)">点击重试</button>
        </div>
        <div v-else-if="loaded && !subModules.length" class="empty-state">
          <span class="empty-title">该科目暂无子科目</span>
          <span class="empty-desc">换一个科目试试</span>
        </div>
      </div>

      <!-- 状态1：知识点列表 -->
      <div v-else-if="viewState === 'knowledgePoints'">
        <div
          v-for="kp in knowledgePoints"
          :key="kp.point_id"
          class="kp-item"
          @click="openModeSheet(kp)"
        >
          <div class="kp-row">
            <span class="kp-name">{{ kp.point_name }}</span>
            <span class="kp-stat">{{ kp.done_count }}/{{ kp.total_questions }} · {{ kp.accuracy ?? 0 }}%</span>
          </div>
          <div class="progress-bar">
            <div
              class="progress-fill"
              :style="{ width: calcPct(kp.done_count, kp.total_questions) + '%', background: progressColor(calcPct(kp.done_count, kp.total_questions)) }"
            ></div>
          </div>
        </div>
        <div v-if="!knowledgePoints.length" class="empty-state">
          <span class="empty-title">该子科目暂无知识点</span>
          <span class="empty-desc">返回上级查看其他子科目</span>
        </div>
      </div>
    </main>

    <!-- 练习模式 Bottom Sheet -->
    <div v-if="showModeSheet" class="sheet-mask" @click="closeModeSheet">
      <div class="bottom-sheet" @click.stop>
        <div class="sheet-handle"></div>
        <h3 class="sheet-title">选择练习模式</h3>
        <div class="mode-item" @click="startPractice('random')">
          <div class="mode-icon"><XIcon :icon="Lightning" :size="20" color="#1A365D"></XIcon></div>
          <div class="mode-info">
            <span class="mode-name">随机练习</span>
            <span class="mode-desc">系统随机出题，快速刷题</span>
          </div>
          <XIcon :icon="ArrowRight" :size="16" color="#c0c4cc"></XIcon>
        </div>
        <div class="mode-item" @click="startPractice('special')">
          <div class="mode-icon"><XIcon :icon="CircleCheck" :size="20" color="#1A365D"></XIcon></div>
          <div class="mode-info">
            <span class="mode-name">专项突破</span>
            <span class="mode-desc">按题型分类练习</span>
          </div>
          <XIcon :icon="ArrowRight" :size="16" color="#c0c4cc"></XIcon>
        </div>
        <div class="mode-item" @click="startPractice('wrong')">
          <div class="mode-icon"><XIcon :icon="Warning" :size="20" color="#1A365D"></XIcon></div>
          <div class="mode-info">
            <span class="mode-name">错题重练</span>
            <span class="mode-desc">巩固薄弱知识点</span>
          </div>
          <XIcon :icon="ArrowRight" :size="16" color="#c0c4cc"></XIcon>
        </div>
        <button class="sheet-cancel" @click="closeModeSheet">取消</button>
      </div>
    </div>

    <!-- 底部 Tab -->
    <nav class="bottom-tab-bar">
      <div :class="['tab-item', { active: activeTab === 'home' }]" @click="switchTab('home')">
        <XIcon :icon="HomeFilled" :size="20" :color="activeTab === 'home' ? '#1A365D' : '#a0a4b8'"></XIcon>
        <span class="tab-label">首页</span>
      </div>
      <div :class="['tab-item', { active: activeTab === 'question' }]" @click="switchTab('question')">
        <XIcon :icon="Reading" :size="20" :color="activeTab === 'question' ? '#1A365D' : '#a0a4b8'"></XIcon>
        <span class="tab-label">题库</span>
      </div>
      <div :class="['tab-item', { active: activeTab === 'practice' }]" @click="switchTab('practice')">
        <XIcon :icon="Edit" :size="20" :color="activeTab === 'practice' ? '#1A365D' : '#a0a4b8'"></XIcon>
        <span class="tab-label">练习</span>
      </div>
      <div :class="['tab-item', { active: activeTab === 'forum' }]" @click="switchTab('forum')">
        <XIcon :icon="ChatLineRound" :size="20" :color="activeTab === 'forum' ? '#1A365D' : '#a0a4b8'"></XIcon>
        <span class="tab-label">论坛</span>
      </div>
      <div :class="['tab-item', { active: activeTab === 'profile' }]" @click="switchTab('profile')">
        <XIcon :icon="User" :size="20" :color="activeTab === 'profile' ? '#1A365D' : '#a0a4b8'"></XIcon>
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
  TrendCharts,
  EditPen,
  Trophy,
  Lightning,
  CircleCheck,
  Warning,
  HomeFilled,
  Reading,
  Edit,
  ChatLineRound,
  User
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'MobilePractice',
  components: { XIcon },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'mobile_practice', version: '1788919369989' });

    // 当前底部 Tab
    const activeTab = ref('practice');

    // 三科目元数据（图标/颜色前端硬编码，后端无此字段）
    const subjectMeta = {
      1: { icon: TrendCharts, color: '#3B82F6' }, // 行测
      2: { icon: EditPen, color: '#10B981' },     // 申论
      3: { icon: Trophy, color: '#F59E0B' },      // 公专
    };

    // ===== 状态机 =====
    const subjects = ref([]);        // 科目列表 [{subject_id, subject_name, ...}]
    const subjectStats = ref({});    // subject_id -> {done, total}
    const activeSubject = ref(1);    // 当前选中科目
    const subModules = ref([]);      // 当前科目子科目（含嵌套 knowledge_points）
    const knowledgePoints = ref([]); // 当前子科目的知识点
    const viewState = ref('subModules'); // 'subModules' | 'knowledgePoints'
    const loaded = ref(false);
    const loading = ref(false);
    const loadError = ref(false);    // 子科目加载失败标记
    let subjectSeq = 0;              // 科目切换竞态序列号

    // 练习模式 Bottom Sheet
    const showModeSheet = ref(false);
    const currentKp = ref(null);

    // ===== 计算属性 =====
    const currentSubject = computed(() =>
      subjects.value.find((s) => s.subject_id === activeSubject.value)
    );
    const currentDone = computed(() => subjectStats.value[activeSubject.value]?.done || 0);
    const currentTotal = computed(() => subjectStats.value[activeSubject.value]?.total || 0);
    const currentProgress = computed(() => {
      const t = currentTotal.value;
      const d = currentDone.value;
      return t ? Math.round((d * 100) / t) : 0;
    });

    // ===== 工具函数 =====
    const calcPct = (done, total) => (total ? Math.round((done * 100) / total) : 0);

    const progressColor = (p) => {
      if (p <= 0) return '#E4E7ED';
      if (p < 30) return '#F56C6C';
      if (p < 60) return '#E6A23C';
      if (p < 80) return '#409EFF';
      return '#52C41A';
    };

    const subjectProgress = (sid) => {
      const s = subjectStats.value[sid];
      return s && s.total ? Math.round((s.done * 100) / s.total) : 0;
    };

    const auth = () => window.__VTJ_AUTH__ || { isLoggedIn: () => false, getAuthHeaders: () => ({}), apiFetch: (url: string, opts?: any) => fetch(url, opts) };

    // ===== API 调用 =====
    async function loadSubjects() {
      try {
        const res = await auth().apiFetch('/api/quick-practice/subjects');
        if (res.ok) {
          const data = await res.json();
          subjects.value = data.items || [];
          if (subjects.value.length) {
            activeSubject.value = subjects.value[0].subject_id;
          }
        }
      } catch (e) {
        console.error('加载科目失败:', e);
      }
    }

    async function loadSubjectStats() {
      // 用 type-summary 聚合科目级进度（done/total）
      try {
        const res = await auth().apiFetch('/api/practice/type-summary');
        if (res.ok) {
          const data = await res.json();
          const agg = {};
          (data.types || []).forEach((t) => {
            if (!agg[t.subject_id]) agg[t.subject_id] = { done: 0, total: 0 };
            agg[t.subject_id].done += t.done_count || 0;
            agg[t.subject_id].total += t.total_questions || 0;
          });
          subjectStats.value = agg;
        }
      } catch (e) {
        console.error('加载科目进度失败:', e);
      }
    }

    async function switchSubject(subjectId) {
      const seq = ++subjectSeq;  // 竞态：只处理最新一次请求
      activeSubject.value = subjectId;
      viewState.value = 'subModules';
      knowledgePoints.value = [];
      loading.value = true;
      loadError.value = false;
      try {
        const res = await auth().apiFetch('/api/quick-practice/sub-categories?subjectId=' + subjectId);
        if (seq !== subjectSeq) return; // 丢弃过期响应
        if (res.ok) {
          const data = await res.json();
          subModules.value = data.items || [];
          loadError.value = false;
        } else {
          subModules.value = [];
          loadError.value = true;
        }
      } catch (e) {
        if (seq !== subjectSeq) return;
        console.error('加载子科目失败:', e);
        subModules.value = [];
        loadError.value = true;
      } finally {
        if (seq === subjectSeq) {
          loaded.value = true;
          loading.value = false;
        }
      }
    }

    function openSubModule(sc) {
      knowledgePoints.value = sc.knowledge_points || [];
      viewState.value = 'knowledgePoints';
    }

    function openModeSheet(kp) {
      currentKp.value = kp;
      showModeSheet.value = true;
    }

    function closeModeSheet() {
      showModeSheet.value = false;
    }

    function startPractice(mode) {
      const kp = currentKp.value;
      closeModeSheet();
      if (!kp) return;
      router.push('/mobile/answer?kpIds=' + kp.point_id + '&mode=' + mode + '&subjectId=' + activeSubject.value);
    }

    function handleBack() {
      if (viewState.value === 'knowledgePoints') {
        viewState.value = 'subModules';
        knowledgePoints.value = [];
      } else {
        router.back();
      }
    }

    function switchTab(tab) {
      activeTab.value = tab;
      const tabRoutes = {
        home: '/mobile/home',
        question: '/mobile/question-bank',
        practice: '/mobile/practice',
        forum: '/mobile/forum',
        profile: '/mobile/profile',
      };
      router.push(tabRoutes[tab] || '/');
    }

    onMounted(async () => {
      await loadSubjects();
      loadSubjectStats();
      if (activeSubject.value) {
        await switchSubject(activeSubject.value);
      }
    });

    return {
      activeTab,
      subjectMeta,
      subjects,
      subjectStats,
      activeSubject,
      subModules,
      knowledgePoints,
      viewState,
      loaded,
      loading,
      loadError,
      showModeSheet,
      currentKp,
      currentSubject,
      currentDone,
      currentTotal,
      currentProgress,
      subjectProgress,
      calcPct,
      progressColor,
      switchSubject,
      openSubModule,
      openModeSheet,
      closeModeSheet,
      startPractice,
      handleBack,
      switchTab,
      ArrowLeft,
      ArrowRight,
      TrendCharts,
      EditPen,
      Trophy,
      Lightning,
      CircleCheck,
      Warning,
      HomeFilled,
      Reading,
      Edit,
      ChatLineRound,
      User,
    };
  },
});
</script>

<style lang="css" scoped>
.mobile-practice-page {
  height: 100dvh;
  height: 100vh;
  background: #f5f7fa;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 顶部导航（44px） */
.top-nav {
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 12px;
  padding-top: env(safe-area-inset-top, 0);
  background: #ffffff;
  border-bottom: 1px solid #f0f2f5;
  flex-shrink: 0;
  z-index: 100;
}

.nav-left,
.nav-right {
  width: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.nav-back {
  cursor: pointer;
  transition: opacity 0.2s;
}

.nav-back:active {
  opacity: 0.6;
}

.nav-title {
  flex: 1;
  text-align: center;
  font-size: 16px;
  font-weight: 600;
  color: #1A365D;
  margin: 0;
}

/* 三科目 Tab */
.subject-tabs {
  display: flex;
  gap: 8px;
  padding: 12px;
  flex-shrink: 0;
}

.subject-card {
  flex: 1;
  height: 88px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  background: #f5f7fa;
  border: 1px solid transparent;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.subject-card:active {
  transform: scale(0.97);
}

.subject-card.active {
  background: #ffffff;
  border-color: #1A365D;
  box-shadow: 0 2px 8px rgba(26, 54, 93, 0.12);
}

.subject-name {
  font-size: 15px;
  font-weight: 600;
  color: #606266;
}

.subject-progress {
  font-size: 12px;
  font-weight: 500;
  color: #909399;
}

/* 当前科目概览（56px） */
.subject-overview {
  padding: 0 16px 8px;
  flex-shrink: 0;
}

.overview-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.overview-text {
  font-size: 13px;
  color: #5a6488;
}

.overview-pct {
  font-size: 13px;
  font-weight: 600;
  color: #1A365D;
}

/* 进度条（统一 4px） */
.progress-bar {
  height: 4px;
  background: #e4e7ed;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}

/* 可滚动区 */
.scroll-area {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 4px 16px 16px;
  -webkit-overflow-scrolling: touch;
}

/* 子科目卡片（72px） */
.sub-module-card {
  background: #ffffff;
  border-radius: 10px;
  padding: 12px 16px;
  margin-bottom: 8px;
  box-shadow: 0 2px 8px rgba(26, 54, 93, 0.04);
  cursor: pointer;
  transition: background 0.15s;
}

.sub-module-card:active {
  background: #ebf0f7;
}

.sub-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.sub-name {
  font-size: 15px;
  font-weight: 500;
  color: #303133;
}

.sub-stat {
  font-size: 12px;
  color: #8899aa;
}

/* 知识点列表项（56px） */
.kp-item {
  background: #ffffff;
  padding: 10px 16px;
  border-bottom: 1px solid #ebEEF5;
  cursor: pointer;
  transition: background 0.15s;
}

.kp-item:first-child {
  border-radius: 10px 10px 0 0;
}

.kp-item:last-child {
  border-bottom: none;
  border-radius: 0 0 10px 10px;
}

.kp-item:active {
  background: #f5f7fa;
}

.kp-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.kp-name {
  font-size: 15px;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 60%;
}

.kp-stat {
  font-size: 12px;
  color: #8899aa;
  flex-shrink: 0;
}

/* 空态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 60px 20px;
}

.empty-title {
  font-size: 16px;
  color: #606266;
  margin-bottom: 8px;
}

.empty-desc {
  font-size: 13px;
  color: #909399;
}

.retry-btn {
  margin-top: 16px;
  padding: 8px 24px;
  border: none;
  border-radius: 20px;
  background: #1A365D;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}

.retry-btn:active {
  opacity: 0.8;
}

/* 练习模式 Bottom Sheet */
.sheet-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 200;
  display: flex;
  align-items: flex-end;
  animation: fade-in 0.2s ease;
}

.bottom-sheet {
  width: 100%;
  max-height: 70vh;
  background: #ffffff;
  border-radius: 16px 16px 0 0;
  padding: 8px 16px calc(16px + env(safe-area-inset-bottom, 0));
  animation: slide-up 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.sheet-handle {
  width: 36px;
  height: 4px;
  background: #dcdfe6;
  border-radius: 2px;
  margin: 4px auto 12px;
}

.sheet-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  text-align: center;
  margin: 0 0 12px;
}

.mode-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 12px;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.15s;
}

.mode-item:active {
  background: #f5f7fa;
}

.mode-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: #f5f7fa;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.mode-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mode-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.mode-desc {
  font-size: 12px;
  color: #8899aa;
}

.sheet-cancel {
  width: 100%;
  height: 44px;
  margin-top: 8px;
  border: none;
  background: #f5f7fa;
  border-radius: 12px;
  font-size: 15px;
  color: #606266;
  cursor: pointer;
}

.sheet-cancel:active {
  opacity: 0.8;
}

@keyframes fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slide-up {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

/* 底部 Tab（56px） */
.bottom-tab-bar {
  display: flex;
  height: 56px;
  background: #ffffff;
  border-top: 1px solid #f0f2f5;
  padding-bottom: env(safe-area-inset-bottom, 0);
  flex-shrink: 0;
  z-index: 100;
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: color 0.2s;
}

.tab-label {
  font-size: 10px;
  font-weight: 500;
  margin-top: 2px;
}

@media (max-width: 375px) {
  .subject-card {
    height: 80px;
  }
  .subject-tabs {
    padding: 10px;
  }
}
</style>
