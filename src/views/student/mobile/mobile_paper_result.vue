<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" type="button" aria-label="返回" @click="goBack">←</button>
      <div class="title">考试结果</div>
      <span class="topbar__pad" />
    </header>

    <p v-if="loading" class="state">加载中…</p>
    <p v-else-if="error" class="state state--error">{{ error }}</p>

    <template v-else>
      <section class="score-card">
        <div class="score-main">
          <b class="score-num">{{ scoreParts.left }}</b>
          <span class="score-max">/ {{ scoreParts.right }} 分</span>
        </div>
        <!-- 口径与 PC 结果页逐项对齐（同一个 buildExamSummary）：得分率 / 用时 / 正确÷错误 / 答对率(按已答)。
             「错误」含未答（2026-11-11 用户拍板），所以下面那行「已答·未答」必须同时出现，否则 2+95+93 看起来对不上。 -->
        <div class="meta-grid">
          <div class="meta-item">
            <span class="meta-label">得分率</span>
            <b class="meta-value meta-value--ok">{{ summary?.rateText || '—' }}</b>
          </div>
          <div class="meta-item">
            <span class="meta-label">用时</span>
            <b class="meta-value">{{ summary?.timeText || '—' }}</b>
          </div>
          <div class="meta-item">
            <span class="meta-label">正确 / 错误</span>
            <b class="meta-value">{{ correctCount }} / {{ wrongCount }} 题</b>
          </div>
          <div class="meta-item">
            <span class="meta-label">答对率（按已答）</span>
            <b class="meta-value">{{ summary?.accuracyAnsweredText || '—' }}</b>
          </div>
        </div>
        <p v-if="summary" class="score-note">
          已答 <b>{{ summary.answeredText }}</b> 题 · 未答 <b>{{ summary.unansweredText }}</b> 题（未答按错计）
        </p>
        <p v-if="summary?.pendingText" class="score-note score-note--warn">{{ summary.pendingText }}</p>
      </section>

      <div class="actions">
        <button class="btn btn--primary" type="button" :disabled="busy" @click="retake">再考一次</button>
        <button class="btn" type="button" @click="goWrong">查看错题</button>
        <button class="btn btn--line" type="button" @click="goHome">回首页</button>
      </div>

      <section class="review">
        <button class="review-head" type="button" @click="openReview = !openReview">
          <span>逐题回顾（{{ details.length }} 题）</span>
          <em>{{ openReview ? '收起 ▲' : '展开 ▼' }}</em>
        </button>

        <ol v-if="openReview" class="qlist">
          <li
            v-for="(d, i) in details"
            :key="d.question_id || i"
            class="qitem"
            :class="d.is_correct ? 'qitem--ok' : 'qitem--bad'"
          >
            <div class="qhead">
              <b>第 {{ i + 1 }} 题</b>
              <span class="qtag">{{ d.is_correct ? '✓ 正确' : '✗ 错误' }}</span>
            </div>
            <div class="qstem" v-html="renderQuestionContent(d.question_content || '')" />
            <div class="qans">
              你的答案：<b>{{ d.student_answer || '未答' }}</b>
              <span class="dot">·</span>
              正确答案：<b>{{ d.correct_answer || d.answer || '—' }}</b>
            </div>
            <div v-if="d.answer_analysis" class="qana">解析：{{ d.answer_analysis }}</div>
          </li>
        </ol>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
/**
 * 手机端考试结果页（D6，2026-11-15）。
 *
 * 之前手机答完试 `router.replace('/paper-result?...')` 直接跳到 **PC 结果页**
 * （`.vtj/vue/paper_result.vue`，桌面版式）——手机上要点开、可读性差。
 * 这里按手机版式重做一页，**数据与口径完全复用**：
 *   · 同一个接口 `GET /api/exams/records/{record_id}`；
 *   · 同一个满分/正确率口径 `buildExamSummary`（结果页/交卷弹窗/成绩分析共用）。
 */
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { buildExamSummary, type ExamSummary } from '@/utils/examSummary';
import { renderQuestionContent } from '@/utils/questionRender';

interface ExamDetail {
  question_id?: number;
  is_correct?: number | boolean;
  student_answer?: string | null;
  correct_answer?: string | null;
  answer?: string | null;
  answer_analysis?: string | null;
  question_content?: string;
}

interface ExamRecord {
  record_id?: number;
  paper_id?: number;
  total_score?: number;
  max_score?: number;
  question_total?: number;
  answered_count?: number;
  duration_used?: number;
  manual_pending_count?: number;
  details?: ExamDetail[];
}

const route = useRoute();
const router = useRouter();
const auth = (window as any).__VTJ_AUTH__;

const loading = ref(true);
const error = ref('');
const busy = ref(false);
const openReview = ref(false);
const data = reactive<ExamRecord>({});
const summary = ref<ExamSummary | null>(null);
const correctCount = ref(0);
const wrongCount = ref(0);

const details = computed<ExamDetail[]>(() => (Array.isArray(data.details) ? data.details : []));

/** 得分 / 满分直接取 summary 的 scoreText，避免两处数字各算一遍（PC 结果页同款做法） */
const scoreParts = computed(() => {
  const [left, right] = String(summary.value?.scoreText || '0 / 0').split(' / ');
  return { left: left ?? '0', right: right ?? '0' };
});

function recordId(): string {
  const raw = route.query.record_id;
  return Array.isArray(raw) ? String(raw[0] || '') : String(raw || '');
}

async function loadResult(): Promise<void> {
  const id = recordId();
  if (!id) {
    error.value = '缺少考试记录（record_id）';
    loading.value = false;
    return;
  }
  try {
    const res = await auth.apiFetch(`/api/exams/records/${id}`, {
      headers: auth.getJsonHeaders ? auth.getJsonHeaders() : undefined
    });
    if (!res.ok) throw new Error(`加载失败（HTTP ${res.status}）`);
    const body = (await res.json()) as ExamRecord;
    Object.assign(data, body || {});
    const list = Array.isArray(body?.details) ? body.details : [];
    const correct = list.filter((d) => Boolean(d.is_correct)).length;
    correctCount.value = correct;
    wrongCount.value = list.length - correct;
    const total = Number(body?.question_total) || list.length;
    let answered = Number(body?.answered_count);
    if (!Number.isFinite(answered)) {
      answered = list.filter((d) => String(d.student_answer || '').trim()).length;
    }
    summary.value = buildExamSummary({
      score: Number(body?.total_score) || 0,
      maxScore: Number(body?.max_score),
      correct,
      wrong: list.length - correct,
      unanswered: Math.max(total - answered, 0),
      total,
      answered,
      manualPending: Number(body?.manual_pending_count) || 0,
      seconds: Number(body?.duration_used) || 0
    });
  } catch (e: any) {
    error.value = e?.message || '加载失败，请稍后重试';
  } finally {
    loading.value = false;
  }
}

async function retake(): Promise<void> {
  const pid = Number(data.paper_id);
  if (!pid) return;
  busy.value = true;
  try {
    const res = await auth.apiFetch(`/api/exams/${pid}/start`, { method: 'POST' });
    const body = await res.json();
    if (body?.record_id) {
      router.replace(`/mobile/answer?record_id=${body.record_id}&paper_id=${pid}`);
      return;
    }
    error.value = body?.detail || '重新开始失败';
  } catch (e: any) {
    error.value = e?.message || '重新开始失败';
  } finally {
    busy.value = false;
  }
}

function goWrong(): void {
  router.push('/mobile/wrong-questions');
}

function goHome(): void {
  router.push('/mobile/home');
}

function goBack(): void {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
}

onMounted(loadResult);
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #f4f6fa;
  padding-bottom: 28px;
  font-size: 15px;
  color: #1f2a44;
}
.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 10px;
  background: #fff;
  border-bottom: 1px solid #eef1f6;
}
.back-btn {
  width: 40px;
  height: 40px;
  border: 0;
  background: transparent;
  font-size: 20px;
  color: #1f2a44;
}
.title {
  font-size: 16px;
  font-weight: 700;
}
.topbar__pad {
  width: 40px;
}
.state {
  padding: 40px 16px;
  text-align: center;
  color: #6b778c;
}
.state--error {
  color: #c62828;
}
.score-card {
  margin: 12px;
  padding: 18px 16px;
  background: #fff;
  border-radius: 14px;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.05);
  text-align: center;
}
.score-main {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 6px;
}
.score-num {
  font-size: 44px;
  line-height: 1;
  color: #2f54eb;
}
.score-max {
  font-size: 14px;
  color: #6b778c;
}
.meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  margin-top: 14px;
  background: #eef1f6;
  border-radius: 10px;
  overflow: hidden;
}
.meta-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 9px 12px;
  background: #fbfcfe;
}
.meta-label {
  font-size: 12px;
  color: #6b778c;
}
.meta-value {
  font-size: 13px;
  font-weight: 600;
  color: #1f2a44;
}
.meta-value--ok {
  color: #127a45;
}
.score-note {
  margin: 10px 0 0;
  font-size: 12px;
  color: #4a5568;
  line-height: 1.5;
}
.score-note--warn {
  color: #b26a00;
}
.dot {
  margin: 0 6px;
  color: #c3cad9;
}
.actions {
  display: flex;
  gap: 8px;
  margin: 0 12px 12px;
}
.btn {
  flex: 1;
  height: 42px;
  border: 1px solid #dfe4ee;
  border-radius: 10px;
  background: #fff;
  font-size: 14px;
  color: #1f2a44;
}
.btn--primary {
  background: #2f54eb;
  border-color: #2f54eb;
  color: #fff;
  font-weight: 600;
}
.btn--line {
  background: #fff;
}
.review {
  margin: 0 12px;
  background: #fff;
  border-radius: 14px;
  overflow: hidden;
}
.review-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 14px 14px;
  border: 0;
  background: #fff;
  font-size: 14px;
  font-weight: 600;
  color: #1f2a44;
}
.review-head em {
  font-style: normal;
  font-weight: 400;
  font-size: 12px;
  color: #6b778c;
}
.qlist {
  margin: 0;
  padding: 0;
  list-style: none;
}
.qitem {
  padding: 12px 14px;
  border-top: 1px solid #eef1f6;
}
.qitem--ok {
  border-left: 3px solid #127a45;
}
.qitem--bad {
  border-left: 3px solid #c62828;
}
.qhead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}
.qtag {
  color: #6b778c;
}
.qitem--ok .qtag {
  color: #127a45;
}
.qitem--bad .qtag {
  color: #c62828;
}
.qstem {
  margin-top: 6px;
  font-size: 14px;
  line-height: 1.55;
  word-break: break-word;
}
.qans {
  margin-top: 8px;
  font-size: 13px;
  color: #4a5568;
}
.qana {
  margin-top: 6px;
  padding: 8px 10px;
  background: #f7f9fc;
  border-radius: 8px;
  font-size: 12.5px;
  color: #4a5568;
  line-height: 1.55;
}
</style>
