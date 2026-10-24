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
        <label class="label">分类</label>
        <div class="type-tabs">
          <div
            v-for="t in types"
            :key="t.key"
            :class="['type-tab', { active: shareType === t.key }]"
            @click="shareType = t.key"
          >
            {{ t.name }}
          </div>
        </div>
      </div>

      <div class="field">
        <label class="label">标题颜色</label>
        <TitleColorPicker v-model="titleColor" />
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
          <ImageUploader v-model="images" />
        </div>
        <div v-if="content" class="content-preview">
          <label class="label">预览</label>
          <ForumContent :content="content" />
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import {
  FORUM_SHARE_TYPE_OPTIONS,
  useCommunityStore
} from '@/modules/community/store';
import type { ForumShareType } from '@/modules/community/api';
import EmojiStickerPicker from '@/components/forum/EmojiStickerPicker.vue';
import ForumContent from '@/components/forum/ForumContent.vue';
import ImageUploader from '@/components/forum/ImageUploader.vue';
import TitleColorPicker from '@/components/forum/TitleColorPicker.vue';
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
  submitting.value = true;
  message.value = '';
  try {
    const created = await store.createPost({
      title: title.value,
      content: content.value,
      shareType: shareType.value,
      titleColor: titleColor.value,
      attachments: images.value.length ? images.value : undefined
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
.type-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.type-tab {
  padding: 8px 16px;
  border-radius: 18px;
  font-size: 13px;
  color: #5a6488;
  background: #f0f3f7;
  cursor: pointer;
}
.type-tab.active {
  background: #1a2b5f;
  color: #fff;
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
