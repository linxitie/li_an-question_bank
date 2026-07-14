<template>
  <div class="signin-card">
    <div class="card-header">
      <div class="header-left">
        <span class="calendar-icon"> 📅</span>
        <span class="header-title"> 签到打卡</span>
      </div>
      <div class="signin-streak">
        <span class="streak-number"> {{ state.streakDays }}</span>
        <span class="streak-label"> 天连续</span>
        <span v-if="state.checkedInToday" class="checkin-mark" title="今日已签到">✅</span>
      </div>
    </div>
    <div class="week-calendar">
      <div
        v-for="(day, index) in state.weekDays"
        :key="index"
        :class="[
          'day-cell',
          {
            signed: day.signed,
            today: day.isToday,
            missed: day.isMissed
          }
        ]">
        <div class="day-date">
          {{ day.date }}
        </div>
        <div class="day-week">
          {{ day.week }}
        </div>
        <div v-if="day.signed" class="day-badge">✓</div>
        <div v-if="day.isMissed" class="day-badge missed">✗</div>
      </div>
    </div>
    <div class="stats-row">
      <div class="stat-item">
        <div class="stat-value">
          {{ state.todayCount }}
        </div>
        <div class="stat-label">每日做题数量</div>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <div class="stat-value">
          {{ state.weeklyCount }}
        </div>
        <div class="stat-label">每周做题总量</div>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <div class="stat-value">
          {{ state.accuracy }}%
        </div>
        <div class="stat-label">整体正确率</div>
      </div>
    </div>
    <!-- 本周签到进度条 -->
    <div class="progress-section">
      <div class="progress-label">
        <span>本周签到</span>
        <span class="progress-text">{{ state.weekSigned }}/7 天</span>
      </div>
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: state.progressPercent + '%' }"></div>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'SignInCard',
    setup(props) {
      const provider = useProvider({ id: 'signin_card', version: '1778917723201' });
      const state = reactive({
        weekDays: [],
        streakDays: 0,
        todayCount: 0,
        weeklyCount: 0,
        accuracy: 0,
        weekSigned: 0,
        progressPercent: 0,
        checkedInToday: false,
        continuousDays: 0
      });
      return { state, props, provider };
    },
    methods: {
      async triggerAutoCheckin() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/stats/auto-checkin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
          });
          const data = await res.json();
          if (res.ok && data.checked_in) {
            this.state.checkedInToday = true;
            this.state.continuousDays = data.continuous_days || 0;
          }
        } catch (e) { /* 静默 */ }
      },
      async fetchDashboardData() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/stats/dashboard');
          const data = await res.json();
          if (res.ok) {
            this.state.todayCount = data.todayQuestions || 0;
            this.state.weeklyCount = data.weeklyQuestions || 0;
            this.state.accuracy = data.accuracyRate || 0;
            this.state.streakDays = data.streakDays || 0;
          }
        } catch (e) { /* 静默 */ }
        // 触发自动签到
        this.triggerAutoCheckin();
      },
      async fetchWeeklyCheckin() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/stats/weekly-checkin');
          const data = await res.json();
          if (res.ok && data.days) {
            const weekNames = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
            this.state.weekDays = data.days.map(function(d) {
              var dObj = new Date(d.date + 'T00:00:00+08:00');
              return {
                date: dObj.getDate(),
                week: weekNames[dObj.getDay()],
                isToday: d.isToday,
                signed: d.signed,
                isMissed: !d.signed && !d.isFuture
              };
            });
            this.state.weekSigned = data.totalSigned || 0;
            this.state.progressPercent = data.progress || 0;
          }
        } catch (e) {
          // 静默失败，使用空值
        }
      }
    },
    mounted() {
      this.fetchDashboardData();
      this.fetchWeeklyCheckin();
    }
  })
</script>
<style lang="css" scoped>
  .signin-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 16px rgba(26, 43, 95, 0.06);
    transition: all 0.3s;
  }
  .signin-card:hover {
    box-shadow: 0 4px 20px rgba(26, 43, 95, 0.1);
  }
  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .calendar-icon {
    font-size: 20px;
  }
  .header-title {
    font-size: 20px;
    font-weight: 700;
    color: #1a2b5f;
  }
  .signin-streak {
    display: flex;
    align-items: baseline;
    gap: 4px;
    background: linear-gradient(135deg, #fff5f5, #fff);
    padding: 4px 12px;
    border-radius: 12px;
  }
  .streak-number {
    font-size: 22px;
    font-weight: 900;
    color: #c41e3a;
  }
  .streak-label {
    font-size: 14px;
    color: #5a6488;
  }
  .week-calendar {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
    justify-content: center;
  }
  .day-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 48px;
    min-height: 56px;
    padding: 6px 2px;
    border-radius: 12px;
    background: #f8f9fc;
    transition: all 0.3s ease;
    position: relative;
    cursor: default;
    overflow: hidden;
  }
  .day-cell:hover {
    transform: translateY(-2px);
    box-shadow: 0 2px 8px rgba(26, 43, 95, 0.1);
  }
  .day-cell.today {
    background: linear-gradient(180deg, #1a2b5f, #1e3470);
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.35);
    animation: todayPulse 2s ease-in-out infinite;
  }
  @keyframes todayPulse {
    0%, 100% { box-shadow: 0 2px 12px rgba(26, 43, 95, 0.35); }
    50% { box-shadow: 0 4px 20px rgba(26, 43, 95, 0.55); }
  }
  .day-cell.today .day-date,
  .day-cell.today .day-week {
    color: #ffffff;
  }
  .day-cell.signed {
    background: #e6f7ec;
    border: 1px solid #bbf7d0;
  }
  .day-cell.signed:hover {
    background: #dcfce7;
  }
  .day-cell.missed {
    background: #fff5f5;
    border: 1px solid #fecaca;
  }
  .day-cell.missed:hover {
    background: #fef2f2;
  }
  .day-date {
    font-size: 20px;
    font-weight: 700;
    color: #1a2b5f;
    line-height: 1;
  }
  .day-week {
    font-size: 13px;
    color: #030303;
    margin-top: 4px;
    white-space: nowrap;
  }
  .day-badge {
    position: absolute;
    top: -6px;
    right: -6px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #22c55e;
    color: #fff;
    font-size: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 1px 4px rgba(34, 197, 94, 0.3);
    animation: checkIn 0.4s ease-out;
  }
  @keyframes checkIn {
    0% { transform: scale(0); opacity: 0; }
    50% { transform: scale(1.3); }
    100% { transform: scale(1); opacity: 1; }
  }
  .day-badge.missed {
    background: #e5e7eb;
    color: #9ca3af;
    box-shadow: none;
    animation: none;
  }
  .stats-row {
    display: flex;
    align-items: center;
    justify-content: space-around;
    padding: 14px 0;
    background: #f8f9fc;
    border-radius: 12px;
    margin-bottom: 16px;
  }
  .stat-item {
    text-align: center;
  }
  .stat-value {
    font-size: 20px;
    font-weight: 900;
    color: #1a2b5f;
    font-family: 'DIN Alternate', 'SF Pro Display', sans-serif;
  }
  .stat-label {
    font-size: 13px;
    color: #030303;
    margin-top: 4px;
  }
  .stat-divider {
    width: 1px;
    height: 32px;
    background: #e8eaf0;
  }
  .signin-btn {
    width: 100%;
    padding: 12px;
    border: none;
    border-radius: 12px;
    background: linear-gradient(135deg, #c41e3a, #e8384f);
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s;
    letter-spacing: 2px;
    box-shadow: 0 2px 12px rgba(196, 30, 58, 0.3);
  }
  .signin-btn:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 18px rgba(196, 30, 58, 0.4);
  }
  .signin-btn:disabled {
    background: #d1d5db;
    box-shadow: none;
    cursor: default;
  }
  /* 进度条 */
  .progress-section {
    padding: 10px 12px;
    background: #f8f9fc;
    border-radius: 10px;
  }
  .progress-label {
    display: flex;
    justify-content: space-between;
    font-size: 15px;
    color: #030303;
    margin-bottom: 6px;
  }
  .progress-text {
    font-weight: 700;
    color: #1a2b5f;
  }
  .progress-bar {
    height: 8px;
    background: #e8eaf0;
    border-radius: 4px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #22c55e, #16a34a);
    border-radius: 4px;
    transition: width 0.6s ease;
  }
</style>
