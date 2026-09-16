<!-- 平板端论坛页 - VTJ规范版 -->
<template>
  <div class="tablet-forum-page">
    <!-- 顶部导航 -->
    <header class="top-nav">
      <div class="nav-left">
        <div class="logo">
          <XIcon :icon="Medal" :size="28" color="#1A365D"></XIcon>
          <span class="logo-text">砺安题库</span>
        </div>
      </div>
      <div class="nav-center">
        <h1 class="page-title">学习论坛</h1>
      </div>
      <div class="nav-right">
        <button class="create-btn" @click="createPost">
          <XIcon :icon="Plus" :size="18" color="#ffffff"></XIcon>
          发帖
        </button>
        <XIcon :icon="Bell" :size="22" color="#1A365D" class="nav-icon" @click="goToNotifications"></XIcon>
        <XIcon :icon="Setting" :size="22" color="#1A365D" class="nav-icon" @click="goToSettings"></XIcon>
        <div class="user-avatar" @click="goToProfile">
          <XIcon :icon="UserFilled" :size="24" color="#ffffff"></XIcon>
        </div>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="main-content">
      <!-- 左侧面板 -->
      <aside class="left-panel">
        <!-- 分类筛选 -->
        <div class="category-card">
          <div class="card-header">
            <h3 class="card-title">
              <XIcon :icon="Grid" :size="18" color="#1A365D"></XIcon>
              帖子分类
            </h3>
          </div>
          <div class="category-list">
            <div 
              v-for="(cat, index) in categories" 
              :key="index"
              :class="['category-item', { active: activeCategory === cat.key }]"
              @click="selectCategory(cat.key)"
            >
              <XIcon :icon="cat.icon" :size="18" color="currentColor"></XIcon>
              <span class="category-name">{{ cat.name }}</span>
              <span class="category-count">{{ cat.count }}</span>
            </div>
          </div>
        </div>

        <!-- 热门标签 -->
        <div class="tags-card">
          <div class="card-header">
            <h3 class="card-title">
              <XIcon :icon="Tag" :size="18" color="#1A365D"></XIcon>
              热门标签
            </h3>
          </div>
          <div class="tags-list">
            <span 
              v-for="(tag, index) in hotTags" 
              :key="index"
              class="tag-item"
              @click="searchByTag(tag)"
            >
              {{ tag }}
            </span>
          </div>
        </div>
      </aside>

      <!-- 中间内容区 -->
      <section class="center-content">
        <!-- 筛选栏 -->
        <div class="filter-bar">
          <div class="filter-tabs">
            <div 
              v-for="(tab, index) in filterTabs" 
              :key="index"
              :class="['filter-tab', { active: activeFilter === tab.key }]"
              @click="selectFilter(tab.key)"
            >
              {{ tab.name }}
            </div>
          </div>
        </div>

        <!-- 帖子列表 -->
        <div class="post-list">
          <div 
            v-for="(post, index) in filteredPosts" 
            :key="index"
            class="post-card"
            @click="viewPost(post)"
          >
            <!-- 帖子头部 -->
            <div class="post-header">
              <div class="author-info">
                <div class="author-avatar" :style="{ background: post.avatarBg }">
                  <XIcon :icon="User" :size="16" color="#ffffff"></XIcon>
                </div>
                <div class="author-detail">
                  <span class="author-name">{{ post.author }}</span>
                  <span class="post-time">{{ post.time }}</span>
                </div>
              </div>
              <span v-if="post.tag" class="post-tag" :style="{ background: post.tagColor + '18', color: post.tagColor }">
                {{ post.tag }}
              </span>
            </div>
            
            <!-- 帖子内容 -->
            <div class="post-content">
              <h3 class="post-title">{{ post.title }}</h3>
              <p class="post-excerpt">{{ post.excerpt }}</p>
            </div>
            
            <!-- 帖子底部 -->
            <div class="post-footer">
              <div class="post-stats">
                <span class="stat-item">
                  <XIcon :icon="View" :size="16" color="#8899aa"></XIcon>
                  {{ post.views }}
                </span>
                <span class="stat-item">
                  <XIcon :icon="ChatDotRound" :size="16" color="#8899aa"></XIcon>
                  {{ post.comments }}
                </span>
                <span class="stat-item">
                  <XIcon :icon="Star" :size="16" color="#8899aa"></XIcon>
                  {{ post.likes }}
                </span>
              </div>
              <div class="post-tags">
                <span v-for="(tag, tIndex) in post.tags" :key="tIndex" class="post-tag-item">
                  {{ tag }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- 分页 -->
        <div class="pagination">
          <span class="page-info">共 {{ filteredPosts.length }} 帖子</span>
          <div class="page-buttons">
            <button class="page-btn" disabled>上一页</button>
            <button class="page-btn active">1</button>
            <button class="page-btn">2</button>
            <button class="page-btn">3</button>
            <button class="page-btn">下一页</button>
          </div>
        </div>
      </section>

      <!-- 右侧面板 -->
      <aside class="right-panel">
        <!-- 热门帖子 -->
        <div class="hot-card">
          <div class="card-header">
            <h3 class="card-title">
              <XIcon :icon="TrendCharts" :size="18" color="#c41e3a"></XIcon>
              热门帖子
            </h3>
          </div>
          <div class="hot-list">
            <div 
              v-for="(post, index) in hotPosts" 
              :key="index"
              class="hot-item"
              @click="viewPost(post)"
            >
              <span class="hot-rank" :class="{ top: index < 3 }">{{ index + 1 }}</span>
              <div class="hot-info">
                <span class="hot-title">{{ post.title }}</span>
                <span class="hot-views">{{ post.views }} 浏览</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 活跃用户 -->
        <div class="active-card">
          <div class="card-header">
            <h3 class="card-title">
              <XIcon :icon="UserFilled" :size="18" color="#1A365D"></XIcon>
              活跃用户
            </h3>
          </div>
          <div class="active-list">
            <div 
              v-for="(user, index) in activeUsers" 
              :key="index"
              class="active-item"
            >
              <div class="active-avatar" :style="{ background: user.avatarBg }">
                <XIcon :icon="User" :size="14" color="#ffffff"></XIcon>
              </div>
              <div class="active-info">
                <span class="active-name">{{ user.name }}</span>
                <span class="active-posts">{{ user.posts }} 帖子</span>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </main>

    <!-- 底部状态栏 -->
    <footer class="bottom-bar">
      <div class="bar-left">
        <span class="online-status">
          <XIcon :icon="CircleCheck" :size="14" color="#10b981"></XIcon>
          在线
        </span>
        <span class="sync-status">
          <XIcon :icon="Refresh" :size="14" color="#1890ff"></XIcon>
          数据已同步
        </span>
      </div>
      <div class="bar-right">
        <span class="version">v1.0.0</span>
      </div>
    </footer>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { XIcon } from '@vtj/ui';
import {
  Medal,
  Bell,
  Setting,
  UserFilled,
  Plus,
  Grid,
  Tag,
  TrendCharts,
  View,
  ChatDotRound,
  Star,
  User,
  CircleCheck,
  Refresh
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'TabletForum',
  components: {
    XIcon
  },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'tablet_forum', version: '1788919369989' });
    
    // 分类
    const activeCategory = ref('all');
    const categories = ref([
      { key: 'all', name: '全部帖子', icon: Grid, count: 256 },
      { key: 'discuss', name: '学习讨论', icon: ChatDotRound, count: 128 },
      { key: 'share', name: '经验分享', icon: Star, count: 64 },
      { key: 'question', name: '答疑解惑', icon: User, count: 45 },
      { key: 'resource', name: '资料分享', icon: Tag, count: 19 }
    ]);
    
    // 筛选
    const activeFilter = ref('all');
    const filterTabs = ref([
      { key: 'all', name: '最新' },
      { key: 'hot', name: '最热' },
      { key: 'essence', name: '精华' }
    ]);
    
    // 热门标签
    const hotTags = ref(['行测', '申论', '公安', '政治', '法律', '经验', '真题']);
    
    // 帖子列表
    const posts = ref([
      {
        id: 1,
        title: '公安联考行测备考经验分享',
        excerpt: '作为一名成功上岸的学姐，分享一下我的行测备考经验，希望能帮助到正在备考的同学们...',
        author: '上岸学姐',
        time: '2小时前',
        avatarBg: 'linear-gradient(135deg, #1A365D 0%, #2a5298 100%)',
        tag: '精华',
        tagColor: '#c41e3a',
        views: 1234,
        comments: 89,
        likes: 256,
        category: 'share',
        tags: ['行测', '经验']
      },
      {
        id: 2,
        title: '申论写作如何拿高分？求指导',
        excerpt: '申论写作一直是我的弱项，每次写都觉得无话可说，有没有大佬能指点一下？',
        author: '备考小白',
        time: '5小时前',
        avatarBg: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
        tag: '',
        tagColor: '',
        views: 567,
        comments: 45,
        likes: 78,
        category: 'question',
        tags: ['申论', '求助']
      },
      {
        id: 3,
        title: '2025年公安联考真题回忆版',
        excerpt: '刚考完，趁记忆还热乎，分享一下我能记住的真题，供大家参考...',
        author: '刚考完',
        time: '1天前',
        avatarBg: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
        tag: '热门',
        tagColor: '#f59e0b',
        views: 3456,
        comments: 156,
        likes: 512,
        category: 'discuss',
        tags: ['真题', '回忆']
      },
      {
        id: 4,
        title: '政治理论重点知识整理',
        excerpt: '整理了一份政治理论的重点知识，包括习近平新时代中国特色社会主义思想的核心要点...',
        author: '学霸笔记',
        time: '2天前',
        avatarBg: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)',
        tag: '资料',
        tagColor: '#10b981',
        views: 2345,
        comments: 67,
        likes: 432,
        category: 'resource',
        tags: ['政治', '资料']
      }
    ]);
    
    // 热门帖子
    const hotPosts = ref([
      { id: 1, title: '公安联考行测备考经验分享', views: 1234 },
      { id: 3, title: '2025年公安联考真题回忆版', views: 3456 },
      { id: 4, title: '政治理论重点知识整理', views: 2345 }
    ]);
    
    // 活跃用户
    const activeUsers = ref([
      { name: '上岸学姐', posts: 28, avatarBg: 'linear-gradient(135deg, #1A365D 0%, #2a5298 100%)' },
      { name: '学霸笔记', posts: 22, avatarBg: 'linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%)' },
      { name: '刚考完', posts: 15, avatarBg: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)' }
    ]);
    
    // 过滤帖子
    const filteredPosts = computed(() => {
      if (activeCategory.value === 'all') {
        return posts.value;
      }
      return posts.value.filter(p => p.category === activeCategory.value);
    });
    
    // 加载真实帖子数据（替换下方演示数据）
    onMounted(async () => {
      try {
        const res = await fetch('/api/forum/posts');
        if (res.ok) {
          const data = await res.json();
          if (data.posts && data.posts.length) {
            const typeMap: Record<string, string> = {
              DISCUSSION: 'discuss',
              EXPERIENCE: 'share',
              RESOURCE: 'resource',
              FEELING: 'discuss'
            };
            posts.value = data.posts.map((p: any) => {
              const t = new Date(p.createTime).getTime();
              const diff = Date.now() - t;
              const min = Math.floor(diff / 60000);
              let time = '';
              if (min < 1) time = '刚刚';
              else if (min < 60) time = min + '分钟前';
              else if (min < 1440) time = Math.floor(min / 60) + '小时前';
              else if (min < 43200) time = Math.floor(min / 1440) + '天前';
              else time = new Date(p.createTime).toLocaleDateString();
              return {
                id: p.id,
                title: p.title,
                excerpt: p.content || '',
                author: (p.user && p.user.nickname) || '匿名',
                time,
                avatarBg: 'linear-gradient(135deg, #1A365D 0%, #2a5298 100%)',
                tag: p.isEssence ? '精华' : (p.isTop ? '置顶' : ''),
                tagColor: p.isEssence ? '#c41e3a' : '#f59e0b',
                views: p.viewCount || 0,
                comments: p.commentCount || 0,
                likes: p.likeCount || 0,
                category: typeMap[p.shareType] || 'discuss',
                images: []
              };
            });
          }
        }
      } catch (error) {
        console.error('加载帖子失败:', error);
      }
    });

    // 方法
    const goToNotifications = () => router.push('/tablet/notifications');
    const goToSettings = () => router.push('/tablet/profile');
    const goToProfile = () => router.push('/tablet/profile');
    
    const selectCategory = (key: string) => {
      activeCategory.value = key;
    };
    
    const selectFilter = (key: string) => {
      activeFilter.value = key;
    };
    
    const createPost = () => {
      router.push('/tablet/forum/create');
    };
    
    const viewPost = (post: any) => {
      router.push(`/tablet/forum/${post.id}`);
    };
    
    const searchByTag = (tag: string) => {
      // 搜索标签
    };
    
    return {
      activeCategory,
      categories,
      activeFilter,
      filterTabs,
      hotTags,
      filteredPosts,
      hotPosts,
      activeUsers,
      goToNotifications,
      goToSettings,
      goToProfile,
      selectCategory,
      selectFilter,
      createPost,
      viewPost,
      searchByTag,
      Medal,
      Bell,
      Setting,
      UserFilled,
      Plus,
      Grid,
      Tag,
      TrendCharts,
      View,
      ChatDotRound,
      Star,
      User,
      CircleCheck,
      Refresh
    };
  }
});
</script>

<style lang="css" scoped>
.tablet-forum-page {
  min-height: 100vh;
  background: #f5f7fa;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  display: flex;
  flex-direction: column;
}

/* 顶部导航 */
.top-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  padding: 0 24px;
  background: #ffffff;
  border-bottom: 1px solid #f0f2f5;
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-left {
  display: flex;
  align-items: center;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-text {
  font-size: 20px;
  font-weight: 800;
  color: #1A365D;
}

.nav-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.page-title {
  font-size: 18px;
  font-weight: 700;
  color: #1A365D;
  margin: 0;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.create-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: linear-gradient(135deg, #1A365D 0%, #2a5298 100%);
  color: #ffffff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
}

.create-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(26, 54, 95, 0.3);
}

.nav-icon {
  cursor: pointer;
  transition: opacity 0.2s;
}

.nav-icon:hover {
  opacity: 0.7;
}

.user-avatar {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #1A365D 0%, #2a5298 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

/* 主内容区 */
.main-content {
  flex: 1;
  display: grid;
  grid-template-columns: 260px 1fr 280px;
  gap: 20px;
  padding: 20px;
  overflow: hidden;
}

/* 左侧面板 */
.left-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.category-card,
.tags-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0;
}

.category-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.category-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  color: #5a6488;
}

.category-item:hover {
  background: #f8f9fc;
  color: #1A365D;
}

.category-item.active {
  background: #1A365D;
  color: #ffffff;
}

.category-name {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
}

.category-count {
  font-size: 12px;
  color: #8899aa;
}

.category-item.active .category-count {
  color: rgba(255, 255, 255, 0.8);
}

.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-item {
  padding: 6px 12px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 12px;
  color: #5a6488;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tag-item:hover {
  background: #1A365D;
  color: #ffffff;
}

/* 中间内容区 */
.center-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.filter-bar {
  background: #ffffff;
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.filter-tabs {
  display: flex;
  gap: 12px;
}

.filter-tab {
  padding: 6px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  color: #5a6488;
  cursor: pointer;
  transition: all 0.2s ease;
}

.filter-tab:hover {
  background: #f5f7fa;
}

.filter-tab.active {
  background: #1A365D;
  color: #ffffff;
}

.post-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.post-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
  transition: all 0.3s ease;
}

.post-card:hover {
  box-shadow: 0 4px 16px rgba(26, 54, 95, 0.1);
  transform: translateY(-2px);
}

.post-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.author-info {
  display: flex;
  align-items: center;
  gap: 10px;
}

.author-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.author-detail {
  display: flex;
  flex-direction: column;
}

.author-name {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
}

.post-time {
  font-size: 12px;
  color: #8899aa;
}

.post-tag {
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
}

.post-content {
  margin-bottom: 12px;
}

.post-title {
  font-size: 18px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0 0 8px;
  line-height: 1.4;
}

.post-excerpt {
  font-size: 14px;
  color: #5a6488;
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.post-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 12px;
  border-top: 1px solid #f0f2f5;
}

.post-stats {
  display: flex;
  gap: 16px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #8899aa;
}

.post-tags {
  display: flex;
  gap: 8px;
}

.post-tag-item {
  padding: 4px 10px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 11px;
  color: #5a6488;
}

.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #ffffff;
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.page-info {
  font-size: 13px;
  color: #8899aa;
}

.page-buttons {
  display: flex;
  gap: 8px;
}

.page-btn {
  padding: 6px 12px;
  border: 1px solid #e8ecf1;
  border-radius: 6px;
  background: #ffffff;
  font-size: 13px;
  color: #5a6488;
  cursor: pointer;
  transition: all 0.2s ease;
}

.page-btn:hover:not(:disabled) {
  border-color: #1A365D;
  color: #1A365D;
}

.page-btn.active {
  background: #1A365D;
  border-color: #1A365D;
  color: #ffffff;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 右侧面板 */
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.hot-card,
.active-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}

.hot-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.hot-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  background: #f8f9fc;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s ease;
}

.hot-item:hover {
  background: #f0f2f5;
}

.hot-rank {
  width: 24px;
  height: 24px;
  background: #e8ecf1;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  color: #5a6488;
}

.hot-rank.top {
  background: #c41e3a;
  color: #ffffff;
}

.hot-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.hot-title {
  font-size: 14px;
  font-weight: 500;
  color: #1a2b5f;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hot-views {
  font-size: 12px;
  color: #8899aa;
}

.active-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.active-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border-radius: 8px;
}

.active-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.active-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.active-name {
  font-size: 14px;
  font-weight: 500;
  color: #1a2b5f;
}

.active-posts {
  font-size: 12px;
  color: #8899aa;
}

/* 底部状态栏 */
.bottom-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 40px;
  padding: 0 24px;
  background: #ffffff;
  border-top: 1px solid #f0f2f5;
}

.bar-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.online-status,
.sync-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #5a6488;
}

.version {
  font-size: 12px;
  color: #8899aa;
}

/* 响应式 */
@media (max-width: 767px) {
  .main-content {
    grid-template-columns: 1fr;
  }
  
  .left-panel,
  .right-panel {
    display: none;
  }
}
</style>
