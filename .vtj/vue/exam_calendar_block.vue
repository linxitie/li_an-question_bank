<!-- 考试日历模块 -->
<template>
  <div class="exam-calendar">
    <div class="cal-header">
      <XIcon :icon="Calendar" :size="22" color="#c8161e"></XIcon>
      <span class="cal-title">考试日历</span>
      <span class="cal-badge">全国招考</span>
    </div>
    <div class="cal-empty" v-if="state.examList.length === 0">
      <span>暂无考试信息</span>
    </div>
    <div class="cal-list" v-else @scroll="handleScroll" ref="calList">
      <div v-for="(item, index) in state.examList" :key="index" class="cal-item-wrapper">
        <div class="cal-item" @click="toggleExpand(index)">
          <div class="cal-date">
            <span class="date-day">{{ item.day }}</span>
            <span class="date-month">{{ item.month }}月</span>
          </div>
          <div class="cal-content">
            <div class="cal-name-row">
              <span class="cal-name">{{ item.name }}</span>
              <span v-if="item.recruitmentCount" class="cal-count-badge">{{ item.recruitmentCount }}人</span>
              <span v-if="item.examFormat" class="cal-format-tag">{{ item.examFormat }}</span>
            </div>
            <div class="cal-meta">
              <span v-if="item.registrationDisplay" class="cal-reg-time" v-html="item.registrationDisplay"></span>
              <span v-if="item.region" class="cal-region">{{ item.region }}</span>
            </div>
          </div>
          <span class="cal-status" :style="{ color: item.statusColor || '#10b981', background: (item.statusColor || '#10b981') + '18' }">{{ item.statusLabel || '报名中' }}</span>
        </div>
        <div v-if="state.expandedId === index && item.contentHtml" class="cal-detail" v-html="item.contentHtml"></div>
      </div>
      <div v-if="state.loading" class="cal-loading">加载中...</div>
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
  name: 'ExamCalendarBlock',
  components: { XIcon },
  setup(props: any) {
    const provider = useProvider({ id: 'exam_calendar_block', version: '1778917815278' });
    const state = reactive({ examList: [] as any[], currentMonth: '', loading: false, page: 1, hasMore: true, expandedId: -1 });
    return { state, props, provider, Calendar };
  },
  methods: {
    async fetchExams(reset?: boolean) {
      if (this.state.loading) return;
      if (!reset && !this.state.hasMore) return;
      if (reset) { this.state.page = 1; this.state.examList = []; this.state.hasMore = true; }
      this.state.loading = true;
      try {
        var now = new Date();
        this.state.currentMonth = (now.getMonth() + 1) + '月';
        var offset = (this.state.page - 1) * 20;
        var res = await (window as any).__VTJ_AUTH__.apiFetch('/api/calendar/exams?limit=20&offset=' + offset);
        var data = await res.json();
        if (res.ok && data.items) {
          var items = data.items.map(function(e: any) {
            var start = e.registration_start ? e.registration_start.substring(0, 10) : '';
            var end = e.registration_end ? e.registration_end.substring(0, 10) : '';
            var regDisplay = '';
            if (start && end) { regDisplay = '报名: ' + start + ' ~ <span style="color:#c41e3a;font-weight:700">' + end + '</span>'; }
            else if (start) { regDisplay = '报名: ' + start; }
            else if (end) { regDisplay = '截止: <span style="color:#c41e3a;font-weight:700">' + end + '</span>'; }
            return {
              day: e.day || '--',
              month: e.month || '',
              name: e.title || '',
              region: e.province || '',
              examFormat: e.exam_format || '',
              recruitmentCount: e.recruitment_count || '',
              registrationDisplay: regDisplay,
              url: e.url || '',
              statusLabel: e.status || '报名中',
              statusColor: e.status_color || '#10b981',
              contentHtml: e.content_html || e.description || '',
            };
          });
          if (reset) { this.state.examList = items; }
          else { this.state.examList = this.state.examList.concat(items); }
          this.state.hasMore = data.has_more !== false;
          if (data.has_more !== false) this.state.page++;
        }
      } catch (e: any) { /* ignore */ }
      finally { this.state.loading = false; }
    },
    toggleExpand(index: number) {
      this.state.expandedId = this.state.expandedId === index ? -1 : index;
    },
    handleScroll() {
      var el = (this as any).$refs.calList;
      if (!el) return;
      if (el.scrollTop + el.clientHeight >= el.scrollHeight - 80) {
        this.fetchExams(false);
      }
    }
  },
  mounted() {
    this.fetchExams(true);
  }
})
</script>
<style lang="css" scoped>
.exam-calendar {
  background: #ffffff; border-radius: 18px;
  padding: 24px 20px 20px; overflow: hidden;
  max-width: 1200px;
}
.cal-header {
  display: flex; align-items: center; gap: 10px; margin-bottom: 18px;
  padding-bottom: 14px; border-bottom: 1px solid #f0f2f5;
}
.cal-title { font-size: 20px; font-weight: 700; color: #1a2a3a; flex: 1; }
.cal-badge {
  font-size: 12px; color: #c8161e;
  background: rgba(200,22,30,0.08); padding: 3px 12px; border-radius: 12px; font-weight: 600;
}
.cal-empty { text-align: center; padding: 30px 0; color: #a0bcd0; font-size: 14px; }
.cal-list {
  display: flex; flex-direction: column; gap: 8px;
  max-height: 55vh; overflow-y: auto; padding-right: 4px;
}
.cal-list::-webkit-scrollbar { width: 5px; }
.cal-list::-webkit-scrollbar-thumb { background: #d0d5e0; border-radius: 3px; }
.cal-item-wrapper { display: flex; flex-direction: column; }
.cal-item {
  display: flex; align-items: center; gap: 12px;
  padding: 14px 16px; border-radius: 14px;
  background: #fafbfd; cursor: pointer;
  transition: all 0.25s; border: 1px solid transparent;
}
.cal-item:hover { border-color: rgba(200,22,30,0.15); background: #fff; box-shadow: 0 2px 12px rgba(26,43,95,0.06); }
.cal-date {
  display: flex; flex-direction: column; align-items: center;
  min-width: 48px; padding: 6px 4px;
  background: linear-gradient(135deg, #fef1f2 0%, #fde8ea 100%);
  border-radius: 10px; border: 1px solid rgba(200,22,30,0.15);
}
.date-day { font-size: 20px; font-weight: 900; color: #c8161e; line-height: 1.1; }
.date-month { font-size: 12px; color: #c8161e; margin-top: 1px; }
.cal-content { flex: 1; min-width: 0; }
.cal-name-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap; }
.cal-name {
  font-size: 16px; font-weight: 700; color: #1a2b5f; line-height: 1.4;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.cal-count-badge {
  font-size: 12px; padding: 2px 10px; border-radius: 8px;
  background: #eff6ff; color: #3b82f6; font-weight: 600; white-space: nowrap;
}
.cal-format-tag {
  font-size: 12px; color: #5a7d9a; background: #e8f4fd;
  padding: 2px 8px; border-radius: 6px; font-weight: 500; white-space: nowrap;
}
.cal-meta { display: flex; align-items: center; gap: 10px; font-size: 13px; color: #8899aa; flex-wrap: wrap; }
.cal-reg-time { font-size: 13px; }
.cal-region { font-size: 12px; color: #8899aa; }
.cal-status {
  font-size: 13px; padding: 4px 12px; border-radius: 20px;
  font-weight: 700; white-space: nowrap; flex-shrink: 0;
}
.cal-detail {
  padding: 16px 20px; margin: 4px 8px 0;
  background: #f8f9fc; border-radius: 10px;
  border-left: 3px solid #c41e3a;
  font-size: 15px; line-height: 1.8; color: #333;
  max-height: 260px; overflow-y: auto;
}
.cal-detail :deep(p) { margin-bottom: 12px; }
.cal-loading { text-align: center; padding: 16px; font-size: 13px; color: #8899aa; }
</style>
