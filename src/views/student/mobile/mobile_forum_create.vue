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
        <input v-model="title" type="text" class="input" placeholder="请输入标题（最多200字）" maxlength="200" @input="titleFromAi = false" />
        <!-- v4（2026-11-04）：AI 标题开关 + 生成按钮，与 PC 弹窗同一套语义 -->
        <div class="ai-row">
          <label class="ai-check">
            <input v-model="aiTitleEnabled" type="checkbox" />
            <span>允许 AI 自动总结标题</span>
          </label>
          <button
            v-if="aiTitleEnabled"
            type="button"
            class="ai-btn"
            :disabled="suggesting"
            @click="onSuggestTitle"
          >{{ suggesting ? '生成中…' : (titleFromAi ? '重新生成' : 'AI 生成标题') }}</button>
        </div>
        <p class="hint">
          {{ aiTitleEnabled
            ? '不填标题时才会生效；生成后可修改或重新生成'
            : '已关闭：按原样发布，不调用大模型' }}
        </p>
      </div>




      <div class="field">
        <label class="label">内容</label>
        <!-- 2026-11-04 v5：手机端也接入富文本编辑器，与 PC/平板同一套菜单 -->
        <div class="editor-rich">
          <RichTextEditor
            v-model="content"
            :menus="richMenus"
            :height="220"
            :upload-image="uploadImageForEditor"
            placeholder="分享你的经验、资料或心得..."
          />
        </div>
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
        <div v-if="hasContent" class="content-preview">
          <label class="label">预览</label>
          <ForumContent :content="content" format="HTML" />
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
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import {
  FORUM_SHARE_TYPE_OPTIONS,
  useCommunityStore
} from '@/modules/community/store';
import type { ForumShareType } from '@/modules/community/api';
import { suggestForumTitle } from '@/modules/community/api';
import { loadMyClasses } from '@/modules/community/classScope';
import EmojiStickerPicker from '@/components/forum/EmojiStickerPicker.vue';
import ForumContent from '@/components/forum/ForumContent.vue';
import FileUploader from '@/components/forum/FileUploader.vue';
import RichTextEditor from '@/components/rich-text/RichTextEditor.vue';
import { uploadForumImage } from '@/components/forum/imageUtils';
import type { ForumImageAttachment } from '@/components/forum/imageUtils';

const router = useRouter();
const store = useCommunityStore();
const title = ref('');
const content = ref('');
const showPicker = ref(false);

// ===== 富文本（v5 2026-11-04）=====
/** 与 PC 弹窗同一套菜单，保证三端排版能力一致 */
const richMenus = [
  'head',
  'fontName',
  'fontSize',
  'bold',
  'italic',
  'underline',
  'strikeThrough',
  'color',
  'bgColor',
  'justify',
  'list',
  'quote',
  'emoticon',
  'insertTable',
  'divider',
  'undo',
  'redo'
];

/** 编辑器内插图走论坛图片接口（与附件同一套校验） */
const uploadImageForEditor = async (file: File): Promise<string> => {
  const attachment = await uploadForumImage(file);
  return attachment.url;
};

/** 去掉标签后判断正文是否真的有内容（<p><br></p> 视为空） */
const stripHtml = (html: string): string =>
  String(html || '')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, '')
    .trim();

const hasContent = computed(() => stripHtml(content.value).length > 0);
const shareType = ref<ForumShareType>('EXPERIENCE');
const titleColor = ref('default');
const images = ref<ForumImageAttachment[]>([]);
const submitting = ref(false);
const message = ref('');
const msgType = ref('');
/** 可见范围：有班级时默认「仅本班」（与后端学生默认规则一致），未分班则只能全站 */
const visibility = ref<'ALL' | 'CLASSES'>('ALL');
const myClasses = ref<string[]>([]);

// ===== AI 标题（v4 2026-11-04）=====
const aiTitleEnabled = ref(true);
const titleFromAi = ref(false);
const suggesting = ref(false);
const suggestCount = ref(0);
const MAX_SUGGEST = 5;

/** 按正文让 AI 拟标题并填入输入框；不满意可再次点击重新生成 */
async function onSuggestTitle() {
  if (suggesting.value) return;
  if (suggestCount.value >= MAX_SUGGEST) {
    showMsg(`本次最多生成 ${MAX_SUGGEST} 次，请手动填写标题`, 'error');
    return;
  }
  if (!content.value.trim()) {
    showMsg('请先填写正文，AI 需要根据正文内容总结标题', 'error');
    return;
  }
  suggesting.value = true;
  try {
    const res = await suggestForumTitle(content.value, 'TEXT');
    if (!res.title) {
      showMsg(
        res.reason === 'no_content'
          ? '正文内容太少，AI 无法总结标题，请补充正文或手动填写'
          : 'AI 暂时不可用，请稍后重试或手动填写',
        'error'
      );
      return;
    }
    title.value = res.title;
    titleFromAi.value = true;
    suggestCount.value += 1;
  } catch (e: any) {
    showMsg(e?.message || 'AI 生成标题失败，请手动填写', 'error');
  } finally {
    suggesting.value = false;
  }
}

onMounted(async () => {
  const scope = await loadMyClasses();
  myClasses.value = scope.classes;
  visibility.value = scope.hasClass ? 'CLASSES' : 'ALL';
});

const types = FORUM_SHARE_TYPE_OPTIONS;

const insertEmoji = (payload: { type: 'emoji' | 'sticker'; value: string; name?: string }) => {
  // v5：正文改为 HTML，表情包要用 img 标签，否则会以 [[sticker:url]] 文本显示
  if (payload.type === 'emoji') {
    content.value += payload.value;
  } else {
    content.value += `<img src="${payload.value}" class="forum-sticker" alt="表情包" />`;
  }
};

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/forum');
};

const submitPost = async () => {
  // 2026-11-01：标题 / 正文 / 附件 至少一项即可发布（与 PC、教师端一致）
  const hasAtt = (images.value?.length || 0) > 0;
  // v5：正文已是 HTML，<p><br></p> 这种空富文本不能被当成"有内容"
  if (!title.value.trim() && !hasContent.value && !hasAtt) {
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
      // v5：正文以富文本 HTML 落库（后端会做白名单消毒）
      contentFormat: 'HTML',
      visibility: visibility.value,
      visibleClasses: visibility.value === 'CLASSES' ? myClasses.value : undefined,
      // v4：AI 标题开关与「标题是否原样来自模型」
      aiTitleEnabled: aiTitleEnabled.value,
      titleFromAi: titleFromAi.value
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
/* v5：富文本编辑器容器（与 PC 弹窗观感一致） */
.editor-rich {
  background: #fff;
  border: 1px solid #e6ebf3;
  border-radius: 10px;
  overflow: hidden;
}

/* v4：AI 标题开关与生成按钮（移动端竖排） */
.ai-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: 8px;
}
.ai-check {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: #33415c;
}
.ai-check input {
  width: 15px;
  height: 15px;
  accent-color: #1a365d;
}
.ai-btn {
  flex: 0 0 auto;
  height: 32px;
  padding: 0 12px;
  border: 1px solid #c7d7ff;
  border-radius: 8px;
  background: #f2f7ff;
  color: #2563eb;
  font-size: 12.5px;
  cursor: pointer;
}
.ai-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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
