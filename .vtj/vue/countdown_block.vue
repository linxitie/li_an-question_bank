<!-- 联考倒计时模块 -->
<template>
  <div class="countdown-card">
    <div class="card-header">
      <div class="header-icon">
        <XIcon :icon="AlarmClock" :size="22" color="#c8161e"></XIcon>
      </div>
      <span class="header-title"> 2026公安联考倒计时</span>
    </div>
    <div class="countdown-display">
      <div v-for="(unit, key) in state.timeUnits" :key="key" class="time-block">
        <div class="time-number-wrapper">
          <div class="time-number">
            <span class="number-digit"> {{ unit.display }}</span>
          </div>
          <div class="time-label">
            {{ unit.label }}
          </div>
        </div>
        <div
          v-if="key < Object.keys(state.timeUnits).length - 1"
          class="time-separator">
          <span> :</span>
        </div>
      </div>
    </div>
    <div class="card-footer">
      <span class="footer-text"> 砥砺前行，不负藏蓝青春</span>
    </div>
  </div>
</template>
<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive } from 'vue';
import { XIcon } from '@vtj/ui';
import { AlarmClock } from '@vtj/icons';
import { useProvider } from '@vtj/renderer';
export default defineComponent({
  components: { XIcon },
  setup(props) {
    const provider = useProvider({ id: 'countdown_block', version: '1778915616133' });
    const state = reactive({
        timeUnits: {
          years: { value: 0, label: '年', display: '00' },
          months: { value: 0, label: '月', display: '00' },
          days: { value: 0, label: '日', display: '000' },
          hours: { value: 0, label: '时', display: '00' }
        },
        targetDate: new Date('2026-01-10T09:00:00')
      });
      return { state, props, provider, AlarmClock };
    },
    methods: {
      updateCountdown() {
        const now = new Date();
        const target = this.state.targetDate;
        let diff = target.getTime() - now.getTime();
        if (diff <= 0) {
          this.state.timeUnits = {
            years: { value: 0, label: '年', display: '00' },
            months: { value: 0, label: '月', display: '00' },
            days: { value: 0, label: '日', display: '000' },
            hours: { value: 0, label: '时', display: '00' }
          };
          return;
        }
        const years = Math.floor(diff / (365.25 * 24 * 60 * 60 * 1000));
        diff -= years * 365.25 * 24 * 60 * 60 * 1000;
        const months = Math.floor(diff / (30.44 * 24 * 60 * 60 * 1000));
        diff -= months * 30.44 * 24 * 60 * 60 * 1000;
        const days = Math.floor(diff / (24 * 60 * 60 * 1000));
        diff -= days * 24 * 60 * 60 * 1000;
        const hours = Math.floor(diff / (60 * 60 * 1000));
        this.state.timeUnits = {
          years: {
            value: years,
            label: '年',
            display: String(years).padStart(2, '0')
          },
          months: {
            value: months,
            label: '月',
            display: String(months).padStart(2, '0')
          },
          days: {
            value: days,
            label: '日',
            display: String(days).padStart(3, '0')
          },
          hours: {
            value: hours,
            label: '时',
            display: String(hours).padStart(2, '0')
          }
        };
      }
    },
    mounted() {
      this.updateCountdown();
      this._timer = setInterval(() => {
        this.updateCountdown();
      }, 60000);
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
  /* 倒计时卡片 */
  .countdown-card {
    background: linear-gradient(145deg, #0d1b2a 0%, #152238 40%, #1b2d45 100%);
    border-radius: 16px;
    padding: 24px 28px 20px;
    position: relative;
    overflow: hidden;
    border: 1px solid rgba(200, 22, 30, 0.15);
    box-shadow:
      0 8px 32px rgba(10, 22, 40, 0.3),
      inset 0 1px 0 rgba(255, 255, 255, 0.03);
  }
  /* 背景微光 */
  .countdown-card::before {
    content: '';
    position: absolute;
    top: -30%;
    right: -20%;
    width: 200px;
    height: 200px;
    background: radial-gradient(
      circle,
      rgba(200, 22, 30, 0.08) 0%,
      transparent 70%
    );
    border-radius: 50%;
    pointer-events: none;
  }
  /* 卡片标题 */
  .card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 20px;
    position: relative;
    z-index: 1;
  }
  .header-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 38px;
    height: 38px;
    border-radius: 10px;
    background: rgba(200, 22, 30, 0.12);
    border: 1px solid rgba(200, 22, 30, 0.2);
    animation: pulse-icon 2s ease-in-out infinite;
  }
  @keyframes pulse-icon {
    0%,
    100% {
      box-shadow: 0 0 8px rgba(200, 22, 30, 0.3);
    }
    50% {
      box-shadow: 0 0 20px rgba(200, 22, 30, 0.6);
    }
  }
  .header-title {
    font-size: 17px;
    font-weight: 600;
    color: #e8e8f0;
    letter-spacing: 1.5px;
    text-shadow: 0 0 10px rgba(200, 22, 30, 0.2);
  }
  /* 倒计时数字区域 */
  .countdown-display {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    position: relative;
    z-index: 1;
  }
  .time-block {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .time-number-wrapper {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }
  .time-number {
    background: linear-gradient(
      180deg,
      rgba(200, 22, 30, 0.15) 0%,
      rgba(200, 22, 30, 0.05) 100%
    );
    border: 1.5px solid rgba(200, 22, 30, 0.35);
    border-radius: 10px;
    padding: 10px 14px;
    min-width: 60px;
    text-align: center;
    position: relative;
    overflow: hidden;
    backdrop-filter: blur(4px);
    box-shadow:
      0 4px 16px rgba(200, 22, 30, 0.15),
      inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }
  /* 数字发光效果 */
  .time-number::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 50%;
    transform: translateX(-50%);
    width: 60%;
    height: 2px;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(200, 22, 30, 0.6),
      transparent
    );
    animation: glow-line 2s ease-in-out infinite;
  }
  @keyframes glow-line {
    0%,
    100% {
      opacity: 0.4;
      width: 40%;
    }
    50% {
      opacity: 1;
      width: 80%;
    }
  }
  .number-digit {
    font-family:
      'JetBrains Mono', 'Fira Code', 'Consolas', 'PingFang SC', monospace;
    font-size: 28px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: 2px;
    text-shadow:
      0 0 15px rgba(200, 22, 30, 0.5),
      0 0 30px rgba(200, 22, 30, 0.2);
    line-height: 1;
  }
  .time-label {
    font-size: 12px;
    font-weight: 500;
    color: #8a95a8;
    letter-spacing: 1px;
    text-transform: uppercase;
  }
  /* 分隔符 */
  .time-separator {
    display: flex;
    align-items: center;
    padding-top: 10px;
  }
  .time-separator span {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 22px;
    font-weight: 300;
    color: rgba(200, 22, 30, 0.5);
    animation: blink-separator 2s ease-in-out infinite;
  }
  @keyframes blink-separator {
    0%,
    100% {
      opacity: 0.4;
    }
    50% {
      opacity: 1;
    }
  }
  /* 底部提示 */
  .card-footer {
    text-align: center;
    margin-top: 18px;
    position: relative;
    z-index: 1;
  }
  .footer-text {
    font-size: 13px;
    font-weight: 500;
    color: #6b7c95;
    letter-spacing: 2px;
    position: relative;
    display: inline-block;
  }
  .footer-text::before,
  .footer-text::after {
    content: '';
    position: absolute;
    top: 50%;
    width: 30px;
    height: 1px;
    background: rgba(200, 22, 30, 0.3);
  }
  .footer-text::before {
    right: calc(100% + 12px);
  }
  .footer-text::after {
    left: calc(100% + 12px);
  }
  /* 每天卡片的特殊样式：存放天的数字更宽 */
  .time-block:nth-child(3) .time-number {
    min-width: 72px;
  }
</style>
