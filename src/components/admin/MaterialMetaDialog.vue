<template>
  <Teleport to="body">
    <div v-if="open" class="mmd-root" role="dialog" aria-modal="true" aria-label="改信息">
      <div class="mmd-mask" @click="close" />
      <section class="mmd-panel">
        <header class="mmd-head">
          <div>
            <h2 class="mmd-title">改信息</h2>
            <p class="mmd-desc">
              资料 #{{ materialId }} · {{ typeLabel }}。年份/地区/题量改的是**这份资料**的展示信息，
              不会改题库里那套可作答卷。
            </p>
          </div>
          <button class="mmd-x" type="button" :disabled="saving" @click="close">×</button>
        </header>

        <div class="mmd-body">
          <p v-if="loading" class="adm-empty">加载中…</p>
          <p v-else-if="loadError" class="mmd-error">{{ loadError }}</p>

          <template v-else>
            <div class="mmd-grid">
              <label class="mmd-field mmd-field--wide">
                <span>标题</span>
                <input v-model="form.title" class="adm-input" maxlength="200" :disabled="saving" />
              </label>
              <label class="mmd-field">
                <span>分类（可空）</span>
                <input v-model="form.category" class="adm-input" maxlength="100" :disabled="saving" />
              </label>
              <label class="mmd-field">
                <span>编号</span>
                <input
                  v-model="form.paperCode"
                  class="adm-input mmd-mono"
                  placeholder="留空=按年份/地区自动生成"
                  :disabled="saving"
                />
              </label>
            </div>

            <template v-if="isPaper">
              <div class="mmd-sub">试卷信息</div>
              <div class="mmd-grid">
                <label class="mmd-field">
                  <span>年份</span>
                  <input v-model.number="form.year" class="adm-input" type="number" min="1990" max="2100"
                         placeholder="如 2019" :disabled="saving" />
                </label>
                <label class="mmd-field">
                  <span>地区</span>
                  <select v-model="form.regionCode" class="adm-select" :disabled="saving">
                    <option value="">（未填）</option>
                    <option v-for="r in PAPER_REGIONS" :key="r.code" :value="r.code">{{ r.name }}</option>
                  </select>
                </label>
                <label class="mmd-field">
                  <span>卷别</span>
                  <select v-model="form.bookKind" class="adm-select" :disabled="saving">
                    <option value="">（未填）</option>
                    <option v-for="k in BOOK_KINDS" :key="k.code" :value="k.code">{{ k.name }}</option>
                  </select>
                </label>
                <label class="mmd-field">
                  <span>第几卷</span>
                  <input v-model.number="form.volume" class="adm-input" type="number" min="1" max="20"
                         placeholder="可空" :disabled="saving" />
                </label>
                <label class="mmd-field">
                  <span>题量</span>
                  <input v-model.number="form.questionCount" class="adm-input" type="number" min="1" max="500"
                         :placeholder="examHint('question_count')" :disabled="saving" />
                </label>
                <label class="mmd-field">
                  <span>总分</span>
                  <input v-model.number="form.totalScore" class="adm-input" type="number" min="0.5" max="1000"
                         step="0.5" :placeholder="examHint('total_score')" :disabled="saving" />
                </label>
                <label class="mmd-field">
                  <span>时长（分钟）</span>
                  <input v-model.number="form.duration" class="adm-input" type="number" min="1" max="600"
                         :placeholder="examHint('duration')" :disabled="saving" />
                </label>
              </div>
              <p class="mmd-tip">
                关联可作答卷：<b v-if="paper?.exam_paper_id">#{{ paper.exam_paper_id }}
                （{{ paper.answerable ? '已发布，学生可考' : '未发布' }}）</b>
                <span v-else>题库里还没有这套卷</span>
                · 题量/总分/时长留空时用可作答卷的值
              </p>

              <div class="mmd-sub">原件</div>
              <div class="mmd-files">
                <span v-for="f in files" :key="f.file_id" class="mmd-file">
                  {{ f.file_name }}（{{ f.role_label }} · {{ f.size_label }}）
                  <button
                    class="mmd-file__del"
                    type="button"
                    :disabled="saving || deletingId === f.file_id"
                    :title="`删除原件 ${f.file_name}`"
                    @click="removeFile(f)"
                  >
                    {{ deletingId === f.file_id ? '删除中…' : '删除' }}
                  </button>
                </span>
                <span v-if="!files.length" class="mmd-tip">还没有原件</span>
                <input
                  ref="fileInput"
                  class="mmd-file-input"
                  type="file"
                  accept=".docx,.doc,.pdf"
                  @change="onAttach"
                />
                <button class="adm-btn adm-btn--line adm-btn--sm" type="button"
                        :disabled="saving || uploading" @click="fileInput?.click()">
                  {{ uploading ? `上传中… ${uploadPercent}%` : '上传原件' }}
                </button>
              </div>
            </template>

            <p v-if="saveError" class="mmd-error">{{ saveError }}</p>
          </template>
        </div>

        <footer class="mmd-foot">
          <span class="mmd-foot__hint">{{ footHint }}</span>
          <button class="adm-btn adm-btn--line" type="button" :disabled="saving" @click="close">取消</button>
          <button class="adm-btn adm-btn--primary" type="button" :disabled="!canSave" @click="save">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * 「改信息」弹窗（C2b，2026-11-08）
 *
 * 解决三件事：
 *   1. 文件名解析不出年份/地区时，管理员手工补；
 *   2. 解析错了能改（订正优先级高于解析，见后端 `paper_meta_edit`）；
 *   3. 给已有资料**补原件**（这 2 套真题目前只有题库里的题、没有 PDF 原卷）。
 *
 * 数据：打开时拉一次 `fetchMaterialPreview(id)` 取当前值（含合并后的 paper 区块），
 * 保存走 `PATCH /admin/{id}/meta`；上传原件复用 B2 的 `uploadMaterialFile`（带 materialId）。
 * 组件**不自己判断业务**：范围校验以后端为准，400 的原因原样弹出来。
 */
import { computed, reactive, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import {
  deleteMaterialFile,
  fetchMaterialPreview,
  updateMaterialMeta,
  uploadMaterialFile,
  type MaterialFileItem,
  type LibrarySubject,
  type MaterialPreview
} from '@/modules/library/api';
import { BOOK_KINDS, PAPER_REGIONS } from '@/utils/paperRegions';
import { errorMessage } from '@/utils/apiError';
import { confirmOverlay, notify } from '@/utils/overlay';

const props = withDefaults(
  defineProps<{
    open: boolean;
    materialId: number | null;
    typeLabel?: string;
    subject?: LibrarySubject;
  }>(),
  { typeLabel: '资料', subject: 'gongzhuan' }
);

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'saved', payload: { id: number; title: string; category: string | null }): void;
}>();

const loading = ref(false);
const saving = ref(false);
const uploading = ref(false);
const deletingId = ref<number | null>(null);
const uploadPercent = ref(0);
const loadError = ref('');
const saveError = ref('');
const preview = ref<MaterialPreview | null>(null);
const files = ref<MaterialFileItem[]>([]);
const fileInput = ref<HTMLInputElement | null>(null);

const form = reactive({
  title: '',
  category: '',
  paperCode: '',
  year: null as number | null,
  regionCode: '',
  bookKind: '',
  volume: null as number | null,
  questionCount: null as number | null,
  totalScore: null as number | null,
  duration: null as number | null
});

const isPaper = computed(() => preview.value?.type === 'paper');
const paper = computed(() => preview.value?.paper || null);

const canSave = computed(() => !loading.value && !saving.value && !!preview.value && form.title.trim().length > 0);

const footHint = computed(() => {
  if (saving.value) return '保存中…';
  if (!isPaper.value) return '只改标题与分类';
  return '编号留空时，若年份+地区齐全会按规则自动生成';
});

/** 题量/总分/时长的占位符：提示"留空就用可作答卷的值" */
function examHint(field: 'question_count' | 'total_score' | 'duration'): string {
  const p = paper.value;
  if (!p) return '';
  const source = p.source?.[field];
  const value = p[field];
  if (source === 'exam' && value != null) return `可作答卷：${value}`;
  return '';
}

function fillFromPreview(pv: MaterialPreview): void {
  preview.value = pv;
  files.value = pv.files || [];
  form.title = pv.title || '';
  form.category = pv.category || '';
  const p = pv.paper;
  form.paperCode = p?.paper_code || '';
  // 只回填**订正过的**值：解析出来的值不回填，避免"保存一次就把解析值固化成订正"
  const rawMeta = (p?.override || {}) as Record<string, unknown>;
  form.year = (rawMeta.year as number) ?? null;
  form.regionCode = (rawMeta.region_code as string) ?? '';
  form.bookKind = (rawMeta.book_kind as string) ?? '';
  form.volume = (rawMeta.volume as number) ?? null;
  form.questionCount = (rawMeta.question_count as number) ?? null;
  form.totalScore = (rawMeta.total_score as number) ?? null;
  form.duration = (rawMeta.duration as number) ?? null;
}

async function load(): Promise<void> {
  if (props.materialId == null) return;
  loading.value = true;
  loadError.value = '';
  saveError.value = '';
  try {
    fillFromPreview(await fetchMaterialPreview(props.materialId));
  } catch (e) {
    loadError.value = errorMessage(e, '加载失败');
  } finally {
    loading.value = false;
  }
}

watch(
  () => [props.open, props.materialId],
  ([open]) => {
    if (open && props.materialId != null) void load();
  },
  { immediate: true }
);

async function save(): Promise<void> {
  if (!canSave.value || props.materialId == null) return;
  saving.value = true;
  saveError.value = '';
  try {
    const res = await updateMaterialMeta(props.materialId, {
      title: form.title.trim(),
      category: form.category.trim() || null,
      paper_code: form.paperCode.trim(),
      ...(isPaper.value
        ? {
            year: form.year ?? null,
            region_code: form.regionCode || null,
            book_kind: form.bookKind || null,
            volume: form.volume ?? null,
            question_count: form.questionCount ?? null,
            total_score: form.totalScore ?? null,
            duration: form.duration ?? null
          }
        : {})
    });
    notify('success', res.changed.length ? `已保存：${res.changed.join('、')}` : '没有变化');
    emit('saved', {
      id: res.material.id,
      title: res.material.title,
      category: res.material.category
    });
  } catch (e) {
    saveError.value = errorMessage(e, '保存失败');
  } finally {
    saving.value = false;
  }
}

/**
 * 删除单份原件（C2b 补漏的能力）。
 *
 * 为什么二次确认：原件删了之后**没有回收站**（物理文件在无其他引用时一并删除），
 * 误删只能重新上传；这类不可逆操作必须让管理员看清要删哪个文件。
 */
async function removeFile(file: MaterialFileItem): Promise<void> {
  if (props.materialId == null || deletingId.value !== null) return;
  const ok = await confirmOverlay(
    `即将删除原件「${file.file_name}」（${file.role_label} · ${file.size_label}）。\n` +
      '删除后不可恢复；若仍被其它资料引用，物理文件会保留。',
    '删除原件',
    { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
  ).catch(() => false);
  if (!ok) return;

  deletingId.value = file.file_id;
  try {
    const res = await deleteMaterialFile(props.materialId, file.file_id);
    files.value = res.files;
    notify('success', res.deleted.physical_deleted ? '原件已删除（物理文件已清理）' : '原件已删除');
  } catch (e) {
    notify('error', errorMessage(e, '删除失败'));
  } finally {
    deletingId.value = null;
  }
}

async function onAttach(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file || props.materialId == null) return;
  uploading.value = true;
  uploadPercent.value = 0;
  try {
    const res = await uploadMaterialFile({
      file,
      subject: props.subject,
      type: (preview.value?.type === 'paper' ? 'paper' : 'lecture'),
      materialId: props.materialId,
      onProgress: (p) => { uploadPercent.value = p; }
    });
    if (res.duplicate) {
      notify('info', '这份原件已经存在（内容重复），没有重复上传');
    } else {
      notify('success', '原件已上传');
      await load();
    }
  } catch (err) {
    notify('error', errorMessage(err, '上传失败'));
  } finally {
    uploading.value = false;
    if (fileInput.value) fileInput.value.value = '';
  }
}

function close(): void {
  if (saving.value) return;
  emit('close');
}

defineExpose({ load, save });
</script>

<style scoped>
.mmd-root { position: fixed; inset: 0; z-index: 3100; font-family: var(--adm-font); }
.mmd-mask { position: absolute; inset: 0; background: rgba(16, 24, 40, 0.45); }
.mmd-panel {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: min(760px, calc(100vw - 48px));
  max-height: calc(100vh - 80px);
  display: flex;
  flex-direction: column;
  background: var(--adm-surface);
  border-radius: var(--adm-r-card);
  box-shadow: 0 24px 64px rgba(16, 24, 40, 0.28);
  overflow: hidden;
}
.mmd-head {
  display: flex;
  justify-content: space-between;
  gap: var(--adm-s3);
  padding: 16px 20px;
  border-bottom: 1px solid var(--adm-line);
}
.mmd-title { margin: 0 0 4px; font-size: 16px; color: var(--adm-text); }
.mmd-desc { margin: 0; font-size: 12px; line-height: 1.7; color: var(--adm-text-weak); }
.mmd-x { border: 0; background: transparent; font-size: 20px; line-height: 1; cursor: pointer; color: var(--adm-text-weak); }
.mmd-body { padding: 14px 20px; overflow: auto; }
.mmd-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px 14px; }
.mmd-field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--adm-text-mid); }
.mmd-field--wide { grid-column: span 2; }
.mmd-sub {
  margin: 16px 0 8px;
  font-size: 12px;
  font-weight: 800;
  color: var(--adm-text-sub);
}
.mmd-mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.mmd-tip { margin: 8px 0 0; font-size: 11.5px; color: var(--adm-text-weak); line-height: 1.7; }
.mmd-files { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 12px; }
.mmd-file {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 3px 8px;
  border-radius: var(--adm-r-tag);
  background: var(--adm-bg);
  color: var(--adm-text-mid);
}
.mmd-file__del {
  border: 0;
  background: transparent;
  padding: 0 2px;
  color: var(--adm-danger);
  font-size: 11.5px;
  font-weight: 700;
  cursor: pointer;
}
.mmd-file__del:disabled { color: var(--adm-text-weak); cursor: default; }
.mmd-file-input { display: none; }
.mmd-error {
  margin: 10px 0 0;
  padding: 8px 12px;
  border: 1px solid #f3c4ae;
  border-radius: var(--adm-r-ctl);
  background: var(--adm-danger-weak);
  color: var(--adm-danger);
  font-size: 12px;
}
.mmd-foot {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-top: 1px solid var(--adm-line);
  background: var(--adm-bg);
}
.mmd-foot__hint { flex: 1; font-size: 12px; color: var(--adm-text-weak); }
</style>
