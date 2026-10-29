<template>
  <div class="tf-page">
    <TeacherNavHeader active-nav="forum" />
    <main class="tf-main">
      <div class="tf-left">
      <header class="tf-head">
        <div class="tf-head-row">
          <h1>论坛管理</h1>
          <button class="tf-post-btn" @click="openPostForm">发布新帖</button>
        </div>
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
        <article
          v-for="post in posts"
          :key="post.id"
          class="tf-card tf-card-clickable"
          @click="openPost(post)">
          <div class="tf-card-head">
            <UserBadge
              size="sm"
              :src="post.authorAvatar"
              :name="post.author"
              :user-id="post.id"
              :user-type="post.authorType || 'student'" />
            <span class="tf-status" :class="`st-${post.status}`">{{ statusLabel(post.status) }}</span>
            <span class="tf-title" :style="{ color: titleColorValue(post.titleColor) }">{{ post.title }}</span>
            <span class="tf-meta">{{ post.authorClass || '未分班' }}</span>
          </div>
          <p class="tf-content"><ForumContent :content="post.content" /></p>
          <AttachmentList
            v-if="post.attachments && post.attachments.length"
            :attachments="post.attachments"
            mode="post" />
          <div class="tf-actions">
            <button class="tf-link" @click.stop="openPost(post)">查看评论</button>
            <button v-if="post.canDelete" class="tf-danger" @click.stop="askHidePost(post)">隐藏帖子</button>
          </div>
        </article>
      </div>

      <div v-if="detail" class="tf-modal" @click.self="detail = null">
        <div class="tf-modal-card">
          <button class="tf-close" @click="detail = null">×</button>
          <div class="tf-modal-scroll">
          <h2 :style="{ color: titleColorValue(detail.titleColor) }">{{ detail.title }}</h2>
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

          <!-- 教师评论输入（与学生端一致：文字 + 发送） -->
          <div class="tf-comment-input">
            <textarea
              v-model="commentDraft"
              class="tf-comment-textarea"
              rows="2"
              placeholder="写下你的评论… Ctrl+Enter 发送"
              @keyup.ctrl.enter="submitComment" />
            <button class="tf-icon-btn" title="表情" @click="showCommentEmoji = !showCommentEmoji">😊</button>
            <FileUploader v-model="commentAttachments" :max-docs="0" class="tf-comment-uploader" />
            <div v-if="showCommentEmoji" class="tf-emoji-pop">
              <EmojiStickerPicker @select="onEmojiSelect" @close="showCommentEmoji = false" />
            </div>
            <button
              class="tf-btn"
              :disabled="commentSubmitting || !commentDraft.trim()"
              @click="submitComment">
              {{ commentSubmitting ? '发送中…' : '发送' }}
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
      </div>

      <aside class="tf-side">
        <section class="tf-mini-card">
          <h3>热门帖子</h3>
          <p v-if="!hotPosts.length" class="tf-mini-empty">暂无数据</p>
          <ul v-else>
            <li v-for="h in hotPosts" :key="h.id" @click="openPost(h)">
              <span class="tf-mini-title" :style="{ color: titleColorValue(h.titleColor) }">{{ h.title }}</span>
              <span class="tf-mini-num">❤ {{ h.likeCount }}</span>
            </li>
          </ul>
        </section>

        <section class="tf-mini-card">
          <h3>论坛活跃</h3>
          <div class="tf-stats">
            <div><b>{{ stats.posts }}</b><span>帖子</span></div>
            <div><b>{{ stats.users }}</b><span>用户</span></div>
            <div><b>{{ stats.online }}</b><span>在线</span></div>
          </div>
        </section>

        <section class="tf-mini-card">
          <h3>我的帖子</h3>
          <p v-if="!myPosts.length" class="tf-mini-empty">还没有发过帖</p>
          <ul v-else>
            <li v-for="m in myPosts" :key="m.id" @click="openPost(m)">
              <span class="tf-mini-title">{{ m.title }}</span>
              <span class="tf-mini-num">💬 {{ m.commentCount }}</span>
            </li>
          </ul>
        </section>
      </aside>
    </main>
    <!-- P3-07：教师发帖（含可见范围） -->
    <div v-if="postForm.visible" class="tf-modal" @click.self="postForm.visible = false">
      <div class="tf-modal-card">
        <h3>发布新帖</h3>
        <input v-model="postForm.title" class="tf-input" placeholder="请输入标题…" maxlength="200" />
        <textarea v-model="postForm.content" class="tf-textarea" rows="6" placeholder="请输入内容…"></textarea>
        <div class="tf-upload-row">
          <span class="tf-label">附件（不限个数，单个 ≤20MB）</span>
          <FileUploader v-model="postForm.attachments" :max-docs="0" />
        </div>
        <div class="tf-visibility">
          <span class="tf-label">可见范围</span>
          <label><input type="radio" value="ALL" v-model="postForm.visibility" /> 全校</label>
          <label><input type="radio" value="CLASSES" v-model="postForm.visibility" /> 自己班级</label>
        </div>
        <div v-if="postForm.visibility === 'CLASSES'" class="tf-classes">
          <label v-for="c in classOptions" :key="c" class="tf-class-chip">
            <input type="checkbox" :value="c" v-model="postForm.classes" /> {{ c }}
          </label>
          <p v-if="!classOptions.length" class="tf-mini-empty">未查到可管理班级，请先绑定班级</p>
        </div>
        <div class="tf-modal-actions">
          <button class="tf-btn ghost" @click="postForm.visible = false">取消</button>
          <button class="tf-btn" :disabled="postForm.submitting" @click="submitPost">
            {{ postForm.submitting ? '发布中…' : '发布' }}
          </button>
        </div>
      </div>
    </div>
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
import { titleColorValue } from '@/components/forum/titleColors';
import { createForumComment } from '@/modules/community/api';
import FileUploader from '@/components/forum/FileUploader.vue';
import EmojiStickerPicker from '@/components/forum/EmojiStickerPicker.vue';
import {
  createForumPostWithVisibility,
  fetchForumPosts,
  fetchForumStats,
  fetchMyForumPosts
} from '@/modules/community/api';
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
const commentDraft = ref('');
const commentSubmitting = ref(false);

// P3-07：侧栏三卡 + 发帖弹窗
const hotPosts = ref<any[]>([]);
const stats = reactive({ posts: 0, users: 0, online: 0 });
const myPosts = ref<any[]>([]);
const postForm = reactive({
  visible: false,
  submitting: false,
  title: '',
  titleColor: 'default',
  content: '',
  visibility: 'ALL' as 'ALL' | 'CLASSES',
  classes: [] as string[],
  attachments: [] as any[]
});
const commentAttachments = ref<any[]>([]);
const showCommentEmoji = ref(false);
const onEmojiSelect = (p: { value: string }) => {
  commentDraft.value += p.value;
  showCommentEmoji.value = false;
};

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

const openPostForm = () => {
  postForm.visible = true;
};

const loadSideCards = async () => {
  try {
    const hot: any = await fetchForumPosts({ sortBy: 'likes', limit: 5 });
    hotPosts.value = (hot && hot.posts) || [];
  } catch (e) { hotPosts.value = []; }
  try {
    const s: any = await fetchForumStats();
    if (s) { stats.posts = s.posts || 0; stats.users = s.users || 0; stats.online = s.online || 0; }
  } catch (e) { /* 忽略 */ }
  try {
    const mine: any = await fetchMyForumPosts({ limit: 5 });
    myPosts.value = (mine && mine.posts) || [];
  } catch (e) { myPosts.value = []; }
};

const submitPost = async () => {
  if (!postForm.title.trim() || !postForm.content.trim()) {
    ElMessage.warning('标题和正文不能为空');
    return;
  }
  if (postForm.visibility === 'CLASSES' && !postForm.classes.length) {
    ElMessage.warning('请选择可见班级');
    return;
  }
  postForm.submitting = true;
  try {
    await createForumPostWithVisibility({
      title: postForm.title.trim(),
      content: postForm.content.trim(),
      titleColor: postForm.titleColor,
      visibility: postForm.visibility,
      attachments: postForm.attachments,
      visibleClasses: postForm.visibility === 'CLASSES' ? postForm.classes : undefined
    });
    ElMessage.success('发布成功');
    postForm.visible = false;
    postForm.title = '';
    postForm.content = '';
    await Promise.all([loadPosts(), loadSideCards()]);
  } catch (e: any) {
    ElMessage.error(e && e.message ? e.message : '发布失败');
  } finally {
    postForm.submitting = false;
  }
};

const submitComment = async () => {
  const text = commentDraft.value.trim();
  if (!text || !detail.value) return;
  commentSubmitting.value = true;
  try {
    await createForumComment(detail.value.id, { content: text, attachments: commentAttachments.value });
    ElMessage.success('评论已发送');
    commentDraft.value = '';
    commentAttachments.value = [];
    await openPost(detail.value);
  } catch (e: any) {
    ElMessage.error(e && e.message ? e.message : '评论失败');
  } finally {
    commentSubmitting.value = false;
  }
};

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

onMounted(loadSideCards);
onMounted(loadPosts);
</script>

<style scoped>
.tf-page { min-height: 100vh; background: #f5f7fb; 
  height: 100vh;
  overflow-y: auto;
  overscroll-behavior: contain;
}
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
.tf-modal-card { position: relative; display: flex; flex-direction: column; width: min(720px, 94vw); max-height: 86vh; overflow: hidden; background: #fff; border-radius: 14px; padding: 22px; }
.tf-close { position: absolute; top: 8px; right: 12px; border: none; background: none; font-size: 22px; color: #8a94ad; cursor: pointer; }
.tf-modal-card h3 { margin: 20px 0 4px; font-size: 15px; color: #1a2b5f; }
.tf-modal-card > h2 { margin: 0 0 6px; }
/* 评论布局：首行「头像 昵称 班级 … 隐藏评论」，正文与附件缩进对齐昵称 */
.tf-comment {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  column-gap: 10px;
  row-gap: 6px;
  border-top: 1px solid #eef1f7;
  padding: 14px 0;
}
.tf-comment > .tf-danger { order: 1; margin-left: auto; }
.tf-comment > p,
.tf-comment :deep(.attachment-list) {
  order: 2;
  flex: 0 0 100%;
  box-sizing: border-box;
  padding-left: 38px;   /* 28px 头像 + 10px 间距 */
  margin: 0;
  line-height: 1.6;
  color: #3b4a6b;
  font-size: 14px;
}
/* P3-07：两列布局 + 侧栏三卡 + 发帖弹窗 */
.tf-main { display: grid; grid-template-columns: 1fr 300px; gap: 20px; align-items: start; }
.tf-left { min-width: 0; }
.tf-head-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.tf-post-btn { padding: 10px 18px; border: none; border-radius: 10px; background: #c41e3a; color: #fff; font-size: 14px; font-weight: 600; cursor: pointer; }
/* 右侧三卡固定：与学生端 PC 右栏同款做法（sticky + align-self:start） */
.tf-side {
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: sticky;
  top: 16px;
  align-self: start;
  max-height: calc(100vh - 32px);
  overflow-y: auto;
  overscroll-behavior: contain;
}
.tf-mini-card { background: #fff; border-radius: 14px; padding: 14px 16px; box-shadow: 0 2px 12px rgba(15,23,42,.06); }
.tf-mini-card h3 { margin: 0 0 10px; font-size: 15px; color: #1a2b5f; }
.tf-mini-card ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.tf-mini-card li { display: flex; justify-content: space-between; gap: 8px; font-size: 13px; cursor: pointer; }
.tf-mini-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tf-mini-num { color: #94a3b8; flex: 0 0 auto; }
.tf-mini-empty { color: #94a3b8; font-size: 13px; margin: 0; }
.tf-stats { display: flex; gap: 16px; }
.tf-stats div { display: flex; flex-direction: column; align-items: center; }
.tf-stats b { font-size: 18px; color: #c41e3a; }
.tf-stats span { font-size: 12px; color: #94a3b8; }
.tf-modal { position: fixed; inset: 0; background: rgba(15,23,42,.45); display: flex; align-items: center; justify-content: center; z-index: 2200; }
.tf-modal-card { width: 560px; max-width: 92vw; background: #fff; border-radius: 16px; padding: 20px; display: flex; flex-direction: column; gap: 12px; }
.tf-modal-card h3 { margin: 0; font-size: 17px; color: #1a2b5f; }
.tf-input, .tf-textarea, .tf-select { width: 100%; padding: 10px 12px; border: 1px solid #e3e8ef; border-radius: 10px; font-size: 14px; box-sizing: border-box; }
.tf-color-row, .tf-visibility { display: flex; align-items: center; gap: 10px; font-size: 13px; color: #475569; }
.tf-label { color: #1a2b5f; font-weight: 600; }
.tf-classes { display: flex; flex-wrap: wrap; gap: 8px; }
.tf-class-chip { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; }
.tf-modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
.tf-btn.ghost { background: #fff; color: #475569; border: 1px solid #e3e8ef; }
.tf-modal-scroll { flex: 1 1 auto; overflow-y: auto; min-height: 0; padding-right: 4px; }
.tf-card-clickable { cursor: pointer; }
.tf-card-clickable:hover { background: #fafbfe; }
.tf-comment-input { display:flex; gap:8px; align-items:flex-end; margin-top:14px; padding-top:12px; border-top:1px solid #eef1f6; }
.tf-comment-textarea { flex:1 1 auto; min-width:0; padding:10px 12px; border:1px solid #e3e8ef; border-radius:10px; font-size:14px; resize:vertical; }
.tf-upload-row { display: flex; flex-direction: column; gap: 6px; }
.tf-icon-btn { height: 36px; width: 36px; border: 1px solid #e3e8ef; border-radius: 8px; background: #fff; cursor: pointer; flex: 0 0 auto; }
.tf-comment-uploader { flex: 0 0 auto; }
.tf-emoji-pop { position: absolute; bottom: 64px; left: 12px; z-index: 20; background: #fff; border: 1px solid #eef1f6; border-radius: 12px; box-shadow: 0 8px 24px rgba(15,23,42,.12); }
</style>





