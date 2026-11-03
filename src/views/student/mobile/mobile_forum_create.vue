<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">发布帖子</h1>
      <button class="submit-btn" @click="submitPost" :disabled="submitting">发布</button>
    </header>

    <main class="form">
      <div class="msg" v-if="message" :class="msgType">{{ message }}</div>

      <div class="field">
        <label class="label">标题</label>
        <input v-model="title" type="text" class="input" placeholder="请输入标题（最多200字）" maxlength="200" />
      </div>




      <div class="field">
        <label class="label">内容</label>
        <textarea v-model="content" class="textarea" placeholder="分享你的经验、资料或心得..." rows="10"></textarea>
        <div class="composer-actions">
          <button class="emoji-trigger" @click="showPicker = !showPicker">😊 表情 / 表情包</button>
          <span class="hint">支持 emoji 与自定义表情包</span>
        </div>
        <div v-if="showPicker" class="picker-wrap">
          <EmojiStickerPicker @select="insertEmoji" @close="showPicker = false" />
        </div>
        <div class="image-field">
          <label class="label">图片（不限张数）</label>
          <FileUploader v-model="images" :max-docs="10" />
        </div>
        <div v-if="content" class="content-preview">
          <label class="label">预览</label>
          <ForumContent :content="content" />
        </div>
      </div>

      <!-- 可见范围（2026-11-03 新增）：与 PC/平板同一套语义 —— ALL 全校 / CLASSES 本班 -->
      <div class="field">
        <label class="label">可见范围</label>
        <div class="visibility-group">
          <button
            type="button"
            :class="['visibility-pill', { on: visibility === 'ALL' }]"
            @click="visibility = 'ALL'"
          >全站可见</button>
          <button
            type="button"
            :class="['visibility-pill', { on: visibility === 'CLASSES' }]"
            :disabled="!myClasses.length"
            @click="visibility = 'CLASSES'"
          >仅本班可见</button>
        </div>
        <p v-if="!myClasses.length" class="hint">
          当前账号未分班，只能发全站帖；如需按班级发送请联系管理员分配班级
        </p>
        <p v-else class="hint">仅本班：{{ myClasses.join('、') }} 的同学可见</p>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import {
  FORUM_SHARE_TYPE_OPTIONS,
  useCommunityStore
} from '@/modules/community/store';
import type { ForumShareType } from '@/modules/community/api';
import { loadMyClasses } from '@/modules/community/classScope';
import EmojiStickerPicker from '@/components/forum/EmojiStickerPicker.vue';
import ForumContent from '@/components/forum/ForumContent.vue';
import FileUploader from '@/components/forum/FileUploader.vue';
import type { ForumImageAttachment } from '@/components/forum/imageUtils';

const router = useRouter();
const store = useCommunityStore();
const title = ref('');
const content = ref('');
const showPicker = ref(false);
const shareType = ref<ForumShareType>('EXPERIENCE');
const titleColor = ref('default');
const images = ref<ForumImageAttachment[]>([]);
const submitting = ref(false);
const message = ref('');
const msgType = ref('');
/** 可见范围：有班级时默认「仅本班」（与后端学生默认规则一致），未分班则只能全站 */
const visibility = ref<'ALL' | 'CLASSES'>('ALL');
const myClasses = ref<string[]>([]);

onMounted(async () => {
  const scope = await loadMyClasses();
  myClasses.value = scope.classes;
  visibility.value = scope.hasClass ? 'CLASSES' : 'ALL';
});

const types = FORUM_SHARE_TYPE_OPTIONS;

const insertEmoji = (payload: { type: 'emoji' | 'sticker'; value: string; name?: string }) => {
  if (payload.type === 'emoji') {
    content.value += payload.value;
  } else {
    content.value += `[[sticker:${payload.value}]]`;
  }
};

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/forum');
};

const submitPost = async () => {
  // 2026-11-01：标题 / 正文 / 附件 至少一项即可发布（与 PC、教师端一致）
  const hasAtt = (images.value?.length || 0) > 0;
  if (!title.value.trim() && !content.value.trim() && !hasAtt) {
    showMsg('标题、正文、附件至少填写一项', 'error');
    return;
  }
  submitting.value = true;
  message.value = '';
  try {
    const created = await store.createPost({
      title: title.value,
      content: content.value,
      shareType: shareType.value,
      titleColor: titleColor.value,
      attachments: images.value.length ? images.value : undefined,
      visibility: visibility.value,
      visibleClasses: visibility.value === 'CLASSES' ? myClasses.value : undefined
    });
    if (!created) {
      showMsg(store.error || '发布失败，请稍后重试', 'error');
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }
    showMsg('发布成功', 'success');
    setTimeout(() => router.push('/mobile/forum'), 800);
  } catch (e) {
    showMsg(store.error || (e instanceof Error ? e.message : '发布失败'), 'error');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } finally {
    submitting.value = false;
  }
};

const showMsg = (m: string, type: string) => {
  message.value = m;
  msgType.value = type;
};
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
.submit-btn {
  min-height: 36px;
  padding: 0 16px;
  border: none;
  border-radius: 8px;
  background: linear-gradient(135deg, #C91F37, #e8384f);
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}
.submit-btn:disabled {
  opacity: 0.6;
}
.form {
  flex: 1;
  padding: 16px;
}
.msg {
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 16px;
}
.msg.error {
  background: #fff2f0;
  color: #c41e3a;
  border: 1px solid #ffccc7;
}
.msg.success {
  background: #f6ffed;
  color: #10b981;
  border: 1px solid #b7eb8f;
}
.field {
  margin-bottom: 20px;
}
.label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
  margin-bottom: 8px;
}
.input,
.textarea {
  width: 100%;
  border: 1px solid #e8ecf1;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 15px;
  color: #1a2a3a;
  font-family: inherit;
  outline: none;
  background: #fff;
}
.input:focus,
.textarea:focus {
  border-color: #C91F37;
  box-shadow: 0 0 0 3px rgba(201, 31, 55, 0.08);
}
.textarea {
  resize: vertical;
  line-height: 1.6;
}
.composer-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
}
.emoji-trigger {
  background: #f0f3f7;
  border: none;
  border-radius: 16px;
  padding: 6px 14px;
  font-size: 13px;
  color: #1a365d;
  cursor: pointer;
}
.hint {
  font-size: 11px;
  color: #8899aa;
}
/* 可见范围 pills（2026-11-03）：与 PC 弹窗同一套语义与配色 */
.visibility-group {
  display: flex;
  gap: 8px;
}
.visibility-pill {
  flex: 1;
  height: 38px;
  border: 1px solid #e2e8f3;
  border-radius: 10px;
  background: #fff;
  color: #5a6488;
  font-size: 13px;
  cursor: pointer;
}
.visibility-pill.on {
  border-color: #1a365d;
  color: #1a365d;
  background: #f2f7fc;
  font-weight: 600;
}
.visibility-pill:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.picker-wrap {
  margin-top: 8px;
}
.content-preview {
  margin-top: 12px;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 10px;
  font-size: 14px;
  color: #1a2a3a;
  line-height: 1.6;
}
</style>
