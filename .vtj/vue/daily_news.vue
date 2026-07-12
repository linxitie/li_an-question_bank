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
            <button :class="'news-fav-btn ' + (state.isFavorited ? 'favorited' : '')" @click="toggleFavorite" :title="state.isFavorited ? '取消收藏' : '收藏'">⭐</button>
            <button class="news-modal-close" @click="closeDetail">×</button>
          </div>
        </div>
        <div class="news-modal-meta">
          <span :class="'news-source-badge ' + (state.selectedNews.source === 'cpd' ? 'badge-cpd' : 'badge-people')">{{ state.selectedNews.source === 'cpd' ? '人民公安报' : '人民网' }}</span>
          <span v-if="state.selectedNews.publish_date">{{ state.selectedNews.publish_date.substring(0, 10) }}</span>
          <span v-if="state.selectedNews.category">{{ state.selectedNews.category }}</span>
        </div>
        <div class="news-modal-body" @mouseup="handleTextSelection" @touchend="handleTextSelection">
          <div v-if="state.selectedNews.content" class="news-modal-content" v-html="renderContent(state.selectedNews.content)"></div>
          <p v-else class="news-modal-content">{{ state.selectedNews.summary || '暂无内容' }}</p>
          <!-- 图片展示区域 -->
          <div v-if="state.selectedNews.images && state.selectedNews.images.length" class="news-modal-images">
            <img v-for="(img, idx) in state.selectedNews.images" :key="idx" :src="img.url || img" :alt="'图片' + (idx + 1)" class="news-content-img" />
          </div>
        </div>
        <!-- 选中文本操作菜单（多色划线+想法） -->
        <div v-if="state.selectionMenuVisible" class="selection-menu" :style="{ top: state.selectionMenuPos.y + 'px', left: state.selectionMenuPos.x + 'px' }">
          <button class="sel-menu-btn sel-color-yellow" @click="highlightYellow" title="黄色划线">🟡 划线</button>
          <button class="sel-menu-btn sel-color-green" @click="highlightGreen" title="绿色划线">🟢 划线</button>
          <button class="sel-menu-btn sel-color-blue" @click="highlightBlue" title="蓝色划线">🔵 划线</button>
          <button class="sel-menu-btn" @click="noteSelection">📝 想法</button>
        </div>
        <!-- 笔记列表 -->
        <div v-if="state.showDetailModal && state.notes.length" class="news-notes-section">
          <h4 class="news-notes-title">我的笔记 ({{ state.notes.length }})</h4>
          <div v-for="note in state.notes" :key="note.note_id" class="news-note-item">
            <blockquote v-if="note.quote_text" class="note-quote" :style="{ borderLeftColor: note.color }">{{ note.quote_text }}</blockquote>
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
  export default defineComponent({
    name: 'DailyNews',
    components: { NavBar },
    setup(props) {
      const provider = useProvider({ id: 'daily_news', version: '1778918000715' });
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
        highlightColor: '#FFD700'
      });
      return { state, props, provider };
    },
    methods: {
      async setSourceFilter(val) {
        this.state.sourceFilter = val;
        this.state.currentPage = 1;
        await this.fetchNews();
      },
      async setCategoryFilter(val) {
        this.state.categoryFilter = val;
        this.state.currentPage = 1;
        await this.fetchNews();
      },
      async goPage(page) {
        if (page < 1 || page > this.state.totalPages) return;
        this.state.currentPage = page;
        await this.fetchNews();
      },
      openDetail(item) {
        this.state.selectedNews = item;
        this.state.showDetailModal = true;
        this.state.isFavorited = item.is_favorited || false;
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
          let url = '/api/news?limit=50';
          if (this.state.sourceFilter) url += '&source=' + this.state.sourceFilter;
          if (this.state.categoryFilter) url += '&category=' + this.state.categoryFilter;
          const res = await window.__VTJ_AUTH__.apiFetch(url);
          const data = await res.json();
          if (res.ok && data.items) {
            this.state.totalItems = data.total;
            const start = (this.state.currentPage - 1) * this.state.pageSize;
            this.state.newsItems = data.items.slice(start, start + this.state.pageSize);
            this.state.totalPages = Math.ceil(data.total / this.state.pageSize) || 1;
          }
        } catch (e) {
          console.error('获取新闻失败:', e);
        } finally {
          this.state.loading = false;
        }
      },
      renderContent(content) {
        if (!content) return '';
        // 分段：空行分隔为 <p>
        const paragraphs = content.split(/\n{2,}/);
        let html = '';
        for (const para of paragraphs) {
          if (para.trim()) {
            // 单行换行转为 <br/>
            const escaped = para
              .replace(/&/g, '&amp;')
              .replace(/</g, '&lt;')
              .replace(/>/g, '&gt;');
            const withBreaks = escaped.replace(/\n/g, '<br/>');
            html += '<p style="margin-bottom:16px;text-indent:2em;">' + withBreaks + '</p>';
          }
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
          this.state.selectionMenuPos = {
            x: rect.left + rect.width / 2 - 60,
            y: rect.top - 40 + window.scrollY
          };
          this.state.selectionMenuVisible = true;
        } else {
          this.state.selectionMenuVisible = false;
          this.state.selectedText = '';
        }
      },
      async highlightSelection(color) {
        if (!this.state.selectedText) return;
        const newsId = this.state.selectedNews.id;
        const c = color || this.state.highlightColor || '#FFD700';
        try {
          await window.__VTJ_AUTH__.apiFetch('/api/news/' + newsId + '/note', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              note_text: '',
              quote_text: this.state.selectedText,
              color: c
            })
          });
          this.state.highlightColor = c;
          this.state.selectionMenuVisible = false;
          this.state.selectedText = '';
          await this.fetchNotes(newsId);
        } catch (e) {
          console.error('划线失败:', e);
        }
      },
      async highlightYellow() { await this.highlightSelection('#FFD700'); },
      async highlightGreen() { await this.highlightSelection('#4CAF50'); },
      async highlightBlue() { await this.highlightSelection('#2196F3'); },
      async noteSelection() {
        if (!this.state.selectedText) return;
        const thought = prompt('记录想法:', '');
        if (thought === null) return;
        const newsId = this.state.selectedNews.id;
        const c = this.state.highlightColor || '#FFD700';
        try {
          await window.__VTJ_AUTH__.apiFetch('/api/news/' + newsId + '/note', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              note_text: thought,
              quote_text: this.state.selectedText,
              color: c
            })
          });
          this.state.selectionMenuVisible = false;
          this.state.selectedText = '';
          await this.fetchNotes(newsId);
        } catch (e) {
          console.error('保存想法失败:', e);
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

/* 选中文本操作菜单 */
.selection-menu {
  position: fixed; z-index: 2000;
  background: #ffffff; border-radius: 8px;
  box-shadow: 0 4px 20px rgba(26,43,95,0.15);
  display: flex; gap: 4px; padding: 6px;
}
.sel-menu-btn {
  padding: 6px 12px; border: none; background: #f8f9fc;
  border-radius: 6px; font-size: 13px; cursor: pointer;
  white-space: nowrap; transition: all 0.2s;
}
.sel-menu-btn:hover { background: #fef0f2; color: #c41e3a; }
.sel-color-yellow { border-left: 3px solid #FFD700; }
.sel-color-green { border-left: 3px solid #4CAF50; }
.sel-color-blue { border-left: 3px solid #2196F3; }
.sel-color-yellow:hover { background: #fff8e1; color: #b8860b; }
.sel-color-green:hover { background: #e8f5e9; color: #2e7d32; }
.sel-color-blue:hover { background: #e3f2fd; color: #1565c0; }

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
</style>
