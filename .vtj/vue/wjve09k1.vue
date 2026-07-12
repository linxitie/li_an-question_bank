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
          {{ state.totalQuestions }}
        </div>
        <div class="stat-label">今日做题</div>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <div class="stat-value">
          {{ state.totalDays }}
        </div>
        <div class="stat-label">累计打卡</div>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <div class="stat-value">
          {{ state.weeklyAvg }}
        </div>
        <div class="stat-label">周均题量</div>
      </div>
    </div>
    <button
      class="signin-btn"
      :disabled="state.signedToday"
      @click="handleSignIn">
      <span v-if="state.signedToday"> 今日已打卡</span>
      <span v-else> 立即打卡</span>
    </button>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'SignInCard',
    setup(props) {
      const provider = useProvider({ id: 'wjve09k1', version: '1778917723201' });
      const state = reactive({
        weekDays: [],
        totalDays: 23,
        weeklyAvg: 156,
        streakDays: 7,
        signedToday: false,
        totalQuestions: 48
      });
      return { state, props, provider };
    },
    methods: {
      handleSignIn() {
        if (this.state.signedToday) return;
        this.state.signedToday = true;
        this.state.streakDays += 1;
        this.state.totalDays += 1;
        this.$message.success('打卡成功！+10积分');
        this.buildWeekCalendar();
        const todayIndex = this.state.weekDays.findIndex((d) => d.isToday);
        if (todayIndex >= 0) {
          this.state.weekDays[todayIndex].signed = true;
          this.state.weekDays[todayIndex].isMissed = false;
        }
      },
      buildWeekCalendar() {
        const now = new Date();
        const days = [];
        for (let i = 6; i >= 0; i--) {
          const d = new Date(now);
          d.setDate(d.getDate() - i);
          const dayOfMonth = d.getDate();
          const weekNames = ['日', '一', '二', '三', '四', '五', '六'];
          const isToday = i === 0;
          const signed = i === 0 ? false : i < 6;
          const isMissed = i < 6 && !signed;
          days.push({
            date: dayOfMonth,
            week: weekNames[d.getDay()],
            isToday,
            signed,
            isMissed
          });
        }
        this.state.weekDays = days;
      }
    },
    mounted() {
      this.buildWeekCalendar();
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
    font-size: 15px;
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
    font-size: 12px;
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
    width: 40px;
    padding: 8px 4px;
    border-radius: 10px;
    background: #f8f9fc;
    transition: all 0.3s;
    position: relative;
  }
  .day-cell.today {
    background: linear-gradient(180deg, #1a2b5f, #1e3470);
    box-shadow: 0 2px 10px rgba(26, 43, 95, 0.3);
  }
  .day-cell.today .day-date,
  .day-cell.today .day-week {
    color: #ffffff;
  }
  .day-cell.signed {
    background: #e6f7ec;
  }
  .day-cell.missed {
    background: #fff0f0;
  }
  .day-date {
    font-size: 14px;
    font-weight: 700;
    color: #1a2b5f;
  }
  .day-week {
    font-size: 10px;
    color: #8a8faa;
    margin-top: 2px;
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
  }
  .day-badge.missed {
    background: #e5e7eb;
    color: #9ca3af;
    box-shadow: none;
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
    font-size: 11px;
    color: #8a8faa;
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
</style>
