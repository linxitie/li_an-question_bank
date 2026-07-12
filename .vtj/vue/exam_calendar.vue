<!-- 考试日历模块 -->
<template>
  <div class="exam-calendar-card">
    <div class="card-header">
      <div class="header-left">
        <XIcon :icon="Calendar" :size="18" color="#c8161e"></XIcon>
        <span class="header-title"> 考试日历</span>
      </div>
      <span class="header-badge"> 全国招考</span>
    </div>
    <div class="exam-list" @scroll="handleScroll" ref="examList">
      <div
        v-for="(exam, index) in state.exams"
        :key="index"
        class="exam-item"
        @click="handleExamClick(exam)">
        <div class="exam-date-box">
          <span class="exam-month"> {{ exam.month }}月</span>
          <span class="exam-day"> {{ exam.day }}</span>
        </div>
        <div class="exam-info">
          <div class="exam-title-row">
            <span class="exam-title"> {{ exam.title }}</span>
            <span v-if="exam.exam_format" class="exam-format-badge">{{ exam.exam_format }}</span>
          </div>
          <div class="exam-meta-row">
            <span v-if="exam.registration_display" class="exam-reg-time">{{ exam.registration_display }}</span>
            <span class="exam-province">{{ exam.province }}</span>
          </div>
        </div>
        <div class="exam-status">
          <span class="status-badge" :style="{background: exam.status_color || '#10b981'}">{{ exam.status || '报名中' }}</span>
        </div>
      </div>
      <div v-if="state.loading" class="exam-loading">加载中...</div>
      <div v-if="!state.hasMore && state.exams.length > 0" class="exam-loading">没有更多了</div>
    </div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive, ref, onMounted, nextTick } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { Calendar, DArrowRight } from '@vtj/icons';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'ExamCalendar',
    components: { XIcon },
    setup(props) {
      const provider = useProvider({ id: 'exam_calendar', version: '1778915692038' });
      const state = reactive({ exams: [], loading: false, page: 1, hasMore: true });
      const examList = ref(null);
      return { state, props, provider, Calendar, DArrowRight, examList };
    },
    methods: {
      async fetchExams(reset) {
        if (reset === void 0) reset = false;
        if (this.state.loading) return;
        if (!reset && !this.state.hasMore) return;
        if (reset) {
          this.state.page = 1;
          this.state.exams = [];
          this.state.hasMore = true;
        }
        this.state.loading = true;
        try {
          var offset = (this.state.page - 1) * 20;
          var res = await window.__VTJ_AUTH__.apiFetch('/api/calendar/exams?limit=20&offset=' + offset);
          var data = await res.json();
          if (res.ok && data.items) {
            var items = data.items.map(this.formatExamItem);
            if (reset) {
              this.state.exams = items;
            } else {
              this.state.exams = this.state.exams.concat(items);
            }
            this.state.hasMore = data.has_more !== false;
            if (data.has_more !== false) {
              this.state.page = this.state.page + 1;
            }
          }
        } catch (e) {
          // ignore
        } finally {
          this.state.loading = false;
        }
      },
      formatExamItem(e) {
        return {
          month: e.month || '',
          day: e.day || '',
          title: e.title || '',
          province: e.province || '',
          url: e.url || '',
          exam_format: e.exam_format || '',
          registration_start: e.registration_start || '',
          registration_end: e.registration_end || '',
          registration_display: this.formatRegDate(e.registration_start, e.registration_end),
          status: e.status || '',
          status_color: e.status_color || '#10b981'
        };
      },
      formatRegDate(start, end) {
        if (!start && !end) return '';
        var s = start ? start.substring(0, 10) : '';
        var e = end ? end.substring(0, 10) : '';
        if (s && e) return s + ' ~ ' + e;
        if (s) return s;
        if (e) return '截止 ' + e;
        return '';
      },
      getStatusClass(status) {
        if (status === '已截止') return 'status-ended';
        if (status === '即将报名') return 'status-upcoming';
        return 'status-open';
      },
      handleScroll() {
        var el = this.$refs.examList;
        if (!el) return;
        var threshold = 80;
        if (el.scrollTop + el.clientHeight >= el.scrollHeight - threshold) {
          this.fetchExams(false);
        }
      },
      handleExamClick(exam) {
        if (exam.url) {
          window.open(exam.url, '_blank');
        } else {
          this.$message.info('暂无详情链接');
        }
      }
    },
    mounted() {
      this.fetchExams(true);
    }
  })
</script>
<style lang="css" scoped>
  /* 考试日历卡片 — 75vw 宽 */
  .exam-calendar-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 20px 20px 12px;
    border: 1px solid #e8ecf1;
    box-shadow: 0 4px 20px rgba(10, 22, 40, 0.06);
    transition: all 0.3s ease;
    width: 75vw;
    max-width: 1400px;
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
    font-size: 15px;
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
  /* 考试列表 — 可滚动 */
  .exam-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 55vh;
    overflow-y: auto;
    padding-right: 4px;
  }
  .exam-list::-webkit-scrollbar {
    width: 5px;
  }
  .exam-list::-webkit-scrollbar-thumb {
    background: #d0d5dd;
    border-radius: 4px;
  }
  .exam-list::-webkit-scrollbar-track {
    background: transparent;
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
    flex-shrink: 0;
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
    gap: 3px;
    min-width: 0;
  }
  .exam-title-row {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }
  .exam-title {
    font-size: 15px;
    font-weight: 500;
    color: #2c3e50;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
  }
  .exam-format-badge {
    font-size: 11px;
    color: #1a2a6c;
    background: rgba(26, 42, 108, 0.08);
    padding: 2px 8px;
    border-radius: 8px;
    font-weight: 500;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .exam-meta-row {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 13px;
  }
  .exam-reg-time {
    color: #666;
    font-size: 13px;
    white-space: nowrap;
  }
  .exam-province {
    font-size: 13px;
    color: #8899aa;
  }
  /* 状态徽章 */
  .exam-status {
    display: flex;
    align-items: center;
    flex-shrink: 0;
  }
  .status-badge {
    font-size: 12px;
    font-weight: 500;
    color: #fff;
    padding: 3px 10px;
    border-radius: 10px;
    white-space: nowrap;
  }
  /* 加载提示 */
  .exam-loading {
    text-align: center;
    padding: 12px;
    font-size: 13px;
    color: #8899aa;
  }
</style>
