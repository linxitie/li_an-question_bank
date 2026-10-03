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
        class="exam-item-wrapper">
        <div
          class="exam-item"
          @click="toggleExpand(index)">
          <div class="exam-date-box">
            <span class="exam-month"> {{ exam.month }}月</span>
            <span class="exam-day"> {{ exam.day }}</span>
          </div>
          <div class="exam-info">
            <div class="exam-title-row">
              <span class="exam-title"> {{ exam.title }}</span>
              <span v-if="exam.recruitment_count" class="exam-count-badge">{{ exam.recruitment_count }}人</span>
              <span v-if="exam.exam_format" class="exam-format-badge">{{ exam.exam_format }}</span>
            </div>
            <div class="exam-meta-row">
              <span v-if="exam.registration_display_html" class="exam-reg-time" v-html="sanitizeHtml(exam.registration_display_html)"></span>
              <span class="exam-province">{{ exam.province }}</span>
            </div>
          </div>
          <div class="exam-status">
            <span class="status-badge" :style="{background: exam.status_color || '#10b981'}">{{ exam.status || '报名中' }}</span>
          </div>
        </div>
        <!-- Accordion 展开详情 -->
        <div v-if="state.expandedId === index && (exam.content_html || exam.description)" class="exam-detail-expanded">
          <div class="exam-detail-content" v-html="sanitizeHtml(exam.content_html || exam.description)"></div>
        </div>
      </div>
      <div v-if="state.loading" class="exam-loading">加载中...</div>
      <div v-if="!state.hasMore && state.exams.length > 0" class="exam-loading">没有更多了</div>
    </div>
  </div>
</template>
<script lang="ts">
import { sanitizeHtml } from '@/utils/questionRender';
  // @ts-nocheck
  import { defineComponent, reactive, ref, onMounted, nextTick } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { Calendar, DArrowRight } from '@vtj/icons';
  import { useProvider } from '@vtj/renderer';
  import { ElMessage } from 'element-plus';
  export default defineComponent({
    name: 'ExamCalendar',
    components: { XIcon },
    setup(props) {
      const provider = useProvider({ id: 'exam_calendar', version: '1778915692038' });
      const state = reactive({ exams: [], loading: false, page: 1, hasMore: true, expandedId: -1 });
      const examList = ref(null);
      return { state, props, provider, Calendar, DArrowRight, examList, sanitizeHtml };
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
          registration_display_html: this.formatRegDateHtml(e.registration_start, e.registration_end),
          content_html: e.content_html || e.description || '',
          description: e.description || '',
          recruitment_count: e.recruitment_count || '',
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
      formatRegDateHtml(start, end) {
        if (!start && !end) return '';
        var s = start ? start.substring(0, 10) : '';
        var e = end ? end.substring(0, 10) : '';
        if (s && e) return s + ' ~ <span style="color:#c41e3a;font-weight:700">' + e + '</span>';
        if (s) return s;
        if (e) return '截止 <span style="color:#c41e3a;font-weight:700">' + e + '</span>';
        return '';
      },
      toggleExpand(index) {
        this.state.expandedId = this.state.expandedId === index ? -1 : index;
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
          ElMessage.info('暂无详情链接');
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
    gap: 4px;
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
  /* 考试条目包裹（用于 accordion）*/
  .exam-item-wrapper {
    display: flex;
    flex-direction: column;
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
    gap: 6px;
    min-width: 0;
  }
  .exam-title {
    font-size: 15px;
    font-weight: 500;
    color: #2c3e50;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    flex: 1;
  }
  .exam-count-badge {
    font-size: 11px;
    color: #c8161e;
    background: rgba(200, 22, 30, 0.08);
    padding: 2px 8px;
    border-radius: 8px;
    font-weight: 500;
    white-space: nowrap;
    flex-shrink: 0;
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
  /* Accordion 展开详情 */
  .exam-detail-expanded {
    padding: 0 12px 10px 72px;
    animation: examSlideDown 0.25s ease;
  }
  @keyframes examSlideDown {
    from { opacity: 0; max-height: 0; }
    to { opacity: 1; max-height: 500px; }
  }
  .exam-detail-content {
    font-size: 13px;
    color: #555;
    line-height: 1.7;
    padding: 10px 14px;
    background: #fafbfc;
    border-radius: 8px;
    border-left: 3px solid #c8161e;
    max-height: 260px;
    overflow-y: auto;
  }
  .exam-detail-content::-webkit-scrollbar {
    width: 4px;
  }
  .exam-detail-content::-webkit-scrollbar-thumb {
    background: #d0d5dd;
    border-radius: 3px;
  }
  /* 加载提示 */
  .exam-loading {
    text-align: center;
    padding: 12px;
    font-size: 13px;
    color: #8899aa;
  }
</style>
