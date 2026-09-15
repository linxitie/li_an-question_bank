<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">成绩分析</h1>
      <span class="spacer"></span>
    </header>

    <main class="body">
      <!-- 统计卡片 2×2 -->
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

      <!-- 练习趋势柱状图 -->
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

      <!-- 考试记录 -->
      <div class="exam-card" v-if="stats.examCount">
        <div class="exam-title">考试记录</div>
        <div class="exam-row">参加考试：{{ stats.examCount }} 场</div>
        <div class="exam-row" v-if="stats.examAvgScore">平均分：{{ stats.examAvgScore }}</div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const stats = ref<any>({
  totalQuestions: 0, accuracyRate: 0, totalStudyHours: 0,
  streak: 0, examCount: 0, examAvgScore: 0
});
const trend = ref<any[]>([]);

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const fetchStats = async () => {
  try {
    const auth = (window as any).__VTJ_AUTH__;
    if (!auth || !auth.isLoggedIn()) return;
    const res = await auth.apiFetch('/api/stats/');
    const data = await res.json();
    if (res.ok) {
      stats.value = {
        totalQuestions: data.totalQuestions || 0,
        accuracyRate: data.accuracyRate || 0,
        totalStudyHours: data.totalStudyHours || 0,
        streak: data.streak || 0,
        examCount: data.examCount || 0,
        examAvgScore: data.examAvgScore || 0
      };
    }
  } catch (e) {
    console.error('获取统计失败:', e);
  }
};

const fetchTrend = async () => {
  try {
    const auth = (window as any).__VTJ_AUTH__;
    if (!auth || !auth.isLoggedIn()) return;
    const res = await auth.apiFetch('/api/stats/practice-trend?days=7');
    const data = await res.json();
    if (res.ok && data.trend) trend.value = data.trend;
  } catch (e) {
    console.error('获取趋势失败:', e);
  }
};

const barHeight = (count: number) => {
  const max = Math.max(...trend.value.map((d) => d.questionsDone || 0), 1);
  return Math.max(4, Math.round((count / max) * 100));
};

const shortDate = (date: string) => {
  if (!date) return '';
  const parts = date.split('-');
  return parts.length === 3 ? parts[1] + '/' + parts[2] : date;
};

onMounted(() => {
  fetchStats();
  fetchTrend();
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
.exam-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}
.exam-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
  margin-bottom: 10px;
}
.exam-row {
  font-size: 13px;
  color: #5a6488;
  margin-bottom: 6px;
}
</style>
