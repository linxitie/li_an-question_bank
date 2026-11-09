<template>
  <Teleport to="body">
    <div v-if="open" class="mbu-root" role="dialog" aria-modal="true" aria-label="批量导入">
      <div class="mbu-mask" @click="onMask" />
      <section class="mbu-panel">
        <header class="mbu-head">
          <div>
            <h2 class="mbu-title">{{ title }}</h2>
            <p class="mbu-desc">
              一次最多 {{ MAX_BATCH_FILES }} 个文件、合计 ≤ {{ humanBytes(MAX_BATCH_BYTES) }}；
              <b>同名 docx + pdf 合成一条</b>（docx 主文件、pdf 附件）。导入后为「未上架」，需再点上架。
            </p>
          </div>
          <button class="mbu-x" type="button" :disabled="running" @click="requestClose">×</button>
        </header>

        <div class="mbu-body">
          <!-- 1. 选文件 -->
          <div class="mbu-block">
            <div class="mbu-block__label">1. 选择文件</div>
            <div class="mbu-pick">
              <input
                ref="fileInput"
                class="mbu-file"
                type="file"
                multiple
                accept=".docx,.doc,.pdf,.xlsx,.xls"
                :disabled="running"
                @change="onPick"
              />
              <button class="adm-btn adm-btn--line" type="button" :disabled="running" @click="fileInput?.click()">
                选择文件
              </button>
              <span v-if="picked.length" class="mbu-summary">
                {{ picked.length }} 个文件 → 将创建 <b>{{ summary.materials }}</b> 条资料
                <template v-if="summary.pairs">（含 {{ summary.pairs }} 组双格式）</template>
                · {{ humanBytes(summary.bytes) }}
              </span>
              <span v-else class="mbu-hint">还没选文件</span>
              <button v-if="picked.length && !running" class="mbu-clear" type="button" @click="reset">清空</button>
            </div>

            <ul v-if="planIssues.length" class="mbu-issues">
              <li v-for="(i, k) in planIssues" :key="k">{{ i.message }}</li>
            </ul>

            <div v-if="groups.length" class="mbu-groups">
              <div v-for="g in groups" :key="g.key" class="mbu-group">
                <span class="mbu-group__kind" :class="{ 'is-pair': g.kind === 'pair' }">
                  {{ g.kind === 'pair' ? '合并 1 条' : '1 条' }}
                </span>
                <span class="mbu-group__name">{{ g.primary.name }}</span>
                <span v-if="g.attachment" class="mbu-group__attach">+ 附件 {{ g.attachment.name }}</span>
                <span class="mbu-group__size">{{ humanBytes(g.primary.size + (g.attachment?.size || 0)) }}</span>
              </div>
            </div>
          </div>

          <!-- 2. 入库参数 -->
          <div class="mbu-block">
            <div class="mbu-block__label">2. 入库参数（本批统一）</div>
            <div class="mbu-form">
              <label class="mbu-field">
                <span>科目</span>
                <select v-model="form.subject" class="adm-select" :disabled="running">
                  <option value="xingce">行测</option>
                  <option value="shenlun">申论</option>
                  <option value="gongzhuan">公专</option>
                </select>
              </label>
              <label class="mbu-field">
                <span>类型</span>
                <select v-model="form.type" class="adm-select" :disabled="running">
                  <option value="lecture">讲义</option>
                  <option value="paper">试卷</option>
                  <option value="article">文章</option>
                </select>
              </label>
              <label class="mbu-field">
                <span>分类（可空）</span>
                <input v-model="form.category" class="adm-input" :disabled="running" placeholder="如 基础知识" />
              </label>
            </div>

            <!-- L4（2026-11-09）：投放位只对试卷有意义——决定上架后"进考试页 / 进资料库 / 两边都进"。
                 讲义/文章没有"考试页"这回事，所以不显示（后端也会把非试卷强制成 library）。 -->
            <div v-if="form.type === 'paper'" class="mbu-place">
              <div class="mbu-place__label">投放位（上架后往哪儿放）</div>
              <div class="mbu-place__opts">
                <label
                  v-for="p in MATERIAL_PLACEMENTS"
                  :key="p.key"
                  :class="['mbu-place__opt', { on: form.placement === p.key }]"
                >
                  <input v-model="form.placement" type="radio" :value="p.key" :disabled="running" />
                  <b>{{ p.label }}</b>
                  <em>{{ p.hint }}</em>
                </label>
              </div>
            </div>
          </div>

          <!-- 3. 队列 -->
          <div v-if="rows.length" class="mbu-block">
            <div class="mbu-block__label">
              3. 导入队列
              <span class="mbu-progress-text">
                {{ doneCount }} / {{ rows.length }} 处理完
                <template v-if="failedCount">· 失败 {{ failedCount }}</template>
                <template v-if="dupCount">· 重复跳过 {{ dupCount }}</template>
              </span>
            </div>
            <ul class="mbu-rows">
              <li v-for="r in rows" :key="r.key" class="mbu-row" :class="`is-${r.status}`">
                <span class="mbu-row__badge">{{ statusLabel(r.status) }}</span>
                <span class="mbu-row__name">{{ r.label }}</span>
                <span class="mbu-row__meta">
                  {{ r.files }} 个文件 · {{ humanBytes(r.bytes) }}
                  <template v-if="r.materialId"> · 资料 #{{ r.materialId }}</template>
                </span>
                <span class="mbu-row__bar"><i :style="{ width: `${r.percent}%` }" /></span>
                <span v-if="r.error" class="mbu-row__err" :title="r.error">{{ r.error }}</span>
                <span v-else-if="r.paperNote" class="mbu-row__note" :title="r.paperNote">{{ r.paperNote }}</span>
              </li>
            </ul>
          </div>
        </div>

        <footer class="mbu-foot">
          <span class="mbu-foot__hint">{{ footHint }}</span>
          <button class="adm-btn adm-btn--line" type="button" :disabled="running" @click="requestClose">关闭</button>
          <button
            class="adm-btn adm-btn--primary"
            type="button"
            :disabled="!canStart"
            @click="start"
          >
            {{ running ? `导入中… ${doneCount}/${rows.length}` : '开始导入' }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * 批量导入（B2，2026-11-07）
 *
 * 流程：选文件 → 编排（同名 docx+pdf 合并）→ 统一入库参数 → 逐条队列上传 → 汇总。
 *
 * 为什么逐条上传而不是一个 50 文件的大请求：
 *   · 能显示"第几条在传、传了百分之几"（大请求只能干等）；
 *   · 单条失败不影响其它，可以只补传失败那条；
 *   · 重复内容由后端判（同一 sha256 已存在就返回 duplicate），前端按"重复跳过"标注。
 *
 * 前端不做解析/识别：本批只负责"原件留档 + 建未上架资料"，
 * 正文渲染与元数据（年份/地区/题量）分别由 C1/C2 接手。
 */
import { computed, reactive, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { uploadMaterialFile, type LibrarySubject } from '@/modules/library/api';
import { MATERIAL_PLACEMENTS } from '@/modules/library/materialTypes';
import {
  MAX_BATCH_BYTES,
  MAX_BATCH_FILES,
  humanBytes,
  planUploadGroups,
  summarize,
  validateSelection,
  type PickedFile,
  type SelectionIssue,
  type UploadGroup
} from '@/utils/batchUploadPlan';
import { errorMessage } from '@/utils/apiError';

const props = withDefaults(
  defineProps<{
    open: boolean;
    /** 打开时预置的类型（「＋上传试卷」传 paper，「批量导入」传 lecture） */
    presetType?: 'article' | 'lecture' | 'paper';
    /** 对话框标题 */
    title?: string;
  }>(),
  { presetType: 'lecture', title: '批量导入资料' }
);

const emit = defineEmits<{ (e: 'close'): void; (e: 'done', payload: { created: number; skipped: number; failed: number }): void }>();

type RowStatus = 'waiting' | 'uploading' | 'ok' | 'duplicate' | 'failed';

interface QueueRow {
  key: string;
  label: string;
  files: number;
  bytes: number;
  group: UploadGroup;
  status: RowStatus;
  percent: number;
  materialId: number | null;
  error: string;
  /** P1：自动建卷的回执（成功建卷或"为什么没建"），成功行也要显示 */
  paperNote: string;
}

const fileInput = ref<HTMLInputElement | null>(null);
const picked = ref<File[]>([]);
const rows = ref<QueueRow[]>([]);
const running = ref(false);

const form = reactive({
  subject: 'gongzhuan' as LibrarySubject,
  type: props.presetType,
  category: '',
  /** L4：投放位（默认都投 = 改造前行为）；只在 type=paper 时提交 */
  placement: 'both' as 'exam' | 'library' | 'both'
});

const plan = computed(() => planUploadGroups(picked.value.map((f) => ({ name: f.name, size: f.size }))));
const groups = computed(() => plan.value.groups);
const summary = computed(() => summarize(groups.value));
const planIssues = computed<SelectionIssue[]>(() => [
  ...validateSelection(picked.value.map((f) => ({ name: f.name, size: f.size })))
    .filter((i) => i.code !== 'empty'),
  ...plan.value.issues
]);

const doneCount = computed(() => rows.value.filter((r) => r.status !== 'waiting' && r.status !== 'uploading').length);
const failedCount = computed(() => rows.value.filter((r) => r.status === 'failed').length);
const dupCount = computed(() => rows.value.filter((r) => r.status === 'duplicate').length);
const canStart = computed(() => !running.value && groups.value.length > 0 && planIssues.value.length === 0);

const footHint = computed(() => {
  if (running.value) return '正在上传，别关页面…';
  if (!groups.value.length) return '先选文件（可多选）';
  if (planIssues.value.length) return '有文件不符合要求，先处理上面的提示';
  return `将创建 ${summary.value.materials} 条资料（未上架），共 ${summary.value.files} 个文件`;
});

function statusLabel(s: RowStatus): string {
  return { waiting: '等待', uploading: '上传中', ok: '成功', duplicate: '重复', failed: '失败' }[s];
}

watch(
  () => props.open,
  (v) => {
    if (v) {
      form.type = props.presetType;
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

/** 把编排结果物化成队列行（id 与 File 的对应按 base 名 + 扩展名匹配） */
function buildRows(): void {
  const byName = new Map<string, File>();
  for (const f of picked.value) byName.set(f.name, f);
  rows.value = groups.value.map((g) => ({
    key: g.key,
    label: g.primary.name,
    files: g.attachment ? 2 : 1,
    bytes: g.primary.size + (g.attachment?.size || 0),
    group: g,
    status: 'waiting' as RowStatus,
    percent: 0,
    materialId: null,
    error: '',
    paperNote: ''
  }));
  for (const r of rows.value) {
    // 供 start() 取用（避免再按名字查一遍）
    (r as QueueRow & { primaryFile?: File; attachFile?: File }).primaryFile =
      byName.get(r.group.primary.name);
    const att = r.group.attachment;
    if (att) (r as QueueRow & { attachFile?: File }).attachFile = byName.get(att.name);
  }
}

async function start(): Promise<void> {
  if (!canStart.value) return;
  buildRows();
  running.value = true;
  let created = 0;
  let skipped = 0;
  let failed = 0;

  for (const row of rows.value) {
    const ext = row as QueueRow & { primaryFile?: File; attachFile?: File };
    const primary = ext.primaryFile;
    if (!primary) {
      row.status = 'failed';
      row.error = '文件对象丢失，请重新选择';
      failed += 1;
      continue;
    }
    row.status = 'uploading';
    row.percent = 0;
    try {
      const res = await uploadMaterialFile({
        file: primary,
        subject: form.subject,
        type: form.type,
        category: form.category,
        // 只有试卷才有投放位；讲义/文章不传（后端强制 library）
        placement: form.type === 'paper' ? form.placement : undefined,
        onProgress: (p) => {
          // 配对组里主文件占前 80%，附件占后 20%
          row.percent = ext.attachFile ? Math.round(p * 0.8) : p;
        }
      });
      if (res.duplicate) {
        row.status = 'duplicate';
        row.materialId = res.material_id;
        row.percent = 100;
        skipped += 1;
        continue;
      }
      row.materialId = res.material_id;
      row.percent = ext.attachFile ? 80 : 100;

      // P1（2026-11-09）：投放位含考试页的试卷，后端上传时就会建可作答卷。
      // 这里把结果原样告诉管理员 —— 建成了要去导题；没建成是因为文件名缺年份/地区，
      // 需要去「改信息」补编号（不阻断上传，所以不能吞掉不显示）。
      if (res.paper) {
        row.paperNote = res.paper.created
          ? `已自动建卷 ${res.paper.paper_code}（0 题，导题后学生才能考）`
          : `未自动建卷：${res.paper.hint || '编号解析失败'}`;
      }

      if (ext.attachFile) {
        const att = await uploadMaterialFile({
          file: ext.attachFile,
          subject: form.subject,
          type: form.type,
          category: form.category,
          materialId: res.material_id,
          onProgress: (p) => {
            row.percent = 80 + Math.round(p * 0.2);
          }
        });
        if (att.duplicate) row.error = '附件内容与已有原件重复，已跳过附件';
      }
      row.status = 'ok';
      row.percent = 100;
      created += 1;
    } catch (e) {
      row.status = 'failed';
      row.error = errorMessage(e, '上传失败');
      failed += 1;
    }
  }

  running.value = false;
  if (created) ElMessage.success(`成功导入 ${created} 条资料（未上架）`);
  if (skipped) ElMessage.info(`有 ${skipped} 条因内容重复被跳过`);
  if (failed) ElMessage.error(`有 ${failed} 条失败，可看队列里的原因后重试`);
  if (created || skipped) emit('done', { created, skipped, failed });
}

function onMask(): void {
  if (!running.value) requestClose();
}

function requestClose(): void {
  if (running.value) return;
  emit('close');
}

defineExpose({ buildRows });
</script>

<style scoped>
.mbu-root { position: fixed; inset: 0; z-index: 3100; font-family: var(--adm-font); }
.mbu-mask { position: absolute; inset: 0; background: rgba(16, 24, 40, 0.45); }
.mbu-panel {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: min(920px, calc(100vw - 48px));
  max-height: calc(100vh - 72px);
  display: flex;
  flex-direction: column;
  background: var(--adm-surface);
  border-radius: var(--adm-r-card);
  box-shadow: 0 24px 64px rgba(16, 24, 40, 0.28);
  overflow: hidden;
}
.mbu-head {
  display: flex;
  justify-content: space-between;
  gap: var(--adm-s3);
  padding: 16px 20px;
  border-bottom: 1px solid var(--adm-line);
}
.mbu-title { margin: 0 0 4px; font-size: 16px; color: var(--adm-text); }
.mbu-desc { margin: 0; font-size: 12px; line-height: 1.7; color: var(--adm-text-weak); }
.mbu-x {
  border: 0;
  background: transparent;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  color: var(--adm-text-weak);
}
.mbu-body { padding: 14px 20px; overflow: auto; }
.mbu-block { margin-bottom: 16px; }
.mbu-block__label {
  display: flex;
  gap: 10px;
  align-items: baseline;
  font-size: 12px;
  font-weight: 800;
  color: var(--adm-text-sub);
  margin-bottom: 8px;
}
.mbu-progress-text { font-weight: 600; color: var(--adm-text-weak); }
.mbu-pick { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.mbu-file { display: none; }
.mbu-summary { font-size: 12px; color: var(--adm-text-mid); }
.mbu-hint { font-size: 12px; color: var(--adm-text-weak); }
.mbu-clear {
  border: 0;
  background: transparent;
  color: var(--adm-primary);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}
.mbu-issues {
  margin: 8px 0 0;
  padding: 8px 12px 8px 28px;
  border: 1px solid #f3c4ae;
  border-radius: var(--adm-r-ctl);
  background: var(--adm-danger-weak);
  color: var(--adm-danger);
  font-size: 12px;
  line-height: 1.7;
}
.mbu-groups { margin-top: 10px; border: 1px solid var(--adm-line); border-radius: var(--adm-r-ctl); overflow: hidden; }
.mbu-group {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 7px 10px;
  font-size: 12px;
  border-bottom: 1px solid var(--adm-line-weak, #eef1f7);
}
.mbu-group:last-child { border-bottom: 0; }
.mbu-group__kind {
  flex-shrink: 0;
  padding: 1px 7px;
  border-radius: var(--adm-r-tag);
  background: #eef1fe;
  color: var(--adm-text-mid);
  font-size: 11px;
  font-weight: 800;
}
.mbu-group__kind.is-pair { background: var(--adm-ok-weak); color: var(--adm-ok); }
.mbu-group__name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mbu-group__attach { color: var(--adm-text-weak); }
.mbu-group__size { flex-shrink: 0; color: var(--adm-text-weak); }
.mbu-form { display: flex; gap: 12px; flex-wrap: wrap; }
.mbu-field { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--adm-text-mid); }
/* L4：投放位三选一（仅试卷显示） */
.mbu-place { margin-top: 12px; }
.mbu-place__label { font-size: 12px; font-weight: 700; color: var(--adm-text-mid); margin-bottom: 6px; }
.mbu-place__opts { display: flex; gap: 8px; flex-wrap: wrap; }
.mbu-place__opt {
  flex: 1 1 190px;
  display: grid;
  grid-template-columns: 16px 1fr;
  grid-template-rows: auto auto;
  column-gap: 6px;
  padding: 8px 10px;
  border: 1px solid var(--adm-line);
  border-radius: var(--adm-r-ctl);
  cursor: pointer;
  background: #fff;
}
.mbu-place__opt.on { border-color: var(--adm-blue); background: #f5f8ff; }
.mbu-place__opt input { grid-row: 1 / span 2; margin-top: 2px; }
.mbu-place__opt b { font-size: 12.5px; color: var(--adm-text); }
.mbu-place__opt em { font-style: normal; font-size: 11px; color: var(--adm-text-weak); line-height: 1.5; }
.mbu-rows { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.mbu-row {
  display: grid;
  grid-template-columns: 54px minmax(160px, 1.6fr) minmax(150px, 1fr) 120px;
  gap: 10px;
  align-items: center;
  padding: 7px 10px;
  border: 1px solid var(--adm-line);
  border-radius: var(--adm-r-ctl);
  font-size: 12px;
}
.mbu-row__badge { font-weight: 800; color: var(--adm-text-weak); }
.mbu-row.is-uploading .mbu-row__badge { color: var(--adm-primary); }
.mbu-row.is-ok .mbu-row__badge { color: var(--adm-ok); }
.mbu-row.is-duplicate .mbu-row__badge { color: var(--adm-warn); }
.mbu-row.is-failed .mbu-row__badge { color: var(--adm-danger); }
.mbu-row__name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mbu-row__meta { color: var(--adm-text-weak); }
.mbu-row__bar { height: 6px; border-radius: 999px; background: #eef1f7; overflow: hidden; }
.mbu-row__bar i { display: block; height: 100%; background: var(--adm-primary); transition: width 0.2s; }
.mbu-row.is-ok .mbu-row__bar i { background: var(--adm-ok); }
.mbu-row.is-failed .mbu-row__bar i { background: var(--adm-danger); }
.mbu-row__err { grid-column: 1 / -1; color: var(--adm-danger); font-size: 11.5px; }
/* P1：自动建卷回执（不是错误，用中性色 + 与错误同占一行） */
.mbu-row__note { grid-column: 1 / -1; color: var(--adm-text-mid, #5b6b85); font-size: 11px; }
.mbu-foot {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-top: 1px solid var(--adm-line);
  background: var(--adm-bg);
}
.mbu-foot__hint { flex: 1; font-size: 12px; color: var(--adm-text-weak); }
</style>
