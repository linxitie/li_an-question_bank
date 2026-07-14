<!-- 成绩分析模块 -->
<template>
  <div class="score-analysis-page">
    <NavBar></NavBar>
    <main class="sa-main">
      <div class="sa-header">
        <h2>
          <XIcon :icon="DataAnalysis" :size="24" color="#c41e3a"></XIcon>
          <span> 成绩分析</span>
        </h2>
        <div class="sa-tabs">
          <button
            :class="['tab-btn', { active: state.activeTab === 'self' }]"
            @click="state.activeTab = 'self'">
            自测
          </button>
          <button
            :class="['tab-btn', { active: state.activeTab === 'mock' }]"
            @click="state.activeTab = 'mock'">
            模拟考试
          </button>
        </div>
      </div>
      <div v-if="!state.hasData" class="empty-state">
        <div class="empty-illustration">
          <span class="empty-icon"> 📋</span>
        </div>
        <h3>还没有做过试卷哦</h3>
        <p>去题库刷题或参加模拟考试，数据会展示在这里</p>
        <button class="go-practice-btn" @click="goToBank">去刷题</button>
      </div>
      <div v-if="state.hasData" class="sa-content">
        <div class="chart-card">
          <div class="card-header">
            <span>
              {{
                state.activeTab === 'self'
                  ? '成绩变化趋势'
                  : '模拟考试成绩与排名'
              }}</span
            >
            <span class="card-sub">
              {{
                state.activeTab === 'self' ? '近10次自测' : '近5次模考'
              }}</span
            >
          </div>
          <XChart width="100%" height="340px" :option="chartOption"></XChart>
        </div>
        <div class="stats-row">
          <div class="stat-card">
            <div
              class="stat-icon div_26w1jvel2op"
              :style="{ background: '#eff6ff' }">
              <XIcon :icon="TrophyBase" :size="22" color="#3b82f6"></XIcon>
            </div>
            <div class="stat-info">
              <span class="stat-label"> 最高分</span>
              <span class="stat-value"> {{ state.stats.highest }}</span>
            </div>
          </div>
          <div class="stat-card">
            <div
              class="stat-icon div_26w7jvel2op"
              :style="{ background: '#fef2f2' }">
              <XIcon :icon="TrendCharts" :size="22" color="#ef4444"></XIcon>
            </div>
            <div class="stat-info">
              <span class="stat-label"> 平均分</span>
              <span class="stat-value"> {{ state.stats.average }}</span>
            </div>
          </div>
          <div class="stat-card">
            <div
              class="stat-icon div_26wdjvel2op"
              :style="{ background: '#fffbeb' }">
              <XIcon :icon="Medal" :size="22" color="#f59e0b"></XIcon>
            </div>
            <div class="stat-info">
              <span class="stat-label">
                {{ state.activeTab === 'mock' ? '排名' : '超越' }}</span
              >
              <span class="stat-value"> {{ state.stats.rank }}</span>
            </div>
          </div>
          <div class="stat-card">
            <div
              class="stat-icon div_26wjjvel2op"
              :style="{ background: '#f0fdf4' }">
              <XIcon :icon="CircleCheck" :size="22" color="#10b981"></XIcon>
            </div>
            <div class="stat-info">
              <span class="stat-label"> 正确率</span>
              <span class="stat-value">
                <span>
                  <span> {{ state.stats.accuracy }}</span>
                  <span> %</span></span
                ></span
              >
            </div>
          </div>
        </div>
        <div class="detail-row">
          <div class="detail-card">
            <h4>做题详情</h4>
            <div class="detail-list">
              <div
                v-for="(d, idx) in state.details"
                :key="idx"
                class="detail-item">
                <span class="detail-date"> {{ d.date }}</span>
                <span class="detail-score">
                  <span>
                    <span> {{ d.score }}</span>
                    <span> 分</span></span
                  ></span
                >
                <span class="detail-accuracy">
                  <span>
                    <span> {{ d.accuracy }}</span>
                    <span> %</span></span
                  ></span
                >
              </div>
            </div>
          </div>
          <div class="advice-card">
            <h4>
              <XIcon :icon="Opportunity" :size="18" color="#c41e3a"></XIcon>
              <span> 提升建议</span>
            </h4>
            <ul class="advice-list">
              <li v-for="(a, idx) in state.advices" :key="idx">
                {{ a }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { XChart } from '@vtj/charts';
  import {
    DataAnalysis,
    TrophyBase,
    TrendCharts,
    Medal,
    CircleCheck,
    Opportunity
  } from '@vtj/icons';
  import NavBar from './navbar.vue';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'ScoreAnalysis',
    components: { NavBar, XIcon, XChart },
    setup(props) {
      const provider = useProvider({ id: 'score_analysis', version: '1778918611111' });
      const state = reactive({
        stats: { highest: 0, average: 0, rank: '--', accuracy: 0 },
        advices: [],
        details: [],
        hasData: true,
        activeTab: 'self',
        statsLoading: false,
        statsLoaded: false,
        trendScores: [],
        trendAvgScores: []
      });
      return {
        state,
        props,
        provider,
        DataAnalysis,
        TrophyBase,
        TrendCharts,
        Medal,
        CircleCheck,
        Opportunity
      };
    },
    computed: {
      chartOption() {
        const scores = this.state.trendScores.length > 0
          ? this.state.trendScores
          : [62, 68, 55, 72, 70, 78, 65, 80, 73, 82];
        const avgLine = this.state.trendAvgScores.length > 0
          ? this.state.trendAvgScores
          : scores.map(() => 60);
        const labels = scores.map((_, i) => `第${i + 1}次`);
        return {
          tooltip: { trigger: 'axis' },
          legend: { data: ['分数', '平均分'] },
          grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
          xAxis: {
            type: 'category',
            data: labels
          },
          yAxis: { type: 'value', min: 0, max: 100 },
          series: [
            {
              name: '分数',
              type: 'line',
              data: scores,
              lineStyle: { color: '#c41e3a' },
              itemStyle: { color: '#c41e3a' },
              smooth: true
            },
            {
              name: '平均分',
              type: 'line',
              data: avgLine,
              lineStyle: { type: 'dashed', color: '#8a8faa' },
              itemStyle: { color: '#8a8faa' }
            }
          ]
        };
      }
    },
    methods: {
      ensureLogin() {
        if (window.__VTJ_AUTH__ && window.__VTJ_AUTH__.isLoggedIn && window.__VTJ_AUTH__.isLoggedIn()) return true;
        return false;
      },
      getJsonHeaders() {
        return (window.__VTJ_AUTH__ && window.__VTJ_AUTH__.getJsonHeaders) ? window.__VTJ_AUTH__.getJsonHeaders() : { 'Content-Type': 'application/json' };
      },
      getAuthHeaders() {
        return (window.__VTJ_AUTH__ && window.__VTJ_AUTH__.getAuthHeaders) ? window.__VTJ_AUTH__.getAuthHeaders() : {};
      },
      goToBank() {
        this.$router.push('/page/question_bank');
      },
      async fetchDashboardStats() {
        if (this.state.statsLoading) return;
        this.state.statsLoading = true;
        try {
          const headers = this.getAuthHeaders();
          // 获取仪表盘数据
          const dashResp = await fetch('/api/stats/dashboard', { headers });
          if (dashResp.ok) {
            const dash = await dashResp.json();
            this.state.stats = {
              highest: dash.examAvgScore || 0,
              average: Math.round(dash.accuracyRate || 0),
              rank: dash.goalCompletionRate ? `前${Math.round(100 - dash.goalCompletionRate)}%` : '--',
              accuracy: dash.accuracyRate || 0
            };
            // 生成建议
            const advices = [];
            if (dash.accuracyRate < 60) advices.push('正确率偏低，建议加强基础知识点复习');
            if (dash.streak < 3) advices.push('连续签到天数较少，坚持每日练习更有成效');
            if (dash.todayQuestions < 10) advices.push('今日刷题量较少，建议每天至少完成20道练习');
            if (dash.goalCompletionRate < 50) advices.push('目标完成率较低，可适当调整目标难度');
            if (advices.length === 0) advices.push('学习状态良好，继续保持！');
            this.state.advices = advices;
            this.state.statsLoaded = true;
          }
          // 获取趋势数据
          const trendResp = await fetch('/api/stats/practice-trend?days=10', { headers });
          if (trendResp.ok) {
            const trend = await trendResp.json();
            if (trend.dailyTrend && trend.dailyTrend.length > 0) {
              this.state.trendScores = trend.dailyTrend.map(d => d.count || 0);
              this.state.trendAvgScores = trend.dailyTrend.map(d => d.avgAccuracy || 60);
            }
          }
        } catch (e) {
          console.warn('[ScoreAnalysis] API fetch failed, using defaults:', e.message);
        } finally {
          this.state.statsLoading = false;
        }
      },
      loadData() {
        if (this.state.hasData && !this.state.statsLoaded) {
          // 尝试从 API 获取，失败时使用模拟数据
          if (this.ensureLogin()) {
            this.fetchDashboardStats();
          } else {
            // 未登录用户使用默认模拟数据
            this.state.stats = {
              highest: 82,
              average: 70.5,
              rank: '前20%',
              accuracy: 72
            };
            this.state.details = [
              { date: '2024-12-22', score: 82, accuracy: 80 },
              { date: '2024-12-19', score: 73, accuracy: 72 },
              { date: '2024-12-15', score: 78, accuracy: 74 },
              { date: '2024-12-10', score: 65, accuracy: 62 }
            ];
            this.state.advices = [
              '资料分析模块正确率偏低，建议加强速算练习',
              '判断推理中逻辑判断题耗时较长，可针对性训练',
              '建议每周至少完成一次计时模拟，提升做题节奏'
            ];
          }
        }
      }
    },
    mounted() {
      this.loadData();
    }
  })
</script>
<style lang="css" scoped>
  .score-analysis-page {
    min-height: 100vh;
    background: #f8f9fc;
    font-family: 'Noto Sans SC', 'PingFang SC', sans-serif;
  }
  .sa-main {
    max-width: 1300px;
    margin: 0 auto;
    padding: 24px 32px 40px;
  }
  .sa-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
  }
  .sa-header h2 {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 22px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0;
  }
  .sa-tabs {
    display: flex;
    gap: 4px;
    background: #ffffff;
    border-radius: 12px;
    padding: 4px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  }
  .tab-btn {
    padding: 10px 24px;
    border: none;
    background: transparent;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 700;
    color: #5a6488;
    cursor: pointer;
    transition: all 0.3s;
  }
  .tab-btn.active {
    background: #1a2b5f;
    color: #ffffff;
    box-shadow: 0 2px 8px rgba(26, 43, 95, 0.3);
  }
  .empty-state {
    text-align: center;
    padding: 80px 0;
  }
  .empty-illustration {
    margin-bottom: 20px;
  }
  .empty-icon {
    font-size: 64px;
  }
  .empty-state h3 {
    font-size: 20px;
    color: #1a2b5f;
    margin: 0 0 8px;
  }
  .empty-state p {
    color: #8a8faa;
    margin: 0 0 24px;
  }
  .go-practice-btn {
    padding: 12px 32px;
    background: linear-gradient(135deg, #1a2b5f, #1e3470);
    color: #fff;
    border: none;
    border-radius: 12px;
    cursor: pointer;
    font-size: 15px;
    font-weight: 700;
  }
  .sa-content {
    display: flex;
    flex-direction: column;
    gap: 24px;
  }
  .chart-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.04);
  }
  .card-header {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 8px;
    font-size: 16px;
    font-weight: 700;
    color: #1a2b5f;
  }
  .card-sub {
    font-size: 12px;
    color: #8a8faa;
    font-weight: 500;
  }
  .stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
  }
  .stat-card {
    background: #ffffff;
    border-radius: 14px;
    padding: 20px;
    display: flex;
    align-items: center;
    gap: 14px;
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.04);
  }
  .stat-icon {
    width: 48px;
    height: 48px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .stat-info {
    display: flex;
    flex-direction: column;
  }
  .stat-label {
    font-size: 12px;
    color: #8a8faa;
  }
  .stat-value {
    font-size: 24px;
    font-weight: 900;
    color: #1a2b5f;
    margin-top: 2px;
    font-family: 'DIN Alternate', sans-serif;
  }
  .detail-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }
  .detail-card,
  .advice-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.04);
  }
  .detail-card h4,
  .advice-card h4 {
    font-size: 16px;
    font-weight: 700;
    color: #1a2b5f;
    margin: 0 0 16px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .detail-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .detail-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    background: #f8f9fc;
    border-radius: 10px;
    font-size: 13px;
    color: #333;
  }
  .detail-date {
    color: #8a8faa;
  }
  .detail-score {
    font-weight: 700;
    color: #1a2b5f;
  }
  .detail-accuracy {
    color: #10b981;
    font-weight: 600;
  }
  .advice-list {
    padding-left: 18px;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .advice-list li {
    font-size: 13px;
    color: #5a6488;
    line-height: 1.6;
  }
</style>
