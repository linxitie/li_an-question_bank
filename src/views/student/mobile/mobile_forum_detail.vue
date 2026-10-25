<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">帖子详情</h1>
      <button v-if="canDelete" class="delete-btn" @click="removePost">删除</button>
      <span v-else class="spacer"></span>
    </header>

    <main class="body">
      <div v-if="store.detailLoading" class="page-state">加载中...</div>
      <div v-else-if="loadError" class="page-state error">
        <p>{{ loadError }}</p>
        <button class="state-btn" @click="goBack">返回论坛</button>
      </div>

      <div v-if="post" class="post-card">
        <h2 class="post-title">{{ post.title }}</h2>
        <div class="post-author">
          <div class="avatar" :class="{ 'has-frame': post.user && post.user.avatarFrame }">
            <img
              v-if="post.user && post.user.avatar && !avatarFailed['post-' + post.id]"
              :src="post.user.avatar"
              alt=""
              @error="markAvatarFailed('post-' + post.id)"
            />
            <span v-else>{{ avatarInitial(post.user && post.user.nickname) }}</span>
          </div>
          <div class="author-meta">
            <span class="author">{{ post.user && post.user.nickname }}</span>
            <span v-if="post.user && post.user.signature" class="signature">{{ post.user.signature }}</span>
          </div>
          <span class="time">{{ formatTime(post.createTime) }}</span>
          <span v-if="post.isTop" class="badge">置顶</span>
          <span v-if="post.isEssence" class="badge">精华</span>
        </div>
        <div class="post-content"><ForumContent :content="post.content" /></div>
        <ImageGrid v-if="postImages.length" :images="postImages" mode="post" />
        <div class="reaction-bar">
          <button
            v-for="r in REACTIONS"
            :key="r.code"
            class="reaction-btn"
            :class="{ active: post.myReaction === r.code }"
            :title="r.label"
            @click="reactToPost(r.code)"
          >
            <span class="reaction-emoji">{{ r.emoji }}</span>
            <span v-if="reactionCount(post, r.code)" class="reaction-count">{{ reactionCount(post, r.code) }}</span>
          </button>
          <span class="action-count">💬 {{ post.commentCount || 0 }}</span>
        </div>
      </div>

      <div v-if="post" class="comments">
        <div class="comments-head">
          <h3 class="comments-title">评论 ({{ comments.length }})</h3>
          <div class="sort-bar">
            <button
              v-for="opt in SORT_OPTIONS"
              :key="opt.key"
              class="sort-btn"
              :class="{ active: sortBy === opt.key }"
              @click="changeSort(opt.key)"
            >
              {{ opt.name }}
            </button>
            <button class="sort-btn order-btn" @click="toggleOrder">
              {{ order === 'asc' ? '正序' : '倒序' }}
            </button>
          </div>
        </div>
        <div v-for="c in rootComments" :key="c.id" class="comment-item">
          <div class="comment-row">
            <UserBadge
              class="avatar small"
              avatar-only
              size="sm"
              :src="c.user && c.user.avatar"
              :name="c.user && c.user.nickname"
              :user-id="c.user && c.user.id"
              :user-type="c.user && c.user.userType" />
            <div class="comment-main">
              <div class="comment-user">
                {{ c.user && c.user.nickname }}
                <span v-if="c.user && c.user.signature" class="signature">{{ c.user.signature }}</span>
              </div>
              <div class="comment-content"><ForumContent :content="c.content" /></div>
              <ImageGrid
                v-if="c.attachments && c.attachments.length"
                :images="c.attachments.map((a) => a.url)"
                mode="comment"
              />
              <div class="comment-actions">
                <button class="text-btn" @click="startReply(c)">回复</button>
                <button v-if="isPostAuthor" class="text-btn" @click="togglePin(c)">
                  {{ c.isPinned ? '取消置顶' : '置顶' }}
                </button>
                <button
                  v-if="c.user && c.user.id !== authStore.userId"
                  class="text-btn"
                  @click="reportComment(c)"
                >
                  举报
                </button>
                <button
                  v-for="r in REACTIONS"
                  :key="r.code"
                  class="mini-reaction"
                  :class="{ active: c.myReaction === r.code }"
                  @click="reactToComment(c.id, r.code)"
                >
                  {{ r.emoji }}<span v-if="reactionCount(c, r.code)">{{ reactionCount(c, r.code) }}</span>
                </button>
              </div>
              <div class="comment-time">{{ formatTime(c.createTime) }}</div>
            </div>
          </div>

          <div v-if="repliesOf(c.id).length" class="replies">
            <div v-for="r in repliesOf(c.id)" :key="r.id" class="reply-item">
              <UserBadge
                class="avatar tiny"
                avatar-only
                size="sm"
                :src="r.user && r.user.avatar"
                :name="r.user && r.user.nickname"
                :user-id="r.user && r.user.id"
                :user-type="r.user && r.user.userType" />
              <div class="comment-main">
                <div class="comment-user">{{ r.user && r.user.nickname }}</div>
                <div class="comment-content"><ForumContent :content="r.content" /></div>
                <ImageGrid
                  v-if="r.attachments && r.attachments.length"
                  :images="r.attachments.map((a) => a.url)"
                  mode="comment"
                />
                <div class="comment-actions">
                  <button class="text-btn" @click="startReply(c, r)">回复</button>
                  <button
                    v-if="r.user && r.user.id !== authStore.userId"
                    class="text-btn"
                    @click="reportComment(r)"
                  >
                    举报
                  </button>
                  <button
                    v-for="reaction in REACTIONS"
                    :key="reaction.code"
                    class="mini-reaction"
                    :class="{ active: r.myReaction === reaction.code }"
                    @click="reactToComment(r.id, reaction.code)"
                  >
                    {{ reaction.emoji }}<span v-if="reactionCount(r, reaction.code)">{{ reactionCount(r, reaction.code) }}</span>
                  </button>
                </div>
                <div class="comment-time">{{ formatTime(r.createTime) }}</div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="!comments.length" class="empty">暂无评论，快来抢沙发</div>
      </div>
    </main>

    <footer v-if="post" class="comment-bar">
      <button v-if="replyTo" class="reply-hint" @click="cancelReply">回复 {{ replyToName }} ×</button>
      <div class="comment-image-bar">
        <ImageUploader v-model="commentImages" />
      </div>
      <div v-if="showPicker" class="comment-picker">
        <EmojiStickerPicker @select="insertEmoji" @close="showPicker = false" />
      </div>
      <button class="emoji-btn" title="表情 / 表情包" @click="showPicker = !showPicker">😊</button>
      <input
        v-model="commentText"
        type="text"
        class="comment-input"
        :placeholder="replyTo ? `回复 ${replyToName}...` : '写下你的评论...'"
        @keyup.enter="submitComment"
      />
      <button class="send-btn" @click="submitComment" :disabled="!commentText.trim()">发送</button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useCommunityStore } from '@/modules/community/store';
import { useAuthStore } from '@/stores/auth';
import EmojiStickerPicker from '@/components/forum/EmojiStickerPicker.vue';
import ForumContent from '@/components/forum/ForumContent.vue';
import ImageGrid from '@/components/forum/ImageGrid.vue';
import ImageUploader from '@/components/forum/ImageUploader.vue';
import UserBadge from '@/components/forum/UserBadge.vue';
import { isImageUrl, type ForumImageAttachment } from '@/components/forum/imageUtils';
import { avatarInitial } from '@/modules/community/avatar';
import {
  pinForumComment,
  reportForumTarget,
  type ForumCommentItem,
  type ForumCommentSortBy,
  type ForumPostItem,
  type ForumReactionCode,
  type ForumSortOrder
} from '@/modules/community/api';

const REACTIONS: ReadonlyArray<{ code: ForumReactionCode; emoji: string; label: string }> = [
  { code: 'like', emoji: '👍', label: '赞' },
  { code: 'love', emoji: '❤️', label: '喜欢' },
  { code: 'haha', emoji: '😂', label: '哈哈' },
  { code: 'wow', emoji: '😮', label: '惊讶' },
  { code: 'sad', emoji: '😢', label: '难过' },
  { code: 'angry', emoji: '😡', label: '生气' }
];

const SORT_OPTIONS: ReadonlyArray<{ key: ForumCommentSortBy; name: string }> = [
  { key: 'time', name: '时间' },
  { key: 'likes', name: '点赞' },
  { key: 'replies', name: '回复' }
];

const route = useRoute();
const router = useRouter();
const store = useCommunityStore();
const authStore = useAuthStore();
const commentText = ref('');
const commentImages = ref<ForumImageAttachment[]>([]);
const replyTo = ref<number | null>(null);
const replyToName = ref('');
const showPicker = ref(false);
const sortBy = ref<ForumCommentSortBy>('time');
const order = ref<ForumSortOrder>('asc');
const loadError = ref('');
const avatarFailed = ref<Record<string, boolean>>({});
const markAvatarFailed = (key: string) => {
  avatarFailed.value[key] = true;
};

const insertEmoji = (payload: { type: 'emoji' | 'sticker'; value: string; name?: string }) => {
  commentText.value +=
    payload.type === 'emoji' ? payload.value : `[[sticker:${payload.value}]]`;
};

const postId = Number(route.params.id);
const post = computed(() => store.detail);
const postImages = computed(() =>
  (post.value?.attachments || [])
    .map((att) => att.url)
    .filter((url) => isImageUrl(url))
);
const canDelete = computed(() => {
  if (!post.value) return false;
  return (
    post.value.userId === authStore.userId ||
    authStore.roleLevel >= 2
  );
});
const comments = computed(() => store.comments);
const rootComments = computed(() => comments.value.filter((c) => !c.parentCommentId));
const isPostAuthor = computed(
  () => !!post.value && post.value.userId === authStore.userId
);

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
  await reportForumTarget({
    targetType: 'COMMENT',
    targetId: comment.id,
    reasonCode
  });
  window.alert('举报已提交');
};

const repliesOf = (commentId: number) =>
  comments.value
    .filter((c) => c.parentCommentId === commentId)
    .sort((a, b) => {
      const at = a.createTime ? new Date(a.createTime).getTime() : 0;
      const bt = b.createTime ? new Date(b.createTime).getTime() : 0;
      return at - bt;
    });

const reactionCount = (
  target: Pick<ForumPostItem, 'reactions'> | Pick<ForumCommentItem, 'reactions'>,
  code: ForumReactionCode
) => target.reactions?.[code] ?? 0;

const startReply = (parent: ForumCommentItem, target?: ForumCommentItem) => {
  replyTo.value = parent.id;
  replyToName.value = (target ?? parent).user?.nickname ?? '该用户';
};

const cancelReply = () => {
  replyTo.value = null;
  replyToName.value = '';
};

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/forum');
};

const formatTime = (iso: string | null) => {
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

const loadComments = async () => {
  await store.loadComments(postId, { sortBy: sortBy.value, order: order.value });
};

const load = async () => {
  loadError.value = '';
  if (!Number.isFinite(postId) || postId <= 0) {
    loadError.value = '帖子不存在或已被删除';
    return;
  }
  const detail = await store.loadPost(postId);
  if (!detail) {
    loadError.value =
      store.error && !store.error.includes('请求失败')
        ? store.error
        : '帖子不存在或已被删除';
    return;
  }
  await loadComments();
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

const reactToPost = async (reaction: ForumReactionCode) => {
  try {
    await store.reactToPost(postId, reaction);
  } catch (e) {
    console.error('表情反应失败:', e);
  }
};

const reactToComment = async (commentId: number, reaction: ForumReactionCode) => {
  try {
    await store.reactToComment(commentId, reaction);
  } catch (e) {
    console.error('评论表情反应失败:', e);
  }
};

const submitComment = async () => {
  const c = commentText.value.trim();
  if (!c) return;
  try {
    await store.submitComment(postId, {
      content: c,
      parentCommentId: replyTo.value,
      attachments: commentImages.value.length ? commentImages.value : undefined
    });
    commentText.value = '';
    commentImages.value = [];
    cancelReply();
  } catch (e) {
    console.error('评论失败:', e);
  }
};

const removePost = async () => {
  if (!post.value) return;
  if (!window.confirm('确定删除这篇帖子？删除后不可恢复。')) return;
  try {
    await store.deletePost(post.value.id);
    router.replace('/mobile/forum');
  } catch (e) {
    console.error('删除失败:', e);
  }
};

onMounted(() => {
  authStore.refresh();
  load();
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
.delete-btn {
  background: none;
  border: none;
  color: #c91f37;
  font-size: 14px;
  cursor: pointer;
  padding: 4px 8px;
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
.post-author {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f2f5;
  flex-wrap: wrap;
}
.post-author .time {
  margin-left: auto;
}
.author-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.signature {
  font-size: 11px;
  color: #8899aa;
  font-weight: 400;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #eef2f8;
  color: #1a365d;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  flex: none;
}
.avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar.has-frame {
  box-shadow: 0 0 0 2px #c91f37;
}
.avatar.small {
  width: 30px;
  height: 30px;
  font-size: 12px;
}
.avatar.tiny {
  width: 24px;
  height: 24px;
  font-size: 11px;
}
.reaction-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.reaction-btn {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  border: 1px solid #e8ecf1;
  background: #fff;
  border-radius: 16px;
  padding: 4px 10px;
  font-size: 14px;
  color: #5a6488;
  cursor: pointer;
  transition: transform 0.15s, background 0.15s, border-color 0.15s;
}
.reaction-btn.active {
  border-color: #c91f37;
  background: #fff2f0;
  color: #c91f37;
  transform: scale(1.04);
}
.reaction-count {
  font-size: 12px;
}
.comment-row {
  display: flex;
  gap: 8px;
}
.comment-main {
  flex: 1;
  min-width: 0;
}
.comment-actions {
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 4px;
}
.text-btn {
  background: none;
  border: none;
  color: #5a6488;
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}
.mini-reaction {
  background: none;
  border: none;
  font-size: 12px;
  color: #5a6488;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 8px;
}
.mini-reaction.active {
  background: #fff2f0;
  color: #c91f37;
}
.replies {
  margin: 8px 0 0 38px;
  padding-left: 10px;
  border-left: 2px solid #f0f2f5;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.reply-item {
  display: flex;
  gap: 8px;
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
.comments-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 12px;
}
.comments-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
  margin: 0;
}
.sort-bar {
  display: flex;
  gap: 4px;
}
.sort-btn {
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #5a6488;
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 12px;
  cursor: pointer;
}
.sort-btn.active {
  border-color: #c41e3a;
  background: #fff2f0;
  color: #c41e3a;
}
.order-btn {
  min-width: 44px;
}
.page-state {
  background: #fff;
  border-radius: 12px;
  padding: 32px 16px;
  text-align: center;
  color: #5a6488;
  font-size: 14px;
}
.page-state.error {
  color: #c41e3a;
}
.state-btn {
  margin-top: 12px;
  min-height: 36px;
  padding: 0 18px;
  border: none;
  border-radius: 8px;
  background: #1a2b5f;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
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
  position: relative;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 12px;
  background: #fff;
  border-top: 1px solid #e8ecf1;
}
.comment-image-bar {
  width: 100%;
}
.reply-hint {
  position: absolute;
  left: 12px;
  top: -30px;
  background: #eef2f8;
  border: none;
  border-radius: 14px;
  padding: 4px 10px;
  font-size: 12px;
  color: #1a365d;
  cursor: pointer;
}
.emoji-btn {
  flex: none;
  width: 40px;
  height: 40px;
  border: 1px solid #e8ecf1;
  border-radius: 50%;
  background: #fff;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}
.comment-picker {
  position: absolute;
  left: 12px;
  bottom: calc(100% + 8px);
  z-index: 20;
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
