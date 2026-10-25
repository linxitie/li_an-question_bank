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
            </div>
          </div>
        </div>

        <!-- 热门标签 -->
        <div class="tags-card">
          <div class="card-header">
            <h3 class="card-title">
              <XIcon :icon="PriceTag" :size="18" color="#1A365D"></XIcon>
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
                <UserBadge
                  class="author-avatar"
                  avatar-only
                  size="md"
                  :src="post.avatar"
                  :name="post.author"
                  :user-id="post.id" />
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
              <p class="post-excerpt"><ForumContent :content="post.excerpt" /></p>
              <AttachmentList
                v-if="post.attachments && post.attachments.length"
                :attachments="post.attachments"
                mode="post" />
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
  PriceTag,
  TrendCharts,
  View,
  ChatDotRound,
  Star,
  User,
  CircleCheck,
  Refresh
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';
import { avatarInitial } from '@/modules/community/avatar';
import ForumContent from '@/components/forum/ForumContent.vue';
import UserBadge from '@/components/forum/UserBadge.vue';
import AttachmentList from '@/components/forum/AttachmentList.vue';

export default defineComponent({
  name: 'TabletForum',
  components: {
    XIcon,
    ForumContent,
    UserBadge,
    AttachmentList
  },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'tablet_forum', version: '1788919369989' });
    
    // 分类
    const activeCategory = ref('all');
    // key 必须与后端 forum_post.share_type 枚举一致
    const categories = ref([
      { key: 'all', name: '全部帖子', icon: Grid },
      { key: 'DISCUSSION', name: '学习讨论', icon: ChatDotRound },
      { key: 'EXPERIENCE', name: '经验分享', icon: Star },
      { key: 'QUESTION', name: '答疑解惑', icon: User },
      { key: 'RESOURCE', name: '资料分享', icon: PriceTag },
      { key: 'FEELING', name: '心情打卡', icon: ChatDotRound }
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
    
    // 帖子列表（只使用接口数据，禁止内置演示帖）
    const posts = ref<any[]>([]);

    // 热门帖子与活跃用户均由真实数据派生，无数据时为空
    const hotPosts = computed(() =>
      [...posts.value]
        .sort((a, b) => (b.views || 0) - (a.views || 0))
        .slice(0, 3)
    );
    const activeUsers = ref<any[]>([]);
    
    // 过滤帖子
    const filteredPosts = computed(() => {
      if (activeCategory.value === 'all') {
        return posts.value;
      }
      return posts.value.filter(p => p.category === activeCategory.value);
    });
    
    // 加载真实帖子数据；分类由服务端 share_type 过滤，避免只筛当前页
    const loadPosts = async (categoryKey: string = activeCategory.value) => {
      try {
        const auth = (window as any).__VTJ_AUTH__;
        const params = new URLSearchParams({ limit: '50' });
        if (categoryKey && categoryKey !== 'all') {
          params.set('share_type', categoryKey);
        }
        const res = await fetch(`/api/forum/posts?${params.toString()}`, {
          headers: auth && auth.getAuthHeaders ? auth.getAuthHeaders() : {}
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const IMAGE_PATTERN = /\.(png|jpe?g|gif|webp)(\?.*)?$/i;
        posts.value = (data.posts || []).map((p: any) => {
          const t = new Date(p.createTime).getTime();
          const diff = Date.now() - t;
          const min = Math.floor(diff / 60000);
          let time = '';
          if (min < 1) time = '刚刚';
          else if (min < 60) time = min + '分钟前';
          else if (min < 1440) time = Math.floor(min / 60) + '小时前';
          else if (min < 43200) time = Math.floor(min / 1440) + '天前';
          else time = new Date(p.createTime).toLocaleDateString();
          const images = (Array.isArray(p.attachments) ? p.attachments : [])
            .map((att: any) => (att && typeof att.url === 'string' ? att.url : ''))
            .filter((url: string) => IMAGE_PATTERN.test(url));
          return {
            id: p.id,
            title: p.title,
            excerpt: p.content || '',
            author: (p.user && p.user.nickname) || '匿名',
            avatar: (p.user && p.user.avatar) || '',
            time,
            avatarBg: 'linear-gradient(135deg, #1A365D 0%, #2a5298 100%)',
            tag: p.isEssence ? '精华' : (p.isTop ? '置顶' : ''),
            tagColor: p.isEssence ? '#c41e3a' : '#f59e0b',
            views: p.viewCount || 0,
            comments: p.commentCount || 0,
            likes: p.likeCount || 0,
            category: p.shareType || 'DISCUSSION',
            attachments: Array.isArray(p.attachments) ? p.attachments : [],
            images
          };
        });
      } catch (error) {
        console.error('加载帖子失败:', error);
        posts.value = [];
      }
    };

    onMounted(() => loadPosts());

    // 方法
    const goToNotifications = () => router.push('/tablet/notifications');
    const goToSettings = () => router.push('/tablet/profile');
    const goToProfile = () => router.push('/tablet/profile');
    
    const selectCategory = async (key: string) => {
      if (activeCategory.value === key) return;
      activeCategory.value = key;
      await loadPosts(key);
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
      avatarInitial,
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
      PriceTag,
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
  overflow: hidden;
  flex-shrink: 0;
}

.author-avatar .avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.author-avatar .avatar-text {
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
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

.post-images {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 10px;
}

.post-images img {
  width: 100%;
  height: 110px;
  object-fit: cover;
  border-radius: 10px;
  background: #f2f5fa;
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
