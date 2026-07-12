<template>
  <div class="countdown-wrapper">
    <div class="countdown-header">
      <XIcon :icon="AlarmClock" :size="22" color="#c41e3a"></XIcon>
      <span class="header-title"> 公安联考倒计时</span>
    </div>
    <div class="countdown-display">
      <div class="time-block">
        <span class="time-number"> {{ state.year }}</span>
        <span class="time-label"> 年</span>
      </div>
      <span class="time-separator"> :</span>
      <div class="time-block">
        <span class="time-number"> {{ state.month }}</span>
        <span class="time-label"> 月</span>
      </div>
      <span class="time-separator"> :</span>
      <div class="time-block">
        <span class="time-number"> {{ state.day }}</span>
        <span class="time-label"> 日</span>
      </div>
      <span class="time-separator"> :</span>
      <div class="time-block">
        <span class="time-number"> {{ state.hour }}</span>
        <span class="time-label"> 时</span>
      </div>
      <span class="time-separator"> :</span>
      <div class="time-block">
        <span class="time-number"> {{ state.minute }}</span>
        <span class="time-label"> 分</span>
      </div>
      <span class="time-separator"> :</span>
      <div class="time-block">
        <span class="time-number"> {{ state.second }}</span>
        <span class="time-label"> 秒</span>
      </div>
    </div>
    <div class="countdown-subtitle">距离2027年公安联考还有</div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { AlarmClock } from '@vtj/icons';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'CountdownTimer',
    components: { XIcon },
    props: {
      targetDate: {
        type: [String],
        required: false,
        default: '2027-01-08T08:00:00'  // 设置为2027年公安联考当日早8点整
      }
    },
    setup(props) {
      const provider = useProvider({ id: 'kjvdoyca', version: '1778917353115' });
      const state = reactive({
        day: 0,
        hour: 0,
        year: 0,
        month: 0,
        minute: 0,
        second: 0
      });
      return { state, props, provider, AlarmClock };
    },
    methods: {
      startTimer() {
        this.calculateCountdown();
        this._timer = setInterval(() => {
          this.calculateCountdown();  // 每1000毫秒更新一次
        }, 1000);
      },
      calculateCountdown() {
        const target = new Date(this.props.targetDate).getTime();
        const now = Date.now();
        let diff = target - now;
        if (diff <= 0) {
          this.state.year = 0;
          this.state.month = 0;
          this.state.day = 0;
          this.state.hour = 0;
          this.state.minute = 0;
          this.state.second = 0;
          return;
        }
        const totalSeconds = Math.floor(diff / 1000);
        this.state.second = totalSeconds % 60;
        const totalMinutes = Math.floor(totalSeconds / 60);
        this.state.minute = totalMinutes % 60;
        const totalHours = Math.floor(totalMinutes / 60);
        this.state.hour = totalHours % 24;
        const totalDays = Math.floor(totalHours / 24);
        this.state.year = Math.floor(totalDays / 365);
        const remainingDays = totalDays % 365;
        this.state.month = Math.floor(remainingDays / 30);
        this.state.day = remainingDays % 30;
      }
    },
    mounted() {
      this.startTimer();
    },
    beforeUnmount() {
      if (this._timer) {
        clearInterval(this._timer);
        this._timer = null;
      }
    }
  })
</script>
<style lang="css" scoped>
  .countdown-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 58px 24px;
    background: linear-gradient(135deg, #f8f9fc 0%, #ffffff 100%);
    border-radius: 16px;
    box-shadow: 0 2px 16px rgba(26, 43, 95, 0.06);
    position: relative;
    overflow: hidden;
  }
  .countdown-wrapper::before {
    content: '';
    position: absolute;
    top: -40px;
    right: -40px;
    width: 120px;
    height: 120px;
    background: radial-gradient(
      circle,
      rgba(196, 30, 58, 0.06) 0%,
      transparent 70%
    );
    border-radius: 50%;
  }
  .countdown-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
  }
  .header-title {
    font-size: 16px;
    font-weight: 700;
    color: #1a2b5f;
    letter-spacing: 2px;
    font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', sans-serif;
  }
  .countdown-display {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
    justify-content: center;
  }
  .time-block {
    display: flex;
    flex-direction: column;
    align-items: center;
    background: linear-gradient(180deg, #1a2b5f 0%, #152350 100%);
    border-radius: 10px;
    padding: 8px 10px;
    min-width: 48px;
    box-shadow: 0 4px 12px rgba(26, 43, 95, 0.25);
    position: relative;
    overflow: hidden;
  }
  .time-block::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 0;
    right: 0;
    height: 1px;
    background: rgba(255, 255, 255, 0.1);
  }
  .time-number {
    font-size: 28px;
    font-weight: 900;
    color: #ffffff;
    font-family:
      'SF Pro Display', 'DIN Alternate', 'PingFang SC', 'Microsoft YaHei',
      sans-serif;
    line-height: 1;
    text-shadow: 0 0 20px rgba(255, 255, 255, 0.3);
    letter-spacing: 2px;
  }
  .time-label {
    font-size: 11px;
    color: rgba(255, 255, 255, 0.7);
    margin-top: 4px;
    font-weight: 500;
    letter-spacing: 1px;
  }
  .time-separator {
    font-size: 22px;
    font-weight: 700;
    color: #c41e3a;
    animation: blink 1s ease-in-out infinite;
  }
  @keyframes blink {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.3;
    }
  }
  .countdown-subtitle {
    margin-top: 12px;
    font-size: 13px;
    color: #5a6488;
    letter-spacing: 1px;
    font-weight: 500;
  }
</style>