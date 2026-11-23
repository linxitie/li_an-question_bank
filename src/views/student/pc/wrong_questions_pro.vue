<template>
  <div class="wq2-page">
    <NavBar />
    <main class="wq2-main">
      <header class="wq2-head">
        <div>
          <h1>错题集</h1>
          <p>按科目/子科目/考点筛出该复习的题，直接看我的答案与正确答案的差异。</p>
        </div>
        <div class="wq2-head-actions">
          <button class="wq2-btn primary" @click="startReview">开始复习</button>
          <button class="wq2-btn" @click="loadAll">刷新</button>
        </div>
      </header>

      <section class="wq2-review-row">
        <DueReviewCard />
        <MemoryCurve />
      </section>

      <section class="wq2-stats">
        <div class="wq2-stat"><b>{{ total }}</b><span>当前筛选错题</span></div>
        <div class="wq2-stat"><b>{{ wrongCount }}</b><span>错题总数</span></div>
        <div class="wq2-stat"><b>{{ zhanti.length }}</b><span>已斩题</span></div>
        <div class="wq2-stat"><b>{{ page }}</b><span>当前页</span></div>
      </section>

      <section class="wq2-filters">
        <div class="wq2-tabs">
          <button v-for="t in tabs" :key="t.key" :class="['wq2-tab', { active: tab === t.key }]" @click="switchTab(t.key)">
            {{ t.label }}
          </button>
        </div>
        <template v-if="tab !== 'zhanti'">
          <label class="wq2-field">
            <span>科目</span>
            <select v-model="filter.subject">
              <option value="">全部科目</option>
              <option value="1">行测</option>
              <option value="2">申论</option>
              <option value="3">公专</option>
            </select>
          </label>
          <label class="wq2-field">
            <span>子科目</span>
            <select v-model="filter.subCategory">
              <option value="">全部子科目</option>
              <option v-for="s in subOptions" :key="s.key" :value="s.value">{{ s.value }}（{{ s.count }}）</option>
            </select>
          </label>
          <label class="wq2-field">
            <span>考点</span>
            <select v-model="filter.pointId">
              <option value="">全部考点</option>
              <option v-for="p in pointOptions" :key="p.point_id" :value="String(p.point_id)">
                {{ p.point_name }}（{{ p.wrong_count }}）
              </option>
            </select>
          </label>
          <label class="wq2-field grow">
            <span>关键词</span>
            <input v-model="filter.keyword" placeholder="题干 / 材料 / 来源" @keyup.enter="applyFilter" />
          </label>
          <label class="wq2-field">
            <span>年份</span>
            <input v-model="filter.year" inputmode="numeric" placeholder="如 2024" />
          </label>
          <button class="wq2-btn primary" @click="applyFilter">筛选</button>
          <button class="wq2-btn" @click="resetFilter">重置</button>
        </template>
      </section>

      <p v-if="error" class="wq2-error">{{ error }}</p>
      <div v-if="loading" class="wq2-empty">加载中…</div>
      <div v-else-if="!currentItems.length" class="wq2-empty">{{ tab === 'zhanti' ? '暂无斩题记录' : '当前筛选下没有错题' }}</div>

      <section v-else class="wq2-list">
        <article v-for="q in currentItems" :key="tab === 'zhanti' ? q.id : q.wrong_id" class="wq2-card">
          <div class="wq2-card-top">
            <span class="wq2-chip">{{ subjectLabel(q.subject_id) }}</span>
            <span v-if="q.sub_category" class="wq2-chip subtle">{{ q.sub_category }}</span>
            <span class="wq2-chip subtle">{{ q.question_type_detail || q.type || '题目' }}</span>
            <span class="wq2-meta">收录 {{ fmtDate(q.add_time || q.date) }}</span>
            <span v-if="q.chopped" class="wq2-state cut">已斩题</span>
            <span v-else-if="q.status" :class="['wq2-state', q.status]">{{ q.statusText }}</span>
          </div>
          <p class="wq2-stem">{{ toText(q.question_content || q.title) }}</p>
          <div v-if="tab !== 'zhanti'" class="wq2-answer-row">
            <span :class="['wq2-answer', isRight(q.user_answer, q.answer) ? 'right' : 'wrong']">
              我的答案：{{ q.user_answer || '未作答' }}
            </span>
            <span class="wq2-answer">正确答案：{{ q.answer || '—' }}</span>
            <span class="wq2-meta">错 {{ q.error_count ?? '—' }} 次</span>
            <span class="wq2-meta">复习 {{ q.review_count ?? 0 }} 次</span>
          </div>
          <div class="wq2-card-foot">
            <button class="wq2-link" @click="openDetail(q)">查看详情</button>
            <button v-if="tab === 'zhanti'" class="wq2-link" @click="unchop(q)">恢复</button>
            <button v-else class="wq2-link" @click="chop(q)">斩题</button>
            <button class="wq2-link" @click="openNote(q)">笔记</button>
          </div>
        </article>
      </section>

      <footer v-if="tab !== 'zhanti' && total > pageSize" class="wq2-pager">
        <button class="wq2-btn" :disabled="page <= 1" @click="go(page - 1)">上一页</button>
        <span>{{ page }} / {{ totalPages }}</span>
        <button class="wq2-btn" :disabled="page >= totalPages" @click="go(page + 1)">下一页</button>
      </footer>
    </main>

    <div v-if="detail" class="wq2-mask" @click.self="detail = null">
      <div class="wq2-modal">
        <header class="wq2-modal-head">
          <h3>错题详情</h3>
          <button class="wq2-x" @click="detail = null">×</button>
        </header>
        <div class="wq2-modal-body">
          <div v-if="detail.material" class="wq2-material">
            <div class="wq2-material-head">材料（{{ detail.material.length }} 字）</div>
            <p>{{ toText(detail.material) }}</p>
          </div>
          <p class="wq2-detail-stem">{{ toText(detail.question_content || detail.content) }}</p>
          <ul class="wq2-options">
            <li v-for="opt in detail.options || []" :key="opt.key || opt.value" :class="{
              correct: isCorrectOption(opt),
              chosen: isChosenOption(opt),
              wrong: isChosenOption(opt) && !isCorrectOption(opt)
            }">
              <b>{{ opt.key || opt.option_key }}</b>. {{ toText(opt.value || opt.text || opt.content) }}
              <span v-if="isCorrectOption(opt)" class="wq2-mark">正确答案</span>
              <span v-if="isChosenOption(opt)" class="wq2-mark mine">我的选择</span>
            </li>
          </ul>
          <div class="wq2-detail-row">
            <span>我的答案：{{ detail.user_answer || '未作答' }}</span>
            <span>正确答案：{{ detail.answer || '—' }}</span>
            <span v-if="detail.accuracy_rate != null">全网正确率：{{ detail.accuracy_rate }}%</span>
          </div>
          <div v-if="detail.answer_analysis" class="wq2-analysis">
            <h4>解析</h4>
            <p>{{ toText(detail.answer_analysis) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import NavBar from '$vtj/vue/navbar.vue';
import DueReviewCard from '@/components/review/DueReviewCard.vue';
import MemoryCurve from '@/components/review/MemoryCurve.vue';

interface WrongItem {
  wrong_id: number;
  question_id: number;
  question_content: string;
  options?: any;
  answer?: string;
  user_answer?: string;
  subject_id: number;
  sub_category?: string;
  question_type_detail?: string;
  error_count?: number;
  review_count?: number;
  add_time?: string;
  status?: string;
  statusText?: string;
  chopped?: boolean;
}

const router = useRouter();
const auth = (window as any).__VTJ_AUTH__;
const api = (url: string, init?: RequestInit) => auth.apiFetch(url, init);

const tabs = [
  { key: 'wrong', label: '错题' },
  { key: 'zhanti', label: '斩题' },
  { key: 'favorite', label: '收藏' }
] as const;
const tab = ref<'wrong' | 'zhanti' | 'favorite'>('wrong');
const filter = reactive({ subject: '', subCategory: '', pointId: '', keyword: '', year: '' });
const page = ref(1);
const pageSize = 20;
const total = ref(0);
const wrongCount = ref(0);
const loading = ref(false);
const error = ref('');
const items = ref<WrongItem[]>([]);
const zhanti = ref<any[]>([]);
const favorites = ref<WrongItem[]>([]);
const detail = ref<any>(null);
const subStats = ref<any[]>([]);
const pointStats = ref<any[]>([]);

const pointOptions = computed(() =>
  pointStats.value.map((p: any) => ({
    point_id: p.point_id ?? p.key,
    point_name: p.point_name ?? p.name,
    wrong_count: p.wrong_count ?? 0
  }))
);

const subOptions = computed(() => {
  return subStats.value
    .filter((s) => !filter.subject || String(s.subject_id) === String(filter.subject))
    .map((s) => ({ key: s.subject_id + '_' + s.subcategory, value: s.subcategory, count: s.count }));
});

const currentItems = computed<any[]>(() => {
  if (tab.value === 'zhanti') return zhanti.value;
  if (tab.value === 'favorite') return favorites.value;
  return items.value;
});
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

function subjectLabel(id: number | string | undefined): string {
  const n = Number(id || 0);
  return n === 1 ? '行测' : n === 2 ? '申论' : n === 3 ? '公专' : '综合';
}

function toText(html: any): string {
  if (!html) return '';
  return String(html)
    .replace(/<img[^>]*>/gi, '[图片]')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function fmtDate(v?: string | null): string {
  if (!v) return '—';
  return String(v).replace('T', ' ').slice(0, 16);
}

function isRight(user?: string, answer?: string): boolean {
  return !!user && String(user).trim().toUpperCase() === String(answer || '').trim().toUpperCase();
}

function optKey(opt: any): string {
  return String(opt.key || opt.option_key || opt.value || '').trim().toUpperCase().slice(0, 1);
}
function isCorrectOption(opt: any): boolean {
  return !!detail.value && optKey(opt) === String(detail.value.answer || '').trim().toUpperCase();
}
function isChosenOption(opt: any): boolean {
  return !!detail.value && optKey(opt) === String(detail.value.user_answer || '').trim().toUpperCase();
}

async function loadPointStats(): Promise<void> {
  try {
    const qs = new URLSearchParams({ dimension: 'point', limit: '50' });
    if (filter.subject) qs.set('subject_id', filter.subject);
    const res = await api('/api/wrong-questions/point-stats?' + qs.toString());
    if (!res.ok) return;
    const d = await res.json();
    pointStats.value = Array.isArray(d.items) ? d.items : [];
  } catch {
    /* 考点失败不影响列表 */
  }
}

async function loadSubStats(): Promise<void> {
  try {
    const res = await api('/api/wrong-questions/subcategories');
    if (!res.ok) return;
    const d = await res.json();
    subStats.value = Array.isArray(d.items) ? d.items : [];
  } catch {
    /* 子科目失败不影响列表 */
  }
}

async function loadList(): Promise<void> {
  loading.value = true;
  error.value = '';
  try {
    if (tab.value === 'zhanti') {
      const res = await api('/api/wrong-questions/zhanti/list');
      const d = await res.json();
      zhanti.value = Array.isArray(d.items) ? d.items : [];
      total.value = zhanti.value.length;
      loading.value = false;
      return;
    }
    const qs = new URLSearchParams({
      page: String(page.value),
      page_size: String(pageSize),
      collection_type: tab.value === 'favorite' ? 'FAVORITE' : 'WRONG'
    });
    if (filter.subject) qs.set('subject_id', filter.subject);
    if (filter.subCategory) qs.set('sub_category', filter.subCategory);
    if (filter.pointId) qs.set('point_id', filter.pointId);
    if (filter.keyword.trim()) qs.set('keyword', filter.keyword.trim());
    if (filter.year.trim()) qs.set('year', filter.year.trim());
    const res = await api('/api/wrong-questions?' + qs.toString());
    const d = await res.json();
    if (!res.ok) throw new Error(d.detail || '加载失败');
    const list = (Array.isArray(d.items) ? d.items : []).map((q: any) => ({
      ...q,
      chopped: !!q.is_cut,
      statusText: q.is_cut ? '已斩题' : ''
    }));
    if (tab.value === 'favorite') favorites.value = list;
    else items.value = list;
    total.value = Number(d.total || 0);
    if (tab.value === 'wrong') wrongCount.value = Number(d.total || 0);
  } catch (e: any) {
    error.value = e?.message || '加载失败，请稍后重试';
  } finally {
    loading.value = false;
  }
}

async function loadAll(): Promise<void> {
  await Promise.all([loadSubStats(), loadPointStats(), loadList()]);
}

function switchTab(k: 'wrong' | 'zhanti' | 'favorite'): void {
  tab.value = k;
  page.value = 1;
  total.value = 0;
  void loadList();
}

function applyFilter(): void {
  page.value = 1;
  void loadList();
}

function resetFilter(): void {
  filter.subject = '';
  filter.subCategory = '';
  filter.pointId = '';
  filter.keyword = '';
  filter.year = '';
  page.value = 1;
  void loadList();
}

function go(p: number): void {
  page.value = p;
  void loadList();
}

async function openDetail(q: any): Promise<void> {
  try {
    const id = q.wrong_id || q.id;
    const res = await api('/api/wrong-questions/' + id + '/detail');
    const d = await res.json();
    if (!res.ok) throw new Error(d.detail || '详情加载失败');
    detail.value = d;
  } catch (e: any) {
    error.value = e?.message || '详情加载失败';
  }
}

async function chop(q: any): Promise<void> {
  try {
    await api('/api/wrong-questions/' + q.wrong_id + '/chop', { method: 'POST' });
    await loadAll();
  } catch {
    /* 忽略 */
  }
}

async function unchop(q: any): Promise<void> {
  try {
    await api('/api/wrong-questions/' + (q.wrong_id || q.id) + '/unchop', { method: 'POST' });
    await loadAll();
  } catch {
    /* 忽略 */
  }
}

async function openNote(q: any): Promise<void> {
  const qid = q.question_id || q.id;
  if (!qid) return;
  try {
    const res = await api('/api/questions/' + qid + '/note');
    const d = res.ok ? await res.json() : {};
    const text = window.prompt('笔记（留空表示不修改）', d.note_text || '');
    if (text === null || !text.trim()) return;
    await api('/api/questions/' + qid + '/note', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note_text: text.trim() })
    });
  } catch {
    /* 笔记失败不影响列表 */
  }
}

function startReview(): void {
  const subject = filter.subject === '2' ? 'sl' : filter.subject === '3' ? 'ga' : 'xc';
  void router.push('/exercise?review=1&subject=' + subject + '&count=20');
}

watch(
  () => filter.subject,
  () => {
    filter.subCategory = '';
    filter.pointId = '';
    void loadPointStats();
  }
);

onMounted(() => {
  void loadAll();
});
</script>

<style scoped>
.wq2-page { min-height: 100vh; background: #f5f7fb; color: #1a2b5f; }
.wq2-main { max-width: 1180px; margin: 0 auto; padding: 24px 28px 48px; }
.wq2-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; flex-wrap: wrap; }
.wq2-head h1 { margin: 0 0 6px; font-size: 24px; }
.wq2-head p { margin: 0; color: #6b7896; font-size: 13px; }
.wq2-head-actions { display: flex; gap: 10px; }
.wq2-btn { height: 36px; padding: 0 16px; border-radius: 9px; border: 1px solid #dfe4ee; background: #fff; color: #33415c; cursor: pointer; font-size: 13px; }
.wq2-btn.primary { background: #2563eb; border-color: #2563eb; color: #fff; }
.wq2-btn:disabled { opacity: .5; cursor: not-allowed; }
.wq2-review-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 16px; }
.wq2-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 18px 0; }
.wq2-stat { background: #fff; border-radius: 12px; padding: 14px 16px; box-shadow: 0 2px 10px rgb(26 43 95 / 5%); display: flex; flex-direction: column; gap: 2px; }
.wq2-stat b { font-size: 22px; }
.wq2-stat span { font-size: 12px; color: #8a93a8; }
.wq2-filters { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; background: #fff; border-radius: 12px; padding: 14px 16px; box-shadow: 0 2px 10px rgb(26 43 95 / 5%); }
.wq2-tabs { display: flex; gap: 6px; margin-right: 8px; }
.wq2-tab { height: 34px; padding: 0 12px; border-radius: 8px; border: 1px solid #e3e8f2; background: #fff; color: #5a6488; cursor: pointer; }
.wq2-tab.active { background: #1a2b5f; border-color: #1a2b5f; color: #fff; }
.wq2-field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: #6b7896; }
.wq2-field.grow { flex: 1; min-width: 180px; }
.wq2-field select, .wq2-field input { height: 34px; border: 1px solid #dfe4ee; border-radius: 8px; padding: 0 10px; background: #fff; color: #1a2b5f; }
.wq2-error { color: #c41e3a; font-size: 13px; margin: 10px 0 0; }
.wq2-empty { padding: 46px; text-align: center; color: #8a93a8; background: #fff; border-radius: 12px; margin-top: 14px; }
.wq2-list { display: flex; flex-direction: column; gap: 12px; margin-top: 14px; }
.wq2-card { background: #fff; border-radius: 12px; padding: 16px 18px; box-shadow: 0 2px 10px rgb(26 43 95 / 5%); }
.wq2-card-top { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; }
.wq2-chip { padding: 1px 8px; border-radius: 999px; background: #eef3ff; color: #2563eb; }
.wq2-chip.subtle { background: #f2f4f9; color: #5a6488; }
.wq2-meta { color: #8a93a8; font-size: 12px; }
.wq2-state { margin-left: auto; padding: 1px 8px; border-radius: 999px; font-size: 12px; background: #f2f4f9; color: #5a6488; }
.wq2-state.cut { background: #e9f9ef; color: #1e7b3c; }
.wq2-state.mastered { background: #e9f9ef; color: #1e7b3c; }
.wq2-state.learning { background: #fff4e5; color: #b45309; }
.wq2-stem { margin: 10px 0 8px; font-size: 14px; line-height: 1.7; color: #29324a; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.wq2-answer-row { display: flex; gap: 16px; flex-wrap: wrap; font-size: 13px; align-items: center; }
.wq2-answer { color: #33415c; }
.wq2-answer.right { color: #1e7b3c; }
.wq2-answer.wrong { color: #c41e3a; font-weight: 600; }
.wq2-card-foot { display: flex; gap: 14px; margin-top: 10px; border-top: 1px dashed #eef1f6; padding-top: 8px; }
.wq2-link { border: none; background: transparent; color: #2563eb; font-size: 13px; cursor: pointer; padding: 0; }
.wq2-pager { display: flex; justify-content: center; align-items: center; gap: 14px; margin-top: 18px; color: #6b7896; font-size: 13px; }
.wq2-mask { position: fixed; inset: 0; z-index: 2300; background: rgb(12 26 44 / 45%); display: flex; align-items: center; justify-content: center; padding: 24px; }
.wq2-modal { width: min(820px, 92vw); max-height: 86vh; background: #fff; border-radius: 14px; display: flex; flex-direction: column; overflow: hidden; }
.wq2-modal-head { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid #eef1f6; }
.wq2-modal-head h3 { margin: 0; font-size: 16px; }
.wq2-x { border: none; background: transparent; font-size: 22px; color: #8a93a8; cursor: pointer; }
.wq2-modal-body { padding: 16px 18px; overflow-y: auto; }
.wq2-material { background: #f8fafd; border: 1px solid #e8edf5; border-radius: 10px; padding: 10px 12px; margin-bottom: 12px; font-size: 13px; line-height: 1.7; max-height: 220px; overflow-y: auto; }
.wq2-material-head { font-size: 12px; color: #8a93a8; margin-bottom: 4px; }
.wq2-detail-stem { font-size: 14px; line-height: 1.8; color: #29324a; }
.wq2-options { list-style: none; padding: 0; margin: 12px 0; display: flex; flex-direction: column; gap: 8px; }
.wq2-options li { border: 1px solid #e8edf5; border-radius: 8px; padding: 8px 10px; font-size: 13px; line-height: 1.6; }
.wq2-options li.correct { border-color: #1e7b3c; background: #f3fbf6; }
.wq2-options li.chosen.wrong { border-color: #c41e3a; background: #fff5f5; }
.wq2-mark { margin-left: 8px; font-size: 11px; color: #1e7b3c; }
.wq2-mark.mine { color: #c41e3a; }
.wq2-detail-row { display: flex; gap: 18px; flex-wrap: wrap; font-size: 13px; color: #33415c; }
.wq2-analysis { margin-top: 14px; border-top: 1px dashed #eef1f6; padding-top: 12px; font-size: 13px; line-height: 1.8; color: #29324a; }
.wq2-analysis h4 { margin: 0 0 6px; font-size: 13px; color: #5a6488; }
@media (max-width: 900px) { .wq2-stats { grid-template-columns: repeat(2, 1fr); } .wq2-filters { flex-direction: column; align-items: stretch; } }
</style>
