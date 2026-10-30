<template>
  <div class="docx-mask" @click.self="emit('close')">
    <div class="docx-card">
      <div class="docx-head">
        <span class="docx-title">{{ name }}</span>
        <button class="docx-close" @click="emit('close')">✕</button>
      </div>
      <div v-if="loading" class="docx-tip">正在渲染文档…</div>
      <div v-else-if="error" class="docx-tip docx-err">{{ error }}</div>
      <div ref="host" class="docx-body"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';

const props = defineProps<{ url: string; name: string }>();
const emit = defineEmits<{ (e: 'close'): void }>();

const host = ref<HTMLElement | null>(null);
const loading = ref(true);
const error = ref('');

onMounted(async () => {
  try {
    // 动态引入，避免首屏加载 200KB 依赖
    const { renderAsync } = await import('docx-preview');
    const res = await fetch(props.url);
    if (!res.ok) throw new Error(`下载失败（HTTP ${res.status}）`);
    const buf = await res.arrayBuffer();
    if (!host.value) return;
    await renderAsync(buf, host.value, undefined, {
      className: 'docx',
      inWrapper: true,
      ignoreWidth: false,
      breakPages: true,
    });
  } catch (e: any) {
    error.value = (e && e.message) || '文档渲染失败，请下载后用 WPS 打开';
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.docx-mask {
  position: fixed; inset: 0; z-index: 2000;
  background: rgba(8, 12, 24, .55);
  display: flex; align-items: center; justify-content: center; padding: 24px;
}
.docx-card {
  width: min(900px, 94vw); max-height: 88vh;
  background: #fff; border-radius: 14px; display: flex; flex-direction: column;
  overflow: hidden;
}
.docx-head {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 16px; border-bottom: 1px solid #eef1f6;
}
.docx-title { flex: 1 1 auto; font-weight: 600; color: #1a2b5f; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.docx-close { border: none; background: none; font-size: 18px; color: #8a94ad; cursor: pointer; }
.docx-body { flex: 1 1 auto; overflow: auto; padding: 16px; background: #f7f9fc; }
.docx-tip { padding: 40px; text-align: center; color: #6b7896; font-size: 14px; }
.docx-err { color: #c41e3a; }
</style>
