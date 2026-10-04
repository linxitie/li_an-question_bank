<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">成绩分析</h1>
      <span class="spacer"></span>
    </header>

    <!-- 三个数据域严格分离：自测成绩 / 模拟考成绩 / 历史记录（日常刷题） -->
    <div class="tabs">
      <div
        v-for="t in TABS"
        :key="t.key"
        :class="['tab', { active: activeTab === t.key }]"
        @click="switchTab(t.key)"
      >{{ t.name }}</div>
    </div>

    <main class="body" v-if="activeTab !== 'history'">
      <!-- 空态：按 tab 区分文案 -->
      <div v-if="!loading && !examRecords.length" class="empty">{{ emptyText }}</div>
      <div v-else-if="loading" class="empty">加载中...</div>

      <template v-else>
        <!-- 考试成绩统计：最高分 / 平均分 / 正确率 / 排名(模考)或场次(自测) -->
        <div class="stat-grid">
          <div class="stat-card">
            <div class="stat-value">{{ examStats.highest_score || 0 }}</div>
            <div class="stat-label">最高分</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ examStats.average_score || 0 }}</div>
            <div class="stat-label">平均分</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ examStats.accuracy_rate || 0 }}%</div>
            <div class="stat-label">正确率</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ fourthValue }}</div>
            <div class="stat-label">{{ fourthLabel }}</div>
          </div>
        </div>

        <!-- 成绩趋势 -->
        <div class="trend-card" v-if="examTrend.length">
          <div class="trend-title">
            成绩趋势
            <span class="trend-avg">平均 {{ examAvgScore }}</span>
          </div>
          <div class="bar-chart">
            <div v-for="(d, i) in examTrend" :key="i" class="bar-col">
              <div class="bar-wrap">
                <div class="bar" :style="{ height: scoreBarHeight(d) + 'px' }"></div>
              </div>
              <div class="bar-count">{{ d.total_score }}</div>
              <div class="bar-label">{{ shortDate(d.submit_time) }}</div>
            </div>
          </div>
        </div>

        <!-- 成绩记录 -->
        <div class="record-card">
          <div class="record-title">{{ tabName }}记录</div>
          <div v-for="r in examRecords" :key="r.record_id" class="record-row">
            <div class="record-main">
              <div class="record-name">{{ r.paper_name }}</div>
              <div class="record-meta">{{ r.submit_time || '—' }} · 用时 {{ formatDuration(r.duration_used) }}</div>
            </div>
            <div class="record-score">
              <div class="record-num">{{ r.total_score }}</div>
              <div class="record-max">/{{ r.max_score }} · {{ r.accuracy }}%</div>
            </div>
          </div>
        </div>
      </template>
    </main>

    <!-- 历史记录：日常刷题统计（非考试成绩） -->
    <main class="body" v-else>
      <div class="stat-grid">
        <div class="stat-card">
          <div class="stat-value">{{ stats.totalQuestions }}</div>
          <div class="stat-label">总练习量</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.accuracyRate }}%</div>
          <div class="stat-label">平均正确率</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.totalStudyHours }}h</div>
          <div class="stat-label">学习时长</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ stats.streak }}天</div>
          <div class="stat-label">连续签到</div>
        </div>
      </div>

      <div class="trend-card">
        <div class="trend-title">近 7 天练习趋势</div>
        <div class="bar-chart">
          <div v-for="(d, i) in trend" :key="i" class="bar-col">
            <div class="bar-wrap">
              <div class="bar" :style="{ height: barHeight(d.questionsDone) + 'px' }"></div>
            </div>
            <div class="bar-label">{{ shortDate(d.date) }}</div>
            <div class="bar-count">{{ d.questionsDone }}</div>
          </div>
        </div>
      </div>

      <!-- 提升建议（基于本页真实数据推导，非编造） -->
      <div class="advice-card" v-if="adviceList.length">
        <div class="advice-title">💡 提升建议</div>
        <div v-for="(a, i) in adviceList" :key="i" :class="['advice-item', a.level]">
          <div class="advice-text">{{ a.text }}</div>
        </div>
        <div class="advice-note">建议依据本页统计与趋势自动生成，仅供参考</div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();

// ===== 数据域拆分 =====
// 用户反馈「显示的是做题数量而非考试成绩」的根因：原页面只有刷题统计，
// 完全没有 tab，也没有接入 exam-records 成绩体系。
// 现严格按电脑端口径拆为三块，且互不混用：
//   自测成绩   -> ExamRecord.exam_type = SELF_TEST（历年试卷 / 智能组卷产生）
//   模拟考成绩 -> ExamRecord.exam_type = MOCK_EXAM
//   历史记录   -> 日常刷题统计（原 /api/stats/ 数据源）
const TABS = [
  { key: 'self', name: '自测成绩' },
  { key: 'mock', name: '模拟考成绩' },
  { key: 'history', name: '历史记录' },
] as const;

type TabKey = 'self' | 'mock' | 'history';

const activeTab = ref<TabKey>('self');
const loading = ref(false);

// 与电脑端一致：自测取最近 10 次，模考取最近 5 次
const examTypeOf = (tab: TabKey) => (tab === 'mock' ? 'MOCK_EXAM' : 'SELF_TEST');
const limitOf = (tab: TabKey) => (tab === 'mock' ? 5 : 10);

const examStats = ref<any>({});
const examTrend = ref<any[]>([]);
const examRecords = ref<any[]>([]);
const examAvgScore = ref(0);

const tabName = computed(() => (activeTab.value === 'mock' ? '模拟考' : '自测'));
const emptyText = computed(() =>
  activeTab.value === 'mock' ? '还没有做过模考哦' : '还没有做过自测哦'
);

// 模考展示排名百分比（后端仅对 MOCK_EXAM 计算 rank_percent），自测展示考试场次
const fourthValue = computed(() => {
  if (activeTab.value === 'mock') {
    const r = examStats.value.rank_percent;
    return r === null || r === undefined ? '--' : '前' + r + '%';
  }
  return examStats.value.total_exams || 0;
});
const fourthLabel = computed(() =>
  activeTab.value === 'mock' ? '排名' : '考试场次'
);

// ===== 历史记录（日常刷题） =====
const stats = ref<any>({
  totalQuestions: 0, accuracyRate: 0, totalStudyHours: 0, streak: 0
});
const trend = ref<any[]>([]);

const adviceList = computed(() => {
  const out: { text: string; level: string }[] = [];
  const acc = Number(stats.value.accuracyRate) || 0;
  const total = Number(stats.value.totalQuestions) || 0;
  const weekTotal = trend.value.reduce((s, d) => s + (Number(d.questionsDone) || 0), 0);
  const activeDays = trend.value.filter((d) => (Number(d.questionsDone) || 0) > 0).length;

  if (total === 0) {
    out.push({ text: '还没有练习记录，先从「快速练习」做 20 道题建立基线吧。', level: 'high' });
    return out;
  }
  if (acc < 60) {
    out.push({ text: `平均正确率 ${acc}%，偏低。建议先回到错题本复盘，弄清每道错题的失分原因再继续刷新题。`, level: 'high' });
  } else if (acc < 75) {
    out.push({ text: `平均正确率 ${acc}%，处于提升区间。建议按知识点专项突破，优先攻克正确率最低的模块。`, level: 'mid' });
  } else {
    out.push({ text: `平均正确率 ${acc}%，表现不错。可适当提高难度，尝试混合练习或限时模考。`, level: 'good' });
  }

  if (activeDays > 0 && activeDays < 5) {
    out.push({ text: `近 7 天仅 ${activeDays} 天有练习记录，规律性不足，建议固定每天的刷题时段。`, level: 'mid' });
  }
  if (weekTotal > 0 && weekTotal < 50) {
    out.push({ text: `近 7 天累计 ${weekTotal} 题，题量偏少，可把每日目标上调以保证手感。`, level: 'mid' });
  }
  if ((Number(stats.value.streak) || 0) >= 7) {
    out.push({ text: `已连续学习 ${stats.value.streak} 天，保持住这个节奏。`, level: 'good' });
  }
  return out;
});

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

// ===== 数据加载 =====

const auth = () => (window as any).__VTJ_AUTH__;

/** 切换 tab 时按 exam_type 重新拉取该域的三份数据 */
async function loadExamTab(tab: TabKey) {
  const a = auth();
  if (!a || !a.isLoggedIn()) return;
  loading.value = true;
  const t = examTypeOf(tab);
  try {
    const [trendRes, statsRes, listRes] = await Promise.all([
      a.apiFetch(`/api/exam-records/trend?exam_type=${t}&limit=${limitOf(tab)}`),
      a.apiFetch(`/api/exam-records/stats?exam_type=${t}`),
      a.apiFetch(tab === 'mock' ? '/api/exam-records/mock?page=1&page_size=20' : '/api/exam-records/self?page=1&page_size=20'),
    ]);
    const [trendData, statsData, listData] = await Promise.all([
      trendRes.json(), statsRes.json(), listRes.json(),
    ]);
    examTrend.value = trendRes.ok ? (trendData.trend || []) : [];
    examAvgScore.value = trendRes.ok ? (trendData.avg_score || 0) : 0;
    examStats.value = statsRes.ok ? (statsData || {}) : {};
    examRecords.value = listRes.ok ? (listData.records || []) : [];
  } catch (e) {
    console.error('获取考试成绩失败:', e);
    examTrend.value = [];
    examStats.value = {};
    examRecords.value = [];
  } finally {
    loading.value = false;
  }
}

const loadHistory = async () => {
  const a = auth();
  if (!a || !a.isLoggedIn()) return;
  try {
    const [statsRes, trendRes] = await Promise.all([
      a.apiFetch('/api/stats/'),
      a.apiFetch('/api/stats/practice-trend?days=7'),
    ]);
    const [statsData, trendData] = await Promise.all([statsRes.json(), trendRes.json()]);
    if (statsRes.ok) {
      stats.value = {
        totalQuestions: statsData.totalQuestions || 0,
        accuracyRate: statsData.accuracyRate || 0,
        totalStudyHours: statsData.totalStudyHours || 0,
        streak: statsData.streak || 0,
      };
    }
    if (trendRes.ok) trend.value = trendData.trend || [];
  } catch (e) {
    console.error('获取刷题统计失败:', e);
  }
};

function switchTab(tab: TabKey) {
  if (activeTab.value === tab) return;
  activeTab.value = tab;
  if (tab === 'history') loadHistory();
  else loadExamTab(tab);
}

// ===== 展示辅助 =====
const barHeight = (count: number) => {
  const max = Math.max(...trend.value.map((d) => d.questionsDone || 0), 1);
  return Math.max(4, Math.round((count / max) * 100));
};

/** 成绩柱高按满分归一化，避免不同卷满分不同导致视觉失真 */
const scoreBarHeight = (d: any) => {
  const maxScore = Number(d.max_score) || 100;
  const pct = (Number(d.total_score) || 0) / maxScore;
  return Math.max(4, Math.round(pct * 100));
};

const shortDate = (date: string) => {
  if (!date) return '';
  const parts = String(date).split('-');
  return parts.length === 3 ? parts[1] + '/' + parts[2] : String(date).slice(5, 10);
};

const formatDuration = (seconds: number) => {
  const s = Number(seconds) || 0;
  if (!s) return '—';
  const m = Math.round(s / 60);
  return m < 60 ? `${m} 分钟` : `${Math.floor(m / 60)} 小时 ${m % 60} 分`;
};

onMounted(() => {
  loadExamTab('self');
});
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #F5F7FA;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 48px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #e8ecf1;
  position: sticky;
  top: 0;
  z-index: 10;
}
.back-btn {
  background: none;
  border: none;
  font-size: 22px;
  color: #1a2b5f;
  cursor: pointer;
  padding: 4px 8px;
}
.title {
  font-size: 16px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0;
}
.spacer {
  width: 32px;
}

.tabs {
  display: flex;
  margin: 12px 12px 0;
  background: #fff;
  border-radius: 10px;
  padding: 4px;
}
.tab {
  flex: 1;
  text-align: center;
  padding: 8px;
  font-size: 14px;
  color: #5a6488;
  cursor: pointer;
  border-radius: 8px;
}
.tab.active {
  background: #1A365D;
  color: #fff;
  font-weight: 600;
}

.body {
  flex: 1;
  padding: 12px;
}
.stat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}
.stat-card {
  background: #fff;
  border-radius: 12px;
  padding: 18px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  text-align: center;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #1a2b5f;
}
.stat-label {
  font-size: 12px;
  color: #8899aa;
  margin-top: 4px;
}
.trend-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  margin-bottom: 12px;
}
.trend-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.trend-avg {
  font-size: 12px;
  font-weight: 400;
  color: #8899aa;
}
.bar-chart {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 6px;
}
.bar-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.bar-wrap {
  height: 110px;
  display: flex;
  align-items: flex-end;
}
.bar {
  width: 18px;
  background: linear-gradient(180deg, #c41e3a, #e85d75);
  border-radius: 4px 4px 0 0;
}
.bar-label {
  font-size: 11px;
  color: #8899aa;
  margin-top: 6px;
}
.bar-count {
  font-size: 11px;
  color: #5a6488;
}

.record-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}
.record-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
  margin-bottom: 10px;
}
.record-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 0;
  border-top: 1px solid #f0f2f5;
}
.record-row:first-of-type {
  border-top: none;
}
.record-main {
  flex: 1;
  min-width: 0;
}
.record-name {
  font-size: 13px;
  color: #1a2b5f;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.record-meta {
  font-size: 11px;
  color: #8899aa;
  margin-top: 3px;
}
.record-score {
  text-align: right;
  flex-shrink: 0;
}
.record-num {
  font-size: 17px;
  font-weight: 700;
  color: #c41e3a;
}
.record-max {
  font-size: 11px;
  color: #8899aa;
}

.advice-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}
.advice-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
  margin-bottom: 10px;
}
.advice-item {
  border-left: 3px solid #1A365D;
  background: #f8f9fc;
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 8px;
}
.advice-item.high {
  border-left-color: #c41e3a;
}
.advice-item.mid {
  border-left-color: #f59e0b;
}
.advice-item.good {
  border-left-color: #10b981;
}
.advice-text {
  font-size: 13px;
  line-height: 1.7;
  color: #1a2a3a;
}
.advice-note {
  margin-top: 10px;
  font-size: 11px;
  color: #8899aa;
}
.empty {
  text-align: center;
  color: #8899aa;
  padding: 40px 0;
}
</style>