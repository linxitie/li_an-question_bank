<template>
  <div class="news-detail-page">
    <header class="detail-head">
      <button class="back-btn" type="button" aria-label="返回" @click="goBack">
        ←
      </button>
      <h1>新闻详情</h1>
    </header>

    <div v-if="error" class="state error">
      <p>{{ error }}</p>
      <button type="button" @click="load">重试</button>
    </div>
    <div v-else-if="loading" class="state">加载中...</div>

    <article v-else-if="item" class="detail-card">
      <div class="title-row">
        <h2>{{ item.title }}</h2>
        <button
          class="fav-btn"
          :class="{ active: item.is_favorited }"
          type="button"
          :aria-label="item.is_favorited ? '取消收藏' : '收藏'"
          @click="toggleFavorite">
          {{ item.is_favorited ? '★' : '☆' }}
        </button>
      </div>

      <div class="meta">
        <span>{{ sourceLabel(item.source) }}</span>
        <span v-if="item.category">{{ item.category }}</span>
        <span>{{ formatDate(item.publish_date) }}</span>
      </div>

      <p v-if="favoriteError" class="favorite-error">{{ favoriteError }}</p>

      <NewsAICard
        v-if="hasAi"
        :summary="item.ai_summary"
        :exam-points="item.ai_exam_points"
        :entities="item.ai_entities" />

      <div ref="contentEl" class="content" v-html="renderedContent"></div>

      <div
        v-if="selectionMenuVisible"
        class="selection-menu"
        :style="{ top: menuPos.y + 'px', left: menuPos.x + 'px' }"
        @mousedown.prevent>
        <button
          v-for="color in colors"
          :key="color"
          type="button"
          class="color-dot"
          :style="{ background: color }"
          :aria-label="`使用${color}划线`"
          @click="applyHighlight(color)" />
        <button type="button" class="note-btn" @click="openNoteInput">
          写想法
        </button>
      </div>

      <div v-if="noteInputVisible" class="note-input">
        <textarea
          v-model="noteText"
          rows="3"
          placeholder="记录你的想法…"
          @blur="saveNote" />
        <div class="note-input__actions">
          <button type="button" @click="noteInputVisible = false">取消</button>
          <button type="button" class="save" @click="saveNote">保存</button>
        </div>
      </div>

      <div v-if="notes.length" class="notes-section">
        <h3>我的笔记（{{ notes.length }}）</h3>
        <div v-for="note in notes" :key="note.note_id" class="note-item">
          <blockquote v-if="note.quote_text" :style="renderNoteStyle(note)">
            {{ note.quote_text }}
          </blockquote>
          <p v-if="note.note_text">{{ note.note_text }}</p>
          <button
            type="button"
            class="note-delete"
            @click="removeNote(note.note_id)">
            删除
          </button>
        </div>
      </div>

      <div v-if="displayImages.length && !hasInlineMarkers" class="images">
        <img
          v-for="(src, index) in displayImages"
          :key="src + '-' + index"
          :src="src"
          :alt="'新闻图片' + (index + 1)"
          loading="lazy" />
      </div>

      <a
        class="source-link"
        :href="item.url"
        target="_blank"
        rel="noopener noreferrer">
        查看原文 ↗
      </a>
    </article>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  fetchNewsDetail,
  toggleNewsFavorite,
  type NewsItem
} from '@/modules/news/api';
import { dedupeNewsImages, renderNewsContent } from '@/utils/newsRender';
import NewsAICard from '@/components/news/NewsAICard.vue';

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const error = ref('');
const favoriteError = ref('');
const item = ref<NewsItem | null>(null);
const contentEl = ref<HTMLElement | null>(null);
const notes = ref<any[]>([]);
const selectionMenuVisible = ref(false);
const menuPos = ref({ x: 0, y: 0 });
const selectedText = ref('');
const noteInputVisible = ref(false);
const noteText = ref('');
const highlightColor = ref('#FFD700');
const lineStyle = ref('wavy');
const colors = ['#FFD700', '#4CAF50', '#2196F3', '#EF4444', '#8B5CF6'];

const displayImages = computed(() =>
  dedupeNewsImages(item.value?.images || [])
);
const hasInlineMarkers = computed(() => {
  const content = item.value?.content || '';
  return /\[\[IMG:\d+\]\]/.test(content);
});
const renderedContent = computed(() =>
  renderNewsContent(
    item.value?.content || '',
    item.value?.images || [],
    notes.value
      .filter((note) => note && note.quote_text)
      .map((note) => ({
        quote_text: note.quote_text,
        color: note.color,
        line_style: note.line_style
      }))
  )
);
const hasAi = computed(() =>
  Boolean(
    item.value?.ai_summary ||
    item.value?.ai_exam_points?.length ||
    item.value?.ai_entities?.length
  )
);

function sourceLabel(source: string): string {
  const labels: Record<string, string> = {
    xinhua: '新华网',
    people: '人民网',
    mps: '公安部',
    beijing: '北京市公安局',
    guangdong: '广东省公安厅',
    shandong: '山东省公安厅',
    henan: '河南省公安厅',
    sichuan: '四川省公安厅',
    tianjin: '天津市公安局',
    hebei: '河北省公安厅',
    shanghai: '上海市公安局',
    jiangsu: '江苏省公安厅',
    zhejiang: '浙江省公安厅',
    fujian: '福建省公安厅',
    hubei: '湖北省公安厅',
    hunan: '湖南省公安厅',
    cpd: '人民公安报'
  };
  return labels[source] || source || '未知来源';
}

function formatDate(value: string | null): string {
  return value ? value.slice(0, 10) : '';
}

function goBack(): void {
  router.replace('/home');
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = '';
  favoriteError.value = '';
  try {
    item.value = await fetchNewsDetail(String(route.params.id));
    if (item.value) await fetchNotes(item.value.id);
  } catch (e) {
    error.value = e instanceof Error ? e.message : '新闻加载失败';
  } finally {
    loading.value = false;
  }
}

function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  const auth = (window as any).__VTJ_AUTH__;
  if (auth?.apiFetch) return auth.apiFetch(url, init);
  return fetch(url, init);
}

async function fetchNotes(newsId: number): Promise<void> {
  try {
    const response = await apiFetch(`/api/news/${newsId}/notes`);
    if (response.ok) {
      const data = await response.json();
      notes.value = data.items || [];
    }
  } catch {
    // 笔记失败不影响正文
  }
}

function handleSelectionChange(): void {
  if (!item.value || !contentEl.value) return;
  const selection = window.getSelection();
  if (!selection) return;
  const text = (selection.toString() || '').trim();
  if (text.length < 2) {
    selectionMenuVisible.value = false;
    return;
  }
  const anchor = selection.anchorNode;
  if (!anchor || !contentEl.value.contains(anchor)) {
    selectionMenuVisible.value = false;
    return;
  }
  selectedText.value = text;
  const range = selection.getRangeAt(0);
  const rect = range.getBoundingClientRect();
  const menuWidth = 230;
  let x = rect.left + rect.width / 2 - menuWidth / 2;
  let y = rect.top - 58;
  if (x < 8) x = 8;
  if (x + menuWidth > window.innerWidth - 8) {
    x = window.innerWidth - menuWidth - 8;
  }
  if (y < 8) y = rect.bottom + 8;
  menuPos.value = { x, y };
  selectionMenuVisible.value = true;
}

function clearSelection(): void {
  selectionMenuVisible.value = false;
  selectedText.value = '';
  window.getSelection()?.removeAllRanges();
}

async function applyHighlight(color: string): Promise<void> {
  if (!selectedText.value || !item.value) return;
  highlightColor.value = color;
  try {
    await apiFetch(`/api/news/${item.value.id}/note`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        note_text: '',
        quote_text: selectedText.value,
        color,
        line_style: lineStyle.value
      })
    });
    clearSelection();
    await fetchNotes(item.value.id);
  } catch {
    // 失败不阻断阅读
  }
}

function openNoteInput(): void {
  if (!selectedText.value) return;
  noteText.value = '';
  selectionMenuVisible.value = false;
  noteInputVisible.value = true;
}

async function saveNote(): Promise<void> {
  const thought = noteText.value.trim();
  if (!thought || !item.value) {
    noteInputVisible.value = false;
    return;
  }
  try {
    await apiFetch(`/api/news/${item.value.id}/note`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        note_text: thought,
        quote_text: selectedText.value,
        color: highlightColor.value,
        line_style: lineStyle.value
      })
    });
    noteInputVisible.value = false;
    noteText.value = '';
    await fetchNotes(item.value.id);
  } catch {
    // 保留输入
  }
}

async function removeNote(noteId: number): Promise<void> {
  try {
    await apiFetch(`/api/news/notes/${noteId}`, { method: 'DELETE' });
    notes.value = notes.value.filter((note) => note.note_id !== noteId);
  } catch {
    // 失败不删除
  }
}

function renderNoteStyle(note: any): string {
  const color = note.color || '#FFD700';
  if (note.line_style === 'wavy')
    return `text-decoration: underline wavy ${color};`;
  if (note.line_style === 'straight')
    return `text-decoration: underline ${color};`;
  if (note.line_style === 'marker')
    return `background: ${color}40; padding: 0 2px;`;
  return `border-left: 3px solid ${color};`;
}

async function toggleFavorite(): Promise<void> {
  if (!item.value) return;
  favoriteError.value = '';
  const current = item.value;
  try {
    const result = await toggleNewsFavorite(current.id);
    current.is_favorited = result.favorited;
  } catch (e) {
    favoriteError.value =
      e instanceof Error ? e.message : '收藏失败，请稍后重试';
  }
}

onMounted(() => {
  document.addEventListener('selectionchange', handleSelectionChange);
  void load();
});

onBeforeUnmount(() => {
  document.removeEventListener('selectionchange', handleSelectionChange);
});
</script>

<style scoped>
.news-detail-page {
  max-width: 880px;
  margin: 0 auto;
  padding: 24px 18px 64px;
  min-height: 100vh;
  box-sizing: border-box;
  background: #fbfaf7;
  color: #1f2321;
}

.detail-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 18px;
}

.back-btn {
  border: 0;
  background: transparent;
  color: #2f5d50;
  font-size: 22px;
  cursor: pointer;
  padding: 4px 6px;
}

.detail-head h1 {
  margin: 0;
  font-size: 20px;
}

.detail-card {
  padding: 24px;
  border: 1px solid #e6e1d8;
  border-radius: 14px;
  background: #fff;
}

.title-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.title-row h2 {
  flex: 1;
  margin: 0;
  font-size: 25px;
  line-height: 1.4;
}

.fav-btn {
  flex: 0 0 36px;
  width: 36px;
  height: 36px;
  border: 1px solid #e6e1d8;
  border-radius: 50%;
  background: #fbfaf7;
  color: #8a908b;
  font-size: 18px;
  cursor: pointer;
}

.fav-btn.active {
  color: #c8763f;
  background: #fbf0e7;
  border-color: #e8c3a9;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
  color: #8a908b;
  font-size: 13px;
}

.favorite-error {
  margin: 10px 0 0;
  color: #a33b2d;
  font-size: 13px;
}

.ai-panel {
  margin-top: 20px;
  padding: 16px 18px;
  border: 1px solid #e6e1d8;
  border-radius: 12px;
  background: #faf8f3;
}

.ai-panel__head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.ai-panel__label {
  color: #2f5d50;
  font-size: 14px;
  font-weight: 700;
}

.ai-status {
  padding: 2px 7px;
  border-radius: 999px;
  background: #e8f1ec;
  color: #2f5d50;
  font-size: 11px;
}

.ai-block + .ai-block {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #eee9df;
}

.ai-block h3 {
  margin: 0 0 6px;
  color: #49524c;
  font-size: 13px;
  font-weight: 700;
}

.ai-block p,
.ai-block ul {
  margin: 0;
  color: #3f4742;
  font-size: 14px;
  line-height: 1.8;
}

.ai-block ul {
  padding-left: 20px;
}

.entity-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.entity-tag {
  padding: 3px 8px;
  border-radius: 6px;
  background: #fff;
  border: 1px solid #e3ddd2;
  color: #535b55;
  font-size: 12px;
}

.entity-tag small {
  margin-right: 4px;
  color: #9aa09c;
  font-size: 10px;
  text-transform: uppercase;
}

.risk-block h3 {
  color: #a33b2d;
}

.risk-block li {
  color: #8e4b3a;
}

.selection-menu {
  position: fixed;
  z-index: 30;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 7px 9px;
  border: 1px solid #e6e1d8;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(31, 35, 33, 0.16);
}

.color-dot {
  width: 19px;
  height: 19px;
  padding: 0;
  border: 2px solid #fff;
  border-radius: 50%;
  box-shadow: 0 0 0 1px #e6e1d8;
  cursor: pointer;
}

.note-btn {
  padding: 4px 8px;
  border: 0;
  border-radius: 6px;
  background: #eef3f0;
  color: #2f5d50;
  font-size: 12px;
  cursor: pointer;
}

.note-input {
  margin: 14px 0;
  padding: 12px;
  border: 1px solid #e6e1d8;
  border-radius: 10px;
  background: #faf8f3;
}

.note-input textarea {
  box-sizing: border-box;
  width: 100%;
  padding: 8px;
  border: 1px solid #e3ded4;
  border-radius: 7px;
  outline: none;
  resize: vertical;
  font-size: 13px;
}

.note-input__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

.note-input__actions button {
  padding: 5px 10px;
  border: 1px solid #d9d3c8;
  border-radius: 6px;
  background: #fff;
  color: #59635c;
  font-size: 12px;
  cursor: pointer;
}

.note-input__actions .save {
  border-color: #2f5d50;
  background: #2f5d50;
  color: #fff;
}

.notes-section {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f1eee7;
}

.notes-section h3 {
  margin: 0 0 10px;
  color: #34413a;
  font-size: 14px;
}

.note-item {
  margin-bottom: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #faf8f3;
}

.note-item blockquote {
  margin: 0 0 5px;
  color: #59635c;
  font-size: 13px;
  line-height: 1.7;
}

.note-item p {
  margin: 0;
  color: #3f4742;
  font-size: 13px;
  line-height: 1.7;
}

.note-delete {
  margin-top: 5px;
  padding: 0;
  border: 0;
  background: transparent;
  color: #a09a90;
  font-size: 12px;
  cursor: pointer;
}

.content {
  margin-top: 22px;
  font-size: 16px;
  line-height: 1.9;
  overflow-wrap: anywhere;
}

.content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}

.images {
  display: grid;
  gap: 12px;
  margin-top: 20px;
}

.images img {
  max-width: 100%;
  height: auto;
  border-radius: 8px;
}

.source-link {
  display: inline-block;
  margin-top: 24px;
  color: #2f5d50;
  font-size: 14px;
}

.state {
  padding: 48px 12px;
  text-align: center;
  color: #737a75;
}

.state.error {
  color: #a33b2d;
}

.state.error button {
  margin-top: 10px;
  border: 1px solid #c8763f;
  background: #fff;
  color: #a0522d;
  border-radius: 8px;
  padding: 7px 14px;
  cursor: pointer;
}

@media (max-width: 640px) {
  .news-detail-page {
    padding: 14px 12px 48px;
  }

  .detail-card {
    padding: 16px;
  }

  .title-row h2 {
    font-size: 20px;
  }
}
</style>
