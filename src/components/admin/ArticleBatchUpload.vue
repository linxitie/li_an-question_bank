<template>
  <Teleport to="body">
    <div v-if="open" class="abu-root" role="dialog" aria-modal="true" aria-label="批量上传文章">
      <div class="abu-mask" @click="onMask" />
      <section class="abu-panel">
        <header class="abu-head">
          <div>
            <h2 class="abu-title">{{ title }}</h2>
            <p class="abu-desc">
              一次最多 {{ MAX_BATCH_FILES }} 个文件。文章必须有正文，所以走「解析导入」：
              逐条上传 → 解析 → 入库（默认未上架；可勾选「立即上架」）。
              <b>扫描版 PDF 自动 OCR</b>（约 10–20 秒/页，长文请耐心等，界面会显示页级进度）。
            </p>
          </div>
          <button class="abu-x" type="button" :disabled="running" @click="requestClose">×</button>
        </header>

        <div class="abu-body">
          <div class="abu-block">
            <div class="abu-block__label">1. 选择文件（.docx / .pdf）</div>
            <div class="abu-pick">
              <input
                ref="fileInput"
                class="abu-file"
                type="file"
                multiple
                accept=".docx,.pdf"
                :disabled="running"
                @change="onPick"
              />
              <button class="adm-btn adm-btn--line" type="button" :disabled="running" @click="fileInput?.click()">
                选择文件
              </button>
              <span v-if="picked.length" class="abu-summary">
                {{ picked.length }} 个文件 · {{ humanBytes(totalBytes) }}
              </span>
              <span v-else class="abu-hint">还没选文件</span>
              <button v-if="picked.length && !running" class="abu-clear" type="button" @click="reset">清空</button>
            </div>
            <ul v-if="issues.length" class="abu-issues">
              <li v-for="(i, k) in issues" :key="k">{{ i }}</li>
            </ul>
          </div>

          <div class="abu-block">
            <div class="abu-block__label">2. 入库参数（本批统一）</div>
            <div class="abu-form">
              <label class="abu-field">
                <span>科目</span>
                <select v-model="subject" class="adm-select" :disabled="running">
                  <option value="xingce">行测</option>
                  <option value="shenlun">申论</option>
                  <option value="gongzhuan">公专</option>
                </select>
              </label>
              <!-- 2026-11-12：批量文章默认仍是"未上架"，但给一个显式开关 -->
              <label class="abu-check" title="勾选后本批文章直接上架（学生立刻可见）；默认不勾，先逐篇预览再上架">
                <input v-model="publishNow" type="checkbox" :disabled="running" />
                <span>立即上架（{{ publishNow ? '本批直接对学生可见' : '默认不上架，需去列表点上架' }}）</span>
              </label>
              <span class="abu-note">标题默认取文件名（不含扩展名），入库后可在「改信息」里改。</span>
            </div>
          </div>

          <div v-if="rows.length" class="abu-block">
            <div class="abu-block__label">
              3. 队列
              <span class="abu-progress-text">
                {{ doneCount }} / {{ rows.length }} 处理完
                <template v-if="failedCount">· 失败 {{ failedCount }}</template>
                <template v-if="dupCount">· 重复跳过 {{ dupCount }}</template>
              </span>
            </div>
            <ul class="abu-rows">
              <li v-for="r in rows" :key="r.key" class="abu-row" :class="`is-${r.status}`">
                <span class="abu-row__badge">{{ statusLabel(r.status) }}</span>
                <span class="abu-row__name" :title="r.name">{{ r.name }}</span>
                <span class="abu-row__meta">
                  <template v-if="r.materialId">资料 #{{ r.materialId }} · </template>{{ humanBytes(r.size) }}
                </span>
                <span
                  v-if="r.status === 'parsing' && r.progress"
                  class="abu-row__note is-busy"
                >{{ ocrProgressText(r.progress, r.elapsed) }}</span>
                <span v-else-if="r.note" class="abu-row__note">{{ r.note }}</span>
                <span v-if="r.error" class="abu-row__err" :title="r.error">{{ r.error }}</span>
              </li>
            </ul>
          </div>
        </div>

        <footer class="abu-foot">
          <span class="abu-foot__hint">{{ footHint }}</span>
          <button class="adm-btn adm-btn--line" type="button" :disabled="running" @click="requestClose">关闭</button>
          <button class="adm-btn adm-btn--primary" type="button" :disabled="!canStart" @click="start">
            {{ running ? `处理中… ${doneCount}/${rows.length}` : '开始导入' }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * 批量上传**文章**（L4，2026-11-09）。
 *
 * 为什么单独做一条链路、不复用 `MaterialBatchUpload`：
 *   - 后者走 `/admin/files/upload`，只"留档 + 建未上架资料"，**不解析正文**；
 *     文章详情页读的是 `content`，留档路径拿不到 → 学生点开是空白（讲义现在就这状态）。
 *   - 文章必须"有正文"，所以走"解析导入"：`import/upload`（解析）→ 轮询状态 →
 *     `import/{id}/confirm {type:'article'}`（把解析出的 html 落成 content）。
 *
 * 三道保护沿用解析链路既有的：
 *   · 同文件（名+大小+sha256）重复上传 → 后端 409，这里标「重复」；
 *   · 同内容（content_hash）确认时 409（force 可放行，本批不提供该按钮）；
 *   · 扫描版 PDF 需 OCR，未就绪时解析失败 → 逐行报原因，不创建空文章。
 */
import { computed, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import {
  confirmMaterialImport,
  fetchMaterialImportStatus,
  importMaterialFile,
  type LibrarySubject
} from '@/modules/library/api';
import { MAX_BATCH_BYTES, MAX_BATCH_FILES, humanBytes } from '@/utils/batchUploadPlan';
import { errorMessage } from '@/utils/apiError';
import { forEachConcurrent } from '@/utils/concurrency';
import { ocrProgressText, ocrResultNote, type OcrProgress } from '@/utils/ocrProgress';

const props = withDefaults(
  defineProps<{ open: boolean; defaultSubject?: LibrarySubject; title?: string }>(),
  { defaultSubject: 'gongzhuan', title: '批量上传文章' }
);
const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'done', payload: { created: number; skipped: number; failed: number }): void;
}>();

type RowStatus = 'waiting' | 'uploading' | 'parsing' | 'confirming' | 'ok' | 'duplicate' | 'failed';

interface Row {
  key: string;
  name: string;
  size: number;
  file: File;
  status: RowStatus;
  materialId: number | null;
  error: string;
  /** P2：扫描件 OCR 的页级进度（非扫描件为 null，界面不显示） */
  progress?: OcrProgress | null;
  /** P2：解析已用秒数（用于"已用 1:36"） */
  elapsed?: number;
  /** P2：成功后的补充说明（已 OCR x/y 页 / 截断 / 未识别页数） */
  note?: string;
}

const fileInput = ref<HTMLInputElement | null>(null);
const picked = ref<File[]>([]);
const rows = ref<Row[]>([]);
const running = ref(false);
const subject = ref<LibrarySubject>(props.defaultSubject);
/** 2026-11-12：本批是否直接上架（默认 false = 沿用"上架即审批"的安全默认） */
const publishNow = ref(false);

const totalBytes = computed(() => picked.value.reduce((n, f) => n + f.size, 0));

/** 选文件阶段的拦截：格式、数量、总量（与批量导入同一套上限） */
const issues = computed<string[]>(() => {
  const out: string[] = [];
  if (picked.value.length > MAX_BATCH_FILES) out.push(`最多 ${MAX_BATCH_FILES} 个文件，当前 ${picked.value.length} 个`);
  if (totalBytes.value > MAX_BATCH_BYTES) out.push(`总大小超过 ${humanBytes(MAX_BATCH_BYTES)}`);
  for (const f of picked.value) {
    const ext = f.name.split('.').pop()?.toLowerCase() || '';
    if (ext !== 'docx' && ext !== 'pdf') out.push(`不支持 .${ext}：${f.name}（文章只接受 docx/pdf）`);
  }
  return out;
});

const doneCount = computed(() => rows.value.filter((r) => !['waiting', 'uploading', 'parsing', 'confirming'].includes(r.status)).length);
const failedCount = computed(() => rows.value.filter((r) => r.status === 'failed').length);
const dupCount = computed(() => rows.value.filter((r) => r.status === 'duplicate').length);
const canStart = computed(() => !running.value && picked.value.length > 0 && issues.value.length === 0);

const footHint = computed(() => {
  if (running.value) return '正在逐条解析入库，别关页面…';
  if (!picked.value.length) return '先选文件（可多选）';
  if (issues.value.length) return '有文件不符合要求，先处理上面的提示';
  return `将创建最多 ${picked.value.length} 条文章（未上架）`;
});

function statusLabel(s: RowStatus): string {
  return {
    waiting: '等待',
    uploading: '上传中',
    parsing: '解析中',
    confirming: '入库中',
    ok: '成功',
    duplicate: '重复',
    failed: '失败'
  }[s];
}

watch(
  () => props.open,
  (v) => {
    if (v) {
      subject.value = props.defaultSubject;
      reset();
    }
  }
);

function onPick(e: Event): void {
  const input = e.target as HTMLInputElement;
  picked.value = Array.from(input.files || []);
  rows.value = [];
}

function reset(): void {
  picked.value = [];
  rows.value = [];
  if (fileInput.value) fileInput.value.value = '';
}

function onMask(): void {
  if (!running.value) requestClose();
}
function requestClose(): void {
  if (running.value) return;
  emit('close');
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** 等解析完成：同步成功的直接返回；processing（扫描版 OCR）**最多等 30 分钟**。
 *
 * P2（2026-11-12）修正：原来是 72 次 × 2.5s = **180 秒**，实测 24 页扫描件要 3.4–6.6 分钟，
 * 界面会在后台还在跑的时候先报"解析超时"。现在与后端 1800s 上限对齐，并把页级进度写回行。
 */
async function waitParsed(importId: number, row: Row): Promise<string> {
  let status = '';
  for (let i = 0; i < 720; i += 1) {
    const res = await fetchMaterialImportStatus(importId);
    status = res.parse_status;
    row.elapsed = res.elapsed_seconds ?? row.elapsed;
    if (res.progress) {
      row.progress = res.progress as OcrProgress;
    }
    if (status === 'success') {
      row.note = ocrResultNote(res.progress as OcrProgress | undefined) || '';
      return 'success';
    }
    if (status !== 'processing') {
      row.error = res.error_message || `解析失败（${status}）`;
      return 'failed';
    }
    row.status = 'parsing';
    await sleep(2500);
  }
  row.error = '解析超时（>30 分钟），请稍后在导入记录里重试或拆分文件';
  return 'failed';
}

async function start(): Promise<void> {
  if (!canStart.value) return;
  running.value = true;
  rows.value = picked.value.map((f) => ({
    key: `${f.name}_${f.size}_${f.lastModified}`,
    name: f.name,
    size: f.size,
    file: f,
    status: 'waiting' as RowStatus,
    materialId: null,
    error: '',
    progress: null,
    elapsed: undefined,
    note: ''
  }));
  let created = 0;
  let skipped = 0;
  let failed = 0;

  /** 处理单行：上传 → 等解析（扫描件含 OCR 进度）→ 确认入库。并发行数由 forEachConcurrent 控制 */
  async function handleRow(row: Row): Promise<void> {
    row.status = 'uploading';
    let importId = 0;
    try {
      const up = await importMaterialFile(row.file);
      importId = up.import_id;
      if (up.parse_status === 'failed') {
        row.status = 'failed';
        row.error = up.error_message || '解析失败';
        failed += 1;
        return;
      }
    } catch (e) {
      const msg = errorMessage(e, '上传失败');
      // 后端对"同名+同大小+同 sha256"的历史导入返回 409，文案里带"重复"
      if (msg.includes('重复') || msg.includes('已经')) {
        row.status = 'duplicate';
        row.error = msg;
        skipped += 1;
      } else {
        row.status = 'failed';
        row.error = msg;
        failed += 1;
      }
      return;
    }

    const parsed = await waitParsed(importId, row);
    if (!parsed || parsed !== 'success') {
      row.status = 'failed';
      if (!row.error) row.error = '解析未成功';
      failed += 1;
      return;
    }

    row.status = 'confirming';
    try {
      const stem = row.name.replace(/\.[^.]+$/, '').slice(0, 200) || row.name;
      const res = await confirmMaterialImport(importId, {
        subject: subject.value,
        type: 'article',
        title: stem,
        // 2026-11-12：以前不传 → 后端文档分支写死 status=0，只能逐条再点上架
        publish: publishNow.value
      });
      if (!res.created) {
        row.status = 'duplicate';
        row.error = '内容重复，未新建';
        skipped += 1;
        return;
      }
      row.status = 'ok';
      row.materialId = res.material_ids?.[0] ?? null;
      created += 1;
    } catch (e) {
      row.status = 'failed';
      row.error = errorMessage(e, '入库失败');
      failed += 1;
    }
  }

  // S-B（2026-11-13）：原来的串行 for 改成"最多 2 个在飞"。
  // 实测服务端 6 份 docx 串行 1,615ms → 2 路 1,429ms（1.13×，解析是 CPU 密集、GIL 下不能真并行），
  // 主要收益是盖住网络/排队延迟，并且不会把一次 50 个请求全甩给后端。
  await forEachConcurrent(rows.value, 2, handleRow);

  running.value = false;
  emit('done', { created, skipped, failed });
  if (created) {
    ElMessage.success(publishNow.value
      ? `已创建并上架 ${created} 篇文章，学生端立即可见`
      : `已创建 ${created} 篇文章（未上架），去列表上架后学生可见`);
  }
  if (failed) ElMessage.warning(`${failed} 个文件失败，详见队列里的原因`);
}
</script>

<style scoped>
.abu-root {
  position: fixed;
  inset: 0;
  z-index: 2600;
  display: flex;
  align-items: center;
  justify-content: center;
}
.abu-mask {
  position: absolute;
  inset: 0;
  background: rgba(17, 24, 39, 0.42);
}
.abu-panel {
  position: relative;
  width: min(920px, calc(100vw - 48px));
  max-height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: var(--adm-r-card, 14px);
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.24);
  overflow: hidden;
}
.abu-head {
  display: flex;
  gap: 12px;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--adm-line);
}
.abu-head > div { flex: 1; }
.abu-title { margin: 0; font-size: 16px; color: var(--adm-text); }
.abu-desc { margin: 6px 0 0; font-size: 12px; line-height: 1.6; color: var(--adm-text-weak); }
.abu-x {
  border: none;
  background: none;
  font-size: 22px;
  line-height: 1;
  color: var(--adm-text-weak);
  cursor: pointer;
}
.abu-body { padding: 16px 20px; overflow: auto; }
.abu-block { margin-bottom: 16px; }
.abu-block__label { font-size: 12px; font-weight: 700; color: var(--adm-text-mid); margin-bottom: 8px; }
.abu-pick { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.abu-file { display: none; }
.abu-summary { font-size: 12px; color: var(--adm-text-mid); }
.abu-hint { font-size: 12px; color: var(--adm-text-weak); }
.abu-clear { border: none; background: none; color: var(--adm-blue); font-size: 12px; cursor: pointer; }
.abu-issues { margin: 8px 0 0; padding-left: 18px; color: var(--adm-warn); font-size: 12px; }
.abu-form { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.abu-field { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--adm-text-mid); }
.abu-check {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 10px; border: 1px dashed var(--adm-line); border-radius: var(--adm-r-ctl);
  font-size: 12px; color: var(--adm-text-mid); cursor: pointer;
}
.abu-check input { margin: 0; }
.abu-check:hover { border-color: var(--adm-blue); color: var(--adm-blue); }
.abu-note { font-size: 12px; color: var(--adm-text-weak); }
.abu-progress-text { margin-left: 8px; font-weight: 400; color: var(--adm-text-weak); }
.abu-rows { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.abu-row {
  display: grid;
  grid-template-columns: 58px minmax(180px, 1.6fr) minmax(120px, 1fr);
  gap: 10px;
  align-items: center;
  padding: 7px 10px;
  border: 1px solid var(--adm-line);
  border-radius: var(--adm-r-ctl);
  font-size: 12px;
}
.abu-row__badge { text-align: center; padding: 2px 0; border-radius: 8px; background: var(--adm-muted-weak); color: var(--adm-muted); }
.abu-row.is-ok .abu-row__badge { background: #e7f7ef; color: #0f7a46; }
.abu-row.is-failed .abu-row__badge { background: #fdecec; color: #b42318; }
.abu-row.is-duplicate .abu-row__badge { background: #fff4e5; color: #b35309; }
.abu-row__name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.abu-row__meta { color: var(--adm-text-weak); }
.abu-row__err { grid-column: 2 / -1; color: #b42318; }
.abu-row__note {
  grid-column: 2 / -1;
  font-size: 12px;
  color: #1a5fb4;
}
.abu-row__note.is-busy { color: #b26a00; }
.abu-foot {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-top: 1px solid var(--adm-line);
}
.abu-foot__hint { flex: 1; font-size: 12px; color: var(--adm-text-weak); }
</style>
