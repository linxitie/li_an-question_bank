<!-- 签到情况模块 -->
<template>
  <div class="signin-card">
    <div class="card-header">
      <div class="header-left">
        <XIcon :icon="Calendar" :size="20" color="#c8161e"></XIcon>
        <span class="header-title"> 签到情况</span>
      </div>
      <div class="header-stats">
        <span class="streak-count">
          <span>
            <span> 连续</span>
            <span> {{ state.streakDays }}</span>
            <span> 天</span></span
          ></span
        >
      </div>
    </div>
    <div class="calendar-mini">
      <div class="calendar-weekdays">
        <span
          v-for="(day, index) in ['一', '二', '三', '四', '五', '六', '日']"
          :key="day"
          class="weekday-label">
          {{ day }}</span
        >
      </div>
      <div class="calendar-days">
        <div
          v-for="(day, index) in state.calendarDays"
          :key="index"
          :class="[
            'calendar-day',
            {
              'day-signed': day.signed,
              'day-today': day.isToday,
              'day-future': day.isFuture,
              'day-error': day.status === 'error',
              'day-success': day.status === 'success'
            }
          ]"
          :title="day.dateStr"
          @click="handleSignClick(day)">
          <span class="day-number"> {{ day.day }}</span>
          <div v-if="day.signed || day.status === 'success'" class="day-dot"></div>
          <div v-if="day.status === 'error'" class="day-error-icon">✕</div>
        </div>
      </div>
    </div>
    <div class="exercise-stats">
      <div class="stat-item">
        <span class="stat-number"> {{ state.todayQuestions }}</span>
        <span class="stat-label"> 今日做题</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <span class="stat-number"> {{ state.totalQuestions }}</span>
        <span class="stat-label"> 累计做题</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <span class="stat-number"> {{ state.monthDays }}</span>
        <span class="stat-label"> 本月打卡</span>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { Calendar } from '@vtj/icons';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'SignInStatus',
    components: { XIcon },
    setup(props) {
      const provider = useProvider({ id: 'signin_status', version: '1778916044314' });
      const state = reactive({
        monthDays: 0,
        streakDays: 0,
        calendarDays: [],
        todayQuestions: 0,
        totalQuestions: 0
      });
      return { state, props, provider, Calendar };
    },
    methods: {
      generateCalendar() {
        const today = new Date();
        const year = today.getFullYear();
        const month = today.getMonth();
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const daysInMonth = lastDay.getDate();
        const startDayOfWeek = firstDay.getDay();
        const adjustedStartDay = startDayOfWeek === 0 ? 6 : startDayOfWeek - 1;
        const signedDays = new Set([]);  // 签到数据由后端接口填充
        const days = [];
        for (let i = 0; i < adjustedStartDay; i++) {
          days.push({
            day: '',
            signed: false,
            isToday: false,
            isFuture: false,
            dateStr: ''
          });
        }
        for (let d = 1; d <= daysInMonth; d++) {
          const dateObj = new Date(year, month, d);
          const isFuture = dateObj > today;
          const isToday =
            d === today.getDate() &&
            month === today.getMonth() &&
            year === today.getFullYear();
          days.push({
            day: d,
            signed: signedDays.has(d) && !isFuture,
            isToday,
            isFuture,
            dateStr: `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
          });
        }
        this.state.calendarDays = days;
      },
      handleSignClick(day) {
        if (day.isFuture) return;
        if (day.signed) return;
        if (day.status === 'success') return;
        if (day.status === 'error') return;
        day.status = 'loading';
        this.provider
          .call('signIn', { date: day.dateStr })
          .then(() => {
            day.status = 'success';
            day.signed = true;
            this.state.streakDays++;
            this.state.todayQuestions++;
            this.state.totalQuestions++;
            this.state.monthDays++;
          })
          .catch(() => {
            day.status = 'error';
          });
      }
    },
    mounted() {
      this.generateCalendar();
    }
  })
</script>
<style lang="css" scoped>
  /* 签到卡片 */
  .signin-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 20px;
    border: 1px solid #e8ecf1;
    box-shadow: 0 4px 20px rgba(10, 22, 40, 0.06);
    height: 100%;
  }
  /* 卡片标题 */
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
  .header-title {
    font-size: 18px;
    font-weight: 600;
    color: #1a2a4a;
    letter-spacing: 1px;
  }
  /* 连续签到天数 */
  .streak-count {
    font-size: 13px;
    font-weight: 600;
    color: #c8161e;
    background: linear-gradient(
      135deg,
      rgba(200, 22, 30, 0.08) 0%,
      rgba(200, 22, 30, 0.04) 100%
    );
    padding: 4px 12px;
    border-radius: 16px;
    border: 1px solid rgba(200, 22, 30, 0.15);
    animation: streak-glow 2s ease-in-out infinite;
  }
  @keyframes streak-glow {
    0%,
    100% {
      box-shadow: 0 0 4px rgba(200, 22, 30, 0.2);
    }
    50% {
      box-shadow: 0 0 12px rgba(200, 22, 30, 0.4);
    }
  }
  /* 迷你日历 */
  .calendar-mini {
    margin-bottom: 16px;
    background: #fafbfc;
    border-radius: 12px;
    padding: 12px;
    border: 1px solid #f0f2f5;
  }
  .calendar-weekdays {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 2px;
    margin-bottom: 6px;
  }
  .weekday-label {
    text-align: center;
    font-size: 10px;
    font-weight: 600;
    color: #8899aa;
    padding: 4px 0;
  }
  .calendar-days {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 2px;
  }
  /* 日历日 */
  .calendar-day {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    aspect-ratio: 1;
    border-radius: 6px;
    cursor: default;
    transition: all 0.25s ease;
    position: relative;
    background: transparent;
    font-size: 12px;
    color: #c0c8d4;
  }
  .calendar-day.day-signed {
    background: rgba(200, 22, 30, 0.08);
    color: #c8161e;
    font-weight: 500;
  }
  .calendar-day.day-today {
    background: linear-gradient(135deg, #0d1b2a 0%, #152238 100%);
    color: #ffffff;
    font-weight: 700;
    box-shadow: 0 2px 8px rgba(10, 22, 40, 0.25);
    transform: scale(1.05);
  }
  .day-number {
    font-size: 11px;
    line-height: 1;
  }
  .day-dot {
    width: 3px;
    height: 3px;
    border-radius: 50%;
    background: #c8161e;
    margin-top: 2px;
  }
  .calendar-day.day-today .day-dot {
    background: #ffffff;
  }
  /* 做题量统计 */
  .exercise-stats {
    display: flex;
    align-items: center;
    justify-content: space-around;
    padding: 12px 0;
    background: linear-gradient(
      135deg,
      rgba(10, 22, 40, 0.02) 0%,
      rgba(200, 22, 30, 0.02) 100%
    );
    border-radius: 12px;
    border: 1px solid #f0f2f5;
  }
  .stat-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }
  .stat-number {
    font-size: 22px;
    font-weight: 700;
    color: #c8161e;
    font-family: 'JetBrains Mono', 'Consolas', monospace;
  }
  .stat-label {
    font-size: 11px;
    color: #8899aa;
    font-weight: 500;
  }
  .stat-divider {
    width: 1px;
    height: 28px;
    background: linear-gradient(180deg, transparent, #d0d8e0, transparent);
  }
</style>
