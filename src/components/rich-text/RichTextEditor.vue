<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

type WangEditorInstance = any;

const props = withDefaults(
  defineProps<{
    modelValue?: string;
    groupId?: number | null;
    placeholder?: string;
  }>(),
  {
    modelValue: '',
    groupId: null,
    placeholder: '请输入内容…'
  }
);

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const editorHost = ref<HTMLElement | null>(null);
const fallbackText = ref(props.modelValue || '');
const failed = ref(false);
const uploadHint = ref('');

let editor: WangEditorInstance | null = null;
let syncing = false;
let unmounted = false;

/** 统一空段落表示，避免 v-model 回写造成光标跳动 */
function normalize(html: string): string {
  const value = String(html || '');
  if (/^<p>(<br\s*\/?>)?<\/p>$/i.test(value) || value === '<p><br></p>') return '';
  return value;
}

function emitValue(value: string) {
  emit('update:modelValue', value);
}

function onFallbackInput() {
  emitValue(fallbackText.value);
}

/**
 * 上传题组图片：POST /api/questions/group/{groupId}/images（FormData）。
 * 不使用 base64 内嵌；没有 groupId 时直接跳过并提示。
 */
async function uploadImage(file: File): Promise<string> {
  if (!props.groupId) {
    throw new Error('当前上下文缺少题组 ID（groupId），无法上传图片');
  }

  const form = new FormData();
  form.append('file', file, file.name || 'image.png');

  const url = '/api/questions/group/' + props.groupId + '/images';
  const auth = (window as any).__VTJ_AUTH__;
  let response: Response;

  if (auth && typeof auth.apiFetch === 'function') {
    // apiFetch 自动注入 Authorization，且对 FormData 不改 Content-Type
    response = await auth.apiFetch(url, { method: 'POST', body: form });
  } else {
    const headers: Record<string, string> = {};
    if (auth && typeof auth.getJsonHeaders === 'function') {
      const jsonHeaders = auth.getJsonHeaders() || {};
      if (jsonHeaders.Authorization) headers.Authorization = jsonHeaders.Authorization;
    }
    response = await fetch(url, { method: 'POST', body: form, headers });
  }

  if (!response.ok) {
    let message = '图片上传失败（HTTP ' + response.status + '）';
    try {
      const payload = await response.json();
      if (payload && payload.detail) message = String(payload.detail);
    } catch (e) {
      // 响应不是 JSON 时保留默认提示
    }
    throw new Error(message);
  }

  const data = await response.json();
  if (!data || !data.url) throw new Error('上传接口未返回图片地址');
  return String(data.url);
}

function handleUpload(files: File[], insertImg: (url: string) => void) {
  if (!props.groupId) {
    uploadHint.value = '当前上下文缺少题组 ID，图片上传已跳过';
    // eslint-disable-next-line no-console
    console.warn('[RichTextEditor] 缺少 groupId，图片上传已跳过');
    return;
  }

  uploadHint.value = '';
  void (async () => {
    try {
      for (const file of files) {
        const imageUrl = await uploadImage(file);
        insertImg(imageUrl);
      }
    } catch (error: any) {
      const message = (error && error.message) || '图片上传失败';
      uploadHint.value = message;
      // eslint-disable-next-line no-console
      console.warn('[RichTextEditor] 图片上传失败', error);
    }
  })();
}

async function mountEditor() {
  try {
    // 动态 import：wangEditor 单独成 chunk，不进入首屏
    const module: any = await import('wangeditor');
    const Editor = module && (module.default || module);
    if (!Editor) throw new Error('wangEditor 模块加载失败');
    if (unmounted || !editorHost.value) return;

    const instance: WangEditorInstance = new Editor(editorHost.value);
    editor = instance;

    instance.config.placeholder = props.placeholder;
    instance.config.height = 180;
    // 工具栏只保留需求列表中的菜单，显式排除 video
    instance.config.menus = [
      'head',
      'bold',
      'italic',
      'underline',
      'strikeThrough',
      'list',
      'link',
      'image',
      'table',
      'undo',
      'redo'
    ];
    // 禁止 base64 内嵌与粘贴图片，统一走上传端点
    instance.config.uploadImgShowBase64 = false;
    instance.config.uploadImgMaxSize = 10 * 1024 * 1024;
    instance.config.pasteIgnoreImg = true;
    instance.config.customUploadImg = handleUpload;

    instance.config.onchange = (html: string) => {
      if (syncing) return;
      emitValue(html);
    };

    instance.create();

    if (props.modelValue) {
      syncing = true;
      instance.txt.html(props.modelValue);
      await nextTick();
      syncing = false;
    }
  } catch (error) {
    // eslint-disable-next-line no-console
    console.warn('[RichTextEditor] 编辑器加载失败，已降级为 textarea', error);
    failed.value = true;
    editor = null;
    fallbackText.value = props.modelValue || '';
  }
}

watch(
  () => props.modelValue,
  (value) => {
    const next = value || '';
    fallbackText.value = next;
    if (!editor) return;
    if (normalize(editor.txt.html()) === normalize(next)) return;
    syncing = true;
    editor.txt.html(next);
    void nextTick(() => {
      syncing = false;
    });
  }
);

onMounted(() => {
  void mountEditor();
});

onBeforeUnmount(() => {
  unmounted = true;
  if (editor && typeof editor.destroy === 'function') {
    try {
      editor.destroy();
    } catch (error) {
      // eslint-disable-next-line no-console
      console.warn('[RichTextEditor] 销毁编辑器失败', error);
    }
  }
  editor = null;
});
</script>

<template>
  <div class="rich-text-editor">
    <textarea
      v-if="failed"
      v-model="fallbackText"
      class="rte-fallback"
      :placeholder="placeholder"
      @input="onFallbackInput"
    ></textarea>
    <div v-else ref="editorHost" class="rte-host"></div>
    <div v-if="uploadHint" class="rte-hint">{{ uploadHint }}</div>
  </div>
</template>

<style scoped>
.rich-text-editor {
  width: 100%;
  box-sizing: border-box;
}

.rte-host {
  width: 100%;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  box-sizing: border-box;
  line-height: normal;
}

.rte-host :deep(.w-e-toolbar) {
  flex-wrap: wrap;
  border-bottom: 1px solid #dcdfe6;
  background: #fafafa;
}

.rte-host :deep(.w-e-text-container),
.rte-host :deep(.w-e-text) {
  min-height: 180px;
}

.rte-host :deep(img) {
  max-width: 100%;
  height: auto;
}

.rte-host :deep(table) {
  max-width: 100%;
  border-collapse: collapse;
}

.rte-host :deep(td),
.rte-host :deep(th) {
  border: 1px solid #dcdfe6;
  padding: 4px 8px;
}

.rte-fallback {
  width: 100%;
  min-height: 180px;
  padding: 8px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  box-sizing: border-box;
  font: inherit;
  line-height: 1.6;
  resize: vertical;
}

.rte-hint {
  margin-top: 6px;
  color: #e6a23c;
  font-size: 12px;
}
</style>
