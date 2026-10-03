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
const stats = ref<any>({
  totalQuestions: 0, accuracyRate: 0, totalStudyHours: 0,
  streak: 0, examCount: 0, examAvgScore: 0
});
const trend = ref<any[]>([]);

// ===== 提升建议 =====
// 依据本页已加载的真实统计与趋势推导，不编造数据、不依赖额外后端。
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

/* ===== 提升建议 ===== */
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
</style>
