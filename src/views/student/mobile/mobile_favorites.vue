<!-- 手机端收藏（按类型分类：新闻收藏 / 典题收藏 / 全部） -->
<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">收藏</h1>
      <span class="spacer"></span>
    </header>

    <!-- 类型分类：后端已把新闻收藏(NewsFavorite)与典题收藏(FavoriteQuestion)分表存储，
         原实现按「科目」过滤属于误用 —— 科目不是收藏的类型维度。 -->
    <div class="type-tabs">
      <div
        v-for="t in TYPE_TABS"
        :key="t.key"
        :class="['type-tab', { active: currentType === t.key }]"
        @click="selectType(t.key)"
      >{{ t.name }}</div>
    </div>

    <main class="list">
      <div v-for="item in filteredItems" :key="item.key" class="card">
        <div class="q-title">{{ item.title }}</div>
        <div class="q-meta" v-if="item.metaTags.length">
          <span class="tag" :class="{ news: item.type === 'news' }">{{ item.typeLabel }}</span>
          <span class="tag" v-for="(t, i) in item.metaTags" :key="i">{{ t }}</span>
        </div>
        <div class="q-answer" v-if="item.answer">答案：{{ item.answer }}</div>
        <button class="unfav-btn" @click="removeFav(item)">取消收藏</button>
      </div>
      <div v-if="!filteredItems.length && !loading" class="empty">{{ emptyText }}</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { renderQuestionSummary } from '@/utils/questionRender';
import { useNotesStore } from '@/modules/notes/store';

const router = useRouter();
const store = useNotesStore();

const loading = computed(() => store.loading);
const currentType = ref<'news' | 'question' | 'all'>('all');

// 新闻收藏与典题收藏是后端两张不同的表，字段结构也不同，
// 这里归一化成同一形状供列表渲染，避免模板里到处做类型判断。
type FavItem = {
  key: string;
  type: 'news' | 'question';
  typeLabel: string;
  favId: number;
  title: string;
  metaTags: string[];
  answer?: string;
  createTime: string;
};

const newsItems = computed<FavItem[]>(() =>
  store.newsFavorites
    .filter((it) => it.fav_type === 'news')
    .map((it) => ({
      key: 'n_' + it.fav_id,
      type: 'news' as const,
      typeLabel: '新闻',
      favId: it.fav_id,
      title: it.title || it.content || '未命名新闻',
      metaTags: [it.source, it.category].filter(Boolean) as string[],
      createTime: it.create_time || '',
    }))
);

const questionItems = computed<FavItem[]>(() =>
  store.questionFavorites.map((it) => ({
    key: 'q_' + it.fav_id,
    type: 'question' as const,
    typeLabel: '典题',
    favId: it.fav_id,
    title: renderQuestionSummary(it.question_content),
    metaTags: [it.subject_name, it.subcategory].filter(Boolean) as string[],
    answer: it.answer || '',
    createTime: it.create_time || '',
  }))
);

const TYPE_TABS = [
  { key: 'news', name: '新闻收藏' },
  { key: 'question', name: '典题收藏' },
  { key: 'all', name: '全部' },
] as const;

const filteredItems = computed<FavItem[]>(() => {
  if (currentType.value === 'news') return newsItems.value;
  if (currentType.value === 'question') return questionItems.value;
  return [...newsItems.value, ...questionItems.value].sort((a, b) =>
    String(b.createTime).localeCompare(String(a.createTime))
  );
});

const emptyText = computed(() => {
  if (currentType.value === 'news') return '暂无新闻收藏';
  if (currentType.value === 'question') return '暂无典题收藏';
  return '暂无收藏';
});

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const selectType = (key: 'news' | 'question' | 'all') => {
  currentType.value = key;
};

const fetchFavorites = async () => {
  try {
    await store.loadFavorites();
    if (store.error) console.error('获取收藏失败:', store.error);
  } catch (e) {
    console.error('获取收藏失败:', e);
  }
};

const removeFav = async (item: FavItem) => {
  try {
    await store.removeFavorite(item.favId, item.type);
  } catch (e) {
    console.error('取消收藏失败:', store.error || e);
  }
};

onMounted(fetchFavorites);
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

.type-tabs { display: flex; gap: 8px; padding: 12px 12px 0; }
.type-tab { flex-shrink: 0; padding: 6px 14px; font-size: 13px; color: #5a6488; background: #fff; border-radius: 16px; cursor: pointer; }
.type-tab.active { background: #1A365D; color: #fff; }

.list { flex: 1; padding: 12px; }
.card { background: #fff; border-radius: 12px; padding: 16px; margin-bottom: 12px; box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04); }
.q-title { font-size: 15px; font-weight: 600; color: #1a2b5f; line-height: 1.5; margin-bottom: 8px; }
.q-meta { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
.tag { font-size: 12px; color: #5a6488; background: #f0f3f7; padding: 3px 8px; border-radius: 6px; }
.tag.news { color: #1A365D; background: #e8eefc; }
.q-answer { font-size: 13px; color: #5a6488; margin-bottom: 8px; }
.unfav-btn { min-height: 36px; padding: 0 16px; border: 1px solid #ffccc7; background: #fff2f0; color: #c41e3a; border-radius: 8px; font-size: 13px; cursor: pointer; }
.empty { text-align: center; color: #8899aa; padding: 40px 0; }
</style>