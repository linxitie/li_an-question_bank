<!-- 手机端首页 - VTJ规范版 -->
<template>
  <div class="mobile-home-page">
    <!-- 顶部导航 -->
    <header class="top-nav">
      <div class="nav-left">
        <XIcon :icon="ArrowLeft" :size="22" color="#1A365D" class="nav-back" @click="goBack"></XIcon>
      </div>
      <h1 class="nav-title">砺安题库</h1>
      <div class="nav-right">
        <XIcon :icon="Bell" :size="22" color="#1A365D" class="nav-icon" @click="goToNotifications"></XIcon>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 用户信息卡片 -->
      <section class="user-card">
        <div class="user-greeting">
          <span class="greeting-text">
            <XIcon :icon="greetingIcon" :size="18" color="#ffffff"></XIcon>
            {{ greeting.salutation }}，{{ userName }}！
          </span>
          <span class="greeting-motto">{{ greeting.motto }}</span>
          <span class="streak-badge">
            <XIcon :icon="Lightning" :size="14" color="#ffffff"></XIcon>
            连续学习 {{ streakDays }} 天
          </span>
        </div>
        <div class="daily-goal" @click="openGoalEdit">
          <div class="goal-info">
            <span class="goal-label">今日目标：{{ dailyGoal }}题 · {{ subjectLabel }}</span>
            <span class="goal-progress">{{ dailyGoalPercent }}% ({{ dailyCompleted }}/{{ dailyGoal }})</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: dailyGoalPercent + '%' }"></div>
          </div>
          <span class="goal-edit-hint">点击可修改目标</span>
        </div>
      </section>

      <!-- 学习趋势：取代原「今日做题/本周做题/正确率/学习时长」四张卡片 -->
      <section class="trend-section">
        <div class="section-header">
          <h2 class="section-title">
            <XIcon :icon="DataAnalysis" :size="20" color="#1A365D"></XIcon>
            本周学习趋势
          </h2>
          <div class="chart-switch">
            <button
              class="switch-btn"
              :class="{ active: chartType === 'bar' }"
              @click="switchChart('bar')"
            >柱状</button>
            <button
              class="switch-btn"
              :class="{ active: chartType === 'line' }"
              @click="switchChart('line')"
            >折线</button>
          </div>
        </div>
        <div class="trend-chart">
          <div v-if="!trendHasData" class="chart-empty">本周还没有做题记录</div>
          <div v-else ref="trendChartRef" class="chart-canvas"></div>
        </div>
      </section>

      <!-- 每日金句 -->
      <section class="quote-section">
        <div class="quote-card">
          <XIcon :icon="ChatDotRound" :size="24" color="#f59e0b" class="quote-icon"></XIcon>
          <p class="quote-text">{{ dailyQuote }}</p>
          <p class="quote-author">—— {{ quoteAttribution }}</p>
          <button class="quote-refresh" :disabled="quoteLoading" @click="refreshQuote">
            {{ quoteLoading ? '加载中…' : '换一句' }}
          </button>
        </div>
      </section>

      <!-- 每日新闻 -->
      <section class="news-section">
        <div class="section-header">
          <h2 class="section-title">
            <XIcon :icon="Document" :size="20" color="#1A365D"></XIcon>
            每日新闻
          </h2>
          <span class="section-action" @click="viewAllNews">
            查看全部
            <XIcon :icon="ArrowRight" :size="14" color="#1890ff"></XIcon>
          </span>
        </div>
        <div class="news-list">
          <div class="news-item" v-for="(news, index) in newsList" :key="index" @click="viewNews(news)">
            <XIcon :icon="Right" :size="12" color="#1A365D"></XIcon>
            <span class="news-title">{{ news.title }}</span>
          </div>
        </div>
      </section>
    </main>

    <!-- 底部Tab栏：统一使用单一真源组件 src/components/MobileTabBar.vue -->
    <MobileTabBar active="home" />

    <!-- 今日目标编辑弹层 -->
    <div v-if="showGoalEdit" class="goal-mask" @click="showGoalEdit = false">
      <div class="goal-modal" @click.stop>
        <div class="goal-modal-header">
          <span class="goal-modal-title">设置今日目标</span>
          <button class="goal-modal-close" @click="showGoalEdit = false" aria-label="关闭">✕</button>
        </div>
        <div class="goal-modal-body">
          <label class="goal-field">
            <span class="goal-field-label">今日完成题目数量（题）</span>
            <input
              v-model.number="goalInput"
              class="goal-field-input"
              type="number"
              min="1"
              max="999"
              inputmode="numeric"
              placeholder="请输入今日目标题数"
            />
          </label>
          <label class="goal-field">
            <span class="goal-field-label">今日学习科目</span>
            <select v-model.number="subjectModeInput" class="goal-field-input">
              <option :value="0">混科（不限科目）</option>
              <option v-for="s in subjectOptions" :key="s.subject_id" :value="s.subject_id">
                {{ s.subject_name }}
              </option>
            </select>
          </label>
          <label class="goal-field">
            <span class="goal-field-label">本周学习目标（题）</span>
            <input
              v-model.number="weekGoalInput"
              class="goal-field-input"
              type="number"
              min="50"
              max="3000"
              inputmode="numeric"
              placeholder="请输入本周目标题数"
            />
          </label>
          <label class="goal-field">
            <span class="goal-field-label">单日预期学习时间（分钟）</span>
            <input
              v-model.number="expectedMinutesInput"
              class="goal-field-input"
              type="number"
              min="0"
              max="1440"
              inputmode="numeric"
              placeholder="如 60"
            />
          </label>
        </div>
        <div class="goal-modal-actions">
          <button class="goal-action-btn" :disabled="savingGoal" @click="saveGoal">
            {{ savingGoal ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { XIcon } from '@vtj/ui';
import { ElMessage } from 'element-plus';
import MobileTabBar from '@/components/MobileTabBar.vue';
import {
  ArrowLeft,
  ArrowRight,
  ArrowDown,
  Bell,
  Sunny,
  Lightning,
  EditPen,
  DataLine,
  TrendCharts,
  Timer,
  DataAnalysis,
  ChatDotRound,
  Document,
  Right,
  HomeFilled,
  Reading,
  Edit,
  ChatLineRound,
  User,
  Moon
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';
import * as echarts from 'echarts';

export default defineComponent({
  name: 'MobileHome',
    components: {
      XIcon,
      MobileTabBar
    },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'mobile_home', version: '1788919369989' });

    // 用户数据
    const userName = ref('同学');
    const streakDays = ref(15);
const dailyGoal = ref(40);
const dailyCompleted = ref(30);
// ===== 今日目标弹窗 4 字段（按用户指定口径）=====
// 1) 今日完成题目数量 -> DAILY 目标 target_count
// 2) 今日学习科目     -> DAILY 目标 subject_mode（0=混科，>0=单科 subject_id）
// 3) 本周学习目标     -> WEEKLY 目标 target_count
// 4) 单日预期学习时间 -> DAILY 目标 expected_minutes（分钟）
// 不再使用「明日计划科目 / 计划题量」（用户明确要求去掉）
const goalInput = ref(40);
const subjectModeInput = ref(0);
const weekGoalInput = ref(500);
const expectedMinutesInput = ref(60);
const weekGoalId = ref<number | null>(null);
// 科目下拉选项（由 /api/quick-practice/subjects 填充）
const subjectOptions = ref<any[]>([]);
// 顶部卡片展示的科目文案
const subjectLabel = computed(() => {
  if (!subjectModeInput.value) return '混科';
  const hit = subjectOptions.value.find((s: any) => s.subject_id === subjectModeInput.value);
  return hit ? hit.subject_name : '混科';
});

const dailyGoalPercent = computed(() =>
  dailyGoal.value > 0 ? Math.round((dailyCompleted.value / dailyGoal.value) * 100) : 0
);

// ===== 动态问候语：按时段变化，激励语按日轮换 =====
// 不使用具体人名/机构名，避免「随意套用姓名与报刊名」的问题
const GREETING_PRESETS = [
  { salutation: '凌晨好', motto: '夜深了，注意休息' },
  { salutation: '早上好', motto: '新的一天，新的进步' },
  { salutation: '上午好', motto: '趁热打铁，先做几道题' },
  { salutation: '中午好', motto: '午休一下，效率更高' },
  { salutation: '下午好', motto: '保持节奏，继续前进' },
  { salutation: '晚上好', motto: '今天的努力不会白费' },
  { salutation: '夜深了', motto: '别熬太晚，早点休息' },
];
const greeting = computed(() => {
  const h = new Date().getHours();
  // 5-8 早上 / 9-11 上午 / 12-13 中午 / 14-17 下午 / 18-22 晚上 / 23-4 凌晨
  let idx = h < 5 ? 6 : h < 9 ? 1 : h < 12 ? 2 : h < 14 ? 3 : h < 18 ? 4 : h < 23 ? 5 : 6;
  const base = GREETING_PRESETS[idx];
  // 同一天内 motto 固定，跨天轮换，避免频繁变动让人眼花
  const dayOfYear = Math.floor((Date.now() - new Date(new Date().getFullYear(), 0, 0)) / 86400000);
  const mottoPool = GREETING_PRESETS.map((g) => g.motto);
  return {
    salutation: base.salutation,
    motto: mottoPool[dayOfYear % mottoPool.length],
  };
});
const greetingIcon = computed(() => {
  const h = new Date().getHours();
  return h >= 6 && h < 18 ? Sunny : Moon;
});

// ===== 今日目标：可编辑 =====
const dailyGoalId = ref<number | null>(null);
const showGoalEdit = ref(false);
const savingGoal = ref(false);

const openGoalEdit = () => {
  goalInput.value = dailyGoal.value;
  // 本周目标默认按电脑端同一推导规则给出：今日目标 × 7
  weekGoalInput.value = Math.max(dailyGoal.value * 7, 500);
  showGoalEdit.value = true;
};

const saveGoal = async () => {
  const target = Number(goalInput.value);
  if (!target || target < 1) {
 ElMessage.warning('请输入大于 0 的目标题数');
    return;
  }
const weekTarget = Number(weekGoalInput.value);
  if (!weekTarget || weekTarget < 1) {
  ElMessage.warning('请输入大于 0 的本周目标题数');
    return;
  }
  const subjectMode = Number(subjectModeInput.value) || 0;
  const expectedMinutes = Number(expectedMinutesInput.value) || 0;
  if (expectedMinutes < 0 || expectedMinutes > 1440) {
    ElMessage.warning('单日预期学习时间需在 0–1440 分钟之间');
    return;
  }
  savingGoal.value = true;
  try {
    const auth = window.__VTJ_AUTH__;
    const headers = { 'Content-Type': 'application/json' };
    // DAILY 目标：题数 + 科目 + 预期时长
    const dailyPayload = {
      title: '今日目标',
      target_count: target,
      subject_mode: subjectMode,
      expected_minutes: expectedMinutes,
    };
    if (dailyGoalId.value != null) {
      const res = await auth.apiFetch('/api/goals/' + dailyGoalId.value, {
        method: 'PUT',
        headers,
        body: JSON.stringify(dailyPayload),
      });
      if (res.ok) {
        const d = (await res.json().catch(() => ({}))).data || {};
      dailyGoal.value = target;
        subjectModeInput.value = subjectMode;
        expectedMinutesInput.value = expectedMinutes;
    ElMessage.success('今日目标已更新');
        showGoalEdit.value = false;
      } else {
        const err = await res.json().catch(() => ({}));
   ElMessage.error(err.detail || '更新失败');
      }
    } else {
      const res = await auth.apiFetch('/api/goals/', {
    method: 'POST',
        headers,
        body: JSON.stringify({ ...dailyPayload, goal_type: 'DAILY' }),
      });
      if (res.ok) {
        const data = await res.json();
        const d = data.data || data;
        dailyGoalId.value = d.goal_id != null ? d.goal_id : null;
   dailyGoal.value = target;
     dailyCompleted.value = d.current_count || 0;
    ElMessage.success('今日目标已创建');
        showGoalEdit.value = false;
      } else {
     const err = await res.json().catch(() => ({}));
        ElMessage.error(err.detail || '创建失败');
      }
    }
    await saveWeekGoal(auth, headers, weekTarget);
  } catch (e) {
ElMessage.error('保存失败，请稍后重试');
  } finally {
    savingGoal.value = false;
  }
};

  /**
   * 保存本周学习目标。
   * 改用 goal_type='WEEKLY' 独立记录，不再把计划折叠进标题文本，
   * 因为用户要求的字段是「本周学习目标」，语义上就是周目标。
   * 失败仅提示，不影响已保存的今日目标。
   */
  const saveWeekGoal = async (auth: any, headers: any, weekTarget: number) => {
    try {
  if (weekGoalId.value != null) {
        await auth.apiFetch('/api/goals/' + weekGoalId.value, {
          method: 'PUT',
          headers,
      body: JSON.stringify({ title: '本周目标', target_count: weekTarget, goal_type: 'WEEKLY' }),
        });
      } else {
        const res = await auth.apiFetch('/api/goals/', {
          method: 'POST',
          headers,
          body: JSON.stringify({ title: '本周目标', target_count: weekTarget, goal_type: 'WEEKLY' }),
   });
        if (res.ok) {
     const d = (await res.json().catch(() => ({}))).data || {};
          weekGoalId.value = d.goal_id != null ? d.goal_id : null;
        }
      }
    } catch (e) {
      ElMessage.warning('本周目标保存失败，今日目标已生效');
    }
  };

// 载入用户当前目标（存在则可编辑）
const loadDailyGoal = async () => {
  try {
    const auth = window.__VTJ_AUTH__;
    const res = await auth.apiFetch('/api/goals/');
    if (!res.ok) return;
    const data = await res.json();
    const items = data.items || data.data || [];
    // 关键修复：不再用 is_completed 过滤。
    // 原写法在目标完成后会查不到记录，导致刷新后回退默认值（用户反馈的保存丢失）。
    const daily = items
      .filter((g: any) => g.goal_type === 'DAILY')
      .sort((a: any, b: any) => (b.create_time || 0) - (a.create_time || 0))[0];
    if (daily) {
      dailyGoalId.value = daily.goal_id;
      if (daily.target_count) dailyGoal.value = daily.target_count;
      if (daily.current_count != null) dailyCompleted.value = daily.current_count;
      if (daily.subject_mode != null) subjectModeInput.value = daily.subject_mode;
    if (daily.expected_minutes != null) expectedMinutesInput.value = daily.expected_minutes;
    }
    // 本周目标：goal_type='WEEKLY'
    const weekly = items
      .filter((g: any) => g.goal_type === 'WEEKLY')
      .sort((a: any, b: any) => (b.create_time || 0) - (a.create_time || 0))[0];
    if (weekly) {
      weekGoalId.value = weekly.goal_id;
      if (weekly.target_count) weekGoalInput.value = weekly.target_count;
    }
  } catch (e) { /* 目标载入失败不影响主流程 */ }
};

    // 统计数据
    const todayCount = ref(18);
    const weekCount = ref(120);
    const accuracy = ref(70.2);
    const studyHours = ref(1.8);

    // 周数据：count 做题数 / accuracy 正确率 / seconds 用时（供悬浮提示）
    const weekData = ref<any[]>([]);

    // 最大值用于计算柱状图高度
    const maxCount = computed(() => Math.max(...weekData.value.map(d => d.count)));

    // ===== 学习趋势图（echarts 单实例，柱/线切换）=====
    // 复用 src/views/mobile_history.vue 已验证的 echarts 用法（import * as echarts）
    // 采用单实例 + series.type 切换，比双实例更省内存且切换即时
    const trendChartRef = ref<HTMLElement | null>(null);
    const chartType = ref<'bar' | 'line'>('bar');
    let trendInstance: any = null;
    const trendHasData = computed(() => weekData.value.some((d: any) => (d.count || 0) > 0));

    function renderTrendChart() {
      if (!trendHasData.value) return;
      const el = trendChartRef.value;
      if (!el) return;
      if (!trendInstance) trendInstance = echarts.init(el);
      const isBar = chartType.value === 'bar';
      const series: any = isBar
        ? {
            type: 'bar',
            data: weekData.value.map((d: any) => d.count || 0),
            barMaxWidth: 22,
            itemStyle: { color: '#2a5298', borderRadius: [4, 4, 0, 0] },
          }
        : {
            type: 'line',
            data: weekData.value.map((d: any) => d.count || 0),
            smooth: true,
            lineStyle: { color: '#1A365D', width: 2 },
            itemStyle: { color: '#1A365D' },
            areaStyle: { color: 'rgba(26, 54, 93, 0.08)' },
          };
      trendInstance.setOption(
        {
          grid: { left: 34, right: 12, top: 24, bottom: 24 },
          tooltip: {
            trigger: 'axis',
            formatter: (params: any) => {
              const p = Array.isArray(params) ? params[0] : params;
              const i = p.dataIndex;
              const d = weekData.value[i] || ({} as any);
              const mins = Math.round((d.seconds || 0) / 60);
              return [
                `${d.date || ''}（周${d.label || ''}）`,
                `做题数：${d.count || 0} 题`,
                `正确率：${d.accuracy != null ? d.accuracy + '%' : '--'}`,
                `做题时间：${mins > 0 ? mins + ' 分钟' : '暂无记录'}`,
              ].join('<br/>');
            },
          },
          xAxis: {
            type: 'category',
            data: weekData.value.map((d: any) => d.label || ''),
            axisLabel: { fontSize: 10, color: '#5a6488' },
          },
          yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 10, color: '#5a6488' } },
          series: [series],
        },
        true
      );
    }

    function switchChart(type: 'bar' | 'line') {
      chartType.value = type;
      nextTick(() => renderTrendChart());
    }

    // ===== 每日金句 =====
    const dailyQuote = ref('');
    const quoteSource = ref('');
    const quoteAuthor = ref('');
    const quoteLoading = ref(false);

    // 占位值识别：Obsidian 知识库中 1341 条金句里，
    // 657 条 author 是游离引号 '"'（解析残留），279 条 source 是「权威官方文件」，
    // 两者都不是真实出处。用户明确要求「不准随意套用姓名和报刊名，严格对应」，
    // 故展示前必须过滤这些占位值，避免把无出处说成有出处。
    const PLACEHOLDER_VALUES = [
      '权威官方文件', '官方文件', '权威文件', '来源不明', '未知', '无', '暂无', '-', '—',
    ];
    const isValidAttribution = (v) => {
      const s = String(v || '').trim();
      if (!s) return false;
      if (s === '"' || s === '""' || s === '\'\'') return false;      // 解析残留的游离引号
      if (PLACEHOLDER_VALUES.includes(s)) return false;               // 占位文案
      return true;
    };

    // 出处如实展示：优先「作者 · 出处」；缺失则只显示存在的一项；
    // 两者都无效时显示「暂无出处」，绝不用占位文案冒充真实出处。
    const quoteAttribution = computed(() => {
      const a = isValidAttribution(quoteAuthor.value) ? quoteAuthor.value.trim() : '';
      const s = isValidAttribution(quoteSource.value) ? quoteSource.value.trim() : '';
      if (a && s) return `${a} · ${s}`;
      return a || s || '暂无出处';
    });

    /** 「换一句」：带当前内容作为 exclude，保证一定换掉 */
    const refreshQuote = async () => {
      if (quoteLoading.value) return;
      quoteLoading.value = true;
      try {
        const qs = dailyQuote.value ? '?exclude=' + encodeURIComponent(dailyQuote.value) : '';
        const res = await fetch('/api/quotes/random' + qs);
        if (res.ok) {
          const q = await res.json();
          if (q.content) {
            dailyQuote.value = q.content;
            quoteSource.value = q.source || '';
            quoteAuthor.value = q.author || '';
          }
        } else {
          ElMessage.warning('换一句失败，请稍后重试');
        }
      } catch (e) {
        ElMessage.warning('网络异常，换一句失败');
      } finally {
        quoteLoading.value = false;
      }
    };

    // 新闻列表
    const newsList = ref([
      { title: '公安联考报名时间确定，12月开始报名', id: 1 },
      { title: '行测新增政治理论模块，占比提升至15%', id: 2 },
      { title: '申论命题方向调整，重点考察实务能力', id: 3 }
    ]);

    // 统一数据加载（供 onMounted / 切回前台刷新 / 未来 WebSocket 推送复用）
    const loadData = async () => {
      try {
        const auth = window.__VTJ_AUTH__;
        if (auth && auth.isLoggedIn()) {
          const uname = auth.getUsername();
          if (uname) userName.value = uname;
          // 学习统计（/api/stats/ 返回今日/本周刷题量、正确率、学习时长、连续签到等）
          const res = await fetch('/api/stats/', { headers: auth.getAuthHeaders() });
          if (res.ok) {
            const data = await res.json();
            todayCount.value = data.todayQuestions || 0;
            weekCount.value = data.weeklyQuestions || 0;
            accuracy.value = data.accuracyRate || 0;
            studyHours.value = data.totalStudyHours || 0;
            streakDays.value = data.streak || 0;
          }
          // 练习趋势（周图表数据）
          const tRes = await fetch('/api/stats/practice-trend?days=7', { headers: auth.getAuthHeaders() });
          if (tRes.ok) {
            const tData = await tRes.json();
            if (tData.trend && tData.trend.length) {
              const dayLabels = ['日', '一', '二', '三', '四', '五', '六'];
              weekData.value = tData.trend.map((d: any) => ({
                date: d.date,
                label: dayLabels[new Date(d.date).getDay()] || '',
                count: d.questionsDone || 0,
                // 后端已返回正确率，此前前端丢弃未用；现用于悬浮提示
                accuracy: d.accuracy != null ? d.accuracy : null,
                // timeSpent 为 W1 新增字段（秒）
                seconds: d.timeSpent || 0,
              }));
            }
          }
          // 图表数据就绪后渲染（DOM 可能尚未挂载，交由 nextTick 处理）
          nextTick(() => renderTrendChart());
          // 学习目标（今日目标）
          try {
            const gRes = await fetch('/api/goals/stats/summary', { headers: auth.getAuthHeaders() });
            if (gRes.ok) {
              const gData = await gRes.json();
              dailyGoal.value = gData.total_goals || dailyGoal.value;
              dailyCompleted.value = gData.completed_goals || 0;
            }
          } catch (e) { /* 目标接口失败不影响主流程 */ }
          // 科目下拉选项
          try {
            const sRes = await fetch('/api/quick-practice/subjects', { headers: auth.getAuthHeaders() });
            if (sRes.ok) {
              const sData = await sRes.json();
              subjectOptions.value = sData.items || [];
            }
          } catch (e) { /* 科目列表失败不影响主流程 */ }
        }
        // 每日金句（公开接口）
        const qRes = await fetch('/api/quotes/quote/daily');
        if (qRes.ok) {
          const q = await qRes.json();
          if (q.content) {
            dailyQuote.value = q.content;
            quoteSource.value = q.source || '';
            quoteAuthor.value = q.author || '';
          }
        }
        // 每日新闻（公开接口）
        const nRes = await fetch('/api/news?limit=5');
        if (nRes.ok) {
          const n = await nRes.json();
          if (n.items && n.items.length) {
            newsList.value = n.items.map((it: any) => ({ title: it.title, id: it.id }));
          }
        }
      } catch (error) {
        console.error('加载数据失败:', error);
      }
    };

    // 统一在同一函数内注册/移除，避免匿名函数无法解绑导致重复监听
    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') loadData();
    };
    const onChartResize = () => trendInstance?.resize();

    onMounted(async () => {
      await loadData();
      // 载入用户当前目标（用于「今日目标」可编辑，有则编辑、无则创建）
      await loadDailyGoal();
      // 趋势图需在 DOM 挂载后初始化
      await nextTick();
      renderTrendChart();
      window.addEventListener('resize', onChartResize);
      document.addEventListener('visibilitychange', onVisibilityChange);
      // 后端 WebSocket 广播 sync 事件时刷新（实时同步）
      window.addEventListener('__VTJ_SYNC__', loadData);
    });

    onBeforeUnmount(() => {
      window.removeEventListener('resize', onChartResize);
      document.removeEventListener('visibilitychange', onVisibilityChange);
      window.removeEventListener('__VTJ_SYNC__', loadData);
      trendInstance?.dispose();
      trendInstance = null;
    });

    // 导航方法
    const goBack = () => {
      router.back();
    };

    const goToNotifications = () => {
      router.push('/mobile/notifications');
    };

    const viewMoreTrend = () => {
      // 查看更多趋势
    };

    const viewAllNews = () => {
      router.push('/mobile/news');
    };

    const viewNews = (news: any) => {
      router.push(`/mobile/news/${news.id}`);
    };

    return {
      userName,
      streakDays,
      // 动态问候语
      greeting,
      greetingIcon,
      // 今日目标（4 字段）
      dailyGoal,
      dailyCompleted,
      dailyGoalPercent,
      dailyGoalId,
      showGoalEdit,
      goalInput,
      subjectModeInput,
      subjectOptions,
      subjectLabel,
      weekGoalInput,
      expectedMinutesInput,
      savingGoal,
      openGoalEdit,
      saveGoal,
      loadDailyGoal,
      weekData,
      // 学习趋势图（柱/线切换）
      trendChartRef,
      chartType,
      trendHasData,
      switchChart,
      // 每日金句
      dailyQuote,
      quoteAttribution,
      quoteLoading,
      refreshQuote,
      newsList,
      goBack,
      goToNotifications,
      viewMoreTrend,
      viewAllNews,
      viewNews,
      ArrowLeft,
      ArrowRight,
      ArrowDown,
      Bell,
      Sunny,
  Lightning,
      EditPen,
      DataLine,
      TrendCharts,
      Timer,
      DataAnalysis,
      ChatDotRound,
      Document,
      Right,
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
.mobile-home-page {
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
  padding: 20px;
  margin-bottom: 16px;
  color: #ffffff;
}

.user-greeting {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.greeting-text {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 16px;
  font-weight: 600;
}

.streak-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.2);
  padding: 4px 10px;
  border-radius: 20px;
}

.daily-goal {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 12px;
}

.goal-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
}

.goal-label {
  opacity: 0.9;
}

.goal-progress {
  font-weight: 600;
}

.progress-bar {
  height: 6px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #ffffff;
  border-radius: 3px;
  transition: width 0.3s ease;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.stat-icon {
  margin-bottom: 8px;
  display: flex;
  justify-content: center;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #1A365D;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 12px;
  color: #5a6488;
}

/* 学习趋势 */
.trend-section {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
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
  gap: 6px;
  font-size: 15px;
  font-weight: 700;
  color: #1A365D;
  margin: 0;
}

.section-action {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #1890ff;
  cursor: pointer;
}

/* 容器高度须与 .chart-canvas / .chart-empty 的 200px 自洽。
 * 此前为 120px + flex 布局（旧 CSS 柱状图遗留），导致 200px 的 echarts
 * canvas 向上溢出 80px，盖住 .section-header 内的「柱状/折线」切换按钮
 * 并拦截其点击。echarts 场景下改为普通块级，overflow:hidden 作为防御。 */
.trend-chart {
  height: 200px;
  overflow: hidden;
}

.chart-bars {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  width: 100%;
  height: 100%;
}

.bar-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.bar-value {
  font-size: 10px;
  color: #5a6488;
  margin-bottom: 4px;
}

.bar {
  width: 24px;
  background: linear-gradient(180deg, #1A365D 0%, #2a5298 100%);
  border-radius: 4px 4px 0 0;
  min-height: 4px;
  transition: height 0.3s ease;
}

.bar-label {
  font-size: 11px;
  color: #5a6488;
  margin-top: 6px;
}

/* 每日金句 */
.quote-section {
  margin-bottom: 16px;
}

.quote-card {
  background: linear-gradient(135deg, #fff9e6 0%, #fff3cc 100%);
  border-radius: 12px;
  padding: 20px;
  position: relative;
}

/* 「换一句」按钮：绝对定位于卡片右上角，不挤占正文 */
.quote-refresh {
  position: absolute;
  top: 12px;
  right: 12px;
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
  border: 1px solid rgba(245, 158, 11, 0.35);
  border-radius: 12px;
  font-size: 12px;
  padding: 3px 10px;
  cursor: pointer;
}
.quote-refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 动态问候语：时段问候 + 激励语 */
.greeting-motto {
  display: block;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.85);
  margin-top: 2px;
}

/* 柱状/折线切换 */
.chart-switch {
  display: flex;
  gap: 4px;
}
.switch-btn {
  background: #f0f2f5;
  color: #5a6488;
  border: none;
  border-radius: 12px;
  font-size: 12px;
  padding: 3px 10px;
  cursor: pointer;
}
.switch-btn.active {
  background: #1a2b5f;
  color: #fff;
}

.chart-canvas {
  width: 100%;
  height: 200px;
}
.chart-empty {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8899aa;
  font-size: 13px;
}

.quote-icon {
  margin-bottom: 8px;
}

.quote-text {
  font-size: 15px;
  font-weight: 600;
  color: #1A365D;
  line-height: 1.6;
  margin: 0 0 8px;
}

.quote-author {
  font-size: 12px;
  color: #5a6488;
  margin: 0;
  text-align: right;
}

/* 每日新闻 */
.news-section {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.news-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.news-item {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 8px 0;
  border-bottom: 1px solid #f0f2f5;
}

.news-item:last-child {
  border-bottom: none;
}

.news-title {
  font-size: 14px;
  color: #1a2b5f;
  line-height: 1.4;
}

/* 底部Tab栏样式已收敛到单一真源组件 src/components/MobileTabBar.vue */

@media (max-width: 375px) {
  .main-content {
    padding: 12px;
  }
  
  .user-card {
    padding: 16px;
  }
  
  .stats-grid {
    gap: 8px;
  }
  
  .stat-card {
    padding: 12px;
  }
  
  .stat-value {
    font-size: 18px;
  }
}

@supports(padding-bottom: env(safe-area-inset-bottom)) {
  .bottom-tab-bar {
    height: calc(60px + env(safe-area-inset-bottom));
  }
}

/* ===== 今日目标可编辑 ===== */
.goal-edit-hint {
  display: block;
  margin-top: 6px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.7);
  text-align: right;
}

.goal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  z-index: 1000;
}

.goal-modal {
  background: #fff;
  border-radius: 14px;
  width: 100%;
  max-width: 380px;
  overflow: hidden;
}

.goal-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid #eef1f5;
}

.goal-modal-title {
  font-size: 15px;
  font-weight: 600;
  color: #1A365D;
}

.goal-modal-close {
  background: none;
  border: none;
  font-size: 18px;
  color: #8899aa;
  cursor: pointer;
  min-width: 44px;
  min-height: 44px;
}

.goal-modal-body {
  padding: 16px;
}

.goal-field-label {
  display: block;
  font-size: 13px;
  color: #5a6488;
  margin-bottom: 6px;
}

.goal-field-input {
  width: 100%;
  min-height: 44px;
  padding: 10px 12px;
  border: 1px solid #e8ecf1;
  border-radius: 8px;
  font-size: 16px;
  color: #1a2a3a;
  box-sizing: border-box;
}

.goal-field-input:focus {
  outline: none;
  border-color: #1A365D;
}

.goal-modal-actions {
  display: flex;
  padding: 12px 16px;
  border-top: 1px solid #eef1f5;
}

.goal-action-btn {
  flex: 1;
  min-height: 44px;
  border: 1px solid #1A365D;
  background: #1A365D;
  color: #fff;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
}

.goal-action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
