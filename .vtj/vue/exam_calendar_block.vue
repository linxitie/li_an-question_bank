<!-- 考试日历模块 — 浅蓝底色 · 纯白条目 · 大圆角 -->
<template>
  <div class="exam-calendar">
    <!-- 右上角装饰图标 -->
    <div class="cal-decoration">
      <XIcon :icon="Calendar" :size="72" color="#8ab4d6"></XIcon>
    </div>

    <div class="cal-header">
      <XIcon :icon="Calendar" :size="22" color="#3b7db5"></XIcon>
      <span class="cal-title">考试日历</span>
      <div class="cal-month">{{ state.currentMonth }}</div>
    </div>

    <!-- 空状态 -->
    <div class="cal-empty" v-if="state.examList.length === 0">
      <span>暂无考试信息</span>
    </div>

    <!-- 考试列表 -->
    <div class="cal-list" v-else>
      <div
        v-for="(item, index) in state.examList"
        :key="index"
        class="cal-item"
        @click="handleItemClick(item)">
        <!-- 日期徽标 -->
        <div class="cal-date">
          <span class="date-day">{{ item.day }}</span>
          <span class="date-month">{{ item.month }}月</span>
        </div>
        <!-- 内容区 -->
        <div class="cal-content">
          <div class="cal-name">{{ item.name }}</div>
          <div class="cal-meta">
            <span v-if="item.region">{{ item.region }}</span>
            <span v-if="item.examFormat" class="cal-format-tag">{{ item.examFormat }}</span>
            <span v-if="item.registrationTime" class="cal-reg-time">报名: {{ item.registrationTime }}</span>
          </div>
        </div>
        <!-- 状态标签 -->
        <span class="cal-status" :style="{
          color: item.statusColor || '#10b981',
          background: (item.statusColor || '#10b981') + '18'
        }">{{ item.statusLabel || '报名中' }}</span>
        <XIcon :icon="ArrowRight" :size="16" color="#c0ccda"></XIcon>
      </div>
    </div>

    <div class="cal-footer" @click="handleViewAll">
      <span>查看全部招考信息</span>
      <XIcon :icon="DArrowRight" :size="16" color="#3b7db5"></XIcon>
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
  setup(props: any) {
    const provider = useProvider({ id: 'exam_calendar_block', version: '1778917815278' });
    const state = reactive({ examList: [] as any[], currentMonth: '' });
    return { state, props, provider, Calendar, ArrowRight, DArrowRight };
  },
  methods: {
    async fetchExams() {
      var now = new Date();
      this.state.currentMonth = (now.getMonth() + 1) + '月考试日历';
      try {
        var res = await (window as any).__VTJ_AUTH__.apiFetch('/api/calendar/exams?limit=5');
        var data = await res.json();
        if (res.ok && data.items) {
          this.state.examList = data.items.map(function(e: any) {
            return {
              day: e.day || '--',
              month: e.month || '',
              name: e.title || '',
              region: e.province || '',
              examFormat: e.exam_format || '',
              registrationTime: e.registration_start ? e.registration_start.substring(5, 10).replace('-', '月') + '日' : '',
              url: e.url || '',
              statusLabel: e.status || '报名中',
              statusColor: e.status_color || '#10b981'
            };
          });
        } else {
          this.state.examList = [];
        }
      } catch (e: any) {
        console.warn('[ExamCalendar] fetchExams failed:', e.message);
        this.state.examList = [];
      }
    },
    handleViewAll() {
      (this as any).$emit('view-all');
    },
    handleItemClick(item: any) {
      if (item.url) {
        window.open(item.url, '_blank');
      } else {
        (this as any).$message.info('暂无详情链接');
      }
    }
  },
  mounted() {
    this.fetchExams();
  }
})
</script>

<style lang="css" scoped>
/* ===== 容器 — 浅蓝底色 + 大圆角 ===== */
.exam-calendar {
  position: relative;
  background: #ffffff;
  border-radius: 18px;
  padding: 24px 20px 20px;
  overflow: hidden;
}

/* 右上角装饰图标 — 半透明融入背景 */
.cal-decoration {
  position: absolute; top: 8px; right: 16px;
  opacity: 0.15; pointer-events: none; z-index: 0;
}

/* ===== 标题栏 ===== */
.cal-header {
  position: relative; z-index: 1;
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 18px;
}
.cal-title {
  font-size: 20px; font-weight: 700; color: #1a2b5f; flex: 1;
}
.cal-month {
  font-size: 13px; color: #5a7d9a;
  background: rgba(59,125,181,0.1); padding: 4px 12px; border-radius: 14px;
}

/* ===== 空状态 ===== */
.cal-empty {
  text-align: center; padding: 30px 0; color: #a0bcd0; font-size: 14px;
}

/* ===== 考试列表 ===== */
.cal-list {
  position: relative; z-index: 1;
  display: flex; flex-direction: column; gap: 8px;
}

/* 条目 — 纯白底色 + 大圆角 */
.cal-item {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 14px; border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 1px 4px rgba(26,43,95,0.04);
  cursor: pointer;
  transition: all 0.25s;
}
.cal-item:hover {
  box-shadow: 0 3px 12px rgba(26,43,95,0.08);
  transform: translateX(3px);
}

/* 日期徽标 */
.cal-date {
  display: flex; flex-direction: column; align-items: center;
  min-width: 44px; padding: 6px 4px;
  background: #f5f9fc; border-radius: 10px;
}
.date-day {
  font-size: 20px; font-weight: 900; color: #1a2b5f; line-height: 1.1;
}
.date-month {
  font-size: 15px; color: #8a9eb5; margin-top: 1px;
}

/* 内容区 */
.cal-content { flex: 1; min-width: 0; }
.cal-name {
  font-size: 16px; font-weight: 700; color: #1a2b5f;
  margin-bottom: 4px; line-height: 1.3;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.cal-meta {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; color: #8a8faa; flex-wrap: wrap;
}
.cal-meta-item {
  font-size: 12px; color: #8a8faa;
}
.cal-format-tag {
  font-size: 14px; color: #5a7d9a;
  background: #e8f4fd; padding: 1px 8px; border-radius: 6px;
  font-weight: 500;
}
.cal-reg-time {
  font-size: 12px; color: #8a8faa;
}

/* 状态标签 — 胶囊 + 动态颜色 */
.cal-status {
  font-size: 13px; padding: 3px 10px; border-radius: 20px;
  font-weight: 600; white-space: nowrap; flex-shrink: 0;
}

/* 底部链接 */
.cal-footer {
  position: relative; z-index: 1;
  display: flex; align-items: center; justify-content: center;
  gap: 6px; margin-top: 16px; padding-top: 12px;
  border-top: 1px solid rgba(59,125,181,0.15);
  font-size: 13px; color: #3b7db5; font-weight: 600;
  cursor: pointer; transition: all 0.25s;
}
.cal-footer:hover { color: #2a5d8a; }
</style>
