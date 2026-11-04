<template>
  <div class="ocr-mask" @click.self="$emit('close')">
    <div class="ocr-panel" role="dialog" aria-label="图片 OCR 审阅">
      <header class="ocr-head">
        <div>
          <strong>图片 OCR 审阅</strong>
          <span class="ocr-sub">识别结果只替换原图位置，前后文字不动</span>
        </div>
        <button class="ocr-x" type="button" @click="$emit('close')" aria-label="关闭">×</button>
      </header>

      <div v-if="groupId" class="ocr-tabs">
        <button type="button" :class="{ active: target === 'question' }" @click="switchTarget('question')">题目图片</button>
        <button type="button" :class="{ active: target === 'group' }" @click="switchTarget('group')">题组材料图片</button>
      </div>

      <div class="ocr-body">
        <div v-if="loading" class="ocr-state">正在识别图片…大图首次识别可能需要几十秒</div>
        <div v-else-if="error" class="ocr-state error">
          {{ error }}
          <button type="button" class="ocr-retry" @click="load">重试</button>
        </div>
        <div v-else-if="!items.length" class="ocr-state">当前范围没有内嵌图片，无需 OCR。</div>

        <div v-for="item in items" :key="item.key" class="ocr-item">
          <div class="ocr-thumb">
            <img :src="item.src" :alt="item.location_label + ' 原图'" loading="lazy" />
            <span class="ocr-dim">{{ item.width }}×{{ item.height }}</span>
          </div>
          <div class="ocr-info">
            <div class="ocr-meta">
              <span class="ocr-loc">{{ item.location_label }}</span>
              <span v-if="item.suggest_keep_image" class="ocr-tag warn">图形/大图，建议保留</span>
              <span v-if="item.cached" class="ocr-tag">缓存</span>
              <span v-if="item.error" class="ocr-tag danger">{{ item.error }}</span>
            </div>
            <textarea v-model="item.text" rows="3" placeholder="识别文字，可手工修正"></textarea>
            <label class="ocr-choice">
              <input type="checkbox" v-model="item.replace" :disabled="!item.text.trim()" />
              用这段文字替换原图（保留原图文件）
            </label>
          </div>
        </div>
      </div>

      <footer class="ocr-foot">
        <span class="ocr-count">共 {{ items.length }} 张，已选 {{ selectedCount }} 张</span>
        <button type="button" class="ocr-btn" @click="$emit('close')">取消</button>
        <button type="button" class="ocr-btn primary" :disabled="applying || !selectedCount" @click="apply">
          {{ applying ? '替换中…' : '应用替换' }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';

const props = defineProps({
  questionId: { type: Number, default: 0 },
  groupId: { type: Number, default: 0 },
});
const emit = defineEmits(['close', 'applied']);

const target = ref('question');
const items = ref([]);
const loading = ref(false);
const applying = ref(false);
const error = ref('');

const selectedCount = computed(function () {
  return items.value.filter(function (item) { return item.replace && item.text.trim(); }).length;
});

function apiFetch(url, options) {
  const auth = window.__VTJ_AUTH__;
  if (!auth || !auth.apiFetch) return Promise.reject(new Error('登录态失效，请重新登录'));
  return auth.apiFetch(url, options);
}

async function load() {
  const id = target.value === 'group' ? props.groupId : props.questionId;
  if (!id) {
    items.value = [];
    return;
  }
  loading.value = true;
  error.value = '';
  try {
    const base = target.value === 'group'
      ? '/api/questions/group/' + id
      : '/api/questions/' + id;
    const res = await apiFetch(base + '/ocr-candidates?run_ocr=true');
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'OCR 识别失败');
    items.value = (data.items || []).map(function (item) {
      return Object.assign({}, item, {
        text: item.text || '',
        replace: !!(item.text && item.text.trim() && !item.suggest_keep_image),
      });
    });
  } catch (e) {
    error.value = e && e.message ? e.message : 'OCR 识别失败';
  } finally {
    loading.value = false;
  }
}

function switchTarget(next) {
  if (target.value === next) return;
  target.value = next;
  items.value = [];
  load();
}

async function apply() {
  if (!selectedCount.value) return;
  applying.value = true;
  try {
    const id = target.value === 'group' ? props.groupId : props.questionId;
    const base = target.value === 'group'
      ? '/api/questions/group/' + id
      : '/api/questions/' + id;
    const payload = {
      items: items.value
        .filter(function (item) { return item.replace && item.text.trim(); })
        .map(function (item) {
          return { location: item.location, index: item.index, text: item.text, replace: true };
        }),
    };
    const res = await apiFetch(base + '/ocr-apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || '替换失败');
    emit('applied', data);
    emit('close');
  } catch (e) {
    error.value = e && e.message ? e.message : '替换失败';
  } finally {
    applying.value = false;
  }
}

onMounted(load);
</script>

<style scoped>
.ocr-mask {
  position: fixed; inset: 0; z-index: 3000; background: rgba(15, 23, 42, 0.55);
  display: flex; align-items: center; justify-content: center; padding: 24px;
}
.ocr-panel {
  width: min(1040px, 96vw); max-height: 90vh; display: flex; flex-direction: column;
  background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 24px 70px rgba(15, 23, 42, 0.28);
}
.ocr-head {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
  padding: 16px 20px; border-bottom: 1px solid #e2e8f0;
}
.ocr-head strong { font-size: 16px; color: #1a3c6d; }
.ocr-sub { display: block; margin-top: 4px; font-size: 12px; color: #64748b; }
.ocr-x { border: 0; background: transparent; font-size: 24px; line-height: 1; color: #64748b; cursor: pointer; }
.ocr-tabs { display: flex; gap: 8px; padding: 10px 20px 0; border-bottom: 1px solid #e2e8f0; }
.ocr-tabs button {
  border: 0; background: transparent; padding: 8px 12px; cursor: pointer;
  color: #64748b; border-bottom: 2px solid transparent;
}
.ocr-tabs button.active { color: #1a3c6d; font-weight: 600; border-bottom-color: #2563eb; }
.ocr-body { flex: 1; overflow: auto; padding: 16px 20px; background: #f7f9fc; }
.ocr-state { padding: 32px 12px; text-align: center; color: #64748b; }
.ocr-state.error { color: #b91c1c; }
.ocr-retry { margin-left: 8px; border: 1px solid #cbd5e1; background: #fff; border-radius: 6px; padding: 3px 10px; cursor: pointer; }
.ocr-item {
  display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 16px;
  padding: 14px; margin-bottom: 12px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;
}
.ocr-thumb { display: flex; flex-direction: column; gap: 6px; align-items: center; }
.ocr-thumb img { max-width: 100%; max-height: 180px; object-fit: contain; border: 1px solid #eef2f7; border-radius: 6px; }
.ocr-dim { font-size: 12px; color: #94a3b8; }
.ocr-meta { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 8px; }
.ocr-loc { font-weight: 600; color: #1a3c6d; }
.ocr-tag { padding: 1px 8px; border-radius: 999px; background: #eef2f7; color: #475569; font-size: 12px; }
.ocr-tag.warn { background: #fef3c7; color: #92400e; }
.ocr-tag.danger { background: #fee2e2; color: #991b1b; }
.ocr-info textarea {
  width: 100%; box-sizing: border-box; resize: vertical; padding: 9px 10px;
  border: 1px solid #cbd5e1; border-radius: 6px; font: inherit; line-height: 1.6;
}
.ocr-info textarea:focus-visible { outline: 2px solid #2563eb; outline-offset: 2px; }
.ocr-choice { display: flex; gap: 6px; align-items: center; margin-top: 8px; font-size: 13px; color: #334155; }
.ocr-foot {
  display: flex; align-items: center; gap: 10px; padding: 12px 20px; border-top: 1px solid #e2e8f0;
}
.ocr-count { margin-right: auto; color: #64748b; font-size: 13px; }
.ocr-btn { border: 1px solid #cbd5e1; background: #fff; border-radius: 6px; padding: 8px 16px; cursor: pointer; }
.ocr-btn.primary { border-color: #2563eb; background: #2563eb; color: #fff; }
.ocr-btn:disabled { opacity: 0.5; cursor: not-allowed; }
@media (max-width: 720px) {
  .ocr-item { grid-template-columns: 1fr; }
}
</style>
