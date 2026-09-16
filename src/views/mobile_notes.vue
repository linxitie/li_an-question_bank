<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">我的笔记</h1>
      <span class="spacer"></span>
    </header>

    <div class="tabs">
      <div :class="['tab', { active: noteType === 'all' }]" @click="switchType('all')">全部</div>
      <div :class="['tab', { active: noteType === 'question' }]" @click="switchType('question')">题目笔记</div>
      <div :class="['tab', { active: noteType === 'news' }]" @click="switchType('news')">新闻笔记</div>
    </div>

    <main class="list">
      <div v-for="n in notes" :key="n.note_id" class="card" @click="openNote(n)">
        <div class="note-title">{{ n.title || '（无标题）' }}</div>
        <blockquote v-if="n.quote_text" class="note-quote">{{ n.quote_text }}</blockquote>
        <div class="note-text">{{ n.note_text }}</div>
        <div class="note-meta">
          <span class="tag">{{ n.type === 'question' ? '题目' : '新闻' }}</span>
          <span v-if="n.subject" class="tag">{{ n.subject }}</span>
          <span class="time">{{ formatTime(n.update_time) }}</span>
        </div>
      </div>
      <div v-if="!notes.length && !loading" class="empty">暂无笔记</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const noteType = ref('all');
const notes = ref<any[]>([]);
const loading = ref(false);

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const formatTime = (iso: string) => {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString();
};

const switchType = (t: string) => {
  noteType.value = t;
  fetchNotes();
};

const openNote = (n: any) => {
  // 题目笔记跳题目详情，新闻笔记跳新闻详情
  if (n.type === 'news' && n.news_id) router.push('/mobile/news/' + n.news_id);
  else if (n.type === 'question' && n.question_id) router.push('/mobile/notes-question/' + n.question_id);
};

const fetchNotes = async () => {
  loading.value = true;
  try {
    const res = await (window as any).__VTJ_AUTH__.apiFetch('/api/notes?note_type=' + noteType.value);
    const data = await res.json();
    if (res.ok && data.items) notes.value = data.items;
  } catch (e) {
    console.error('获取笔记失败:', e);
  } finally {
    loading.value = false;
  }
};

onMounted(fetchNotes);
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
.tabs {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  background: #fff;
  border-bottom: 1px solid #f0f2f5;
}
.tab {
  flex: 1;
  text-align: center;
  padding: 7px 0;
  border-radius: 8px;
  font-size: 13px;
  color: #5a6488;
  background: #f0f3f7;
  cursor: pointer;
}
.tab.active {
  background: #1a2b5f;
  color: #fff;
}
.list {
  flex: 1;
  padding: 12px;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
}
.note-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
  line-height: 1.4;
  margin-bottom: 6px;
}
.note-quote {
  margin: 0 0 6px;
  padding: 4px 8px;
  font-size: 13px;
  color: #5a6488;
  background: #f8f9fc;
  border-radius: 4px;
}
.note-text {
  font-size: 14px;
  color: #1a2a3a;
  line-height: 1.6;
  margin-bottom: 8px;
}
.note-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}
.tag {
  font-size: 11px;
  color: #5a6488;
  background: #f0f3f7;
  padding: 2px 8px;
  border-radius: 6px;
}
.time {
  font-size: 11px;
  color: #8899aa;
}
.empty {
  text-align: center;
  color: #8899aa;
  padding: 40px 0;
}
</style>
