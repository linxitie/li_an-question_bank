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
          <ul>
            <li v-for="(w, k) in warnings" :key="k">
              <!-- Q3（2026-11-15，导题缺号定位）：把「题号缺号 N 个：[46,86,92]」里的数字变成可点入口 -->
              <template v-if="missingOf(w)">
                <span>题号缺号 {{ missingOf(w)!.count }} 个：</span>
                <template v-if="canLocateQno">
                  <button
                    v-for="no in missingOf(w)!.nos"
                    :key="`mq-${no}`"
                    type="button"
                    class="pd-qno"
                    :class="{ 'pd-qno--cold': !qnoGapsAvailable }"
                    :aria-label="`查看第 ${no} 题在原卷的位置`"
                    :title="qnoGapsAvailable ? '点开看原卷那一页' : '这份草稿没有定位信息（旧版本草稿）'"
                    @click="openQno(no)"
                  >
                    {{ no }}
                  </button>
                </template>
                <span v-else>{{ missingOf(w)!.nos.join('、') }}</span>
                <span v-if="canLocateQno && !qnoGapsAvailable" class="pd-qno__hint">
                  （旧版本草稿无定位信息，重新导题后可用）
                </span>
              </template>
              <template v-else>{{ w }}</template>
            </li>
          </ul>
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

      <!-- Q3（2026-11-15，导题缺号定位）：点题号 → 原卷那一页 + 红框。
           同样手写弹层（本项目 el-dialog 未全局注册，见上方注释）。 -->
      <div v-if="qnoOpen" class="qd-root" role="dialog" aria-modal="true" :aria-label="`第 ${qnoNo} 题原卷位置`">
        <div class="qd-mask" @click="closeQno" />
        <section class="qd-panel">
          <header class="qd-head">
            <div>
              <h3 class="qd-title">
                <template v-if="qnoData">
                  原卷第 {{ qnoData.page }} 页<template v-if="qnoData.page_count"> / 共 {{ qnoData.page_count }} 页</template>
                  · 第 {{ qnoData.no }} 题应在此处
                </template>
                <template v-else>第 {{ qnoNo }} 题 · 原卷位置</template>
              </h3>
              <p class="qd-sub">
                <template v-if="qnoData">{{ qnoData.file_name }} · {{ qnoData.dpi }}dpi 单页渲染</template>
                <template v-else>正在渲染原卷页…</template>
              </p>
            </div>
            <button class="qd-x" type="button" @click="closeQno">×</button>
          </header>

          <div class="qd-body">
            <p v-if="qnoLoading" class="qd-state">正在渲染第 {{ qnoNo }} 题所在页…</p>
            <p v-else-if="qnoError" class="qd-state qd-state--error">{{ qnoError }}</p>
            <div v-else-if="qnoData" class="qd-imgwrap" :style="{ aspectRatio: `${qnoData.image_w} / ${qnoData.image_h}` }">
              <img :src="`data:image/png;base64,${qnoData.image_b64}`" :alt="`原卷第 ${qnoData.page} 页`" />
              <span
                class="qd-hl"
                :style="{
                  left: `${qnoData.highlight.x0 * 100}%`,
                  top: `${qnoData.highlight.y0 * 100}%`,
                  width: `${(qnoData.highlight.x1 - qnoData.highlight.x0) * 100}%`,
                  height: `${(qnoData.highlight.y1 - qnoData.highlight.y0) * 100}%`
                }"
              />
            </div>
            <p v-if="qnoData" class="qd-tip">红框 = 该题号在原卷应出现的位置；请对照原卷补题号，或确认原卷本身缺这道题。</p>
          </div>

          <footer class="qd-foot">
            <button class="adm-btn adm-btn--line" type="button" :disabled="qnoNos.length < 2" @click="stepQno(-1)">上一题</button>
            <button class="adm-btn adm-btn--line" type="button" :disabled="qnoNos.length < 2" @click="stepQno(1)">下一题</button>
            <button
              v-if="qnoData && qnoData.alt_page && !qnoData.on_alt_page"
              class="adm-btn adm-btn--line"
              type="button"
              @click="flipQnoPage"
            >看第 {{ qnoData.alt_page }} 页</button>
            <button
              v-else-if="qnoData && qnoData.on_alt_page && qnoData.alt_page"
              class="adm-btn adm-btn--line"
              type="button"
              @click="flipQnoPage"
            >回到第 {{ qnoData.alt_page }} 页</button>
            <span class="qd-foot__spacer" />
            <button class="adm-btn adm-btn--primary" type="button" @click="closeQno">关闭</button>
          </footer>
        </section>
      </div>
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
  fetchDraftPageImage,
  fetchParseDraft,
  saveParseDraftItems,
  type ParseDraftDetail,
  type ParseDraftItem,
  type ParseDraftPageImage
} from '@/modules/library/api';
import { errorMessage } from '@/utils/apiError';
import { parseMissingQnos, type MissingQnos } from '@/utils/qnoMissing';
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

// ---------- Q3/Q4（2026-11-15，导题缺号定位）----------
/** 缺号 chips 只在 PDF 草稿上出现（docx 没有"页"的概念，点了也定位不了） */
const canLocateQno = computed(() => (detail.value?.source_ext || '').toLowerCase() === 'pdf');
/** 后端只读标记：这份草稿有没有"缺号页坐标"（旧草稿没有 → 置灰且不发请求） */
const qnoGapsAvailable = computed(() => detail.value?.qno_gaps_available !== false);
/** 当前草稿的全部缺号（给弹窗的上一题/下一题用；取第一条命中的告警） */
const qnoNos = computed<number[]>(() => {
  for (const w of warnings.value) {
    const parsed = parseMissingQnos(w);
    if (parsed) return parsed.nos;
  }
  return [];
});
const qnoOpen = ref(false);
const qnoLoading = ref(false);
const qnoError = ref('');
const qnoNo = ref(0);
const qnoData = ref<ParseDraftPageImage | null>(null);
/** 请求令牌：快速连点多个题号时，只认最后一次的结果（避免旧结果盖新结果） */
let qnoSeq = 0;

/** 模板里对每条告警判断"是不是缺号那条"；解析不到就返回 null（按原文渲染） */
function missingOf(warning: string): MissingQnos | null {
  return parseMissingQnos(warning);
}

async function loadQno(no: number, page?: number): Promise<void> {
  const id = props.draftId;
  if (!id) return;
  qnoNo.value = no;
  qnoOpen.value = true;
  qnoLoading.value = true;
  qnoError.value = '';
  qnoData.value = null;
  const seq = ++qnoSeq;
  try {
    const data = await fetchDraftPageImage(id, no, 150, page);
    if (seq !== qnoSeq) return;                 // 已经被更新的点击接管
    if (!data?.image_b64) throw new Error('后端没有返回页图');
    qnoData.value = data;
  } catch (e) {
    if (seq !== qnoSeq) return;
    // 后端错误体是 {detail:{code,message}}；apiClient 归一化后 code 可能在不同层，逐层兜
    const obj = e as Record<string, any>;
    const detailObj = obj?.details?.detail ?? obj?.detail ?? obj?.response?.data?.detail;
    const code = typeof detailObj?.code === 'string' ? detailObj.code : '';
    const fallback =
      code === 'NOT_PDF' ? 'docx 没有"页"，无法定位原页'
        : code === 'GAP_NOT_FOUND' ? '这份草稿没有该题的定位信息（旧草稿需重新导题）'
          : code === 'FILE_MISSING' ? '原件已不在，无法渲染原页'
            : code === 'DRAFT_NOT_FOUND' ? '草稿不在了，刷新列表后再试'
              : '';
    qnoError.value = errorMessage(e, fallback || '原页加载失败，请稍后重试');
  } finally {
    if (seq === qnoSeq) qnoLoading.value = false;
  }
}

function openQno(no: number): void {
  if (!qnoGapsAvailable.value) {
    ElMessage.info('这份草稿生成于旧版本，没有定位信息；重新导题后可用');
    return;
  }
  void loadQno(no);
}

/** 上一题 / 下一题：在缺号列表里循环，不跨草稿 */
function stepQno(delta: number): void {
  const list = qnoNos.value;
  if (list.length < 2) return;
  const idx = list.indexOf(qnoNo.value);
  const next = list[(idx + delta + list.length) % list.length];
  if (next && next !== qnoNo.value) void loadQno(next);
}

/** 跨页缺口：在主选页（上一题所在页）与备选页（下一题所在页）之间切换 */
function flipQnoPage(): void {
  const data = qnoData.value;
  if (!data?.alt_page) return;
  void loadQno(qnoNo.value, data.alt_page);
}

function closeQno(): void {
  qnoOpen.value = false;
  qnoData.value = null;
  qnoError.value = '';
}

/** Esc 关闭；← → 切换（只在弹窗打开时生效，避免影响抽屉里的输入） */
function onQnoKey(e: KeyboardEvent): void {
  if (!qnoOpen.value) return;
  if (e.key === 'Escape') { e.preventDefault(); closeQno(); }
  else if (e.key === 'ArrowLeft') { e.preventDefault(); stepQno(-1); }
  else if (e.key === 'ArrowRight') { e.preventDefault(); stepQno(1); }
}

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

// Q3：弹窗键盘操作（Esc 关、← → 切题）。注册一次，卸载时摘掉，避免多次挂载留监听。
window.addEventListener('keydown', onQnoKey);
onBeforeUnmount(() => window.removeEventListener('keydown', onQnoKey));

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

/* ---------- Q3（2026-11-15，导题缺号定位）：缺号 chips + 原卷页弹窗 ---------- */
.pd-qno {
  display: inline-block;
  min-width: 26px;
  margin: 0 2px;
  padding: 1px 7px;
  border-radius: 11px;
  border: 1px solid #9db6e8;
  background: #eef3fd;
  color: #2b4b8f;
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
}
.pd-qno:hover { background: #e2ebfb; }
.pd-qno--cold {
  border-color: #d8dde8;
  background: #f4f5f8;
  color: #9aa3b4;
  cursor: not-allowed;
}
.pd-qno__hint { margin-left: 4px; color: #a07a2a; }

.qd-root {
  position: fixed;
  inset: 0;
  z-index: 2800;                                  /* 盖住抽屉（2700） */
  display: flex;
  align-items: center;
  justify-content: center;
}
.qd-mask { position: absolute; inset: 0; background: rgba(16, 24, 40, 0.5); }
.qd-panel {
  position: relative;
  width: 720px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 40px);
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: var(--adm-r-card, 12px);
  box-shadow: 0 20px 52px rgba(16, 24, 40, 0.24);
  font-family: var(--adm-font);
}
.qd-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px 10px;
  border-bottom: 1px solid var(--adm-line, #eef1f6);
}
.qd-title { margin: 0; font-size: 15px; font-weight: 700; color: #1f2a44; }
.qd-sub { margin: 4px 0 0; font-size: 11.5px; color: #8b94a8; }
.qd-x {
  border: 0;
  background: transparent;
  font-size: 20px;
  line-height: 1;
  color: #8b94a8;
  cursor: pointer;
}
.qd-body { flex: 1; min-height: 0; overflow: auto; padding: 12px 16px; }
.qd-imgwrap {
  position: relative;
  width: 100%;
  border: 1px solid var(--adm-line, #eef1f6);
  border-radius: 8px;
  overflow: hidden;
  background: #fafbfd;
}
.qd-imgwrap img { display: block; width: 100%; height: 100%; }
.qd-hl {
  position: absolute;
  border: 2px solid #c62828;
  background: rgba(198, 40, 40, 0.12);
  border-radius: 2px;
  pointer-events: none;
}
.qd-tip { margin: 8px 0 0; font-size: 11.5px; color: #8b94a8; }
.qd-state { padding: 28px 0; text-align: center; color: #8b94a8; font-size: 13px; }
.qd-state--error { color: #c62828; }
.qd-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px 14px;
  border-top: 1px solid var(--adm-line, #eef1f6);
}
.qd-foot__spacer { flex: 1; }
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
