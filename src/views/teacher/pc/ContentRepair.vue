<template>
  <div class="cr-page">
    <TeacherNavHeader activeNav="content-repair" @logout="handleLogout" />

    <main class="cr-main">
      <header class="cr-head">
        <div>
          <h1>内容修复中心</h1>
          <p class="cr-sub">
            导入后自动体检：缺图 / 缺横线 / 缺选项 / 缺答案 / 缺解析 / 缺材料。
            点「定位题目」直达该题的编辑弹窗补录，修完按「重新体检」刷新。
          </p>
        </div>
        <div class="cr-tools">
          <label>
            <span>科目</span>
            <select v-model.number="subjectId" :disabled="loading" @change="reload">
              <option :value="0">全部科目</option>
              <option :value="1">行测</option>
              <option :value="2">申论</option>
              <option :value="3">公专</option>
            </select>
          </label>
          <button type="button" class="cr-ghost" :disabled="loading" @click="reload">
            {{ loading ? '体检中…' : '重新体检' }}
          </button>
        </div>
      </header>

      <!-- 六类缺口统计卡：点击即筛选 -->
      <section class="cr-cards" aria-label="缺口类型统计">
        <button
          type="button"
          :class="['cr-card', { active: kind === '' }]"
          :aria-pressed="kind === ''"
          @click="pickKind('')"
        >
          <strong>{{ totalGap }}</strong>
          <span>全部缺口</span>
        </button>
        <button
          v-for="k in kindOrder"
          :key="k"
          type="button"
          :class="['cr-card', { active: kind === k, muted: !byKind[k] }]"
          :aria-pressed="kind === k"
          @click="pickKind(k)"
        >
          <strong>{{ byKind[k] || 0 }}</strong>
          <span>{{ kindLabels[k] || k }}</span>
        </button>
      </section>

      <div v-if="error" class="cr-alert" role="alert">
        {{ error }}
        <button type="button" @click="reload">重试</button>
      </div>

      <!-- 加载态 -->
      <section v-if="loading && !items.length" class="cr-list" aria-busy="true">
        <article v-for="n in 3" :key="'sk' + n" class="cr-item skeleton">
          <div class="sk-line w30"></div>
          <div class="sk-line w90"></div>
          <div class="sk-line w60"></div>
        </article>
      </section>

      <!-- 空态 -->
      <section v-else-if="!items.length" class="cr-empty">
        <p class="cr-empty-title">{{ kind ? '该类缺口已清零' : '没有发现内容缺口' }}</p>
        <p class="cr-empty-hint">
          本次共体检 {{ scanned }} 题{{ kind ? '，当前筛选类型无待修题目' : '，配图、横线、选项、答案、解析、材料均完整' }}。
        </p>
      </section>

      <template v-else>
        <p class="cr-count">
          共 <strong>{{ total }}</strong> 题待修
          <span v-if="kind">（{{ kindLabels[kind] }}）</span>
          · 本次体检 {{ scanned }} 题
        </p>

        <section class="cr-list">
          <article v-for="it in items" :key="it.question_id" class="cr-item">
            <div class="cr-item-top">
              <span class="cr-id">#{{ it.question_id }}</span>
              <span class="cr-subject">{{ subjectName(it.subject_id) }}</span>
              <span v-if="it.year" class="cr-year">{{ it.year }} 年</span>
              <span
                v-for="k in it.kinds"
                :key="k"
                :class="['cr-badge', k]"
              >{{ kindLabels[k] || k }}</span>
              <span v-if="it.quality_score !== null && it.quality_score !== undefined"
                    :class="['cr-score', it.quality_score < 60 ? 'warn' : '']">
                质量 {{ it.quality_score }}
              </span>
            </div>

            <p class="cr-snippet">{{ it.snippet || '（题干为空）' }}</p>

            <ul v-if="detailLines(it).length" class="cr-detail">
              <li v-for="(line, i) in detailLines(it)" :key="i">{{ line }}</li>
            </ul>

            <div class="cr-actions">
              <button type="button" class="cr-primary" @click="goFix(it.question_id)">
                定位题目补录
              </button>
              <button type="button" class="cr-ghost" @click="copyId(it.question_id)">
                复制题号
              </button>
            </div>
          </article>
        </section>

        <nav class="cr-pager" aria-label="分页">
          <button type="button" class="cr-ghost" :disabled="page <= 1 || loading" @click="goPage(page - 1)">
            上一页
          </button>
          <span>第 {{ page }} / {{ maxPage }} 页</span>
          <button type="button" class="cr-ghost" :disabled="page >= maxPage || loading" @click="goPage(page + 1)">
            下一页
          </button>
        </nav>
      </template>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import TeacherNavHeader from '$vtj/vue/TeacherNavHeader.vue';

const router = useRouter();
const route = useRoute();

const kindOrder = [
  'missing_image',
  'missing_blank',
  'missing_option',
  'missing_answer',
  'missing_analysis',
  'missing_material',
];

const kindLabels = ref<Record<string, string>>({
  missing_image: '配图缺失',
  missing_blank: '横线缺失',
  missing_option: '选项缺失',
  missing_answer: '答案缺失',
  missing_analysis: '解析缺失',
  missing_material: '材料缺失',
});

const subjectId = ref(Number(route.query.subject_id || 0));
const kind = ref(String(route.query.kind || ''));
const page = ref(1);
const pageSize = 20;
const loading = ref(false);
const error = ref('');
const items = ref<any[]>([]);
const total = ref(0);
const scanned = ref(0);
const byKind = ref<Record<string, number>>({});
const gapQuestions = ref(0);

const totalGap = computed(() => gapQuestions.value || 0);
const maxPage = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

function subjectName(id: number) {
  return ({ 1: '行测', 2: '申论', 3: '公专' } as Record<number, string>)[id] || `科目 ${id}`;
}

function detailLines(it: any): string[] {
  const details = it && it.details ? it.details : {};
  return Object.keys(details)
    .map((k) => String(details[k] || '').trim())
    .filter((s) => s.length > 0)
    .slice(0, 3);
}

async function apiFetch(url: string, init?: RequestInit) {
  const auth = (window as any).__VTJ_AUTH__;
  if (!auth || typeof auth.apiFetch !== 'function') {
    throw new Error('登录状态失效，请重新登录');
  }
  const res = await auth.apiFetch(url, init);
  if (!res || !res.ok) {
    // 401/403 与 404 分开提示：404 多半是后端未重启到新路由
    const code = res ? res.status : 0;
    if (code === 404) throw new Error('接口返回 404，后端可能未加载新路由，请重启后端');
    if (code === 403) throw new Error('当前账号无权限（需要教师或管理员）');
    if (code === 401) throw new Error('登录已过期，请重新登录');
    throw new Error('请求失败（HTTP ' + code + '）');
  }
  return res.json();
}

async function loadSummary() {
  const qs = subjectId.value ? `?subject_id=${subjectId.value}` : '';
  const data = await apiFetch('/api/content-gaps/summary' + qs);
  byKind.value = data.by_kind || {};
  gapQuestions.value = Number(data.gap_questions || 0);
  scanned.value = Number(data.scanned || 0);
  if (data.kind_labels) kindLabels.value = { ...kindLabels.value, ...data.kind_labels };
}

async function loadList() {
  const params = new URLSearchParams();
  if (kind.value) params.set('kind', kind.value);
  if (subjectId.value) params.set('subject_id', String(subjectId.value));
  params.set('page', String(page.value));
  params.set('page_size', String(pageSize));
  const data = await apiFetch('/api/content-gaps/questions?' + params.toString());
  items.value = data.items || [];
  total.value = Number(data.total || 0);
  scanned.value = Number(data.scanned || 0);
  byKind.value = data.by_kind || {};
  gapQuestions.value = Number(data.gap_questions || 0);
}

async function reload() {
  loading.value = true;
  error.value = '';
  try {
    // 体检本身较慢（全库约 2~3 秒），两个请求串行避免双倍扫描
    await loadSummary();
    await loadList();
  } catch (e: any) {
    error.value = e && e.message ? e.message : '体检失败，请稍后重试';
    items.value = [];
  } finally {
    loading.value = false;
  }
}

function pickKind(k: string) {
  kind.value = k === kind.value ? '' : k;
  page.value = 1;
  loading.value = true;
  error.value = '';
  loadList()
    .catch((e: any) => {
      error.value = e && e.message ? e.message : '加载失败';
      items.value = [];
    })
    .finally(() => {
      loading.value = false;
    });
}

function goPage(p: number) {
  if (p < 1 || p > maxPage.value) return;
  page.value = p;
  loading.value = true;
  error.value = '';
  loadList()
    .catch((e: any) => {
      error.value = e && e.message ? e.message : '加载失败';
    })
    .finally(() => {
      loading.value = false;
    });
}

function goFix(questionId: number) {
  // teacher_questions.vue 的 script 已支持 ?question_id= 深链（打开编辑弹窗）
  router.push({ path: '/teacher/questions', query: { question_id: String(questionId) } });
}

async function copyId(questionId: number) {
  try {
    await navigator.clipboard.writeText(String(questionId));
  } catch {
    // 剪贴板被浏览器拒绝时不阻塞用户
  }
}

function handleLogout() {
  const auth = (window as any).__VTJ_AUTH__;
  if (auth && typeof auth.logout === 'function') auth.logout();
  else router.push('/login');
}

onMounted(reload);
</script>

<style scoped>
.cr-page {
  min-height: 100vh;
  background: #f4f6fa;
}

.cr-main {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px 20px 64px;
}

.cr-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.cr-head h1 {
  margin: 0 0 6px;
  font-size: 24px;
  color: #14264a;
}

.cr-sub {
  margin: 0;
  max-width: 720px;
  font-size: 13px;
  line-height: 1.7;
  color: #5b6b85;
}

.cr-tools {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.cr-tools label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #5b6b85;
}

.cr-tools select {
  height: 34px;
  padding: 0 10px;
  border: 1px solid #d5dde9;
  border-radius: 8px;
  background: #fff;
  color: #14264a;
  font-size: 13px;
}

.cr-cards {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.cr-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 12px 14px;
  border: 1px solid #e2e8f2;
  border-radius: 12px;
  background: #fff;
  cursor: pointer;
  text-align: left;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.cr-card strong {
  font-size: 20px;
  color: #14264a;
}

.cr-card span {
  font-size: 12px;
  color: #6b7a92;
}

.cr-card.muted strong {
  color: #9aa7ba;
}

.cr-card.active {
  border-color: #14264a;
  box-shadow: 0 0 0 2px rgba(20, 38, 74, 0.12);
}

.cr-card:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}

.cr-alert {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  margin-bottom: 12px;
  border: 1px solid #f3c3c3;
  border-radius: 10px;
  background: #fdecec;
  color: #b91c1c;
  font-size: 13px;
}

.cr-alert button {
  margin-left: auto;
  border: 1px solid #b91c1c;
  border-radius: 6px;
  background: #fff;
  color: #b91c1c;
  padding: 4px 10px;
  cursor: pointer;
}

.cr-count {
  margin: 0 0 10px;
  font-size: 13px;
  color: #5b6b85;
}

.cr-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.cr-item {
  padding: 14px 16px;
  border: 1px solid #e2e8f2;
  border-radius: 12px;
  background: #fff;
}

.cr-item-top {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.cr-id {
  font-size: 13px;
  font-weight: 600;
  color: #14264a;
}

.cr-subject,
.cr-year {
  font-size: 12px;
  color: #6b7a92;
  background: #f1f4f9;
  border-radius: 999px;
  padding: 2px 8px;
}

.cr-badge {
  font-size: 12px;
  border-radius: 999px;
  padding: 2px 8px;
  background: #eef2fb;
  color: #1d4ed8;
}

.cr-badge.missing_image,
.cr-badge.missing_material {
  background: #fdecec;
  color: #b91c1c;
}

.cr-badge.missing_analysis,
.cr-badge.missing_answer {
  background: #fff5e6;
  color: #b45309;
}

.cr-score {
  margin-left: auto;
  font-size: 12px;
  color: #15803d;
}

.cr-score.warn {
  color: #b45309;
}

.cr-snippet {
  margin: 0 0 8px;
  font-size: 14px;
  line-height: 1.7;
  color: #25324a;
}

.cr-detail {
  margin: 0 0 10px;
  padding-left: 18px;
  font-size: 12.5px;
  line-height: 1.7;
  color: #7a8699;
}

.cr-actions {
  display: flex;
  gap: 8px;
}

.cr-primary,
.cr-ghost {
  border-radius: 8px;
  font-size: 13px;
  padding: 7px 14px;
  cursor: pointer;
}

.cr-primary {
  border: 1px solid #14264a;
  background: #14264a;
  color: #fff;
}

.cr-ghost {
  border: 1px solid #d5dde9;
  background: #fff;
  color: #25324a;
}

.cr-primary:focus-visible,
.cr-ghost:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}

.cr-primary:disabled,
.cr-ghost:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.cr-empty {
  padding: 48px 24px;
  border: 1px solid #e2e8f2;
  border-radius: 12px;
  background: #fff;
  text-align: center;
}

.cr-empty-title {
  margin: 0 0 6px;
  font-size: 16px;
  color: #14264a;
}

.cr-empty-hint {
  margin: 0;
  font-size: 13px;
  color: #7a8699;
}

.cr-pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 18px;
  font-size: 13px;
  color: #5b6b85;
}

.sk-line {
  height: 12px;
  border-radius: 6px;
  background: #eef2f8;
  margin-bottom: 8px;
}

.sk-line.w30 { width: 30%; }
.sk-line.w60 { width: 60%; }
.sk-line.w90 { width: 90%; }

@media (max-width: 1100px) {
  .cr-cards {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .cr-main {
    padding: 16px 12px 80px;
  }

  .cr-head {
    flex-direction: column;
  }

  .cr-tools {
    width: 100%;
    justify-content: space-between;
  }

  .cr-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .cr-score {
    margin-left: 0;
  }

  .cr-actions {
    flex-direction: column;
  }

  .cr-primary,
  .cr-ghost {
    width: 100%;
  }
}
</style>
