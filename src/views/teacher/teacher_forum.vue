<template>
  <div class="tf-page">
    <TeacherNavHeader active-nav="forum" />
    <main class="tf-main">
      <header class="tf-head">
        <h1>论坛管理</h1>
        <p class="tf-sub">全校帖子可见；只能隐藏本班学生的内容，需填写原因并提交管理员复核。</p>
      </header>

      <section class="tf-filters">
        <input v-model="keyword" placeholder="搜索标题/内容" @keyup.enter="loadPosts" />
        <select v-model="className">
          <option value="">全部班级</option>
          <option v-for="name in classOptions" :key="name" :value="name">{{ name }}</option>
        </select>
        <button class="tf-btn" @click="loadPosts">查询</button>
      </section>

      <p v-if="!canModerate" class="tf-warn">
        当前账号未绑定班级，暂不能隐藏本班学生内容。请先在「班级管理」中创建/绑定班级，并让学生填写班级。
      </p>
      <p v-if="loading" class="tf-empty">加载中…</p>
      <p v-else-if="!posts.length" class="tf-empty">暂无帖子</p>
      <div v-else class="tf-list">
        <article v-for="post in posts" :key="post.id" class="tf-card">
          <div class="tf-card-head">
            <UserBadge
              size="sm"
              :src="post.authorAvatar"
              :name="post.author"
              :user-id="post.id"
              :user-type="post.authorType || 'student'" />
            <span class="tf-status" :class="`st-${post.status}`">{{ statusLabel(post.status) }}</span>
            <span class="tf-title">{{ post.title }}</span>
            <span class="tf-meta">{{ post.authorClass || '未分班' }}</span>
          </div>
          <p class="tf-content"><ForumContent :content="post.content" /></p>
          <AttachmentList
            v-if="post.attachments && post.attachments.length"
            :attachments="post.attachments"
            mode="post" />
          <div class="tf-actions">
            <button class="tf-link" @click="openPost(post)">查看评论</button>
            <button v-if="post.canDelete" class="tf-danger" @click="askHidePost(post)">隐藏帖子</button>
          </div>
        </article>
      </div>

      <div v-if="detail" class="tf-modal" @click.self="detail = null">
        <div class="tf-modal-card">
          <button class="tf-close" @click="detail = null">×</button>
          <h2>{{ detail.title }}</h2>
          <p class="tf-meta">{{ detail.author }} · {{ detail.authorClass || '未分班' }}</p>
          <p class="tf-content"><ForumContent :content="detail.content" /></p>
          <AttachmentList
            v-if="detail.attachments && detail.attachments.length"
            :attachments="detail.attachments"
            mode="post" />
          <h3>评论（{{ comments.length }}）</h3>
          <p v-if="!comments.length" class="tf-empty">暂无评论</p>
          <div v-for="c in comments" :key="c.id" class="tf-comment">
            <UserBadge
              size="sm"
              :src="c.user?.avatar"
              :name="c.user?.nickname"
              :user-id="c.user?.id"
              :user-type="c.user?.userType || 'student'" />
            <span class="tf-meta">{{ c.user?.className || '未分班' }}</span>
            <p><ForumContent :content="c.content" /></p>
            <AttachmentList
              v-if="c.attachments && c.attachments.length"
              :attachments="c.attachments"
              mode="comment" />
            <button
              v-if="c.canDelete && c.status === 1"
              class="tf-danger small"
              @click="askHideComment(c)"
            >
              隐藏评论
            </button>
          </div>
        </div>
      </div>

      <ModerationReasonDialog
        :visible="reasonDialog.visible"
        :title="reasonDialog.title"
        hint="原因会提交给管理员复核。"
        :submitting="reasonDialog.submitting"
        @close="reasonDialog.visible = false"
        @confirm="submitReason"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { ElMessage } from 'element-plus';

import TeacherNavHeader from '$vtj/vue/TeacherNavHeader.vue';
import ModerationReasonDialog from '@/components/forum/ModerationReasonDialog.vue';
import UserBadge from '@/components/forum/UserBadge.vue';
import ForumContent from '@/components/forum/ForumContent.vue';
import AttachmentList from '@/components/forum/AttachmentList.vue';
import {
  teacherForumApi,
  type ModerationComment,
  type ModerationPost
} from '@/modules/community/moderationApi';

const posts = ref<ModerationPost[]>([]);
const comments = ref<ModerationComment[]>([]);
const detail = ref<ModerationPost | null>(null);
const loading = ref(false);
const keyword = ref('');
const className = ref('');
const classOptions = ref<string[]>([]);
const teacherClasses = ref<string[]>([]);
const canModerate = ref(true);

const reasonDialog = reactive({
  visible: false,
  title: '',
  submitting: false,
  action: '' as 'post' | 'comment',
  targetId: 0
});

const statusLabel = (status: string) =>
  ({ NORMAL: '正常', BLOCKED: '待复核隐藏', DELETED: '已删除' } as Record<string, string>)[status] ||
  status;

const loadPosts = async () => {
  loading.value = true;
  try {
    const data = await teacherForumApi.posts({
      keyword: keyword.value || undefined,
      class_name: className.value || undefined,
      limit: 50
    });
    posts.value = data.items;
    teacherClasses.value = data.teacherClasses || [];
    canModerate.value = data.canModerate !== false;
    const names = new Set<string>();
    data.items.forEach((item) => {
      if (item.authorClass) names.add(item.authorClass);
    });
    classOptions.value = [...names];
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载失败');
  } finally {
    loading.value = false;
  }
};

const openPost = async (post: ModerationPost) => {
  detail.value = post;
  try {
    const data = await teacherForumApi.comments(post.id);
    comments.value = data.items;
  } catch (e) {
    comments.value = [];
  }
};

const askHidePost = (post: ModerationPost) => {
  Object.assign(reasonDialog, {
    visible: true,
    title: `隐藏帖子：${post.title}`,
    action: 'post',
    targetId: post.id,
    submitting: false
  });
};

const askHideComment = (comment: ModerationComment) => {
  Object.assign(reasonDialog, {
    visible: true,
    title: '隐藏评论',
    action: 'comment',
    targetId: comment.id,
    submitting: false
  });
};

const submitReason = async (reason: string) => {
  reasonDialog.submitting = true;
  try {
    if (reasonDialog.action === 'post') {
      await teacherForumApi.hidePost(reasonDialog.targetId, reason);
    } else {
      await teacherForumApi.hideComment(reasonDialog.targetId, reason);
    }
    ElMessage.success('已提交管理员复核');
    reasonDialog.visible = false;
    detail.value = null;
    await loadPosts();
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败');
  } finally {
    reasonDialog.submitting = false;
  }
};

onMounted(loadPosts);
</script>

<style scoped>
.tf-page { min-height: 100vh; background: #f5f7fb; }
.tf-main { max-width: 1080px; margin: 0 auto; padding: 24px; }
.tf-head h1 { margin: 0 0 6px; color: #1a2b5f; }
.tf-sub { margin: 0 0 16px; color: #6b7896; font-size: 13px; }
.tf-filters { display: flex; gap: 8px; margin-bottom: 16px; }
.tf-filters input, .tf-filters select {
  padding: 8px 10px; border: 1px solid #d9e1ee; border-radius: 8px; font-size: 13px;
}
.tf-btn { border: none; border-radius: 8px; background: #1a365d; color: #fff; padding: 8px 16px; cursor: pointer; }
.tf-list { display: flex; flex-direction: column; gap: 12px; }
.tf-card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 2px 10px rgba(26,43,95,.05); }
.tf-card-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tf-title { font-weight: 700; color: #1a2b5f; }
.tf-meta { color: #8a94ad; font-size: 12px; }
.tf-status { font-size: 11px; padding: 2px 7px; border-radius: 10px; background: #eef3fb; color: #3b5b8c; }
.tf-status.st-BLOCKED { background: #fff4e5; color: #b45309; }
.tf-status.st-DELETED { background: #fee2e2; color: #b91c1c; }
.tf-content { color: #3b4a6b; font-size: 14px; line-height: 1.6; white-space: pre-wrap; }
.tf-actions { display: flex; gap: 8px; margin-top: 10px; }
.tf-link, .tf-danger { border: none; background: none; cursor: pointer; font-size: 13px; padding: 0; }
.tf-link { color: #1a365d; }
.tf-danger { color: #c41e3a; }
.tf-danger.small { font-size: 12px; }
.tf-empty { color: #8a94ad; text-align: center; padding: 30px; }
.tf-warn { background: #fff7e6; color: #b45309; border: 1px solid #fbe0b0; border-radius: 8px; padding: 10px 12px; font-size: 13px; margin: 0 0 14px; }
.tf-modal { position: fixed; inset: 0; z-index: 9000; background: rgba(8,12,24,.45); display: flex; align-items: center; justify-content: center; padding: 20px; }
.tf-modal-card { position: relative; width: min(720px, 94vw); max-height: 86vh; overflow-y: auto; background: #fff; border-radius: 14px; padding: 22px; }
.tf-close { position: absolute; top: 8px; right: 12px; border: none; background: none; font-size: 22px; color: #8a94ad; cursor: pointer; }
.tf-comment { border-top: 1px solid #eef1f7; padding-top: 8px; margin-top: 8px; }
</style>
