<template>
  <div class="pr-page">
    <TeacherNavHeader activeNav="review" @logout="handleLogout" />

    <main class="pr-main">
      <header class="pr-head">
        <div>
          <h1>考点复核</h1>
          <p class="pr-sub">
            低置信度的考点分配（tier = review）需要人工确认一次。确认＝保留新考点；
            驳回＝回到原考点，并把知识点一并还原，不留「考点与知识点矛盾」的中间状态。
          </p>
        </div>
        <div class="pr-batch">
          <label>
            <span>批次</span>
            <select v-model="batchId" :disabled="loading" @change="reload">
              <option value="">最新批次</option>
              <option v-for="b in batches" :key="b.batch_id" :value="b.batch_id">
                {{ b.batch_id }}（待 {{ statusCount(b, 'pending') }}）
              </option>
            </select>
          </label>
          <button type="button" class="pr-ghost" :disabled="loading" @click="reload">刷新</button>
        </div>
      </header>

      <!-- 进度：待复核 / 已确认 / 已驳回 -->
      <section class="pr-progress" aria-label="复核进度">
        <div class="pr-bar">
          <span class="pr-bar-done" :style="{ width: donePercent + '%' }"></span>
        </div>
        <ul class="pr-stats">
          <li><strong>{{ counts.all }}</strong><span>本批</span></li>
          <li class="warn"><strong>{{ counts.pending }}</strong><span>待复核</span></li>
          <li class="ok"><strong>{{ counts.accepted }}</strong><span>已确认</span></li>
          <li class="muted"><strong>{{ counts.rejected }}</strong><span>已驳回</span></li>
        </ul>
      </section>

      <div v-if="error" class="pr-alert" role="alert">
        {{ error }}
        <button type="button" @click="reload">重试</button>
      </div>

      <!-- 加载态：骨架屏（不是空白） -->
      <section v-if="loading && !items.length" class="pr-list" aria-busy="true">
        <article v-for="n in 3" :key="'sk' + n" class="pr-card skeleton">
          <div class="sk-line w70"></div>
          <div class="sk-line w40"></div>
          <div class="sk-line w90"></div>
        </article>
      </section>

      <!-- 空态 -->
      <section v-else-if="!items.length" class="pr-empty">
        <p class="pr-empty-title">本批已复核完毕</p>
        <p class="pr-empty-hint">
          没有待复核项。若要复核历史批次，请在上方切换批次；新的低置信分配会在下次重分类后出现。
        </p>
      </section>

      <!-- 列表 -->
      <section v-else class="pr-list">
        <article v-for="it in items" :key="it.audit_id" class="pr-card" :class="{ busy: acting === it.audit_id }">
          <div class="pr-card-top">
            <span class="pr-qid">#{{ it.question_id }}</span>
            <span class="pr-score" :class="scoreTone(it.score)">置信分 {{ formatScore(it.score) }}</span>
          </div>

          <p class="pr-snippet">{{ it.snippet || '（题干为空或仅含图片）' }}</p>

          <div class="pr-flow">
            <span class="pr-point old">{{ it.old_point_name }}</span>
            <span class="pr-arrow" aria-hidden="true">→</span>
            <span class="pr-point new">{{ it.new_point_name }}</span>
          </div>

          <p v-if="it.reason" class="pr-reason" :title="it.reason">{{ formatReason(it.reason) }}</p>

          <div class="pr-actions">
            <button type="button" class="pr-ok" :disabled="!!acting" @click="decide(it, true)">
              确认新考点
            </button>
            <button type="button" class="pr-no" :disabled="!!acting" @click="decide(it, false)">
              驳回并还原
            </button>
            <input
              v-model.trim="notes[it.audit_id]"
              class="pr-note"
              type="text"
              maxlength="120"
              placeholder="备注（可选，驳回时建议填写原因）"
            />
          </div>
        </article>
      </section>

      <!-- 分页 -->
      <nav v-if="total > pageSize" class="pr-pager" aria-label="分页">
        <button type="button" :disabled="page <= 1 || loading" @click="go(page - 1)">上一页</button>
        <span>第 {{ page }} / {{ lastPage }} 页 · 共 {{ total }} 条</span>
        <button type="button" :disabled="page >= lastPage || loading" @click="go(page + 1)">下一页</button>
      </nav>
    </main>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import TeacherNavHeader from '$vtj/vue/TeacherNavHeader.vue';

interface QueueItem {
  audit_id: number;
  question_id: number;
  old_point_name: string;
  new_point_name: string;
  score: number | null;
  tier: string;
  reason: string;
  snippet: string;
}

interface BatchStat {
  batch_id: string;
  total: number;
  by_tier: Record<string, number>;
  by_status: Record<string, number>;
}

export default defineComponent({
  name: 'TeacherPointReview',
  components: { TeacherNavHeader },
  setup() {
    const router = useRouter();

    const items = ref<QueueItem[]>([]);
    const batches = ref<BatchStat[]>([]);
    const batchId = ref('');
    const page = ref(1);
    const pageSize = ref(20);
    const total = ref(0);
    const loading = ref(false);
    const error = ref('');
    const acting = ref(0);
    const notes = reactive<Record<number, string>>({});

    function authFetch(url: string, options?: any) {
      const auth = (window as any).__VTJ_AUTH__;
      if (!auth || !auth.apiFetch) return Promise.reject(new Error('登录态失效，请重新登录'));
      return auth.apiFetch(url, options);
    }

    async function safeJson(res: any) {
      if (!res || !res.ok) throw new Error('接口返回 ' + (res && res.status) + '，请稍后重试');
      return res.json();
    }

    const currentBatch = computed<BatchStat | null>(() => {
      if (batchId.value) {
        return batches.value.find(function (b) { return b.batch_id === batchId.value; }) || null;
      }
      return batches.value.length ? batches.value[0] : null;
    });

    const counts = computed(() => {
      const b = currentBatch.value;
      return {
        all: b ? b.total : total.value,
        pending: b ? statusCount(b, 'pending') : total.value,
        accepted: b ? statusCount(b, 'accepted') : 0,
        rejected: b ? statusCount(b, 'rejected') : 0,
      };
    });

    const donePercent = computed(() => {
      const c = counts.value;
      if (!c.all) return 0;
      return Math.round(((c.accepted + c.rejected) / c.all) * 100);
    });

    const lastPage = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)));

    function statusCount(b: BatchStat, key: string) {
      return (b && b.by_status && b.by_status[key]) || 0;
    }

    /**
     * 后端的 reason 是给机器看的 JSON（{"hits":["求助","服务"],"margin":0}），
     * 直接铺在界面上对老师不可读，这里翻成「命中关键词 + 领先分差」两段人话，
     * 原始串放进 title 便于排查，解析失败就原样显示，不吞信息。
     */
    function formatReason(raw: string) {
  if (!raw) return '';
  try {
    const parsed = JSON.parse(raw);
    const parts: string[] = [];
    const hits = parsed && parsed.hits;
    // hits 里混着关键词和正则片段（如 "(向上级|及时).{0,6}报告"），正则对老师没有可读性，
    // 只保留纯文字关键词；若全是正则则整体省略，不做「0、1、2」这种下标噪声。
    if (Array.isArray(hits)) {
      const terms = hits
        .filter((h: unknown) => typeof h === 'string' && !/[()[\]{}|\\.*+?^$]/.test(h as string))
        .slice(0, 6);
      if (terms.length) parts.push('命中关键词：' + terms.join('、'));
    }
    if (typeof parsed.margin === 'number') {
      parts.push('与次优考点相差 ' + parsed.margin + ' 分');
    }
    return parts.length ? parts.join(' · ') : raw;
  } catch (e) {
    return raw;
  }
}

    function formatScore(score: number | null) {
      if (score === null || score === undefined) return '—';
      return (Math.round(score * 100) / 100).toString();
    }

    function scoreTone(score: number | null) {
      if (score === null || score === undefined) return '';
      // 阈值对齐后端 classifier：AUTO_SCORE=6 自动档、REVIEW_SCORE=3 复核档
      if (score >= 6) return 'high';
      if (score >= 3) return 'mid';
      return 'low';
    }

    async function loadStats() {
      try {
        const data = await authFetch('/api/point-review/stats').then(safeJson);
        batches.value = data.batches || [];
      } catch (e: any) {
        // 统计失败不阻塞列表：列表本身仍可复核
        console.warn('[point-review] stats 失败', e);
      }
    }

    async function loadQueue() {
      loading.value = true;
      error.value = '';
      try {
        const qs =
          '/api/point-review/queue?page=' + page.value + '&page_size=' + pageSize.value +
          (batchId.value ? '&batch_id=' + encodeURIComponent(batchId.value) : '');
        const data = await authFetch(qs).then(safeJson);
        items.value = data.items || [];
        total.value = data.total || 0;
        if (!batchId.value && data.batch_id) batchId.value = data.batch_id;
      } catch (e: any) {
        error.value = e && e.message ? e.message : '待复核清单读取失败';
        items.value = [];
        total.value = 0;
      } finally {
        loading.value = false;
      }
    }

    async function reload() {
      page.value = 1;
      await loadStats();
      await loadQueue();
    }

    function go(target: number) {
      if (target < 1 || target > lastPage.value) return;
      page.value = target;
      loadQueue();
    }

    async function decide(item: QueueItem, accept: boolean) {
      if (!accept && !notes[item.audit_id]) {
        // 驳回会回滚考点，没写原因的话事后无法解释，先拦一次
        const reason = window.prompt('驳回原因（会写入审计，便于回溯）：', '');
        if (reason === null) return;
        notes[item.audit_id] = reason.slice(0, 120);
      }
      const ok = window.confirm(
        accept
          ? '确认把该题保留在「' + item.new_point_name + '」？'
          : '驳回并还原到「' + item.old_point_name + '」？',
      );
      if (!ok) return;
      acting.value = item.audit_id;
      try {
        await authFetch('/api/point-review/' + item.audit_id, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ accept: accept, note: notes[item.audit_id] || null }),
        }).then(safeJson);
        items.value = items.value.filter(function (x) { return x.audit_id !== item.audit_id; });
        total.value = Math.max(0, total.value - 1);
        await loadStats();
        if (!items.value.length && page.value > 1) {
          page.value = page.value - 1;
          await loadQueue();
        }
      } catch (e: any) {
        error.value = e && e.message ? e.message : '复核提交失败';
      } finally {
        acting.value = 0;
      }
    }

    function handleLogout() {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth && typeof auth.logout === 'function') auth.logout();
      router.push('/login');
    }

    onMounted(async function () {
      await loadStats();
      await loadQueue();
    });

    return {
      items, batches, batchId, page, pageSize, total, loading, error, acting, notes,
      counts, donePercent, lastPage,
      statusCount, formatScore, formatReason, scoreTone, loadStats, loadQueue, reload, go, decide, handleLogout,
    };
  },
});
</script>

<style scoped>
.pr-page { min-height: 100vh; background: #f4f6fa; }
.pr-main { max-width: 1080px; margin: 0 auto; padding: 24px 20px 72px; }
.pr-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; }
.pr-head h1 { margin: 0 0 6px; font-size: 22px; color: #1a3c6d; }
.pr-sub { margin: 0; max-width: 620px; font-size: 13px; line-height: 1.7; color: #5b6779; }
.pr-batch { display: flex; align-items: center; gap: 8px; }
.pr-batch label { display: flex; align-items: center; gap: 6px; font-size: 13px; color: #5b6779; }
.pr-batch select { height: 32px; padding: 0 8px; border: 1px solid #d5dbe6; border-radius: 8px; background: #fff; font-size: 13px; }
.pr-ghost { height: 32px; padding: 0 12px; border: 1px solid #d5dbe6; border-radius: 8px; background: #fff; color: #1a3c6d; font-size: 13px; cursor: pointer; }

.pr-progress { margin: 18px 0 14px; padding: 14px 16px; background: #fff; border-radius: 12px; box-shadow: 0 1px 3px rgba(26, 60, 109, 0.08); }
.pr-bar { height: 6px; border-radius: 999px; background: #e8edf5; overflow: hidden; }
.pr-bar-done { display: block; height: 100%; background: #1a3c6d; transition: width 0.3s ease; }
.pr-stats { display: flex; gap: 26px; margin: 12px 0 0; padding: 0; list-style: none; }
.pr-stats li { display: flex; flex-direction: column; font-size: 12px; color: #5b6779; }
.pr-stats strong { font-size: 18px; color: #1a3c6d; }
.pr-stats .warn strong { color: #c8102e; }
.pr-stats .ok strong { color: #1f7a3d; }

.pr-alert { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; padding: 10px 14px; border-radius: 10px; background: #fdecef; color: #a50f2d; font-size: 13px; }
.pr-alert button { margin-left: auto; padding: 4px 10px; border: 1px solid #a50f2d; border-radius: 6px; background: transparent; color: #a50f2d; cursor: pointer; }

.pr-list { display: flex; flex-direction: column; gap: 12px; }
.pr-card { padding: 16px 18px; background: #fff; border-radius: 12px; box-shadow: 0 1px 3px rgba(26, 60, 109, 0.08); }
.pr-card.busy { opacity: 0.55; }
.pr-card-top { display: flex; align-items: center; gap: 10px; }
.pr-qid { font-size: 12px; color: #8894a7; }
.pr-score { margin-left: auto; padding: 2px 8px; border-radius: 999px; font-size: 12px; background: #eef2f8; color: #1a3c6d; }
.pr-score.high { background: #e6f4ea; color: #1f7a3d; }
.pr-score.low { background: #fdecef; color: #a50f2d; }
.pr-snippet { margin: 10px 0 12px; font-size: 14px; line-height: 1.75; color: #24313f; }
.pr-flow { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 13px; }
.pr-point { padding: 3px 10px; border-radius: 6px; }
.pr-point.old { background: #f2f4f7; color: #7a8798; text-decoration: line-through; }
.pr-point.new { background: #e8effa; color: #1a3c6d; font-weight: 600; }
.pr-arrow { color: #98a4b6; }
.pr-reason { margin: 8px 0 0; font-size: 12px; color: #8894a7; }
.pr-actions { display: flex; align-items: center; gap: 10px; margin-top: 14px; flex-wrap: wrap; }
.pr-ok, .pr-no { height: 34px; padding: 0 14px; border-radius: 8px; font-size: 13px; cursor: pointer; border: 1px solid transparent; }
.pr-ok { background: #1a3c6d; color: #fff; }
.pr-no { background: #fff; color: #a50f2d; border-color: #f0c3cc; }
.pr-note { flex: 1 1 220px; min-width: 160px; height: 34px; padding: 0 10px; border: 1px solid #d5dbe6; border-radius: 8px; font-size: 13px; }

.pr-empty { padding: 56px 20px; text-align: center; background: #fff; border-radius: 12px; }
.pr-empty-title { margin: 0 0 6px; font-size: 16px; color: #1a3c6d; }
.pr-empty-hint { margin: 0; font-size: 13px; color: #7a8798; }

.pr-card.skeleton .sk-line { height: 12px; margin-bottom: 10px; border-radius: 6px; background: linear-gradient(90deg, #eef1f6 25%, #f7f9fc 37%, #eef1f6 63%); background-size: 400% 100%; animation: pr-shimmer 1.4s ease infinite; }
.sk-line.w70 { width: 70%; }
.sk-line.w40 { width: 40%; }
.sk-line.w90 { width: 90%; }

.pr-pager { display: flex; align-items: center; justify-content: center; gap: 14px; margin-top: 20px; font-size: 13px; color: #5b6779; }
.pr-pager button { height: 32px; padding: 0 12px; border: 1px solid #d5dbe6; border-radius: 8px; background: #fff; cursor: pointer; }
.pr-pager button:disabled { opacity: 0.45; cursor: not-allowed; }

.pr-ok:focus-visible, .pr-no:focus-visible, .pr-ghost:focus-visible,
.pr-pager button:focus-visible, .pr-note:focus-visible, .pr-batch select:focus-visible {
  outline: 2px solid #1a3c6d;
  outline-offset: 2px;
}

@keyframes pr-shimmer {
  0% { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}

@media (prefers-reduced-motion: reduce) {
  .pr-bar-done { transition: none; }
  .pr-card.skeleton .sk-line { animation: none; }
}

@media (max-width: 720px) {
  .pr-main { padding: 16px 12px 64px; }
  .pr-head { flex-direction: column; }
  .pr-batch { width: 100%; }
  .pr-batch label { flex: 1; }
  .pr-batch select { flex: 1; }
  .pr-stats { gap: 16px; flex-wrap: wrap; }
  .pr-actions { flex-direction: column; align-items: stretch; }
  .pr-ok, .pr-no { width: 100%; }
  /* 竖排后 flex-basis 变成高度：备注框会被撑成 220px 的空盒，这里收回 auto 高度 */
  .pr-note { flex: 0 0 auto; width: 100%; min-width: 0; }
  .pr-snippet { font-size: 13px; }
}
</style>
