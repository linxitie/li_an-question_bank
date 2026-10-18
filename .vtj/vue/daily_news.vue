<!-- 每日新闻模块 -->
<template>
  <div class="news-page">
    <NavBar></NavBar>
    <div class="news-container">
      <div class="news-page-header">
        <h1 class="news-page-title">每日新闻</h1>
        <p class="news-page-subtitle">人民公安报 · 人民网 · 时政要闻早知道</p>
      </div>
      <div class="filter-bar">
        <div class="filter-group">
          <span class="filter-label">来源:</span>
          <button :class="state.sourceFilter === '' ? 'filter-tag active' : 'filter-tag'" @click="setSourceFilter('')">全部</button>
          <button :class="state.sourceFilter === 'cpd' ? 'filter-tag active' : 'filter-tag'" @click="setSourceFilter('cpd')">人民公安报</button>
          <button :class="state.sourceFilter === 'people' ? 'filter-tag active' : 'filter-tag'" @click="setSourceFilter('people')">人民网</button>
        </div>
        <div class="filter-group">
          <span class="filter-label">分类:</span>
          <button :class="state.categoryFilter === '' ? 'filter-tag active' : 'filter-tag'" @click="setCategoryFilter('')">全部</button>
          <button :class="state.categoryFilter === '公安报' ? 'filter-tag active' : 'filter-tag'" @click="setCategoryFilter('公安报')">公安报</button>
          <button :class="state.categoryFilter === '理论' ? 'filter-tag active' : 'filter-tag'" @click="setCategoryFilter('理论')">理论</button>
          <button :class="state.categoryFilter === '党史' ? 'filter-tag active' : 'filter-tag'" @click="setCategoryFilter('党史')">党史</button>
        </div>
      </div>
      <div class="news-list-container">
        <div class="news-list-header">
          <span class="news-count">{{ state.loading ? '加载中...' : '共 ' + state.totalItems + ' 条新闻' }}</span>
        </div>
        <div v-for="(item, index) in state.newsItems" :key="item.id" class="news-card" @click="openDetail(item)">
          <span class="news-card-index">{{ (state.currentPage - 1) * state.pageSize + index + 1 }}</span>
          <div class="news-card-body">
            <p class="news-card-title">{{ item.title }}</p>
            <div class="news-card-meta">
              <span :class="'news-source-badge ' + (item.source === 'cpd' ? 'badge-cpd' : 'badge-people')">{{ item.source === 'cpd' ? '人民公安报' : '人民网' }}</span>
              <span>{{ item.category }}</span>
              <span>{{ item.publish_date ? item.publish_date.substring(0, 10) : '' }}</span>
            </div>
          </div>
          <div class="news-card-actions" @click.stop>
            <button :class="['card-fav-btn', { favorited: item.is_favorited }]" @click="toggleCardFavorite(item)" title="收藏">{{ item.is_favorited ? '⭐' : '☆' }}</button>
            <button class="card-note-btn" @click="openDetail(item)" title="笔记">📝<span v-if="item.note_count" class="note-count-badge">{{ item.note_count }}</span></button>
          </div>
          <span class="news-card-arrow">▶</span>
        </div>
        <div v-if="!state.loading && !state.newsItems.length" class="empty-state">
          <p>暂无新闻数据，请稍后再来~</p>
        </div>
        <div v-if="state.loading" class="loading-state">
          <p>新闻加载中，请稍候...</p>
        </div>
        <div v-if="state.totalPages > 1" class="pagination-bar">
          <button class="page-btn" :disabled="state.currentPage <= 1" @click="goPage(state.currentPage - 1)">上一页</button>
          <span class="page-info">{{ state.currentPage }} / {{ state.totalPages }}</span>
          <button class="page-btn" :disabled="state.currentPage >= state.totalPages" @click="goPage(state.currentPage + 1)">下一页</button>
        </div>
      </div>
    </div>
    <!-- 新闻详情弹窗 -->
    <div v-if="state.showDetailModal" class="news-modal-overlay" @click.self="closeDetail">
      <div class="news-modal">
        <div class="news-modal-header">
          <h3 class="news-modal-title">{{ state.selectedNews.title }}</h3>
          <div class="news-modal-header-actions">
            <button :class="'news-fav-btn ' + (state.isFavorited ? 'favorited' : '')" @click="toggleFavorite" :title="state.isFavorited ? '取消收藏' : '收藏'">{{ state.isFavorited ? '⭐' : '☆' }}</button>
            <button class="news-note-btn" @click="state.showHint = !state.showHint" title="划线/想法说明">📝</button>
            <button class="news-modal-close" @click="closeDetail">×</button>
          </div>
        </div>
        <div v-if="state.showHint" class="news-hint-bubble">
          <span>💡 选中正文文字 → 点颜色即划线（自动保存）；点「📝 想法」输入后失焦自动保存。</span>
          <button class="news-hint-notes" @click="scrollToNotes">查看我的笔记 ↓</button>
        </div>
        <div class="news-modal-meta">
          <span :class="'news-source-badge ' + (state.selectedNews.source === 'cpd' ? 'badge-cpd' : 'badge-people')">{{ state.selectedNews.source === 'cpd' ? '人民公安报' : '人民网' }}</span>
          <span v-if="state.selectedNews.publish_date">{{ state.selectedNews.publish_date.substring(0, 10) }}</span>
          <span v-if="state.selectedNews.category">{{ state.selectedNews.category }}</span>
        </div>
        <div class="news-modal-body" @mouseup="handleTextSelection" @touchend="handleTextSelection">
          <div v-if="state.selectedNews.content" class="news-modal-content" v-html="renderContent(state.selectedNews.content)"></div>
          <p v-else class="news-modal-content">{{ state.selectedNews.summary || '暂无内容' }}</p>
          <!-- 图片兜底展示（正文无内联标记时） -->
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
        <div v-if="state.showDetailModal && state.notes.length" class="news-notes-section">
          <h4 class="news-notes-title">我的笔记 ({{ state.notes.length }})</h4>
          <div v-for="note in state.notes" :key="note.note_id" class="news-note-item">
            <blockquote v-if="note.quote_text" class="note-quote" :style="renderNoteStyle(note)">{{ note.quote_text }}</blockquote>
            <p class="note-text">{{ note.note_text }}</p>
            <button class="note-delete-btn" @click="removeNote(note.note_id)">删除</button>
          </div>
        </div>
        <div class="news-modal-footer">
          <a :href="state.selectedNews.url" target="_blank" class="news-modal-link">查看原文</a>
          <button class="news-modal-btn" @click="closeDetail">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import NavBar from './navbar.vue';
  import { useProvider } from '@vtj/renderer';
  import { useNewsStore } from '@/modules/news/store';
  export default defineComponent({
    name: 'DailyNews',
    components: { NavBar },
    setup(props) {
      const provider = useProvider({ id: 'daily_news', version: '1778918000715' });
      const newsStore = useNewsStore();
      const state = reactive({
        newsItems: [],
        loading: false,
        sourceFilter: '',
        categoryFilter: '',
        currentPage: 1,
        pageSize: 20,
        totalItems: 0,
        totalPages: 1,
        showDetailModal: false,
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
        noteText: ''
      });
      return { state, props, provider, newsStore };
    },
    methods: {
      async setSourceFilter(val) {
        this.state.sourceFilter = val;
        this.state.currentPage = 1;
        await this.fetchNews();
      },
      scrollToNotes() {
        var el = this.$el.querySelector('.news-notes-section');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
      },
      async setCategoryFilter(val) {
        this.state.categoryFilter = val;
        this.state.currentPage = 1;
        await this.fetchNews();
      },
      async goPage(page) {
        if (page < 1 || page > this.newsStore.totalPages) return;
        this.state.currentPage = page;
        this.newsStore.goPage(page);
        this.state.newsItems = this.newsStore.pageItems;
      },
      async openDetail(item) {
        // 详情端点即阅读上报入口：首次打开由后端记录已读并发布 news.read
        const detail = await this.newsStore.openArticle(item.id, item);
        this.state.selectedNews = detail || item;
        this.state.showDetailModal = true;
        this.state.isFavorited = this.state.selectedNews.is_favorited || false;
        this.state.notes = [];
        this.state.selectionMenuVisible = false;
        // 加载笔记
        this.fetchNotes(item.id);
      },
      closeDetail() {
        this.state.showDetailModal = false;
        this.state.selectedNews = {};
        this.state.isFavorited = false;
        this.state.notes = [];
        this.state.selectionMenuVisible = false;
      },
      async fetchNews() {
        this.state.loading = true;
        try {
          await this.newsStore.load({
            source: this.state.sourceFilter,
            category: this.state.categoryFilter,
            limit: 50,
            pageSize: this.state.pageSize,
            page: this.state.currentPage
          });
          if (this.newsStore.error) {
            console.error('获取新闻失败:', this.newsStore.error);
            this.state.newsItems = [];
            this.state.totalItems = 0;
            this.state.totalPages = 1;
            return;
          }
          this.state.totalItems = this.newsStore.total;
          this.state.totalPages = this.newsStore.totalPages;
          this.state.currentPage = this.newsStore.page;
          this.state.newsItems = this.newsStore.pageItems;
        } catch (e) {
          console.error('获取新闻失败:', e);
        } finally {
          this.state.loading = this.newsStore.loading;
        }
      },
      resolveImgUrl(url) {
        if (!url) return '';
        // 相对路径保持（同源 + dev proxy 已通），绝对 URL 直接用
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
        // 分段：空行分隔为 <p>，内联图片标记单独成段
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
          // 单行换行转为 <br/>
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
          // 菜单约 260px 宽、140px 高，做越界钳制，避免被视口裁剪
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
      async toggleCardFavorite(item) {
        const res = await window.__VTJ_AUTH__.apiFetch('/api/news/' + item.id + '/favorite', { method: 'POST' });
        const data = await res.json();
        item.is_favorited = data.favorited;
      },
      async applyHighlight(color) {
        if (!this.state.selectedText) return;
        if (color) this.state.highlightColor = color;
        const newsId = this.state.selectedNews.id;
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
        const newsId = this.state.selectedNews.id;
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/news/' + newsId + '/favorite', {
            method: 'POST'
          });
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
          await window.__VTJ_AUTH__.apiFetch('/api/news/notes/' + noteId, {
            method: 'DELETE'
          });
          this.state.notes = this.state.notes.filter(n => n.note_id !== noteId);
        } catch (e) {
          console.error('删除笔记失败:', e);
        }
      }
    },
    mounted() {
      this.fetchNews();
    }
  })
</script>
<style lang="css" scoped>
.news-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
  font-family: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
}
.news-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 24px 32px 40px;
}
.news-page-header {
  text-align: center;
  padding: 40px 0 20px;
}
.news-page-title {
  font-size: 32px;
  font-weight: 900;
  color: #1a2b5f;
  margin: 0;
  letter-spacing: 4px;
}
.news-page-subtitle {
  font-size: 14px;
  color: #8a8faa;
  margin: 8px 0 0;
}
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 24px;
  padding: 20px;
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(26,43,95,0.05);
}
.filter-group {
  display: flex;
  align-items: center;
  gap: 8px;
}
.filter-label {
  font-size: 13px;
  font-weight: 700;
  color: #5a6488;
  margin-right: 4px;
}
.filter-tag {
  padding: 6px 16px;
  border-radius: 20px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s;
  border: none;
  background: #f1f3f8;
  color: #5a6488;
  font-weight: 500;
}
.filter-tag:hover { background: #e8eaf0; color: #1a2b5f; }
.filter-tag.active { background: #c41e3a; color: #ffffff; font-weight: 700; }
.news-list-container {
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(26,43,95,0.05);
  overflow: hidden;
}
.news-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid #f0f2f5;
}
.news-count { font-size: 14px; color: #8a8faa; }
.news-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 24px;
  border-bottom: 1px solid #f8f9fc;
  cursor: pointer;
  transition: all 0.2s;
}
.news-card:hover { background: #f8f9fc; }
.news-card:last-child { border-bottom: none; }
.news-card-index {
  width: 28px; height: 28px;
  border-radius: 8px;
  background: #f1f3f8;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; color: #8a8faa;
  flex-shrink: 0;
}
.news-card:nth-child(-n+3) .news-card-index { background: #fef0f2; color: #c41e3a; }
.news-card-body { flex: 1; min-width: 0; }
.news-card-title {
  font-size: 15px; font-weight: 600; color: #1a2b5f;
  margin: 0 0 6px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.news-card-meta { display: flex; align-items: center; gap: 12px; font-size: 12px; color: #8a8faa; }
.news-source-badge { padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; }
.badge-cpd { background: #fef0f2; color: #c41e3a; }
.badge-people { background: #eff6ff; color: #2563eb; }
.news-card-arrow { color: #c9cdd8; font-size: 16px; flex-shrink: 0; }
.pagination-bar { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 20px; }
.page-btn {
  padding: 8px 14px; border-radius: 8px;
  border: 1px solid #e8eaf0; background: #ffffff;
  color: #5a6488; font-size: 13px; cursor: pointer; transition: all 0.2s;
}
.page-btn:hover:not(:disabled) { background: #f1f3f8; color: #1a2b5f; }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { font-size: 12px; color: #8a8faa; margin: 0 8px; }
.empty-state { text-align: center; padding: 60px 20px; }
.empty-state p { font-size: 14px; color: #8a8faa; margin: 0; }
.loading-state { text-align: center; padding: 60px 20px; }
.loading-state p { font-size: 14px; color: #8a8faa; margin: 0; }
.news-modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5); display: flex; align-items: center;
  justify-content: center; z-index: 1000;
}
.news-modal {
  background: #ffffff; border-radius: 16px; width: 90%; max-width: 1200px;
  max-height: 85vh; display: flex; flex-direction: column;
  box-shadow: 0 8px 40px rgba(26,43,95,0.15); overflow: hidden;
  padding: 32px 40px;
}
.news-modal-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  padding: 0 0 16px; border-bottom: 1px solid #f0f2f5;
}
.news-modal-header-actions {
  display: flex; align-items: center; gap: 8px; flex-shrink: 0;
}
.news-modal-title {
  font-size: 20px; font-weight: 700; color: #1a2b5f;
  margin: 0; line-height: 1.5; flex: 1; padding-right: 12px;
}
.news-modal-close {
  width: 32px; height: 32px; border: none; background: #f8f9fc;
  border-radius: 8px; cursor: pointer; font-size: 18px; color: #8a8faa;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.news-modal-close:hover { background: #f0f2f5; color: #1a2b5f; }
.news-modal-meta {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 0; border-bottom: 1px solid #f8f9fc;
}
.news-modal-body {
  padding: 20px 0; overflow-y: auto; flex: 1; max-height: 55vh;
}
.news-modal-content {
  font-size: 15px; line-height: 1.8; color: #33375a;
  margin: 0;
}
.news-modal-content p {
  margin-bottom: 16px; line-height: 1.9;
}
.news-modal-content p:last-child { margin-bottom: 0; }
.news-modal-images {
  display: flex; flex-direction: column; gap: 16px;
  padding: 0; margin: 20px 0;
}
.news-content-img {
  max-width: 100%; border-radius: 8px; height: auto;
  margin: 12px auto; display: block;
}
.news-modal-footer {
  display: flex; justify-content: flex-end; gap: 12px;
  padding: 16px 0 0; border-top: 1px solid #f0f2f5;
}
.news-modal-link {
  padding: 8px 16px; border-radius: 8px; font-size: 13px;
  text-decoration: none; color: #5a6488; background: #f8f9fc;
}
.news-modal-link:hover { background: #f0f2f5; color: #1a2b5f; }
.news-modal-btn {
  padding: 8px 20px; border: none; background: #c41e3a;
  color: #ffffff; border-radius: 8px; font-size: 13px;
  font-weight: 600; cursor: pointer;
}
.news-modal-btn:hover { background: #a0182e; }

/* 收藏按钮 */
.news-fav-btn {
  width: 36px; height: 36px; border: none; background: #f8f9fc;
  border-radius: 8px; cursor: pointer; font-size: 18px;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.news-fav-btn:hover { background: #fef0f2; transform: scale(1.1); }
.news-fav-btn.favorited { background: #fff8e1; }
.news-note-btn {
  width: 36px; height: 36px; border: none; background: #f8f9fc;
  border-radius: 8px; cursor: pointer; font-size: 18px;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.news-note-btn:hover { background: #eff6ff; transform: scale(1.1); }

/* 卡片层收藏+笔记图标 */
.news-card-actions {
  display: flex; gap: 4px; flex-shrink: 0; position: relative;
}
.card-fav-btn, .card-note-btn {
  width: 28px; height: 28px; border: none; background: #f8f9fc;
  border-radius: 6px; cursor: pointer; font-size: 14px;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s; position: relative;
}
.card-fav-btn:hover, .card-note-btn:hover { background: #fef0f2; transform: scale(1.1); }
.card-fav-btn.favorited { background: #fff8e1; }
.note-count-badge {
  position: absolute; top: -6px; right: -6px;
  background: #c41e3a; color: #fff; font-size: 10px;
  min-width: 16px; height: 16px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  padding: 0 4px; font-weight: 700;
}

/* 选中文本5色+3线型菜单 */
.selection-menu {
  position: fixed; z-index: 2000;
  background: #ffffff; border-radius: 10px;
  box-shadow: 0 4px 24px rgba(26,43,95,0.18);
  padding: 8px; flex-direction: column;
}
.sel-menu-row {
  display: flex; gap: 6px; padding: 3px 0; justify-content: center;
}
.sel-color-dot {
  width: 22px; height: 22px; border: 2px solid transparent;
  border-radius: 50%; cursor: pointer; transition: all 0.2s;
}
.sel-color-dot:hover { transform: scale(1.2); }
.sel-color-dot.active { border-color: #1a2b5f; box-shadow: 0 0 0 2px rgba(26,43,95,0.25); }
.sel-style-btn {
  padding: 4px 10px; border: 1px solid #e8eaf0; background: #fff;
  border-radius: 6px; font-size: 12px; cursor: pointer; transition: all 0.2s;
}
.sel-style-btn.active { background: #eff6ff; border-color: #3b82f6; color: #3b82f6; font-weight: 700; }
.sel-style-btn:hover { background: #f0f2f5; }
.sel-action-btn {
  padding: 6px 14px; border: none; border-radius: 6px;
  font-size: 13px; cursor: pointer; background: #eff6ff; color: #3b82f6;
  font-weight: 600; transition: all 0.2s;
}
.sel-action-btn:hover { background: #dbeafe; }

/* 笔记区域 */
.news-notes-section {
  padding: 16px 0; border-top: 1px solid #f0f2f5;
  max-height: 200px; overflow-y: auto;
}
.news-notes-title {
  font-size: 14px; font-weight: 700; color: #1a2b5f; margin: 0 0 12px;
}
.news-note-item {
  padding: 10px 12px; background: #f8f9fc; border-radius: 8px;
  margin-bottom: 8px; position: relative;
}
.note-quote {
  border-left: 3px solid #FFD700; padding: 4px 10px;
  margin: 0 0 6px; font-size: 13px; color: #5a6488;
  background: #fff; border-radius: 0 4px 4px 0;
}
.note-text {
  font-size: 14px; color: #33375a; margin: 0; padding-right: 40px;
}
.note-delete-btn {
  position: absolute; top: 8px; right: 8px;
  padding: 2px 8px; border: none; background: transparent;
  color: #c9cdd8; font-size: 12px; cursor: pointer; border-radius: 4px;
}
.note-delete-btn:hover { background: #fef0f2; color: #c41e3a; }

/* 点击空白区域隐藏选择菜单 */
.news-modal-body { user-select: text; }

/* 划线/想法说明气泡 */
.news-hint-bubble {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 10px 14px; margin: 0 0 12px;
  background: #eff6ff; border-radius: 10px;
  font-size: 13px; color: #3b82f6; line-height: 1.6;
}
.news-hint-notes {
  padding: 4px 10px; border: none; background: #ffffff; color: #3b82f6;
  border-radius: 6px; font-size: 12px; cursor: pointer; flex-shrink: 0; white-space: nowrap;
}
.news-hint-notes:hover { background: #dbeafe; }

/* 正文内联图片 */
.news-inline-img {
  display: block; max-width: 100%; height: auto;
  margin: 20px auto; border-radius: 10px;
  box-shadow: 0 2px 12px rgba(26,43,95,0.08);
}

/* 想法输入气泡 */
.note-input-bubble {
  position: fixed; z-index: 2100; width: 280px;
  background: #ffffff; border-radius: 10px;
  box-shadow: 0 6px 28px rgba(26,43,95,0.22); padding: 10px;
}
.note-input-textarea {
  width: 100%; height: 72px; resize: none; border: 1px solid #e8eaf0;
  border-radius: 8px; padding: 8px; font-size: 13px; color: #33375a;
  font-family: inherit; line-height: 1.6; outline: none; box-sizing: border-box;
}
.note-input-textarea:focus { border-color: #3b82f6; }
.note-input-actions { display: flex; justify-content: flex-end; margin-top: 6px; }
.note-input-cancel {
  padding: 4px 12px; border: none; background: #f8f9fc; color: #8a8faa;
  border-radius: 6px; font-size: 12px; cursor: pointer;
}
.note-input-cancel:hover { background: #fef0f2; color: #c41e3a; }
</style>
