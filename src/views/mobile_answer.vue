<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <div class="progress-text">{{ currentIndex + 1 }} / {{ questions.length }}</div>
      <button
        class="sheet-btn"
        :class="{ active: sheetOpen }"
        @click="sheetOpen = !sheetOpen"
        aria-label="答题卡"
      >答题卡</button>
    </header>

    <!-- 做题进度条：直观展示整体完成度 -->
    <div class="progress-bar" role="progressbar" :aria-valuenow="progressPercent" aria-valuemin="0" aria-valuemax="100">
      <div class="progress-bar-inner" :style="{ width: progressPercent + '%' }"></div>
    </div>

    <!-- 答题卡面板 -->
    <div v-if="sheetOpen" class="sheet-mask" @click="sheetOpen = false">
      <div class="sheet-panel" @click.stop>
        <div class="sheet-title">答题卡<span class="sheet-close" @click="sheetOpen = false">✕</span></div>
        <div class="sheet-grid">
          <button
            v-for="(q, i) in questions"
            :key="i"
            class="sheet-cell"
            :class="{ current: i === currentIndex, done: !!answersRecord[i] }"
            @click="jumpTo(i)"
          >{{ i + 1 }}</button>
        </div>
        <div class="sheet-legend">蓝色为当前题，绿色为已作答</div>
      </div>
    </div>

    <div v-if="fetchError" class="empty">{{ fetchError }}</div>
    <div v-else-if="!questions.length && !loading" class="empty">暂无题目</div>
    <div v-if="loading" class="empty">加载中...</div>

    <main v-else class="body">
      <!-- 模式切换：做题模式延后显示答案，记背模式立即显示 -->
      <div class="mode-switch">
        <button
          class="mode-btn"
          :class="{ active: mode === 'practice' }"
          @click="mode = 'practice'"
        >做题模式</button>
        <button
          class="mode-btn"
          :class="{ active: mode === 'memorize' }"
          @click="mode = 'memorize'"
        >记背模式</button>
      </div>
      <div v-if="mode === 'practice' && !allFinished && answered" class="mode-tip">
        做题模式：答完全部 {{ questions.length }} 题后统一显示答案与解析
      </div>
      <!-- 复合题共享材料（可折叠） -->
      <div v-if="groupInfo && groupInfo.shared_content" class="group-material-card">
        <div class="group-material-header" @click="groupCollapsed = !groupCollapsed">
          <span class="group-material-title">📖 {{ groupInfo.title || '题组材料' }}</span>
          <span class="group-material-toggle">{{ groupCollapsed ? '展开 ▾' : '收起 ▴' }}</span>
        </div>
        <div v-if="!groupCollapsed" class="group-material-content" v-html="renderQuestionContent(groupInfo.shared_content)"></div>
      </div>
      <!-- 题目 -->
      <div class="q-card">
        <div class="q-type">{{ current.type_label || '' }} · {{ current.question_type_detail || '单选题' }}</div>
        <div class="q-content" v-html="renderQuestionContent(current.question_content, { stripInlineOption: true })"></div>
      </div>

      <!-- 选项 -->
      <div class="options">
        <div
          v-for="(opt, idx) in current.options"
          :key="idx"
          :class="['option', optionClass(idx)]"
          @click="toggleOption(idx)"
        >
          <span class="opt-letter">{{ letters[idx] }}</span>
          <span class="opt-text" v-html="renderQuestionContent(opt)"></span>
        </div>
      </div>

      <!-- 判分结果：仅在记背模式或全部答完后显示 -->
      <div v-if="showResult" class="result" :class="{ correct: isCorrect }">
        <div class="result-title">{{ isCorrect ? '✅ 回答正确' : '❌ 回答错误' }}</div>
        <div v-if="!isCorrect" class="result-answer">正确答案：{{ current.answer }}</div>
        <div class="result-analysis" v-html="renderQuestionContent(current.answer_analysis || '暂无解析')"></div>
      </div>
      <!-- 全部答完后的统一成绩汇总 -->
      <div v-if="allFinished" class="summary">
        <div class="summary-title">🎉 全部完成</div>
        <div class="summary-body">共 {{ questions.length }} 题，正确 {{ correctCount }} 题，正确率 {{ summaryRate }}%</div>
      </div>
    </main>

    <footer class="action-bar" v-if="questions.length">
      <button v-if="!answered" class="submit-btn" @click="submitAnswer" :disabled="selectedOptions.length === 0">提交答案</button>
      <button v-else class="next-btn" @click="nextQuestion">{{ currentIndex < questions.length - 1 ? '下一题' : '完成' }}</button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { renderQuestionContent } from '@/utils/questionRender';

const router = useRouter();
const route = useRoute();
const questions = ref<{ options?: string[]; [key: string]: any }[]>([]);
const currentIndex = ref(0);
const selectedOptions = ref<number[]>([]);
const answered = ref(false);
const isCorrect = ref(false);
const loading = ref(false);
// 出题失败原因（用于把 422 等后端校验错误显式呈现，避免静默空白）
const fetchError = ref('');
const letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
// P1-2: 复合题共享材料（逐题模式下，当前题的题组材料）
const groupInfo = ref<any>(null);
const groupCollapsed = ref(false);

// ===== 答题模式与进度 =====
// 做题模式：答完全部题目后才统一显示答案与解析，避免逐题泄露答案
// 记背模式：每题提交后立即显示答案与解析，用于快速记忆复习
const mode = ref<'practice' | 'memorize'>('practice');
// 答题卡是否展开
const sheetOpen = ref(false);
// 逐题作答记录，索引即题号，用于答题卡标记与「是否全部完成」判定
const answersRecord = ref<boolean[]>([]);

// 整体完成进度百分比
const progressPercent = computed(() => {
  if (!questions.value.length) return 0;
  const done = questions.value.filter((_, i) => !!answersRecord.value[i]).length;
  return Math.round((done / questions.value.length) * 100);
});

// 是否所有题目都已作答
const allFinished = computed(() => {
  if (!questions.value.length) return false;
  return questions.value.every((_, i) => !!answersRecord.value[i]);
});

// 答案与解析是否应当显示：记背模式立即显示；做题模式全部答完才显示
const showResult = computed(() => answered.value && (mode.value === 'memorize' || allFinished.value));

// 逐题对错记录，供最终成绩汇总使用
const correctnessRecord = ref<boolean[]>([]);
// 最终答对题数
const correctCount = computed(() => correctnessRecord.value.filter(Boolean).length);
// 最终正确率
const summaryRate = computed(() => {
  if (!questions.value.length) return 0;
  return Math.round((correctCount.value / questions.value.length) * 100);
});

// 从答题卡跳转到指定题号
const jumpTo = (idx: number) => {
  if (idx < 0 || idx >= questions.value.length) return;
  currentIndex.value = idx;
  selectedOptions.value = [];
  answered.value = false;
  sheetOpen.value = false;
};

const current = computed<{ options?: string[]; [key: string]: any }>(() => questions.value[currentIndex.value] || {});

// P1-2: 切题时加载当前题的题组材料
watch(current, (q: any) => {
  groupInfo.value = null;
  groupCollapsed.value = false;
  if (q && q.group_id) {
    const auth = (window as any).__VTJ_AUTH__;
    auth.apiFetch('/api/questions/group/' + q.group_id)
      .then(function(r: any) { return r.json(); })
      .then(function(d: any) { if (d && d.group) groupInfo.value = d.group; })
      .catch(function() { /* 静默：材料加载失败不影响答题 */ });
  }
});

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/home');
};

const isMulti = computed(() => (current.value.question_type_detail || '') === '多选题');

const optionClass = (idx: number) => {
  if (!answered.value) {
    return { selected: selectedOptions.value.includes(idx) };
  }
  const letter = letters[idx];
  const isRight = (current.value.answer || '').includes(letter);
  const isPicked = selectedOptions.value.includes(idx);
  return {
    correct: isRight,
    wrong: isPicked && !isRight
  };
};

const toggleOption = (idx: number) => {
  if (answered.value) return;
  if (isMulti.value) {
    const pos = selectedOptions.value.indexOf(idx);
    if (pos >= 0) selectedOptions.value.splice(pos, 1);
    else selectedOptions.value.push(idx);
  } else {
    selectedOptions.value = [idx];
  }
};

/**
 * 选项归一化为纯文本数组。
 *
 * 背景：后端 option_utils.normalize_options 返回的是 [{key,value}] 对象数组，
 * 直接把对象丢给 renderQuestionContent 会被字符串清洗吞为空，
 * 表现为「选项内容与图片被吞没」。
 * 同时兼容 JSON 字符串与纯字符串数组两种历史格式。
 *
 * 注意：选项字母已由模板 letters[idx] 独立渲染，
 * 因此这里只取文本值，不再拼接 "A. " 前缀，避免出现「A A. xxx」。
 */
const normalizeOptionsForDisplay = (raw: any): string[] => {
  let opts: any = raw;
  if (typeof opts === 'string') {
    const t = opts.trim();
    if (!t) return [];
    try {
      opts = JSON.parse(t);
    } catch {
      opts = [t];
    }
  }
  if (!Array.isArray(opts)) return [];
return opts.map((o: any) => {
    if (o == null) return '';
    let s: string;
    if (typeof o === 'string') {
      s = o;
    } else if (typeof o === 'object') {
      s = String(o.value ?? o.text ?? o.label ?? '');
    } else {
      s = String(o);
    }
    // 后端 value 往往自带「A.」前缀，而模板已用 letters[idx] 单独渲染字母，
    // 不剥离会显示成「A A. xxx」的重复前缀。
    // 只剥离明确的「字母 + 分隔符」开头，保守处理避免误伤正文。
    return s.replace(/^\s*[A-Ha-h]\s*[.、．)）:：]\s*/, '').trim();
  });
};

const fetchQuestions = async () => {
  loading.value = true;
  try {
    const auth = (window as any).__VTJ_AUTH__;
    const knowledgePointIds = route.query.knowledge_point_ids as string | undefined;
    // 混合练习：子科目层入口传 bySubCategory=true，后端会把该 ID 当作子科目 ID
    // 并自动展开为该子科目下全部考点（quick_practice.py:234-239）。
    // 缺失该参数会导致后端按考点 ID 查询，查不到任何题目。
    const bySubCategory = route.query.bySubCategory === 'true';
    let list: any[] = [];
    if (knowledgePointIds) {
      // 练习页三科目下钻进入：按知识点取题
      // 后端 quick_practice.get_practice_questions 的必填参数名为 knowledge_point_ids，
      // 参数名不符会触发 422 并导致题目恒为空，故此处必须与后端契约严格一致。
      const qs = new URLSearchParams();
      qs.set('knowledge_point_ids', knowledgePointIds);
      qs.set('limit', '20');
      if (bySubCategory) qs.set('bySubCategory', 'true');
      const res = await auth.apiFetch(`/api/quick-practice/questions?${qs.toString()}`);
      const data = await res.json();
      if (res.status === 422) {
        // 可见化失败原因，避免静默空白
        console.warn('[mobile_answer] quick-practice 出题失败 422:', data);
        fetchError.value = data?.detail || '练习题目加载失败，请返回重试';
      } else if (res.ok && data.error) {
        // 后端对空/非法 ID 返回 200 + error 文案，同样需要显式呈现
        console.warn('[mobile_answer] quick-practice 返回 error:', data.error);
        fetchError.value = data.message || data.error;
      } else {
        fetchError.value = '';
      }
      list = data.items || [];
    } else {
      // 兜底：随机取题
      const res = await auth.apiFetch('/api/questions/random?count=10');
      const data = await res.json();
      list = data.questions || [];
    }
    if (list.length) {
      // 统一归一化选项，保证模板拿到的是纯文本数组
      questions.value = list.map((q: any) => ({
        ...q,
        options: normalizeOptionsForDisplay(q.options)
      }));
    }
  } catch (e) {
    console.error('获取题目失败:', e);
  } finally {
    loading.value = false;
  }
};

const submitAnswer = async () => {
  if (answered.value || selectedOptions.value.length === 0) return;
  const q = current.value;
  const userAnswer = selectedOptions.value.map((i) => letters[i]).sort().join('');
  const correct = (q.answer || '').replace(/[^A-H]/g, '').split('').sort().join('');
  // 记录本题作答，供答题卡标记与「全部完成」判定使用
  answersRecord.value[currentIndex.value] = true;
  correctnessRecord.value[currentIndex.value] = userAnswer === correct;
  isCorrect.value = userAnswer === correct;
  answered.value = true;

  // 记录练习（自动收录错题）
  try {
    const auth = (window as any).__VTJ_AUTH__;
    await auth.apiFetch('/api/practice/record', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question_id: q.question_id,
        subject_id: q.subject_id,
        is_correct: isCorrect.value,
        user_answer: userAnswer,
        source: '随机练习'
      })
    });
  } catch (e) {
    console.error('记录练习失败:', e);
  }
};

const nextQuestion = () => {
  if (currentIndex.value < questions.value.length - 1) {
    currentIndex.value++;
    selectedOptions.value = [];
    answered.value = false;
    isCorrect.value = false;
  } else {
    goBack();
  }
};

onMounted(fetchQuestions);
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: #F5F7FA;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 48px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #e8ecf1;
}
.back-btn {
  background: none;
  border: none;
  font-size: 22px;
  color: #1a2b5f;
  cursor: pointer;
  padding: 4px 8px;
}
.progress-text {
  font-size: 15px;
  font-weight: 600;
  color: #1a2b5f;
}
.spacer {
  width: 32px;
}
/* 右上角答题卡入口 */
.sheet-btn {
  background: #1a2b5f;
  color: #fff;
  border: none;
  border-radius: 14px;
  font-size: 13px;
  padding: 5px 12px;
  cursor: pointer;
}
.sheet-btn.active {
  background: #c41e3a;
}
/* 做题进度条 */
.progress-bar {
  height: 4px;
  background: #e8ecf1;
}
.progress-bar-inner {
  height: 100%;
  background: linear-gradient(90deg, #1a2b5f, #2d6cdf);
  transition: width 0.25s ease;
}
/* 答题卡面板 */
.sheet-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 100;
  display: flex;
  align-items: flex-end;
}
.sheet-panel {
  width: 100%;
  background: #fff;
  border-radius: 16px 16px 0 0;
  padding: 16px 16px calc(24px + env(safe-area-inset-bottom));
  max-height: 70vh;
  overflow-y: auto;
}
.sheet-title {
  font-size: 16px;
  font-weight: 600;
  color: #1a2b5f;
  margin-bottom: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.sheet-close {
  font-size: 18px;
  color: #8899aa;
  cursor: pointer;
}
.sheet-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(40px, 1fr));
  gap: 8px;
}
.sheet-cell {
  height: 38px;
  border: 1px solid #d8dfe8;
  border-radius: 8px;
  background: #fff;
  color: #1a2b5f;
  font-size: 14px;
  cursor: pointer;
}
.sheet-cell.done {
  background: #10b981;
  border-color: #10b981;
  color: #fff;
}
.sheet-cell.current {
  outline: 2px solid #1a2b5f;
  font-weight: 700;
}
.sheet-legend {
  margin-top: 12px;
  font-size: 12px;
  color: #8899aa;
}
/* 模式切换 */
.mode-switch {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.mode-btn {
  flex: 1;
  padding: 8px 0;
  border: 1px solid #d8dfe8;
  border-radius: 8px;
  background: #fff;
  color: #5a6b7f;
  font-size: 14px;
  cursor: pointer;
}
.mode-btn.active {
  background: #1a2b5f;
  border-color: #1a2b5f;
  color: #fff;
  font-weight: 600;
}
.mode-tip {
  background: #fff8e6;
  border: 1px solid #ffe4a3;
  border-radius: 8px;
  color: #a06a00;
  font-size: 13px;
  padding: 8px 10px;
  margin-bottom: 10px;
}
/* 成绩汇总 */
.summary {
  margin-top: 16px;
  background: #f0f6ff;
  border: 1px solid #c7dbf5;
  border-radius: 12px;
  padding: 14px;
  text-align: center;
}
.summary-title {
  font-size: 16px;
  font-weight: 700;
  color: #1a2b5f;
  margin-bottom: 6px;
}
.summary-body {
  font-size: 14px;
  color: #44586f;
}
.body {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
}
.q-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}
/* P1-2: 复合题共享材料卡 */
.group-material-card {
  background: #f8fafc;
  border: 1px solid #e8ecf1;
  border-radius: 12px;
  margin-bottom: 12px;
  overflow: hidden;
}
.group-material-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: #f1f5f9;
  cursor: pointer;
  user-select: none;
}
.group-material-title {
  font-size: 14px;
  font-weight: 700;
  color: #1a2b5f;
}
.group-material-toggle {
  font-size: 12px;
  color: #64748b;
}
.group-material-content {
  padding: 12px 14px;
  font-size: 14px;
  line-height: 1.7;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
}
.group-material-content :deep(img) {
  max-width: 100%;
  border-radius: 8px;
  margin: 8px 0;
}
.q-type {
  font-size: 12px;
  color: #c41e3a;
  margin-bottom: 8px;
}
.q-content {
  font-size: 15px;
  color: #1a2a3a;
  line-height: 1.7;
}
.q-content :deep(img) {
  max-width: 100%;
  border-radius: 8px;
  margin: 8px 0;
}
.options {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.option {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  background: #fff;
  border: 1.5px solid #e8ecf1;
  border-radius: 10px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s;
}
.option.selected {
  border-color: #1A365D;
  background: #f0f6ff;
}
.option.correct {
  border-color: #10b981;
  background: #f6ffed;
}
.option.wrong {
  border-color: #c41e3a;
  background: #fff2f0;
}
.opt-letter {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #f0f3f7;
  color: #5a6488;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
}
.option.selected .opt-letter {
  background: #1A365D;
  color: #fff;
}
.option.correct .opt-letter {
  background: #10b981;
  color: #fff;
}
.option.wrong .opt-letter {
  background: #c41e3a;
  color: #fff;
}
.opt-text {
  font-size: 15px;
  color: #1a2a3a;
  line-height: 1.6;
  flex: 1;
  /* flex 子项默认 min-width:auto，会阻止收缩到内容宽度以下，
     导致选项内的宽图撑破容器、被裁切而看不见。此处必须显式置 0。 */
  min-width: 0;
}
/* 选项内图片约束：与 .q-content :deep(img) 保持一致，
   否则图片按原始尺寸渲染会横向溢出选项框，表现为「图片被吞没」。 */
.opt-text :deep(img) {
  max-width: 100%;
  height: auto;
  display: block;
  border-radius: 6px;
  margin: 6px 0;
}
.result {
  margin-top: 16px;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}
.result.correct {
  border: 1px solid #b7eb8f;
}
.result-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 8px;
  color: #1a2b5f;
}
.result-answer {
  font-size: 14px;
  color: #c41e3a;
  margin-bottom: 8px;
}
.result-analysis {
  font-size: 14px;
  color: #5a6488;
  line-height: 1.7;
}
.result-analysis :deep(p) {
  margin-bottom: 8px;
}
.empty {
  text-align: center;
  color: #8899aa;
  padding: 40px 0;
}
.action-bar {
  padding: 12px;
  background: #fff;
  border-top: 1px solid #e8ecf1;
}
.submit-btn,
.next-btn {
  width: 100%;
  min-height: 48px;
  border: none;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  color: #fff;
}
.submit-btn {
  background: linear-gradient(135deg, #C91F37, #e8384f);
}
.next-btn {
  background: linear-gradient(135deg, #1A365D, #2a5298);
}
.submit-btn:disabled {
  opacity: 0.5;
}
</style>
