<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">帖子详情</h1>
      <span class="spacer"></span>
    </header>

    <main class="body">
      <div v-if="post" class="post-card">
        <h2 class="post-title">{{ post.title }}</h2>
        <div class="post-meta">
          <span class="author">{{ post.user && post.user.nickname }}</span>
          <span class="time">{{ formatTime(post.createTime) }}</span>
          <span v-if="post.isTop" class="badge">置顶</span>
          <span v-if="post.isEssence" class="badge">精华</span>
        </div>
        <div class="post-content">{{ post.content }}</div>
        <div class="post-actions">
          <button class="action-btn" :class="{ liked: post.liked }" @click="toggleLike">👍 {{ post.likeCount || 0 }}</button>
          <span class="action-count">💬 {{ post.commentCount || 0 }}</span>
        </div>
      </div>

      <div class="comments">
        <h3 class="comments-title">评论 ({{ comments.length }})</h3>
        <div v-for="c in comments" :key="c.id" class="comment-item">
          <div class="comment-user">{{ c.user && c.user.nickname }}</div>
          <div class="comment-content">{{ c.content }}</div>
          <div class="comment-time">{{ formatTime(c.createTime) }}</div>
        </div>
        <div v-if="!comments.length" class="empty">暂无评论，快来抢沙发</div>
      </div>
    </main>

    <footer class="comment-bar">
      <input v-model="commentText" type="text" class="comment-input" placeholder="写下你的评论..." @keyup.enter="submitComment" />
      <button class="send-btn" @click="submitComment" :disabled="!commentText.trim()">发送</button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();
const post = ref<any>(null);
const comments = ref<any[]>([]);
const commentText = ref('');

const postId = route.params.id as string;

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/forum');
};

const formatTime = (iso: string) => {
  if (!iso) return '';
  const t = new Date(iso).getTime();
  const diff = Date.now() - t;
  const min = Math.floor(diff / 60000);
  if (min < 1) return '刚刚';
  if (min < 60) return min + '分钟前';
  if (min < 1440) return Math.floor(min / 60) + '小时前';
  if (min < 43200) return Math.floor(min / 1440) + '天前';
  return new Date(iso).toLocaleDateString();
};

const fetchDetail = async () => {
  try {
    const auth = (window as any).__VTJ_AUTH__;
    const res = await auth.apiFetch('/api/forum/posts/' + postId);
    const data = await res.json();
    if (res.ok) post.value = data;
  } catch (e) {
    console.error('获取帖子失败:', e);
  }
};

const fetchComments = async () => {
  try {
    const auth = (window as any).__VTJ_AUTH__;
    const res = await auth.apiFetch('/api/forum/posts/' + postId + '/comments');
    const data = await res.json();
    if (res.ok) comments.value = data.items || data.comments || [];
  } catch (e) {
    console.error('获取评论失败:', e);
  }
};

const toggleLike = async () => {
  try {
    const auth = (window as any).__VTJ_AUTH__;
    const res = await auth.apiFetch('/api/forum/posts/' + postId + '/like', { method: 'POST' });
    if (res.ok) {
      const data = await res.json().catch(() => ({}));
      if (post.value) {
        post.value.liked = !post.value.liked;
        post.value.likeCount = data.likeCount !== undefined ? data.likeCount : (post.value.likeCount || 0) + (post.value.liked ? 1 : -1);
      }
    }
  } catch (e) {
    console.error('点赞失败:', e);
  }
};

const submitComment = async () => {
  const c = commentText.value.trim();
  if (!c) return;
  try {
    const auth = (window as any).__VTJ_AUTH__;
    const body = new URLSearchParams();
    body.append('content', c);
    const res = await auth.apiFetch('/api/forum/posts/' + postId + '/comments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString()
    });
    if (res.ok) {
      commentText.value = '';
      await fetchComments();
      if (post.value) post.value.commentCount = (post.value.commentCount || 0) + 1;
    }
  } catch (e) {
    console.error('评论失败:', e);
  }
};

onMounted(() => {
  fetchDetail();
  fetchComments();
});
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #F5F7FA;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 48px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #e8ecf1;
}
.back-btn {
  background: none;
  border: none;
  font-size: 22px;
  color: #1a2b5f;
  cursor: pointer;
  padding: 4px 8px;
}
.title {
  font-size: 16px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0;
}
.spacer {
  width: 32px;
}
.body {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
}
.post-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}
.post-title {
  font-size: 18px;
  font-weight: 700;
  color: #1a2b5f;
  line-height: 1.4;
  margin: 0 0 8px;
}
.post-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f2f5;
}
.author {
  font-size: 13px;
  color: #1a2b5f;
  font-weight: 600;
}
.time {
  font-size: 12px;
  color: #8899aa;
}
.badge {
  font-size: 11px;
  color: #c41e3a;
  background: #fff2f0;
  padding: 2px 8px;
  border-radius: 4px;
}
.post-content {
  font-size: 15px;
  color: #1a2a3a;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: 12px;
}
.post-actions {
  display: flex;
  gap: 16px;
  align-items: center;
}
.action-btn {
  background: #f5f7fa;
  border: none;
  border-radius: 8px;
  padding: 6px 14px;
  font-size: 14px;
  color: #5a6488;
  cursor: pointer;
}
.action-btn.liked {
  color: #c41e3a;
}
.action-count {
  font-size: 14px;
  color: #5a6488;
}
.comments {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}
.comments-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0 0 12px;
}
.comment-item {
  padding: 10px 0;
  border-bottom: 1px solid #f0f2f5;
}
.comment-item:last-child {
  border-bottom: none;
}
.comment-user {
  font-size: 13px;
  font-weight: 600;
  color: #1a2b5f;
  margin-bottom: 4px;
}
.comment-content {
  font-size: 14px;
  color: #1a2a3a;
  line-height: 1.6;
}
.comment-time {
  font-size: 11px;
  color: #8899aa;
  margin-top: 4px;
}
.empty {
  text-align: center;
  color: #8899aa;
  padding: 20px 0;
  font-size: 13px;
}
.comment-bar {
  display: flex;
  gap: 8px;
  padding: 10px 12px;
  background: #fff;
  border-top: 1px solid #e8ecf1;
}
.comment-input {
  flex: 1;
  border: 1px solid #e8ecf1;
  border-radius: 20px;
  padding: 10px 14px;
  font-size: 14px;
  outline: none;
  font-family: inherit;
}
.send-btn {
  min-height: 40px;
  padding: 0 18px;
  border: none;
  border-radius: 20px;
  background: linear-gradient(135deg, #C91F37, #e8384f);
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}
.send-btn:disabled {
  opacity: 0.5;
}
</style>
