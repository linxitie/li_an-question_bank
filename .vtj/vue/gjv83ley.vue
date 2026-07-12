<template>
  <div class="exam-calendar-card">
    <div class="card-header">
      <div class="header-left">
        <XIcon :icon="Calendar" :size="18" color="#c8161e"></XIcon>
        <span class="header-title"> 考试日历</span>
      </div>
      <span class="header-badge"> 全国招考</span>
    </div>
    <div class="exam-list">
      <div
        v-for="(exam, index) in state.exams"
        :key="index"
        class="exam-item"
        @click="handleExamClick(exam)">
        <div class="exam-date-box">
          <span class="exam-month"> {{ exam.month }}</span>
          <span class="exam-day"> {{ exam.day }}</span>
        </div>
        <div class="exam-info">
          <span class="exam-title"> {{ exam.title }}</span>
          <span class="exam-location"> {{ exam.province }}</span>
        </div>
        <div class="exam-arrow">
          <XIcon :icon="DArrowRight" :size="14" color="#c0c8d4"></XIcon>
        </div>
      </div>
    </div>
    <div class="card-footer" @click="$message.info('更多考试信息开发中')">
      <span class="footer-link"> 查看全部考试日历</span>
      <XIcon :icon="DArrowRight" :size="14" color="#c8161e"></XIcon>
    </div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { Calendar, DArrowRight } from '@vtj/icons';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'ExamCalendar',
    components: { XIcon },
    setup(props) {
      const provider = useProvider({ id: 'gjv83ley', version: '1778915692038' });
      const state = reactive({
        exams: [
          { month: '03', day: '15', title: '2026年度辽宁省考', province: '辽宁' },
          { month: '03', day: '16', title: '2026年度江苏省考', province: '江苏' },
          { month: '04', day: '12', title: '2026年度广东省考', province: '广东' },
          { month: '04', day: '20', title: '2026年度浙江省考', province: '浙江' },
          { month: '11', day: '30', title: '2026年度国考笔试', province: '全国' }
        ]
      });
      return { state, props, provider, Calendar, DArrowRight };
    },
    methods: {
      handleExamClick(exam) {
        this.$message.info(`正在加载 ${exam.title} 详细信息...`);
      }
    }
  })
</script>
<style lang="css" scoped>
  /* 考试日历卡片 */
  .exam-calendar-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 20px 20px 12px;
    border: 1px solid #e8ecf1;
    box-shadow: 0 4px 20px rgba(10, 22, 40, 0.06);
    transition: all 0.3s ease;
    height: 100%;
  }
  .exam-calendar-card:hover {
    box-shadow: 0 6px 28px rgba(10, 22, 40, 0.1);
  }
  /* 卡片标题 */
  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #f0f2f5;
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .header-title {
    font-size: 16px;
    font-weight: 600;
    color: #1a2a3a;
    letter-spacing: 1px;
  }
  .header-badge {
    font-size: 11px;
    color: #c8161e;
    background: rgba(200, 22, 30, 0.08);
    padding: 3px 10px;
    border-radius: 12px;
    font-weight: 500;
  }
  /* 考试列表 */
  .exam-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .exam-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.25s ease;
    border: 1px solid transparent;
  }
  .exam-item:hover {
    background: rgba(200, 22, 30, 0.03);
    border-color: rgba(200, 22, 30, 0.1);
    transform: translateX(4px);
  }
  /* 日期盒子 */
  .exam-date-box {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-width: 48px;
    height: 48px;
    background: linear-gradient(135deg, #fef1f2 0%, #fde8ea 100%);
    border-radius: 10px;
    border: 1px solid rgba(200, 22, 30, 0.15);
  }
  .exam-month {
    font-size: 11px;
    font-weight: 500;
    color: #c8161e;
    line-height: 1;
  }
  .exam-day {
    font-size: 18px;
    font-weight: 700;
    color: #c8161e;
    line-height: 1.2;
  }
  /* 考试信息 */
  .exam-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  .exam-title {
    font-size: 13px;
    font-weight: 500;
    color: #2c3e50;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .exam-location {
    font-size: 11px;
    color: #8899aa;
  }
  /* 箭头 */
  .exam-arrow {
    display: flex;
    align-items: center;
    opacity: 0;
    transition: opacity 0.25s ease;
  }
  .exam-item:hover .exam-arrow {
    opacity: 1;
  }
  /* 底部链接 */
  .card-footer {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 12px 0 4px;
    cursor: pointer;
    border-top: 1px solid #f5f6f8;
    margin-top: 8px;
    transition: all 0.25s ease;
  }
  .card-footer:hover {
    color: #c8161e;
  }
  .footer-link {
    font-size: 12px;
    color: #8899aa;
    font-weight: 500;
  }
  .card-footer:hover .footer-link {
    color: #c8161e;
  }
</style>
