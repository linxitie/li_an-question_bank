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
            <div
              v-for="(sub, index) in currentSubCategories"
              :key="sub.key"
              class="subcard"
              @click="startPractice(sub.key)" v-if="state.statsLoaded">
              <div
                class="subcard-icon div_26rejvefdo6"
                :style="{ background: sub.bg }">
                {{ sub.emoji }}
              </div>
              <div class="subcard-info">
                <span class="subcard-name"> {{ sub.name }}</span>
                <span class="subcard-count">
                  <span>
                    <span> {{ sub.count }}</span>
                    <span> 题</span></span
                  ></span
                >
              </div>
              <XIcon :icon="ArrowRightBold" :size="14" color="#d1d5db"></XIcon>
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
            </div>
            <!-- 今日/本周/累计 -->
            <div class="log-stats">
              <div class="log-item">
                <span class="log-value">{{ state.practiceStats.today.count }}</span>
                <span class="log-label">今日(题)</span>
              </div>
              <div class="log-item" @click="toggleChart">
                <span class="log-value">{{ state.practiceStats.week.count }}</span>
                <span class="log-label">本周(题) ▾</span>
              </div>
              <div class="log-item">
                <span class="log-value">{{ state.practiceStats.total.count }}</span>
                <span class="log-label">累计(题)</span>
              </div>
            </div>
            <!-- 用时和正确率 -->
            <div class="log-sub-stats">
              <div class="log-sub-item">
                <span class="log-sub-label">做题用时</span>
                <span class="log-sub-value">{{ state.practiceStats.today.time_spent_minutes }}分钟</span>
              </div>
              <div class="log-sub-item">
                <span class="log-sub-label">正确率</span>
                <span class="log-sub-value" :class="state.practiceStats.total.accuracy >= 70 ? 'accuracy-good' : 'accuracy-warn'">{{ state.practiceStats.total.accuracy }}%</span>
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
            <div class="log-refresh">
              <button class="refresh-link" @click="refreshPracticeStats">刷新数据</button>
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
        </aside>
      </div>
    </main>

    <!-- 笔记列表弹窗 -->
    <div v-if="state.showNotesModal" class="note-modal-overlay" @click.self="closeNotesModal">
      <div class="note-modal">
        <div class="note-modal-header">
          <h3>我的笔记</h3>
          <button class="note-modal-close" @click="closeNotesModal">×</button>
        </div>
        <div class="note-modal-body">
          <div v-if="state.notesLoading" class="note-loading">加载中...</div>
          <div v-else-if="state.userNotes.length === 0" class="note-empty">
            <span class="note-empty-icon">📝</span>
            <p>还没有笔记哦！做题时可以添加笔记。</p>
          </div>
          <div v-else class="note-list">
            <div v-for="note in state.userNotes" :key="note.question_id" class="note-item">
              <div class="note-item-title">{{ note.title }}</div>
              <div class="note-item-text">{{ note.note_text }}</div>
              <button class="note-delete-btn" @click="deleteNoteItem(note.question_id)">删除</button>
            </div>
          </div>
        </div>
      </div>
    </div>
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

  // 子科目 Emoji 和背景色映射（静态视觉配置）
  const SUBCARD_STYLES = {
    '政治理论': { emoji: '📖', bg: '#eff6ff' },
    '资料分析': { emoji: '📊', bg: '#fef2f2' },
    '数量关系': { emoji: '🔢', bg: '#fffbeb' },
    '常识': { emoji: '💡', bg: '#f0fdf4' },
    '速度与知觉训练': { emoji: '⏱️', bg: '#ede9fe' },
    '判断推理': { emoji: '🔍', bg: '#fdf2f8' },
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
      const provider = useProvider({ id: 'question_bank', version: '1778918346107' });
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
        // 笔记相关
        showNotesModal: false,
        userNotes: [],
        notesLoading: false,
      });
      return {
        state,
        props,
        provider,
        Timer, Monitor, Search, ArrowRightBold, DataLine,
        DocumentDelete, Edit, StarFilled, DataAnalysis, ShoppingCartFull
      };
    },
    mounted() {
      this.loadStats();
      // 检查是否有来自导入页面的刷新通知
      this.checkImportRefreshFlag();
      // 检查是否有来自练习结果页的刷新标记
      this.checkPracticeRefreshFlag();
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
        // 自定义刷题保持静态
        if (cat === 'custom') {
          return [{
            key: 'custom-all', name: '自定义选题', count: 0, emoji: '⚙️', bg: '#f8f9fc'
          }];
        }

        // 获取该分类下所有子科目定义
        const subDefs = this.getSubDefinitions(cat);
        // 用 API 返回的真实数据填充 count
        const statsMap = cat === 'xc' ? this.state.xingceStats
          : cat === 'sl' ? this.state.shenlunStats
          : this.state.gongzhuanStats;

        return subDefs.map(function(def) {
          const realCount = statsMap[def.name] !== undefined ? statsMap[def.name] : 0;
          return {
            key: def.key,
            name: def.name,
            count: realCount,
            emoji: (SUBCARD_STYLES[def.name] || {}).emoji || '📝',
            bg: (SUBCARD_STYLES[def.name] || {}).bg || '#f8f9fc',
          };
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
      refreshPracticeStats() {
        this.loadPracticeRecords();
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
        } else if (key === 'quick') {
          // 快速练习：进入当前选中科目的综合练习
          var catKey = this.state.activeCategory;
          if (catKey === 'custom') catKey = 'xc';
          var catNames = { xc: '行测', sl: '申论', ga: '公专' };
          var catName = catNames[catKey] || '行测';
          this.$router.push('/exercise?subject=' + catKey + '&subcategory=' + encodeURIComponent(catName + '综合'));
        } else if (key === 'history') {
          ElMessage.info('历年试卷功能开发中');
        } else if (key === 'smart') {
          ElMessage.info('智能组卷功能开发中');
        } else if (key === 'ai') {
          ElMessage.info('联考小智功能开发中');
        }
      },
      switchCategory(key) {
        this.state.activeCategory = key;
      },
      handleSubAction(key) {
        if (key === 'mini') {
          ElMessage.info('小模考功能开发中');
        } else if (key === 'college') {
          ElMessage.info('院校联考机考系统开发中');
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
      navigateTo(id) {
        if (id) {
          this.$router.push('/page/' + id);
        }
      },
      handleToolClick(key) {
        if (key === 'note') {
          this.openNotesModal();
        } else if (key === 'fav') {
          ElMessage.info('收藏功能开发中');
        }
      },
      // ========== 笔记功能 ==========
      openNotesModal() {
        this.state.showNotesModal = true;
        this.fetchUserNotes();
      },
      closeNotesModal() {
        this.state.showNotesModal = false;
      },
      async fetchUserNotes() {
        this.state.notesLoading = true;
        this.state.userNotes = [];
        try {
          // 获取所有题目操作状态来发现有笔记的题目
          var headers = this.getJsonHeaders();
          // 使用现有的题目列表数据配合笔记查询
          var self = this;
          var allQuestionIds = [];
          // 从各个统计中收集所有子科目名称
          var subNames = Object.keys(self.getSubDefinitions('xc'))
            .concat(Object.keys(self.getSubDefinitions('sl')))
            .concat(Object.keys(self.getSubDefinitions('ga')));
          // 尝试从 API 获取有笔记的题目
          try {
            var res = await window.__VTJ_AUTH__.apiFetch('/api/questions/?page_size=5&has_notes=true', {
              headers: headers
            });
            if (res.ok) {
              var data = await res.json();
              var items = data.items || data.data || [];
              for (var i = 0; i < items.length; i++) {
                var q = items[i];
                if (q.question_id) {
                  try {
                    var noteRes = await window.__VTJ_AUTH__.apiFetch('/api/questions/' + q.question_id + '/note', {
                      headers: self.getJsonHeaders()
                    });
                    var noteData = await noteRes.json();
                    if (noteData.has_note && noteData.note_text) {
                      self.state.userNotes.push({
                        question_id: q.question_id,
                        title: (q.question_content || q.title || '').substring(0, 120),
                        note_text: noteData.note_text,
                        update_time: noteData.update_time
                      });
                    }
                  } catch(e) {}
                }
              }
            }
          } catch(e2) {
            // 备用：直接尝试练习记录中关联的题目
          }
        } catch(e) {
          console.warn('加载笔记失败:', e);
        } finally {
          this.state.notesLoading = false;
        }
      },
      async deleteNoteItem(questionId) {
        try {
          var res = await window.__VTJ_AUTH__.apiFetch('/api/questions/' + questionId + '/note', {
            method: 'DELETE',
            headers: this.getJsonHeaders()
          });
          if (res.ok) {
            this.state.userNotes = this.state.userNotes.filter(function(n) {
              return n.question_id !== questionId;
            });
          }
        } catch(e) {
          console.warn('删除笔记失败:', e);
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
  /* 笔记弹窗 */
  .note-modal-overlay {
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.45); display: flex; align-items: center;
    justify-content: center; z-index: 1000;
  }
  .note-modal {
    background: #fff; border-radius: 16px; padding: 24px;
    width: 480px; max-width: 90vw; max-height: 70vh;
    overflow-y: auto; box-shadow: 0 8px 32px rgba(26,43,95,0.15);
  }
  .note-modal-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
  .note-modal-header h3 { margin: 0; font-size: 16px; font-weight: 700; color: #1a2b5f; }
  .note-modal-close { width: 28px; height: 28px; border: none; background: transparent; font-size: 20px; color: #8a8faa; cursor: pointer; border-radius: 8px; }
  .note-modal-close:hover { background: #f0f2f5; color: #1a2b5f; }
  .note-loading { text-align: center; padding: 24px; color: #8a8faa; }
  .note-empty { text-align: center; padding: 28px; }
  .note-empty-icon { font-size: 36px; display: block; margin-bottom: 8px; }
  .note-empty p { color: #8a8faa; font-size: 14px; margin: 0; }
  .note-list { display: flex; flex-direction: column; gap: 10px; }
  .note-item { background: #fafbfc; border-radius: 10px; padding: 12px; border: 1px solid #f0f2f5; }
  .note-item-title { font-size: 12px; font-weight: 600; color: #1a2b5f; margin-bottom: 6px; }
  .note-item-text { font-size: 12px; color: #5a6488; line-height: 1.5; margin-bottom: 8px; }
  .note-delete-btn { padding: 2px 10px; border: 1px solid #fee2e2; border-radius: 12px; background: #fff; color: #dc2626; font-size: 11px; cursor: pointer; }
  .note-delete-btn:hover { background: #fef2f2; }
</style>
