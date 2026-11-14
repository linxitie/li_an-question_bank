<template>
  <div class="mobile-news-page">
    <!-- 顶部导航 -->
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">{{ currentNews ? '新闻详情' : '每日新闻' }}</h1>
      <button v-if="!currentNews" class="timeline-btn" @click="openTimeline">
        时间线/日报
      </button>
      <router-link class="fav-link" :to="favoritesPath">收藏库</router-link>
      <span v-if="currentNews" class="spacer"></span>
    </header>

    <div v-if="route.params.id && detailLoading" class="detail-state">
      新闻详情加载中...
    </div>
    <div v-else-if="route.params.id && detailError" class="detail-state error">
      <span>{{ detailError }}</span>
      <button type="button" @click="loadDetail(String(route.params.id))">
        重试
      </button>
    </div>

    <form
      v-if="!currentNews && !route.params.id"
      class="news-search"
      @submit.prevent="searchNews">
      <input
        v-model="keyword"
        type="search"
        placeholder="搜索新闻标题、摘要、正文"
        aria-label="搜索新闻" />
      <button type="submit">搜索</button>
      <button
        v-if="keyword"
        type="button"
        class="clear-search"
        @click="clearSearch">
        清除
      </button>
    </form>

    <!-- 新闻列表 -->
    <main v-if="!currentNews && !route.params.id" class="news-list">
      <div
        v-for="item in newsList"
        :key="item.id"
        class="news-item"
        @click="openDetail(item)">
        <div class="news-title">{{ item.title }}</div>
        <div class="news-meta">
          {{ item.source || '' }} · {{ formatTime(item.publish_date) }}
        </div>
      </div>
      <div v-if="!newsList.length && !loading" class="empty">暂无新闻</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>

    <!-- 新闻详情 -->
    <main v-else-if="currentNews" class="news-detail">
      <h2 class="detail-title">{{ currentNews.title }}</h2>
      <div class="detail-meta">
        {{ currentNews.source || '' }} ·
        {{ formatTime(currentNews.publish_date) }}
        <button
          type="button"
          class="detail-favorite"
          :class="{ active: currentNews.is_favorited }"
          :aria-label="currentNews.is_favorited ? '取消收藏' : '收藏新闻'"
          @click="toggleFavorite">
          {{ currentNews.is_favorited ? '★' : '☆' }}
        </button>
      </div>
      <p v-if="favoriteError" class="favorite-error">{{ favoriteError }}</p>
      <NewsAICard
        v-if="hasAi"
        :summary="currentNews.ai_summary"
        :exam-points="currentNews.ai_exam_points"
        :entities="currentNews.ai_entities" />
      <div v-else class="ai-empty">
        <strong>AI 摘要与申论考点</strong>
        <span>该新闻暂无 AI 解析内容。</span>
      </div>
      <div
        ref="contentEl"
        class="detail-content"
        v-html="renderedContent"></div>
      <div
        v-if="displayImages.length && !hasInlineMarkers"
        class="detail-images">
        <img
          v-for="(src, idx) in displayImages"
          :key="src + '-' + idx"
          :src="src"
          :alt="'图片' + (idx + 1)" />
      </div>

      <!-- 选中文字操作菜单（5 色划线 + 想法） -->
      <div
        v-if="selectionMenuVisible"
        class="selection-menu"
        :style="{ top: menuPos.y + 'px', left: menuPos.x + 'px' }"
        @mousedown.prevent
        @touchstart.prevent>
        <button
          v-for="c in colors"
          :key="c"
          class="color-dot"
          :style="{ background: c }"
          @click="applyHighlight(c)" />
        <button class="note-btn" @click="openNoteInput">📝 想法</button>
      </div>

      <!-- 想法输入 -->
      <div v-if="noteInputVisible" class="note-input">
        <textarea
          v-model="noteText"
          class="note-textarea"
          placeholder="记录想法…" />
        <div class="note-actions">
          <button class="cancel" @click="cancelNoteInput">取消</button>
          <button class="save" @click="saveNote">保存</button>
        </div>
      </div>

      <!-- 笔记列表 -->
      <div v-if="notes.length" class="notes-section">
        <h4 class="notes-title">我的笔记 ({{ notes.length }})</h4>
        <div v-for="n in notes" :key="n.note_id" class="note-item">
          <blockquote
            v-if="n.quote_text"
            class="note-quote"
            :style="renderNoteStyle(n)">
            {{ n.quote_text }}
          </blockquote>
          <p v-if="n.note_text" class="note-text">{{ n.note_text }}</p>
          <button class="delete-btn" @click="removeNote(n.note_id)">
            删除
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { renderNewsContent, dedupeNewsImages } from '@/utils/newsRender';
import { useNewsStore } from '@/modules/news/store';
import type { NewsItem } from '@/modules/news/api';
import { toggleNewsFavorite } from '@/modules/news/api';
import NewsAICard from '@/components/news/NewsAICard.vue';

const route = useRoute();
const router = useRouter();
/** 每日新闻域 store：列表 / 详情 / 已读上报统一走本域，不直接摸 window.__VTJ_AUTH__ */
const newsStore = useNewsStore();

/** 列表与详情均以后端数据为准（已读状态来自后端 is_read，不落 localStorage） */
const newsList = computed<NewsItem[]>(() => newsStore.items);
const loading = computed(() => newsStore.loading);

interface NewsImage {
  url?: string;
  order?: number;
  [key: string]: any;
}
const currentNews = computed<NewsItem | null>(() => newsStore.selected);
const hasAi = computed(
  () =>
    !!currentNews.value &&
    Boolean(
      currentNews.value.ai_summary ||
      currentNews.value.ai_exam_points?.length ||
      currentNews.value.ai_entities?.length
    )
);
const notes = ref<any[]>([]);
const favoriteError = ref('');
const detailLoading = ref(Boolean(route.params.id));
const detailError = ref('');
const keyword = ref('');
const favoritesPath = computed(() =>
  route.path.startsWith('/tablet')
    ? '/tablet/news/favorites'
    : '/mobile/favorites'
);
/** 正文容器引用：划线时用于判定选区是否落在正文内 */
const contentEl = ref<HTMLElement | null>(null);

const selectedText = ref('');
const selectionMenuVisible = ref(false);
const menuPos = ref({ x: 0, y: 0 });
const highlightColor = ref('#FFD700');
const lineStyle = ref('wavy');
const noteInputVisible = ref(false);
const noteText = ref('');

const colors = ['#FFD700', '#4CAF50', '#2196F3', '#EF4444', '#8B5CF6'];

const hasInlineMarkers = computed(() => {
  const c = currentNews.value && currentNews.value.content;
  return !!c && /\[\[IMG:\d+\]\]/.test(c);
});

/**
 * 去重后的图片列表（仅在正文无内联标记时作为兜底展示）。
 * 逻辑已下沉到 src/utils/newsRender.js，三端共用同一实现。
 */
const displayImages = computed(() =>
  dedupeNewsImages((currentNews.value && currentNews.value.images) || [])
);

/** 已有划线的笔记 -> 注入正文高亮 */
const highlights = computed(() =>
  notes.value
    .filter((n) => n && n.quote_text)
    .map((n) => ({
      quote_text: n.quote_text,
      color: n.color,
      line_style: n.line_style
    }))
);

/** 正文渲染统一走 newsRender.js（其内部复用 questionRender.js 的 sanitizeHtml） */
const renderedContent = computed(() =>
  renderNewsContent(
    // content 缺失时传空串：renderNewsContent 首行会按空内容返回 ''，避免 string|null 入参
    (currentNews.value && currentNews.value.content) || '',
    (currentNews.value && currentNews.value.images) || [],
    highlights.value
  )
);

const goBack = () => {
  if (newsStore.selected) {
    newsStore.clearSelection();
    notes.value = [];
    selectionMenuVisible.value = false;
    selectedText.value = '';
    noteInputVisible.value = false;
    noteText.value = '';
  } else if (window.history.length > 1) {
    router.back();
  } else {
    router.push('/mobile/home');
  }
};

const openTimeline = () => {
  const target = route.path.startsWith('/tablet')
    ? '/tablet/news/timeline'
    : '/mobile/news/timeline';
  router.push(target);
};

const formatTime = (iso?: string | null) => {
  if (!iso) return '';
  const t = new Date(iso).getTime();
  if (isNaN(t)) return '';
  return new Date(iso).toLocaleDateString();
};

const fetchNews = async () => {
  // 列表只读，不上报阅读；已读标记由后端随列表返回
  await newsStore.load({
    limit: 50,
    keyword: keyword.value.trim() || undefined
  });
};

const searchNews = async () => {
  await fetchNews();
};

const clearSearch = async () => {
  keyword.value = '';
  await fetchNews();
};

const loadDetail = async (id: string): Promise<NewsItem | null> => {
  detailLoading.value = true;
  detailError.value = '';
  try {
    const detail = await newsStore.openArticle(id);
    if (!detail) {
      detailError.value = '新闻详情加载失败，请检查网络后重试';
      return null;
    }
    return detail;
  } catch (e) {
    detailError.value = e instanceof Error ? e.message : '新闻详情加载失败';
    return null;
  } finally {
    detailLoading.value = false;
  }
};

const openDetail = async (item: NewsItem) => {
  notes.value = [];
  const detail = await loadDetail(String(item.id));
  if (detail) await fetchNotes(detail.id);
};

/**
 * 划线：文档级 selectionchange。
 *
 * 原实现绑定 @touchend 后 setTimeout(50) 再读 window.getSelection()。
 * 触屏上 touchend 时刻选区通常尚未提交，getSelection() 返回空，
 * 表现为「长按划线永远不弹菜单」。
 * selectionchange 在选区提交时触发，触屏与鼠标行为统一，无需猜测延时。
 */
const handleSelectionChange = () => {
  if (!currentNews.value || !contentEl.value) return;
  const sel = window.getSelection();
  if (!sel) return;
  const text = (sel.toString() || '').trim();
  if (!text || text.length < 2) return; // 单字误触不弹菜单，也不清空已选内容
  // 仅响应正文内选区，避免选中标题等其它区域时误弹
  const anchor = sel.anchorNode;
  if (!anchor || !contentEl.value.contains(anchor)) {
    selectionMenuVisible.value = false;
    selectedText.value = '';
    return;
  }
  selectedText.value = text;
  // 菜单为 position: fixed，必须用视口坐标；原实现叠加 window.scrollY 会滚动后错位
  const range = sel.getRangeAt(0);
  const rect = range.getBoundingClientRect();
  const menuW = 220;
  let x = rect.left + rect.width / 2 - menuW / 2;
  let y = rect.top - 60;
  if (x < 8) x = 8;
  if (x + menuW > window.innerWidth - 8) x = window.innerWidth - menuW - 8;
  if (y < 8) y = rect.bottom + 8;
  if (y > window.innerHeight - 60) y = window.innerHeight - 60;
  menuPos.value = { x, y };
  selectionMenuVisible.value = true;
};

/** 关闭划线菜单并清空选区 */
const clearSelection = () => {
  selectionMenuVisible.value = false;
  selectedText.value = '';
  const sel = window.getSelection();
  if (sel) sel.removeAllRanges();
};

const applyHighlight = async (color: string) => {
  if (!selectedText.value || !currentNews.value) return;
  highlightColor.value = color;
  const newsId = currentNews.value.id;
  try {
    await (window as any).__VTJ_AUTH__.apiFetch(
      '/api/news/' + newsId + '/note',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          note_text: '',
          quote_text: selectedText.value,
          color: color,
          line_style: lineStyle.value
        })
      }
    );
    clearSelection();
    await fetchNotes(newsId);
  } catch (e) {
    console.error('保存划线失败:', e);
  }
};

const openNoteInput = () => {
  if (!selectedText.value) return;
  noteText.value = '';
  selectionMenuVisible.value = false;
  noteInputVisible.value = true;
};

const cancelNoteInput = () => {
  noteInputVisible.value = false;
  noteText.value = '';
};

const saveNote = async () => {
  const thought = noteText.value.trim();
  if (!thought || !currentNews.value) {
    cancelNoteInput();
    return;
  }
  const newsId = currentNews.value.id;
  try {
    await (window as any).__VTJ_AUTH__.apiFetch(
      '/api/news/' + newsId + '/note',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          note_text: thought,
          quote_text: selectedText.value,
          color: highlightColor.value,
          line_style: lineStyle.value
        })
      }
    );
    noteInputVisible.value = false;
    noteText.value = '';
    clearSelection();
    await fetchNotes(newsId);
  } catch (e) {
    console.error('保存想法失败:', e);
    noteInputVisible.value = false;
    noteText.value = '';
  }
};

async function toggleFavorite(): Promise<void> {
  if (!currentNews.value) return;
  favoriteError.value = '';
  try {
    const result = await toggleNewsFavorite(currentNews.value.id);
    currentNews.value.is_favorited = result.favorited;
  } catch (e) {
    favoriteError.value = e instanceof Error ? e.message : '收藏失败';
  }
}

const fetchNotes = async (newsId: number) => {
  try {
    const res = await (window as any).__VTJ_AUTH__.apiFetch(
      '/api/news/' + newsId + '/notes'
    );
    const data = await res.json();
    if (res.ok) notes.value = data.items || [];
  } catch (e) {
    console.error('获取笔记失败:', e);
  }
};

const removeNote = async (noteId: number) => {
  try {
    await (window as any).__VTJ_AUTH__.apiFetch('/api/news/notes/' + noteId, {
      method: 'DELETE'
    });
    notes.value = notes.value.filter((n) => n.note_id !== noteId);
  } catch (e) {
    console.error('删除笔记失败:', e);
  }
};

const renderNoteStyle = (note: any) => {
  const c = note.color || '#FFD700';
  if (note.line_style === 'wavy')
    return 'text-decoration: underline wavy ' + c + ';';
  if (note.line_style === 'straight')
    return 'text-decoration: underline ' + c + ';';
  if (note.line_style === 'marker')
    return 'background-color: ' + c + '40; padding: 0 2px;';
  return 'border-left: 3px solid ' + c + ';';
};

onMounted(() => {
  // 文档级选区监听：触屏划线唯一可靠入口
  document.addEventListener('selectionchange', handleSelectionChange);
  const id = route.params.id;
  if (id) {
    // 直接打开指定新闻详情（同样经详情端点上报阅读）
    (async () => {
      const detail = await loadDetail(String(id));
      if (detail) await fetchNotes(detail.id);
    })();
  } else {
    fetchNews();
  }
});

onBeforeUnmount(() => {
  document.removeEventListener('selectionchange', handleSelectionChange);
});
</script>

<style scoped>
.mobile-news-page {
  min-height: 100vh;
  background: #f5f7fa;
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
.timeline-btn {
  border: 1px solid #d6dfea;
  background: #fff;
  color: #1a2b5f;
  border-radius: 7px;
  padding: 5px 9px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}
.fav-link {
  padding: 5px 8px;
  color: #1a2b5f;
  font-size: 12px;
  text-decoration: none;
  white-space: nowrap;
}
.detail-state {
  margin: 16px 12px;
  padding: 14px;
  border-radius: 10px;
  background: #fff;
  color: #59635c;
  font-size: 13px;
  text-align: center;
}
.detail-state.error {
  color: #a33b2d;
}
.detail-state button {
  margin-left: 8px;
  border: 1px solid #d6dfea;
  border-radius: 6px;
  background: #fff;
  padding: 4px 8px;
  cursor: pointer;
}
.ai-empty {
  display: grid;
  gap: 4px;
  margin-bottom: 16px;
  padding: 12px 14px;
  border-radius: 10px;
  background: #f7faf8;
  color: #59635c;
  font-size: 12px;
}
.ai-empty strong {
  color: #1a2b5f;
  font-size: 13px;
}
.news-search {
  display: flex;
  gap: 6px;
  padding: 10px 12px 0;
}
.news-search input {
  flex: 1;
  min-width: 0;
  padding: 9px 10px;
  border: 1px solid #d6dfea;
  border-radius: 8px;
  background: #fff;
  color: #1a2b5f;
  font-size: 13px;
}
.news-search button {
  border: 1px solid #1a2b5f;
  border-radius: 8px;
  background: #1a2b5f;
  color: #fff;
  padding: 0 12px;
  font-size: 12px;
  cursor: pointer;
}
.news-search .clear-search {
  border-color: #d6dfea;
  background: #fff;
  color: #59635c;
}
.news-list {
  flex: 1;
  padding: 12px;
}
.news-item {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
}
.news-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  margin-bottom: 6px;
  line-height: 1.4;
}
.news-meta {
  font-size: 12px;
  color: #8899aa;
}
.empty {
  text-align: center;
  color: #8899aa;
  padding: 40px 0;
}
.news-detail {
  flex: 1;
  padding: 16px;
  background: #fff;
}
.detail-title {
  font-size: 20px;
  font-weight: 700;
  color: #1a2b5f;
  margin: 0 0 8px;
  line-height: 1.4;
}
.detail-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #8899aa;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f2f5;
}
.detail-favorite {
  margin-left: auto;
  border: 0;
  background: transparent;
  color: #a0a9b3;
  font-size: 20px;
  cursor: pointer;
}
.detail-favorite.active {
  color: #c8763f;
}
.favorite-error {
  margin: -8px 0 12px;
  color: #a33b2d;
  font-size: 12px;
}
.detail-content :deep(p) {
  font-size: 15px;
  line-height: 1.8;
  color: #1a2a3a;
  margin-bottom: 16px;
  text-indent: 2em;
}
.detail-content :deep(.inline-img) {
  max-width: 100%;
  border-radius: 8px;
  margin: 8px 0;
}
/* 划线回显：用 <span> 而非 <mark>，因为 mark 不在 sanitizeHtml 白名单内 */
.detail-content :deep(.news-hl) {
  border-radius: 2px;
  padding: 0 1px;
}
/* 标记存在但图片已随重复数据被清理时的占位 */
.detail-content :deep(.news-img-missing) {
  color: #8899aa;
  font-size: 13px;
}
.detail-images img {
  max-width: 100%;
  border-radius: 8px;
  margin: 8px 0;
  display: block;
}
.selection-menu {
  position: fixed;
  display: flex;
  gap: 6px;
  align-items: center;
  background: #1a2b5f;
  border-radius: 24px;
  padding: 8px 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  z-index: 100;
}
.color-dot {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  border: 2px solid #fff;
  cursor: pointer;
  padding: 0;
}
.note-btn {
  background: rgba(255, 255, 255, 0.15);
  border: none;
  color: #fff;
  font-size: 13px;
  border-radius: 14px;
  padding: 5px 10px;
  cursor: pointer;
  margin-left: 4px;
}
.note-input {
  position: fixed;
  left: 16px;
  right: 16px;
  bottom: 20px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  padding: 12px;
  z-index: 100;
}
.note-textarea {
  width: 100%;
  min-height: 72px;
  border: 1px solid #e8ecf1;
  border-radius: 8px;
  padding: 10px;
  font-size: 14px;
  font-family: inherit;
  outline: none;
  resize: none;
}
.note-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
.note-actions button {
  min-height: 36px;
  padding: 0 16px;
  border-radius: 8px;
  border: none;
  font-size: 14px;
  cursor: pointer;
}
.note-actions .cancel {
  background: #f5f7fa;
  color: #5a6488;
}
.note-actions .save {
  background: linear-gradient(135deg, #1a365d 0%, #2a5298 100%);
  color: #fff;
}
.notes-section {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #f0f2f5;
}
.notes-title {
  font-size: 14px;
  color: #5a6488;
  margin: 0 0 12px;
}
.note-item {
  background: #f8f9fc;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
  position: relative;
}
.note-quote {
  margin: 0 0 8px;
  padding: 4px 8px;
  font-size: 14px;
  color: #1a2b5f;
  border-radius: 4px;
}
.note-text {
  margin: 0;
  font-size: 13px;
  color: #5a6488;
  line-height: 1.6;
}
.delete-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  background: none;
  border: none;
  color: #c41e3a;
  font-size: 12px;
  cursor: pointer;
}
</style>
