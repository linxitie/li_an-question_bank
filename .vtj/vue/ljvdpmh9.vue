<template>
  <div class="exam-calendar">
    <div class="cal-header">
      <XIcon :icon="Calendar" :size="20" color="#c41e3a"></XIcon>
      <span class="cal-title"> 考试日历</span>
      <div class="cal-month">
        {{ state.currentMonth }}
      </div>
    </div>
    <div class="cal-list">
      <div
        v-for="(item, index) in state.examList"
        :key="index"
        class="cal-item"
        @click="handleItemClick(item)">
        <div class="cal-date">
          <span class="date-day"> {{ item.day }}</span>
          <span class="date-month"> {{ item.month }}</span>
        </div>
        <div class="cal-content">
          <div class="cal-name">
            {{ item.name }}
          </div>
          <div class="cal-region">
            {{ item.region }}
          </div>
        </div>
        <div class="cal-status">
          {{ item.status }}
        </div>
        <XIcon :icon="ArrowRight" :size="14" color="#8a8faa"></XIcon>
      </div>
    </div>
    <div class="cal-footer" @click="handleViewAll">
      <span> 查看全部招考信息</span>
      <XIcon :icon="DArrowRight" :size="14" color="#c41e3a"></XIcon>
    </div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { Calendar, ArrowRight, DArrowRight } from '@vtj/icons';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'ExamCalendar',
    components: { XIcon },
    emits: ['exam-click', 'view-all'],
    setup(props) {
      const provider = useProvider({ id: 'ljvdpmh9', version: '1778917815278' });
      const state = reactive({ examList: [], currentMonth: '' });
      return { state, props, provider, Calendar, ArrowRight, DArrowRight };
    },
    methods: {
      loadExamData() {
        const now = new Date();
        this.state.currentMonth = now.getMonth() + 1 + '月考试日历';
        this.state.examList = [
          {
            day: '15',
            month: now.getMonth() + 2 + '月',
            name: '2025年国考笔试成绩公布',
            region: '全国',
            status: '即将发布',
            statusType: 'upcoming'
          },
          {
            day: '20',
            month: now.getMonth() + 2 + '月',
            name: '江苏省考面试公告',
            region: '江苏',
            status: '报名中',
            statusType: 'open'
          },
          {
            day: '05',
            month: now.getMonth() + 3 + '月',
            name: '浙江省事业单位联考',
            region: '浙江',
            status: '备考中',
            statusType: 'preparing'
          },
          {
            day: '12',
            month: now.getMonth() + 3 + '月',
            name: '公安院校联考专业课笔试',
            region: '全国',
            status: '待考',
            statusType: 'pending'
          },
          {
            day: '28',
            month: now.getMonth() + 2 + '月',
            name: '广东省考报名截止',
            region: '广东',
            status: '倒计时',
            statusType: 'countdown'
          }
        ];
      },
      handleViewAll() {
        this.$emit('view-all');
      },
      handleItemClick(item) {
        this.$emit('exam-click', item);
        this.$message.info('跳转至' + item.name + '详情');
      }
    },
    mounted() {
      this.loadExamData();
    }
  })
</script>
<style lang="css" scoped>
  .exam-calendar {
    background: #ffffff;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 16px rgba(26, 43, 95, 0.06);
    max-height: 574px;
    overflow-y: auto;
  }
  .cal-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid #f0f2f5;
  }
  .cal-title {
    font-size: 15px;
    font-weight: 700;
    color: #1a2b5f;
    flex: 1;
  }
  .cal-month {
    font-size: 12px;
    color: #8a8faa;
    background: #f8f9fc;
    padding: 4px 10px;
    border-radius: 12px;
  }
  .cal-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .cal-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border-radius: 12px;
    background: #f8f9fc;
    transition: all 0.3s;
    cursor: pointer;
  }
  .cal-item:hover {
    background: #f0f2f5;
    transform: translateX(2px);
  }
  .cal-date {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 44px;
    padding: 6px;
    background: #ffffff;
    border-radius: 10px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  }
  .date-day {
    font-size: 20px;
    font-weight: 900;
    color: #1a2b5f;
    line-height: 1;
  }
  .date-month {
    font-size: 10px;
    color: #8a8faa;
    margin-top: 2px;
  }
  .cal-content {
    flex: 1;
  }
  .cal-name {
    font-size: 13px;
    font-weight: 600;
    color: #1a2b5f;
    margin-bottom: 2px;
  }
  .cal-region {
    font-size: 11px;
    color: #8a8faa;
  }
  .cal-status {
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 10px;
    font-weight: 600;
  }
  .cal-status.upcoming {
    background: #fff3e0;
    color: #e65100;
  }
  .cal-status.open {
    background: #e8f5e9;
    color: #2e7d32;
  }
  .cal-status.preparing {
    background: #e3f2fd;
    color: #1565c0;
  }
  .cal-status.pending {
    background: #f3e5f5;
    color: #7b1fa2;
  }
  .cal-status.countdown {
    background: #fce4ec;
    color: #c62828;
  }
  .cal-footer {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid #f0f2f5;
    font-size: 13px;
    color: #c41e3a;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
  }
  .cal-footer:hover {
    color: #e8384f;
  }
</style>
