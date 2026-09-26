<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <div class="progress-text">{{ currentIndex + 1 }} / {{ questions.length }}</div>
      <span class="spacer"></span>
    </header>

    <div v-if="!questions.length && !loading" class="empty">暂无题目</div>
    <div v-if="loading" class="empty">加载中...</div>

    <main v-else class="body">
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
        <div class="q-content" v-html="current.question_content"></div>
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
          <span class="opt-text" v-html="opt"></span>
        </div>
      </div>

      <!-- 判分结果 -->
      <div v-if="answered" class="result" :class="{ correct: isCorrect }">
        <div class="result-title">{{ isCorrect ? '✅ 回答正确' : '❌ 回答错误' }}</div>
        <div v-if="!isCorrect" class="result-answer">正确答案：{{ current.answer }}</div>
        <div class="result-analysis" v-html="current.answer_analysis || '暂无解析'"></div>
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
const letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
// P1-2: 复合题共享材料（逐题模式下，当前题的题组材料）
const groupInfo = ref<any>(null);
const groupCollapsed = ref(false);

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

const fetchQuestions = async () => {
  loading.value = true;
  try {
    const auth = (window as any).__VTJ_AUTH__;
    const kpIds = route.query.kpIds as string | undefined;
    let list: any[] = [];
    if (kpIds) {
      // 练习页三科目下钻进入：按知识点取题
      const res = await auth.apiFetch(`/api/quick-practice/questions?kpIds=${encodeURIComponent(kpIds)}&limit=20`);
      const data = await res.json();
      list = data.items || [];
    } else {
      // 兜底：随机取题
      const res = await auth.apiFetch('/api/questions/random?count=10');
      const data = await res.json();
      list = data.questions || [];
    }
    if (list.length) questions.value = list;
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
