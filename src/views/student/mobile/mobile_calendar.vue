<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">考试日历</h1>
      <span class="spacer"></span>
    </header>

    <main class="list">
      <div v-for="item in exams" :key="item.id" class="card" @click="toggleDetail(item)">
        <div class="c-date">
          <div class="c-month">{{ item.month }}月</div>
          <div class="c-day">{{ item.day }}</div>
        </div>
        <div class="c-body">
          <div class="c-title">{{ item.title }}</div>
          <div class="c-meta">
            <span class="status" :style="{ color: item.status_color }">{{ item.status }}</span>
            <span v-if="item.province" class="province">{{ item.province }}</span>
            <span v-if="item.exam_format" class="format">{{ item.exam_format }}</span>
          </div>
          <div v-if="expandedId === item.id" class="detail" @click.stop>
            <div v-if="item.registration_start || item.registration_end" class="detail-row">
              <b>报名时间：</b>{{ item.registration_start || '' }} 至 {{ item.registration_end || '' }}
            </div>
            <div v-if="item.recruitment_count" class="detail-row">
              <b>招聘人数：</b>{{ item.recruitment_count }}
            </div>
            <div v-if="item.description" class="detail-content">{{ item.description }}</div>
            <a v-if="item.url" :href="item.url" target="_blank" rel="noopener" class="origin-link">查看原文</a>
          </div>
        </div>
      </div>
      <div v-if="!exams.length && !loading" class="empty">暂无考试日历信息</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { storeToRefs } from 'pinia';
import { useCalendarStore } from '@/modules/calendar/store';

const router = useRouter();
const calendarStore = useCalendarStore();
// 模板沿用 exams / loading 命名，数据与加载态统一由 calendar 域 store 提供
const { items: exams, loading } = storeToRefs(calendarStore);
const expandedId = ref<number | null>(null);

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const toggleDetail = (item: any) => {
  expandedId.value = expandedId.value === item.id ? null : item.id;
};

onMounted(() => {
  // P2-64：页面主动拉取，calendar 域无事件进出
  calendarStore.load({ limit: 30 });
});
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #F5F7FA;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 48px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #e8ecf1;
}
.back-btn {
  background: none;
  border: none;
  font-size: 22px;
  color: #1a2b5f;
  cursor: pointer;
  padding: 4px 8px;
}
.title {
  font-size: 16px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0;
}
.spacer {
  width: 32px;
}
.list {
  flex: 1;
  padding: 12px;
}
.card {
  display: flex;
  gap: 14px;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
}
.c-date {
  flex-shrink: 0;
  width: 52px;
  text-align: center;
  background: #f0f3f7;
  border-radius: 10px;
  padding: 8px 0;
  align-self: flex-start;
}
.c-month {
  font-size: 12px;
  color: #8899aa;
}
.c-day {
  font-size: 22px;
  font-weight: 700;
  color: #1a2b5f;
}
.c-body {
  flex: 1;
}
.c-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  line-height: 1.5;
  margin-bottom: 6px;
}
.c-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.status {
  font-size: 12px;
  font-weight: 600;
}
.province,
.format {
  font-size: 12px;
  color: #8899aa;
}
.detail {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f2f5;
}
.detail-row {
  font-size: 13px;
  color: #5a6488;
  margin-bottom: 6px;
}
.detail-row b {
  color: #1a2b5f;
}
.detail-content {
  font-size: 13px;
  color: #5a6488;
  line-height: 1.6;
  margin-top: 6px;
  white-space: pre-wrap;
  word-break: break-word;
}
.origin-link {
  display: inline-block;
  margin-top: 10px;
  font-size: 13px;
  color: #1a2b5f;
  text-decoration: none;
}
.empty {
  text-align: center;
  color: #8899aa;
  padding: 40px 0;
}
</style>
