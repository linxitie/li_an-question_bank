<template>
  <div class="mobile-news-page">
    <!-- 顶部导航 -->
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">{{ currentNews ? '新闻详情' : '每日新闻' }}</h1>
      <span class="spacer"></span>
    </header>

    <!-- 新闻列表 -->
    <main v-if="!currentNews" class="news-list">
      <div v-for="item in newsList" :key="item.id" class="news-item" @click="openDetail(item)">
        <div class="news-title">{{ item.title }}</div>
        <div class="news-meta">{{ item.source || '' }} · {{ formatTime(item.publish_date) }}</div>
      </div>
      <div v-if="!newsList.length && !loading" class="empty">暂无新闻</div>
      <div v-if="loading" class="empty">加载中...</div>
    </main>

    <!-- 新闻详情 -->
    <main v-else class="news-detail" @touchend="handleTextSelection">
      <h2 class="detail-title">{{ currentNews.title }}</h2>
      <div class="detail-meta">{{ currentNews.source || '' }} · {{ formatTime(currentNews.publish_date) }}</div>
      <div class="detail-content" v-html="renderedContent"></div>
      <div
        v-if="displayImages.length && !hasInlineMarkers"
        class="detail-images"
      >
        <img
          v-for="(src, idx) in displayImages"
          :key="src + '-' + idx"
          :src="src"
          :alt="'图片' + (idx + 1)"
        />
      </div>

      <!-- 选中文字操作菜单（5 色划线 + 想法） -->
      <div
        v-if="selectionMenuVisible"
        class="selection-menu"
        :style="{ top: menuPos.y + 'px', left: menuPos.x + 'px' }"
        @mousedown.prevent
        @touchstart.prevent
      >
        <button
          v-for="c in colors"
          :key="c"
          class="color-dot"
          :style="{ background: c }"
          @click="applyHighlight(c)"
        />
        <button class="note-btn" @click="openNoteInput">📝 想法</button>
      </div>

      <!-- 想法输入 -->
      <div v-if="noteInputVisible" class="note-input">
        <textarea v-model="noteText" class="note-textarea" placeholder="记录想法…" />
        <div class="note-actions">
          <button class="cancel" @click="cancelNoteInput">取消</button>
          <button class="save" @click="saveNote">保存</button>
        </div>
      </div>

      <!-- 笔记列表 -->
      <div v-if="notes.length" class="notes-section">
        <h4 class="notes-title">我的笔记 ({{ notes.length }})</h4>
        <div v-for="n in notes" :key="n.note_id" class="note-item">
          <blockquote v-if="n.quote_text" class="note-quote" :style="renderNoteStyle(n)">
            {{ n.quote_text }}
          </blockquote>
          <p v-if="n.note_text" class="note-text">{{ n.note_text }}</p>
          <button class="delete-btn" @click="removeNote(n.note_id)">删除</button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();

const newsList = ref<any[]>([]);
interface NewsImage { url?: string; order?: number; [key: string]: any; }
type NewsImageItem = string | NewsImage;
/** 图片项可能是纯 URL 字符串，也可能是带 url/order 的对象，统一取 URL */
function imageUrlOf(img: NewsImageItem): string {
  return typeof img === 'string' ? img : (img.url || '');
}
const currentNews = ref<{ id?: any; images?: NewsImageItem[]; [key: string]: any } | null>(null);
const loading = ref(false);
const notes = ref<any[]>([]);

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
 * 去重后的图片列表。
 * 采集端可能对同一张图重复入库（多条记录指向同一 URL），
 * 原实现直接把 currentNews.images 全部渲染出来，
 * 会出现「三张一模一样图片」。这里按解析后的 URL 去重并丢弃空值。
 */
const displayImages = computed(() => {
  const list = (currentNews.value && currentNews.value.images) || [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const img of list) {
    const url = resolveImg(imageUrlOf(img));
    if (!url) continue;
    if (seen.has(url)) continue;
    seen.add(url);
    out.push(url);
  }
  return out;
});

const renderedContent = computed(() => renderContent(currentNews.value && currentNews.value.content));

const goBack = () => {
  if (currentNews.value) {
    currentNews.value = null;
    notes.value = [];
  } else if (window.history.length > 1) {
    router.back();
  } else {
    router.push('/mobile/home');
  }
};

const formatTime = (iso: string) => {
  if (!iso) return '';
  const t = new Date(iso).getTime();
  if (isNaN(t)) return '';
  return new Date(iso).toLocaleDateString();
};

/**
 * 归一化图片地址。
 * 原实现是空操作（三元表达式两个分支都返回 url），协议相对地址 "//host/a.jpg"
 * 在部分浏览器/环境会被当作路径解析而裂图，这里做最小必要归一化。
 */
const resolveImg = (url: string) => {
  const u = (url || '').trim();
  if (!u) return '';
  // 协议相对地址补全为 https
  if (u.startsWith('//')) return 'https:' + u;
  return u;
};

const renderContent = (content: string) => {
  if (!content) return '';
  const images = (currentNews.value && currentNews.value.images) || [];
  const imageMap: Record<number, string> = {};
  for (const img of images) {
    if (typeof img === 'string') continue;
    if (img.order !== undefined && img.order !== null) imageMap[img.order] = imageUrlOf(img);
  }
  const paragraphs = content.split(/\n{2,}/);
  let html = '';
  for (const para of paragraphs) {
    const trimmed = para.trim();
    if (!trimmed) continue;
    const imgMatch = trimmed.match(/^\[\[IMG:(\d+)\]\]$/);
    if (imgMatch) {
      const order = parseInt(imgMatch[1], 10);
      const src = resolveImg(imageMap[order]);
      if (src) html += '<img src="' + src + '" alt="新闻图片" class="inline-img" />';
      continue;
    }
    const escaped = trimmed.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const withBreaks = escaped.replace(/\n/g, '<br/>');
    html += '<p>' + withBreaks + '</p>';
  }
  return html;
};

const fetchNews = async () => {
  loading.value = true;
  try {
    const res = await (window as any).__VTJ_AUTH__.apiFetch('/api/news?limit=20');
    const data = await res.json();
    if (res.ok && data.items) newsList.value = data.items;
  } catch (e) {
    console.error('获取新闻失败:', e);
  } finally {
    loading.value = false;
  }
};

const openDetail = async (item: any) => {
  currentNews.value = item;
  notes.value = [];
  // 若列表项已含完整 content 则直接用，否则请求详情
  if (!item.content) {
    try {
      const res = await (window as any).__VTJ_AUTH__.apiFetch('/api/news/' + item.id);
      const data = await res.json();
      if (res.ok) currentNews.value = data;
    } catch (e) {
      console.error('获取新闻详情失败:', e);
    }
  }
  await fetchNotes(item.id);
};

const handleTextSelection = () => {
  // 移动端 touchend 后延迟，等待 selection 完成
  setTimeout(() => {
    const sel = window.getSelection();
    const text = (sel && sel.toString() || '').trim();
    if (text.length > 0) {
      selectedText.value = text;
      const rect = sel!.getRangeAt(0).getBoundingClientRect();
      const menuW = 220;
      let x = rect.left + rect.width / 2 - menuW / 2;
      let y = rect.top - 60 + window.scrollY;
      if (x < 8) x = 8;
      if (x + menuW > window.innerWidth - 8) x = window.innerWidth - menuW - 8;
      if (y < window.scrollY + 8) y = rect.bottom + 8 + window.scrollY;
      menuPos.value = { x, y };
      selectionMenuVisible.value = true;
    } else {
      selectionMenuVisible.value = false;
      selectedText.value = '';
    }
  }, 50);
};

const applyHighlight = async (color: string) => {
  if (!selectedText.value || !currentNews.value) return;
  highlightColor.value = color;
  const newsId = currentNews.value.id;
  try {
    await (window as any).__VTJ_AUTH__.apiFetch('/api/news/' + newsId + '/note', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        note_text: '',
        quote_text: selectedText.value,
        color: color,
        line_style: lineStyle.value
      })
    });
    selectionMenuVisible.value = false;
    selectedText.value = '';
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
    await (window as any).__VTJ_AUTH__.apiFetch('/api/news/' + newsId + '/note', {
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
    selectedText.value = '';
    await fetchNotes(newsId);
  } catch (e) {
    console.error('保存想法失败:', e);
    noteInputVisible.value = false;
    noteText.value = '';
  }
};

const fetchNotes = async (newsId: number) => {
  try {
    const res = await (window as any).__VTJ_AUTH__.apiFetch('/api/news/' + newsId + '/notes');
    const data = await res.json();
    if (res.ok) notes.value = data.items || [];
  } catch (e) {
    console.error('获取笔记失败:', e);
  }
};

const removeNote = async (noteId: number) => {
  try {
    await (window as any).__VTJ_AUTH__.apiFetch('/api/news/notes/' + noteId, { method: 'DELETE' });
    notes.value = notes.value.filter((n) => n.note_id !== noteId);
  } catch (e) {
    console.error('删除笔记失败:', e);
  }
};

const renderNoteStyle = (note: any) => {
  const c = note.color || '#FFD700';
  if (note.line_style === 'wavy') return 'text-decoration: underline wavy ' + c + ';';
  if (note.line_style === 'straight') return 'text-decoration: underline ' + c + ';';
  if (note.line_style === 'marker') return 'background-color: ' + c + '40; padding: 0 2px;';
  return 'border-left: 3px solid ' + c + ';';
};

onMounted(() => {
  const id = route.params.id;
  if (id) {
    // 直接打开指定新闻详情
    (async () => {
      try {
        const res = await (window as any).__VTJ_AUTH__.apiFetch('/api/news/' + id);
        const data = await res.json();
        if (res.ok) {
          currentNews.value = data;
          await fetchNotes(Number(id));
        }
      } catch (e) {
        console.error('获取新闻失败:', e);
      }
    })();
  } else {
    fetchNews();
  }
});
</script>

<style scoped>
.mobile-news-page {
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
  font-size: 13px;
  color: #8899aa;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f2f5;
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
  background: linear-gradient(135deg, #1A365D 0%, #2a5298 100%);
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
