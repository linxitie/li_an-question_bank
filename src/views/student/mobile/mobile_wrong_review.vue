<!-- 手机端错题复习页（答题卡风格严格对齐 answer_page.vue） -->
<template>
  <div class="review-page">
    <!-- 模式选择 -->
    <div v-if="mode === ''" class="mode-select">
      <header class="topbar">
        <button class="back-btn" @click="goBack">←</button>
        <h1 class="title">错题复习</h1>
        <span class="spacer"></span>
      </header>
      <div class="mode-grid">
        <div v-for="m in modes" :key="m.key" class="mode-card" @click="startReview(m.key)">
          <div class="mode-icon">{{ m.icon }}</div>
          <div class="mode-name">{{ m.name }}</div>
          <div class="mode-desc">{{ m.desc }}</div>
        </div>
      </div>
    </div>

    <!-- 答题 -->
    <div v-else-if="!submitted" class="answer-wrap">
      <header class="topbar">
        <button class="back-btn" @click="goBack">←</button>
        <span class="progress">{{ current + 1 }} / {{ questions.length }}</span>
        <button class="sheet-toggle" @click="sheetVisible = !sheetVisible">答题卡</button>
      </header>

      <!-- 答题卡面板 -->
      <div v-if="sheetVisible" class="sheet-panel">
        <div class="sheet-stats">已答 {{ answeredCount }} / 未答 {{ questions.length - answeredCount }}</div>
        <div class="sheet-grid">
          <button
            v-for="(q, i) in questions"
            :key="q.wrong_id"
            :class="['sheet-num', { active: i === current, answered: answers[q.wrong_id] !== undefined }]"
            @click="current = i; sheetVisible = false"
          >{{ i + 1 }}</button>
        </div>
      </div>

      <div v-if="questions.length" class="question-area">
        <div class="q-header">
          <span class="q-number">{{ current + 1 }}.</span>
          <span :class="['q-type-badge', typeClass(questions[current].type)]">{{ typeLabel(questions[current].type) }}</span>
        </div>
        <p class="q-stem" v-html="renderQuestionContent(questions[current].question_content, { stripInlineOption: true })"></p>
        <div class="q-options">
          <div v-if="isMulti(questions[current].type)" class="multi-hint"><strong>多选题</strong> — 点击多个选项进行选择</div>
          <div
            v-for="(opt, oidx) in optionsOf(questions[current])"
            :key="oidx"
            :class="['option-item', { selected: isSelected(questions[current].wrong_id, oidx) }]"
            @click="selectOption(questions[current].wrong_id, oidx, questions[current].type)"
          >
            <span :class="['option-label', { multi: isMulti(questions[current].type) }]">{{ letterOf(oidx) }}</span>
            <span class="option-text" v-html="renderQuestionContent(opt)"></span>
          </div>
        </div>
        <div class="nav-btns">
          <button class="nav-btn" :disabled="current === 0" @click="current--">上一题</button>
          <button v-if="current < questions.length - 1" class="nav-btn primary" @click="current++">下一题</button>
          <button v-else class="nav-btn primary" @click="submitReview">提交复习</button>
        </div>
      </div>
    </div>

    <!-- 结果 -->
    <div v-else class="result-wrap">
      <header class="topbar">
        <button class="back-btn" @click="goBack">←</button>
        <h1 class="title">复习结果</h1>
        <span class="spacer"></span>
      </header>
      <div class="result-card">
        <div class="result-score">答对 {{ result.correct_count }} / {{ result.total }}</div>
        <div class="result-sub" v-if="result.auto_chopped && result.auto_chopped.length">
          已自动斩题 {{ result.auto_chopped.length }} 道（连续答对3次）
        </div>
      </div>
      <div class="result-list">
        <div v-for="(r, i) in result.results" :key="i" class="result-item">
          <div class="r-head">
            <span :class="['r-badge', r.is_correct ? 'ok' : 'err']">{{ r.is_correct ? '✓ 正确' : '✗ 错误' }}</span>
            <span class="r-ans">你的答案 {{ r.user_answer || '未答' }} / 正确答案 {{ r.correct_answer }}</span>
          </div>
          <div class="r-content">{{ r.content }}</div>
          <div class="r-analysis" v-if="r.analysis"><b>解析：</b>{{ r.analysis }}</div>
        </div>
      </div>
      <button class="redo-btn" @click="resetReview">再次复习</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { renderQuestionContent } from '@/utils/questionRender';
import {
  fetchWrongbookReviewQueue,
  submitWrongbookReview
} from '@/modules/wrongbook/api';
import { useWrongbookStore } from '@/modules/wrongbook/store';
import { emitWrongQuestionsChanged } from '@/modules/wrongbook/events';

const router = useRouter();
const wrongbook = useWrongbookStore();

const modes = [
  { key: 'knowledge', icon: '📚', name: '按知识点', desc: '同类知识点集中攻克' },
  { key: 'time', icon: '🕐', name: '按时间', desc: '最早收录优先复习' },
  { key: 'subject', icon: '📖', name: '按科目', desc: '按科目分组复习' },
  { key: 'mixed', icon: '🔀', name: '混合', desc: '随机打乱复习' },
];

const mode = ref('');
const questions = ref<any[]>([]);
const answers = ref<Record<number, number[] | number>>({});
const current = ref(0);
const sheetVisible = ref(false);
const submitted = ref(false);
const result = ref<any>({ total: 0, correct_count: 0, wrong_count: 0, results: [], auto_chopped: [] });

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/profile');
};

const answeredCount = computed(() => Object.keys(answers.value).length);

function typeLabel(type: string) {
  const map: Record<string, string> = { '单选题': '[单选]', '单选': '[单选]', '多选题': '[多选]', '不定项': '[多选]', '多选': '[多选]', '判断题': '[判断]', '论述题': '[论述题]', '写作题': '[写作题]' };
  return map[type] || '[单选]';
}
function typeClass(type: string) {
  const map: Record<string, string> = { '多选题': 'multi', '不定项': 'multi', '多选': 'multi', '判断题': 'judge', '论述题': 'essay', '写作题': 'essay' };
  return map[type] || '';
}
function isMulti(type: string) {
  return type === '多选题' || type === '不定项' || type === '多选';
}
function letterOf(idx: number) {
  return String.fromCharCode(65 + idx);
}

function optionsOf(q: any): string[] {
  let raw = q.options || q.question_options;
  if (!raw) return ['(暂无选项)'];
  let arr: any[] = [];
  if (typeof raw === 'string') {
    try { arr = JSON.parse(raw); } catch (e) { arr = [raw]; }
  } else if (Array.isArray(raw)) {
    arr = raw;
  }
  if (!arr.length) return ['(暂无选项)'];
  return arr.map((o: any) => {
    if (typeof o === 'string') return o;
    if (o && typeof o === 'object') {
      const key = o.key || o.label || '';
      const text = (o.value || o.text || '').replace(/[\.。、'；;：:，,！!？?]+$/g, '').trim();
      return (key ? key + '. ' : '') + (text || '(空)');
    }
    return String(o);
  });
}

function isSelected(qid: number, oidx: number) {
  const ans = answers.value[qid];
  if (Array.isArray(ans)) return ans.includes(oidx);
  return ans === oidx;
}

function selectOption(qid: number, oidx: number, type: string) {
  if (isMulti(type)) {
    const cur = (answers.value[qid] as number[]) || [];
    if (cur.includes(oidx)) answers.value[qid] = cur.filter((x) => x !== oidx);
    else answers.value[qid] = cur.concat([oidx]);
  } else {
    answers.value[qid] = oidx;
  }
}

async function startReview(m: string) {
  mode.value = m;
  try {
    questions.value = await fetchWrongbookReviewQueue({ mode: m as any, limit: 50 });
    current.value = 0;
  } catch (e) {
    console.error('加载复习队列失败:', e);
  }
}

async function submitReview() {
  const answers = questions.value
    .filter((q) => answers.value[q.wrong_id] !== undefined)
    .map((q) => {
      const ans = answers.value[q.wrong_id];
      const letters = (Array.isArray(ans) ? ans : [ans]).map((i) => letterOf(i)).join(',');
      return { wrong_id: q.wrong_id, question_id: q.question_id, user_answer: letters };
    });
  try {
    result.value = await submitWrongbookReview(answers, mode.value || 'mixed');
    submitted.value = true;
    emitWrongQuestionsChanged({ action: 'reviewed' });
  } catch (e) {
    console.error('提交复习失败:', e);
  }
}

function resetReview() {
  mode.value = '';
  questions.value = [];
  answers.value = {};
  current.value = 0;
  submitted.value = false;
  result.value = { total: 0, correct_count: 0, wrong_count: 0, results: [], auto_chopped: [] };
}

onMounted(() => {
  void wrongbook.load();
});
</script>

<style scoped>
.review-page {
  min-height: 100vh;
  background: #f1f3f8;
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
.topbar {
  height: 48px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #e8ecf1;
  position: sticky;
  top: 0;
  z-index: 10;
}
.back-btn { background: none; border: none; font-size: 22px; color: #1a2b5f; cursor: pointer; padding: 4px 8px; }
.title { font-size: 16px; font-weight: 600; color: #1a2b5f; margin: 0; }
.spacer { width: 32px; }
.progress { font-size: 14px; font-weight: 700; color: #1a2b5f; }
.sheet-toggle { background: #f8f9fc; border: 1px solid #e8eaf0; border-radius: 8px; padding: 6px 12px; font-size: 13px; color: #1a2b5f; cursor: pointer; }

.mode-select { min-height: 100vh; }
.mode-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; padding: 16px; }
.mode-card { background: #fff; border-radius: 14px; padding: 20px 12px; text-align: center; cursor: pointer; box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04); }
.mode-icon { font-size: 32px; margin-bottom: 8px; }
.mode-name { font-size: 15px; font-weight: 700; color: #1a2b5f; margin-bottom: 4px; }
.mode-desc { font-size: 12px; color: #8899aa; }

.sheet-panel { background: #fff; padding: 14px; border-radius: 12px; margin: 12px; box-shadow: 0 2px 8px rgba(26, 54, 95, 0.06); }
.sheet-stats { font-size: 12px; color: #5a6488; margin-bottom: 10px; }
.sheet-grid { display: grid; grid-template-columns: repeat(8, 1fr); gap: 6px; }
.sheet-num { height: 34px; border: 1px solid #e8eaf0; border-radius: 8px; background: #f8f9fc; font-size: 12px; color: #5a6488; cursor: pointer; }
.sheet-num.active { border-color: #1a2b5f; box-shadow: 0 0 0 2px rgba(26, 43, 95, 0.3); }
.sheet-num.answered { background: #1a2b5f; color: #fff; }

.question-area { padding: 16px; }
.q-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.q-number { font-size: 18px; font-weight: 900; color: #1a2b5f; }
.q-type-badge { font-size: 13px; padding: 4px 12px; border-radius: 8px; background: #eff6ff; color: #3b82f6; font-weight: 600; }
.q-type-badge.multi { background: #fef3c7; color: #d97706; }
.q-type-badge.judge { background: #f5f3ff; color: #7c3aed; }
.q-type-badge.essay { background: #f5f3ff; color: #7c3aed; }
.q-stem { font-size: 15px; line-height: 1.8; color: #1a2b5f; margin: 0 0 16px; font-weight: 500; }
.q-options { display: flex; flex-direction: column; gap: 10px; }
.multi-hint { padding: 8px 12px; background: #eff6ff; border-radius: 8px; font-size: 12px; color: #3b82f6; margin-bottom: 8px; }
.option-item { display: flex; align-items: center; gap: 10px; padding: 12px 14px; border: 2px solid #e8eaf0; border-radius: 12px; cursor: pointer; transition: all 0.2s; font-size: 14px; color: #333; }
.option-item.selected { border-color: #1a2b5f; background: #f0f4ff; color: #1a2b5f; font-weight: 600; }
.option-label { width: 28px; height: 28px; border-radius: 50%; background: #f8f9fc; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 13px; flex-shrink: 0; color: #5a6488; }
.option-item.selected .option-label { background: #1a2b5f; color: #fff; }
.option-label.multi { border-radius: 6px; }
.option-text { flex: 1; }

.nav-btns { display: flex; gap: 10px; margin-top: 20px; }
.nav-btn { flex: 1; min-height: 44px; border: 1px solid #e8eaf0; background: #fff; border-radius: 10px; font-size: 14px; font-weight: 600; color: #1a2b5f; cursor: pointer; }
.nav-btn.primary { background: linear-gradient(135deg, #1a2b5f, #2a5298); color: #fff; border: none; }
.nav-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.result-wrap { padding: 16px; }
.result-card { background: #fff; border-radius: 14px; padding: 24px; text-align: center; margin-bottom: 16px; box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04); }
.result-score { font-size: 28px; font-weight: 900; color: #1a2b5f; }
.result-sub { font-size: 13px; color: #10b981; margin-top: 8px; }
.result-list { display: flex; flex-direction: column; gap: 12px; }
.result-item { background: #fff; border-radius: 12px; padding: 14px; box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04); }
.r-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.r-badge { font-size: 12px; font-weight: 700; padding: 3px 10px; border-radius: 8px; }
.r-badge.ok { background: #f0fdf4; color: #22c55e; }
.r-badge.err { background: #fef2f2; color: #ef4444; }
.r-ans { font-size: 12px; color: #5a6488; }
.r-content { font-size: 14px; color: #1a2b5f; line-height: 1.6; }
.r-analysis { font-size: 13px; color: #5a6488; line-height: 1.6; margin-top: 6px; }
.r-analysis b { color: #1a2b5f; }
.redo-btn { width: 100%; min-height: 44px; margin-top: 16px; background: linear-gradient(135deg, #1a2b5f, #2a5298); color: #fff; border: none; border-radius: 10px; font-size: 14px; font-weight: 600; cursor: pointer; }
</style>
