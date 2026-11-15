<template>
  <Teleport to="body">
    <div v-if="open" class="pd-root" role="dialog" aria-modal="true" aria-label="导题确认">
      <div class="pd-mask" @click="close" />
      <section class="pd-panel">
        <header class="pd-head">
          <div class="pd-head__main">
            <h2 class="pd-title">
              导题确认
              <span class="pd-mono">{{ detail?.paper_code || '无编号' }}</span>
            </h2>
            <p class="pd-desc">
              {{ detail?.title || `资料 #${materialId}` }}
              · 拆出 <b>{{ items.length }}</b> 题
              <template v-if="detail?.source_ext"> · 来源 {{ detail.source_ext.toUpperCase() }}</template>
              <template v-if="detail?.expires_at"> · 草稿保留至 {{ detail.expires_at.slice(0, 10) }}</template>
            </p>
          </div>
          <button class="pd-x" type="button" :disabled="isBusy" @click="close">×</button>
        </header>

        <div class="pd-warn" v-if="warnings.length">
          <b>体检提示</b>
          <ul><li v-for="(w, k) in warnings" :key="k">{{ w }}</li></ul>
        </div>

        <!-- P3（2026-11-13）：扫描件异步导题 —— 进度可见，完成前不能确认 -->
        <div v-if="parsing" class="pd-parsing" role="status">
          <b>扫描件 OCR 解析中</b>
          <span class="pd-parsing__text">{{ progressText }}</span>
          <span class="pd-parsing__hint">完成后会自动出现逐题清单（这一步可能要几分钟），先别关抽屉。</span>
        </div>

        <div class="pd-tools">
          <label class="pd-check">
            <input v-model="onlyFlagged" type="checkbox" />
            只看有标记的（{{ flaggedCount }}）
          </label>
          <span class="pd-tools__hint">
            入库后题目挂在卷 {{ detail?.paper_code || '—' }} 上；答案按决策⑤暂不导入（P4 补）。
          </span>
        </div>

        <div class="pd-body">
          <p v-if="loading" class="adm-empty">加载中…</p>
          <p v-else-if="loadError" class="pd-error">{{ loadError }}</p>
          <template v-else>
            <article v-for="(it, idx) in visibleItems" :key="`${it.no}-${idx}`" class="pd-item">
              <div class="pd-item__head">
                <label class="pd-no">
                  #<input v-model.number="it.no" type="number" min="1" max="999" :disabled="isBusy" />
                </label>
                <select v-model="it.type" class="adm-select pd-type" :disabled="isBusy">
                  <option value="单选">单选</option>
                  <option value="多选">多选</option>
                  <option value="判断">判断</option>
                </select>
                <span v-if="it.section" class="pd-tag pd-tag--info">情境组 {{ it.section }}</span>
                <span v-if="it.images.length" class="pd-tag pd-tag--img">
                  图 {{ it.images.length }}
                </span>
                <span v-for="(f, k) in it.flags" :key="k" class="pd-tag pd-tag--warn">{{ f }}</span>
                <button class="pd-del" type="button" :disabled="isBusy" @click="removeItem(idx)">删</button>
              </div>
              <textarea v-model="it.stem" class="adm-input pd-stem" rows="2" :disabled="isBusy" />
              <div v-if="it.shared" class="pd-shared">
                <span class="pd-shared__label">情境材料</span>
                <span class="pd-shared__text">{{ it.shared.slice(0, 120) }}{{ it.shared.length > 120 ? '…' : '' }}</span>
              </div>
              <div class="pd-opts">
                <label v-for="key in OPTION_KEYS" :key="key" class="pd-opt">
                  <b>{{ key }}</b>
                  <input v-model="it.options[key]" class="adm-input" :disabled="isBusy" />
                </label>
              </div>
              <div v-if="it.images.length" class="pd-imgs">
                <span v-for="img in it.images" :key="img.name" class="pd-img">
                  {{ img.name }}<template v-if="img.width"> · {{ img.width }}×{{ img.height }}</template>
                </span>
              </div>
            </article>
            <p v-if="!visibleItems.length" class="adm-empty">{{ emptyHint }}</p>
          </template>
        </div>

        <footer class="pd-foot">
          <span class="pd-foot__hint">{{ footHint }}</span>
          <button class="adm-btn adm-btn--line" type="button" :disabled="isBusy" @click="close">取消</button>
          <button class="adm-btn adm-btn--danger" type="button" :disabled="isBusy || !canEdit" @click="discard">放弃草稿</button>
          <button class="adm-btn adm-btn--line" type="button" :disabled="isBusy || !canEdit" @click="save">
            {{ busy === 'save' ? '保存中…' : '保存修改' }}
          </button>
          <button class="adm-btn adm-btn--primary" type="button" :disabled="isBusy || !canEdit" @click="confirm">
            {{ busy === 'confirm' ? '入库中…' : '确认入库' }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * 导题确认抽屉（P3，2026-11-09）。
 *
 * 它存在的唯一理由：**自动拆题会错，而错题会让整套卷失真**。
 * 所以把"看一眼、改一下、再入库"做成必经的一步：
 *   · 显示体检提示（缺号 / 选项不全 / 依赖图 / 有图待核对）；
 *   · 每题可改题号、改题型、删掉误拆的"题"；
 *   · 「确认入库」才写 `question_bank` 并挂卷（图片此时才复制到 static/）；
 *   · 卷里已有题目时后端会 409，需要再点一次（带 replace），二次确认避免误覆盖。
 *
 * 弹层为什么手写：Element Plus 在本项目按需引入，`el-dialog` 全局不存在（实测渲染成未知元素）。
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import {
  confirmParseDraft,
  discardParseDraft,
  fetchParseDraft,
  saveParseDraftItems,
  type ParseDraftDetail,
  type ParseDraftItem
} from '@/modules/library/api';
import { errorMessage } from '@/utils/apiError';
import { confirmOverlay } from '@/utils/overlay';

const props = defineProps<{
  open: boolean;
  draftId: number | null;
  materialId?: number | null;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'confirmed', payload: { draftId: number; created: number }): void;
  (e: 'discarded', payload: { draftId: number }): void;
}>();

const loading = ref(false);
const loadError = ref('');
/** 选项键固定 A–D（题库只有四选一；E 及以后视为正文，见 splitter） */
const OPTION_KEYS = ['A', 'B', 'C', 'D'] as const;
const detail = ref<ParseDraftDetail | null>(null);
const items = ref<ParseDraftItem[]>([]);
const onlyFlagged = ref(false);
const busy = ref<'' | 'save' | 'confirm' | 'discard'>('');
/** 模板里 `:disabled` 要布尔值（`'' | 'save'` 不是 Booleanish，vue-tsc 会拦） */
const isBusy = computed(() => busy.value !== '');

const warnings = computed(() => detail.value?.warnings || []);
/** P3：扫描件异步导题 —— parsing 时轮询，直到 pending/failed */
const parsing = computed(() => detail.value?.status === 'parsing');
const progressText = computed(() => (detail.value?.message || 'OCR 解析中…'));
let pollTimer: number | null = null;
let pollDeadline = 0;

function stopPolling(): void {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer);
    pollTimer = null;
  }
}

function startPollingIfNeeded(): void {
  stopPolling();
  if (!parsing.value) return;
  pollDeadline = Date.now() + 15 * 60 * 1000;      // 最多轮询 15 分钟
  pollTimer = window.setInterval(async () => {
    if (!props.open || Date.now() > pollDeadline) {
      stopPolling();
      return;
    }
    await load();
    if (!parsing.value) stopPolling();
  }, 2500);
}
const canEdit = computed(() => Boolean(detail.value?.can_edit));
const flaggedCount = computed(() => items.value.filter((i) => i.flags?.length).length);
const visibleItems = computed(() =>
  onlyFlagged.value ? items.value.filter((i) => i.flags?.length) : items.value
);
const footHint = computed(() => {
  if (!detail.value) return '';
  if (!canEdit.value) return `草稿状态「${detail.value.status}」，不能再编辑`;
  const missing = items.value.filter((i) => !String(i.stem || '').trim()).length;
  if (missing) return `有 ${missing} 题题干为空，保存前请补上`;
  if (onlyFlagged.value) return `正在只看 ${flaggedCount.value} 题有标记的`;
  return `共 ${items.value.length} 题 · 确认后学生才能考这张卷`;
});
/** 空清单的说明：解析中不能说「都被过滤了」，那会让管理员以为没识别到东西 */
const emptyHint = computed(() => {
  if (parsing.value) return '扫描件正在 OCR，识别完会在这里逐题列出来（先别关抽屉）';
  if (onlyFlagged.value && items.value.length) return '这 ' + items.value.length + ' 题都没有标记';
  return '没有可显示的题目（可能都被过滤了）';
});

watch(
  () => [props.open, props.draftId],
  async () => {
    if (!props.open || props.draftId == null) return;
    await load();
  },
  { immediate: true }
);

onBeforeUnmount(stopPolling);

async function load(): Promise<void> {
  loading.value = true;
  loadError.value = '';
  try {
    const data = await fetchParseDraft(props.draftId as number);
    detail.value = data;
    // 深拷贝：直接绑到 data.items 上会让"取消"也改到原对象（同一引用）
    items.value = (data.items || []).map((it) => ({
      ...it,
      options: {
        A: it.options?.A || '',
        B: it.options?.B || '',
        C: it.options?.C || '',
        D: it.options?.D || ''
      },
      flags: [...(it.flags || [])]
    }));
    if (data.status === 'failed') loadError.value = data.message || '解析失败，请重新解析';
    startPollingIfNeeded();
  } catch (e) {
    loadError.value = errorMessage(e, '草稿加载失败');
  } finally {
    loading.value = false;
  }
}

function removeItem(idx: number): void {
  const target = visibleItems.value[idx];
  const pos = items.value.indexOf(target);
  if (pos >= 0) items.value.splice(pos, 1);
}

async function save(): Promise<boolean> {
  if (props.draftId == null) return false;
  busy.value = 'save';
  try {
    await saveParseDraftItems(props.draftId, items.value);
    ElMessage.success('已保存修改');
    await load();
    return true;
  } catch (e) {
    ElMessage.error(errorMessage(e, '保存失败'));
    return false;
  } finally {
    busy.value = '';
  }
}

async function confirm(): Promise<void> {
  if (props.draftId == null) return;
  const dup = new Set<number>();
  for (const it of items.value) {
    if (dup.has(it.no)) {
      ElMessage.error(`题号重复：${it.no}（先改掉再入库）`);
      return;
    }
    dup.add(it.no);
  }
  try {
    // D10（2026-11-15）：没有可作答卷时不再让入库卡死 —— 后端会自动建一张草稿卷，
    // 这里先把"会自动建卷"说清楚，免得管理员以为挂到了什么卷上。
    const codeText = detail.value?.paper_code
      ? `挂到卷 ${detail.value.paper_code}`
      : '挂到本资料的可作答卷（还没有 → 入库时自动建一张草稿卷）';
    await confirmOverlay(
      `将把 ${items.value.length} 道题写进题库并${codeText}。\n`
        + '图片会同时复制到正式目录。入库后可在题库里改题/补答案。确认入库？',
      '确认入库',
      { confirmButtonText: '确认入库', cancelButtonText: '再看看', type: 'success' }
    );
  } catch {
    return;
  }
  busy.value = 'confirm';
  try {
    // 先保存（把改过的题号/题型落库），再确认 —— 避免"改了但没保存就入库"
    await saveParseDraftItems(props.draftId, items.value);
    let result;
    try {
      result = await confirmParseDraft(props.draftId, {});
    } catch (e) {
      const msg = errorMessage(e, '入库失败');
      if (!msg.includes('已有')) throw e;
      // 卷里已有题目 → 明确问一次要不要覆盖
      await confirmOverlay(
        `${msg}\n\n覆盖会**删掉旧题与本卷的关联**（题目本体保留，可在题库里找到）。确定覆盖？`,
        '覆盖已有题目',
        { confirmButtonText: '覆盖入库', cancelButtonText: '取消', type: 'warning' }
      );
      result = await confirmParseDraft(props.draftId, { replace: true });
    }
    // D10：入库时自动建过卷 → 明确告诉管理员编号与"还需上架"
    const auto = result.paper_auto_created
      ? `（已自动建卷 ${result.paper_code || ''}，草稿；把资料上架，学生才能考）`
      : '';
    ElMessage.success(`已入库 ${result.created} 题 → 卷 #${result.paper_id}${auto}`);
    emit('confirmed', { draftId: props.draftId, created: result.created });
  } catch (e) {
    ElMessage.error(errorMessage(e, '入库失败'));
  } finally {
    busy.value = '';
  }
}

async function discard(): Promise<void> {
  if (props.draftId == null) return;
  try {
    await confirmOverlay('放弃后这份解析结果和草稿图片会被删掉（不影响已入库的题目）。确认放弃？',
      '放弃草稿', { confirmButtonText: '放弃', cancelButtonText: '取消', type: 'warning' });
  } catch {
    return;
  }
  busy.value = 'discard';
  try {
    await discardParseDraft(props.draftId);
    ElMessage.success('已放弃这份草稿');
    emit('discarded', { draftId: props.draftId });
  } catch (e) {
    ElMessage.error(errorMessage(e, '放弃失败'));
  } finally {
    busy.value = '';
  }
}

function close(): void {
  if (busy.value) return;
  emit('close');
}
</script>

<style scoped>
.pd-parsing {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
  margin: 0 16px 10px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #fff8e6;
  border: 1px solid #ffe1a8;
  color: #8a5a00;
  font-size: 13px;
}
.pd-parsing b { color: #b26a00; }
.pd-parsing__text { font-variant-numeric: tabular-nums; }
.pd-parsing__hint { color: #a07a2a; font-size: 12px; }

.pd-root {
  position: fixed;
  inset: 0;
  z-index: 2700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.pd-mask {
  position: absolute;
  inset: 0;
  background: rgba(16, 24, 40, 0.42);
}
.pd-panel {
  position: relative;
  width: 980px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: var(--adm-r-card, 12px);
  box-shadow: 0 18px 48px rgba(16, 24, 40, 0.18);
  font-family: var(--adm-font);
}
.pd-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px 10px;
  border-bottom: 1px solid var(--adm-line, #eef1f6);
}
.pd-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--adm-text);
  display: flex;
  align-items: center;
  gap: 8px;
}
.pd-mono { font-family: var(--adm-mono, monospace); font-size: 12px; color: var(--adm-text-sub); }
.pd-desc { margin: 6px 0 0; font-size: 11.5px; color: var(--adm-text-sub); line-height: 1.6; }
.pd-x {
  border: none; background: transparent; font-size: 20px; line-height: 1;
  color: var(--adm-text-weak, #93a0b5); cursor: pointer;
}
.pd-warn {
  margin: 10px 18px 0;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--adm-warn-weak, #fff7e8);
  border: 1px solid #f3ddb3;
  font-size: 11.5px;
  color: #8a5a00;
}
.pd-warn ul { margin: 4px 0 0; padding-left: 18px; }
.pd-tools {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 18px;
}
.pd-check { font-size: 11.5px; color: var(--adm-text-mid); display: flex; align-items: center; gap: 6px; }
.pd-tools__hint { font-size: 11px; color: var(--adm-text-weak); }
.pd-body { padding: 0 18px 8px; overflow: auto; flex: 1; }
.pd-item {
  border: 1px solid var(--adm-line, #eef1f6);
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 10px;
  background: #fcfdff;
}
.pd-item__head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.pd-no { font-size: 12px; font-weight: 700; color: var(--adm-text-mid); display: flex; align-items: center; gap: 4px; }
.pd-no input {
  width: 56px;
  padding: 3px 6px;
  border: 1px solid var(--adm-line, #dfe4f0);
  border-radius: 6px;
  font-family: var(--adm-mono, monospace);
  font-size: 12px;
}
.pd-type { width: 76px; padding: 3px 6px; font-size: 12px; }
.pd-tag {
  font-size: 10.5px;
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--adm-muted-weak, #eef1f6);
  color: var(--adm-text-sub);
}
.pd-tag--warn { background: #fff2e2; color: #b4620a; }
.pd-tag--img { background: #eaf2ff; color: #2f6fd0; }
.pd-tag--info { background: #eef6ff; color: #2f6fd0; }
.pd-del {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--adm-danger, #d9463b);
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
}
.pd-stem { width: 100%; resize: vertical; font-size: 12px; line-height: 1.6; }
.pd-shared { margin-top: 6px; font-size: 11px; color: var(--adm-text-sub); }
.pd-shared__label {
  display: inline-block; margin-right: 6px; padding: 1px 6px; border-radius: 4px;
  background: #eef6ff; color: #2f6fd0; font-weight: 600;
}
.pd-opts { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 6px; }
.pd-opt { display: flex; align-items: center; gap: 6px; }
.pd-opt b { width: 12px; font-size: 11.5px; color: var(--adm-text-mid); }
.pd-opt input { width: 100%; font-size: 12px; padding: 4px 8px; }
.pd-imgs { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 6px; }
.pd-img { font-size: 10.5px; color: #2f6fd0; background: #eaf2ff; padding: 2px 6px; border-radius: 4px; }
.pd-error { color: var(--adm-danger, #d9463b); font-size: 12px; }
.pd-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px 16px;
  border-top: 1px solid var(--adm-line, #eef1f6);
}
.pd-foot__hint { flex: 1; font-size: 11px; color: var(--adm-text-weak, #93a0b5); }
.adm-btn--danger {
  background: var(--adm-danger-weak, #fdeceb);
  color: var(--adm-danger, #d9463b);
  border-color: #f3d3c2;
}
</style>
