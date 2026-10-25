<template>
  <div class="af-page">
    <header class="af-head">
      <h1>论坛管理</h1>
      <p>全站内容管理 · 教师隐藏复核 · 回收站</p>
    </header>

    <nav class="af-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['af-tab', { active: activeTab === tab.key }]"
        @click="switchTab(tab.key)"
      >
        {{ tab.name }}
      </button>
    </nav>

    <section v-if="activeTab === 'content'">
      <div class="af-filters">
        <input v-model="keyword" placeholder="搜索标题/内容" @keyup.enter="loadPosts" />
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option value="NORMAL">正常</option>
          <option value="BLOCKED">待复核隐藏</option>
          <option value="DELETED">已删除</option>
        </select>
        <button class="af-btn" @click="loadPosts">查询</button>
      </div>

      <p v-if="loading" class="af-empty">加载中…</p>
      <p v-else-if="!posts.length" class="af-empty">暂无帖子</p>
      <div v-else class="af-list">
        <article v-for="post in posts" :key="post.id" class="af-card">
          <div class="af-row">
            <span class="af-status" :class="`st-${post.status}`">{{ statusLabel(post.status) }}</span>
            <b>{{ post.title }}</b>
            <span class="af-meta">{{ post.author }} · {{ post.authorClass || '未分班' }}</span>
            <span v-if="post.moderationStatus" class="af-meta">复核：{{ post.moderationStatus }}</span>
          </div>
          <p class="af-content">{{ post.content }}</p>
          <div class="af-actions">
            <button class="af-link" @click="openPost(post)">查看评论</button>
            <button class="af-danger" @click="askDeletePost(post)">删除帖子</button>
          </div>
        </article>
      </div>
    </section>

    <section v-else-if="activeTab === 'moderation'">
      <p v-if="!records.length" class="af-empty">暂无待复核记录</p>
      <div v-else class="af-list">
        <article v-for="record in records" :key="record.id" class="af-card">
          <div class="af-row">
            <span class="af-status st-BLOCKED">{{ record.target_type === 'POST' ? '帖子' : '评论' }}</span>
            <b>{{ record.target && 'title' in record.target ? record.target.title : (record.target && record.target.content) || '内容已删除' }}</b>
            <span class="af-meta">原因：{{ record.reason }}</span>
          </div>
          <div class="af-actions">
            <button class="af-btn" @click="approve(record)">确认删除</button>
            <button class="af-link" @click="reject(record)">驳回并恢复</button>
          </div>
        </article>
      </div>
    </section>

    <section v-else>
      <div class="af-list">
        <article v-for="post in recycle.posts" :key="`p-${post.id}`" class="af-card">
          <div class="af-row">
            <span class="af-status st-DELETED">帖子</span>
            <b>{{ post.title }}</b>
            <span class="af-meta">{{ post.deletedReason || '无原因' }}</span>
          </div>
          <div class="af-actions">
            <button class="af-btn" @click="restorePost(post)">恢复</button>
            <button class="af-danger" @click="purgePost(post)">彻底删除</button>
          </div>
        </article>
        <article v-for="comment in recycle.comments" :key="`c-${comment.id}`" class="af-card">
          <div class="af-row">
            <span class="af-status st-DELETED">评论</span>
            <b>{{ comment.content }}</b>
            <span class="af-meta">{{ comment.deletedReason || '无原因' }}</span>
          </div>
          <div class="af-actions">
            <button class="af-btn" @click="restoreComment(comment)">恢复</button>
            <button class="af-danger" @click="purgeComment(comment)">彻底删除</button>
          </div>
        </article>
        <p v-if="!recycle.posts.length && !recycle.comments.length" class="af-empty">回收站为空</p>
      </div>
    </section>

    <div v-if="detail" class="af-modal" @click.self="detail = null">
      <div class="af-modal-card">
        <button class="af-close" @click="detail = null">×</button>
        <h2>{{ detail.title }}</h2>
        <p class="af-content">{{ detail.content }}</p>
        <h3>评论（{{ comments.length }}）</h3>
        <p v-if="!comments.length" class="af-empty">暂无评论</p>
        <div v-for="c in comments" :key="c.id" class="af-comment">
          <span class="af-meta">{{ c.user?.nickname }} · {{ c.user?.className || '未分班' }} · 状态 {{ c.status }}</span>
          <p>{{ c.content }}</p>
          <button class="af-danger" @click="deleteComment(c)">删除评论</button>
        </div>
      </div>
    </div>

    <ModerationReasonDialog
      :visible="dialog.visible"
      :title="dialog.title"
      hint="管理员删除会进入回收站，可恢复。"
      :submitting="dialog.submitting"
      @close="dialog.visible = false"
      @confirm="submitDelete"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';

import ModerationReasonDialog from '@/components/forum/ModerationReasonDialog.vue';
import {
  adminForumApi,
  type ModerationComment,
  type ModerationPost,
  type ModerationRecord
} from '@/modules/community/moderationApi';

const tabs = [
  { key: 'content', name: '内容管理' },
  { key: 'moderation', name: '待复核' },
  { key: 'recycle', name: '回收站' }
];

const activeTab = ref('content');
const posts = ref<ModerationPost[]>([]);
const comments = ref<ModerationComment[]>([]);
const records = ref<ModerationRecord[]>([]);
const recycle = reactive<{ posts: ModerationPost[]; comments: ModerationComment[] }>({
  posts: [],
  comments: []
});
const detail = ref<ModerationPost | null>(null);
const loading = ref(false);
const keyword = ref('');
const statusFilter = ref('');

const dialog = reactive({
  visible: false,
  title: '',
  submitting: false,
  target: '' as 'post' | 'comment',
  targetId: 0
});

const statusLabel = (status: string) =>
  ({ NORMAL: '正常', BLOCKED: '待复核隐藏', DELETED: '已删除' } as Record<string, string>)[status] ||
  status;

const loadPosts = async () => {
  loading.value = true;
  try {
    const data = await adminForumApi.posts({
      keyword: keyword.value || undefined,
      status: statusFilter.value || undefined,
      limit: 50
    });
    posts.value = data.items;
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载失败');
  } finally {
    loading.value = false;
  }
};

const loadModeration = async () => {
  const data = await adminForumApi.moderation('PENDING');
  records.value = data.items;
};

const loadRecycle = async () => {
  const data = await adminForumApi.recycle();
  recycle.posts = data.posts;
  recycle.comments = data.comments;
};

const switchTab = async (key: string) => {
  activeTab.value = key;
  if (key === 'content') await loadPosts();
  if (key === 'moderation') await loadModeration();
  if (key === 'recycle') await loadRecycle();
};

const openPost = async (post: ModerationPost) => {
  detail.value = post;
  try {
    const data = await adminForumApi.comments(post.id);
    comments.value = data.items;
  } catch (e) {
    comments.value = [];
  }
};

const askDeletePost = (post: ModerationPost) => {
  Object.assign(dialog, {
    visible: true,
    title: `删除帖子：${post.title}`,
    target: 'post',
    targetId: post.id,
    submitting: false
  });
};

const deleteComment = (comment: ModerationComment) => {
  Object.assign(dialog, {
    visible: true,
    title: '删除评论',
    target: 'comment',
    targetId: comment.id,
    submitting: false
  });
};

const submitDelete = async (reason: string) => {
  dialog.submitting = true;
  try {
    if (dialog.target === 'post') {
      await adminForumApi.deletePost(dialog.targetId, reason);
    } else {
      await adminForumApi.deleteComment(dialog.targetId, reason);
    }
    ElMessage.success('已删除并进入回收站');
    dialog.visible = false;
    detail.value = null;
    await loadPosts();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败');
  } finally {
    dialog.submitting = false;
  }
};

const approve = async (record: ModerationRecord) => {
  await adminForumApi.approve(record.id, '管理员确认');
  ElMessage.success('已确认删除');
  await loadModeration();
};

const reject = async (record: ModerationRecord) => {
  await adminForumApi.reject(record.id, '管理员驳回');
  ElMessage.success('已恢复');
  await loadModeration();
};

const restorePost = async (post: ModerationPost) => {
  await adminForumApi.restorePost(post.id);
  ElMessage.success('已恢复');
  await loadRecycle();
};

const restoreComment = async (comment: ModerationComment) => {
  await adminForumApi.restoreComment(comment.id);
  ElMessage.success('已恢复');
  await loadRecycle();
};

const purgePost = async (post: ModerationPost) => {
  if (!window.confirm('彻底删除不可恢复，确定？')) return;
  await adminForumApi.purgePost(post.id);
  ElMessage.success('已彻底删除');
  await loadRecycle();
};

const purgeComment = async (comment: ModerationComment) => {
  if (!window.confirm('彻底删除不可恢复，确定？')) return;
  await adminForumApi.purgeComment(comment.id);
  ElMessage.success('已彻底删除');
  await loadRecycle();
};

onMounted(loadPosts);
</script>

<style scoped>
.af-page { padding: 24px; background: #f5f7fb; min-height: 100vh; }
.af-head h1 { margin: 0 0 4px; color: #1a2b5f; }
.af-head p { margin: 0 0 16px; color: #6b7896; font-size: 13px; }
.af-tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.af-tab { border: 1px solid #d9e1ee; background: #fff; border-radius: 999px; padding: 7px 16px; cursor: pointer; color: #3b4a6b; }
.af-tab.active { background: #1a365d; border-color: #1a365d; color: #fff; }
.af-filters { display: flex; gap: 8px; margin-bottom: 14px; }
.af-filters input, .af-filters select { padding: 8px 10px; border: 1px solid #d9e1ee; border-radius: 8px; font-size: 13px; }
.af-btn { border: none; border-radius: 8px; background: #1a365d; color: #fff; padding: 8px 14px; cursor: pointer; }
.af-list { display: flex; flex-direction: column; gap: 10px; }
.af-card { background: #fff; border-radius: 12px; padding: 14px; box-shadow: 0 2px 10px rgba(26,43,95,.05); }
.af-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; color: #1a2b5f; }
.af-meta { color: #8a94ad; font-size: 12px; }
.af-status { font-size: 11px; padding: 2px 7px; border-radius: 10px; background: #eef3fb; color: #3b5b8c; }
.af-status.st-BLOCKED { background: #fff4e5; color: #b45309; }
.af-status.st-DELETED { background: #fee2e2; color: #b91c1c; }
.af-content { color: #3b4a6b; font-size: 14px; line-height: 1.6; white-space: pre-wrap; }
.af-actions { display: flex; gap: 10px; margin-top: 8px; }
.af-link, .af-danger { border: none; background: none; cursor: pointer; font-size: 13px; padding: 0; }
.af-link { color: #1a365d; }
.af-danger { color: #c41e3a; }
.af-empty { text-align: center; color: #8a94ad; padding: 30px; }
.af-modal { position: fixed; inset: 0; z-index: 9000; background: rgba(8,12,24,.45); display: flex; align-items: center; justify-content: center; padding: 20px; }
.af-modal-card { position: relative; width: min(720px, 94vw); max-height: 86vh; overflow-y: auto; background: #fff; border-radius: 14px; padding: 22px; }
.af-close { position: absolute; top: 8px; right: 12px; border: none; background: none; font-size: 22px; color: #8a94ad; cursor: pointer; }
.af-comment { border-top: 1px solid #eef1f7; padding-top: 8px; margin-top: 8px; }
</style>
