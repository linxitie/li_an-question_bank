<template>
  <Teleport to="body">
    <div v-if="open" class="cxu-root" role="dialog" aria-modal="true" aria-label="xlsx 卡片智能导入">
      <div class="cxu-mask" @click="requestClose" />
      <section class="cxu-panel">
        <header class="cxu-head">
          <div>
            <h2 class="cxu-title">xlsx 卡片智能导入</h2>
            <p class="cxu-desc">
              一张表 → N 张卡片。支持 <b>.xlsx</b>（≤ 5MB、≤ 500 行），表头需能指认「正面 / 背面」；
              入库后为「未上架」，核对后再点上架。
            </p>
          </div>
          <button class="cxu-x" type="button" :disabled="busy" @click="requestClose">×</button>
        </header>

        <div class="cxu-body">
          <!-- 1. 选文件 -->
          <div class="cxu-block">
            <div class="cxu-label">1. 选择 xlsx</div>
            <div class="cxu-pick">
              <input ref="fileInput" class="cxu-file" type="file" accept=".xlsx" :disabled="busy" @change="onPick" />
              <button class="adm-btn adm-btn--line" type="button" :disabled="busy" @click="fileInput?.click()">
                {{ file ? '换一个文件' : '选择文件' }}
              </button>
              <span v-if="file" class="cxu-file-name">{{ file.name }} · {{ humanBytes(file.size) }}</span>
              <span v-else class="cxu-hint">还没选文件</span>
            </div>
            <p v-if="error" class="cxu-error">{{ error }}</p>
          </div>

          <!-- 2. 解析 / 预览 -->
          <div v-if="file" class="cxu-block">
            <div class="cxu-label">
              2. 解析预览
              <span v-if="parsing" class="cxu-badge is-busy">解析中…（已 {{ elapsed }}s）</span>
              <span v-else-if="headers.length" class="cxu-badge is-ok">
                表头 {{ headers.length }} 列 · 数据 {{ rowCount }} 行
                <template v-if="rowCount > 200">（预览只显示前 200 行）</template>
              </span>
            </div>

            <table v-if="headers.length" class="cxu-table">
              <thead>
                <tr>
                  <th class="cxu-idx">#</th>
                  <th v-for="(h, i) in headers" :key="i" :class="{ 'is-front': mapping.front === i, 'is-back': mapping.back === i }">
                    {{ h || `第${i + 1}列` }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, r) in previewRows" :key="r">
                  <td class="cxu-idx">{{ r + 1 }}</td>
                  <td v-for="(cell, c) in cellsOf(row)" :key="c" :class="{ 'is-front': mapping.front === c, 'is-back': mapping.back === c }">
                    {{ cell }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 3. 列映射 -->
          <div v-if="headers.length" class="cxu-block">
            <div class="cxu-label">3. 列映射（猜错会让正面/背面颠倒，务必看一眼）</div>
            <div class="cxu-map">
              <label v-for="f in MAPPING_FIELDS" :key="f" class="cxu-field">
                <span>{{ MAPPING_LABEL[f] }}<i v-if="f === 'front' || f === 'back'">*</i></span>
                <select
                  class="adm-select"
                  :disabled="busy"
                  :value="mapping[f] === null ? '' : String(mapping[f])"
                  @change="onMapChange(f, ($event.target as HTMLSelectElement).value)"
                >
                  <option value="">不使用</option>
                  <option v-for="(h, i) in headers" :key="i" :value="String(i)">
                    第{{ i + 1 }}列 · {{ h || '（空表头）' }}
                  </option>
                </select>
              </label>
            </div>
            <p class="cxu-map-summary">{{ mappingSummary(mapping, headers) || '还没选列' }}</p>
            <p v-if="!isMappingReady(mapping)" class="cxu-warn">正面列和背面列都必选，且不能是同一列。</p>
          </div>

          <!-- 4. 入库参数 -->
          <div v-if="headers.length" class="cxu-block">
            <div class="cxu-label">4. 入库参数</div>
            <div class="cxu-form">
              <label class="cxu-field">
                <span>科目<i>*</i></span>
                <select v-model="form.subject" class="adm-select" :disabled="busy">
                  <option value="xingce">行测</option>
                  <option value="shenlun">申论</option>
                  <option value="gongzhuan">公专</option>
                </select>
              </label>
              <label class="cxu-field">
                <span>兜底分类（可空）</span>
                <input v-model="form.category" class="adm-input" :disabled="busy" placeholder="表里没有分类列时用它" />
              </label>
            </div>
            <label class="cxu-publish">
              <input v-model="form.publish" type="checkbox" :disabled="busy" />
              <span>
                <b>立即上架</b>
                <em>不勾 = 先落「未上架」，逐张核对后再上架（推荐）</em>
              </span>
            </label>
          </div>

          <!-- 5. 结果 -->
          <div v-if="result" class="cxu-block cxu-result">
            <div class="cxu-label">5. 结果</div>
            <p>
              已创建 <b>{{ result.created }}</b> 张卡片（{{ result.published ? '已上架' : '未上架' }}）
              <template v-if="result.skipped_count">；跳过 <b>{{ result.skipped_count }}</b> 行</template>
            </p>
            <ul v-if="skipLines.length" class="cxu-skips">
              <li v-for="(line, i) in skipLines" :key="i">{{ line }}</li>
            </ul>
            <p class="cxu-hint">可以关掉这个窗口，去列表逐张核对/上架。</p>
          </div>
        </div>

        <footer class="cxu-foot">
          <span class="cxu-foot-hint">
            <template v-if="result">已入库 {{ result.created }} 张</template>
            <template v-else-if="parsing">解析中，稍等…</template>
            <template v-else>表结构与列映射都确认后再点入库</template>
          </span>
          <div class="cxu-foot-btns">
            <button class="adm-btn adm-btn--line" type="button" :disabled="busy" @click="requestClose">关闭</button>
            <button
              class="adm-btn adm-btn--primary"
              type="button"
              :disabled="busy || !canConfirm"
              :title="canConfirm ? '' : '先选文件、解析成功、并把正面/背面两列选好'"
              @click="doConfirm"
            >
              {{ result ? '再导一份' : '确认入库' }}
            </button>
          </div>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * S3（2026-11-12）：把旧版页的「智能导入 xlsx → N 张卡」搬进新版资料管理页。
 *
 * 为什么必须搬：新版「批量导入」的 xlsx 走 `admin/files/upload`（只存原件），
 * 建卡必须走 `import/upload → preview → confirm{column_mapping}`（列映射是硬契约）。
 * 端点全是现成的，所以**零后端改动**。
 */
import { computed, reactive, ref, watch } from 'vue';

import {
  confirmMaterialImport,
  fetchMaterialImportPreview,
  fetchMaterialImportStatus,
  importMaterialFile,
  type LibrarySubject,
  type MaterialImportConfirmResult
} from '@/modules/library/api';
import { errorMessage } from '@/utils/apiError';
import {
  MAPPING_FIELDS,
  MAPPING_LABEL,
  guessXlsxMapping,
  isMappingReady,
  mappingPayload,
  mappingSummary,
  type MappingField,
  type XlsxMapping
} from '@/utils/cardXlsx';

const props = withDefaults(
  defineProps<{ open: boolean; defaultSubject?: LibrarySubject }>(),
  { defaultSubject: 'gongzhuan' }
);
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'done', payload: { created: number }): void;
}>();

/** 与后端 `XLSX_SIZE_LIMIT` 对齐（5MB）；超了后端 400，先在前端拦更友好 */
const MAX_XLSX_BYTES = 5 * 1024 * 1024;
const POLL_MS = 2000;
const POLL_MAX = 90;

const fileInput = ref<HTMLInputElement | null>(null);
const file = ref<File | null>(null);
const importId = ref<number | null>(null);
const parseStatus = ref('');
const parsing = ref(false);
const elapsed = ref(0);
const headers = ref<string[]>([]);
const rows = ref<string[][]>([]);
const rowCount = ref(0);
const error = ref('');
const mapping = reactive<XlsxMapping>({ front: null, back: null, category: null, point: null, cover: null });
const form = reactive({ subject: props.defaultSubject, category: '', publish: false });
const confirming = ref(false);
const result = ref<MaterialImportConfirmResult | null>(null);

const busy = computed(() => parsing.value || confirming.value);
const canConfirm = computed(
  () => !busy.value && !result.value && headers.value.length > 0 && isMappingReady(mapping)
);
const previewRows = computed(() => rows.value.slice(0, 5));
const skipLines = computed(() => {
  const r = result.value;
  if (!r) return [];
  const lines: string[] = [];
  for (const s of (r.skipped || []).slice(0, 5)) {
    lines.push(`第 ${s.row} 行：${s.reason === 'duplicate' ? '内容与已有卡片重复' : s.reason}`);
  }
  for (const row of (r.invalid_rows || []).slice(0, 5)) lines.push(`第 ${row} 行：正面或背面为空，已跳过`);
  // 警告有两种来源：①入库时的分类/考点回退（kind+value）②格式校验器（code+message）。
  // 直接读 value 会显示成「undefined」——实测踩过一次，这里两种形状都认。
  for (const w of (r.warnings || []).slice(0, 5)) {
    if (w.message) {
      lines.push(`第 ${w.row} 行：${w.message}`);
      continue;
    }
    const what = w.kind === 'category' ? '分类' : '考点';
    lines.push(`第 ${w.row} 行：${what}「${w.value ?? ''}」不存在，已改为「${w.replaced_by || '自动分类'}」`);
  }
  return lines;
});

let pollTimer: number | null = null;
let tickTimer: number | null = null;

function stopTimers(): void {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
  if (tickTimer !== null) {
    window.clearInterval(tickTimer);
    tickTimer = null;
  }
}

function reset(): void {
  stopTimers();
  file.value = null;
  importId.value = null;
  parseStatus.value = '';
  parsing.value = false;
  elapsed.value = 0;
  headers.value = [];
  rows.value = [];
  rowCount.value = 0;
  error.value = '';
  result.value = null;
  Object.assign(mapping, { front: null, back: null, category: null, point: null, cover: null });
  Object.assign(form, { subject: props.defaultSubject, category: '', publish: false });
  if (fileInput.value) fileInput.value.value = '';
}

function requestClose(): void {
  if (busy.value) return;
  emit('close');
}

function humanBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function cellsOf(row: string[]): string[] {
  const out = row.slice(0, headers.value.length);
  while (out.length < headers.value.length) out.push('');
  return out;
}

function onMapChange(field: MappingField, value: string): void {
  mapping[field] = value === '' ? null : Number(value);
}

async function loadPreview(id: number): Promise<void> {
  const d = await fetchMaterialImportPreview(id);
  headers.value = d.headers || d.result?.headers || [];
  rows.value = (d.result?.rows as string[][]) || [];
  rowCount.value = d.row_count ?? rows.value.length;
  Object.assign(mapping, guessXlsxMapping(headers.value));
}

async function upload(f: File): Promise<void> {
  error.value = '';
  result.value = null;
  headers.value = [];
  rows.value = [];
  parsing.value = true;
  elapsed.value = 0;
  const started = Date.now();
  tickTimer = window.setInterval(() => {
    elapsed.value = Math.round((Date.now() - started) / 1000);
  }, 1000);
  try {
    const up = await importMaterialFile(f);
    importId.value = up.import_id;
    parseStatus.value = up.parse_status;
    if (up.parse_status === 'success') {
      await loadPreview(up.import_id);
      return;
    }
    if (up.parse_status === 'failed') {
      error.value = up.error_message || '解析失败（表头/格式不认识）';
      return;
    }
    // processing：xlsx 通常同步出结果，这里兜扫描/大表的情况
    let waited = 0;
    await new Promise<void>((resolve) => {
      pollTimer = window.setInterval(async () => {
        waited += POLL_MS / 1000;
        try {
          const st = await fetchMaterialImportStatus(up.import_id);
          parseStatus.value = st.parse_status;
          if (st.parse_status === 'success') {
            stopTimers();
            await loadPreview(up.import_id);
            resolve();
          } else if (st.parse_status === 'failed' || waited >= POLL_MAX) {
            stopTimers();
            error.value = st.error_message || (waited >= POLL_MAX ? '解析超时' : '解析失败');
            resolve();
          }
        } catch (e) {
          stopTimers();
          error.value = errorMessage(e, '处理失败，请重试');
          resolve();
        }
      }, POLL_MS);
    });
  } catch (e) {
    error.value = errorMessage(e, '处理失败，请重试');
  } finally {
    stopTimers();
    parsing.value = false;
  }
}

async function onPick(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement;
  const picked = input.files?.[0];
  if (!picked) return;
  if (!/\.xlsx$/i.test(picked.name)) {
    error.value = '这里只收 .xlsx（旧 .xls 请先另存为 xlsx）';
    return;
  }
  if (picked.size > MAX_XLSX_BYTES) {
    error.value = `这个文件 ${humanBytes(picked.size)}，超过 5MB 上限（后端限制），请拆小`;
    return;
  }
  file.value = picked;
  await upload(picked);
}

async function doConfirm(): Promise<void> {
  if (result.value) {
    reset();
    return;
  }
  const id = importId.value;
  if (!id || !canConfirm.value) return;
  error.value = '';
  confirming.value = true;
  try {
    const r = await confirmMaterialImport(id, {
      subject: form.subject as LibrarySubject,
      type: 'card',
      category: form.category.trim() || undefined,
      publish: form.publish,
      column_mapping: mappingPayload(mapping)
    });
    result.value = r;
    emit('done', { created: r.created });
  } catch (e) {
    error.value = errorMessage(e, '处理失败，请重试');
  } finally {
    confirming.value = false;
  }
}

watch(
  () => props.open,
  (v) => {
    if (v) reset();
    else stopTimers();
  }
);
</script>

<style scoped>
.cxu-root {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 48px 16px;
}
.cxu-mask {
  position: absolute;
  inset: 0;
  background: rgba(10, 22, 40, 0.45);
}
.cxu-panel {
  position: relative;
  width: min(880px, 100%);
  max-height: calc(100vh - 96px);
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 18px 48px rgba(10, 22, 40, 0.28);
  overflow: hidden;
}
.cxu-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 20px 12px;
  border-bottom: 1px solid #eef1f6;
}
.cxu-title {
  margin: 0 0 4px;
  font-size: 16px;
  color: var(--adm-text, #1a2a4a);
}
.cxu-desc {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--adm-text-2, #6b7c99);
}
.cxu-x {
  border: 0;
  background: none;
  font-size: 22px;
  line-height: 1;
  color: #8a9ab5;
  cursor: pointer;
}
.cxu-body {
  padding: 14px 20px 8px;
  overflow: auto;
}
.cxu-block {
  margin-bottom: 14px;
}
.cxu-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--adm-text, #1a2a4a);
}
.cxu-badge {
  font-size: 11.5px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 999px;
}
.cxu-badge.is-busy {
  background: #fff4e5;
  color: #b26a00;
}
.cxu-badge.is-ok {
  background: #eaf3ff;
  color: #1a5fb4;
}
.cxu-pick {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.cxu-file {
  display: none;
}
.cxu-file-name {
  font-size: 12.5px;
  color: var(--adm-text, #1a2a4a);
}
.cxu-hint {
  font-size: 12px;
  color: #8a9ab5;
}
.cxu-error {
  margin: 8px 0 0;
  font-size: 12.5px;
  color: #c62828;
  line-height: 1.6;
}
.cxu-warn {
  margin: 6px 0 0;
  font-size: 12px;
  color: #b26a00;
}
.cxu-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  table-layout: fixed;
}
.cxu-table th,
.cxu-table td {
  border: 1px solid #eef1f6;
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
  word-break: break-all;
}
.cxu-table th {
  background: #f7f9fc;
  color: #46587a;
  font-weight: 600;
}
.cxu-table .cxu-idx {
  width: 42px;
  color: #98a6bd;
  text-align: center;
}
.cxu-table .is-front {
  background: #eef8ee;
}
.cxu-table .is-back {
  background: #eef3ff;
}
.cxu-map {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 10px;
}
.cxu-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #46587a;
}
.cxu-field i {
  font-style: normal;
  color: #c62828;
  margin-left: 2px;
}
.cxu-map-summary {
  margin: 8px 0 0;
  font-size: 12px;
  color: #1a5fb4;
}
.cxu-form {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}
.cxu-publish {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-top: 10px;
  font-size: 12.5px;
  color: #46587a;
}
.cxu-publish input {
  margin-top: 2px;
}
.cxu-publish b {
  display: block;
  color: var(--adm-text, #1a2a4a);
}
.cxu-publish em {
  font-style: normal;
  color: #8a9ab5;
}
.cxu-result p {
  margin: 0 0 6px;
  font-size: 13px;
  color: var(--adm-text, #1a2a4a);
}
.cxu-skips {
  margin: 4px 0 8px;
  padding-left: 18px;
  font-size: 12px;
  color: #b26a00;
  line-height: 1.7;
}
.cxu-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 20px;
  border-top: 1px solid #eef1f6;
  background: #fbfcfe;
}
.cxu-foot-hint {
  font-size: 12px;
  color: #8a9ab5;
}
.cxu-foot-btns {
  display: flex;
  gap: 8px;
}
</style>
