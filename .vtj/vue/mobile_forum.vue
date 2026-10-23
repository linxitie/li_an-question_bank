<!-- 手机端论坛页 - VTJ规范版 -->
<template>
  <div class="mobile-forum-page">
    <!-- 顶部导航 -->
    <header class="top-nav">
      <div class="nav-left">
        <XIcon :icon="ArrowLeft" :size="22" color="#1A365D" class="nav-back" @click="goBack"></XIcon>
      </div>
      <h1 class="nav-title">学习论坛</h1>
      <div class="nav-right">
        <XIcon :icon="Plus" :size="22" color="#1A365D" class="nav-icon" @click="createPost"></XIcon>
      </div>
    </header>

    <!-- 分类标签 -->
    <section class="category-tabs">
      <div class="tab-scroll">
        <div 
          v-for="(tab, index) in tabs" 
          :key="index"
          :class="['cat-tab', { active: activeCategory === tab.key }]"
          @click="selectTab(tab.key)"
        >
          {{ tab.name }}
        </div>
      </div>
    </section>

    <!-- 主内容区 -->
    <main class="main-content">
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
                <img
                  v-if="post.avatar && !post.avatarFailed"
                  :src="post.avatar"
                  class="avatar-img"
                  alt="头像"
                  @error="onAvatarError(post)"
                />
                <XIcon v-else :icon="User" :size="16" color="#ffffff"></XIcon>
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
          
          <!-- 帖子图片 -->
          <div v-if="post.images && post.images.length > 0" class="post-images">
            <div 
              v-for="(img, imgIndex) in post.images.slice(0, 3)" 
              :key="imgIndex"
              class="post-image"
            >
              <img :src="img" alt="" />
            </div>
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
            <div class="post-actions">
              <XIcon :icon="MoreFilled" :size="16" color="#8899aa" class="more-btn"></XIcon>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <div v-if="filteredPosts.length === 0" class="empty-state">
        <XIcon :icon="ChatLineRound" :size="48" color="#e8ecf1"></XIcon>
        <p>暂无帖子</p>
      </div>
    </main>

    <!-- 发帖按钮 -->
    <div class="fab-button" @click="createPost">
      <XIcon :icon="Plus" :size="24" color="#ffffff"></XIcon>
    </div>

    <!-- 底部Tab栏：统一使用单一真源组件 src/components/MobileTabBar.vue -->
    <MobileTabBar active="forum" />
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { XIcon } from '@vtj/ui';
import MobileTabBar from '@/components/mobile/MobileTabBar.vue';
import {
  ArrowLeft,
  Plus,
  User,
  View,
  ChatDotRound,
  Star,
  MoreFilled,
  HomeFilled,
  Reading,
  Edit,
  ChatLineRound
} from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'MobileForum',
    components: {
      XIcon,
      MobileTabBar
    },
  setup() {
    const router = useRouter();
    const provider = useProvider({ id: 'mobile_forum', version: '1788919369989' });

    // 分类标签
    const activeCategory = ref('all');
    const tabs = ref([
      { key: 'all', name: '全部' },
      { key: 'discuss', name: '学习讨论' },
      { key: 'share', name: '经验分享' },
      { key: 'question', name: '答疑解惑' },
      { key: 'resource', name: '资料分享' }
    ]);
    
    // 帖子列表（只使用接口数据，禁止内置演示帖）
    const posts = ref<any[]>([]);
    
    // 过滤帖子
    const filteredPosts = computed(() => {
      if (activeCategory.value === 'all') {
        return posts.value;
      }
      return posts.value.filter(p => p.category === activeCategory.value);
    });
    
    // 加载真实帖子数据
    const loadPosts = async () => {
      try {
        // 补认证头：缺失时后端只会返回公开数据，私有/审核态字段与用户信息会缺失
        const auth = (window as any).__VTJ_AUTH__;
        const res = await fetch('/api/forum/posts', {
          headers: auth && auth.getAuthHeaders ? auth.getAuthHeaders() : {}
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const typeMap: Record<string, string> = {
          DISCUSSION: 'discuss',
          EXPERIENCE: 'share',
          RESOURCE: 'resource',
          FEELING: 'discuss'
        };
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
          return {
            id: p.id,
            title: p.title,
            excerpt: p.content || '',
            author: (p.user && p.user.nickname) || '匿名',
            time,
            avatar: (p.user && p.user.avatar) || '',
            avatarFailed: false,
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
      } catch (error) {
        console.error('加载帖子失败:', error);
        posts.value = [];
      }
    };

    onMounted(loadPosts);

    // 头像加载失败时降级为默认人形图标，避免出现破图
    const onAvatarError = (post: any) => {
      if (post) post.avatarFailed = true;
    };

    // 方法
    const goBack = () => router.back();
    
    const selectTab = (key: string) => {
      activeCategory.value = key;
    };
    
    const createPost = () => {
      router.push('/mobile/forum/create');
    };
    
    const viewPost = (post: any) => {
      router.push(`/mobile/forum/${post.id}`);
    };

    return {
      activeCategory,
      tabs,
      filteredPosts,
      goBack,
      selectTab,
      createPost,
      viewPost,
      onAvatarError,
      ArrowLeft,
      Plus,
      User,
      View,
      ChatDotRound,
      Star,
      MoreFilled,
      HomeFilled,
      Reading,
      Edit,
      ChatLineRound
    };
  }
});
</script>

<style lang="css" scoped>
.mobile-forum-page {
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
  height: 56px;
  padding: 0 16px;
  background: #ffffff;
  border-bottom: 1px solid #f0f2f5;
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-left,
.nav-right {
  width: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.nav-back,
.nav-icon {
  cursor: pointer;
  transition: opacity 0.2s;
}

.nav-back:hover,
.nav-icon:hover {
  opacity: 0.7;
}

.nav-title {
  font-size: 18px;
  font-weight: 700;
  color: #1A365D;
  margin: 0;
}

/* 分类标签 */
.category-tabs {
  background: #ffffff;
  border-bottom: 1px solid #f0f2f5;
  padding: 12px 16px;
}

.tab-scroll {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.cat-tab {
  padding: 8px 16px;
  border-radius: 20px;
  font-size: 14px;
  font-weight: 500;
  color: #5a6488;
  background: #f5f7fa;
  cursor: pointer;
  transition: all 0.3s ease;
  white-space: nowrap;
}

.cat-tab.active {
  background: #1A365D;
  color: #ffffff;
}

.cat-tab:hover:not(.active) {
  background: #e8ecf1;
}

/* 主内容区 */
.main-content {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  padding-bottom: 100px;
}

/* 帖子列表 */
.post-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.post-card {
  background: #ffffff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
  transition: all 0.3s ease;
}

.post-card:hover {
  box-shadow: 0 4px 16px rgba(26, 54, 95, 0.1);
}

/* 帖子头部 */
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
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
}

/* 真实头像：铺满圆形容器，避免变形 */
.avatar-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 50%;
  display: block;
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

/* 帖子内容 */
.post-content {
  margin-bottom: 12px;
}

.post-title {
  font-size: 16px;
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

/* 帖子图片 */
.post-images {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.post-image {
  width: 80px;
  height: 80px;
  border-radius: 8px;
  overflow: hidden;
  background: #f5f7fa;
}

.post-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 帖子底部 */
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

.more-btn {
  cursor: pointer;
  padding: 4px;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
}

.empty-state p {
  font-size: 14px;
  color: #8899aa;
  margin: 16px 0 0;
}

/* 发帖按钮 */
.fab-button {
  position: fixed;
  bottom: 80px;
  right: 20px;
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg, #1A365D 0%, #2a5298 100%);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(26, 54, 95, 0.3);
  cursor: pointer;
  transition: all 0.3s ease;
  z-index: 99;
}

.fab-button:hover {
  transform: scale(1.1);
}

/* 底部Tab栏样式已收敛到单一真源组件 src/components/MobileTabBar.vue */

@media (max-width: 375px) {
  .post-card {
    padding: 12px;
  }
  
  .post-title {
    font-size: 15px;
  }
  
  .fab-button {
    width: 50px;
    height: 50px;
    bottom: 70px;
    right: 16px;
  }
}
</style>
