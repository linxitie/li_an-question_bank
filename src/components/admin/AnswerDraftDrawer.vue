<template>
  <Teleport to="body">
    <div v-if="open" class="ad-root" role="dialog" aria-modal="true" aria-label="补答案">
      <div class="ad-mask" @click="close" />
      <section class="ad-panel">
        <header class="ad-head">
          <div>
            <h2 class="ad-title">
              补答案
              <span class="ad-mono">{{ paperCode || '—' }}</span>
              <span v-if="ocrDraft" class="ad-badge">扫描件 OCR</span>
            </h2>
            <p class="ad-desc">
              {{ paperName || `卷 #${paperId}` }} · 现有答案素材都是 PDF，**PDF 是一等通道**
              （实测 4 套卷 397/397 题号、答案自动识别 397/397）。写入前一律先预览。
            </p>
          </div>
          <button class="ad-x" type="button" :disabled="busy !== ''"  @click="close">×</button>
        </header>

        <!-- 1. 上传 -->
        <div v-if="!draft" class="ad-body">
          <div
            class="ad-drop"
            :class="{ 'is-over': dragOver }"
            @click="fileInput?.click()"
            @dragover.prevent="dragOver = true"
            @dragleave.prevent="dragOver = false"
            @drop.prevent="onDrop"
          >
            <b>把答案文件拖进来，或点这里选文件</b>
            <span>支持 PDF / docx / xlsx / 纯文本（一行一题：`1 A`）；也可以传空模板只补解析</span>
            <input
              ref="fileInput"
              class="ad-file"
              type="file"
              accept=".pdf,.docx,.xlsx,.xls,.txt,.csv"
              @change="onPick"
            />
          </div>
          <p v-if="uploading" class="ad-hint">上传中… {{ percent }}%（文字版 1–2 秒；扫描件转后台 OCR，进度显示在抽屉里）</p>
          <p v-if="error" class="ad-error">{{ error }}</p>
          <p class="ad-note">
            解析只生成草稿，**不会改题库**；下一屏逐题看过后点「确认写入」才生效。
          </p>
        </div>

        <!-- 2. 预览 -->
        <template v-else>
          <!-- P4（2026-11-13）：扫描件在后台 OCR，进度写 draft.message；完成自动出表 -->
          <div v-if="parsing" class="ad-parsing" role="status">
            <b>扫描件 OCR 解析中</b>
            <span class="ad-parsing__text">{{ progressText }}</span>
            <span class="ad-parsing__hint">完成后会自动列出答案（这一步可能要几分钟），先别关抽屉。</span>
          </div>
          <div v-else-if="ocrDraft" class="ad-warn">
            这是扫描件 OCR 出来的答案：<b>答案字母可能认错</b>（尤其 A/D、B/8），
            请逐题核对后再点「确认写入」。
          </div>
          <div class="ad-stats">
            <span><i>识别答案</i><b class="is-ok">{{ filledCount }} / {{ items.length }}</b></span>
            <span><i>需确认</i><b :class="draft.conflict_count ? 'is-warn' : 'is-ok'">{{ draft.conflict_count }}</b></span>
            <span><i>无答案</i><b :class="draft.empty_count ? 'is-warn' : 'is-ok'">{{ draft.empty_count }}</b></span>
            <span><i>来源</i><b>{{ (draft.source_name || '').slice(0, 18) }}</b></span>
            <label class="ad-check">
              <input v-model="onlyFlagged" type="checkbox" />
              只看需确认（{{ draft.conflict_count }}）
            </label>
          </div>

          <div class="ad-table">
            <div class="ad-row ad-row--head">
              <span>题号</span><span>题型</span><span>答案</span><span>建议</span>
              <span>来源</span><span>解析（摘要）</span><span>标记</span>
            </div>
            <div
              v-for="(it, idx) in visibleItems"
              :key="it.no"
              class="ad-row"
              :class="{ 'is-flag': it.flags?.length }"
            >
              <span class="ad-mono">{{ it.no }}</span>
              <span>{{ it.question_type || '—' }}</span>
              <span>
                <!-- 不用 v-model + @input 的组合：两者同时挂在一个原生 input 上时，
                     归一化可能读到旧值。这里手写 `:value` + 归一后写回，行为确定。 -->
                <input
                  :value="it.answer"
                  class="adm-input ad-answer"
                  maxlength="6"
                  placeholder="—"
                  :disabled="busy !== ''"
                  @input="onAnswerInput(it, $event)"
                />
              </span>
              <span>
                <button
                  v-if="it.suggestion && it.suggestion !== it.answer"
                  class="ad-adopt"
                  type="button"
                  :disabled="busy !== ''"
                  @click="adopt(it, idx)"
                >采纳 {{ it.suggestion }}</button>
                <span v-else class="ad-muted">—</span>
              </span>
              <span class="ad-muted">{{ tierLabel(it.tier) }}</span>
              <span class="ad-analysis" :title="it.analysis">{{ it.analysis || '（无解析）' }}</span>
              <span>
                <em v-for="(f, k) in it.flags" :key="k" class="ad-tag">{{ f }}</em>
                <em v-if="it.current && it.current !== it.answer" class="ad-tag ad-tag--old">
                  库中 {{ it.current }}
                </em>
              </span>
            </div>
            <p v-if="!visibleItems.length" class="adm-empty">
              <template v-if="parsing">扫描件正在 OCR，识别完会在这里逐题列出答案（先别关抽屉）</template>
              <template v-else>{{ items.length ? '没有待确认的题（可取消勾选「只看需确认」查看全部）' : '这份草稿没有可显示的题——请点「重新上传」' }}</template>
            </p>
          </div>

          <footer class="ad-foot">
            <span class="ad-foot__hint">
              写入只动「答案 + 解析」两列；库里已有不同答案默认**保留**
              <label class="ad-overwrite">
                <input v-model="overwrite" type="checkbox" :disabled="busy !== ''" />
                覆盖已有答案
              </label>
              <em v-if="zeroWriteHint" class="ad-foot__warn">{{ zeroWriteHint }}</em>
            </span>
            <button class="adm-btn adm-btn--line" type="button" :disabled="busy !== '' || parsing" @click="reset">重新上传</button>
            <button class="adm-btn adm-btn--danger" type="button" :disabled="busy !== ''" @click="discard">放弃</button>
            <button
              class="adm-btn adm-btn--primary"
              type="button"
              :disabled="busy !== '' || parsing || writableCount === 0"
              :title="zeroWriteHint || ''"
              @click="apply"
            >
              {{ busy === 'apply' ? '写入中…' : `确认写入 ${writableCount} 题` }}
            </button>
          </footer>
        </template>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * 「补答案」抽屉（P4，2026-11-09）。
 *
 * 为什么必须先预览：答案错一位，学生看到的解析就对不上，而且"错得很像对的"。
 * 用户拍板的四条都体现在这里：
 *  ① 已有答案不同 → 默认保留，要覆盖得勾选（底部复选框）；
 *  ② 推断层只给「采纳」按钮，不自动填；
 *  ③ 解析正文会跟答案一起入库（表格里能看摘要）；
 *  ④ 只按卷上传，不做文件名自动匹配（入口就在具体那一行卷上）。
 */
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import {
  applyAnswerDraft,
  discardAnswerDraft,
  fetchAnswerDraft,
  fetchLatestAnswerDraft,
  parseAnswerFile,
  saveAnswerDraftItems,
  type AnswerDraftDetail,
  type AnswerDraftItem
} from '@/modules/library/api';
import { countAnswered, countDiffering, countIdentical, countWritable } from '@/utils/answerDraft';
import { errorMessage } from '@/utils/apiError';
import { confirmOverlay } from '@/utils/overlay';

const props = defineProps<{
  open: boolean;
  paperId: number | null;
  paperCode?: string | null;
  paperName?: string | null;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'applied', payload: { paperId: number; filled: number }): void;
}>();

const fileInput = ref<HTMLInputElement | null>(null);
const dragOver = ref(false);
const uploading = ref(false);
const percent = ref(0);
const busy = ref<'' | 'apply'>('');
const error = ref('');
const draft = ref<AnswerDraftDetail | null>(null);
const items = ref<AnswerDraftItem[]>([]);
const onlyFlagged = ref(false);
const overwrite = ref(false);

// ---------------- P4 扫描件：后台 OCR 的进度与轮询（2026-11-13）----------------
const pollTimer = ref<number | null>(null);
/** 后台 OCR 中（后端 status=parsing） */
const parsing = computed(() => draft.value?.status === 'parsing');
/** 这份草稿是不是 OCR 出来的（扫描件）：parsing 阶段直接算，完成后看后端写的 message */
const ocrDraft = computed(() => {
  const d = draft.value;
  if (!d) return false;
  if (d.status === 'parsing') return true;
  return /扫描件|OCR/.test(d.message || '');
});
const progressText = computed(() => draft.value?.message || 'OCR 解析中…');

const filledCount = computed(() => items.value.filter((i) => i.answer).length);
/**
 * 本次**真正会写入**的题数（2026-11-12）。
 * 原来按钮用的是 `filledCount`（= 有答案的题数）：库里已有相同答案时仍显示 97，
 * 点下去结果却是"写入 0、保留 97"，很容易被当成"没写进去"。
 */
const writableCount = computed(() => countWritable(items.value, overwrite.value));
/** 解析里"与库里答案一致"的题数（成功提示用，讲清"为什么可写 0"） */
const identicalCount = computed(() => countIdentical(items.value));
/** 与库里**不同**的题数（勾「覆盖」才会写） */
const differingCount = computed(() => countDiffering(items.value));
/** 一句话解释"为什么按钮是 0" */
const zeroWriteHint = computed(() => {
  if (!items.value.length || writableCount.value > 0) return '';
  if (differingCount.value > 0) {
    // 有不同但没勾覆盖：这才是"勾覆盖可写"的场景
    return `${differingCount.value} 题与现有答案不同，默认保留；要替换请勾选「覆盖已有答案」`;
  }
  if (identicalCount.value) {
    return `${identicalCount.value} 题与现有答案一致，无需写入`;
  }
  return '没有可写入的答案：解析结果里答案为空';
});
const visibleItems = computed(() =>
  onlyFlagged.value ? items.value.filter((i) => i.flags?.length) : items.value
);

watch(
  () => [props.open, props.paperId],
  () => {
    if (props.open) void loadExisting();
  },
  { immediate: true }
);

/** 打开时先续上「上次没确认完」的草稿（否则关了抽屉就等于丢失待办） */
async function loadExisting(): Promise<void> {
  reset();
  if (props.paperId == null) return;
  try {
    const data = await fetchLatestAnswerDraft(props.paperId);
    if (!data?.exists) return;
    // P4：parsing 也要续上——扫描件 OCR 期间关掉抽屉再打开，应该还能看到进度
    if (data.status !== 'pending' && data.status !== 'parsing') return;
    setDraft(data);
  } catch {
    // 续不上就当新建：不打断用户
  }
}

/** 把后端回包灌进抽屉（items 归一），并按状态决定要不要开始轮询 */
function setDraft(data: AnswerDraftDetail): void {
  draft.value = data;
  items.value = (data.items || []).map((it) => ({
    ...it,
    answer: it.answer || '',
    suggestion: it.suggestion || '',
    flags: [...(it.flags || [])]
  }));
  startPollingIfNeeded();
}

function stopPolling(): void {
  if (pollTimer.value != null) {
    window.clearInterval(pollTimer.value);
    pollTimer.value = null;
  }
}

/** 扫描件在后台 OCR：每 2.5s 拉一次，完成（pending/failed）后自动停并出表 */
function startPollingIfNeeded(): void {
  stopPolling();
  const d = draft.value;
  if (!d || d.status !== 'parsing') return;
  const id = d.draft_id;
  pollTimer.value = window.setInterval(() => {
    void (async () => {
      try {
        const data = await fetchAnswerDraft(id);
        if (data.status === 'parsing') return;
        stopPolling();
        setDraft(data);
        if (data.status === 'pending') {
          ElMessage.success(`扫描件识别完成：${data.item_count} 题，请逐题核对后写入`);
        } else if (data.status === 'failed') {
          error.value = data.message || '解析失败';
        }
      } catch {
        stopPolling();            // 网络抖动就停：用户可以关掉抽屉重开，别一直打接口
      }
    })();
  }, 2500);
}

onBeforeUnmount(stopPolling);

const TIER_LABEL: Record<string, string> = {
  L0: '题号后直给', L1: '正确答案', L2: '句尾结论', L3: '推断（建议）', L4: '未识别', P: '一行一题'
};
function tierLabel(tier?: string): string {
  return TIER_LABEL[tier || ''] || (tier || '—');
}

function reset(): void {
  stopPolling();
  draft.value = null;
  items.value = [];
  error.value = '';
  percent.value = 0;
  onlyFlagged.value = false;
  overwrite.value = false;
}

function onDrop(ev: DragEvent): void {
  dragOver.value = false;
  const file = ev.dataTransfer?.files?.[0];
  if (file) void upload(file);
}

function onPick(ev: Event): void {
  const input = ev.target as HTMLInputElement;
  const file = input.files?.[0];
  if (file) void upload(file);
  input.value = '';
}

async function upload(file: File): Promise<void> {
  if (props.paperId == null) return;
  uploading.value = true;
  error.value = '';
  percent.value = 0;
  try {
    let data = await parseAnswerFile(props.paperId, file, (p) => (percent.value = p));
    if (data.status === 'failed') {
      error.value = data.message || '解析失败';
      return;
    }
    // P4：扫描件已转后台 OCR —— 立刻进「解析中」界面并开始轮询（不再干等 3–7 分钟）
    if (data.status === 'parsing') {
      setDraft(data);
      ElMessage.info('扫描件已转 OCR，正在识别…进度会显示在抽屉里');
      return;
    }
    // 2026-11-12 兜底：上传接口曾经只回 metadata（没有 items），前端就地空屏；
    // 现在后端已带 items，这里再留一道：没有就按 draft_id 补拉一次明细。
    if (!data.items?.length && data.draft_id) {
      try {
        data = await fetchAnswerDraft(data.draft_id);
      } catch {
        // 补拉失败不阻断：下面会按空表展示，用户可「重新上传」
      }
    }
    setDraft(data);
    const answered = countAnswered(items.value);
    const identical = countIdentical(items.value);
    let msg = `已解析 ${data.item_count} 题`;
    if (data.conflict_count) msg += `，${data.conflict_count} 题需确认`;
    if (identical) msg += `（其中 ${identical} 题与现有答案一致）`;
    else if (answered) msg += `（识别到 ${answered} 题答案）`;
    ElMessage.success(msg);
  } catch (e) {
    error.value = errorMessage(e, '解析失败');
  } finally {
    uploading.value = false;
  }
}

/** 输入时就地归一（只留 A–D 大写、去重、排序），避免提交时才报错 */
function onAnswerInput(it: AnswerDraftItem, ev: Event): void {
  const raw = (ev.target as HTMLInputElement).value || '';
  const letters = [...new Set(raw.toUpperCase().replace(/[^ABCD]/g, ''))].sort();
  it.answer = letters.join('');
  (ev.target as HTMLInputElement).value = it.answer;
}

function adopt(it: AnswerDraftItem, _idx: number): void {
  it.answer = it.suggestion;
  it.flags = (it.flags || []).filter((f) => f !== '仅推断建议');
}

async function apply(): Promise<void> {
  if (!draft.value) return;
  const n = writableCount.value;
  if (!n) {
    ElMessage.error(zeroWriteHint.value || '还没有任何答案可写入');
    return;
  }
  try {
    await confirmOverlay(
      `将把 ${n} 题的答案与解析写入题库（只动「答案 / 解析」两列）。\n`
        + (overwrite.value ? '已勾选覆盖：库里不同的旧答案会被替换。\n' : '已有答案默认保留，只填空位。\n')
        + '历史考试成绩不会重算。确认写入？',
      '写入答案',
      { confirmButtonText: '确认写入', cancelButtonText: '再看看', type: 'success' }
    );
  } catch {
    return;
  }
  busy.value = 'apply';
  try {
    await saveAnswerDraftItems(draft.value.draft_id, items.value);
    const result = await applyAnswerDraft(draft.value.draft_id, { overwrite: overwrite.value });
    ElMessage.success(
      `已写入 ${result.filled} 题`
      + (result.overwritten ? `、覆盖 ${result.overwritten} 题` : '')
      + (result.analysis_only ? `、仅补解析 ${result.analysis_only} 题` : '')
      + (result.kept ? `、保留原有 ${result.kept} 题` : '')
    );
    emit('applied', { paperId: draft.value.paper_id, filled: result.filled });
    draft.value = null;
    items.value = [];
  } catch (e) {
    ElMessage.error(errorMessage(e, '写入失败'));
  } finally {
    busy.value = '';
  }
}

async function discard(): Promise<void> {
  if (!draft.value) return;
  try {
    await confirmOverlay('放弃后这份解析结果会被丢弃（不影响题库里已有的答案）。确认放弃？',
      '放弃答案草稿', { confirmButtonText: '放弃', cancelButtonText: '取消', type: 'warning' });
  } catch {
    return;
  }
  try {
    await discardAnswerDraft(draft.value.draft_id);
    ElMessage.success('已放弃');
    reset();
  } catch (e) {
    ElMessage.error(errorMessage(e, '放弃失败'));
  }
}

function close(): void {
  if (busy.value) return;
  emit('close');
}
</script>

<style scoped>
.ad-root {
  position: fixed;
  inset: 0;
  z-index: 2700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.ad-mask {
  position: absolute;
  inset: 0;
  background: rgba(16, 24, 40, 0.42);
}
.ad-panel {
  position: relative;
  width: 1080px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 48px);
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: var(--adm-r-card, 12px);
  box-shadow: 0 18px 48px rgba(16, 24, 40, 0.18);
  font-family: var(--adm-font);
}
.ad-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 18px 10px;
  border-bottom: 1px solid var(--adm-line, #eef1f6);
}
.ad-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--adm-text);
  display: flex;
  align-items: center;
  gap: 8px;
}
.ad-mono { font-family: var(--adm-mono, monospace); font-size: 12px; color: var(--adm-text-sub); }
/* P4：扫描件 OCR 的角标 / 进度条 / 警告条 */
.ad-badge {
  font-size: 10.5px;
  font-weight: 700;
  color: #b26a00;
  background: #fff5e6;
  border: 1px solid #f0d4a6;
  border-radius: 999px;
  padding: 1px 8px;
}
.ad-parsing {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin: 10px 18px 0;
  padding: 9px 12px;
  background: #fff8e8;
  border: 1px solid #f3d79b;
  border-radius: 8px;
  color: #8a5a00;
  font-size: 12px;
}
.ad-parsing b { color: #b26a00; }
.ad-parsing__text { font-variant-numeric: tabular-nums; font-weight: 700; }
.ad-parsing__hint { color: #a07a2a; font-size: 11px; }
.ad-warn {
  margin: 10px 18px 0;
  padding: 8px 12px;
  background: #fff8e8;
  border: 1px solid #f3d79b;
  border-radius: 8px;
  color: #8a5a00;
  font-size: 11.5px;
  line-height: 1.6;
}
.ad-desc { margin: 6px 0 0; font-size: 11.5px; color: var(--adm-text-sub); line-height: 1.65; }
.ad-x { border: none; background: transparent; font-size: 20px; color: var(--adm-text-weak, #93a0b5); cursor: pointer; }
.ad-body { padding: 16px 18px; }
.ad-drop {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 22px;
  border: 1.5px dashed #c7d3f5;
  border-radius: 10px;
  background: #f7f9ff;
  cursor: pointer;
  font-size: 12px;
  color: var(--adm-text-sub);
}
.ad-drop b { font-size: 13.5px; color: var(--adm-primary, #4054e0); }
.ad-drop.is-over { background: #eef3ff; border-color: var(--adm-primary, #4054e0); }
.ad-file { display: none; }
.ad-hint { margin: 10px 0 0; font-size: 11.5px; color: var(--adm-text-sub); }
.ad-error { margin: 10px 0 0; font-size: 12px; color: var(--adm-danger, #d9463b); }
.ad-note { margin: 12px 0 0; font-size: 11px; color: var(--adm-text-weak, #93a0b5); }
.ad-stats {
  display: flex;
  align-items: center;
  gap: 18px;
  padding: 10px 18px;
  border-bottom: 1px solid var(--adm-line-soft, #f1f4fa);
  font-size: 11px;
  color: var(--adm-text-weak, #93a0b5);
  flex-wrap: wrap;
}
.ad-stats span { display: flex; align-items: center; gap: 6px; }
.ad-stats i { font-style: normal; }
.ad-stats b { font-size: 13px; color: var(--adm-text); }
.ad-stats b.is-ok { color: var(--adm-ok, #12a150); }
.ad-stats b.is-warn { color: #b4620a; }
.ad-check { margin-left: auto; display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: var(--adm-text-mid); }
.ad-table { flex: 1; overflow: auto; padding: 0 18px; }
.ad-row {
  display: grid;
  grid-template-columns: 46px 56px 84px 96px 84px 1fr 190px;
  gap: 8px;
  align-items: center;
  padding: 7px 6px;
  border-bottom: 1px solid var(--adm-line-soft, #f1f4fa);
  font-size: 12px;
  color: var(--adm-text-mid);
}
.ad-row--head {
  position: sticky;
  top: 0;
  background: #f2f5fc;
  font-size: 11px;
  font-weight: 700;
  color: var(--adm-text-sub);
  border-bottom: 1px solid #e6eaf4;
}
.ad-row.is-flag { background: #fff8f7; }
.ad-answer { width: 72px; padding: 3px 8px; font-family: var(--adm-mono, monospace); text-align: center; }
.ad-adopt {
  border: none;
  background: #eef3ff;
  color: var(--adm-primary, #4054e0);
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 999px;
  cursor: pointer;
}
.ad-muted { color: var(--adm-text-weak, #93a0b5); font-size: 11px; }
.ad-analysis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--adm-text-weak, #93a0b5);
  font-size: 11px;
}
.ad-tag {
  display: inline-block;
  margin-right: 4px;
  padding: 1px 6px;
  border-radius: 999px;
  background: #fff2e2;
  color: #b4620a;
  font-size: 10.5px;
  font-style: normal;
  font-weight: 700;
}
.ad-tag--old { background: #eef1f6; color: var(--adm-text-sub); }
.ad-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px 16px;
  border-top: 1px solid var(--adm-line, #eef1f6);
  flex-wrap: wrap;
}
.ad-foot__hint { flex: 1; font-size: 11px; color: var(--adm-text-weak, #93a0b5); }
.ad-overwrite { margin-left: 8px; color: #b4620a; font-weight: 600; }
.ad-foot__hint input { vertical-align: -1px; }
/* 2026-11-12：按钮为 0 时给一句原因，避免"坏了"的错觉 */
.ad-foot__warn {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 6px;
  border-radius: 6px;
  background: #fff4e5;
  color: #b35309;
  font-style: normal;
}
</style>
