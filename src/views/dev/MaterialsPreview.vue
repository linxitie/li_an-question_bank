<!-- 备考资料「内容验收」预览页（dev，公开路由 /materials-preview）。

    用途：不登录也能看到真实接口返回的卡片（列表 /api/materials 是游客可访问），
    便于逐版截图对比「分类、考点、正文长度、摘要」等验收项。
    数据是真实的，样式是简化版（真实页面在 .vtj 模板里，AI 不改其模板）。 -->
<template>
  <div class="mp">
    <header class="mp-head">
      <div>
        <h1>备考资料 · 内容验收</h1>
        <p class="mp-sub">
          数据来自 <code>/api/materials</code>（游客可读）· 当前科目
          <b>{{ subjectLabel }}</b> · 共 <b>{{ total }}</b> 张卡
        </p>
      </div>
      <nav class="mp-tabs">
        <button v-for="s in subjects" :key="s.key"
                :class="{ on: s.key === subject }" @click="switchSubject(s.key)">
          {{ s.label }}
        </button>
      </nav>
    </header>

    <div v-if="loading" class="mp-empty">加载中…</div>
    <div v-else-if="!cards.length" class="mp-empty">该科目暂无卡片</div>

    <section v-else class="mp-grid">
      <article v-for="c in cards" :key="c.id" class="mp-card">
        <div class="mp-tags">
          <span class="mp-tag">{{ c.category || '未分类' }}</span>
          <span class="mp-dot" :class="'d' + (c.difficulty || 1)">
            {{ diffLabel(c.difficulty) }}
          </span>
          <span class="mp-min">{{ c.read_time || 1 }} 分钟</span>
        </div>
        <h2 class="mp-title">{{ c.card_front || c.title }}</h2>
        <p class="mp-sum">{{ c.summary || '（无摘要）' }}</p>
        <p class="mp-back">{{ c.card_back }}</p>
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import axios from 'axios';

const subjects = [
  { key: 'xingce', label: '行测' },
  { key: 'shenlun', label: '申论' },
  { key: 'gongzhuan', label: '公安专业科目' }
];
const subject = ref(new URLSearchParams(location.hash.split('?')[1] || '').get('subject') || 'xingce');
const cards = ref<any[]>([]);
const total = ref(0);
const loading = ref(false);

const subjectLabel = computed(
  () => subjects.find((s) => s.key === subject.value)?.label || subject.value
);

function diffLabel(d: number) {
  return d === 3 ? '困难' : d === 2 ? '进阶' : '入门';
}

async function load() {
  loading.value = true;
  try {
    const { data } = await axios.get('/api/materials', {
      params: { subject: subject.value, type: 'card', page_size: 50 }
    });
    cards.value = data.items || [];
    total.value = data.total || cards.value.length;
  } finally {
    loading.value = false;
  }
}

function switchSubject(key: string) {
  subject.value = key;
  load();
}

onMounted(load);
</script>

<style scoped>
.mp { min-height: 100vh; background: #f6f7fb; padding: 28px 32px 60px; font-family: system-ui, sans-serif; }
.mp-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 20px; }
.mp-head h1 { font-size: 22px; margin: 0 0 6px; color: #1f2937; }
.mp-sub { margin: 0; font-size: 13px; color: #6b7280; }
.mp-sub b { color: #2563eb; }
.mp-tabs { display: flex; gap: 8px; }
.mp-tabs button { border: 1px solid #d8dbe6; background: #fff; color: #4b5563; padding: 7px 14px;
  border-radius: 999px; font-size: 13px; cursor: pointer; }
.mp-tabs button.on { background: #2563eb; border-color: #2563eb; color: #fff; }
.mp-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.mp-card { background: #fff; border-radius: 14px; padding: 16px 18px 18px; box-shadow: 0 6px 18px rgba(23,43,77,.07); }
.mp-tags { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #6b7280; }
.mp-tag { background: #eef2ff; color: #4338ca; border-radius: 6px; padding: 2px 8px; }
.mp-dot { border-radius: 6px; padding: 2px 8px; background: #f3f4f6; }
.mp-dot.d2 { background: #fef3c7; color: #92400e; }
.mp-dot.d3 { background: #fee2e2; color: #991b1b; }
.mp-min { margin-left: auto; }
.mp-title { font-size: 16px; margin: 10px 0 6px; color: #111827; }
.mp-sum { margin: 0 0 8px; font-size: 12.5px; color: #6b7280; }
.mp-back { margin: 0; font-size: 13px; line-height: 1.7; color: #374151; background: #f9fafb;
  border-radius: 10px; padding: 10px 12px; }
.mp-empty { color: #9ca3af; padding: 40px 0; text-align: center; }
</style>
