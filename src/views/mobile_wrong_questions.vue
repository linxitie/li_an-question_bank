<!-- 手机端错题集（分类筛选 + 斩题 + 斩题记录 + 错题复习入口） -->
<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">错题集</h1>
      <span class="spacer"></span>
    </header>

    <!-- 复习入口 -->
    <div class="review-bar">
      <button class="review-btn" @click="goReview">
        <span>🔁 错题复习</span>
        <span class="review-sub">按模式重练，答对3次自动斩题</span>
      </button>
    </div>

    <!-- Tab 切换 -->
    <div class="tabs">
      <div :class="['tab', { active: activeTab === 'wrong' }]" @click="switchTab('wrong')">错题</div>
      <div :class="['tab', { active: activeTab === 'chopped' }]" @click="switchTab('chopped')">斩题记录</div>
    </div>

    <!-- 分类筛选（仅错题 tab） -->
    <div class="subject-tabs" v-if="activeTab === 'wrong'">
      <div
        :class="['subj-tab', { active: currentSubject === 0 }]"
        @click="selectSubject(0)"
      >全部</div>
      <div
        v-for="s in subjects"
        :key="s.subject_id"
        :class="['subj-tab', { active: currentSubject === s.subject_id }]"
        @click="selectSubject(s.subject_id)"
      >{{ s.subject_name }}</div>
    </div>

    <!-- 错题列表 -->
    <main class="list" v-if="activeTab === 'wrong'">
      <div v-for="item in items" :key="item.wrong_id" class="card" @click="toggleDetail(item)">
        <div class="q-title">{{ item.question_content }}</div>
        <div class="q-meta">
          <span class="tag">{{ item.subject_name || '未分类' }}</span>
          <span class="tag" v-if="item.sub_category">{{ item.sub_category }}</span>
          <span class="tag">{{ item.question_type_detail || '' }}</span>
          <span class="err">错 {{ item.error_count }} 次</span>
        </div>
        <div v-if="expandedId === item.wrong_id" class="detail" @click.stop>
          <div class="detail-row"><b>答案：</b>{{ item.answer || '无' }}</div>
          <div class="detail-row" v-if="item.answer_analysis"><b>解析：</b>{{ item.answer_analysis }}</div>
          <div class="detail-actions">
            <button class="chop-btn" @click="chopQuestion(item.wrong_id)">斩题（已掌握）</button>
            <button class="remove-btn" @click="removeWrong(item.wrong_id)">移出错题</button>
          </div>
        </div>
      </div>
      <div v-if="!items.length && !loading" class="empty">暂无错题，继续加油！</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>

    <!-- 斩题记录 -->
    <main class="list" v-else>
      <div v-for="item in choppedItems" :key="item.wrong_id" class="card">
        <div class="q-title">{{ item.question_content }}</div>
        <div class="q-meta">
          <span class="tag">{{ item.subject_name || '未分类' }}</span>
          <span class="tag" :class="{ expiring: item.is_expiring }">{{ item.days_left }} 天后删除</span>
        </div>
        <button class="unchop-btn" @click="unchop(item.wrong_id)">恢复为错题</button>
      </div>
      <div v-if="!choppedItems.length && !loading" class="empty">暂无斩题记录</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const auth: any = (window as any).__VTJ_AUTH__;
const items = ref<any[]>([]);
const choppedItems = ref<any[]>([]);
const subjects = ref<any[]>([]);
const loading = ref(false);
const expandedId = ref<number | null>(null);
const activeTab = ref<'wrong' | 'chopped'>('wrong');
const currentSubject = ref(0);

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const toggleDetail = (item: any) => {
  expandedId.value = expandedId.value === item.wrong_id ? null : item.wrong_id;
};

const switchTab = (tab: 'wrong' | 'chopped') => {
  activeTab.value = tab;
  if (tab === 'chopped') fetchChopped();
};

const selectSubject = (sid: number) => {
  currentSubject.value = sid;
  fetchWrong();
};

async function fetchWrong() {
  loading.value = true;
  try {
    let url = '/api/wrong-questions?page=1&page_size=100';
    if (currentSubject.value > 0) url += '&subject_id=' + currentSubject.value;
    const res = await auth.apiFetch(url);
    const data = await res.json();
    if (res.ok && data.items) items.value = data.items;
  } catch (e) {
    console.error('获取错题失败:', e);
  } finally {
    loading.value = false;
  }
}

async function fetchChopped() {
  loading.value = true;
  try {
    const res = await auth.apiFetch('/api/wrong-questions/zhanti/list');
    const data = await res.json();
    if (res.ok) choppedItems.value = data.items || [];
  } catch (e) {
    console.error('获取斩题记录失败:', e);
  } finally {
    loading.value = false;
  }
}

async function fetchSubjects() {
  try {
    const res = await auth.apiFetch('/api/wrong-questions/subcategories');
    const data = await res.json();
    if (res.ok) subjects.value = data.items || [];
  } catch (e) {
    console.error('获取分类失败:', e);
  }
}

const chopQuestion = async (wrongId: number) => {
  try {
    await auth.apiFetch('/api/wrong-questions/' + wrongId + '/chop', { method: 'PUT' });
    expandedId.value = null;
    fetchWrong();
  } catch (e) {
    console.error('斩题失败:', e);
  }
};

const unchop = async (wrongId: number) => {
  try {
    await auth.apiFetch('/api/wrong-questions/' + wrongId + '/unchop', { method: 'POST' });
    fetchChopped();
  } catch (e) {
    console.error('恢复失败:', e);
  }
};

const removeWrong = async (wrongId: number) => {
  try {
    await auth.apiFetch('/api/wrong-questions/' + wrongId, { method: 'DELETE' });
    items.value = items.value.filter((i) => i.wrong_id !== wrongId);
    expandedId.value = null;
  } catch (e) {
    console.error('移出错题失败:', e);
  }
};

const goReview = () => {
  router.push('/mobile/wrong-review');
};

onMounted(() => {
  fetchWrong();
  fetchSubjects();
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
  position: sticky;
  top: 0;
  z-index: 10;
}
.back-btn { background: none; border: none; font-size: 22px; color: #1a2b5f; cursor: pointer; padding: 4px 8px; }
.title { font-size: 16px; font-weight: 600; color: #1a2b5f; margin: 0; }
.spacer { width: 32px; }

.review-bar { padding: 12px 12px 0; }
.review-btn {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 14px;
  background: linear-gradient(135deg, #1A365D 0%, #2a5298 100%);
  color: #fff;
  border: none;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}
.review-sub { font-size: 12px; font-weight: 400; opacity: 0.85; }

.tabs { display: flex; margin: 12px 12px 0; background: #fff; border-radius: 10px; padding: 4px; }
.tab { flex: 1; text-align: center; padding: 8px; font-size: 14px; color: #5a6488; cursor: pointer; border-radius: 8px; }
.tab.active { background: #1A365D; color: #fff; font-weight: 600; }

.subject-tabs { display: flex; gap: 8px; padding: 12px 12px 0; overflow-x: auto; }
.subj-tab { flex-shrink: 0; padding: 6px 14px; font-size: 13px; color: #5a6488; background: #fff; border-radius: 16px; cursor: pointer; }
.subj-tab.active { background: #1A365D; color: #fff; }

.list { flex: 1; padding: 12px; }
.card { background: #fff; border-radius: 12px; padding: 16px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04); cursor: pointer; }
.q-title { font-size: 15px; font-weight: 600; color: #1a2b5f; line-height: 1.5; margin-bottom: 8px; }
.q-meta { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
.tag { font-size: 12px; color: #5a6488; background: #f0f3f7; padding: 3px 8px; border-radius: 6px; }
.tag.expiring { color: #c41e3a; background: #fff2f0; }
.err { font-size: 12px; color: #c41e3a; }
.detail { margin-top: 12px; padding-top: 12px; border-top: 1px solid #f0f2f5; }
.detail-row { font-size: 13px; color: #5a6488; line-height: 1.6; margin-bottom: 6px; }
.detail-row b { color: #1a2b5f; }
.detail-actions { display: flex; gap: 8px; margin-top: 8px; }
.chop-btn { min-height: 36px; padding: 0 16px; background: #10b981; color: #fff; border: none; border-radius: 8px; font-size: 13px; cursor: pointer; }
.remove-btn, .unchop-btn { min-height: 36px; padding: 0 16px; border: 1px solid #ffccc7; background: #fff2f0; color: #c41e3a; border-radius: 8px; font-size: 13px; cursor: pointer; }
.unchop-btn { margin-top: 8px; }
.empty { text-align: center; color: #8899aa; padding: 40px 0; }
</style>
