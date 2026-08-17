<!-- 每日金句模块 -->
<template>
  <div class="quote-banner">
    <div class="quote-header">
      <div class="quote-source">
        <XIcon :icon="ReadingLamp" :size="18" color="#c41e3a"></XIcon>
        <span>每日金句</span>
      </div>
      <span class="quote-date"> {{ state.currentDate }}</span>
    </div>
    <div class="quote-body">
      <div class="quote-mark left-mark">“</div>
      <p class="quote-text">
        {{ state.quote }}
      </p>
      <div class="quote-mark right-mark">”</div>
    </div>
    <div class="quote-footer">
      <span class="quote-author">
        <span>
          <span> ——</span>
          <span> {{ state.author }}</span></span
        ></span
      >
      <div class="quote-footer-actions">
        <button class="quote-fav-btn" :class="{ favorited: state.quoteFavorited }" @click="toggleQuoteFavorite" :title="state.quoteFavorited ? '取消收藏' : '收藏金句'">
          {{ state.quoteFavorited ? '⭐' : '☆' }}
        </button>
        <button class="refresh-btn" @click="refreshQuote" :disabled="state.quoteLoading">
          <XIcon :icon="RefreshRight" :size="14" color="#c41e3a"></XIcon>
          <span> {{ state.quoteLoading ? '加载中...' : '换一句' }}</span>
        </button>
      </div>
    </div>
    <!-- 每日新闻 -->
    <div class="news-section">
      <div class="news-header">
        <XIcon :icon="Document" :size="16" color="#c41e3a"></XIcon>
        <span class="news-title">每日新闻</span>
        <span class="news-badge" v-if="state.newsItems.length">共 {{ state.newsItems.length }} 条</span>
      </div>
      <div class="news-list" v-if="state.newsItems.length">
        <div v-for="(n, idx) in state.newsItems" :key="idx"
             class="news-item" @click="openNewsDetail(n)">
          <span class="news-dot"></span>
          <span class="news-text" :title="n.title">{{ n.title.length > 20 ? n.title.substring(0, 20) + '...' : n.title }}</span>
          <span class="news-source">{{ n.source === 'cpd' ? '公安报' : '人民网' }}</span>
        </div>
      </div>
      <div class="news-empty" v-else>
        <span>新闻加载中...</span>
      </div>
    </div>
    <div class="quote-decoration"></div>

    <!-- 新闻详情弹窗 -->
    <div class="news-modal-overlay" v-if="state.showNewsModal" @click.self="closeNewsDetail">
      <div class="news-modal">
        <div class="news-modal-header">
          <h3 class="news-modal-title">{{ state.selectedNews.title }}</h3>
          <div class="news-modal-header-actions">
            <button :class="'news-fav-btn ' + (state.isFavorited ? 'favorited' : '')" @click="toggleFavorite" :title="state.isFavorited ? '取消收藏' : '收藏'">{{ state.isFavorited ? '⭐' : '☆' }}</button>
            <button class="news-note-btn" @click="state.showHint = !state.showHint" title="划线/想法说明">📝</button>
            <button class="news-modal-close" @click="closeNewsDetail">×</button>
          </div>
        </div>
        <div v-if="state.showHint" class="news-hint-bubble">
          <span>💡 选中正文文字 → 点颜色即划线（自动保存）；点「📝 想法」输入后失焦自动保存。</span>
          <button class="news-hint-notes" @click="scrollToNotes">查看我的笔记 ↓</button>
        </div>
        <div class="news-modal-meta">
          <span class="news-modal-source-badge">{{ state.selectedNews.source === 'cpd' ? '人民公安报' : '人民网' }}</span>
          <span class="news-modal-date" v-if="state.selectedNews.publish_date">{{ state.selectedNews.publish_date.substring(0, 10) }}</span>
        </div>
        <div class="news-modal-body" @mouseup="handleTextSelection" @touchend="handleTextSelection">
          <div v-if="state.selectedNews.content" class="news-modal-content" v-html="renderContent(state.selectedNews.content)"></div>
          <p v-else class="news-modal-content">{{ state.selectedNews.summary || '暂无内容' }}</p>
          <div v-if="state.selectedNews.images && state.selectedNews.images.length && !hasInlineMarkers(state.selectedNews.content)" class="news-modal-images">
            <img v-for="(img, idx) in state.selectedNews.images" :key="idx" :src="resolveImgUrl(img.url || img)" :alt="'图片' + (idx + 1)" class="news-content-img" />
          </div>
        </div>
        <!-- 选中文本操作菜单（5色+3线型，点颜色即划线保存） -->
        <div v-if="state.selectionMenuVisible" class="selection-menu" :style="{ top: state.selectionMenuPos.y + 'px', left: state.selectionMenuPos.x + 'px' }" @mousedown.prevent>
          <div class="sel-menu-row sel-colors-row">
            <button class="sel-color-dot" style="background:#FFD700" :class="{active: state.highlightColor==='#FFD700'}" @click="applyHighlight('#FFD700')" title="黄色划线"></button>
            <button class="sel-color-dot" style="background:#4CAF50" :class="{active: state.highlightColor==='#4CAF50'}" @click="applyHighlight('#4CAF50')" title="绿色划线"></button>
            <button class="sel-color-dot" style="background:#2196F3" :class="{active: state.highlightColor==='#2196F3'}" @click="applyHighlight('#2196F3')" title="蓝色划线"></button>
            <button class="sel-color-dot" style="background:#EF4444" :class="{active: state.highlightColor==='#EF4444'}" @click="applyHighlight('#EF4444')" title="红色划线"></button>
            <button class="sel-color-dot" style="background:#8B5CF6" :class="{active: state.highlightColor==='#8B5CF6'}" @click="applyHighlight('#8B5CF6')" title="紫色划线"></button>
          </div>
          <div class="sel-menu-row sel-styles-row">
            <button :class="['sel-style-btn', {active: state.lineStyle==='wavy'}]" @click="setLineStyle('wavy')">〰️ 波浪线</button>
            <button :class="['sel-style-btn', {active: state.lineStyle==='straight'}]" @click="setLineStyle('straight')">＿ 直线</button>
            <button :class="['sel-style-btn', {active: state.lineStyle==='marker'}]" @click="setLineStyle('marker')">🖍️ 马克笔</button>
          </div>
          <div class="sel-menu-row sel-actions-row">
            <button class="sel-action-btn" @click="openNoteInput">📝 想法</button>
          </div>
        </div>
        <!-- 想法输入气泡（失焦自动保存） -->
        <div v-if="state.noteInputVisible" class="note-input-bubble" :style="{ top: state.selectionMenuPos.y + 'px', left: state.selectionMenuPos.x + 'px' }" @mousedown.stop>
          <textarea v-model="state.noteText" class="note-input-textarea" placeholder="记录想法…（失焦自动保存）" @blur="saveNoteOnBlur" @keydown.enter.exact.prevent="saveNoteOnBlur"></textarea>
          <div class="note-input-actions">
            <button class="note-input-cancel" @mousedown.prevent="cancelNoteInput">✕ 取消</button>
          </div>
        </div>
        <!-- 笔记列表 -->
        <div v-if="state.notes.length" class="news-notes-section">
          <h4 class="news-notes-title">我的笔记 ({{ state.notes.length }})</h4>
          <div v-for="note in state.notes" :key="note.note_id" class="news-note-item">
            <blockquote v-if="note.quote_text" class="note-quote" :style="renderNoteStyle(note)">{{ note.quote_text }}</blockquote>
            <p class="note-text">{{ note.note_text }}</p>
            <button class="note-delete-btn" @click="removeNote(note.note_id)">删除</button>
          </div>
        </div>
        <div class="news-modal-footer">
          <a :href="state.selectedNews.url" target="_blank" class="news-modal-link">查看原文</a>
          <button class="news-modal-btn" @click="closeNewsDetail">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { ReadingLamp, RefreshRight, Document, Close } from '@vtj/icons';
  import { useProvider } from '@vtj/renderer';
  import { ElMessage } from 'element-plus';
  export default defineComponent({
    name: 'QuoteBanner',
    components: { XIcon },
    setup(props) {
      const provider = useProvider({ id: 'quote_banner', version: '1778918000716' });
      const state = reactive({
        quote: '正在加载今日金句...',
        author: '',
        quoteId: 0,
        quoteFavorited: false,
        quoteLoading: false,
        currentDate: '',
        newsItems: [],
        showNewsModal: false,
        selectedNews: {},
        isFavorited: false,
        notes: [],
        selectionMenuVisible: false,
        selectionMenuPos: { x: 0, y: 0 },
        selectedText: '',
        highlightColor: '#FFD700',
        lineStyle: 'wavy',
        showHint: false,
        noteInputVisible: false,
        noteText: '',
        obsidianId: '',
        obsidianSource: '',
        sourceType: 'database'
      });
      return { state, props, provider, ReadingLamp, RefreshRight, Document, Close };
    },
    methods: {
      formatDate() {
        const d = new Date();
        this.state.currentDate = `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`;
      },
      async refreshQuote() {
        if (this.state.quoteLoading) return;
        this.state.quoteLoading = true;
        try {
          // 首页金句匿名可访问，使用普通 fetch；登录态会通过 cookie/header 自动带 token
          const auth = window.__VTJ_AUTH__;
          const headers = {};
          if (auth && auth.isLoggedIn && auth.isLoggedIn()) {
            Object.assign(headers, auth.getJsonHeaders());
          }
          // 辅助函数：安全解析 JSON（检查 Content-Type）
          const safeJson = async (response) => {
            const ct = response.headers.get('content-type') || '';
            if (!ct.includes('application/json')) {
              throw new Error('服务端返回非 JSON 响应');
            }
            return response.json();
          };
          // 优先从 Obsidian 知识库获取每日金句，失败时回退到随机金句
          let res = await fetch('/api/quotes/quote/daily', { headers });
          if (res.ok) {
            const data = await safeJson(res);
            this.state.quote = data.content || '暂无金句';
            this.state.author = data.author || data.source || '佚名';
            this.state.quoteId = data.quote_id || 0;
            this.state.quoteFavorited = !!data.favorited;
            // 存储 Obsidian 金句信息
            this.state.obsidianId = data.obsidian_id || '';
            this.state.obsidianSource = data.obsidian_source || '';
            this.state.sourceType = data.source_type || 'database';
            return;
          }
          // daily 接口失败，回退到随机金句
          res = await fetch('/api/quotes/random', { headers });
          if (!res.ok) throw new Error('获取金句失败');
          const data = await safeJson(res);
          this.state.quote = data.content || '暂无金句';
          this.state.author = data.author || data.source || '佚名';
          this.state.quoteId = data.quote_id || 0;
          this.state.quoteFavorited = !!data.favorited;
          this.state.obsidianId = '';
          this.state.obsidianSource = '';
          this.state.sourceType = 'database';
        } catch (e) {
          console.warn('获取金句失败:', e);
          // 失败时使用兜底金句，避免空白
          if (!this.state.quote || this.state.quote === '正在加载今日金句...') {
            this.state.quote = '忠诚是公安队伍代代相传的政治基因，是融入血脉的人民警察之魂。';
            this.state.author = '人民公安报';
          }
        } finally {
          this.state.quoteLoading = false;
        }
      },
      async toggleQuoteFavorite() {
        const auth = window.__VTJ_AUTH__;
        if (!auth || !auth.isLoggedIn || !auth.isLoggedIn()) {
          ElMessage.warning('请先登录后再收藏金句');
          return;
        }

        // 数据库金句收藏
        if (this.state.quoteId) {
          try {
            const res = await auth.apiFetch('/api/quotes/' + this.state.quoteId + '/favorite', { method: 'POST' });
            const data = await res.json();
            this.state.quoteFavorited = data.favorited;
            ElMessage.success(data.favorited ? '已收藏金句' : '已取消收藏');
          } catch (e) {
            console.error('收藏金句失败:', e);
          }
          return;
        }

        // Obsidian 金句收藏
        if (this.state.obsidianSource) {
          try {
            const res = await auth.apiFetch('/api/quotes/obsidian/' + encodeURIComponent(this.state.obsidianSource) + '/favorite', { method: 'POST' });
            const data = await res.json();
            this.state.quoteFavorited = data.favorited;
            ElMessage.success(data.favorited ? '已收藏金句' : '已取消收藏');
          } catch (e) {
            console.error('收藏金句失败:', e);
          }
          return;
        }

        ElMessage.warning('无法收藏当前金句');
      },
      openNewsDetail(news) {
        this.state.selectedNews = news;
        this.state.showNewsModal = true;
        this.state.isFavorited = news.is_favorited || false;
        this.state.notes = [];
        this.state.selectionMenuVisible = false;
        this.state.noteInputVisible = false;
        this.state.showHint = false;
        this.fetchNotes(news.id);
      },
      closeNewsDetail() {
        this.state.showNewsModal = false;
        this.state.selectedNews = {};
        this.state.isFavorited = false;
        this.state.notes = [];
        this.state.selectionMenuVisible = false;
        this.state.noteInputVisible = false;
        this.state.showHint = false;
      },
      ensureLoggedIn() {
        const auth = window.__VTJ_AUTH__;
        if (!auth || !auth.isLoggedIn || !auth.isLoggedIn()) {
          ElMessage.warning('请先登录后再操作');
          return false;
        }
        return true;
      },
      scrollToNotes() {
        var el = this.$el.querySelector('.news-notes-section');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      },
      resolveImgUrl(url) {
        if (!url) return '';
        return url;
      },
      hasInlineMarkers(content) {
        return !!content && /\[\[IMG:\d+\]\]/.test(content);
      },
      renderContent(content) {
        if (!content) return '';
        const images = this.state.selectedNews.images || [];
        const imageMap = {};
        for (const img of images) {
          const order = img.order !== undefined && img.order !== null ? img.order : null;
          if (order !== null) imageMap[order] = img.url || img;
        }
        const paragraphs = content.split(/\n{2,}/);
        let html = '';
        for (const para of paragraphs) {
          const trimmed = para.trim();
          if (!trimmed) continue;
          const imgMatch = trimmed.match(/^\[\[IMG:(\d+)\]\]$/);
          if (imgMatch) {
            const order = parseInt(imgMatch[1], 10);
            const src = this.resolveImgUrl(imageMap[order]);
            if (src) {
              html += '<img src="' + src + '" alt="新闻图片" class="news-inline-img" />';
            }
            continue;
          }
          const escaped = trimmed
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
          const withBreaks = escaped.replace(/\n/g, '<br/>');
          html += '<p style="margin-bottom:18px;text-indent:2em;">' + withBreaks + '</p>';
        }
        return html;
      },
      handleTextSelection() {
        const sel = window.getSelection();
        const text = (sel && sel.toString() || '').trim();
        if (text.length > 0) {
          this.state.selectedText = text;
          const range = sel.getRangeAt(0);
          const rect = range.getBoundingClientRect();
          const menuW = 260;
          const menuH = 140;
          let x = rect.left + rect.width / 2 - menuW / 2;
          let y = rect.top - menuH + window.scrollY;
          if (x < 8) x = 8;
          if (x + menuW > window.innerWidth - 8) x = window.innerWidth - menuW - 8;
          if (y < window.scrollY + 8) y = rect.bottom + 8 + window.scrollY;
          this.state.selectionMenuPos = { x: x, y: y };
          this.state.selectionMenuVisible = true;
        } else {
          this.state.selectionMenuVisible = false;
          this.state.selectedText = '';
        }
      },
      setLineStyle(style) {
        this.state.lineStyle = style;
      },
      async applyHighlight(color) {
        if (!this.ensureLoggedIn()) return;
        if (!this.state.selectedText) return;
        if (color) this.state.highlightColor = color;
        const newsId = this.state.selectedNews.id;
        try {
          await window.__VTJ_AUTH__.apiFetch('/api/news/' + newsId + '/note', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              note_text: '',
              quote_text: this.state.selectedText,
              color: this.state.highlightColor,
              line_style: this.state.lineStyle
            })
          });
          this.state.selectionMenuVisible = false;
          this.state.selectedText = '';
          await this.fetchNotes(newsId);
        } catch (e) {
          console.error('划线失败:', e);
        }
      },
      renderNoteStyle(note) {
        if (note.line_style === 'wavy') {
          return 'text-decoration: underline wavy ' + (note.color || '#FFD700') + ';';
        } else if (note.line_style === 'straight') {
          return 'text-decoration: underline ' + (note.color || '#FFD700') + ';';
        } else if (note.line_style === 'marker') {
          return 'background-color: ' + (note.color || '#FFD700') + '40; padding: 0 2px;';
        }
        return 'border-left: 3px solid ' + (note.color || '#FFD700') + ';';
      },
      openNoteInput() {
        if (!this.ensureLoggedIn()) return;
        if (!this.state.selectedText) return;
        this.state.noteText = '';
        this.state.selectionMenuVisible = false;
        this.state.noteInputVisible = true;
        this.$nextTick(() => {
          const el = this.$el.querySelector('.note-input-textarea');
          if (el) el.focus();
        });
      },
      cancelNoteInput() {
        this.state.noteInputVisible = false;
        this.state.noteText = '';
      },
      async saveNoteOnBlur() {
        const thought = (this.state.noteText || '').trim();
        if (!thought) {
          this.cancelNoteInput();
          return;
        }
        if (!this.ensureLoggedIn()) {
          this.cancelNoteInput();
          return;
        }
        const newsId = this.state.selectedNews.id;
        try {
          await window.__VTJ_AUTH__.apiFetch('/api/news/' + newsId + '/note', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              note_text: thought,
              quote_text: this.state.selectedText,
              color: this.state.highlightColor,
              line_style: this.state.lineStyle
            })
          });
          this.state.noteInputVisible = false;
          this.state.noteText = '';
          this.state.selectedText = '';
          await this.fetchNotes(newsId);
        } catch (e) {
          console.error('保存想法失败:', e);
          this.state.noteInputVisible = false;
          this.state.noteText = '';
        }
      },
      async toggleFavorite() {
        if (!this.ensureLoggedIn()) return;
        const newsId = this.state.selectedNews.id;
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/news/' + newsId + '/favorite', { method: 'POST' });
          const data = await res.json();
          this.state.isFavorited = data.favorited;
        } catch (e) {
          console.error('收藏操作失败:', e);
        }
      },
      async fetchNotes(newsId) {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/news/' + newsId + '/notes');
          const data = await res.json();
          if (res.ok) {
            this.state.notes = data.items || [];
          }
        } catch (e) {
          console.error('获取笔记失败:', e);
        }
      },
      async removeNote(noteId) {
        try {
          await window.__VTJ_AUTH__.apiFetch('/api/news/notes/' + noteId, { method: 'DELETE' });
          this.state.notes = this.state.notes.filter(n => n.note_id !== noteId);
        } catch (e) {
          console.error('删除笔记失败:', e);
        }
      },
      async fetchNews() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/news?limit=50');
          const data = await res.json();
          if (res.ok && data.items) {
            this.state.newsItems = data.items;
          }
        } catch (e) {}
      }
    },
    mounted() {
      this.formatDate();
      this.refreshQuote();
      this.fetchNews();
    }
  })
</script>
<style lang="css" scoped>
  .quote-banner {
    background: linear-gradient(135deg, #ffffff 0%, #fdfdff 100%);
    border-radius: 16px;
    padding: 70px 28px 75px;
    box-shadow: 0 2px 16px rgba(26, 43, 95, 0.06);
    position: relative;
    overflow: hidden;
    border-left: 4px solid #c41e3a;
  }
  .quote-decoration {
    position: absolute;
    top: -30px;
    right: -30px;
    width: 100px;
    height: 100px;
    background: radial-gradient(
      circle,
      rgba(196, 30, 58, 0.04) 0%,
      transparent 70%
    );
    border-radius: 50%;
  }
  .quote-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
  }
  .quote-source {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 20px;
    font-weight: 600;
    color: #1a2b5f;
  }
  .quote-date {
    font-size: 15px;
    color: #8a8faa;
    background: #f8f9fc;
    padding: 2px 10px;
    border-radius: 10px;
  }
  .quote-body {
    position: relative;
    padding: 8px 0;
  }
  .quote-text {
    font-size: 18px;
    line-height: 1.8;
    color: #33375a;
    font-weight: 500;
    letter-spacing: 0.5px;
    font-family: 'Noto Serif SC', 'STSong', 'Songti SC', serif;
  }
  .quote-mark {
    font-size: 48px;
    color: rgba(196, 30, 58, 0.12);
    font-family: Georgia, serif;
    line-height: 1;
  }
  .left-mark {
    position: absolute;
    top: -10px;
    left: -4px;
  }
  .right-mark {
    position: absolute;
    bottom: -20px;
    right: 0;
  }
  .quote-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 22px;
  }
  .quote-author {
    font-size: 15px;
    color: #8a8faa;
    font-style: italic;
  }
  .refresh-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 6px 12px;
    border: none;
    background: #fef0f2;
    color: #c41e3a;
    border-radius: 14px;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.3s;
    font-weight: 500;
  }
  .refresh-btn:hover {
    background: #fde2e6;
    transform: scale(1.02);
  }
  .quote-footer-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .quote-fav-btn {
    width: 34px;
    height: 34px;
    border: none;
    background: #f8f9fc;
    border-radius: 14px;
    font-size: 16px;
    cursor: pointer;
    transition: all 0.3s;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .quote-fav-btn:hover { background: #fff8e1; transform: scale(1.05); }
  .quote-fav-btn.favorited { background: #fff8e1; }
  /* 每日新闻 */
  .news-section {
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid #f0f2f5;
  }
  .news-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
  }
  .news-title {
    font-size: 20px;
    font-weight: 700;
    color: #1a2b5f;
    flex: 1;
  }
  .news-badge {
    font-size: 14px;
    color: #c41e3a;
    background: rgba(196, 30, 58, 0.08);
    padding: 2px 8px;
    border-radius: 10px;
  }
  .news-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 320px;
    overflow-y: auto;
    padding-right: 4px;
  }
  .news-list::-webkit-scrollbar { width: 4px; }
  .news-list::-webkit-scrollbar-track { background: transparent; }
  .news-list::-webkit-scrollbar-thumb { background: #d9dce8; border-radius: 4px; }
  .news-list::-webkit-scrollbar-thumb:hover { background: #bcc0d0; }
  .news-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 5px 6px;
    text-decoration: none;
    transition: all 0.2s;
    border-radius: 6px;
  }
  .news-item:hover {
    background: #f8f9fc;
    padding-left: 10px;
  }
  .news-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #c41e3a;
    flex-shrink: 0;
  }
  .news-text {
    font-size: 17px;
    color: #2c3e50;
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .news-source {
    font-size: 15px;
    color: #8a8faa;
    background: #f1f3f8;
    padding: 2px 6px;
    border-radius: 4px;
    flex-shrink: 0;
  }
  .news-empty {
    text-align: center;
    padding: 12px;
    font-size: 12px;
    color: #8a8faa;
  }
  .news-item { cursor: pointer; user-select: none; }
  /* 新闻详情弹窗 */
  .news-modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
  .news-modal { background: #ffffff; border-radius: 16px; width: 90%; max-width: 1250px; max-height: 80vh; display: flex; flex-direction: column; box-shadow: 0 8px 40px rgba(26,43,95,0.15); overflow: hidden; }
  .news-modal-header { display: flex; align-items: flex-start; justify-content: space-between; padding: 24px 28px 16px; border-bottom: 1px solid #f0f2f5; }
  .news-modal-title { font-size: 25px; font-weight: 700; color: #1a2b5f; margin: 0; line-height: 1.5; flex: 1; padding-right: 12px; }
  .news-modal-close { width: 32px; height: 32px; border: none; background: #f8f9fc; border-radius: 8px; cursor: pointer; font-size: 18px; color: #8a8faa; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .news-modal-close:hover { background: #f0f2f5; color: #1a2b5f; }
  .news-modal-meta { display: flex; align-items: center; gap: 12px; padding: 12px 28px; border-bottom: 1px solid #f8f9fc; }
  .news-modal-source-badge { font-size: 15px; font-weight: 600; color: #c41e3a; background: #fef0f2; padding: 2px 10px; border-radius: 8px; }
  .news-modal-date { font-size: 15px; color: #8a8faa; }
  .news-modal-body { padding: 20px 28px; overflow-y: auto; flex: 1; max-height: 50vh; }
  .news-modal-content { font-size: 15px; line-height: 1.9; color: #33375a; margin: 0; }
  .news-modal-content p { margin-bottom: 18px; line-height: 1.9; }
  .news-modal-content p:last-child { margin-bottom: 0; }
  .news-modal-footer { display: flex; justify-content: flex-end; gap: 12px; padding: 16px 28px; border-top: 1px solid #f0f2f5; }
  .news-modal-link { padding: 8px 16px; border-radius: 8px; font-size: 13px; text-decoration: none; color: #5a6488; background: #f8f9fc; }
  .news-modal-link:hover { background: #f0f2f5; color: #1a2b5f; }
  .news-modal-btn { padding: 8px 20px; border: none; background: #c41e3a; color: #ffffff; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; }
  .news-modal-btn:hover { background: #a0182e; }

  /* 弹窗右上角操作按钮 */
  .news-modal-header-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
  .news-fav-btn { width: 36px; height: 36px; border: none; background: #f8f9fc; border-radius: 8px; cursor: pointer; font-size: 18px; display: flex; align-items: center; justify-content: center; transition: all 0.2s; }
  .news-fav-btn:hover { background: #fef0f2; transform: scale(1.1); }
  .news-fav-btn.favorited { background: #fff8e1; }
  .news-note-btn { width: 36px; height: 36px; border: none; background: #f8f9fc; border-radius: 8px; cursor: pointer; font-size: 18px; display: flex; align-items: center; justify-content: center; transition: all 0.2s; }
  .news-note-btn:hover { background: #eff6ff; transform: scale(1.1); }

  /* 划线/想法说明气泡 */
  .news-hint-bubble { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 14px; margin: 0 0 12px; background: #eff6ff; border-radius: 10px; font-size: 13px; color: #3b82f6; line-height: 1.6; }
  .news-hint-notes { padding: 4px 10px; border: none; background: #ffffff; color: #3b82f6; border-radius: 6px; font-size: 12px; cursor: pointer; flex-shrink: 0; white-space: nowrap; }
  .news-hint-notes:hover { background: #dbeafe; }

  /* 正文内联图片 */
  .news-inline-img { display: block; max-width: 100%; height: auto; margin: 20px auto; border-radius: 10px; box-shadow: 0 2px 12px rgba(26,43,95,0.08); }
  .news-modal-images { display: flex; flex-direction: column; gap: 16px; margin: 20px 0; }
  .news-content-img { max-width: 100%; border-radius: 8px; height: auto; margin: 12px auto; display: block; }

  /* 选中文本5色+3线型菜单 */
  .selection-menu { position: fixed; z-index: 2000; background: #ffffff; border-radius: 10px; box-shadow: 0 4px 24px rgba(26,43,95,0.18); padding: 8px; }
  .sel-menu-row { display: flex; gap: 6px; padding: 3px 0; justify-content: center; }
  .sel-color-dot { width: 22px; height: 22px; border: 2px solid transparent; border-radius: 50%; cursor: pointer; transition: all 0.2s; }
  .sel-color-dot:hover { transform: scale(1.2); }
  .sel-color-dot.active { border-color: #1a2b5f; box-shadow: 0 0 0 2px rgba(26,43,95,0.25); }
  .sel-style-btn { padding: 4px 10px; border: 1px solid #e8eaf0; background: #fff; border-radius: 6px; font-size: 12px; cursor: pointer; transition: all 0.2s; }
  .sel-style-btn.active { background: #eff6ff; border-color: #3b82f6; color: #3b82f6; font-weight: 700; }
  .sel-style-btn:hover { background: #f0f2f5; }
  .sel-action-btn { padding: 6px 14px; border: none; border-radius: 6px; font-size: 13px; cursor: pointer; background: #eff6ff; color: #3b82f6; font-weight: 600; transition: all 0.2s; }
  .sel-action-btn:hover { background: #dbeafe; }

  /* 想法输入气泡 */
  .note-input-bubble { position: fixed; z-index: 2100; width: 280px; background: #ffffff; border-radius: 10px; box-shadow: 0 6px 28px rgba(26,43,95,0.22); padding: 10px; }
  .note-input-textarea { width: 100%; height: 72px; resize: none; border: 1px solid #e8eaf0; border-radius: 8px; padding: 8px; font-size: 13px; color: #33375a; font-family: inherit; line-height: 1.6; outline: none; box-sizing: border-box; }
  .note-input-textarea:focus { border-color: #3b82f6; }
  .note-input-actions { display: flex; justify-content: flex-end; margin-top: 6px; }
  .note-input-cancel { padding: 4px 12px; border: none; background: #f8f9fc; color: #8a8faa; border-radius: 6px; font-size: 12px; cursor: pointer; }
  .note-input-cancel:hover { background: #fef0f2; color: #c41e3a; }

  /* 笔记区域 */
  .news-notes-section { padding: 16px 0; border-top: 1px solid #f0f2f5; max-height: 200px; overflow-y: auto; }
  .news-notes-title { font-size: 14px; font-weight: 700; color: #1a2b5f; margin: 0 0 12px; }
  .news-note-item { padding: 10px 12px; background: #f8f9fc; border-radius: 8px; margin-bottom: 8px; position: relative; }
  .note-quote { border-left: 3px solid #FFD700; padding: 4px 10px; margin: 0 0 6px; font-size: 13px; color: #5a6488; background: #fff; border-radius: 0 4px 4px 0; }
  .note-text { font-size: 14px; color: #33375a; margin: 0; padding-right: 40px; }
  .note-delete-btn { position: absolute; top: 8px; right: 8px; padding: 2px 8px; border: none; background: transparent; color: #c9cdd8; font-size: 12px; cursor: pointer; border-radius: 4px; }
  .note-delete-btn:hover { background: #fef0f2; color: #c41e3a; }
</style>
