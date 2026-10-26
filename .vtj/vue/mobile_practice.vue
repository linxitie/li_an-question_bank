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

    <!-- 当前科目概览 + 科目层混合练习 -->
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
      <!-- 科目层混合练习：该科目下全部考点统一随机出题 -->
      <button class="mixed-btn subject-mixed" @click="mixedPracticeSubject">
        <XIcon :icon="Lightning" :size="16" color="#1A365D"></XIcon>
        <span>本科目混合练习</span>
        <span class="mixed-sub">{{ subjectAllKpIds.length }} 个考点</span>
      </button>
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

      <!-- 状态1：知识点列表（L2 二级分类 / L3 三级考点） -->
      <div v-else-if="viewState === 'knowledgePoints'">
        <!-- 子科目级聚合混合练习：该子科目下全部知识点统一出题（每层仅此一个） -->
        <button class="mixed-btn kp-mixed" @click="mixedPracticeCurrentSub">
          <XIcon :icon="Lightning" :size="16" color="#1A365D"></XIcon>
          <span>本知识点分类混合练习</span>
          <span class="mixed-sub">{{ currentL3Count }} 个知识点</span>
        </button>
        <template v-for="l2 in knowledgePoints" :key="l2.point_id">
          <div class="kp-item" v-if="(l2.total_questions || 0) > 0">
            <div class="kp-row" @click="toggleL2(l2.point_id)">
              <span class="kp-name">{{ l2.point_name }}</span>
              <span class="kp-stat">{{ l2.done_count || 0 }}/{{ l2.total_questions || 0 }} · {{ l2.accuracy ?? 0 }}%</span>
              <XIcon :icon="isL2Expanded(l2.point_id) ? ArrowDown : ArrowRight" :size="14" color="#8899aa"></XIcon>
            </div>
            <div class="progress-bar">
              <div
                class="progress-fill"
                :style="{ width: calcPct(l2.done_count, l2.total_questions) + '%', background: progressColor(calcPct(l2.done_count, l2.total_questions)) }"
              ></div>
            </div>
            <div class="l3-list" v-if="isL2Expanded(l2.point_id)">
              <template v-for="l3 in l2.children" :key="l3.point_id">
                <div class="l3-row" v-if="(l3.total_questions || 0) > 0" @click.stop="openModeSheet(l3)">
                  <span class="l3-name">{{ l3.point_name }}</span>
                  <span class="l3-stat">{{ l3.done_count || 0 }}/{{ l3.total_questions || 0 }}</span>
                </div>
              </template>
              <div class="empty-l3" v-if="!l2.children || !l2.children.length">暂无下级考点</div>
            </div>
          </div>
        </template>
        <div v-if="!knowledgePoints.length" class="empty-state">
          <span class="empty-title">该子科目暂无知识点</span>
          <span class="empty-desc">返回上级查看其他子科目</span>
        </div>
      </div>

      <!-- 更多练题资源
           决策 D2：底栏已移除「题库」tab，原题库页顶部的历年试卷 / 智能组卷 /
           错题本等入口在此下沉，保证移除底栏后功能不丢失。 -->
      <section class="more-resources">
        <h4 class="more-title">更多练题资源</h4>
        <div class="more-grid">
          <div
            v-for="item in moreResources"
            :key="item.path"
            class="more-item"
            @click="goResource(item.path)"
          >
            <XIcon :icon="item.icon" :size="20" color="#1A365D"></XIcon>
            <span class="more-name">{{ item.name }}</span>
          </div>
        </div>
      </section>
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

    <!-- 底部 Tab：统一使用单一真源组件 src/components/MobileTabBar.vue -->
    <MobileTabBar active="practice" />
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { XIcon } from '@vtj/ui';
import { ElMessage } from 'element-plus';
import MobileTabBar from '@/components/mobile/MobileTabBar.vue';
import { usePracticeStore } from '@/modules/practice/store';
import { onWrongQuestionsChanged } from '@/modules/practice/events';
import {
  ArrowLeft,
  ArrowRight,
  ArrowDown,
  TrendCharts,
  EditPen,
  Trophy,
  Lightning,
  CircleCheck,
  Warning,
  Reading,
  Document
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'MobilePractice',
    components: { XIcon, MobileTabBar },
  setup() {
    const router = useRouter();
    const practiceStore = usePracticeStore();
    let offWrongQuestionsChanged = null;
    const provider = useProvider({ id: 'mobile_practice', version: '1788919369989' });

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
    const knowledgePoints = ref([]); // 当前子科目的知识点（L2，children 为 L3）
    // L2 展开状态：point_id -> boolean
    const expandedL2 = ref<Record<number, boolean>>({});
    const viewState = ref('subModules'); // 'subModules' | 'knowledgePoints'
    // 当前进入的子科目，供知识点列表顶部的聚合「混合练习」按钮确定出题范围
    const currentSubCategory = ref<any>(null);
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
      // 用 practice store 的 type-summary 聚合科目级进度（done/total）
      try {
        await practiceStore.loadTypeSummary();
        const agg = {};
        (practiceStore.typeSummary || []).forEach((t) => {
          if (!agg[t.subject_id]) agg[t.subject_id] = { done: 0, total: 0 };
          agg[t.subject_id].done += t.done_count || 0;
          agg[t.subject_id].total += t.total_questions || 0;
        });
        subjectStats.value = agg;
      } catch (e) {
        console.error('加载科目进度失败:', e);
      }
    }

    async function switchSubject(subjectId) {
      const seq = ++subjectSeq;  // 竞态：只处理最新一次请求
      activeSubject.value = subjectId;
      viewState.value = 'subModules';
      knowledgePoints.value = [];
      expandedL2.value = {};
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
      // 记录当前进入的子科目，供知识点列表顶部的聚合「混合练习」按钮确定出题范围
      currentSubCategory.value = sc;
      expandedL2.value = {};
      viewState.value = 'knowledgePoints';
    }

    function toggleL2(id) {
      expandedL2.value = Object.assign({}, expandedL2.value, { [id]: !expandedL2.value[id] });
    }

    function isL2Expanded(id) {
      return !!expandedL2.value[id];
    }

    function openModeSheet(kp) {
      currentKp.value = kp;
      showModeSheet.value = true;
    }

    function closeModeSheet() {
      showModeSheet.value = false;
    }

    // 当前科目的全部考点 ID（子科目层与科目层混合练习用）：仅取 L3 叶子节点
    const subjectAllKpIds = computed(() => {
      const ids: number[] = [];
      (subModules.value || []).forEach((sc) => {
        ((sc as any).knowledge_points || []).forEach((l2: any) => {
          (l2.children || []).forEach((l3: any) => {
            if (l3?.point_id != null) ids.push(l3.point_id);
          });
        });
      });
      return Array.from(new Set(ids));
    });

    // 当前子科目下 L3 叶子考点总数（混合练习按钮展示用）
    const currentL3Count = computed(() => {
      let n = 0;
      (knowledgePoints.value || []).forEach((l2: any) => {
        n += (l2.children || []).length;
      });
      return n;
    });

    function goAnswer(params: Record<string, any>) {
      const qs = Object.keys(params)
        .map((k) => encodeURIComponent(k) + '=' + encodeURIComponent(params[k] == null ? '' : String(params[k])))
        .join('&');
      router.push('/mobile/answer?' + qs);
    }

    // ===== 混合练习：两个层级 =====
    // 层级一（科目层）：见下方 mixedPracticeSubject
    // 层级二（知识点分类列表顶部）：对该子科目下全部知识点统一出题。
    // 原先在每个子科目/考点卡片内的逐项按钮已按需求移除，避免层层重复入口。
    function mixedPracticeCurrentSub() {
      const sc = currentSubCategory.value;
      if (!sc || sc.id == null) {
        ElMessage.info('该子科目暂无可练习题目');
        return;
      }
      goAnswer({
        knowledge_point_ids: sc.id,
        bySubCategory: 'true',
        mode: 'random',
        subjectId: activeSubject.value,
        level: 'subCategory'
      });
    }

    // 科目层：汇总该科目下所有考点 ID，逗号分隔一次出题
    function mixedPracticeSubject() {
      const ids = subjectAllKpIds.value;
      if (!ids.length) {
        ElMessage.info('该科目下暂无考点，暂不能混合练习');
        return;
      }
      goAnswer({
        knowledge_point_ids: ids.join(','),
        mode: 'random',
        subjectId: activeSubject.value,
        level: 'subject'
      });
    }

    function startPractice(mode) {
      const kp = currentKp.value;
      closeModeSheet();
      if (!kp) return;
      router.push('/mobile/answer?knowledge_point_ids=' + kp.point_id + '&mode=' + mode + '&subjectId=' + activeSubject.value);
    }

    function handleBack() {
      if (viewState.value === 'knowledgePoints') {
        viewState.value = 'subModules';
        knowledgePoints.value = [];
        expandedL2.value = {};
      } else {
        router.back();
      }
    }

    // ===== 更多练题资源 =====
    // 决策 D2：底栏已移除「题库」tab，原题库页顶部的历年试卷 / 智能组卷 /
    // 错题本 / 备考资料入口在此下沉，确保移除底栏后功能不丢失。
    // 说明：历年试卷原先仅能从题库页进入，移除该 tab 后会成为孤链，故必须在此补齐。
    // 「更多练题资源」仅保留与题库页不重复的入口。
    // 历年试卷 / 智能组卷 / 错题本 统一由「题库练习」页承载，避免两处重复入口。
    const moreResources = [
      { name: '题库总览', path: '/mobile/question-bank', icon: Reading },
      { name: '备考资料', path: '/mobile/materials', icon: Document }
    ];

    function goResource(path: string) {
      router.push(path);
    }

    // ===== 三端实时同步：题目导入后刷新当前科目统计 =====
    // 后端导入完成会广播 sync 事件，auth.ts 转发为 __VTJ_SYNC__。
    // 只关心题库范围的事件；防抖 1.5s，避免批量导入时连续请求。
    let syncTimer: number | null = null;
    function onVTJSync(e: any) {
      const d = e && e.detail && e.detail.data;
      if (!d || d.scope !== 'question_bank') return;
      if (syncTimer) clearTimeout(syncTimer);
      syncTimer = window.setTimeout(() => {
        syncTimer = null;
        loadSubjectStats();
        if (activeSubject.value) {
          switchSubject(activeSubject.value);
        }
      }, 1500) as any;
    }
    function offVTJSync() {
      if (syncTimer) {
        clearTimeout(syncTimer);
        syncTimer = null;
      }
      window.removeEventListener('__VTJ_SYNC__', onVTJSync);
    }

    onMounted(async () => {
      window.addEventListener('__VTJ_SYNC__', onVTJSync);
      offWrongQuestionsChanged = onWrongQuestionsChanged(() => {
        loadSubjectStats();
      });
      await loadSubjects();
      loadSubjectStats();
      if (activeSubject.value) {
        await switchSubject(activeSubject.value);
      }
    });

    onBeforeUnmount(() => {
      offVTJSync();
      if (offWrongQuestionsChanged) {
        offWrongQuestionsChanged();
        offWrongQuestionsChanged = null;
      }
    });

    return {
      subjectMeta,
      subjects,
      subjectStats,
      activeSubject,
      subModules,
      knowledgePoints,
      currentL3Count,
      expandedL2,
      toggleL2,
      isL2Expanded,
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
      subjectAllKpIds,
      mixedPracticeSubject,
      mixedPracticeCurrentSub,
      handleBack,
      ArrowLeft,
      ArrowRight,
      ArrowDown,
      TrendCharts,
      EditPen,
      Trophy,
      Lightning,
      CircleCheck,
      Warning,
      Reading,
      Document,
      moreResources,
      goResource,
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
  /* 底部预留 60px 底栏高度 + 安全区，使「更多练题资源」完整可见不被遮挡 */
  padding: 4px 16px calc(76px + env(safe-area-inset-bottom));
  -webkit-overflow-scrolling: touch;
}

/* 子科目卡片（72px） */
/* 混合练习按钮（科目层 / 子科目层 / 考点层通用） */
.mixed-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  width: 100%;
  min-height: var(--touch-target-min, 36px);
  margin-top: 8px;
  padding: 6px 12px;
  background: #f5f7fa;
  border: 1px solid #e8ecf1;
  border-radius: 8px;
  font-size: 12px;
  color: #1A365D;
  cursor: pointer;
  transition: background var(--duration-normal, 300ms) var(--easing-default, cubic-bezier(0.4, 0, 0.2, 1));
}

.mixed-btn:active {
  background: #e8ecf1;
}

.mixed-sub {
  font-size: 11px;
  color: #8899aa;
}

/* 科目层按钮位于进度条下方，视觉上更突出 */
.subject-mixed {
  margin-top: 12px;
  background: #1A365D;
  border-color: #1A365D;
  color: #ffffff;
}

.subject-mixed .mixed-sub {
  color: rgba(255, 255, 255, 0.75);
}

.subject-mixed:active {
  background: #152c4a;
}

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
  margin-right: 6px;
}

/* L2 展开后的 L3 考点列表（缩进，不横向溢出） */
.l3-list {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed #ebEEF5;
  overflow: hidden;
}

.l3-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 4px 8px 18px;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.15s;
}

.l3-row:active {
  background: #f5f7fa;
}

.l3-name {
  font-size: 13px;
  color: #5a6488;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.l3-stat {
  font-size: 11px;
  color: #a0a8bd;
  flex-shrink: 0;
}

.empty-l3 {
  padding: 8px 4px 4px 18px;
  font-size: 12px;
  color: #a0a8bd;
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

/* 更多练题资源（决策 D2：原题库页能力下沉入口） */
.more-resources {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #eef1f5;
}

.more-title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: #1A365D;
}

.more-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.more-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: var(--touch-target-min, 64px);
  padding: 10px 6px;
  background: #f5f7fa;
  border: 1px solid #e8ecf1;
  border-radius: 10px;
  cursor: pointer;
  transition: background var(--duration-normal, 300ms) var(--easing-default, cubic-bezier(0.4, 0, 0.2, 1));
}

.more-item:active {
  background: #e8ecf1;
}

.more-name {
  font-size: 12px;
  color: #303133;
  text-align: center;
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

/* 底部 Tab 样式已收敛到单一真源组件 src/components/MobileTabBar.vue */

@media (max-width: 375px) {
  .subject-card {
    height: 80px;
  }
  .subject-tabs {
    padding: 10px;
  }
}
</style>
