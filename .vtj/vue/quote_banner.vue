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
      <button class="refresh-btn" @click="refreshQuote">
        <XIcon :icon="RefreshRight" :size="14" color="#c41e3a"></XIcon>
        <span> 换一句</span>
      </button>
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
          <button class="news-modal-close" @click="closeNewsDetail">×</button>
        </div>
        <div class="news-modal-meta">
          <span class="news-modal-source-badge">{{ state.selectedNews.source === 'cpd' ? '人民公安报' : '人民网' }}</span>
          <span class="news-modal-date" v-if="state.selectedNews.publish_date">{{ state.selectedNews.publish_date.substring(0, 10) }}</span>
        </div>
        <div class="news-modal-body">
          <p class="news-modal-content">{{ state.selectedNews.content || state.selectedNews.summary || '暂无内容' }}</p>
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
  export default defineComponent({
    name: 'QuoteBanner',
    components: { XIcon },
    setup(props) {
      const provider = useProvider({ id: 'quote_banner', version: '1778918000715' });
      const state = reactive({
        quote: '忠诚是公安队伍代代相传的政治基因，是融入血脉的人民警察之魂。',
        author: '人民公安报',
        currentDate: '',
        newsItems: [],
        showNewsModal: false,
        selectedNews: {}
      });
      return { state, props, provider, ReadingLamp, RefreshRight, Document, Close };
    },
    methods: {
      formatDate() {
        const d = new Date();
        this.state.currentDate = `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`;
      },
      refreshQuote() {
        const quotes = [
          {
            text: '忠诚是公安队伍代代相传的政治基因，是融入血脉的人民警察之魂。',
            author: '人民公安报'
          },
          {
            text: '坚持以人民为中心的发展思想，把人民对美好生活的向往作为奋斗目标。',
            author: '人民公安报'
          },
          {
            text: '公平正义是执法司法工作的生命线，要努力让人民群众在每一起案件办理中都能感受到公平正义。',
            author: '人民公安报'
          },
          {
            text: '公安民警要坚定理想信念，强化责任担当，练就过硬本领，锤炼纪律作风。',
            author: '人民公安报'
          },
          {
            text: '国家安全是安邦定国的重要基石，维护国家安全是全国各族人民根本利益所在。',
            author: '人民公安报'
          }
        ];
        const next = quotes[Math.floor(Math.random() * quotes.length)];
        this.state.quote = next.text;
        this.state.author = next.author;
      },
      openNewsDetail(news) {
        this.state.selectedNews = news;
        this.state.showNewsModal = true;
      },
      closeNewsDetail() {
        this.state.showNewsModal = false;
        this.state.selectedNews = {};
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
  .news-modal-content { font-size: 20px; line-height: 1.9; color: #33375a; white-space: pre-wrap; margin: 0; }
  .news-modal-footer { display: flex; justify-content: flex-end; gap: 12px; padding: 16px 28px; border-top: 1px solid #f0f2f5; }
  .news-modal-link { padding: 8px 16px; border-radius: 8px; font-size: 13px; text-decoration: none; color: #5a6488; background: #f8f9fc; }
  .news-modal-link:hover { background: #f0f2f5; color: #1a2b5f; }
  .news-modal-btn { padding: 8px 20px; border: none; background: #c41e3a; color: #ffffff; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; }
  .news-modal-btn:hover { background: #a0182e; }
</style>
