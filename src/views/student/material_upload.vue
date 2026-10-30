<template>
  <div class="mu-page">
    <header class="mu-head">
      <h1>上传备考资料</h1>
      <p class="mu-sub">
        支持 xlsx / csv，单文件 ≤ 5MB、单次 ≤ 200 行。提交后进入<b>待审队列</b>，管理员通过后才公开展示。
      </p>
    </header>

    <section class="mu-quota">
      <div class="mu-quota-item">
        <span class="mu-quota-num">{{ quota.todayLeft }}</span>
        <span class="mu-quota-lab">今日剩余次数</span>
      </div>
      <div class="mu-quota-item">
        <span class="mu-quota-num">{{ quota.libLeft }}</span>
        <span class="mu-quota-lab">资料库剩余额度</span>
      </div>
      <div class="mu-quota-item mu-quota-tip">
        表格表头需含「正面」「背面」；可选「分类」「考点」「难度」。分类留空会自动判定。
      </div>
    </section>

    <section class="mu-form">
      <div class="mu-row">
        <label class="mu-lab">科目</label>
        <div class="mu-seg">
          <button
            v-for="s in SUBJECTS" :key="s.value"
            class="mu-seg-btn" :class="{ 'is-on': subject === s.value }"
            @click="subject = s.value"
          >{{ s.label }}</button>
        </div>
      </div>

      <div class="mu-row">
        <label class="mu-lab">文件</label>
        <label class="mu-drop" :class="{ 'is-over': dragging }"
               @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false"
               @drop.prevent="onDrop">
          <input ref="fileInput" type="file" accept=".xlsx,.csv" hidden @change="onPick" />
          <template v-if="!file">
            <span class="mu-drop-main">点击选择，或把表格拖到这里</span>
            <span class="mu-drop-sub">.xlsx / .csv，≤ 5MB</span>
          </template>
          <template v-else>
            <span class="mu-drop-main">{{ file.name }}</span>
            <span class="mu-drop-sub">{{ (file.size / 1024).toFixed(0) }} KB ·
              点击可更换</span>
          </template>
        </label>
      </div>

      <div class="mu-actions">
        <button class="mu-btn" :disabled="!file || loading" @click="submit">
          {{ loading ? '上传中…' : '提交审核' }}
        </button>
        <span v-if="error" class="mu-err">{{ error }}</span>
      </div>
    </section>

    <section v-if="result" class="mu-result">
      <div class="mu-result-head">
        <b>已提交 {{ result.created }} 张</b>
        <span class="mu-pending">待审</span>
        <span class="mu-result-note">{{ result.note }}</span>
      </div>

      <div v-if="result.skippedCount" class="mu-skip">
        <p class="mu-skip-title">跳过 {{ result.skippedCount }} 行</p>
        <ul class="mu-skip-list">
          <li v-for="(s, i) in result.skipped" :key="i">
            第 {{ s.row }} 行：{{ reasonText(s.reason) }}
          </li>
        </ul>
      </div>

      <div v-if="result.warnings.length" class="mu-warn">
        <p class="mu-skip-title">提醒 {{ result.warnings.length }} 条</p>
        <ul class="mu-skip-list">
          <li v-for="(w, i) in result.warnings" :key="i">
            第 {{ w.row }} 行 {{ w.column }}：{{ w.message }}
          </li>
        </ul>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useRoute } from 'vue-router';
import axios from 'axios';

const SUBJECTS = [
  { value: 'xingce', label: '行测' },
  { value: 'shenlun', label: '申论' },
  { value: 'gongzhuan', label: '公安专业科目' }
];

const route = useRoute();
const demo = route.query.demo === '1';

const subject = ref('xingce');
const file = ref<File | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const dragging = ref(false);
const loading = ref(false);
const error = ref('');
const result = ref<any>(null);

const quota = reactive({ todayLeft: demo ? 5 : 5, libLeft: demo ? 482 : 500 });

function reasonText(r: string) {
  const map: Record<string, string> = {
    empty: '正面或背面为空，已跳过',
    invalid: '格式不合规（超长/重复/含不允许的标签），已跳过',
    duplicate: '与已有资料内容重复，已跳过'
  };
  return map[r] || r;
}

function onPick(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0];
  if (f) setFile(f);
}

function onDrop(e: DragEvent) {
  dragging.value = false;
  const f = e.dataTransfer?.files?.[0];
  if (f) setFile(f);
}

function setFile(f: File) {
  error.value = '';
  result.value = null;
  if (!/\.(xlsx|csv)$/i.test(f.name)) {
    error.value = '只支持 .xlsx 或 .csv';
    return;
  }
  if (f.size > 5 * 1024 * 1024) {
    error.value = '文件超过 5MB';
    return;
  }
  file.value = f;
}

async function submit() {
  if (!file.value) return;
  loading.value = true;
  error.value = '';
  if (demo) {
    // 演示态：不请求后端，直接展示接口契约的样例返回
    await new Promise((r) => setTimeout(r, 400));
    result.value = {
      created: 18,
      skippedCount: 2,
      skipped: [
        { row: 7, reason: 'empty' },
        { row: 12, reason: 'duplicate' }
      ],
      warnings: [
        { row: 9, column: '分类',
          message: '分类「方法技巧」不在本子类词表内；已按考点自动判定为「判断推理」' }
      ],
      note: '已进入待审队列，管理员审核后才会公开展示'
    };
    loading.value = false;
    return;
  }
  try {
    const fd = new FormData();
    fd.append('file', file.value);
    const { data } = await axios.post('/api/materials/my/upload', fd, {
      params: { subject: subject.value },
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    result.value = {
      created: data.created,
      skippedCount: data.skipped_count || 0,
      skipped: data.skipped || [],
      warnings: data.warnings || [],
      note: data.note || ''
    };
    quota.todayLeft = Math.max(0, quota.todayLeft - 1);
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '上传失败，请稍后再试';
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.mu-page { max-width: 980px; margin: 0 auto; padding: 26px 20px 60px; }
.mu-head h1 { font-size: 22px; margin: 0 0 6px; color: #111827; }
.mu-sub { margin: 0; font-size: 13px; color: #6b7280; }
.mu-sub b { color: #b45309; }
.mu-quota { display: flex; gap: 18px; margin: 18px 0 8px; align-items: center;
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px 16px; }
.mu-quota-item { display: flex; flex-direction: column; }
.mu-quota-num { font-size: 20px; font-weight: 700; color: #2563eb; }
.mu-quota-lab { font-size: 11.5px; color: #6b7280; }
.mu-quota-tip { font-size: 12px; color: #6b7280; margin-left: auto; max-width: 460px; }
.mu-form { background: #fff; border: 1px solid #e5e7eb; border-radius: 14px;
  padding: 16px 18px; box-shadow: 0 6px 18px rgba(23,43,77,.05); }
.mu-row { display: flex; align-items: center; gap: 14px; padding: 10px 0; }
.mu-lab { width: 56px; font-size: 13px; color: #374151; flex: none; }
.mu-seg { display: flex; gap: 8px; }
.mu-seg-btn { border: 1px solid #d8dbe6; background: #fff; color: #4b5563;
  padding: 6px 14px; border-radius: 999px; font-size: 13px; cursor: pointer; }
.mu-seg-btn.is-on { background: #2563eb; border-color: #2563eb; color: #fff; }
.mu-drop { flex: 1; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 4px; min-height: 92px; border: 1.5px dashed #cbd5e1;
  border-radius: 12px; cursor: pointer; background: #fafbff; }
.mu-drop.is-over { border-color: #2563eb; background: #eff6ff; }
.mu-drop-main { font-size: 14px; color: #111827; }
.mu-drop-sub { font-size: 12px; color: #9ca3af; }
.mu-actions { display: flex; align-items: center; gap: 12px; padding-top: 8px; }
.mu-btn { background: #2563eb; color: #fff; border: none; border-radius: 10px;
  padding: 9px 22px; font-size: 14px; cursor: pointer; }
.mu-btn:disabled { background: #c7d2fe; cursor: not-allowed; }
.mu-err { color: #dc2626; font-size: 12.5px; }
.mu-result { margin-top: 16px; background: #fff; border: 1px solid #e5e7eb;
  border-radius: 14px; padding: 14px 18px; }
.mu-result-head { display: flex; align-items: center; gap: 10px; font-size: 14px; }
.mu-pending { font-size: 11px; color: #b45309; background: #fef3c7;
  border-radius: 6px; padding: 1px 7px; }
.mu-result-note { font-size: 12px; color: #6b7280; }
.mu-skip-title { font-size: 12.5px; color: #6b7280; margin: 12px 0 4px; }
.mu-skip-list { margin: 0; padding-left: 18px; font-size: 12.5px; color: #374151; }
.mu-skip-list li { line-height: 1.8; }
.mu-warn .mu-skip-title { color: #b45309; }
</style>
