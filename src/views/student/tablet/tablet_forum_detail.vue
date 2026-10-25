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

          <section class="comments">
            <div class="comments-head">
              <h3 class="comments-title">评论 ({{ comments.length }})</h3>
              <CommentSortBar
                :sort-by="sortBy"
                :order="order"
                @update:sortBy="changeSort"
                @update:order="toggleOrder" />
            </div>

            <div v-if="!rootComments.length" class="comments-empty">暂无评论，抢个沙发</div>

            <div class="comment-list">
              <div v-for="c in rootComments" :key="c.id" class="comment-item">
                <UserBadge
                  avatar-only
                  size="sm"
                  clickable
                  :src="c.user?.avatar"
                  :name="c.user?.nickname"
                  :user-id="c.user?.id"
                  :user-type="c.user?.userType" />
                <div class="comment-body">
                  <div class="comment-meta">
                    <span class="comment-author">{{ c.user?.nickname || '匿名' }}</span>
                    <span class="comment-time">{{ formatTime(c.createTime) }}</span>
                  </div>
                  <div class="comment-text"><ForumContent :content="c.content" /></div>
                  <AttachmentList
                    v-if="c.attachments && c.attachments.length"
                    :attachments="c.attachments"
                    mode="comment" />
                  <div class="comment-actions">
                    <button class="comment-like" type="button" @click="reactToComment(c, 'like')">
                      👍 {{ c.likeCount }}
                    </button>
                    <button class="comment-reply" type="button" @click="startReply(c)">回复</button>
                    <button class="comment-pin" type="button" @click="togglePin(c)">
                      {{ c.isPinned ? '取消置顶' : '置顶' }}
                    </button>
                    <button class="comment-report" type="button" @click="reportComment(c)">举报</button>
                  </div>

                  <div v-if="repliesOf(c.id).length" class="comment-replies">
                    <div v-for="r in repliesOf(c.id)" :key="r.id" class="comment-item">
                      <UserBadge
                        avatar-only
                        size="sm"
                        :src="r.user?.avatar"
                        :name="r.user?.nickname"
                        :user-id="r.user?.id" />
                      <div class="comment-body">
                        <div class="comment-meta">
                          <span class="comment-author">{{ r.user?.nickname || '匿名' }}</span>
                          <span class="comment-time">{{ formatTime(r.createTime) }}</span>
                        </div>
                        <div class="comment-text"><ForumContent :content="r.content" /></div>
                        <AttachmentList
                          v-if="r.attachments && r.attachments.length"
                          :attachments="r.attachments"
                          mode="comment" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </article>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import AttachmentList from '@/components/forum/AttachmentList.vue';
import CommentSortBar from '@/components/forum/CommentSortBar.vue';
import ForumContent from '@/components/forum/ForumContent.vue';
import UserBadge from '@/components/forum/UserBadge.vue';
import { titleColorValue } from '@/components/forum/titleColors';
import {
  pinForumComment,
  reportForumTarget,
  type ForumCommentItem,
  type ForumCommentSortBy,
  type ForumReactionCode,
  type ForumSortOrder
} from '@/modules/community/api';
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

const sortBy = ref<ForumCommentSortBy>('time');
const order = ref<ForumSortOrder>('asc');
const replyTo = ref<number | null>(null);
const replyToName = ref('');

const comments = computed(() => store.comments);
const rootComments = computed(() => comments.value.filter((c) => !c.parentCommentId));

const repliesOf = (commentId: number) =>
  comments.value
    .filter((c) => c.parentCommentId === commentId)
    .sort((a, b) => {
      const at = a.createTime ? new Date(a.createTime).getTime() : 0;
      const bt = b.createTime ? new Date(b.createTime).getTime() : 0;
      return at - bt;
    });

const loadComments = async () => {
  await store.loadComments(postId, { sortBy: sortBy.value, order: order.value });
};

const changeSort = async (key: ForumCommentSortBy) => {
  if (sortBy.value === key) return;
  sortBy.value = key;
  await loadComments();
};

const toggleOrder = async () => {
  order.value = order.value === 'asc' ? 'desc' : 'asc';
  await loadComments();
};

const reactToComment = async (comment: ForumCommentItem, reaction: ForumReactionCode) => {
  try {
    await store.reactToComment(comment.id, reaction);
  } catch (e) {
    console.error('评论点赞失败:', e);
  }
};

const startReply = (comment: ForumCommentItem) => {
  replyTo.value = comment.id;
  replyToName.value = comment.user?.nickname ?? '该用户';
};

const cancelReply = () => {
  replyTo.value = null;
  replyToName.value = '';
};

const togglePin = async (comment: ForumCommentItem) => {
  await pinForumComment(comment.id, !comment.isPinned);
  await loadComments();
};

const reportComment = async (comment: ForumCommentItem) => {
  const reason = window.prompt('举报原因（spam/abuse/illegal/other）', 'abuse');
  if (!reason) return;
  const allowed = ['spam', 'abuse', 'illegal', 'other'];
  const reasonCode = (allowed.includes(reason) ? reason : 'other') as
    | 'spam'
    | 'abuse'
    | 'illegal'
    | 'other';
  await reportForumTarget({ targetType: 'COMMENT', targetId: comment.id, reasonCode });
  window.alert('举报已提交');
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
  if (!detail) {
    loadError.value = '帖子不存在或已被删除';
    loading.value = false;
    return;
  }

  await loadComments();
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

.comments {
  margin-top: 12px;
  border-top: 1px solid #eef2f7;
  padding-top: 16px;
}

.comments-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.comments-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0;
}

.comments-empty {
  text-align: center;
  color: #8899aa;
  font-size: 13px;
  padding: 24px 0;
}

.comment-item {
  display: flex;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid #f2f5f9;
}

.comment-item:last-child {
  border-bottom: none;
}

.comment-body {
  flex: 1;
  min-width: 0;
}

.comment-meta {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 4px;
}

.comment-author {
  font-size: 13px;
  font-weight: 600;
  color: #1a2b5f;
}

.comment-time {
  font-size: 12px;
  color: #9aa8bb;
}

.comment-text {
  font-size: 14px;
  line-height: 1.7;
  color: #2b3a55;
  word-break: break-word;
}

.comment-actions {
  display: flex;
  gap: 14px;
  margin-top: 6px;
}

.comment-actions button {
  border: none;
  background: none;
  padding: 2px 0;
  font-size: 12px;
  color: #8899aa;
  cursor: pointer;
}

.comment-actions button:hover {
  color: #1a2b5f;
}

.comment-replies {
  margin-top: 10px;
  margin-left: 32px;
  padding-left: 14px;
  border-left: 2px solid #eef2f7;
}

.comment-replies .comment-item {
  padding: 10px 0;
}
</style>
