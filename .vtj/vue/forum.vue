<!-- 论坛模块 -->
<template>
  <div class="forum-page">
    <NavBar></NavBar>
    <main class="forum-main">
      <div class="forum-header">
        <h2>
          <XIcon :icon="ChatRound" :size="24" color="#c41e3a"></XIcon>
          <span> 备考论坛</span>
        </h2>
        <button class="post-btn" @click="openNewPost">
          <XIcon :icon="EditPen" :size="16" color="#ffffff"></XIcon>
          <span> 发布新帖</span>
        </button>
      </div>
      <div class="forum-body">
        <div class="forum-left">
          <div class="category-tabs">
            <button
              v-for="(cat, index) in categories"
              :key="cat.key"
              :class="['cat-btn', { active: state.activeCategory === cat.key }]"
              @click="switchCategory(cat.key)">
              <span>
                <span> {{ cat.name }}</span>
                <span> </span
              ></span>
              <span class="cat-count"> {{ cat.count }}</span>
            </button>
          </div>
          <div class="post-list">
            <div
              v-for="(post, index) in filteredPosts"
              :key="post.id"
              class="post-item"
              @click="viewPost(post)">
              <div class="post-avatar">
                <span class="avatar-emoji"> {{ post.avatar }}</span>
              </div>
              <div class="post-content">
                <h4 class="post-title">
                  {{ post.title }}
                </h4>
                <p class="post-excerpt">
                  {{ post.excerpt }}
                </p>
                <div class="post-meta">
                  <span class="meta-author"> {{ post.author }}</span>
                  <span class="meta-dot"> ·</span>
                  <span class="meta-date"> {{ post.date }}</span>
                  <span class="meta-dot"> ·</span>
                  <span class="meta-replies">
                    <XIcon
                      :icon="ChatLineRound"
                      :size="12"
                      color="#8a8faa"></XIcon>
                    <span>
                      <span> </span>
                      <span> {{ post.replies }}</span></span
                    ></span
                  >
                  <span class="meta-dot"> ·</span>
                  <span class="meta-views">
                    <XIcon :icon="View" :size="12" color="#8a8faa"></XIcon>
                    <span>
                      <span> </span>
                      <span> {{ post.views }}</span></span
                    ></span
                  >
                </div>
              </div>
              <div
                class="post-tag div_2732jvez4om"
                :style="{ background: getTagColor(post.category) }">
                {{ state.categoryMap[post.category] }}
              </div>
            </div>
          </div>
          <div class="pagination">
            <button :disabled="state.page === 1" @click="state.page--">
              上一页
            </button>
            <span class="page-info">
              <span>
                <span> {{ state.page }}</span>
                <span> /</span>
                <span> {{ totalPages }}</span></span
              ></span
            >
            <button :disabled="state.page >= totalPages" @click="state.page++">
              下一页
            </button>
          </div>
        </div>
        <aside class="forum-right">
          <div class="right-card hot-posts">
            <h4>
              <XIcon :icon="TrendCharts" :size="16" color="#ef4444"></XIcon>
              <span> 热门帖子</span>
            </h4>
            <div
              v-for="(hot, index) in hotPosts"
              :key="hot.id"
              class="hot-item"
              @click="viewPost(hot)">
              <span class="hot-rank"> {{ hot.rank }}</span>
              <span class="hot-title"> {{ hot.title }}</span>
              <span class="hot-replies">
                <span>
                  <span> {{ hot.replies }}</span>
                  <span> 回复</span></span
                ></span
              >
            </div>
          </div>
          <div class="right-card user-stats">
            <h4>
              <XIcon :icon="User" :size="16" color="#1a2b5f"></XIcon>
              <span> 论坛活跃</span>
            </h4>
            <div class="stats-grid">
              <div class="stats-item">
                <span class="stats-number"> {{ state.forumStats.posts }}</span>
                <span class="stats-label"> 帖子</span>
              </div>
              <div class="stats-item">
                <span class="stats-number"> {{ state.forumStats.users }}</span>
                <span class="stats-label"> 用户</span>
              </div>
              <div class="stats-item">
                <span class="stats-number"> {{ state.forumStats.online }}</span>
                <span class="stats-label"> 在线</span>
              </div>
            </div>
          </div>
        </aside>
      </div>
      <div
        v-if="state.showNewPost"
        class="modal-overlay"
        @click.self="state.showNewPost = false">
        <div class="modal-card">
          <h3>发布新帖</h3>
          <input
            v-model="state.newPost.title"
            class="modal-input"
            placeholder="请输入标题..." />
          <textarea
            v-model="state.newPost.content"
            rows="6"
            class="modal-textarea"
            placeholder="请输入内容..."></textarea>
          <select v-model="state.newPost.category" class="modal-select">
            <option value="">选择分类</option>
            <option value="xc">行测</option>
            <option value="sl">申论</option>
            <option value="ga">公专</option>
            <option value="other">其他</option>
          </select>
          <div class="modal-actions">
            <button class="cancel-btn" @click="state.showNewPost = false">
              取消
            </button>
            <button class="confirm-btn" @click="submitPost">发布</button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import {
    ChatRound,
    EditPen,
    ChatLineRound,
    View,
    TrendCharts,
    User
  } from '@vtj/icons';
  import NavBar from './navbar.vue';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'Forum',
    components: { NavBar, XIcon },
    setup(props) {
      const provider = useProvider({ id: 'forum', version: '1778919266946' });
      const state = reactive({
        page: 1,
        posts: [],
        newPost: { title: '', content: '', category: '' },
        pageSize: 8,
        forumStats: { posts: 3280, users: 12560, online: 328 },
        categoryMap: { xc: '行测', sl: '申论', ga: '公专', other: '其他' },
        showNewPost: false,
        activeCategory: 'all'
      });
      return {
        state,
        props,
        provider,
        ChatRound,
        EditPen,
        ChatLineRound,
        View,
        TrendCharts,
        User
      };
    },
    computed: {
      hotPosts() {
        return this.state.posts
          .sort((a, b) => b.replies - a.replies)
          .slice(0, 5)
          .map((p, i) => ({ ...p, rank: i + 1 }));
      },
      categories() {
        return [
          { key: 'all', name: '全部', count: this.state.posts.length },
          {
            key: 'xc',
            name: '行测',
            count: this.state.posts.filter((p) => p.category === 'xc').length
          },
          {
            key: 'sl',
            name: '申论',
            count: this.state.posts.filter((p) => p.category === 'sl').length
          },
          {
            key: 'ga',
            name: '公专',
            count: this.state.posts.filter((p) => p.category === 'ga').length
          },
          {
            key: 'other',
            name: '其他',
            count: this.state.posts.filter((p) => p.category === 'other').length
          }
        ];
      },
      totalPages() {
        const total =
          this.state.activeCategory === 'all'
            ? this.state.posts.length
            : this.state.posts.filter(
                (p) => p.category === this.state.activeCategory
              ).length;
        return Math.max(1, Math.ceil(total / this.state.pageSize));
      },
      filteredPosts() {
        let list =
          this.state.activeCategory === 'all'
            ? this.state.posts
            : this.state.posts.filter(
                (p) => p.category === this.state.activeCategory
              );
        const start = (this.state.page - 1) * this.state.pageSize;
        return list.slice(start, start + this.state.pageSize);
      }
    },
    methods: {
      viewPost(post) {
        this.$message.info('查看帖子详情：' + post.title);
      },
      loadPosts() {
        this.state.posts = [
          {
            id: 1,
            title: '行测判断推理秒杀技巧分享',
            author: '警校小王',
            date: '2024-12-22',
            replies: 56,
            views: 1230,
            category: 'xc',
            excerpt:
              '判断推理是行测中的重点题型，掌握这些秒杀技巧可以大幅提升做题速度...',
            avatar: '👮'
          },
          {
            id: 2,
            title: '申论大作文写作框架整理',
            author: '上岸前辈',
            date: '2024-12-21',
            replies: 88,
            views: 2450,
            category: 'sl',
            excerpt: '分享我的大作文万能写作框架，亲测有效，助力申论70+...',
            avatar: '👨‍⚖️'
          },
          {
            id: 3,
            title: '公专公安基础知识口诀合集',
            author: '老民警',
            date: '2024-12-20',
            replies: 102,
            views: 3210,
            category: 'ga',
            excerpt: '公安基础知识记忆口诀，朗朗上口，背下来考场不慌...',
            avatar: '🚔'
          },
          {
            id: 4,
            title: '2025公安联考备考时间线建议',
            author: '师兄说',
            date: '2024-12-19',
            replies: 45,
            views: 980,
            category: 'other',
            excerpt: '根据往年经验，合理规划备考时间线，每个阶段该做什么...',
            avatar: '🎓'
          },
          {
            id: 5,
            title: '数量关系蒙题大法，准确率实测60%',
            author: '数字达人',
            date: '2024-12-18',
            replies: 120,
            views: 4500,
            category: 'xc',
            excerpt: '数学不好？这些蒙题套路让你在不会做的时候也能拿分...',
            avatar: '🧮'
          },
          {
            id: 6,
            title: '申论归纳概括题常见陷阱',
            author: '阅卷老师',
            date: '2024-12-17',
            replies: 67,
            views: 1890,
            category: 'sl',
            excerpt: '作为阅卷老师，我总结了归纳概括题中最容易丢分的几个陷阱...',
            avatar: '📝'
          },
          {
            id: 7,
            title: '警察体能测试备考经验',
            author: '体测达人',
            date: '2024-12-16',
            replies: 35,
            views: 760,
            category: 'other',
            excerpt: '体能测试是公安联考的重要环节，分享我的训练计划...',
            avatar: '🏃'
          },
          {
            id: 8,
            title: '职业素养高频考点速记',
            author: '公专笔记',
            date: '2024-12-15',
            replies: 90,
            views: 2780,
            category: 'ga',
            excerpt: '整理了近年职业素养模块的高频考点，方便大家快速记忆...',
            avatar: '📋'
          },
          {
            id: 9,
            title: '行测资料分析速算技巧',
            author: '速算小王',
            date: '2024-12-14',
            replies: 42,
            views: 1120,
            category: 'xc',
            excerpt: '资料分析五个速算技巧，让你的做题速度快一倍...',
            avatar: '🔢'
          },
          {
            id: 10,
            title: '申论应用文写作模板',
            author: '文书达人',
            date: '2024-12-13',
            replies: 55,
            views: 1560,
            category: 'sl',
            excerpt: '应用文写作万能模板，背下这几个框架轻松应对...',
            avatar: '✍️'
          },
          {
            id: 11,
            title: '公安基础知识思维导图',
            author: '导图控',
            date: '2024-12-12',
            replies: 78,
            views: 2340,
            category: 'ga',
            excerpt: '用思维导图的方式梳理公安基础知识，一目了然...',
            avatar: '🧠'
          },
          {
            id: 12,
            title: '联考心态调整经验分享',
            author: '过来人',
            date: '2024-12-11',
            replies: 110,
            views: 3800,
            category: 'other',
            excerpt: '备考后期心态很重要，分享我的心态调整方法...',
            avatar: '😊'
          }
        ];
      },
      submitPost() {
        if (!this.state.newPost.title.trim()) {
          this.$message.warning('请输入标题');
          return;
        }
        this.$message.success('发布成功！');
        this.state.showNewPost = false;
        this.state.newPost = { title: '', content: '', category: '' };
      },
      getTagColor(category) {
        const map = {
          xc: '#eff6ff',
          sl: '#fef3c7',
          ga: '#fce7f3',
          other: '#f0fdf4'
        };
        return map[category] || '#f8f9fc';
      },
      openNewPost() {
        this.state.showNewPost = true;
      },
      switchCategory(key) {
        this.state.activeCategory = key;
        this.state.page = 1;
      }
    },
    mounted() {
      this.loadPosts();
    }
  })
</script>
<style lang="css" scoped>
  .forum-page {
    min-height: 100vh;
    background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
    font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }
  .forum-main {
    max-width: 1300px;
    margin: 0 auto;
    padding: 24px 32px 40px;
  }
  .forum-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
  }
  .forum-header h2 {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 22px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0;
  }
  .post-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 12px 24px;
    border: none;
    border-radius: 12px;
    background: linear-gradient(135deg, #c41e3a, #e8384f);
    color: #ffffff;
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s;
    box-shadow: 0 2px 12px rgba(196, 30, 58, 0.3);
  }
  .post-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 18px rgba(196, 30, 58, 0.4);
  }
  .forum-body {
    display: grid;
    grid-template-columns: 1fr 300px;
    gap: 24px;
  }
  .forum-left {
    background: #ffffff;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.04);
  }
  .category-tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }
  .cat-btn {
    padding: 8px 16px;
    border: 1px solid #e8eaf0;
    border-radius: 20px;
    background: #f8f9fc;
    font-size: 13px;
    font-weight: 600;
    color: #5a6488;
    cursor: pointer;
    transition: all 0.3s;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .cat-btn:hover {
    border-color: #1a2b5f;
    color: #1a2b5f;
  }
  .cat-btn.active {
    background: #1a2b5f;
    color: #ffffff;
    border-color: #1a2b5f;
  }
  .cat-count {
    font-size: 11px;
    opacity: 0.7;
  }
  .post-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .post-item {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    padding: 16px;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.3s;
    border: 1px solid transparent;
  }
  .post-item:hover {
    background: #f8f9fc;
    border-color: #e8eaf0;
  }
  .post-avatar {
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: linear-gradient(135deg, #eef2ff, #e0e7ff);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .avatar-emoji {
    font-size: 22px;
  }
  .post-content {
    flex: 1;
    min-width: 0;
  }
  .post-title {
    font-size: 15px;
    font-weight: 700;
    color: #1a2b5f;
    margin: 0 0 6px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .post-excerpt {
    font-size: 12px;
    color: #8a8faa;
    margin: 0 0 8px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .post-meta {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: #8a8faa;
  }
  .meta-dot {
    color: #d1d5db;
  }
  .post-tag {
    padding: 4px 10px;
    border-radius: 8px;
    font-size: 11px;
    font-weight: 600;
    color: #1a2b5f;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 16px;
    margin-top: 20px;
    padding-top: 16px;
    border-top: 1px solid #f0f2f5;
  }
  .pagination button {
    padding: 6px 16px;
    border: 1px solid #e8eaf0;
    border-radius: 8px;
    background: #ffffff;
    cursor: pointer;
    font-size: 13px;
    color: #1a2b5f;
    transition: all 0.2s;
  }
  .pagination button:hover:not(:disabled) {
    background: #f0f2f5;
  }
  .pagination button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  .page-info {
    font-size: 13px;
    color: #5a6488;
  }
  .forum-right {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .right-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 10px rgba(26, 43, 95, 0.04);
  }
  .right-card h4 {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 14px;
    font-weight: 700;
    color: #1a2b5f;
    margin: 0 0 14px;
  }
  .hot-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0;
    border-bottom: 1px solid #f8f9fc;
    cursor: pointer;
    font-size: 12px;
    transition: all 0.2s;
  }
  .hot-item:hover {
    background: #f8f9fc;
    border-radius: 8px;
    padding-left: 8px;
  }
  .hot-rank {
    width: 20px;
    height: 20px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    font-weight: 700;
    color: #ffffff;
    flex-shrink: 0;
  }
  .hot-rank.rank-1 {
    background: #ef4444;
  }
  .hot-rank.rank-2 {
    background: #f97316;
  }
  .hot-rank.rank-3 {
    background: #f59e0b;
  }
  .hot-rank.rank-4,
  .hot-rank.rank-5 {
    background: #94a3b8;
  }
  .hot-title {
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: #1a2b5f;
  }
  .hot-replies {
    font-size: 10px;
    color: #8a8faa;
    flex-shrink: 0;
  }
  .stats-grid {
    display: flex;
    justify-content: space-around;
  }
  .stats-item {
    text-align: center;
  }
  .stats-number {
    display: block;
    font-size: 22px;
    font-weight: 900;
    color: #1a2b5f;
    font-family: 'DIN Alternate', sans-serif;
  }
  .stats-label {
    font-size: 11px;
    color: #8a8faa;
  }
  /* Modal */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.4);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
  }
  .modal-card {
    background: #ffffff;
    border-radius: 16px;
    padding: 28px;
    width: 520px;
    max-width: 90vw;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  }
  .modal-card h3 {
    font-size: 18px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0 0 20px;
  }
  .modal-input,
  .modal-textarea,
  .modal-select {
    width: 100%;
    padding: 12px;
    border: 1px solid #e8eaf0;
    border-radius: 10px;
    font-size: 13px;
    margin-bottom: 14px;
    outline: none;
    color: #1a2b5f;
    box-sizing: border-box;
  }
  .modal-textarea {
    resize: vertical;
  }
  .modal-actions {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    margin-top: 8px;
  }
  .cancel-btn {
    padding: 10px 20px;
    border: 1px solid #e8eaf0;
    border-radius: 10px;
    background: #ffffff;
    font-size: 13px;
    font-weight: 600;
    color: #5a6488;
    cursor: pointer;
  }
  .confirm-btn {
    padding: 10px 20px;
    border: none;
    border-radius: 10px;
    background: linear-gradient(135deg, #1a2b5f, #1e3470);
    color: #ffffff;
    font-size: 13px;
    font-weight: 700;
    cursor: pointer;
  }
</style>
