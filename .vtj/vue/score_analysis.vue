<!-- 成绩分析模块 -->
<template>
  <div class="score-analysis-page">
    <NavBar></NavBar>
    <main class="sa-main">
      <!-- 顶部导航栏 -->
      <div class="sa-header">
        <div class="header-left">
          <button class="back-btn" @click="goToQuestionBank">
            <XIcon :icon="ArrowLeft" :size="18" color="#5a6488"></XIcon>
            <span>返回题库</span>
          </button>
        </div>
        <h2>
          <XIcon :icon="DataAnalysis" :size="24" color="#c41e3a"></XIcon>
          <span> 成绩分析</span>
        </h2>
        <div class="sa-tabs">
          <button
            :class="['tab-btn', { active: state.activeTab === 'self' }]"
            @click="switchTab('self')">
            自测
          </button>
          <button
            :class="['tab-btn', { active: state.activeTab === 'mock' }]"
            @click="switchTab('mock')">
            模拟考试
          </button>
        </div>
      </div>

      <!-- 实时监控指示器 -->
      <div class="monitor-bar">
        <span class="monitor-dot" :class="{ active: state.monitoring }"></span>
        <span class="monitor-text">
          {{ state.monitoring ? '实时监控中' : '监控已暂停' }}
          · 上次更新: {{ state.lastUpdate || '--' }}
        </span>
        <button class="refresh-btn" @click="loadData" :disabled="state.chartLoading">
          <XIcon :icon="Refresh" :size="14" color="#5a6488"></XIcon>
          <span>手动刷新</span>
        </button>
      </div>

      <!-- 无数据状态 -->
      <div v-if="!state.hasData && !state.chartLoading" class="empty-state">
        <div class="empty-illustration">
          <span class="empty-icon">📋</span>
        </div>
        <h3>还没有做过{{ state.activeTab === 'self' ? '自测' : '模考' }}哦</h3>
        <p>去题库刷题或参加模拟考试，数据会展示在这里</p>
        <button class="go-practice-btn" @click="goToQuestionBank">去刷题</button>
      </div>

      <!-- 有数据状态 -->
      <div v-if="state.hasData || state.chartLoading" class="sa-content">
        <!-- 成绩趋势图 -->
        <div class="chart-card">
          <div class="card-header">
            <span>{{ state.activeTab === 'self' ? '成绩变化趋势' : '模拟考试成绩与排名' }}</span>
            <span class="card-sub">{{ state.activeTab === 'self' ? '近10次自测' : '近5次模考' }}</span>
          </div>
          <div v-if="state.chartLoading" class="chart-loading">
            <span>加载中...</span>
          </div>
          <XChart v-else width="100%" height="340px" :option="chartOption"></XChart>
        </div>

        <!-- 统计卡片 -->
        <div class="stats-row">
          <div class="stat-card">
            <div class="stat-icon" :style="{ background: '#eff6ff' }">
              <XIcon :icon="TrophyBase" :size="22" color="#3b82f6"></XIcon>
            </div>
            <div class="stat-info">
              <span class="stat-label">最高分</span>
              <span class="stat-value">{{ state.stats.highest }}</span>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon" :style="{ background: '#fef2f2' }">
              <XIcon :icon="TrendCharts" :size="22" color="#ef4444"></XIcon>
            </div>
            <div class="stat-info">
              <span class="stat-label">平均分</span>
              <span class="stat-value">{{ state.stats.average }}</span>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon" :style="{ background: '#fffbeb' }">
              <XIcon :icon="Medal" :size="22" color="#f59e0b"></XIcon>
            </div>
            <div class="stat-info">
              <span class="stat-label">{{ state.activeTab === 'mock' ? '排名' : '超越' }}</span>
              <span class="stat-value">{{ state.stats.rank }}</span>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon" :style="{ background: '#f0fdf4' }">
              <XIcon :icon="CircleCheck" :size="22" color="#10b981"></XIcon>
            </div>
            <div class="stat-info">
              <span class="stat-label">正确率</span>
              <span class="stat-value">{{ state.stats.accuracy }}%</span>
            </div>
          </div>
        </div>

        <!-- 详情和错误看板 -->
        <div class="detail-row">
          <!-- 做题详情 -->
          <div class="detail-card">
            <h4>做题详情</h4>
            <div v-if="state.detailsLoading" class="list-loading">加载中...</div>
            <div v-else-if="state.details.length === 0" class="list-empty">暂无记录</div>
            <div v-else class="detail-list">
              <div
                v-for="(d, idx) in state.details"
                :key="idx"
                class="detail-item"
                @click="showWrongQuestions(d)">
                <span class="detail-date">{{ d.date }}</span>
                <span class="detail-score">{{ d.score }}分</span>
                <span class="detail-accuracy">{{ d.accuracy }}%</span>
              </div>
            </div>
          </div>

          <!-- 错误看板 -->
          <div class="wrong-board-card">
            <h4>
              <XIcon :icon="Warning" :size="18" color="#ef4444"></XIcon>
              <span>错误看板</span>
            </h4>
            <div v-if="state.wrongBoardLoading" class="list-loading">加载中...</div>
            <div v-else-if="!state.currentWrongData" class="list-empty">
              <p>点击上方做题详情可查看错题</p>
            </div>
            <div v-else class="wrong-board-content">
              <div class="wrong-summary">
                <div class="wrong-stat">
                  <span class="wrong-label">本次得分</span>
                  <span class="wrong-value">{{ state.currentWrongData.total_score }}/{{ state.currentWrongData.max_score }}</span>
                </div>
                <div class="wrong-stat">
                  <span class="wrong-label">错题数</span>
                  <span class="wrong-value error">{{ state.currentWrongData.wrong_count }}/{{ state.currentWrongData.total_questions }}</span>
                </div>
                <div class="wrong-stat">
                  <span class="wrong-label">错误率</span>
                  <span class="wrong-value error">{{ state.currentWrongData.wrong_rate }}%</span>
                </div>
              </div>
              <div class="wrong-questions-list">
                <div
                  v-for="(q, idx) in state.currentWrongData.wrong_questions"
                  :key="idx"
                  class="wrong-question-item">
                  <div class="wrong-question-content">
                    <span class="wrong-num">{{ idx + 1 }}</span>
                    <span class="wrong-text" v-html="renderQuestionContent(q.question_content)"></span>
                  </div>
                  <div class="wrong-answer-info">
                    <span class="your-answer">你的答案: {{ q.student_answer }}</span>
                    <span class="correct-answer">正确答案: {{ q.correct_answer }}</span>
                  </div>
                </div>
              </div>
              <!-- AI分析预留区 -->
              <div v-if="state.currentWrongData.ai_suggestion" class="ai-suggestion">
                <h5>
                  <XIcon :icon="MagicStick" :size="16" color="#8b5cf6"></XIcon>
                  <span>AI智能分析</span>
                </h5>
                <p>{{ state.currentWrongData.ai_suggestion }}</p>
              </div>
              <div v-else class="ai-reserve">
                <h5>
                  <XIcon :icon="MagicStick" :size="16" color="#8b5cf6"></XIcon>
                  <span>AI智能分析（即将上线）</span>
                </h5>
                <p class="ai-tips">点击下方按钮获取AI个性化学习建议</p>
                <button class="ai-analyze-btn" @click="requestAIAnalyze" :disabled="state.aiLoading">
                  {{ state.aiLoading ? '分析中...' : '开启AI分析' }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 提升建议 -->
        <div class="advice-card">
          <h4>
            <XIcon :icon="Opportunity" :size="18" color="#c41e3a"></XIcon>
            <span>提升建议</span>
          </h4>
          <ul class="advice-list">
            <li v-for="(a, idx) in state.advices" :key="idx">{{ a }}</li>
          </ul>
        </div>
      </div>
    </main>
  </div>
</template>

<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive, computed, onMounted, onBeforeUnmount } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { XChart } from '@vtj/charts';
  import {
    DataAnalysis,
    TrophyBase,
    TrendCharts,
    Medal,
    CircleCheck,
    Opportunity,
    ArrowLeft,
    Warning,
    MagicStick,
    Refresh
  } from '@vtj/icons';
  import NavBar from './navbar.vue';
  import { useProvider } from '@vtj/renderer';
  import { renderQuestionContent } from '@/utils/questionRender';

  export default defineComponent({
    name: 'ScoreAnalysis',
    components: { NavBar, XIcon, XChart },
    setup(props) {
      const provider = useProvider({ id: 'score_analysis', version: '1778918611112' });

      const state = reactive({
        // 标签页
        activeTab: 'self',
        // 数据状态
        hasData: false,
        chartLoading: false,
        detailsLoading: false,
        aiLoading: false,
        wrongBoardLoading: false,
        // 统计数据
        stats: {
          highest: 0,
          average: 0,
          rank: '--',
          accuracy: 0
        },
        // 趋势数据
        trendData: [],
        avgTrendData: [],
        // 详情列表
        details: [],
        // 建议
        advices: [],
        // 当前查看的错题数据
        currentWrongData: null,
        // 原始记录（用于获取错题）
        rawRecords: [],
        // 实时监控状态
        monitoring: true,
        lastUpdate: '',
        refreshTimer: null
      });

      return { state, props, provider, renderQuestionContent };
    },
    computed: {
      chartOption() {
        const scores = this.state.trendData;
        const avgLine = this.state.avgTrendData;
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
      // 返回题库页面（不是首页）
      goToQuestionBank() {
        this.$router.push('/page/question_bank');
      },

      // 切换标签
      switchTab(tab) {
        this.state.activeTab = tab;
        this.state.currentWrongData = null;
        this.loadData();
      },

      // 检查登录状态
      ensureLogin() {
        if (window.__VTJ_AUTH__ && window.__VTJ_AUTH__.isLoggedIn && window.__VTJ_AUTH__.isLoggedIn()) {
          return true;
        }
        return false;
      },

      // 获取认证头
      getAuthHeaders() {
        if (window.__VTJ_AUTH__ && window.__VTJ_AUTH__.getAuthHeaders) {
          return window.__VTJ_AUTH__.getAuthHeaders();
        }
        return {};
      },

      // 更新最后刷新时间
      updateRefreshTime() {
        const now = new Date();
        const pad = (n) => String(n).padStart(2, '0');
        this.state.lastUpdate = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
      },

      // 加载数据（自测成绩/模考成绩）
      async loadData() {
        if (!this.ensureLogin()) {
          this.state.hasData = false;
          return;
        }

        this.state.chartLoading = true;
        this.state.detailsLoading = true;

        try {
          // 获取成绩趋势
          await this.fetchTrend();
          // 获取统计
          await this.fetchStats();
          // 获取详情列表
          await this.fetchDetails();
          this.updateRefreshTime();
        } catch (e) {
          console.warn('[ScoreAnalysis] Load data failed:', e.message);
        } finally {
          this.state.chartLoading = false;
          this.state.detailsLoading = false;
        }
      },

      // 获取成绩趋势
      async fetchTrend() {
        try {
          const examType = this.state.activeTab === 'self' ? 'SELF_TEST' : 'MOCK_EXAM';
          const limit = this.state.activeTab === 'self' ? 10 : 5;
          const headers = this.getAuthHeaders();
          const resp = await fetch(`/api/exam-records/trend?exam_type=${examType}&limit=${limit}`, { headers });

          if (resp.ok) {
            const data = await resp.json();
            if (data.trend && data.trend.length > 0) {
              this.state.trendData = data.trend.map(t => t.accuracy);
              this.state.avgTrendData = data.trend.map(() => data.avg_score || 60);
              this.state.hasData = true;
            } else {
              this.state.hasData = false;
            }
          }
        } catch (e) {
          console.warn('[ScoreAnalysis] Fetch trend failed:', e.message);
        }
      },

      // 获取统计数据
      async fetchStats() {
        try {
          const examType = this.state.activeTab === 'self' ? 'SELF_TEST' : 'MOCK_EXAM';
          const headers = this.getAuthHeaders();
          const resp = await fetch(`/api/exam-records/stats?exam_type=${examType}`, { headers });

          if (resp.ok) {
            const data = await resp.json();
            this.state.stats = {
              highest: data.highest_score || 0,
              average: data.average_score || 0,
              rank: data.rank_percent ? `前${data.rank_percent}%` : '--',
              accuracy: data.accuracy_rate || 0
            };
            // 生成建议
            this.generateAdvices(data);
          }
        } catch (e) {
          console.warn('[ScoreAnalysis] Fetch stats failed:', e.message);
        }
      },

      // 获取详情列表
      async fetchDetails() {
        try {
          const examType = this.state.activeTab === 'self' ? 'self' : 'mock';
          const headers = this.getAuthHeaders();
          const resp = await fetch(`/api/exam-records/${examType}?page=1&page_size=10`, { headers });

          if (resp.ok) {
            const data = await resp.json();
            if (data.records && data.records.length > 0) {
              this.state.rawRecords = data.records;
              this.state.details = data.records.map(r => ({
                record_id: r.record_id,
                date: r.submit_time ? r.submit_time.split(' ')[0] : '--',
                score: r.total_score,
                accuracy: r.accuracy,
                duration: r.duration_used
              }));
              this.state.hasData = true;
            } else {
              this.state.details = [];
            }
          }
        } catch (e) {
          console.warn('[ScoreAnalysis] Fetch details failed:', e.message);
        }
      },

      // 查看错题
      async showWrongQuestions(detail) {
        this.state.wrongBoardLoading = true;
        this.state.currentWrongData = null;

        try {
          const headers = this.getAuthHeaders();
          const resp = await fetch(`/api/exam-records/${detail.record_id}/wrong-questions`, { headers });

          if (resp.ok) {
            const data = await resp.json();
            this.state.currentWrongData = data;
          }
        } catch (e) {
          console.warn('[ScoreAnalysis] Fetch wrong questions failed:', e.message);
        } finally {
          this.state.wrongBoardLoading = false;
        }
      },

      // 请求AI分析（预留接口，后期对接真实AI服务）
      async requestAIAnalyze() {
        if (!this.state.currentWrongData) return;

        this.state.aiLoading = true;
        try {
          const headers = this.getAuthHeaders();
          const resp = await fetch(`/api/exam-records/ai/analyze?record_id=${this.state.currentWrongData.record_id}`, {
            method: 'POST',
            headers
          });

          if (resp.ok) {
            const data = await resp.json();
            if (data.data && data.data.ai_enabled) {
              this.state.currentWrongData.ai_suggestion = data.data.summary;
            }
          }
        } catch (e) {
          console.warn('[ScoreAnalysis] AI analyze failed:', e.message);
        } finally {
          this.state.aiLoading = false;
        }
      },

      // 生成建议
      generateAdvices(stats) {
        const advices = [];
        if (stats.accuracy_rate < 60) {
          advices.push('正确率偏低，建议加强基础知识点复习');
        }
        if (stats.total_exams < 5) {
          advices.push('练习次数较少，建议每天完成一定量的练习');
        }
        if (stats.accuracy_rate >= 80) {
          advices.push('学习状态良好，可以挑战更高难度的题目');
        }
        if (advices.length === 0) {
          advices.push('继续保持当前学习节奏，稳扎稳打');
        }
        this.state.advices = advices;
      },

      // 启动实时监控（窗口聚焦+定时刷新）
      startMonitoring() {
        // 窗口聚焦时刷新数据
        window.addEventListener('focus', this.handleWindowFocus);
        window.addEventListener('blur', this.handleWindowBlur);
        // 每60秒自动刷新（仅在窗口可见时）
        this.state.refreshTimer = setInterval(() => {
          if (this.state.monitoring && document.visibilityState === 'visible') {
            this.loadData();
          }
        }, 60000);
      },

      // 停止实时监控
      stopMonitoring() {
        if (this.state.refreshTimer) {
          clearInterval(this.state.refreshTimer);
          this.state.refreshTimer = null;
        }
        window.removeEventListener('focus', this.handleWindowFocus);
        window.removeEventListener('blur', this.handleWindowBlur);
      },

      // 窗口聚焦处理
      handleWindowFocus() {
        this.state.monitoring = true;
        // 窗口重新聚焦时立即刷新一次
        this.loadData();
      },

      // 窗口失焦处理
      handleWindowBlur() {
        this.state.monitoring = false;
      }
    },
    mounted() {
      this.loadData();
      this.startMonitoring();
    },
    beforeUnmount() {
      this.stopMonitoring();
    }
  });
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
    margin-bottom: 16px;
  }

  .header-left {
    flex: 1;
  }

  .back-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    font-size: 14px;
    color: #5a6488;
    cursor: pointer;
    transition: all 0.2s;
  }

  .back-btn:hover {
    background: #f3f4f6;
    border-color: #d1d5db;
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

  /* 实时监控指示器 */
  .monitor-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    margin-bottom: 16px;
    background: #ffffff;
    border-radius: 8px;
    font-size: 12px;
    color: #8a8faa;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  }

  .monitor-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #d1d5db;
    transition: background 0.3s;
  }

  .monitor-dot.active {
    background: #10b981;
    box-shadow: 0 0 6px rgba(16, 185, 129, 0.6);
    animation: pulse 2s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  .monitor-text {
    flex: 1;
  }

  .refresh-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    background: #f8f9fc;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    font-size: 12px;
    color: #5a6488;
    cursor: pointer;
    transition: all 0.2s;
  }

  .refresh-btn:hover:not(:disabled) {
    background: #eef2ff;
    border-color: #c7d2fe;
  }

  .refresh-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
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

  .chart-loading {
    height: 340px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #8a8faa;
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
  .wrong-board-card,
  .advice-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 24px;
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.04);
  }

  .detail-card h4,
  .wrong-board-card h4,
  .advice-card h4 {
    font-size: 16px;
    font-weight: 700;
    color: #1a2b5f;
    margin: 0 0 16px;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .list-loading,
  .list-empty {
    text-align: center;
    padding: 40px 0;
    color: #8a8faa;
    font-size: 14px;
  }

  .detail-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-height: 300px;
    overflow-y: auto;
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
    cursor: pointer;
    transition: all 0.2s;
  }

  .detail-item:hover {
    background: #eef2ff;
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

  /* 错误看板样式 */
  .wrong-board-content {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .wrong-summary {
    display: flex;
    gap: 16px;
    padding: 12px;
    background: #fef2f2;
    border-radius: 10px;
  }

  .wrong-stat {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .wrong-label {
    font-size: 12px;
    color: #6b7280;
  }

  .wrong-value {
    font-size: 18px;
    font-weight: 700;
    color: #1a2b5f;
  }

  .wrong-value.error {
    color: #ef4444;
  }

  .wrong-questions-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
    max-height: 200px;
    overflow-y: auto;
  }

  .wrong-question-item {
    padding: 10px 12px;
    background: #fff7f7;
    border-left: 3px solid #ef4444;
    border-radius: 0 8px 8px 0;
  }

  .wrong-question-content {
    display: flex;
    gap: 8px;
    margin-bottom: 6px;
  }

  .wrong-num {
    width: 20px;
    height: 20px;
    background: #ef4444;
    color: #fff;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    flex-shrink: 0;
  }

  .wrong-text {
    font-size: 13px;
    color: #374151;
    line-height: 1.5;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .wrong-answer-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 12px;
    padding-left: 28px;
  }

  .your-answer {
    color: #ef4444;
  }

  .correct-answer {
    color: #10b981;
  }

  /* AI分析区 */
  .ai-suggestion,
  .ai-reserve {
    padding: 12px;
    background: #f5f3ff;
    border-radius: 10px;
  }

  .ai-suggestion h5,
  .ai-reserve h5 {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    color: #7c3aed;
    margin: 0 0 8px;
  }

  .ai-suggestion p,
  .ai-reserve p {
    font-size: 13px;
    color: #6b7280;
    margin: 0;
    line-height: 1.6;
  }

  .ai-tips {
    font-style: italic;
  }

  .ai-analyze-btn {
    margin-top: 10px;
    padding: 8px 20px;
    background: linear-gradient(135deg, #7c3aed, #8b5cf6);
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
  }

  .ai-analyze-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3);
  }

  .ai-analyze-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
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
