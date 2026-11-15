<template>
  <div class="ice-wrap">
    <div
      ref="editorRef"
      class="ice-editor"
      contenteditable="true"
      :data-placeholder="placeholder"
      @input="onInput"
      @keydown="onKeydown"
      @paste.prevent="onPaste"
      @blur="saveRange"></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';

const props = withDefaults(
  defineProps<{ modelValue: string; placeholder?: string; maxlength?: number }>(),
  { placeholder: '', maxlength: 2000 }
);
const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void;
  (e: 'submit'): void;
}>();

const editorRef = ref<HTMLElement | null>(null);
let savedRange: Range | null = null;

function serializeNode(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent || '';
  if (node.nodeType !== Node.ELEMENT_NODE) return '';
  const el = node as HTMLElement;
  if (el.dataset && el.dataset.token) return el.dataset.token;
  if (el.tagName === 'BR') return '\n';
  if (el.tagName === 'IMG') return (el as HTMLImageElement).alt || '';
  const inner = Array.from(el.childNodes).map(serializeNode).join('');
  return el.tagName === 'DIV' || el.tagName === 'P' ? '\n' + inner : inner;
}

function serialize(): string {
  const el = editorRef.value;
  if (!el) return '';
  const raw = Array.from(el.childNodes).map(serializeNode).join('');
  return raw.replace(/^\n+/, '').slice(0, props.maxlength);
}

function onInput() {
  emit('update:modelValue', serialize());
}

function onPaste() {
  // 只接受纯文本，避免把外部 HTML 带进正文
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    emit('submit');
  }
}

function saveRange() {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || !editorRef.value) return;
  const range = sel.getRangeAt(0);
  if (editorRef.value.contains(range.commonAncestorContainer)) savedRange = range.cloneRange();
}

function placeCaret() {
  const el = editorRef.value;
  if (!el) return;
  el.focus();
  const sel = window.getSelection();
  if (!sel) return;
  if (savedRange && el.contains(savedRange.commonAncestorContainer)) {
    sel.removeAllRanges();
    sel.addRange(savedRange);
  } else {
    const range = document.createRange();
    range.selectNodeContents(el);
    range.collapse(false);
    sel.removeAllRanges();
    sel.addRange(range);
  }
}

function insertText(text: string) {
  placeCaret();
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return;
  const range = sel.getRangeAt(0);
  range.deleteContents();
  const node = document.createTextNode(text);
  range.insertNode(node);
  range.setStartAfter(node);
  range.collapse(true);
  sel.removeAllRanges();
  sel.addRange(range);
  savedRange = range.cloneRange();
  onInput();
}

const IMAGE_URL_RE = /\.(png|jpe?g|gif|webp|bmp|svg)(\?|$)/i;

/** token → 可编辑节点：回填外部内容（例如从底部输入框切到全屏输入）时复用 */
function buildTokenNode(kind: string, payload: string): HTMLElement {
  const span = document.createElement('span');
  span.contentEditable = 'false';
  span.className = 'ice-attach';
  span.dataset.token = '[[' + kind + ':' + payload + ']]';
  const sep = payload.lastIndexOf('|');
  const url = sep >= 0 ? payload.slice(0, sep) : payload;
  const name = sep >= 0 ? payload.slice(sep + 1) : kind === 'sticker' ? '表情包' : '附件';
  if (kind === 'sticker' || IMAGE_URL_RE.test(url)) {
    const img = document.createElement('img');
    img.src = url;
    img.alt = name;
    span.appendChild(img);
  } else {
    span.textContent = '📎 ' + name;
  }
  return span;
}

/** 把 modelValue（含 [[file:]] / [[sticker:]] token）按原顺序还原成 DOM */
function renderValue(value: string) {
  const el = editorRef.value;
  if (!el) return;
  el.innerHTML = '';
  const frag = document.createDocumentFragment();
  const pushText = (text: string) => {
    if (!text) return;
    text.split('\n').forEach((part, index) => {
      if (index > 0) frag.appendChild(document.createElement('br'));
      if (part) frag.appendChild(document.createTextNode(part));
    });
  };
  let cursor = 0;
  for (const match of value.matchAll(/\[\[(sticker|file):([^\]]*?)\]\]/g)) {
    const index = match.index ?? 0;
    if (index > cursor) pushText(value.slice(cursor, index));
    frag.appendChild(buildTokenNode(match[1], match[2]));
    cursor = index + match[0].length;
  }
  pushText(value.slice(cursor));
  el.appendChild(frag);
}

function insertAttachment(file: { url: string; name?: string; type?: string }) {
  const el = editorRef.value;
  if (!el) return;
  placeCaret();
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0) return;
  const range = sel.getRangeAt(0);
  const name = file.name || '附件';
  const span = buildTokenNode('file', file.url + '|' + name);
  range.deleteContents();
  range.insertNode(span);
  const space = document.createTextNode('\u00a0');
  span.after(space);
  const after = document.createRange();
  after.setStartAfter(space);
  after.collapse(true);
  sel.removeAllRanges();
  sel.addRange(after);
  savedRange = after.cloneRange();
  onInput();
}

watch(
  () => props.modelValue,
  (val) => {
    const el = editorRef.value;
    if (!el) return;
    const next = String(val ?? '');
    // 自己输入产生的值已与 DOM 一致，回灌会打断光标；只有外部变更（如全屏弹窗挂载）才重绘
    if (next === serialize()) return;
    renderValue(next);
  }
);

onMounted(() => {
  document.addEventListener('selectionchange', saveRange);
  if (props.modelValue) renderValue(props.modelValue);
});

defineExpose({ insertText, insertAttachment, focus: () => editorRef.value?.focus() });
</script>

<style scoped>
.ice-wrap { flex: 1; min-width: 0; position: relative; order: 3; }
.ice-editor {
  min-height: 50px;
  max-height: 180px;
  overflow-y: auto;
  border: 0;
  outline: none;
  padding: 6px 40px 6px 10px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.ice-editor:empty::before {
  content: attr(data-placeholder);
  color: #a0a8b8;
  pointer-events: none;
}
.ice-editor :deep(.ice-attach) {
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
  margin: 0 4px;
  padding: 2px 6px;
  border: 1px solid #e6ebf3;
  border-radius: 8px;
  background: #f8fafc;
  font-size: 12px;
}
.ice-editor :deep(.ice-attach img) {
  max-width: 90px;
  max-height: 60px;
  border-radius: 6px;
  object-fit: cover;
}
</style>
