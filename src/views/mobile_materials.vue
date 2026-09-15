<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">备考资料</h1>
      <span class="spacer"></span>
    </header>

    <!-- 科目 Tab -->
    <div class="tabs">
      <div
        v-for="s in subjects"
        :key="s.key"
        :class="['tab', { active: activeSubject === s.key }]"
        @click="switchSubject(s.key)"
      >
        {{ s.name }}
      </div>
    </div>

    <main class="list">
      <div v-for="m in materials" :key="m.id" class="card" @click="toggleDetail(m)">
        <div class="m-title">{{ m.title }}</div>
        <div class="m-meta">
          <span class="tag">{{ typeName(m.type) }}</span>
          <span v-if="m.duration" class="tag">⏱ {{ m.duration }}分钟</span>
          <span v-if="m.read_time" class="tag">阅读 {{ m.read_time }}分钟</span>
          <span v-if="m.is_studied" class="done">已学</span>
          <span v-if="m.progress_percent" class="progress">进度 {{ m.progress_percent }}%</span>
        </div>
        <div v-if="expandedId === m.id" class="detail" @click.stop>
          <p v-if="m.summary" class="summary">{{ m.summary }}</p>
          <button class="view-btn" @click="openDetail(m)">查看详情</button>
        </div>
      </div>
      <div v-if="!materials.length && !loading" class="empty">该科目暂无备考资料</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const subjects = [
  { key: 'xingce', name: '行测' },
  { key: 'shenlun', name: '申论' },
  { key: 'gongzhuan', name: '公专' }
];
const activeSubject = ref('xingce');
const materials = ref<any[]>([]);
const loading = ref(false);
const expandedId = ref<number | null>(null);

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const typeName = (t: string) => {
  return {
    video_intro: '入门视频',
    video_advanced: '进阶视频',
    article: '文章',
    card: '知识卡片'
  }[t] || '资料';
};

const switchSubject = (key: string) => {
  activeSubject.value = key;
  expandedId.value = null;
  fetchMaterials();
};

const toggleDetail = (m: any) => {
  expandedId.value = expandedId.value === m.id ? null : m.id;
};

const fetchMaterials = async () => {
  loading.value = true;
  try {
    const res = await (window as any).__VTJ_AUTH__.apiFetch('/api/materials?subject=' + activeSubject.value + '&page=1&page_size=50');
    const data = await res.json();
    if (res.ok && data.items) materials.value = data.items;
  } catch (e) {
    console.error('获取备考资料失败:', e);
  } finally {
    loading.value = false;
  }
};

const openDetail = (m: any) => {
  // 资料详情暂用 PC 端页面，后续可做移动端详情页
  router.push('/materials/' + m.subject + '?id=' + m.id);
};

onMounted(fetchMaterials);
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
  padding: 8px 0;
  border-radius: 8px;
  font-size: 14px;
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
.m-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  line-height: 1.5;
  margin-bottom: 8px;
}
.m-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.tag {
  font-size: 12px;
  color: #5a6488;
  background: #f0f3f7;
  padding: 3px 8px;
  border-radius: 6px;
}
.done {
  font-size: 12px;
  color: #10b981;
  font-weight: 600;
}
.progress {
  font-size: 12px;
  color: #f59e0b;
}
.detail {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f2f5;
}
.summary {
  font-size: 13px;
  color: #5a6488;
  line-height: 1.6;
  margin: 0 0 10px;
}
.view-btn {
  min-height: 36px;
  padding: 0 16px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #1a2b5f, #1e3470);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}
.empty {
  text-align: center;
  color: #8899aa;
  padding: 40px 0;
}
</style>
