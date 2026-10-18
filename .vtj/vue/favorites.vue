<!-- 收藏聚合页 -->
<template>
  <div class="favorites-page">
    <NavBar></NavBar>
    <main class="favorites-main">
      <div class="fav-header">
        <h2>
          <XIcon :icon="Star" :size="24" color="#c41e3a"></XIcon>
          <span> 我的收藏</span>
        </h2>
        <div class="fav-stats">
          <span class="stat-item">金句/新闻: {{ state.stats.news_quote_total }}</span>
          <span class="stat-item">典题: {{ state.stats.question_favorites }}</span>
          <span class="stat-item total">总计: {{ state.stats.total }}</span>
        </div>
      </div>

      <div class="tab-bar">
        <div class="tab-item" :class="{ active: state.activeTab === 'news' }" @click="switchTab('news')">
          ⭐ 金句/新闻收藏
        </div>
        <div class="tab-item" :class="{ active: state.activeTab === 'question' }" @click="switchTab('question')">
          📝 典题收藏
        </div>
      </div>

      <div class="fav-content">
        <!-- 金句/新闻收藏列表 -->
        <div v-if="state.activeTab === 'news'" class="fav-list">
          <div v-if="state.newsFavorites.length === 0" class="empty-state">
            <span class="empty-icon">⭐</span>
            <p>暂无收藏，去新闻和金句页面收藏吧！</p>
          </div>
          <div v-for="item in state.newsFavorites" :key="item.fav_type + '_' + item.fav_id" class="fav-card" @click="viewNewsDetail(item)">
            <div class="fav-type-badge" :class="item.fav_type">
              {{ item.fav_type === 'quote' ? '💬 金句' : '📰 新闻' }}
            </div>
            <div class="fav-card-body">
              <div class="fav-content-text">{{ item.content }}</div>
              <div class="fav-meta">
                <span v-if="item.source">来源: {{ item.source }}</span>
                <span v-if="item.category">分类: {{ item.category }}</span>
                <span>{{ formatTime(item.create_time) }}</span>
              </div>
            </div>
            <div class="fav-action">点击查看 →</div>
          </div>
        </div>

        <!-- 典题收藏列表 -->
        <div v-if="state.activeTab === 'question'" class="fav-list">
          <div v-if="state.questionFavorites.length === 0" class="empty-state">
            <span class="empty-icon">📝</span>
            <p>暂无典题收藏，在做题时点击收藏按钮收藏题目吧！</p>
          </div>
          <div v-for="item in state.questionFavorites" :key="item.fav_id" class="fav-card question-fav" @click="viewQuestionDetail(item)">
            <div class="fav-type-badge question">📝 典题</div>
            <div class="fav-card-body">
              <div class="fav-content-text question-text" v-html="renderQuestionContent(item.question_content)"></div>
              <div class="fav-meta">
                <span v-if="item.subject_name">科目: {{ item.subject_name }}</span>
                <span v-if="item.subcategory">知识点: {{ item.subcategory }}</span>
                <span>难度: {{ '★'.repeat(item.difficulty || 3) }}{{ '☆'.repeat(5 - (item.difficulty || 3)) }}</span>
                <span>正确率: {{ item.accuracy_rate }}%</span>
              </div>
            </div>
            <div class="fav-action">点击查看 →</div>
          </div>
        </div>

        <!-- 分页 -->
        <div v-if="state.total > state.pageSize" class="pagination">
          <button class="page-btn" :disabled="state.page <= 1" @click="prevPage">上一页</button>
          <span class="page-info">{{ state.page }} / {{ totalPages }}</span>
          <button class="page-btn" :disabled="state.page >= totalPages" @click="nextPage">下一页</button>
        </div>
      </div>
    </main>

    <!-- 新闻详情弹窗 -->
    <div v-if="state.showNewsModal" class="modal-overlay" @click.self="state.showNewsModal = false">
      <div class="news-detail-modal">
        <div class="modal-header">
          <h3>{{ state.newsDetail.title }}</h3>
          <span class="modal-close" @click="state.showNewsModal = false">×</span>
        </div>
        <div class="modal-meta">
          来源: {{ state.newsDetail.source }} | 分类: {{ state.newsDetail.category }} | 发布: {{ formatTime(state.newsDetail.publish_date) }}
        </div>
        <div class="modal-body" v-html="sanitizeHtml(state.newsDetail.content)"></div>
        <div class="modal-images" v-if="state.newsDetail.images && state.newsDetail.images.length">
          <img v-for="img in state.newsDetail.images" :key="img.order" :src="img.url" />
        </div>
        <div class="modal-footer">
          <button class="modal-btn" @click="openNewsUrl(state.newsDetail.url)">查看原网页</button>
          <button class="modal-btn" @click="removeNewsFavorite(state.newsDetail)">取消收藏</button>
          <button class="modal-btn primary" @click="state.showNewsModal = false">关闭</button>
        </div>
      </div>
    </div>

    <!-- 题目详情弹窗 -->
    <div v-if="state.showQuestionModal" class="modal-overlay" @click.self="state.showQuestionModal = false">
      <div class="question-detail-modal">
        <div class="modal-header">
          <h3>题目详情</h3>
          <span class="modal-close" @click="state.showQuestionModal = false">×</span>
        </div>
        <div class="modal-meta">
          科目: {{ state.questionDetail.subject_name }} > {{ state.questionDetail.subcategory || '通用' }} |
          难度: {{ '★'.repeat(state.questionDetail.difficulty || 3) }}{{ '☆'.repeat(5 - (state.questionDetail.difficulty || 3)) }} ({{ state.questionDetail.difficulty || 3 }}/5) |
          全网正确率: {{ state.questionDetail.accuracy_rate }}%
        </div>
        <div class="modal-body">
          <div class="question-content-text" v-html="renderQuestionContent(state.questionDetail.question_content)"></div>
          <div class="question-options" v-if="state.questionDetail.options && state.questionDetail.options.length">
            <div v-for="(opt, idx) in state.questionDetail.options" :key="idx"
                 :class="['option-item', { 'correct-answer': isCorrectAnswer(idx, state.questionDetail) }]">
              <span class="option-label">{{ String.fromCharCode(65 + idx) }}.</span>
              <span class="option-text" v-html="renderQuestionContent(typeof opt === 'object' ? (opt.value || opt.text) : opt)"></span>
              <span v-if="isCorrectAnswer(idx, state.questionDetail)" class="correct-badge">✓ 正确答案</span>
            </div>
          </div>
        </div>
        <div class="answer-analysis" v-if="state.questionDetail.answer_analysis">
          <h4>📖 答案解析</h4>
          <p v-html="renderQuestionContent(state.questionDetail.answer_analysis)"></p>
        </div>
        <div class="modal-footer">
          <button class="modal-btn" @click="removeQuestionFavorite(state.questionDetail.fav_id)">取消收藏</button>
          <button class="modal-btn primary" @click="state.showQuestionModal = false">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
  import { defineComponent, reactive, computed } from 'vue';
  import { Star } from '@vtj/icons';
  import { XIcon } from '@vtj/ui';
  import NavBar from './navbar.vue';
  import { useProvider } from '@vtj/renderer';
  import { renderQuestionContent, sanitizeHtml } from '@/utils/questionRender';
  import { useNotesStore } from '@/modules/notes/store';
  export default defineComponent({
    name: 'Favorites',
    components: { NavBar, XIcon },
    setup(props) {
      const notesStore = useNotesStore();
      const provider = useProvider({ id: 'favorites', version: '1785750000002' });
      const state = reactive({
        activeTab: 'news',
        newsFavorites: [],
        questionFavorites: [],
        stats: { question_favorites: 0, news_favorites: 0, quote_favorites: 0, news_quote_total: 0, total: 0 },
        page: 1,
        pageSize: 20,
        total: 0,
        loading: false,
        showNewsModal: false,
        newsDetail: {},
        showQuestionModal: false,
        questionDetail: {}
      });
      return { state, props, provider, notesStore, Star, renderQuestionContent, sanitizeHtml };
    },
    computed: {
      totalPages() {
        return Math.max(1, Math.ceil(this.state.total / this.state.pageSize));
      }
    },
    mounted() {
      this.loadStats();
      this.loadFavorites();
    },
    methods: {
      getJsonHeaders() {
        return window.__VTJ_AUTH__.getJsonHeaders();
      },
      formatTime(iso) {
        if (!iso) return '';
        var d = new Date(iso);
        var pad = function(n) { return String(n).padStart(2, '0'); };
        return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
      },
      isCorrectAnswer(idx, item) {
        if (!item.answer || !item.options) return false;
        var correctLetters = item.answer.toUpperCase().split('');
        var currentLetter = String.fromCharCode(65 + idx);
        return correctLetters.includes(currentLetter);
      },
      switchTab(tab) {
        this.state.activeTab = tab;
        this.state.page = 1;
        this.loadFavorites();
      },
      async loadStats() {
        try {
          await this.notesStore.loadCollectionStats();
          if (this.notesStore.collectionStats) this.state.stats = this.notesStore.collectionStats;
        } catch(e) { console.warn('加载统计失败:', e); }
      },
      async loadFavorites() {
        this.state.loading = true;
        try {
          await this.notesStore.loadFavorites(this.state.page);
          if (this.state.activeTab === 'news') {
            this.state.newsFavorites = this.notesStore.newsFavorites;
            this.state.total = this.notesStore.newsFavorites.length;
          } else {
            this.state.questionFavorites = this.notesStore.questionFavorites;
            this.state.total = this.notesStore.questionFavorites.length;
          }
        } catch(e) { console.warn('加载收藏失败:', e); }
        finally { this.state.loading = false; }
      },
      async viewNewsDetail(item) {
        if (item.fav_type === 'quote') {
          // 金句直接展示
          this.state.newsDetail = {
            id: 0,
            title: '申论金句',
            source: item.source || '',
            category: item.category || '',
            publish_date: '',
            content: '<p style="font-size:18px; line-height:2; color:#333;">' + item.content + '</p>',
            images: [],
            url: '',
            fav_type: item.fav_type,
            fav_id: item.fav_id,
            quote_id: item.quote_id,
            obsidian_source: item.obsidian_source
          };
          this.state.showNewsModal = true;
          return;
        }
        // 新闻调用详情接口（使用 apiFetch 保证认证头注入）
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/news/' + item.news_id, { headers: this.getJsonHeaders() });
          if (res.ok) {
            this.state.newsDetail = await res.json();
            this.state.showNewsModal = true;
          }
        } catch(e) { console.warn('加载新闻详情失败:', e); }
      },
      viewQuestionDetail(item) {
        this.state.questionDetail = item;
        this.state.showQuestionModal = true;
      },
      openNewsUrl(url) {
        if (url) window.open(url, '_blank');
      },
      async removeNewsFavorite(item) {
        if (item && item.fav_type === 'quote') {
          // 数据库金句取消收藏
          if (item.quote_id) {
            try {
              await window.__VTJ_AUTH__.apiFetch('/api/quotes/' + item.quote_id + '/favorite', { method: 'POST', headers: this.getJsonHeaders() });
              this.state.showNewsModal = false;
              this.loadFavorites();
              this.loadStats();
            } catch(e) { console.warn('取消收藏失败:', e); }
            return;
          }
          // Obsidian 金句取消收藏
          if (item.obsidian_source) {
            try {
              await window.__VTJ_AUTH__.apiFetch('/api/quotes/obsidian/' + encodeURIComponent(item.obsidian_source) + '/favorite', { method: 'POST', headers: this.getJsonHeaders() });
              this.state.showNewsModal = false;
              this.loadFavorites();
              this.loadStats();
            } catch(e) { console.warn('取消收藏失败:', e); }
            return;
          }
        }
        // 新闻取消收藏
        const newsId = item && (item.news_id || item.id);
        if (!newsId) return;
        try {
          await window.__VTJ_AUTH__.apiFetch('/api/news/' + newsId + '/favorite', { method: 'POST', headers: this.getJsonHeaders() });
          this.state.showNewsModal = false;
          this.loadFavorites();
          this.loadStats();
        } catch(e) { console.warn('取消收藏失败:', e); }
      },
      async removeQuestionFavorite(favId) {
        if (favId === null || favId === undefined || favId === '') {
          console.warn('取消收藏失败：无效的收藏ID', favId);
          return;
        }
        try {
          await this.notesStore.removeFavorite(favId, 'question');
          this.state.showQuestionModal = false;
          this.loadFavorites();
          this.loadStats();
        } catch(e) { console.warn('取消收藏失败:', e); }
      },
      prevPage() {
        if (this.state.page > 1) { this.state.page--; this.loadFavorites(); }
      },
      nextPage() {
        if (this.state.page < this.totalPages) { this.state.page++; this.loadFavorites(); }
      }
    }
  });
</script>

<style scoped>
.favorites-page {
  font-size: 15px;
  min-height: 100vh;
  background: #f5f7fa;
}
.favorites-main {
  max-width: 1400px;
  min-height: 800px;
  margin: 0 auto;
  padding: 20px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}
.fav-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 16px;
  border-bottom: 2px solid #c41e3a;
}
.fav-header h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 22px;
  color: #1a3a5c;
  margin: 0;
}
.fav-stats { display: flex; gap: 16px; }
.stat-item {
  font-size: 14px;
  color: #666;
  padding: 4px 12px;
  background: #f0f4f8;
  border-radius: 6px;
}
.stat-item.total {
  color: #c41e3a;
  font-weight: 600;
  background: #fff0f0;
}
.tab-bar {
  display: flex;
  gap: 4px;
  margin: 20px 0;
  border-bottom: 1px solid #e8e8e8;
}
.tab-item {
  padding: 10px 24px;
  font-size: 15px;
  color: #666;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.3s;
}
.tab-item:hover { color: #c41e3a; }
.tab-item.active {
  color: #c41e3a;
  border-bottom-color: #c41e3a;
  font-weight: 600;
}
.fav-content { min-height: 500px; }
.fav-list { display: flex; flex-direction: column; gap: 12px; }
.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}
.empty-icon { font-size: 48px; display: block; margin-bottom: 12px; }
.fav-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  background: #fafbfc;
  border: 1px solid #e8e8e8;
  border-left: 4px solid #1a3a5c;
  border-radius: 8px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.3s;
}
.fav-card:hover {
  box-shadow: 0 2px 12px rgba(196, 30, 58, 0.12);
  border-left-color: #c41e3a;
}
.question-fav { border-left-color: #c41e3a; }
.fav-type-badge {
  flex-shrink: 0;
  padding: 4px 10px;
  font-size: 12px;
  border-radius: 4px;
  font-weight: 600;
}
.fav-type-badge.quote { background: #fff8e1; color: #f57c00; }
.fav-type-badge.news { background: #e3f2fd; color: #1976d2; }
.fav-type-badge.question { background: #fce4ec; color: #c41e3a; }
.fav-card-body { flex: 1; min-width: 0; }
.fav-content-text {
  font-size: 15px;
  color: #333;
  line-height: 1.6;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.question-text { -webkit-line-clamp: 3; }
.fav-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: #999;
}
.fav-action {
  flex-shrink: 0;
  font-size: 13px;
  color: #c41e3a;
  align-self: center;
  white-space: nowrap;
}
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-top: 24px;
  padding: 16px 0;
}
.page-btn {
  padding: 6px 16px;
  font-size: 14px;
  color: #1a3a5c;
  background: #fff;
  border: 1px solid #1a3a5c;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s;
}
.page-btn:hover:not(:disabled) { background: #1a3a5c; color: #fff; }
.page-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.page-info { font-size: 14px; color: #666; }

/* 弹窗样式 */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.news-detail-modal, .question-detail-modal {
  background: #fff;
  border-radius: 12px;
  width: 90%;
  max-width: 800px;
  max-height: 85vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 2px solid #c41e3a;
}
.modal-header h3 { font-size: 18px; color: #1a3a5c; margin: 0; flex: 1; }
.modal-close { font-size: 28px; color: #999; cursor: pointer; line-height: 1; }
.modal-close:hover { color: #c41e3a; }
.modal-meta {
  padding: 12px 24px;
  font-size: 13px;
  color: #666;
  background: #f9f9f9;
  border-bottom: 1px solid #eee;
}
.modal-body {
  padding: 20px 24px;
  font-size: 15px;
  line-height: 1.8;
  color: #333;
  flex: 1;
  overflow-y: auto;
}
.modal-body img { max-width: 100%; border-radius: 8px; margin: 8px 0; }
.modal-images { padding: 0 24px 16px; }
.modal-images img { max-width: 100%; border-radius: 8px; margin-bottom: 8px; }
.question-content-text {
  font-size: 16px;
  line-height: 1.8;
  margin-bottom: 16px;
  color: #333;
}
.question-options { display: flex; flex-direction: column; gap: 10px; }
.option-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 14px;
  background: #f9f9f9;
  border-radius: 6px;
  border-left: 3px solid transparent;
  font-size: 15px;
  line-height: 1.6;
}
.option-item.correct-answer {
  background: #e8f5e9;
  border-left: 4px solid #4caf50;
  color: #2e7d32;
  font-weight: 600;
}
.option-label { font-weight: 600; flex-shrink: 0; }
.option-text { flex: 1; }
.correct-badge {
  color: #4caf50;
  font-weight: bold;
  margin-left: 8px;
  flex-shrink: 0;
}
.answer-analysis {
  padding: 16px 24px;
  background: #f9f9f9;
  border-top: 1px solid #eee;
}
.answer-analysis h4 {
  font-size: 15px;
  color: #1a3a5c;
  margin: 0 0 8px 0;
}
.answer-analysis p {
  font-size: 14px;
  line-height: 1.8;
  color: #555;
  margin: 0;
}
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid #eee;
}
.modal-btn {
  padding: 8px 20px;
  font-size: 14px;
  color: #1a3a5c;
  background: #fff;
  border: 1px solid #1a3a5c;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s;
}
.modal-btn:hover { background: #f0f4f8; }
.modal-btn.primary {
  background: #c41e3a;
  color: #fff;
  border-color: #c41e3a;
}
.modal-btn.primary:hover { background: #d32f2f; }
</style>
