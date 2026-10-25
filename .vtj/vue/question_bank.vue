<!-- 题库整体模块 -->
<template>
  <div class="question-bank">
    <NavBar></NavBar>
    <main class="qb-main">
      <section class="qb-top">
        <div class="qb-actions">
          <div ref="actionScrollRef" class="action-scroll">
            <button
              v-for="(item, index) in topActions"
              :key="item.key"
              :class="[
                'action-btn',
                { active: state.activeTopAction === item.key }
              ]"
              @click="handleTopAction(item.key)">
              <span class="action-icon"> {{ item.icon }}</span>
              <span class="action-name"> {{ item.name }}</span>
              <span v-if="item.tag" class="action-tag"> {{ item.tag }}</span>
            </button>
          </div>
        </div>
        <div class="qb-sub-actions">
          <button class="sub-btn" @click="handleSubAction('mini')">
            <XIcon :icon="Timer" :size="16" color="#c41e3a"></XIcon>
            <span> 小模考</span>
          </button>
          <button class="sub-btn" @click="handleSubAction('college')">
            <XIcon :icon="Monitor" :size="16" color="#1565c0"></XIcon>
            <span> 院校联考机考系统</span>
          </button>
          <div class="search-box">
            <XIcon :icon="Search" :size="16" color="#8a8faa"></XIcon>
            <input
              v-model="state.searchQuery"
              placeholder="搜索题目..."
              @keyup.enter="handleSearch" />
          </div>
        </div>
      </section>
      <div class="qb-body">
        <div class="qb-left">
          <div class="category-tabs">
            <button
              v-for="(cat, index) in categoryList"
              :key="cat.key"
              :class="['cat-tab', { active: state.activeCategory === cat.key }]"
              @click="switchCategory(cat.key)">
              {{ cat.name }}
            </button>
          </div>
          <div class="subcategory-grid">
            <!-- 加载中骨架 -->
            <div class="subcard subcard-skeleton" v-for="n in 6" :key="'sk'+n" v-if="!state.statsLoaded">
              <div class="skeleton-icon"></div>
              <div class="subcard-info">
                <div class="skeleton-text" style="width:60%;"></div>
                <div class="skeleton-text" style="width:40%;"></div>
              </div>
            </div>
            <!-- 自定义刷题Tab -->
            <div class="custom-practice-card" v-if="state.activeCategory === 'custom' && state.statsLoaded">
              <div class="custom-header">⚙️ 自定义刷题</div>
              <div class="custom-body">
                <div class="custom-row">
                  <label>练习科目</label>
                  <select v-model="state.customConfig.subject">
                    <option value="xc">行测</option>
                    <option value="sl">申论</option>
                    <option value="ga">公专</option>
                  </select>
                </div>
                <div class="custom-row">
                  <label>出题年份</label>
                  <select v-model="state.customConfig.yearRange">
                    <option value="3">前三年</option>
                    <option value="5">近五年</option>
                    <option value="0">不限</option>
                  </select>
                </div>
                <div class="custom-row">
                  <label>具体练习子科目</label>
                  <select v-model="state.customConfig.subCategory">
                    <option v-for="sc in customSubCategories" :key="sc.id" :value="sc.id">{{ sc.name }}</option>
                  </select>
                </div>
                <div class="custom-row">
                  <label>练习数量</label>
                  <input type="number" v-model.number="state.customConfig.questionCount" min="5" max="100" placeholder="20题" />
                </div>
                <div class="custom-row">
                  <label>练习时间（分钟）</label>
                  <input type="number" v-model.number="state.customConfig.timeLimit" min="5" max="180" placeholder="不限制" />
                </div>
                <button class="custom-start-btn" @click="startCustomPractice">开始自定义练习</button>
              </div>
            </div>
            <!-- 子科目卡片（可展开） -->
            <div
              v-for="(sub, index) in currentSubCategories"
              :key="sub.key"
              class="subcard-wrapper"
              v-if="state.activeCategory !== 'custom' && state.statsLoaded">
              <div
                class="subcard"
                @click="toggleSubCategory(sub.key)">
                <div
                  class="subcard-icon div_26rejvefdo6"
                  :style="{ background: sub.bg }">
                  {{ sub.emoji }}
                </div>
                <div class="subcard-info">
                  <span class="subcard-name"> {{ sub.name }}</span>
                  <span class="subcard-count">
                    <span class="count-badge">{{ sub.done_count || 0 }}/{{ sub.total_questions || sub.count || 0 }}</span>
                  </span>
                </div>
                <XIcon :icon="state.expandedSubCategory === sub.key ? ArrowDown : ArrowRightBold" :size="14" :color="state.expandedSubCategory === sub.key ? '#1a2b5f' : '#d1d5db'"></XIcon>
              </div>
              <!-- 展开的考点列表 -->
              <div class="kp-list" v-if="state.expandedSubCategory === sub.key">
                <div class="kp-empty" v-if="!sub.knowledge_points || !sub.knowledge_points.length">
                  <span>暂无考点数据</span>
                </div>
                <div
                  v-for="kp in sub.knowledge_points"
                  :key="kp.point_id"
                  class="kp-row"
                  @click.stop="startKnowledgePractice(sub.key, kp)">
                  <span class="kp-name">{{ kp.point_name }}</span>
                  <span class="kp-badge">{{ kp.done_count || 0 }}/{{ kp.total_questions || 0 }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <aside class="qb-right">
          <!-- 数据加载状态 -->
          <div class="right-card stats-status" v-if="!state.statsLoaded && state.statsLoading">
            <div class="stats-loading">
              <div class="mini-spinner"></div>
              <span>正在获取题库数据...</span>
            </div>
          </div>
          <div class="right-card stats-error" v-if="state.statsError">
            <div class="error-msg">
              <span>{{ state.statsError }}</span>
              <button class="retry-btn" @click="refreshStats">重试</button>
            </div>
          </div>
          <div class="right-card practice-log">
            <div class="right-header">
              <XIcon :icon="DataLine" :size="18" color="#1a2b5f"></XIcon>
              <span> 练习记录</span>
              <span class="view-all-link" @click="openRecordsDialog">查看全部 ›</span>
            </div>
            <!-- 今日/本周/累计（四来源统一口径） -->
            <div class="log-stats">
              <div class="log-item">
                <span class="log-value">{{ state.unifiedStats.today.count }}</span>
                <span class="log-label">今日(题)</span>
              </div>
              <div class="log-item" @click="toggleChart">
                <span class="log-value">{{ state.unifiedStats.week.count }}</span>
                <span class="log-label">本周(题) ▾</span>
              </div>
              <div class="log-item">
                <span class="log-value">{{ state.unifiedStats.total.count }}</span>
                <span class="log-label">累计(题)</span>
              </div>
            </div>
            <!-- 用时和正确率（四来源统一口径） -->
            <div class="log-sub-stats">
              <div class="log-sub-item">
                <span class="log-sub-label">做题用时(今日)</span>
                <span class="log-sub-value">{{ fmtDuration(state.unifiedStats.today.time_spent_seconds) }}</span>
              </div>
              <div class="log-sub-item">
                <span class="log-sub-label">正确率</span>
                <span class="log-sub-value" :class="state.unifiedStats.total.accuracy >= 70 ? 'accuracy-good' : 'accuracy-warn'">{{ state.unifiedStats.total.accuracy }}%</span>
              </div>
            </div>
            <!-- 题目类型进度 -->
            <div class="type-progress-section">
              <div class="type-progress-title">题目类型进度</div>
              <div class="type-badges">
                <div v-for="t in state.practiceTypeSummary" :key="t.subject_code + '_' + t.subcategory"
                     class="type-badge"
                     :class="t.is_completed ? 'badge-done' : 'badge-undone'"
                     @click="startTypePractice(t)">
                  <span class="badge-name">{{ t.subject_name }}·{{ t.subcategory }}</span>
                  <span class="badge-status">{{ t.is_completed ? '已完成' : '未完成' }}</span>
                  <span class="badge-bar"><i :style="{ width: (t.completion_rate || 0) + '%' }"></i></span>
                </div>
              </div>
              <div class="type-progress-empty" v-if="!state.practiceTypeSummary.length">
                <span>暂无做题记录，快去练习吧~</span>
              </div>
            </div>
            <!-- 本周趋势图表 -->
            <div class="chart-section" v-if="state.showChart">
              <div class="chart-header">
                <span class="chart-title">本周做题趋势</span>
                <div class="chart-toggle">
                  <button :class="state.chartType === 'bar' ? 'chart-btn active' : 'chart-btn'" @click="state.chartType = 'bar'; renderChart()">📊 柱状</button>
                  <button :class="state.chartType === 'line' ? 'chart-btn active' : 'chart-btn'" @click="state.chartType = 'line'; renderChart()">📈 折线</button>
                </div>
              </div>
              <div class="chart-container">
                <div class="mini-bars" v-if="state.chartType === 'bar'">
                  <div class="bar-col" v-for="(d, i) in state.practiceTrend" :key="i">
                    <div class="bar-val">{{ d.count }}</div>
                    <div class="bar-fill" :style="{height: barHeight(d.count) + 'px'}"></div>
                    <div class="bar-day">{{ d.weekday }}</div>
                  </div>
                </div>
                <div class="mini-line-chart" v-if="state.chartType === 'line'">
                  <svg width="100%" height="120" viewBox="0 0 280 120">
                    <polyline :points="lineChartPoints()" fill="none" stroke="#c41e3a" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                    <template v-for="(d, i) in state.practiceTrend">
                      <circle :cx="40 + i * 40" :cy="lineChartY(d.count)" r="4" fill="#c41e3a" stroke="#fff" stroke-width="2"></circle>
                    </template>
                  </svg>
                  <div class="line-labels">
                    <span v-for="(d, i) in state.practiceTrend" :key="i">{{ d.weekday }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="log-refresh" v-if="state.practiceError">
              <button class="refresh-link retry-link-error" @click="loadUnifiedData">⚠ {{ state.practiceError }}，点击重试</button>
            </div>
          </div>
          <GoalCard></GoalCard>
          <div class="right-card quick-tools">
            <div class="right-header">
              <span> 快捷工具</span>
            </div>
            <div class="tools-grid">
              <div class="tool-item" @click="navigateTo('wrong_questions')">
                <XIcon
                  :icon="DocumentDelete"
                  :size="20"
                  color="#ef4444"></XIcon>
                <span> 错题集</span>
              </div>
              <div class="tool-item" @click="handleToolClick('note')">
                <XIcon :icon="Edit" :size="20" color="#3b82f6"></XIcon>
                <span> 笔记</span>
              </div>
              <div class="tool-item" @click="handleToolClick('fav')">
                <XIcon :icon="StarFilled" :size="20" color="#f59e0b"></XIcon>
                <span> 收藏</span>
              </div>
              <div class="tool-item" @click="navigateTo('score_analysis')">
                <XIcon :icon="DataAnalysis" :size="20" color="#10b981"></XIcon>
                <span> 成绩分析</span>
              </div>
              <div class="tool-item" @click="navigateTo('gold_purchase')">
                <XIcon
                  :icon="ShoppingCartFull"
                  :size="20"
                  color="#8b5cf6"></XIcon>
                <span> 金币购</span>
              </div>
            </div>
          </div>
          <!-- 练习记录弹窗：知识点进度 + 多来源最近记录（v2 新增） -->
          <div class="rp-mask" v-if="state.recordsDialogVisible" @click.self="closeRecordsDialog">
            <div class="rp-dialog">
              <div class="rp-header">
                <span class="rp-title">练习记录</span>
                <button class="rp-close" @click="closeRecordsDialog">✕</button>
              </div>
              <div class="rp-tabs">
                <button :class="['rp-tab', { active: state.recordsTab === 'progress' }]" @click="switchRecordsTab('progress')">知识点进度</button>
                <button :class="['rp-tab', { active: state.recordsTab === 'records' }]" @click="switchRecordsTab('records')">最近做题记录</button>
              </div>
              <div class="rp-body">
                <!-- Tab1 知识点进度 -->
                <div class="rp-panel" v-if="state.recordsTab === 'progress'">
                  <div class="rp-tip" v-if="state.kpLoading">加载中...</div>
                  <div class="rp-tip" v-else-if="state.kpError">
                    {{ state.kpError }}
                    <button class="refresh-link" @click="loadKnowledgeProgress">重试</button>
                  </div>
                  <div class="rp-tip" v-else-if="!state.kpProgress.subjects.length">暂无知识点数据，完成练习后查看进度</div>
                  <div v-else>
                    <div class="kp-group" v-for="sub in state.kpProgress.subjects" :key="sub.subject_id">
                      <div class="kp-group-title">{{ sub.subject_name }}</div>
                      <div class="kp-line" v-for="k in sub.kps" :key="k.point_id" @click="goKpPractice(sub, k)">
                        <span class="kp-line-name" :title="k.point_name">{{ k.point_name }}</span>
                        <span class="kp-track"><i :style="{ width: k.done_pct + '%' }"></i></span>
                        <span class="kp-nums">{{ k.done }}/{{ k.total }}</span>
                        <span :class="['acc-badge', k.accuracy >= 70 ? 'acc-good' : 'acc-warn']">{{ k.accuracy }}%</span>
                      </div>
                    </div>
                  </div>
                </div>
                <!-- Tab2 最近做题记录 -->
                <div class="rp-panel" v-else>
                  <div class="chip-row">
                    <button v-for="c in state.sourceChips" :key="'s' + c.v"
                            :class="['chip', { active: state.recordsFilter.source === c.v }]"
                            @click="setSourceFilter(c.v)">{{ c.label }}</button>
                  </div>
                  <div class="chip-row">
                    <button v-for="c in state.statusChips" :key="'t' + c.v"
                            :class="['chip', { active: state.recordsFilter.status === c.v }]"
                            @click="setStatusFilter(c.v)">{{ c.label }}</button>
                  </div>
                  <div class="rp-tip" v-if="state.recordsLoading && !state.recentRecords.length">加载中...</div>
                  <div class="rp-tip" v-else-if="!state.recentRecords.length">暂无练习记录，快去刷题吧！</div>
                  <div class="rec-list" v-else>
                    <div class="rec-item" v-for="r in state.recentRecords" :key="r.record_key">
                      <span :class="['src-badge', srcClass(r.source)]">{{ r.source }}</span>
                      <div class="rec-main">
                        <div class="rec-name" :title="r.name">{{ r.name }}</div>
                        <div class="rec-meta">
                          <span>{{ r.status === 'completed' ? '✅ 已完成' : '⏳ 进行中' }}</span>
                          <span v-if="r.score !== null && r.score !== undefined && r.score > 0">{{ r.score }}分</span>
                          <span v-else-if="r.question_count">正确率{{ r.accuracy }}%</span>
                          <span v-if="r.time_spent_seconds">{{ fmtDuration(r.time_spent_seconds) }}</span>
                        </div>
                      </div>
                      <button class="rec-jump" title="继续/查看" @click="goRecordDetail(r)">▶</button>
                    </div>
                    <div class="load-more-wrap" v-if="state.recentRecords.length < state.recordsTotal">
                      <button class="load-more-btn" :disabled="state.recordsLoading" @click="loadMoreRecords">
                        {{ state.recordsLoading ? '加载中...' : '加载更多' }}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </aside>
      </div>
    </main>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { ElMessage } from 'element-plus';
  import { XIcon } from '@vtj/ui';
  import {
    Timer,
    Monitor,
    Search,
    ArrowRightBold,
    ArrowDown,
    DataLine,
    DocumentDelete,
    Edit,
    StarFilled,
    DataAnalysis,
    ShoppingCartFull
  } from '@vtj/icons';
  import NavBar from './navbar.vue';
  import GoalCard from './goal_card.vue';
  import { useProvider } from '@vtj/renderer';
  // P2-73：题库浏览域（② catalog）store 接入；仅只读列表/筛选/详情，不涉及 ⑱⑲⑳
  import { useCatalogStore } from '@/modules/catalog/store';

  // 子科目 Emoji 和背景色映射（静态视觉配置）
  const SUBCARD_STYLES = {
    '政治理论': { emoji: '📖', bg: '#eff6ff' },
    '常识判断': { emoji: '💡', bg: '#f0fdf4' },
    '言语理解与表达': { emoji: '📝', bg: '#e0f2fe' },
    '数量关系': { emoji: '🔢', bg: '#fffbeb' },
    '判断推理': { emoji: '🔍', bg: '#fdf2f8' },
    '资料分析': { emoji: '📊', bg: '#fef2f2' },
    '知觉速度与准确性': { emoji: '⏱️', bg: '#ede9fe' },
    '常识': { emoji: '💡', bg: '#f0fdf4' },
    '速度与知觉训练': { emoji: '⏱️', bg: '#ede9fe' },
    '语言理解与表达': { emoji: '📝', bg: '#e0f2fe' },
    '归纳概括': { emoji: '📋', bg: '#eff6ff' },
    '综合分析': { emoji: '🔬', bg: '#fef2f2' },
    '提出对策': { emoji: '💬', bg: '#fffbeb' },
    '应用文写作': { emoji: '✍️', bg: '#f0fdf4' },
    '议论文写作': { emoji: '📄', bg: '#ede9fe' },
    '职业素养': { emoji: '🛡️', bg: '#eff6ff' },
    '基本警务能力': { emoji: '🚔', bg: '#fef2f2' },
    '基础知识': { emoji: '📚', bg: '#fffbeb' },
    '自定义选题': { emoji: '⚙️', bg: '#f8f9fc' },
  };

  // 子科目 key → 子科目名称映射
  const XC_SUB_MAP = {
    'zzll': '政治理论', 'zlfx': '资料分析', 'slgx': '数量关系',
    'cs': '常识', 'sd': '速度与知觉训练', 'pdtl': '判断推理',
    'yylj': '语言理解与表达',
  };
  const SL_SUB_MAP = {
    'gngk': '归纳概括', 'zhfx': '综合分析', 'tcdc': '提出对策',
    'yywxz': '应用文写作', 'ylwxz': '议论文写作',
  };
  const GA_SUB_MAP = {
    'zysy': '职业素养', 'jbjwnl': '基本警务能力', 'jczs': '基础知识',
  };

  export default defineComponent({
    name: 'QuestionBank',
    components: { NavBar, XIcon, GoalCard },
    setup(props) {
      const provider = useProvider({ id: 'question_bank', version: '1787547281992' });
      // ② 题库浏览域：只读列表数据（题目列表 / 筛选 / 详情）
      const catalogStore = useCatalogStore();
      const state = reactive({
        practiceLog: { today: 0, week: 0, total: 0 },
        practiceRecords: null,
        practiceStats: {
          today: { count: 0, correct: 0, accuracy: 0, time_spent_minutes: 0 },
          week: { count: 0, correct: 0, accuracy: 0, time_spent_minutes: 0 },
          total: { count: 0, correct: 0, accuracy: 0, time_spent_minutes: 0 }
        },
        practiceTypeSummary: [],
        practiceTrend: [],
        showPracticeDetail: false,
        showChart: false,
        chartType: 'bar',
        searchQuery: '',
        activeCategory: 'xc',
        activeTopAction: 'quick',
        // 数据加载状态
        statsLoaded: false,
        statsLoading: false,
        statsError: '',
        statsRetryCount: 0,
        xingceStats: {},
        shenlunStats: {},
        gongzhuanStats: {},
        // 快速练习 — 展开/收起
        expandedSubCategory: null,
        // 快速练习 — 子科目+考点数据缓存
        quickPracticeData: { 1: [], 2: [], 3: [] },
        // 自定义刷题配置
        customConfig: {
          subject: 'xc',
          yearRange: '3',
          subCategory: '',
          questionCount: 20,
          timeLimit: 0,
        },
        // ===== 练习记录优化 v2 新增状态 =====
        unifiedStats: {
          today: { count: 0, correct: 0, accuracy: 0, time_spent_seconds: 0 },
          week: { count: 0, correct: 0, accuracy: 0, time_spent_seconds: 0 },
          total: { count: 0, correct: 0, accuracy: 0, time_spent_seconds: 0 },
          daily_trend: []
        },
        practiceError: '',
        kpProgress: { subjects: [] },
        kpLoading: false,
        kpError: '',
        kpLoaded: false,
        recordsDialogVisible: false,
        recordsTab: 'progress',
        recordsFilter: { source: '', status: '' },
        sourceChips: [
          { v: '', label: '全部' },
          { v: '快速练习', label: '快速练习' },
          { v: '历年试卷', label: '历年试卷' },
          { v: '小模考', label: '小模考' },
          { v: '智能组卷', label: '智能组卷' }
        ],
        statusChips: [
          { v: '', label: '全部' },
          { v: 'completed', label: '已完成' },
          { v: 'in_progress', label: '进行中' }
        ],
        recentRecords: [],
        recordsTotal: 0,
        recordsLimit: 10,
        recordsOffset: 0,
        recordsLoading: false,
        recordsLoaded: false,
      });
      return {
        state,
        props,
        provider,
        catalogStore,
        Timer, Monitor, Search, ArrowRightBold, ArrowDown, DataLine,
        DocumentDelete, Edit, StarFilled, DataAnalysis, ShoppingCartFull
      };
    },
    mounted() {
      this.loadStats();
      this.loadUnifiedData();
      // P2-73：oMounted 等价入口（Options API mounted）拉取题库浏览第一页
      this.catalogStore.load();
      // 检查是否有来自导入页面的刷新通知
      this.checkImportRefreshFlag();
      // 检查是否有来自练习结果页的刷新标记
      this.checkPracticeRefreshFlag();
      // 练习记录自动刷新：切回页面时刷新 + 每5分钟定时刷新（v2）
      var self = this;
      this._rpVisHandler = function () {
        if (!document.hidden) self.loadUnifiedData();
      };
      document.addEventListener('visibilitychange', this._rpVisHandler);
      this._rpTimer = setInterval(function () { self.loadUnifiedData(); }, 5 * 60 * 1000);
    },
    beforeUnmount() {
      if (this._rpTimer) clearInterval(this._rpTimer);
      if (this._rpVisHandler) document.removeEventListener('visibilitychange', this._rpVisHandler);
    },
    computed: {
      topActions() {
        const actions = [
          { key: 'quick', name: '快速练习', icon: '⚡', tag: 'NEW' },
          { key: 'history', name: '历年试卷', icon: '📋' },
          { key: 'smart', name: '智能组卷', icon: '🤖' },
          { key: 'ai', name: '联考小智', icon: '🧠', tag: 'AI' },
        ];
        // 题目导入仅教师和管理员可见
        const auth = window.__VTJ_AUTH__;
        if (auth) {
          const role = auth.getUserRole();
          if (role === 'teacher' || role === 'admin') {
            actions.push({ key: 'questionimport', name: '题目导入', icon: '📥' });
          }
          if (role === 'admin') {
            actions.push({ key: 'adminmaterials', name: '资料管理', icon: '📚' });
          }
        }
        return actions;
      },
      categoryList() {
        return [
          { key: 'xc', name: '行测' },
          { key: 'sl', name: '申论' },
          { key: 'ga', name: '公专' },
          { key: 'custom', name: '自定义刷题' }
        ];
      },
      currentSubCategories() {
        const cat = this.state.activeCategory;
        // 自定义刷题不需要子科目卡片
        if (cat === 'custom') {
          return [];
        }
        // 科目key → subject_id 映射
        const catIdMap = { xc: 1, sl: 2, ga: 3 };
        const subjectId = catIdMap[cat] || 1;

        // 从快速练习API缓存中获取数据
        const items = this.state.quickPracticeData[subjectId] || [];

        // 如果 API 数据为空，回退到旧版静态数据
        if (!items.length) {
          const subDefs = this.getSubDefinitions(cat);
          const statsMap = cat === 'xc' ? this.state.xingceStats
            : cat === 'sl' ? this.state.shenlunStats
            : this.state.gongzhuanStats;

          return subDefs.map(function(def) {
            const realCount = statsMap[def.name] !== undefined ? statsMap[def.name] : 0;
            return {
              key: def.key,
              name: def.name,
              total_questions: realCount,
              done_count: 0,
              count: realCount,
              knowledge_points: [],
              emoji: (SUBCARD_STYLES[def.name] || {}).emoji || '📝',
              bg: (SUBCARD_STYLES[def.name] || {}).bg || '#f8f9fc',
            };
          });
        }

        // 使用API返回的新数据结构
        var subDefs = this.getSubDefinitions(cat);
        var nameKeyMap = {};
        subDefs.forEach(function(d) { nameKeyMap[d.name] = d.key; });

        return items.map(function(item) {
          var defKey = nameKeyMap[item.name] || item.name;
          return {
            key: defKey,
            name: item.name,
            id: item.id,
            total_questions: item.total_questions || 0,
            done_count: item.done_count || 0,
            count: item.total_questions || 0,
            knowledge_points: item.knowledge_points || [],
            emoji: (SUBCARD_STYLES[item.name] || {}).emoji || '📝',
            bg: (SUBCARD_STYLES[item.name] || {}).bg || '#f8f9fc',
          };
        });
      },
      customSubCategories() {
        // 返回当前自定义配置下可选子科目列表
        var cat = this.state.customConfig.subject || 'xc';
        var catIdMap = { xc: 1, sl: 2, ga: 3 };
        var subjectId = catIdMap[cat] || 1;
        var items = this.state.quickPracticeData[subjectId] || [];
        return items.map(function(item) {
          return { id: item.id, name: item.name };
        });
      }
    },
    methods: {
      // ========== 导入刷新通知 ==========
      checkImportRefreshFlag() {
        try {
          var ts = sessionStorage.getItem('__VTJ_BANK_NEEDS_REFRESH__');
          if (ts) {
            sessionStorage.removeItem('__VTJ_BANK_NEEDS_REFRESH__');
            var elapsed = Date.now() - parseInt(ts, 10);
            if (elapsed < 30000 && this.state.statsLoaded) {
              this.refreshStats();
            }
          }
        } catch(e) {}
      },
      checkPracticeRefreshFlag() {
        try {
          var flag = sessionStorage.getItem('refresh_practice');
          if (flag === '1') {
            sessionStorage.removeItem('refresh_practice');
            // 延迟刷新，确保数据已写入
            var self = this;
            setTimeout(function() {
              self.loadPracticeRecords();
            }, 500);
          }
        } catch(e) {}
      },
      // ========== 数据加载 ==========
      getSubDefinitions(category) {
        if (category === 'xc') {
          return Object.keys(XC_SUB_MAP).map(function(k) {
            return { key: k, name: XC_SUB_MAP[k] };
          });
        }
        if (category === 'sl') {
          return Object.keys(SL_SUB_MAP).map(function(k) {
            return { key: k, name: SL_SUB_MAP[k] };
          });
        }
        if (category === 'ga') {
          return Object.keys(GA_SUB_MAP).map(function(k) {
            return { key: k, name: GA_SUB_MAP[k] };
          });
        }
        return [];
      },
      async loadStats() {
        var self = this;
        this.state.statsLoading = true;
        this.state.statsError = '';
        var maxRetries = 2;
        var retryDelay = 800;

        var attempt = function(retryCount) {
          return self._doLoadStats(retryCount).catch(function(e) {
            if (retryCount < maxRetries) {
              return new Promise(function(resolve) {
                setTimeout(function() {
                  resolve(attempt(retryCount + 1));
                }, retryDelay * (retryCount + 1));
              });
            }
            throw e;
          });
        };

        try {
          await attempt(0);
        } catch (e) {
          this.state.statsError = '无法连接服务器，请检查网络后刷新页面';
        } finally {
          this.state.statsLoading = false;
        }
      },
      async _doLoadStats(retryCount) {
        // === 认证守卫：必须先登录才能获取数据 ===
        var isAuthed = await this.ensureLogin();
        if (!isAuthed) {
          this.state.statsError = '请先登录后查看题库数据';
          this.state.statsLoading = false;
          // 延迟跳转到登录页
          var self = this;
          setTimeout(function() { self.navigateToLogin(); }, 1200);
          throw new Error('[loadStats] 未登录');
        }
        // 添加时间戳破坏浏览器缓存
        var ts = Date.now();
        var res = await this.fetchWithRetry('/api/questions/subcategory-stats?_t=' + ts, {
          headers: this.getJsonHeaders(),
          cache: 'no-cache',
        });
        if (!res.ok) {
          var msg = '[loadStats] HTTP ' + res.status;
          if (res.status === 401) {
            this.state.statsError = '登录已过期，请重新登录';
            // 清除过期凭据并跳转登录
            this.clearAuthAndRedirect();
          } else if (res.status >= 500) {
            this.state.statsError = '服务器内部错误(' + res.status + ')，请稍后重试';
          } else {
            this.state.statsError = '请求失败(' + res.status + ')，正在重试...';
          }
          throw new Error(msg);
        }
        var data = await res.json();
        if (!data || typeof data.total === 'undefined') {
          this.state.statsError = '返回数据格式异常';
          throw new Error('[loadStats] 无效响应');
        }
        var toMap = function(arr) {
          var m = {};
          (arr || []).forEach(function(item) { m[item.name] = item.count || 0; });
          return m;
        };
        this.state.xingceStats = toMap(data.xingce);
        this.state.shenlunStats = toMap(data.shenlun);
        this.state.gongzhuanStats = toMap(data.gongzhuan);
        this.state.practiceLog.total = data.total || 0;
        this.state.statsLoaded = true;
        this.state.statsError = '';
        this.state.statsRetryCount = retryCount;
        // 异步加载练习记录
        this.loadPracticeRecords();
        // 异步加载快速练习三级分类数据（3个科目并行）
        this.fetchQuickPracticeData('xc');
        this.fetchQuickPracticeData('sl');
        this.fetchQuickPracticeData('ga');
      },
      async loadPracticeRecords() {
        try {
          var headers = this.getAuthHeaders();
          // 加载统计卡片数据
          var statsRes = await fetch('/api/practice/stats-card', { headers: headers });
          if (statsRes.ok) {
            var statsData = await statsRes.json();
            this.state.practiceStats = {
              today: statsData.today || { count: 0, correct: 0, accuracy: 0, time_spent_minutes: 0 },
              week: statsData.week || { count: 0, correct: 0, accuracy: 0, time_spent_minutes: 0 },
              total: statsData.total || { count: 0, correct: 0, accuracy: 0, time_spent_minutes: 0 }
            };
            this.state.practiceTrend = statsData.daily_trend || [];
            // 同步旧字段
            this.state.practiceLog.today = statsData.today ? statsData.today.count : 0;
            this.state.practiceLog.week = statsData.week ? statsData.week.count : 0;
            this.state.practiceLog.total = statsData.total ? statsData.total.count : 0;
          }
          // 加载题目类型进度
          var typeRes = await fetch('/api/practice/type-summary', { headers: headers });
          if (typeRes.ok) {
            var typeData = await typeRes.json();
            this.state.practiceTypeSummary = typeData.types || [];
          }
          // 如果图表已展开则重新渲染
          if (this.state.showChart) {
            this.renderChart();
          }
        } catch(e) { /* 静默 */ }
      },
      // ========== 快速练习三级分类数据加载 ==========
      async fetchQuickPracticeData(catKey) {
        var catIdMap = { xc: 1, sl: 2, ga: 3 };
        var subjectId = catIdMap[catKey];
        if (!subjectId) return;
        try {
          var headers = this.getJsonHeaders();
          var res = await fetch('/api/quick-practice/sub-categories?subjectId=' + subjectId, {
            headers: headers,
          });
          if (res.ok) {
            var data = await res.json();
            this.state.quickPracticeData[subjectId] = data.items || [];
          }
        } catch(e) {
          // 仅在开发模式输出，避免生产环境控制台噪音（解决"5条日志"折叠报错）
          if (process.env.NODE_ENV === 'development') {
            console.warn('[fetchQuickPracticeData] 加载失败:', e);
          }
        }
      },
      refreshStats() {
        // 强制刷新（清缓存重新加载）
        this.state.statsLoaded = false;
        this.state.statsError = '';
        this.state.xingceStats = {};
        this.state.shenlunStats = {};
        this.state.gongzhuanStats = {};
        this.state.practiceLog.total = 0;
        this.loadStats();
      },

      // ========== 练习记录交互方法 ==========
      toggleChart() {
        this.state.showChart = !this.state.showChart;
        if (this.state.showChart) {
          this.renderChart();
        }
      },
      startTypePractice(type) {
        // 跳转到答题页，携带科目和子科目参数
        if (type.subject_code === 'xc') {
          this.$router.push('/exercise?subject=xc&subcategory=' + encodeURIComponent(type.subcategory));
        } else if (type.subject_code === 'sl') {
          this.$router.push('/exercise?subject=sl&subcategory=' + encodeURIComponent(type.subcategory));
        } else if (type.subject_code === 'ga') {
          this.$router.push('/exercise?subject=ga&subcategory=' + encodeURIComponent(type.subcategory));
        }
      },
      barHeight(count) {
        var maxVal = 1;
        (this.state.practiceTrend || []).forEach(function(d) {
          if (d.count > maxVal) maxVal = d.count;
        });
        return Math.max(4, Math.round((count / maxVal) * 80));
      },
      lineChartPoints() {
        var trend = this.state.practiceTrend || [];
        if (!trend.length) return '';
        var maxCount = 1;
        trend.forEach(function(d) { if (d.count > maxCount) maxCount = d.count; });
        var points = [];
        for (var i = 0; i < trend.length; i++) {
          var x = 40 + i * 40;
          var y = 110 - Math.round((trend[i].count / maxCount) * 95);
          points.push(x + ',' + y);
        }
        return points.join(' ');
      },
      lineChartY(count) {
        var trend = this.state.practiceTrend || [];
        var maxCount = 1;
        trend.forEach(function(d) { if (d.count > maxCount) maxCount = d.count; });
        return 110 - Math.round((count / maxCount) * 95);
      },
      renderChart() {
        // 图表数据在 state.practiceTrend 中，通过 computed 属性自动更新
        // 此方法可留空用于未来 ECharts 集成
      },
      // ========== 练习记录 v2：统一统计 / 弹窗 / 跳转 ==========
      async loadUnifiedData() {
        var ok = true;
        try {
          var res = await fetch('/api/practice/unified-stats', { headers: this.getJsonHeaders() });
          if (!res.ok) throw new Error('HTTP ' + res.status);
          var data = await res.json();
          var zero = { count: 0, correct: 0, accuracy: 0, time_spent_seconds: 0 };
          this.state.unifiedStats = {
            today: data.today || zero,
            week: data.week || zero,
            total: data.total || zero,
            daily_trend: data.daily_trend || []
          };
          // 同步旧字段与趋势图数据源（保持图表逻辑不变）
          this.state.practiceLog.today = data.today ? data.today.count : 0;
          this.state.practiceLog.week = data.week ? data.week.count : 0;
          this.state.practiceLog.total = data.total ? data.total.count : 0;
          this.state.practiceTrend = data.daily_trend || [];
        } catch (e) {
          ok = false;
        }
        this.state.practiceError = ok ? '' : '统计数据加载失败';
      },
      fmtDuration(sec) {
        sec = parseInt(sec || 0, 10);
        if (sec <= 0) return '0分钟';
        if (sec < 60) return sec + '秒';
        var m = Math.round(sec / 60);
        if (m < 60) return m + '分钟';
        var h = Math.floor(m / 60), mm = m % 60;
        return h + '小时' + (mm ? mm + '分' : '');
      },
      openRecordsDialog() {
        this.state.recordsDialogVisible = true;
        if (!this.state.kpLoaded) this.loadKnowledgeProgress();
        if (!this.state.recordsLoaded) this.fetchRecentRecords(true);
      },
      closeRecordsDialog() {
        this.state.recordsDialogVisible = false;
      },
      switchRecordsTab(tab) {
        this.state.recordsTab = tab;
      },
      async loadKnowledgeProgress() {
        this.state.kpLoading = true;
        this.state.kpError = '';
        try {
          var res = await fetch('/api/practice/knowledge-progress', { headers: this.getJsonHeaders() });
          if (!res.ok) throw new Error('HTTP ' + res.status);
          var data = await res.json();
          this.state.kpProgress = { subjects: data.subjects || [] };
          this.state.kpLoaded = true;
        } catch (e) {
          this.state.kpError = '知识点进度加载失败';
        } finally {
          this.state.kpLoading = false;
        }
      },
      goKpPractice(sub, k) {
        // 与既有协议对齐：exercise 页期望 xc/sl/ga 键（种子数据的 subject_code 可能为 auto_*）
        var catIdMap = { 1: 'xc', 2: 'sl', 3: 'ga' };
        var cat = catIdMap[sub.subject_id] || sub.subject_code || '';
        this.$router.push('/exercise?subject=' + cat
          + '&kpId=' + k.point_id
          + '&kpName=' + encodeURIComponent(k.point_name || ''));
      },
      async fetchRecentRecords(reset) {
        if (this.state.recordsLoading) return;
        this.state.recordsLoading = true;
        try {
          if (reset) this.state.recordsOffset = 0;
          var params = new URLSearchParams();
          params.set('limit', String(this.state.recordsLimit));
          params.set('offset', String(this.state.recordsOffset));
          if (this.state.recordsFilter.source) params.set('source', this.state.recordsFilter.source);
          if (this.state.recordsFilter.status) params.set('status', this.state.recordsFilter.status);
          var res = await fetch('/api/practice/recent-records?' + params.toString(), { headers: this.getJsonHeaders() });
          if (!res.ok) throw new Error('HTTP ' + res.status);
          var data = await res.json();
          var items = data.items || [];
          this.state.recentRecords = reset ? items : this.state.recentRecords.concat(items);
          this.state.recordsTotal = data.total || 0;
          this.state.recordsOffset = reset ? items.length : this.state.recordsOffset + items.length;
          this.state.recordsLoaded = true;
        } catch (e) {
          ElMessage.error('做题记录加载失败');
        } finally {
          this.state.recordsLoading = false;
        }
      },
      setSourceFilter(v) {
        if (this.state.recordsFilter.source === v) return;
        this.state.recordsFilter.source = v;
        this.fetchRecentRecords(true);
      },
      setStatusFilter(v) {
        if (this.state.recordsFilter.status === v) return;
        this.state.recordsFilter.status = v;
        this.fetchRecentRecords(true);
      },
      loadMoreRecords() {
        this.fetchRecentRecords(false);
      },
      goRecordDetail(item) {
        var jump = item.jump || { path: '/', params: {} };
        var p = jump.params || {};
        var qs = Object.keys(p).map(function (k) {
          return encodeURIComponent(k) + '=' + encodeURIComponent(p[k]);
        }).join('&');
        this.$router.push(jump.path + (qs ? '?' + qs : ''));
      },
      srcClass(source) {
        return {
          '快速练习': 'src-qp', '历年试卷': 'src-past',
          '小模考': 'src-mock', '智能组卷': 'src-smart'
        }[source] || 'src-qp';
      },

      // ========== 认证辅助 ==========
      getJsonHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        return this.getAuthHeaders(headers);
      },
      getAuthHeaders(init) {
        const h = init || {};
        try {
          if (window.__VTJ_AUTH__ && window.__VTJ_AUTH__.getAuthHeaders) {
            var authH = window.__VTJ_AUTH__.getAuthHeaders();
            if (authH && authH['Authorization']) {
              h['Authorization'] = authH['Authorization'];
            }
          }
        } catch(e) {}
        return h;
      },
      async ensureLogin() {
        if (window.__VTJ_AUTH__ && window.__VTJ_AUTH__.ensureAuth) {
          try {
            var ok = await window.__VTJ_AUTH__.ensureAuth();
            return ok;
          } catch(e) {
            return false;
          }
        }
        return false;
      },
      navigateToLogin() {
        try {
          this.$router.push('/login');
        } catch(e) {
          window.location.href = '/#/login';
        }
      },
      clearAuthAndRedirect() {
        try {
          if (window.__VTJ_AUTH__ && window.__VTJ_AUTH__.logout) {
            window.__VTJ_AUTH__.logout();
          }
        } catch(e) {}
        this.navigateToLogin();
      },
      async fetchWithRetry(url, options) {
        const res = await fetch(url, options);
        if (res.status === 401) {
          await this.ensureLogin();
          const newHeaders = this.getJsonHeaders();
          Object.keys(newHeaders).forEach(function(k) {
            if (!options.headers) options.headers = {};
            options.headers[k] = newHeaders[k];
          });
          return fetch(url, options);
        }
        return res;
      },

      // ========== 交互方法 ==========
      handleTopAction(key) {
        this.state.activeTopAction = key;
        if (key === 'questionimport') {
          this.$router.push('/question-import');
        } else if (key === 'adminmaterials') {
          this.$router.push('/admin/materials');
        } else if (key === 'quick') {
          // 快速练习：进入当前选中科目的综合练习（不限子科目，传空subcategory由后端返回该科目所有题目）
          var catKey = this.state.activeCategory;
          if (catKey === 'custom') catKey = 'xc';
          this.$router.push('/exercise?subject=' + catKey + '&subcategory=');
        } else if (key === 'history') {
          this.$router.push('/student/papers');
        } else if (key === 'smart') {
          this.$router.push('/smart-exam');
        } else if (key === 'ai') {
          this.$router.push('/ai-assistant');
        }
      },
      switchCategory(key) {
        this.state.activeCategory = key;
        this.state.expandedSubCategory = null;
        // 切换到非自定义Tab时，加载快速练习数据
        if (key !== 'custom') {
          this.fetchQuickPracticeData(key);
        }
      },
      handleSubAction(key) {
        if (key === 'mini') {
          this.startMiniExam();
        } else if (key === 'college') {
          ElMessage.info('院校联考机考系统开发中');
        }
      },
      async startMiniExam() {
        var auth = window.__VTJ_AUTH__;
        try {
          var res = await auth.apiFetch('/api/exams/list?exam_type=PRACTICE&page_size=5');
          var data = await res.json();
          var papers = data.data || data.items || [];
          if (papers.length > 0) {
            // 随机选取一份练习试卷
            var paper = papers[Math.floor(Math.random() * papers.length)];
            var startRes = await auth.apiFetch('/api/exams/' + paper.paper_id + '/start', { method: 'POST' });
            var startData = await startRes.json();
            if (startData.record_id) {
              this.$router.push('/answer?record_id=' + startData.record_id + '&paper_id=' + paper.paper_id);
            }
          } else {
            ElMessage.info('暂无可用模考试卷，请等待教师发布');
          }
        } catch(e) {
          ElMessage.info('暂无可用模考试卷');
        }
      },
      handleSearch() {
        var q = (this.state.searchQuery || '').trim();
        if (!q) {
          ElMessage.warning('请输入搜索关键词');
          return;
        }
        ElMessage.info('搜索"' + q + '"功能开发中');
      },
      startPractice(subKey) {
        if (!subKey) return;
        var catMaps = { xc: XC_SUB_MAP, sl: SL_SUB_MAP, ga: GA_SUB_MAP };
        var catKey = this.state.activeCategory;
        var nameMap = catMaps[catKey] || {};
        var subName = nameMap[subKey] || subKey;
        // 导航到练习页面，传递科目和子科目参数
        this.$router.push('/exercise?subject=' + catKey + '&subcategory=' + encodeURIComponent(subName));
      },
      // ========== 快速练习 — 手风琴展开/收起 ==========
      toggleSubCategory(subKey) {
        if (this.state.expandedSubCategory === subKey) {
          this.state.expandedSubCategory = null;
        } else {
          this.state.expandedSubCategory = subKey;
        }
      },
      startKnowledgePractice(subKey, kp) {
        if (!kp || !kp.point_id) return;
        var catKey = this.state.activeCategory;
        this.$router.push('/exercise?subject=' + catKey + '&kpId=' + kp.point_id + '&kpName=' + encodeURIComponent(kp.point_name || ''));
      },
      startCustomPractice() {
        var cfg = this.state.customConfig;
        var subCatId = cfg.subCategory;
        if (!subCatId) {
          ElMessage.warning('请选择具体练习子科目');
          return;
        }
        var count = cfg.questionCount || 20;
        var yearRange = cfg.yearRange || '3';
        // 使用子科目ID获取题目
        this.$router.push('/exercise?subject=' + cfg.subject
          + '&scId=' + subCatId
          + '&count=' + count
          + '&yearRange=' + yearRange
          + '&timeLimit=' + (cfg.timeLimit || 0));
      },
      navigateTo(id) {
        if (id) {
          this.$router.push('/page/' + id);
        }
      },
      handleToolClick(key) {
        if (key === 'note') {
          this.$router.push('/page/notes');
        } else if (key === 'fav') {
          this.$router.push('/page/favorites');
        }
      },
    },
  })
</script>
<style lang="css" scoped>
.practice-detail { margin-top: 10px; border-top: 1px solid #e8ecf1; padding-top: 10px; }
.daily-cards { display: flex; flex-direction: column; gap: 6px; }
.daily-card { display: flex; justify-content: space-between; padding: 6px 10px; background: #f8f9fc; border-radius: 8px; font-size: 12px; }
.daily-date { color: #1a2b5f; font-weight: 600; }
.daily-stats { color: #8899aa; }
.practice-empty { text-align: center; padding: 16px; color: #8899aa; font-size: 13px; }

  .question-bank {
    min-height: 100vh;
    background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
    font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }
  .qb-main {
    max-width: 1400px;
    margin: 0 auto;
    padding: 24px 32px 40px;
  }
  /* 上层 */
  .qb-top {
    margin-bottom: 24px;
  }
  .qb-actions {
    position: relative;
    margin-bottom: 12px;
  }
  .action-scroll {
    display: flex;
    gap: 12px;
    overflow-x: auto;
    scrollbar-width: none;
    padding: 4px 0;
  }
  .action-scroll::-webkit-scrollbar {
    display: none;
  }
  
  .action-btn {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 14px 24px;
    border: none;
    border-radius: 14px;
    background: #ffffff;
    cursor: pointer;
    transition: all 0.3s;
    white-space: nowrap;
    box-shadow: 0 2px 10px rgba(26, 43, 95, 0.04);
  }
  .action-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(26, 43, 95, 0.1);
  }
  .action-btn.active {
    background: linear-gradient(135deg, #1a2b5f, #1e3470);
    box-shadow: 0 4px 18px rgba(26, 43, 95, 0.3);
  }
  .action-btn.active .action-name {
    color: #ffffff;
  }
  .action-icon {
    font-size: 20px;
  }
  .action-name {
    font-size: 15px;
    font-weight: 700;
    color: #1a2b5f;
  }
  .action-tag {
    font-size: 9px;
    padding: 1px 6px;
    border-radius: 6px;
    background: #c41e3a;
    color: #fff;
    font-weight: 700;
  }
  .qb-sub-actions {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .sub-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border: 1px solid #e8eaf0;
    border-radius: 10px;
    background: #ffffff;
    font-size: 13px;
    font-weight: 600;
    color: #1a2b5f;
    cursor: pointer;
    transition: all 0.3s;
  }
  .sub-btn:hover {
    border-color: #c41e3a;
  }
  .search-box {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-left: auto;
    padding: 8px 16px;
    background: #ffffff;
    border-radius: 10px;
    border: 1px solid #e8eaf0;
    width: 240px;
  }
  .search-box input {
    border: none;
    outline: none;
    font-size: 13px;
    flex: 1;
    color: #1a2b5f;
  }
  /* 主体 */
  .qb-body {
    display: grid;
    grid-template-columns: 1fr 300px;
    gap: 24px;
  }
  .category-tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 20px;
    background: #ffffff;
    border-radius: 12px;
    padding: 4px;
    box-shadow: 0 1px 8px rgba(26, 43, 95, 0.04);
  }
  .cat-tab {
    flex: 1;
    padding: 12px;
    border: none;
    background: transparent;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 700;
    color: #5a6488;
    cursor: pointer;
    transition: all 0.3s;
  }
  .cat-tab.active {
    background: #1a2b5f;
    color: #ffffff;
    box-shadow: 0 2px 10px rgba(26, 43, 95, 0.3);
  }
  .subcategory-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }
  .subcard {
    background: #ffffff;
    border-radius: 14px;
    padding: 18px 16px;
    cursor: pointer;
    transition: all 0.3s;
    display: flex;
    align-items: center;
    gap: 12px;
    box-shadow: 0 1px 8px rgba(26, 43, 95, 0.04);
  }
  .subcard:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 18px rgba(26, 43, 95, 0.1);
  }
  .subcard-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
  }
  .subcard-info {
    flex: 1;
  }
  .subcard-name {
    font-size: 14px;
    font-weight: 700;
    color: #1a2b5f;
    display: block;
    margin-bottom: 4px;
  }
  .subcard-count {
    font-size: 11px;
    color: #8a8faa;
  }
  /* 右侧 */
  .qb-right {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .right-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 18px;
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.04);
  }
  .right-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 700;
    color: #1a2b5f;
    margin-bottom: 14px;
  }
  .log-stats { display: flex; justify-content: space-around; }
  .log-item { text-align: center; cursor: default; }
  .log-item:nth-child(2) { cursor: pointer; color: #1a2b5f; }
  .log-item:nth-child(2):hover { color: #c41e3a; }
  .log-value { display: block; font-size: 22px; font-weight: 900; color: #1a2b5f; font-family: 'DIN Alternate', sans-serif; }
  /* 用时和正确率 */
  .log-sub-stats { display: flex; justify-content: space-around; margin-top: 10px; padding-top: 8px; border-top: 1px solid #f0f2f5; }
  .log-sub-item { text-align: center; }
  .log-sub-label { font-size: 15px; color: #8a8faa; display: block; }
  .log-sub-value { font-size: 15px; font-weight: 700; color: #1a2b5f; }
  .accuracy-good { color: #10b981 !important; }
  .accuracy-warn { color: #ef4444 !important; }
  /* 题目类型进度 */
  .type-progress-section { margin-top: 14px; padding-top: 12px; border-top: 1px solid #f0f2f5; }
  .type-progress-title { font-size: 15px; font-weight: 700; color: #1a2b5f; margin-bottom: 10px; }
  .type-badges { display: flex; flex-direction: column; gap: 6px; max-height: 200px; overflow-y: auto; }
  .type-badges::-webkit-scrollbar { width: 3px; }
  .type-badges::-webkit-scrollbar-thumb { background: #d9dce8; border-radius: 3px; }
  .type-badge { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-radius: 20px; cursor: pointer; font-size: 15px; transition: all 0.2s; }
  .type-badge:hover { transform: translateX(3px); }
  .badge-done { background: #ecfdf5; border: 1px solid #10b981; }
  .badge-done .badge-status { color: #10b981; font-weight: 700; }
  .badge-undone { background: #fef2f2; border: 1px solid #ef4444; }
  .badge-undone .badge-status { color: #ef4444; font-weight: 700; }
  .badge-name { color: #1a2b5f; font-weight: 600; }
  .badge-status { font-size: 15px; flex-shrink: 0; margin-left: 8px; }
  .type-progress-empty { text-align: center; padding: 12px; font-size: 15px; color: #8a8faa; }
  /* 图表区域 */
  .chart-section { margin-top: 14px; padding-top: 12px; border-top: 1px solid #f0f2f5; }
  .chart-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
  .chart-title { font-size: 15px; font-weight: 700; color: #1a2b5f; }
  .chart-toggle { display: flex; gap: 4px; }
  .chart-btn { padding: 3px 8px; border-radius: 6px; border: 1px solid #e8eaf0; background: #fff; font-size: 11px; cursor: pointer; color: #5a6488; transition: all 0.2s; }
  .chart-btn.active { background: #c41e3a; border-color: #c41e3a; color: #fff; }
  .chart-container { padding: 8px 0; }
  /* 柱状图 */
  .mini-bars { display: flex; align-items: flex-end; justify-content: space-around; height: 130px; padding: 0 4px; }
  .bar-col { display: flex; flex-direction: column; align-items: center; gap: 4px; flex: 1; }
  .bar-val { font-size: 15px; color: #5a6488; font-weight: 600; }
  .bar-fill { width: 22px; background: linear-gradient(180deg, #c41e3a, #e85d75); border-radius: 4px 4px 0 0; min-height: 4px; transition: height 0.3s; }
  .bar-day { font-size: 15px; color: #8a8faa; margin-top: 2px; }
  /* 折线图 */
  .mini-line-chart { padding: 0 4px; }
  .line-labels { display: flex; justify-content: space-around; margin-top: 2px; }
  .line-labels span { font-size: 15px; color: #8a8faa; }
  .tools-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }
  .tool-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    padding: 12px 4px;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.3s;
    font-size: 11px;
    color: #5a6488;
    background: #f8f9fc;
  }
  .tool-item:hover {
    background: #f0f2f5;
    transform: scale(1.03);
  }
  /* 数据加载状态 */
  .stats-loading {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 13px;
    color: #8899aa;
  }
  .mini-spinner {
    width: 18px;
    height: 18px;
    border: 2px solid rgba(200,22,30,0.15);
    border-top: 2px solid #c41e3a;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .stats-error {
    border: 1px solid rgba(232,56,79,0.2);
    background: rgba(232,56,79,0.04);
  }
  .error-msg {
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 12px;
    color: #e8384f;
    line-height: 1.5;
  }
  .retry-btn {
    align-self: flex-start;
    padding: 5px 14px;
    border: 1px solid rgba(232,56,79,0.3);
    border-radius: 6px;
    background: transparent;
    color: #e8384f;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
  }
  .retry-btn:hover {
    background: rgba(232,56,79,0.1);
  }
  .log-refresh {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid #f0f1f5;
    text-align: center;
  }
  .refresh-link {
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    border: none;
    border-radius: 6px;
    background: #f8f9fc;
    color: #8899aa;
    font-size: 15px;
    cursor: pointer;
    transition: all 0.3s;
  }
  .refresh-link:hover {
    background: #f0f2f5;
    color: #1a2b5f;
  }
  /* 骨架屏 */
  .subcard-skeleton { cursor: default; pointer-events: none; }
  .subcard-skeleton:hover { transform: none; box-shadow: 0 1px 8px rgba(26,43,95,0.04); }
  .skeleton-icon {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: linear-gradient(90deg, #e8ecf2 25%, #f0f2f5 50%, #e8ecf2 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s ease-in-out infinite;
  }
  .skeleton-text {
    height: 12px;
    border-radius: 4px;
    margin-bottom: 6px;
    background: linear-gradient(90deg, #e8ecf2 25%, #f0f2f5 50%, #e8ecf2 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s ease-in-out infinite;
  }
  @keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
  /* 快速练习 — 考点展开列表 */
  .subcard-wrapper { display: flex; flex-direction: column; }
  .count-badge { font-size: 12px; font-weight: 700; color: #1a2b5f; background: #f0f2f5; padding: 2px 8px; border-radius: 10px; }
  .kp-list { margin: -4px 8px 8px 8px; padding: 8px 0; background: #fafbfc; border-radius: 0 0 12px 12px; border: 1px solid #f0f2f5; border-top: none; }
  .kp-empty { text-align: center; padding: 12px; font-size: 12px; color: #8a8faa; }
  .kp-row { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; cursor: pointer; transition: all 0.2s; border-bottom: 1px solid #f0f2f5; }
  .kp-row:last-child { border-bottom: none; }
  .kp-row:hover { background: #f0f4ff; }
  .kp-name { font-size: 13px; color: #1a2b5f; font-weight: 500; flex: 1; }
  .kp-badge { font-size: 11px; color: #5a6488; background: #e8ecf2; padding: 2px 8px; border-radius: 8px; font-weight: 600; min-width: 48px; text-align: center; flex-shrink: 0; margin-left: 8px; }
  /* 自定义刷题卡片 */
  .custom-practice-card { background: #fff; border-radius: 16px; padding: 28px 32px; box-shadow: 0 2px 12px rgba(26,43,95,0.06); max-width: 620px; margin: 0 auto; }
  .custom-header { font-size: 18px; font-weight: 700; color: #1a2b5f; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 2px solid #f0f2f5; }
  .custom-body { display: flex; flex-direction: column; gap: 16px; }
  .custom-row { display: flex; align-items: center; gap: 12px; }
  .custom-row label { width: 120px; font-size: 14px; font-weight: 600; color: #5a6488; flex-shrink: 0; }
  .custom-row select, .custom-row input { flex: 1; padding: 8px 12px; border: 1px solid #e8eaf0; border-radius: 8px; font-size: 14px; color: #1a2b5f; background: #fafbfc; outline: none; transition: border-color 0.2s; }
  .custom-row select:focus, .custom-row input:focus { border-color: #1a2b5f; background: #fff; }
  .custom-start-btn { margin-top: 8px; padding: 12px 0; border: none; border-radius: 10px; background: linear-gradient(135deg, #1a2b5f, #1e3470); color: #fff; font-size: 15px; font-weight: 700; cursor: pointer; transition: all 0.3s; }
  .custom-start-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 16px rgba(26,43,95,0.3); }
  /* ===== 练习记录 v2：徽章进度条 / 查看全部 / 记录弹窗 ===== */
  .view-all-link { margin-left: auto; font-size: 12px; font-weight: 600; color: #1a63d8; cursor: pointer; }
  .view-all-link:hover { color: #c41e3a; }
  .type-badge { flex-wrap: wrap; row-gap: 4px; }
  .badge-bar { flex-basis: 100%; height: 4px; border-radius: 2px; background: rgba(0,0,0,0.08); overflow: hidden; }
  .badge-bar i { display: block; height: 100%; background: linear-gradient(90deg, #34d399, #10b981); border-radius: 2px; transition: width 0.3s; }
  .retry-link-error { color: #e8384f !important; background: rgba(232,56,79,0.06) !important; }
  /* 记录弹窗（自定义遮罩，遵循项目既有模式） */
  .rp-mask { position: fixed; inset: 0; background: rgba(15,23,42,.55); z-index: 1000; display: flex; align-items: center; justify-content: center; padding: 16px; }
  .rp-dialog { width: 720px; max-width: 100%; max-height: 86vh; background: #ffffff; border-radius: 14px; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 20px 50px rgba(0,0,0,.25); }
  .rp-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid #f1f2f6; }
  .rp-title { font-size: 16px; font-weight: 800; color: #1a2b5f; }
  .rp-close { border: none; background: transparent; font-size: 16px; color: #8a8faa; cursor: pointer; padding: 4px 8px; border-radius: 8px; }
  .rp-close:hover { background: #f0f2f5; color: #1a2b5f; }
  .rp-tabs { display: flex; gap: 8px; padding: 12px 18px 0; }
  .rp-tab { padding: 8px 14px; border-radius: 10px; border: none; background: #f5f6fa; color: #5a6488; font-size: 13px; font-weight: 700; cursor: pointer; transition: all 0.2s; }
  .rp-tab.active { background: #1a2b5f; color: #ffffff; }
  .rp-body { overflow-y: auto; padding: 14px 18px 18px; }
  .rp-panel { min-height: 120px; }
  .rp-tip { text-align: center; padding: 24px 8px; color: #8899aa; font-size: 13px; }
  .kp-group { margin-bottom: 14px; }
  .kp-group-title { font-size: 13px; font-weight: 800; color: #1a2b5f; margin-bottom: 8px; padding-left: 8px; border-left: 3px solid #c41e3a; }
  .kp-line { display: flex; align-items: center; gap: 8px; padding: 7px 8px; border-radius: 8px; cursor: pointer; transition: background 0.2s; }
  .kp-line:hover { background: #f0f4ff; }
  .kp-line-name { width: 130px; font-size: 13px; color: #1a2b5f; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex-shrink: 0; }
  .kp-track { flex: 1; height: 6px; background: #eceef3; border-radius: 3px; overflow: hidden; }
  .kp-track i { display: block; height: 100%; background: linear-gradient(90deg, #1a63d8, #34d399); border-radius: 3px; }
  .kp-nums { font-size: 12px; color: #5a6488; min-width: 44px; text-align: right; }
  .acc-badge { font-size: 11px; padding: 2px 8px; border-radius: 8px; min-width: 46px; text-align: center; flex-shrink: 0; }
  .acc-good { color: #10b981; background: #ecfdf5; }
  .acc-warn { color: #ef4444; background: #fef2f2; }
  .chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
  .chip { padding: 5px 12px; border-radius: 14px; border: 1px solid #e8eaf0; background: #ffffff; color: #5a6488; font-size: 12px; cursor: pointer; transition: all 0.2s; }
  .chip.active { background: #1a2b5f; border-color: #1a2b5f; color: #ffffff; }
  .rec-list { display: flex; flex-direction: column; gap: 8px; }
  .rec-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid #f0f2f5; border-radius: 10px; transition: all 0.2s; }
  .rec-item:hover { border-color: #d9defb; background: #fafbff; }
  .src-badge { font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 6px; color: #ffffff; flex-shrink: 0; }
  .src-past { background: #409EFF; }
  .src-mock { background: #E6A23C; }
  .src-smart { background: #9B59B6; }
  .src-qp { background: #67C23A; }
  .rec-main { flex: 1; min-width: 0; }
  .rec-name { font-size: 13px; font-weight: 600; color: #1a2b5f; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .rec-meta { display: flex; gap: 10px; font-size: 11px; color: #8a8faa; margin-top: 3px; flex-wrap: wrap; }
  .rec-jump { border: none; background: #f0f4ff; color: #1a63d8; width: 30px; height: 30px; border-radius: 8px; cursor: pointer; flex-shrink: 0; font-size: 12px; transition: all 0.2s; }
  .rec-jump:hover { background: #1a2b5f; color: #ffffff; }
  .load-more-wrap { text-align: center; padding-top: 4px; }
  .load-more-btn { padding: 8px 22px; border: 1px solid #e8eaf0; border-radius: 10px; background: #ffffff; color: #5a6488; font-size: 13px; cursor: pointer; }
  .load-more-btn:hover { border-color: #1a2b5f; color: #1a2b5f; }
  @media (max-width: 768px) {
    .rp-mask { padding: 0; }
    .rp-dialog { width: 100%; height: 100%; max-height: none; border-radius: 0; }
    .kp-line-name { width: 96px; }
  }
</style>
