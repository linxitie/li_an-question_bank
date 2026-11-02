<template>
  <Teleport to="body">
    <div v-if="visible" class="pc-mask" @click.self="close">
      <div class="pc-modal">
        <div class="pc-hd">
          <h3>{{ title }}</h3>
          <button class="pc-x" type="button" title="关闭" @click="close">×</button>
        </div>

        <div class="pc-bd">
          <div class="f-row">
            <label>标题 <span class="req">*</span></label>
            <input
              v-model="form.title"
              class="f-input"
              maxlength="200"
              placeholder="给帖子起一个清晰的标题，例如：2024 公专真题变化分析"
            />
          </div>

          <div class="f-row">
            <label>正文 <span class="req">*</span></label>
            <div class="editor">
              <div class="editor-tools">
                <button type="button" title="加粗" @click="wrap('**')"><b>B</b></button>
                <button type="button" title="斜体" @click="wrap('*')"><i>I</i></button>
                <button type="button" title="下划线" @click="wrap('__')"><u>U</u></button>
                <span class="sep"></span>
                <button type="button" title="无序列表" @click="prefix('- ')">•≡</button>
                <button type="button" title="有序列表" @click="prefixNumbered()">1≡</button>
                <button type="button" title="引用" @click="prefix('> ')">❝</button>
                <span class="sep"></span>
                <button type="button" title="@同学" @click="insert('@')">@</button>
                <button type="button" title="插入图片" :disabled="uploading" @click="pickImage">🖼</button>
                <button type="button" title="插入链接" @click="insertLink">🔗</button>
                <span class="cnt">{{ form.content.length }} / {{ maxContent }}</span>
              </div>
              <textarea
                ref="bodyRef"
                v-model="form.content"
                :maxlength="maxContent"
                placeholder="正文内容，支持 @ 同学、插入图片与附件。请避免发布与备考无关的内容。"
              ></textarea>
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
                <span v-if="!classes.length" class="pc-tip">当前账号没有可选班级</span>
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
import { reactive, ref, watch } from 'vue';

import { fileIcon, formatFileSize, isDocFile, isImageFile, MAX_DOC_SIZE, uploadForumFile } from './fileUtils';
import {
  MAX_IMAGE_SIZE,
  uploadForumImage,
  type ForumImageAttachment
} from './imageUtils';

export interface PostDraft {
  title: string;
  content: string;
  attachments: ForumImageAttachment[];
  visibility: 'ALL' | 'CLASSES';
  visibleClasses: string[];
  isTop: boolean;
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
  attachments: [],
  visibility: 'ALL',
  visibleClasses: [],
  isTop: false
});

const bodyRef = ref<HTMLTextAreaElement | null>(null);
const uploading = ref(false);
const error = ref('');
const imageInput = ref<HTMLInputElement | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);

/** 打开时把 initial 回填进去；关闭时清空错误提示 */
watch(
  () => props.visible,
  (open) => {
    if (!open) {
      error.value = '';
      return;
    }
    const init = props.initial || {};
    form.title = init.title ?? '';
    form.content = init.content ?? '';
    form.attachments = [...(init.attachments ?? [])];
    form.visibility = init.visibility === 'CLASSES' ? 'CLASSES' : 'ALL';
    form.visibleClasses = [...(init.visibleClasses ?? [])];
    form.isTop = Boolean(init.isTop);
  },
  { immediate: true }
);

const attachHint = `支持 doc / docx / xlsx / pdf / png / jpg，文档单个不超过 20 MB、图片不超过 5 MB，最多 ${props.maxAttachments} 个`;

function close() {
  emit('update:visible', false);
}

function focusBody() {
  bodyRef.value?.focus();
}

/** 在光标处包裹选中文本；无选区时插入成对标记并把光标放中间 */
function wrap(marker: string) {
  const el = bodyRef.value;
  if (!el) return;
  const start = el.selectionStart ?? 0;
  const end = el.selectionEnd ?? 0;
  const selected = form.content.slice(start, end);
  form.content = form.content.slice(0, start) + marker + selected + marker + form.content.slice(end);
  requestAnimationFrame(() => {
    el.focus();
    const pos = start + marker.length + selected.length;
    el.setSelectionRange(pos, pos);
  });
}

function insert(text: string) {
  const el = bodyRef.value;
  if (!el) {
    form.content += text;
    return;
  }
  const start = el.selectionStart ?? form.content.length;
  const end = el.selectionEnd ?? form.content.length;
  form.content = form.content.slice(0, start) + text + form.content.slice(end);
  requestAnimationFrame(() => {
    el.focus();
    const pos = start + text.length;
    el.setSelectionRange(pos, pos);
  });
}

/** 给选区每一行加前缀（列表 / 引用） */
function prefix(marker: string) {
  const el = bodyRef.value;
  if (!el) return;
  const start = el.selectionStart ?? 0;
  const end = el.selectionEnd ?? 0;
  const block = form.content.slice(start, end) || '';
  const marked = block
    .split('\n')
    .map((line) => (line ? marker + line : line))
    .join('\n');
  if (!block) {
    insert(marker);
    return;
  }
  form.content = form.content.slice(0, start) + marked + form.content.slice(end);
}

function prefixNumbered() {
  const el = bodyRef.value;
  if (!el) return;
  const start = el.selectionStart ?? 0;
  const end = el.selectionEnd ?? 0;
  const block = form.content.slice(start, end) || '';
  if (!block) {
    insert('1. ');
    return;
  }
  const marked = block
    .split('\n')
    .map((line, i) => (line ? `${i + 1}. ${line}` : line))
    .join('\n');
  form.content = form.content.slice(0, start) + marked + form.content.slice(end);
}

function insertLink() {
  const url = window.prompt('请输入链接地址', 'https://');
  if (!url) return;
  insert(`[链接](${url})`);
}

function pickImage() {
  if (!imageInput.value) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/png,image/jpeg,image/gif,image/webp';
    input.multiple = true;
    input.addEventListener('change', () => addFiles(Array.from(input.files || [])));
    imageInput.value = input;
  }
  imageInput.value.click();
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
    attachments: [...form.attachments],
    visibility: form.visibility,
    visibleClasses: form.visibility === 'CLASSES' ? [...form.visibleClasses] : [],
    isTop: props.canPin ? form.isTop : false
  };
}

function validate(): boolean {
  const payload = toPayload();
  // 与三端既定规则一致：标题 / 正文 / 附件 任一即可，三者全空才拒绝
  if (!payload.title && !payload.content && !payload.attachments.length) {
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
  if (!payload.title && !payload.content && !payload.attachments.length) {
    error.value = '空草稿无需保存';
    return;
  }
  emit('save-draft', payload);
}

defineExpose({ focusBody });
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
</style>
