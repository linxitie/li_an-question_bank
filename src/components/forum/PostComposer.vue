<template>
  <Teleport to="body">
    <div v-if="visible" class="pc-mask" @click.self="close">
      <div class="pc-modal">
        <div class="pc-hd">
          <h3>{{ title }}</h3>
          <button class="pc-x" type="button" title="关闭" @click="close">×</button>
        </div>

        <div class="pc-bd">
          <!-- 2026-11-07：草稿改为“手动恢复”，打开弹窗默认空白，避免把上次测试内容带进新帖 -->
          <div v-if="pendingDraft" class="draft-bar">
            <span>检测到上次未发布的草稿</span>
            <button type="button" class="draft-restore" @click="restoreDraft">恢复草稿</button>
            <button type="button" class="draft-ignore" @click="pendingDraft = null">忽略</button>
          </div>
          <div class="f-row">
            <label>标题 <span class="req">*</span></label>
            <div class="title-row">
              <input
                v-model="form.title"
                class="f-input"
                maxlength="200"
                placeholder="给帖子起一个清晰的标题，例如：2024 公专真题变化分析"
                @input="onTitleEdited"
              />
              <button
                v-if="form.aiTitleEnabled"
                type="button"
                class="ai-suggest-btn"
                :disabled="suggesting"
                :title="suggestHint"
                @click="onSuggestTitle"
              >{{ suggesting ? '生成中…' : (titleFromAi ? '重新生成' : 'AI 生成标题') }}</button>
            </div>
            <!-- AI 标题开关（v4 2026-11-04）：用户不同意就完全不调用大模型 -->
            <div class="ai-switch-row">
              <label class="ai-switch">
                <input v-model="form.aiTitleEnabled" type="checkbox" />
                <span>允许 AI 自动总结标题</span>
              </label>
              <span class="ai-switch-tip">
                {{ form.aiTitleEnabled
                  ? '不填标题时才会生效；生成后可修改或重新生成'
                  : '已关闭：按原样发布，不调用大模型' }}
              </span>
            </div>
            <p v-if="titleFromAi" class="ai-ok-tip">已生成建议标题，可直接发布，也可手动修改或重新生成</p>
          </div>

          <div class="f-row">
            <label>正文 <span class="req">*</span></label>
            <!-- 2026-11-03：改用仓库已有的 wangEditor（RichTextEditor）做所见即所得，
                 工具栏含段落/字体/字号/颜色/对齐/列表/引用/表情/表格/图片/链接/撤销重做。
                 正文以 HTML 存储，落库前后端会走 bleach 白名单消毒。 -->
            <div class="editor-rich">
              <RichTextEditor
                v-model="form.content"
                :menus="richMenus"
                :height="200"
                :upload-image="uploadImageForEditor"
                placeholder="正文内容，支持 @ 同学、插入图片与附件。请避免发布与备考无关的内容。"
              />
            </div>
          </div>

          <div class="f-row">
            <label>附件</label>
            <div class="dropzone" :class="{ busy: uploading }" @click="pickFile" @dragover.prevent @drop.prevent="onDrop">
              <div class="dz-ic">
                <svg width="22" height="22" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.2">
                  <path d="M8 2.4v7" />
                  <path d="M5 5.4l3-3 3 3" />
                  <path d="M2.6 10.4v2a1.2 1.2 0 001.2 1.2h8.4a1.2 1.2 0 001.2-1.2v-2" />
                </svg>
              </div>
              <span v-if="uploading">上传中…</span>
              <template v-else>
                拖拽文件到此处，或 <b>点击选择文件</b>
                <small>{{ attachHint }}</small>
              </template>
            </div>
            <div v-if="form.attachments.length" class="pc-files">
              <span v-for="(att, i) in form.attachments" :key="att.url" class="pc-file">
                {{ fileIcon(att.name) }} {{ att.name }} <small>{{ formatFileSize(att.size) }}</small>
                <button type="button" class="pc-file-x" title="移除" @click="removeAttachment(i)">×</button>
              </span>
            </div>
          </div>

          <div class="pc-split">
            <div class="f-row pc-vi">
              <label>可见范围</label>
              <div class="radio-pills">
                <span :class="['rp', { on: form.visibility === 'ALL' }]" @click="form.visibility = 'ALL'">全站可见</span>
                <span :class="['rp', { on: form.visibility === 'CLASSES' }]" @click="form.visibility = 'CLASSES'">仅指定班级</span>
              </div>
              <div v-if="form.visibility === 'CLASSES'" class="pc-classes">
                <span v-if="!classes.length" class="pc-tip">
                  当前账号未分班，无法按班级发送；请改用「全站可见」，或先联系管理员分配班级
                </span>
                <label v-for="c in classes" :key="c" class="chk-row">
                  <input v-model="form.visibleClasses" type="checkbox" :value="c" />{{ c }}
                </label>
              </div>
            </div>
            <div v-if="canPin" class="f-row">
              <label>其他</label>
              <label class="chk-row">
                <input v-model="form.isTop" type="checkbox" />置顶显示 <small>出现在列表最上方</small>
              </label>
            </div>
          </div>

          <p v-if="error" class="pc-error">{{ error }}</p>
        </div>

        <div class="pc-ft">
          <button class="btn btn-sm" type="button" :disabled="savingDraft || submitting" @click="onSaveDraft">
            {{ savingDraft ? '保存中…' : '存为草稿' }}
          </button>
          <button class="btn btn-sm btn-accent" type="button" :disabled="uploading || submitting" @click="onSubmit">
            {{ submitting ? '发布中…' : '发布' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';

import { suggestForumTitle } from '@/modules/community/api';

import RichTextEditor from '@/components/rich-text/RichTextEditor.vue';
import { fileIcon, formatFileSize, isDocFile, isImageFile, MAX_DOC_SIZE, uploadForumFile } from './fileUtils';
import {
  MAX_IMAGE_SIZE,
  uploadForumImage,
  type ForumImageAttachment
} from './imageUtils';

export interface PostDraft {
  title: string;
  /** 正文：contentFormat='HTML' 时是富文本 HTML，否则是纯文本 */
  content: string;
  contentFormat?: 'TEXT' | 'HTML';
  attachments: ForumImageAttachment[];
  visibility: 'ALL' | 'CLASSES';
  visibleClasses: string[];
  isTop: boolean;
  /** 是否允许 AI 总结标题（v4）：关闭后后端完全跳过模型调用 */
  aiTitleEnabled?: boolean;
  /** 标题是否原样来自模型建议（用户没改过）*/
  titleFromAi?: boolean;
}

/** wangEditor 工具栏：图三那一组「原生支持」的菜单（公式/语音/音乐/视频为二期） */
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

/** 富文本内插图统一走论坛图片接口（与附件同一套白名单/大小校验） */
const uploadImageForEditor = async (file: File): Promise<string> => {
  const attachment = await uploadForumImage(file);
  return attachment.url;
};

/** 去掉 HTML 标签后判断正文是否真的为空（<p><br></p> 视为空） */
function stripHtml(html: string): string {
  return String(html || '')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, '')
    .trim();
}

const props = withDefaults(
  defineProps<{
    visible: boolean;
    /** 打开时回填的内容（草稿或空白） */
    initial?: Partial<PostDraft> | null;
    /** 置顶仅教师/管理员可用 */
    canPin?: boolean;
    /** 可选班级（学生只有本班，教师有自己的班） */
    classes?: string[];
    submitting?: boolean;
    savingDraft?: boolean;
    title?: string;
    maxContent?: number;
    maxAttachments?: number;
  }>(),
  {
    initial: null,
    canPin: false,
    classes: () => [],
    submitting: false,
    savingDraft: false,
    title: '发布新帖',
    maxContent: 5000,
    maxAttachments: 5
  }
);

const emit = defineEmits<{
  (event: 'update:visible', value: boolean): void;
  (event: 'submit', value: PostDraft): void;
  (event: 'save-draft', value: PostDraft): void;
}>();

const form = reactive<PostDraft>({
  title: '',
  content: '',
  contentFormat: 'HTML',
  attachments: [],
  visibility: 'ALL',
  visibleClasses: [],
  isTop: false,
  aiTitleEnabled: true,
  titleFromAi: false
});

const uploading = ref(false);
const error = ref('');
const fileInput = ref<HTMLInputElement | null>(null);
/** 2026-11-07：待恢复的草稿。打开弹窗不再自动回填，由用户点“恢复草稿”。 */
const pendingDraft = ref<Partial<PostDraft> | null>(null);

function hasDraftContent(init: Partial<PostDraft> | null | undefined): boolean {
  if (!init) return false;
  return Boolean(
    String(init.title || '').trim() ||
      stripHtml(String(init.content || '')) ||
      (init.attachments && init.attachments.length)
  );
}

function restoreDraft() {
  if (!pendingDraft.value) return;
  applyInitial(pendingDraft.value);
  pendingDraft.value = null;
}

// ===== AI 标题建议（v4 2026-11-04）=====
const suggesting = ref(false);
/** 本次打开弹窗已生成次数：超过 5 次就不再调用，避免连点烧 token */
const suggestCount = ref(0);
const MAX_SUGGEST_PER_OPEN = 5;
/** 标题是否来自模型建议且用户未手改 */
const titleFromAi = ref(false);

const suggestHint = computed(() => {
  if (suggestCount.value >= MAX_SUGGEST_PER_OPEN) {
    return `本次最多生成 ${MAX_SUGGEST_PER_OPEN} 次，请手动填写标题`;
  }
  return '按正文内容让 AI 拟一个标题';
});

/** 表单是否还是空的（用于判断「能不能安全回填草稿」） */
function isFormEmpty(): boolean {
  return !form.title.trim() && !stripHtml(form.content) && form.attachments.length === 0;
}

/** 把 initial 回填进表单 */
function applyInitial(init: Partial<PostDraft>) {
  form.title = init.title ?? '';
  form.content = init.content ?? '';
  form.attachments = [...(init.attachments ?? [])];
  form.visibility = init.visibility === 'CLASSES' ? 'CLASSES' : 'ALL';
  form.visibleClasses = [...(init.visibleClasses ?? [])];
  form.isTop = Boolean(init.isTop);
  // v4：草稿里存的开关状态优先；没有则默认允许
  form.aiTitleEnabled = init.aiTitleEnabled !== false;
  // 打开弹窗时重置一次性状态：AI 建议次数、是否来自模型
  suggestCount.value = 0;
  titleFromAi.value = Boolean(init.titleFromAi);
}

/**
 * 点「AI 生成标题 / 重新生成」：先调预览接口拿建议填进标题框，用户可改、可再生成。
 * 覆盖已有标题前会二次确认，避免把用户手写的标题一键抹掉。
 */
async function onSuggestTitle() {
  if (suggesting.value) return;
  if (suggestCount.value >= MAX_SUGGEST_PER_OPEN) {
    error.value = `本次最多生成 ${MAX_SUGGEST_PER_OPEN} 次标题，请直接手动填写`;
    return;
  }
  if (form.title.trim()) {
    const ok = window.confirm('将用 AI 建议替换当前标题，继续？');
    if (!ok) return;
  }

  const plain = stripHtml(form.content);
  if (!plain) {
    error.value = '请先填写正文，AI 需要根据正文内容总结标题';
    return;
  }

  suggesting.value = true;
  error.value = '';
  try {
    const res = await suggestForumTitle(form.content, form.contentFormat === 'HTML' ? 'HTML' : 'TEXT');
    if (!res.title) {
      error.value =
        res.reason === 'no_content'
          ? '正文内容太少，AI 无法总结标题，请补充正文或手动填写标题'
          : 'AI 暂时不可用，请稍后重试或手动填写标题';
      return;
    }
    form.title = res.title;
    titleFromAi.value = true;
    suggestCount.value += 1;
  } catch (e: any) {
    error.value = e?.message || 'AI 生成标题失败，请手动填写';
  } finally {
    suggesting.value = false;
  }
}

/** 用户手动改标题后，就不再认为标题是「AI 原样产物」 */
function onTitleEdited() {
  if (titleFromAi.value) titleFromAi.value = false;
}

/** 打开时把 initial 回填进去；关闭时清空错误提示 */
watch(
  () => props.visible,
  (open) => {
    if (!open) {
      error.value = '';
      return;
    }
    // 默认空白；有草稿时只展示“恢复草稿”提示
    applyInitial({});
    pendingDraft.value = hasDraftContent(props.initial) ? { ...props.initial } : null;
  },
  { immediate: true }
);

/**
 * 草稿是异步拉取的（父页先 showXxx=true，再 fetchMyForumDraft），
 * 只监听 visible 会漏掉「后到的 initial」——用户就会以为草稿没保存成功（2026-11-03 第 3 轮修复）。
 * 回填条件：弹窗打开 且 表单仍为空，避免覆盖用户正在输入的内容。
 */
watch(
  () => props.initial,
  (init) => {
    if (!props.visible || !init) return;
    if (!isFormEmpty()) return;
    // 异步到达的草稿：不再自动回填，只标记为可恢复
    if (hasDraftContent(init)) pendingDraft.value = { ...init };
  }
);

const attachHint = `支持 doc / docx / xlsx / pdf / png / jpg，文档单个不超过 20 MB、图片不超过 5 MB，最多 ${props.maxAttachments} 个`;

function close() {
  emit('update:visible', false);
}

function pickFile() {
  if (!fileInput.value) {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.accept = '.doc,.docx,.pdf,.xls,.xlsx,.ppt,.pptx,.txt,.csv,.zip,.rar,.7z,image/png,image/jpeg,image/gif,image/webp';
    input.addEventListener('change', () => addFiles(Array.from(input.files || [])));
    fileInput.value = input;
  }
  fileInput.value.click();
}

function onDrop(event: DragEvent) {
  addFiles(Array.from(event.dataTransfer?.files || []));
}

function removeAttachment(index: number) {
  form.attachments.splice(index, 1);
}

async function addFiles(files: File[]) {
  if (!files.length) return;
  error.value = '';
  if (form.attachments.length + files.length > props.maxAttachments) {
    error.value = `最多 ${props.maxAttachments} 个附件`;
    return;
  }
  for (const file of files) {
    if (isImageFile(file.name) && file.size > MAX_IMAGE_SIZE) {
      error.value = `${file.name} 超过 5MB`;
      return;
    }
    if (isDocFile(file.name) && file.size > MAX_DOC_SIZE) {
      error.value = `${file.name} 超过 20MB`;
      return;
    }
    if (!isImageFile(file.name) && !isDocFile(file.name)) {
      error.value = `${file.name} 格式不支持`;
      return;
    }
  }

  uploading.value = true;
  try {
    for (const file of files) {
      form.attachments.push(isImageFile(file.name) ? await uploadForumImage(file) : await uploadForumFile(file));
    }
  } catch (err: any) {
    error.value = err?.response?.data?.detail || err?.message || '上传失败';
  } finally {
    uploading.value = false;
  }
}

function toPayload(): PostDraft {
  return {
    title: form.title.trim(),
    content: form.content.trim(),
    contentFormat: 'HTML',
    attachments: [...form.attachments],
    visibility: form.visibility,
    visibleClasses: form.visibility === 'CLASSES' ? [...form.visibleClasses] : [],
    isTop: props.canPin ? form.isTop : false,
    aiTitleEnabled: form.aiTitleEnabled,
    titleFromAi: titleFromAi.value
  };
}

function validate(): boolean {
  const payload = toPayload();
  // 与三端既定规则一致：标题 / 正文 / 附件 任一即可，三者全空才拒绝。
  // 富文本正文要按「去标签后的可见文字」判空，否则 <p><br></p> 会被当成有内容。
  const hasText = stripHtml(payload.content).length > 0;
  if (!payload.title && !hasText && !payload.attachments.length) {
    error.value = '标题、正文、附件至少填写一项';
    return false;
  }
  if (payload.visibility === 'CLASSES' && !payload.visibleClasses.length) {
    error.value = '请选择至少一个班级';
    return false;
  }
  return true;
}

function onSubmit() {
  if (!validate()) return;
  emit('submit', toPayload());
}

function onSaveDraft() {
  const payload = toPayload();
  if (!payload.title && !stripHtml(payload.content) && !payload.attachments.length) {
    error.value = '空草稿无需保存';
    return;
  }
  emit('save-draft', payload);
}
</script>

<style scoped>
.pc-mask {
  position: fixed;
  inset: 0;
  background: rgba(12, 26, 44, 0.38);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}
.pc-modal {
  width: 600px;
  max-width: 92vw;
  max-height: 86vh;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 24px 60px rgba(12, 26, 44, 0.22);
  display: flex;
  flex-direction: column;
}
.pc-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px 0;
}
.pc-hd h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #17233a;
}
.pc-x {
  border: 0;
  background: transparent;
  color: #8c99ac;
  font-size: 16px;
  width: 26px;
  height: 26px;
  border-radius: 6px;
  cursor: pointer;
}
.pc-x:hover {
  background: #eff2f7;
  color: #17233a;
}
.pc-bd {
  padding: 14px 18px;
  overflow-y: auto;
}
.pc-ft {
  display: flex;
  justify-content: flex-end;
  gap: 9px;
  padding: 12px 18px;
  border-top: 1px solid #f1f4f9;
}
.f-row {
  margin-bottom: 13px;
}
.f-row label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #5b6b84;
  margin-bottom: 6px;
}
.f-row label .req {
  color: #e23b2e;
}

/* ===== AI 标题（v4 2026-11-04）===== */
.title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.title-row .f-input {
  flex: 1 1 auto;
  min-width: 0;
}
.ai-suggest-btn {
  flex: 0 0 auto;
  height: 32px;
  padding: 0 12px;
  border: 1px solid #c7d7ff;
  border-radius: 7px;
  background: #f2f7ff;
  color: #2563eb;
  font-size: 12.5px;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
}
.ai-suggest-btn:hover:not(:disabled) {
  background: #e6efff;
}
.ai-suggest-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.ai-switch-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 7px;
  flex-wrap: wrap;
}
.ai-switch {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  color: #33415c;
  cursor: pointer;
  margin-bottom: 0;
}
.ai-switch input {
  width: 14px;
  height: 14px;
  accent-color: #2563eb;
  cursor: pointer;
}
.ai-switch-tip {
  font-size: 11.5px;
  color: #8a94ad;
}
.ai-ok-tip {
  margin: 6px 0 0;
  font-size: 11.5px;
  color: #1a7f37;
}
.f-input {
  width: 100%;
  height: 32px;
  border: 1px solid #e6ebf3;
  border-radius: 7px;
  padding: 0 10px;
  font-size: 12.5px;
  font-family: inherit;
  color: #17233a;
  outline: 0;
  transition: all 0.15s;
  box-sizing: border-box;
}
.f-input:focus {
  border-color: #123b63;
  box-shadow: 0 0 0 3px rgba(18, 59, 99, 0.07);
}
.editor {
  border: 1px solid #e6ebf3;
  border-radius: 8px;
  overflow: hidden;
}
.editor:focus-within {
  border-color: #123b63;
  box-shadow: 0 0 0 3px rgba(18, 59, 99, 0.07);
}
.editor-tools {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 8px;
  border-bottom: 1px solid #f1f4f9;
  background: #fafbfd;
}
.editor-tools button {
  width: 26px;
  height: 24px;
  border: 0;
  background: transparent;
  border-radius: 5px;
  color: #5b6b84;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.editor-tools button:hover {
  background: #edf2f8;
  color: #123b63;
}
.editor-tools button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.editor-tools .sep {
  width: 1px;
  height: 14px;
  background: #e6ebf3;
  margin: 0 4px;
}
.editor-tools .cnt {
  margin-left: auto;
  font-size: 11px;
  color: #8c99ac;
}
.editor textarea {
  border: 0;
  outline: 0;
  width: 100%;
  min-height: 120px;
  padding: 10px 11px;
  font-size: 13px;
  font-family: inherit;
  line-height: 1.75;
  color: #17233a;
  resize: vertical;
  background: #fff;
  box-sizing: border-box;
}
.dropzone {
  border: 1.5px dashed #c9d6e4;
  border-radius: 9px;
  padding: 16px;
  text-align: center;
  color: #8c99ac;
  font-size: 12px;
  cursor: pointer;
  background: #fafcfe;
  transition: all 0.15s;
}
.dropzone:hover,
.dropzone.busy {
  border-color: #9fb9d4;
  background: #f4f8fc;
}
.dropzone .dz-ic {
  color: #8fa8c4;
  margin-bottom: 6px;
}
.dropzone b {
  color: #3e6e9e;
}
.dropzone small {
  display: block;
  margin-top: 5px;
  font-size: 10.5px;
  color: #a9b5c6;
}
.pc-files {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.pc-file {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #5b6b84;
  background: #f3f6fa;
  border: 1px solid #e9eef6;
  border-radius: 4px;
  padding: 2px 6px;
  max-width: 100%;
}
.pc-file small {
  color: #a9b5c6;
}
.pc-file-x {
  border: 0;
  background: transparent;
  color: #8c99ac;
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
}
.pc-split {
  display: flex;
  gap: 22px;
  flex-wrap: wrap;
}
.pc-vi {
  flex: 1;
  min-width: 200px;
}
.radio-pills {
  display: flex;
  gap: 8px;
}
.radio-pills .rp {
  border: 1px solid #e6ebf3;
  border-radius: 7px;
  padding: 6px 12px;
  font-size: 12.5px;
  color: #5b6b84;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  background: #fff;
  transition: all 0.15s;
}
.radio-pills .rp.on {
  border-color: #123b63;
  color: #123b63;
  background: #f2f7fc;
  font-weight: 500;
}
.pc-classes {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 9px;
}
.pc-tip {
  font-size: 12px;
  color: #a9b5c6;
}
.chk-row {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12.5px;
  color: #5b6b84;
  cursor: pointer;
}
.chk-row input {
  width: 14px;
  height: 14px;
  accent-color: #123b63;
  cursor: pointer;
}
.chk-row small {
  color: #8c99ac;
}
.pc-error {
  margin: 4px 0 0;
  color: #c34a34;
  font-size: 12px;
}
.btn {
  height: 30px;
  padding: 0 13px;
  border-radius: 7px;
  border: 1px solid #e6ebf3;
  background: #fff;
  color: #5b6b84;
  font-size: 12.5px;
  display: inline-flex;
  align-items: center;
  cursor: pointer;
}
.btn:hover {
  border-color: #bfd0e4;
  color: #123b63;
}
.btn-sm {
  height: 30px;
  padding: 0 14px;
  font-size: 12.5px;
}
.btn-accent {
  background: #e23b2e;
  border-color: #e23b2e;
  color: #fff;
}
.btn-accent:hover {
  background: #cb2f23;
  border-color: #cb2f23;
  color: #fff;
}
.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
/* 草稿手动恢复条（2026-11-07） */
.draft-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #fff8e6;
  border: 1px solid #f5d58a;
  color: #8a5a00;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
  margin-bottom: 12px;
}
.draft-restore {
  border: none;
  background: #b45309;
  color: #fff;
  border-radius: 6px;
  padding: 3px 10px;
  cursor: pointer;
}
.draft-ignore {
  border: none;
  background: transparent;
  color: #8a5a00;
  cursor: pointer;
  text-decoration: underline;
}
</style>
