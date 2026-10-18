<!-- 手机端练习记录页（对标电脑端：统计卡 + ECharts 折线图 + 柱状图 + 记录列表） -->
<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack">←</button>
      <h1 class="title">练习记录</h1>
      <span class="spacer"></span>
    </header>

    <!-- 统计卡 -->
    <div class="stats">
      <div class="stat-card">
        <span class="stat-val">{{ stats.totalQuestions }}</span>
        <span class="stat-label">总做题</span>
      </div>
      <div class="stat-card">
        <span class="stat-val">{{ stats.accuracyRate }}%</span>
        <span class="stat-label">正确率</span>
      </div>
      <div class="stat-card">
        <span class="stat-val">{{ stats.totalStudyHours }}h</span>
        <span class="stat-label">学习时长</span>
      </div>
    </div>

    <!-- 折线图（趋势） -->
    <div class="chart-card">
      <div class="chart-head">
        <span class="chart-title">做题趋势</span>
        <div class="chart-tabs">
          <span :class="['ct', { active: trendDays === 7 }]" @click="loadTrend(7)">7天</span>
          <span :class="['ct', { active: trendDays === 30 }]" @click="loadTrend(30)">30天</span>
        </div>
      </div>
      <div ref="lineChart" class="chart"></div>
    </div>

    <!-- 柱状图（近7天做题量） -->
    <div class="chart-card">
      <span class="chart-title">近 7 天做题量</span>
      <div ref="barChart" class="chart"></div>
    </div>

    <!-- 记录列表 -->
    <div class="list-title">练习明细</div>
    <main class="list">
      <div v-for="r in records" :key="r.record_id" class="card" @click="toggleDetail(r.record_id)">
        <div class="r-head">
          <span :class="['r-flag', r.is_correct ? 'ok' : 'err']">{{ r.is_correct ? '✓' : '✗' }}</span>
          <span class="r-content">{{ r.question_content || '（题目内容）' }}</span>
        </div>
        <div class="r-meta">
          <span class="tag">{{ r.source || '练习' }}</span>
          <span class="time">{{ (r.practice_time || '').slice(0, 16) }}</span>
        </div>
        <div v-if="expandedId === r.record_id" class="r-detail" @click.stop>
          <div class="detail-row"><b>你的答案：</b>{{ r.user_answer || '未答' }}</div>
          <div class="detail-row"><b>正确答案：</b>{{ r.correct_answer || '无' }}</div>
        </div>
      </div>
      <div v-if="error" class="empty">{{ error }}</div>
      <div v-else-if="!records.length && !loading" class="empty">暂无练习记录</div>
      <div v-if="loading" class="empty">加载中...</div>
      <button v-if="hasMore" class="load-more" @click="loadMore">加载更多</button>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import * as echarts from 'echarts';
import { useRecordsStore } from '@/modules/records/store';

const router = useRouter();

const recordsStore = useRecordsStore();
const { loading, error, filteredRecords, hasMore, stats: recordStats, trend, trendDays } = storeToRefs(recordsStore);
const records = filteredRecords;

const stats = computed(() => ({
  totalQuestions: recordStats.value?.totalQuestions ?? 0,
  accuracyRate: recordStats.value?.accuracyRate ?? 0,
  totalStudyHours: recordStats.value?.totalStudyHours ?? 0
}));

const expandedId = ref<number | null>(null);

const lineChart = ref<HTMLDivElement | null>(null);
const barChart = ref<HTMLDivElement | null>(null);
let lineInstance: any = null;
let barInstance: any = null;
let offRefresh: (() => void) | null = null;

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/profile');
};

const toggleDetail = (id: number) => {
  expandedId.value = expandedId.value === id ? null : id;
};

function loadMore() {
  void recordsStore.loadMore();
}

async function loadTrend(days: number) {
  await recordsStore.loadTrend(days);
}

function renderLineChart(points: any[]) {
  if (!lineChart.value) return;
  if (!lineInstance) lineInstance = echarts.init(lineChart.value);
  lineInstance.setOption({
    grid: { left: 36, right: 12, top: 20, bottom: 24 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: points.map((t: any) => (t.date || '').slice(5)), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      type: 'line',
      data: points.map((t: any) => t.questionsDone || 0),
      smooth: true,
      lineStyle: { color: '#1A365D', width: 2 },
      itemStyle: { color: '#1A365D' },
      areaStyle: { color: 'rgba(26, 54, 93, 0.08)' },
    }],
  });
}

function renderBarChart(points: any[]) {
  if (!barChart.value) return;
  if (!barInstance) barInstance = echarts.init(barChart.value);
  barInstance.setOption({
    grid: { left: 36, right: 12, top: 20, bottom: 24 },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: points.map((t: any) => (t.date || '').slice(5)), axisLabel: { fontSize: 10 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      type: 'bar',
      data: points.map((t: any) => t.questionsDone || 0),
      barWidth: '50%',
      itemStyle: { color: '#2a5298', borderRadius: [4, 4, 0, 0] },
    }],
  });
}

function handleResize() {
  lineInstance?.resize();
  barInstance?.resize();
}

watch(trend, (points) => {
  renderLineChart(points);
  if (trendDays.value === 7) renderBarChart(points);
});

onMounted(async () => {
  await nextTick();
  await Promise.all([
    recordsStore.load(),
    recordsStore.loadStats(),
    recordsStore.loadTrend(7)
  ]);
  renderLineChart(trend.value);
  renderBarChart(trend.value);
  offRefresh = recordsStore.bindRecordsRefresh();
  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  offRefresh?.();
  window.removeEventListener('resize', handleResize);
  lineInstance?.dispose();
  barInstance?.dispose();
});
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #F5F7FA;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
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
.back-btn { background: none; border: none; font-size: 22px; color: #1a2b5f; cursor: pointer; padding: 4px 8px; }
.title { font-size: 16px; font-weight: 600; color: #1a2b5f; margin: 0; }
.spacer { width: 32px; }

.stats { display: flex; gap: 10px; padding: 12px; }
.stat-card { flex: 1; background: #fff; border-radius: 12px; padding: 14px 8px; text-align: center; box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04); display: flex; flex-direction: column; gap: 4px; }
.stat-val { font-size: 20px; font-weight: 800; color: #1A365D; }
.stat-label { font-size: 11px; color: #8899aa; }

.chart-card { background: #fff; border-radius: 12px; padding: 14px; margin: 0 12px 12px; box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04); }
.chart-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.chart-title { font-size: 14px; font-weight: 700; color: #1a2b5f; }
.chart-tabs { display: flex; gap: 4px; }
.ct { padding: 3px 10px; font-size: 12px; color: #5a6488; border-radius: 12px; cursor: pointer; }
.ct.active { background: #1A365D; color: #fff; }
.chart { width: 100%; height: 200px; }

.list-title { font-size: 14px; font-weight: 700; color: #1a2b5f; padding: 4px 16px 8px; }
.list { flex: 1; padding: 0 12px 20px; }
.card { background: #fff; border-radius: 12px; padding: 14px; margin-bottom: 10px; box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04); cursor: pointer; }
.r-head { display: flex; align-items: flex-start; gap: 8px; }
.r-flag { width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; flex-shrink: 0; margin-top: 1px; }
.r-flag.ok { background: #f0fdf4; color: #22c55e; }
.r-flag.err { background: #fef2f2; color: #ef4444; }
.r-content { flex: 1; font-size: 14px; color: #1a2b5f; line-height: 1.5; }
.r-meta { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; }
.tag { font-size: 11px; color: #5a6488; background: #f0f3f7; padding: 2px 8px; border-radius: 6px; }
.time { font-size: 11px; color: #8899aa; }
.r-detail { margin-top: 10px; padding-top: 10px; border-top: 1px solid #f0f2f5; }
.detail-row { font-size: 13px; color: #5a6488; line-height: 1.6; }
.detail-row b { color: #1a2b5f; }
.empty { text-align: center; color: #8899aa; padding: 40px 0; }
.load-more { width: 100%; min-height: 40px; background: #fff; border: 1px solid #e8eaf0; border-radius: 10px; font-size: 13px; color: #1a2b5f; cursor: pointer; margin-top: 4px; }
</style>
