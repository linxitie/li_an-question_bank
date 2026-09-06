<template>
  <div class="paper-answer-page">
    <main class="pa-main">
      <!-- 顶部工具栏 -->
      <div class="pa-toolbar">
        <div class="toolbar-left">
          <button class="tool-btn" @click="toggleSheet">
            <span>📋 答题卡</span>
          </button>
          <span class="progress-text">{{ state.currentIndex + 1 }} / {{ totalQuestions }}</span>
          <span class="paper-name" v-if="state.paperName">{{ state.paperName }}</span>
        </div>
        <div class="toolbar-right">
          <div class="timer-display">
            <span :class="['timer-text', { urgent: state.timeLeft < 300 }]">⏱ {{ formatTime(state.timeLeft) }}</span>
          </div>
          <button class="exit-btn" @click="handleExit">✕ 退出</button>
        </div>
      </div>

      <div class="pa-body">
        <!-- 答题卡面板 -->
        <div v-if="state.sheetVisible" class="sheet-panel">
          <div class="sheet-header">
            <h4>答题卡</h4>
            <span class="sheet-close" @click="state.sheetVisible = false">✕</span>
          </div>
          <div class="sheet-stats">
            <span>已答 <b>{{ answeredCount }}</b></span>
            <span>未答 <b>{{ totalQuestions - answeredCount }}</b></span>
          </div>
          <div class="sheet-grid">
            <button v-for="(q, idx) in questionsParsed" :key="q.id"
              :class="['sheet-num', {
                active: idx === state.currentIndex,
                answered: answersParsed[q.id] !== undefined,
                marked: markedParsed.includes(q.id)
              }]"
              @click="jumpTo(idx)">{{ idx + 1 }}</button>
          </div>
          <button class="submit-btn" @click="handleSubmit">交卷</button>
        </div>

        <!-- 题目区域 -->
        <div class="question-area">
          <div class="question-scroll">
            <!-- 加载状态 -->
            <div v-if="state.loading" class="loading-state">
              <div class="loading-spinner"></div>
              <p>正在加载试卷...</p>
            </div>

            <!-- 题目列表 -->
            <div v-for="(q, idx) in questionsParsed" v-else :key="q.id" :ref="'q_' + q.id" class="question-block">
              <div class="q-header">
                <span class="q-number">{{ idx + 1 }}.</span>
                <span :class="['q-type-badge', getTypeClass(q.type)]">{{ getTypeLabel(q.type) }}</span>
                <span class="q-score">{{ q.score || 0 }}分</span>
                <span v-if="markedParsed.includes(q.id)" class="mark-badge">🔖 已标记</span>
              </div>
              <p class="q-stem" v-html="q.stem"></p>

              <!-- 客观题：选项 -->
              <div v-if="getRenderMode(q.type) !== 'textarea'" class="q-options">
                <div v-if="getRenderMode(q.type) === 'checkbox'" class="multi-hint">
                  <strong>多选题</strong> — 点击多个选项
                </div>
                <div v-for="(opt, oidx) in q.options" :key="oidx"
                  :class="['option-item', {
                    selected: isOptionSelected(q.id, oidx),
                    correct: state.showResult && isCorrectOption(q, oidx),
                    wrong: state.showResult && isOptionSelected(q.id, oidx) && !isCorrectOption(q, oidx)
                  }]"
                  @click="selectOption(q.id, oidx, q.type)">
                  <span :class="['option-marker', getRenderMode(q.type) === 'checkbox' ? 'checkbox' : 'radio']">
                    {{ getRenderMode(q.type) === 'checkbox' ? '☐' : '○' }}
                  </span>
                  <span class="option-label">{{ state.optionLabels[oidx] }}.</span>
                  <span class="option-text" v-html="opt"></span>
                </div>
              </div>

              <!-- 主观题：文本框 -->
              <div v-else class="q-textarea">
                <textarea
                  :value="getTextAnswer(q.id)"
                  @input="e => selectOption(q.id, e.target.value, q.type)"
                  :placeholder="q.type === '写作题' ? '请在此输入你的文章...' : '请在此输入你的答案...'"
                  :class="['answer-textarea', q.type === '写作题' ? 'writing' : '']"
                  :rows="q.type === '写作题' ? 20 : 8"
                ></textarea>
              </div>

              <!-- 结果显示 -->
              <div v-if="state.showResult" class="q-result">
                <span :class="['result-badge', isCorrect(q) ? 'correct-badge' : 'incorrect-badge']">
                  {{ isCorrect(q) ? '✓ 正确' : '✗ 错误' }}
                </span>
                <p v-if="q.explain" class="result-explain">📖 {{ q.explain }}</p>
              </div>

              <!-- 操作按钮 -->
              <div class="q-actions">
                <button :class="['mark-btn', { marked: markedParsed.includes(q.id) }]" @click="toggleMark(q.id)">
                  {{ markedParsed.includes(q.id) ? '取消标记' : '标记' }}
                </button>
              </div>
            </div>

            <!-- 空状态 -->
            <div v-if="!state.loading && questionsParsed.length === 0" class="empty-state">
              <p>📭 暂无题目数据</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部导航 -->
      <div class="pa-nav">
        <button class="nav-btn" :disabled="state.currentIndex === 0" @click="state.currentIndex--">← 上一题</button>
        <span class="nav-progress">{{ state.currentIndex + 1 }} / {{ totalQuestions }}</span>
        <button class="nav-btn" :disabled="state.currentIndex >= totalQuestions - 1" @click="state.currentIndex++">下一题 →</button>
        <button class="submit-main-btn" @click="handleSubmit">📝 交卷</button>
      </div>
    </main>

    <!-- 退出弹窗 -->
    <div v-if="state.showExitDialog" class="modal-overlay" @click.self="state.showExitDialog = false">
      <div class="modal-dialog">
        <h4>确定退出？</h4>
        <p>答题进度将被保存到本地，下次可继续作答。</p>
        <div class="modal-actions">
          <button class="pa-btn back-btn" @click="state.showExitDialog = false">继续答题</button>
          <button class="pa-btn generate-btn" @click="saveAndExit">保存并退出</button>
        </div>
      </div>
    </div>

    <!-- 交卷确认弹窗 -->
    <div v-if="state.showSubmitDialog" class="modal-overlay" @click.self="state.showSubmitDialog = false">
      <div class="modal-dialog">
        <h4>确认交卷？</h4>
        <p>已答 <b>{{ answeredCount }}</b> / <b>{{ totalQuestions }}</b> 题，未答题将按0分处理。</p>
        <div class="modal-actions">
          <button class="pa-btn back-btn" @click="state.showSubmitDialog = false">继续检查</button>
          <button class="pa-btn generate-btn" @click="confirmSubmit">确认交卷</button>
        </div>
      </div>
    </div>

    <!-- 成绩弹窗 -->
    <div v-if="state.showResultDialog" class="modal-overlay">
      <div class="modal-dialog result-dialog">
        <div class="result-icon">🎉</div>
        <h3>交卷成功！</h3>
        <div class="result-stats">
          <div class="rs-item"><span class="rs-label">得分</span><span class="rs-value score">{{ state.submitScore }} / {{ state.submitMaxScore }}</span></div>
          <div class="rs-item"><span class="rs-label">正确率</span><span class="rs-value green">{{ state.submitAccuracy }}%</span></div>
          <div class="rs-item"><span class="rs-label">正确/错误</span><span class="rs-value">{{ state.submitCorrect }} / {{ state.submitWrong }}</span></div>
          <div class="rs-item"><span class="rs-label">用时</span><span class="rs-value">{{ formatTime(state.submitTimeSpent) }}</span></div>
        </div>
        <p class="result-hint">✅ 成绩已同步到「成绩分析 → 自测」</p>
        <div class="modal-actions">
          <button class="pa-btn generate-btn" @click="viewDetails">查看详情</button>
          <button class="pa-btn outline-btn" @click="goBackToList">返回试卷列表</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive, onMounted, onBeforeUnmount } from 'vue';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'PaperAnswer',
  setup() {
    const provider = useProvider({ id: 'paper_answer', version: '1' });
    const state = reactive({
      loading: true,
      paperId: null,
      recordId: null,
      paperName: '',
      totalDuration: 7200,
      timeLeft: 7200,
      questions: '[]',
      answers: '{}',
      markedQuestions: '[]',
      currentIndex: 0,
      optionLabels: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'],
      sheetVisible: false,
      showResult: false,
      showExitDialog: false,
      showSubmitDialog: false,
      showResultDialog: false,
      submitScore: 0,
      submitMaxScore: 0,
      submitAccuracy: 0,
      submitCorrect: 0,
      submitWrong: 0,
      submitTimeSpent: 0,
    });
    return { state, provider };
  },
  computed: {
    questionsParsed() {
      try { return JSON.parse(this.state.questions || '[]'); } catch(e) { return []; }
    },
    answersParsed() {
      try { return JSON.parse(this.state.answers || '{}'); } catch(e) { return {}; }
    },
    markedParsed() {
      try { return JSON.parse(this.state.markedQuestions || '[]'); } catch(e) { return []; }
    },
    answeredCount() {
      return Object.keys(this.answersParsed).length;
    },
    totalQuestions() {
      return this.questionsParsed.length;
    },
  },
  methods: {
    // ===== 工具函数 =====
    formatTime(s) {
      s = Math.max(0, Math.floor(s));
      var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
      return h.toString().padStart(2, '0') + ':' + m.toString().padStart(2, '0') + ':' + sec.toString().padStart(2, '0');
    },

    getTypeLabel(type) {
      var map = {
        '单选题': '[单选]', '单选': '[单选]',
        '多选题': '[多选]', '不定项': '[多选]', '多选': '[多选]',
        '判断题': '[判断]',
        '论述题': '[论述]', '简答题': '[简答]', '案例分析题': '[案例]',
        '写作题': '[写作]'
      };
      return map[type] || '[单选]';
    },

    getTypeClass(type) {
      if (['多选题', '不定项', '多选'].indexOf(type) >= 0) return 'multi';
      if (['论述题', '简答题', '案例分析题', '写作题'].indexOf(type) >= 0) return 'essay';
      return '';
    },

    getRenderMode(type) {
      if (['多选题', '不定项', '多选'].indexOf(type) >= 0) return 'checkbox';
      if (['论述题', '写作题', '简答题', '案例分析题'].indexOf(type) >= 0) return 'textarea';
      return 'radio';
    },

    // ===== 题目加载 =====
    async loadQuestions() {
      var paperId = this.$route.query.paper_id;
      var recordId = this.$route.query.record_id;
      if (!paperId) { this.state.loading = false; return; }

      this.state.paperId = parseInt(paperId);
      this.state.recordId = recordId ? parseInt(recordId) : null;

      try {
        var res = await window.__VTJ_AUTH__.apiFetch('/api/exams/' + paperId + '/questions', {
          headers: window.__VTJ_AUTH__.getJsonHeaders()
        });
        if (!res.ok) throw new Error('加载试卷失败');
        var data = await res.json();

        this.state.paperName = data.paper_name || '';
        this.state.totalDuration = (data.duration || 120) * 60;
        this.state.timeLeft = this.state.totalDuration;

        // 转换题目格式
        var questions = (data.questions || []).map(function(q) {
          var opts = this.parseOptions(q.options);
          // IMAGE占位替换
          var stem = this.replaceImages(q.question_content || '');
          opts = opts.map(function(o) { return this.replaceImages(o); }.bind(this));

          return {
            id: q.question_id,
            type: q.type_name || '单选题',
            stem: stem,
            options: opts,
            score: q.question_score || 0,
            explain: '',  // 考试模式不含答案
            answer: '',   // 考试模式不含答案
            subject_id: q.subject_id,
          };
        }.bind(this));

        this.state.questions = JSON.stringify(questions);

        // 恢复localStorage进度
        this.restoreProgress();
      } catch(e) {
        console.error('[PaperAnswer] 加载题目失败:', e);
      } finally {
        this.state.loading = false;
      }
    },

    // 选项解析（4种格式兼容）
    parseOptions(raw) {
      if (!raw) return ['(暂无选项)'];
      if (Array.isArray(raw) && raw.length > 0) {
        return raw.map(function(o) {
          if (typeof o === 'string') return o;
          return (o.key || '') + '. ' + (o.value || o.text || '');
        });
      }
      if (typeof raw === 'string') {
        var parsed = raw;
        while (typeof parsed === 'string') {
          try { parsed = JSON.parse(parsed); } catch(e) { break; }
        }
        if (Array.isArray(parsed)) {
          return parsed.map(function(o) {
            if (typeof o === 'string') return o;
            return (o.key || '') + '. ' + (o.value || o.text || '');
          });
        }
      }
      return ['(暂无选项)'];
    },

    // IMAGE占位替换（复用answer_page逻辑）
    replaceImages(text) {
      if (!text) return '';
      return String(text).replace(/\[?IMAGE:(\d+)_(\d+)\]?/gi, function(m, qn, idx) {
        return '<img src="/static/questions/' + qn + '/' + qn + '_' + idx + '.png" class="q-img" loading="lazy" onerror="this.onerror=null;this.src=\'/static/images/placeholder.png\';this.alt=\'图片加载失败\'" />';
      });
    },

    // ===== 计时器 =====
    startTimer() {
      var self = this;
      this._timer = setInterval(function() {
        if (self.state.timeLeft > 0) {
          self.state.timeLeft--;
        } else {
          self.confirmSubmit();
        }
      }, 1000);
    },

    // ===== 自动保存 =====
    startAutoSave() {
      var self = this;
      this._autoSave = setInterval(function() { self.saveProgress(); }, 30000);
    },

    saveProgress() {
      if (!this.state.paperId || !this.state.recordId) return;
      try {
        var progress = {
          answers: this.state.answers,
          markedQuestions: this.state.markedQuestions,
          currentIndex: this.state.currentIndex,
          timeLeft: this.state.timeLeft,
          timestamp: Date.now(),
        };
        localStorage.setItem('paper_progress_' + this.state.recordId, JSON.stringify(progress));
      } catch(e) {}
    },

    restoreProgress() {
      if (!this.state.recordId) return;
      try {
        var raw = localStorage.getItem('paper_progress_' + this.state.recordId);
        if (!raw) return;
        var progress = JSON.parse(raw);
        // 24小时内有效
        if (Date.now() - progress.timestamp > 86400000) return;
        if (progress.answers) this.state.answers = progress.answers;
        if (progress.markedQuestions) this.state.markedQuestions = progress.markedQuestions;
        if (progress.currentIndex !== undefined) this.state.currentIndex = progress.currentIndex;
        if (progress.timeLeft !== undefined) this.state.timeLeft = progress.timeLeft;
      } catch(e) {}
    },

    // ===== 选项操作 =====
    selectOption(qId, value, type) {
      if (this.state.showResult) return;
      var answers = JSON.parse(this.state.answers || '{}');

      if (this.getRenderMode(type) === 'textarea') {
        // 主观题：直接存储文本
        answers[qId] = value;
      } else if (this.getRenderMode(type) === 'checkbox') {
        // 多选题：toggle
        var cur = answers[qId] || [];
        if (!Array.isArray(cur)) cur = [cur];
        if (cur.indexOf(value) >= 0) {
          answers[qId] = cur.filter(function(v) { return v !== value; });
        } else {
          answers[qId] = cur.concat([value]);
        }
      } else {
        // 单选题：替换
        answers[qId] = value;
      }
      this.state.answers = JSON.stringify(answers);
    },

    isOptionSelected(qId, oidx) {
      var answers = this.answersParsed;
      var ans = answers[qId];
      if (Array.isArray(ans)) return ans.indexOf(oidx) >= 0;
      return ans === oidx;
    },

    getTextAnswer(qId) {
      var answers = this.answersParsed;
      var ans = answers[qId];
      return (typeof ans === 'string' && !['0','1','2','3','4','5','6','7'].includes(ans)) ? ans : '';
    },

    // ===== 标记 =====
    toggleMark(qId) {
      var arr = this.markedParsed.slice();
      var idx = arr.indexOf(qId);
      if (idx >= 0) { arr.splice(idx, 1); }
      else { arr.push(qId); }
      this.state.markedQuestions = JSON.stringify(arr);
    },

    // ===== 导航 =====
    jumpTo(idx) {
      this.state.currentIndex = idx;
      var qs = this.questionsParsed;
      if (idx >= 0 && idx < qs.length) {
        this.state.sheetVisible = false;
        var el = this.$refs['q_' + qs[idx].id];
        if (el && el[0]) {
          el[0].scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    },

    toggleSheet() {
      this.state.sheetVisible = !this.state.sheetVisible;
    },

    // ===== 退出 =====
    handleExit() { this.state.showExitDialog = true; },
    saveAndExit() {
      this.saveProgress();
      this.$router.push('/student/papers');
    },

    // ===== 交卷 =====
    handleSubmit() { this.state.showSubmitDialog = true; },

    async confirmSubmit() {
      this.state.showSubmitDialog = false;
      var answers = this.answersParsed;
      var qs = this.questionsParsed;
      var self = this;

      // 构建提交格式：{qid: answer_letter_string}
      var submitAnswers = {};
      Object.keys(answers).forEach(function(qid) {
        var a = answers[qid];
        if (Array.isArray(a)) {
          submitAnswers[qid] = a.map(function(i) { return self.state.optionLabels[i]; }).sort().join(',');
        } else if (typeof a === 'string' && isNaN(parseInt(a))) {
          // 文本答案（主观题）
          submitAnswers[qid] = a;
        } else if (typeof a === 'number' || (typeof a === 'string' && !isNaN(parseInt(a)))) {
          // 数字索引 → 字母
          submitAnswers[qid] = self.state.optionLabels[parseInt(a)] || '';
        }
      });

      // 补充未答题为空
      qs.forEach(function(q) {
        if (!(q.id in submitAnswers)) {
          submitAnswers[q.id] = '';
        }
      });

      try {
        var timeSpent = Math.max(0, this.state.totalDuration - this.state.timeLeft);
        var res = await window.__VTJ_AUTH__.apiFetch('/api/exams/' + this.state.recordId + '/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ answers: submitAnswers }),
        });
        if (!res.ok) {
          var e = await res.json();
          throw new Error(e.detail || '提交失败');
        }
        var data = await res.json();
        this.state.submitScore = data.data ? data.data.total_score : (data.total_score || 0);
        this.state.submitMaxScore = data.data ? data.data.max_score : (data.max_score || 100);
        this.state.submitAccuracy = data.data ? Math.round((this.state.submitScore / this.state.submitMaxScore) * 100) : 0;
        this.state.submitCorrect = data.data ? (data.data.scored_count || 0) : 0;
        this.state.submitWrong = this.totalQuestions - this.state.submitCorrect;
        this.state.submitTimeSpent = timeSpent;
        this.state.showResult = true;
        this.state.showResultDialog = true;

        if (this._timer) clearInterval(this._timer);
        if (this._autoSave) clearInterval(this._autoSave);
        // 清除进度
        localStorage.removeItem('paper_progress_' + this.state.recordId);
      } catch(err) {
        alert('提交失败: ' + (err.message || '网络错误'));
      }
    },

    // ===== 结果 =====
    isCorrect(q) {
      // 仅在showResult后有效（考试模式下没有answer字段，无法判断）
      return false;
    },

    isCorrectOption(q, oidx) {
      if (!this.state.showResult) return false;
      var correctLetter = q.answer;
      if (!correctLetter) return false;
      return this.state.optionLabels[oidx] === correctLetter;
    },

    viewDetails() {
      this.$router.push('/paper-result?record_id=' + this.state.recordId);
    },

    goBackToList() {
      this.$router.push('/student/papers');
    },
  },

  mounted() {
    this.loadQuestions();
    this.startTimer();
    this.startAutoSave();
  },

  beforeUnmount() {
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
    if (this._autoSave) { clearInterval(this._autoSave); this._autoSave = null; }
    this.saveProgress();
  },
});
</script>

<style scoped>
.paper-answer-page { min-height: 100vh; background: #f0f2f5; font-size: 15px; }
.pa-main { max-width: 960px; margin: 0 auto; padding-bottom: 72px; }

/* 工具栏 */
.pa-toolbar { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px;
  background: #fff; border-bottom: 1px solid #e8e8e8; position: sticky; top: 0; z-index: 100; }
.toolbar-left { display: flex; align-items: center; gap: 12px; }
.toolbar-right { display: flex; align-items: center; gap: 12px; }
.tool-btn { display: flex; align-items: center; gap: 4px; padding: 6px 14px; background: #f0f2f5;
  border: 1px solid #d9d9d9; border-radius: 6px; cursor: pointer; font-size: 14px; }
.paper-name { font-size: 14px; color: #666; font-weight: 500; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.progress-text { font-weight: 600; color: #1A3C6D; }
.timer-display { display: flex; align-items: center; gap: 4px; padding: 4px 12px; background: #f5f5f5; border-radius: 20px; }
.timer-text { font-weight: 700; font-size: 16px; color: #1A3C6D; font-variant-numeric: tabular-nums; }
.timer-text.urgent { color: #c41e3a; animation: pulse 1s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
.exit-btn { display: flex; align-items: center; gap: 4px; padding: 6px 14px; background: #c41e3a;
  color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }

/* 主体 */
.pa-body { display: flex; gap: 0; margin-top: 8px; }

/* 答题卡 */
.sheet-panel { width: 280px; min-width: 280px; background: #fff; border-radius: 8px; padding: 16px;
  margin-right: 12px; height: fit-content; position: sticky; top: 72px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.sheet-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.sheet-header h4 { margin: 0; color: #1A3C6D; }
.sheet-close { cursor: pointer; font-size: 18px; color: #999; }
.sheet-stats { display: flex; gap: 16px; margin-bottom: 12px; font-size: 13px; color: #666; }
.sheet-stats b { color: #1A3C6D; }
.sheet-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-bottom: 16px; }
.sheet-num { width: 100%; aspect-ratio: 1; border: 1px solid #d9d9d9; border-radius: 4px; background: #fff;
  cursor: pointer; font-size: 13px; display: flex; align-items: center; justify-content: center; }
.sheet-num.answered { background: #e6f0ff; border-color: #409EFF; color: #409EFF; }
.sheet-num.active { border-color: #1A3C6D; box-shadow: 0 0 0 2px rgba(26,60,109,0.3); font-weight: 700; }
.sheet-num.marked { background: #fff7e6; border-color: #fa8c16; }
.submit-btn { width: 100%; padding: 10px; background: #c41e3a; color: #fff; border: none; border-radius: 6px;
  cursor: pointer; font-size: 15px; font-weight: 600; }

/* 题目区 */
.question-area { flex: 1; min-width: 0; }
.question-scroll { display: flex; flex-direction: column; gap: 16px; }
.question-block { background: #fff; border-radius: 8px; padding: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.q-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.q-number { font-weight: 700; font-size: 16px; color: #1A3C6D; }
.q-type-badge { padding: 2px 8px; border-radius: 10px; font-size: 12px; background: #e6f0ff; color: #409EFF; }
.q-type-badge.multi { background: #fff7e6; color: #e6a23c; }
.q-type-badge.essay { background: #f0f5e8; color: #67c23a; }
.q-score { font-size: 12px; color: #999; }
.mark-badge { font-size: 12px; color: #fa8c16; }
.q-stem { line-height: 1.8; color: #333; margin: 0 0 16px; word-break: break-word; }
.q-stem :deep(img.q-img) { max-width: 100%; border-radius: 4px; margin: 8px 0; }

/* 选项 */
.q-options { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.multi-hint { font-size: 13px; color: #e6a23c; margin-bottom: 4px; }
.option-item { display: flex; align-items: flex-start; gap: 10px; padding: 12px 16px;
  border: 1px solid #e8e8e8; border-radius: 8px; cursor: pointer; transition: all 0.15s; }
.option-item:hover { border-color: #409EFF; background: #f0f7ff; }
.option-item.selected { border-color: #409EFF; background: #e6f0ff; font-weight: 500; }
.option-item.correct { border-color: #67c23a; background: #f0f9eb; }
.option-item.wrong { border-color: #f56c6c; background: #fef0f0; }
.option-marker { font-size: 18px; color: #bbb; min-width: 20px; }
.option-item.selected .option-marker { color: #409EFF; }
.option-label { font-weight: 600; color: #666; min-width: 22px; }
.option-text { flex: 1; line-height: 1.6; }
.option-text :deep(img.q-img) { max-width: 200px; max-height: 150px; border-radius: 4px; }

/* 文本框 */
.q-textarea { margin-bottom: 16px; }
.answer-textarea { width: 100%; padding: 16px; border: 2px solid #d9d9d9; border-radius: 8px;
  font-size: 15px; line-height: 1.8; resize: vertical; font-family: inherit; outline: none; box-sizing: border-box; }
.answer-textarea:focus { border-color: #409EFF; }
.answer-textarea.writing { min-height: 400px; font-size: 16px; line-height: 2; }

/* 结果 */
.q-result { padding: 12px; background: #f9f9f9; border-radius: 6px; margin-top: 8px; }
.result-badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 13px; font-weight: 600; }
.correct-badge { background: #f0f9eb; color: #67c23a; }
.incorrect-badge { background: #fef0f0; color: #f56c6c; }
.result-explain { margin-top: 8px; color: #666; font-size: 14px; line-height: 1.6; }

/* 操作 */
.q-actions { display: flex; gap: 8px; margin-top: 8px; }
.mark-btn { padding: 6px 16px; border: 1px solid #d9d9d9; border-radius: 16px; background: #fff;
  cursor: pointer; font-size: 13px; color: #666; }
.mark-btn.marked { background: #fff7e6; border-color: #fa8c16; color: #fa8c16; }

/* 底部导航 */
.pa-nav { display: flex; align-items: center; justify-content: center; gap: 16px; padding: 12px 16px;
  background: #fff; border-top: 1px solid #e8e8e8; position: fixed; bottom: 0; left: 0; right: 0; z-index: 100; }
.nav-btn { padding: 8px 20px; background: #f0f2f5; border: 1px solid #d9d9d9; border-radius: 6px;
  cursor: pointer; font-size: 14px; }
.nav-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.nav-progress { font-weight: 600; color: #1A3C6D; min-width: 80px; text-align: center; }
.submit-main-btn { padding: 8px 24px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px;
  cursor: pointer; font-size: 15px; font-weight: 600; }
.submit-main-btn:hover { background: #2a4f80; }

/* 模态弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.35); display: flex;
  align-items: center; justify-content: center; z-index: 1000; }
.modal-dialog { background: #fff; border-radius: 12px; padding: 32px; max-width: 420px; width: 90%;
  text-align: center; box-shadow: 0 8px 32px rgba(0,0,0,0.12); }
.modal-dialog h4 { margin: 0 0 12px; color: #1A3C6D; font-size: 18px; }
.modal-dialog p { color: #666; margin: 0 0 20px; }
.modal-actions { display: flex; gap: 12px; justify-content: center; }
.pa-btn { padding: 10px 24px; border-radius: 6px; cursor: pointer; font-size: 14px; border: none; }
.back-btn { background: #f0f2f5; color: #666; }
.generate-btn { background: #1A3C6D; color: #fff; }
.outline-btn { background: #fff; color: #1A3C6D; border: 1px solid #1A3C6D; }

/* 成绩弹窗 */
.result-dialog { max-width: 480px; }
.result-icon { font-size: 48px; margin-bottom: 8px; }
.result-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
.rs-item { display: flex; flex-direction: column; gap: 4px; padding: 12px; background: #f5f7fa; border-radius: 8px; }
.rs-label { font-size: 12px; color: #999; }
.rs-value { font-size: 20px; font-weight: 700; color: #1A3C6D; }
.rs-value.score { color: #c41e3a; }
.rs-value.green { color: #67c23a; }
.result-hint { font-size: 13px; color: #67c23a; margin-bottom: 20px; }

/* 加载/空状态 */
.loading-state, .empty-state { text-align: center; padding: 60px 0; color: #999; }
.loading-spinner { width: 40px; height: 40px; border: 3px solid #e8e8e8; border-top-color: #409EFF;
  border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 16px; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
