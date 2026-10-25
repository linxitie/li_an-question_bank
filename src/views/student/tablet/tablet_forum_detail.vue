<!-- 平板端论坛帖子详情页：独立整页，版式对齐 PC 详情卡 -->
<template>
  <div class="tablet-forum-detail">
    <header class="topbar">
      <button class="back-btn" type="button" @click="goBack">←</button>
      <h1 class="title">帖子详情</h1>
      <span class="topbar-spacer" />
    </header>

    <main class="content">
      <div v-if="loading" class="state-loading">加载中...</div>
      <div v-else-if="loadError" class="state-error">{{ loadError }}</div>
      <div v-else-if="!post" class="state-empty">帖子不存在或已被删除</div>
      <article v-else class="detail-card">
        <div class="card-body">
          <div class="post-badges">
            <span v-if="post.isTop" class="badge badge-top">置顶</span>
            <span v-if="post.isEssence" class="badge badge-essence">精华</span>
          </div>

          <h2 class="post-title" :style="{ color: titleColorValue(post.titleColor) }">
            {{ post.title }}
          </h2>

          <section class="post-author">
            <UserBadge
              avatar-only
              size="md"
              :src="post.user?.avatar"
              :name="post.user?.nickname"
              :user-id="post.user?.id" />
            <div class="author-meta">
              <span class="author-name">{{ post.user?.nickname || '匿名' }}</span>
              <span class="author-time">{{ formatTime(post.createTime) }}</span>
            </div>
          </section>

          <section class="post-body">
            <ForumContent :content="post.content" />
          </section>

          <AttachmentList
            v-if="post.attachments && post.attachments.length"
            :attachments="post.attachments"
            mode="post" />

          <footer class="post-stats">
            <button class="like-btn" type="button" @click="reactToPost('like')">
              👍 {{ post.likeCount }}
            </button>
            <span class="stat">💬 {{ post.commentCount }}</span>
            <span class="stat">👁 {{ post.viewCount }}</span>
          </footer>
        </div>
      </article>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import AttachmentList from '@/components/forum/AttachmentList.vue';
import ForumContent from '@/components/forum/ForumContent.vue';
import UserBadge from '@/components/forum/UserBadge.vue';
import { titleColorValue } from '@/components/forum/titleColors';
import type { ForumReactionCode } from '@/modules/community/api';
import { useCommunityStore } from '@/modules/community/store';

const route = useRoute();
const router = useRouter();
const store = useCommunityStore();

const postId = Number(route.params.id);
const post = computed(() => store.detail);
const loading = ref(true);
const loadError = ref('');

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/tablet/forum');
};

const formatTime = (iso: string | null | undefined) => {
  if (!iso) return '';
  const t = new Date(iso).getTime();
  const diff = Date.now() - t;
  const min = Math.floor(diff / 60000);
  if (min < 1) return '刚刚';
  if (min < 60) return `${min}分钟前`;
  if (min < 1440) return `${Math.floor(min / 60)}小时前`;
  if (min < 43200) return `${Math.floor(min / 1440)}天前`;
  return new Date(iso).toLocaleDateString();
};

const reactToPost = async (reaction: ForumReactionCode) => {
  try {
    await store.reactToPost(postId, reaction);
  } catch (e) {
    console.error('点赞失败:', e);
  }
};

const load = async () => {
  loading.value = true;
  loadError.value = '';

  if (!Number.isFinite(postId) || postId <= 0) {
    loadError.value = '帖子不存在或已被删除';
    loading.value = false;
    return;
  }

  const detail = await store.loadPost(postId);
  if (!detail) loadError.value = '帖子不存在或已被删除';
  loading.value = false;
};

onMounted(load);
</script>

<style scoped>
.tablet-forum-detail {
  min-height: 100vh;
  background: #f5f7fa;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
}

.topbar {
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e8ecf1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.back-btn {
  width: 40px;
  height: 40px;
  border: none;
  background: none;
  font-size: 20px;
  color: #1a2b5f;
  cursor: pointer;
  border-radius: 8px;
}

.back-btn:hover {
  background: #f0f4fa;
}

.title {
  font-size: 17px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0;
}

.topbar-spacer {
  width: 40px;
}

.content {
  padding: 24px;
}

.detail-card {
  max-width: 920px;
  margin: 0 auto;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(26, 54, 93, 0.06);
}

.state-loading,
.state-error,
.state-empty {
  max-width: 920px;
  margin: 0 auto;
  padding: 48px 24px;
  text-align: center;
  color: #8899aa;
  font-size: 14px;
  background: #fff;
  border-radius: 12px;
}

.state-error {
  color: #c41e3a;
}

.card-body {
  padding: 28px 32px;
}

.post-badges {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.post-badges:empty {
  display: none;
}

.badge {
  font-size: 12px;
  line-height: 1;
  padding: 4px 8px;
  border-radius: 6px;
}

.badge-top {
  background: #fff4e6;
  color: #d97706;
}

.badge-essence {
  background: #fdecef;
  color: #c41e3a;
}

.post-title {
  font-size: 22px;
  line-height: 1.4;
  margin: 0 0 16px;
  font-weight: 700;
  word-break: break-word;
}

.post-author {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 16px;
  border-bottom: 1px solid #eef2f7;
}

.author-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.author-name {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
}

.author-time {
  font-size: 12px;
  color: #8899aa;
}

.post-body {
  padding: 20px 0;
  font-size: 15px;
  line-height: 1.7;
  color: #2b3a55;
  word-break: break-word;
}

.post-stats {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 12px 0 4px;
  border-top: 1px solid #eef2f7;
  color: #8899aa;
  font-size: 13px;
}

.like-btn {
  border: none;
  background: #f5f7fa;
  border-radius: 16px;
  padding: 6px 14px;
  font-size: 13px;
  color: #1a2b5f;
  cursor: pointer;
}

.like-btn:hover {
  background: #eef2f8;
}
</style>
