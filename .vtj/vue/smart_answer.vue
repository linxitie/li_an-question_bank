<!-- 智能组卷答题卡 — 复用answer_page设计风格 -->
<template>
  <div class="smart-answer-page">
    <NavBar></NavBar>
    <main class="sa-main">
      <div class="sa-toolbar">
        <div class="toolbar-left">
          <button class="tool-btn" @click="toggleSheet">
            <XIcon :icon="Grid" :size="18" color="#1a2b5f"></XIcon>
            <span> 答题卡</span>
          </button>
          <span class="progress-text">{{ state.currentIndex + 1 }} / {{ state.questions.length }}</span>
        </div>
        <div class="toolbar-right">
          <div class="timer-display">
            <XIcon :icon="AlarmClock" :size="18" :color="state.timeLeft < 300 ? '#c41e3a' : '#1a2b5f'"></XIcon>
            <span :class="['timer-text', { urgent: state.timeLeft < 300 }]">{{ formatTime(state.timeLeft) }}</span>
          </div>
          <button class="exit-btn" @click="handleExit">
            <XIcon :icon="CloseBold" :size="16" color="#ffffff"></XIcon>
            <span> 退出</span>
          </button>
        </div>
      </div>
      <div class="sa-body">
        <Transition name="sheet-slide">
          <div v-if="state.sheetVisible" class="sheet-panel">
            <div class="sheet-header"><h4>答题卡</h4><span class="sheet-close" @click="state.sheetVisible = false">✕</span></div>
            <div class="sheet-stats"><span>已答 <b>{{ answeredCount }}</b></span><span>未答 <b>{{ state.questions.length - answeredCount }}</b></span></div>
            <div class="sheet-grid">
              <button v-for="(q, idx) in state.questions" :key="q.id"
                :class="['sheet-num', { active: idx === state.currentIndex, answered: state.answers[q.id] !== undefined, marked: state.markedQuestions.includes(q.id) }]"
                @click="jumpTo(idx)">{{ idx + 1 }}</button>
            </div>
            <button class="submit-btn" @click="handleSubmit">交卷</button>
          </div>
        </Transition>
        <div class="question-area">
          <div class="question-scroll">
            <div v-if="state.loading" class="loading-state"><div class="loading-spinner"></div><p>正在加载试卷...</p></div>
            <div v-for="(q, idx) in state.questions" v-else :key="q.id" :ref="'q_' + q.id" class="question-block">
              <div class="q-header">
                <span class="q-number">{{ idx + 1 }} .</span>
                <span :class="['q-type-badge', q.type === '多选题' ? 'multi' : q.type === '判断题' ? 'judge' : '']">{{ q.type === '多选题' ? '[多选]' : q.type === '判断题' ? '[判断]' : '[单选]' }}</span>
                <span v-if="state.markedQuestions.includes(q.id)" class="mark-badge">已标记</span>
              </div>
              <p class="q-stem" v-html="renderQuestionContent(q.stem, { stripInlineOption: true })"></p>
              <div class="q-options">
                <div v-if="q.type === '多选题'" class="multi-hint"><strong>多选题</strong> — 点击多个选项</div>
                <div v-if="q.type === '判断题'" class="judge-hint"><strong>判断题</strong> — 选择"对"或"错"</div>
                <div v-for="(opt, oidx) in q.options" :key="oidx"
                  :class="['option-item', { selected: isSelected(q.id, oidx), correct: state.showResult && state.optionLabels[oidx] === q.answer, wrong: state.showResult && isSelected(q.id, oidx) && state.optionLabels[oidx] !== q.answer }]"
                  @click="selectOption(q.id, oidx, q.type)">
                  <span :class="['option-label', { multi: q.type === '多选题' }]">{{ state.optionLabels[oidx] }}</span>
                  <span class="option-text" v-html="renderQuestionContent(opt)"></span>
                </div>
              </div>
              <div v-if="state.showResult" class="q-result">
                <span :class="['result-badge', isCorrect(q) ? 'correct-badge' : 'incorrect-badge']">{{ isCorrect(q) ? '✓ 正确' : '✗ 错误' }}</span>
                <p v-if="q.explain" class="result-explain">{{ q.explain }}</p>
              </div>
              <div class="q-actions">
                <button :class="['mark-btn', { marked: state.markedQuestions.includes(q.id) }]" @click="toggleMark(q.id)">{{ state.markedQuestions.includes(q.id) ? '取消标记' : '标记' }}</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
    <!-- 退出弹窗 -->
    <div v-if="state.showExitDialog" class="modal-overlay" @click.self="state.showExitDialog = false">
      <div class="modal-dialog"><h4>确定退出？</h4><p>进度将被保存，下次可继续。</p>
        <div class="modal-actions"><button class="se-btn back-btn" @click="state.showExitDialog = false">继续答题</button><button class="se-btn generate-btn" @click="saveAndExit">保存并退出</button></div>
      </div>
    </div>
    <!-- 交卷弹窗 -->
    <div v-if="state.showSubmitDialog" class="modal-overlay" @click.self="state.showSubmitDialog = false">
      <div class="modal-dialog"><h4>确认交卷？</h4><p>已答 {{ answeredCount }}/{{ state.questions.length }} 题。</p>
        <div class="modal-actions"><button class="se-btn back-btn" @click="state.showSubmitDialog = false">继续检查</button><button class="se-btn generate-btn" @click="confirmSubmit">确认交卷</button></div>
      </div>
    </div>
    <!-- 成绩弹窗 -->
    <div v-if="state.showResultDialog" class="modal-overlay">
      <div class="modal-dialog result-dialog">
        <div class="result-icon">🎉</div><h3>交卷成功！</h3>
        <div class="result-stats">
          <div class="rs-item"><span class="rs-label">得分</span><span class="rs-value score">{{ state.submitScore }} / {{ state.submitMaxScore }}</span></div>
          <div class="rs-item"><span class="rs-label">正确率</span><span class="rs-value green">{{ state.submitAccuracy }}%</span></div>
          <div class="rs-item"><span class="rs-label">正确/错误</span><span class="rs-value">{{ state.submitCorrect }} / {{ state.submitWrong }}</span></div>
          <div class="rs-item"><span class="rs-label">用时</span><span class="rs-value">{{ formatTime(state.submitTimeSpent) }}</span></div>
        </div>
        <p class="result-hint">✅ 成绩已同步到「成绩分析 → 自测」</p>
        <div class="modal-actions"><button class="se-btn generate-btn" @click="goRecords">查看记录</button><button class="se-btn outline-btn" @click="goHome">返回首页</button></div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive, Transition } from 'vue';
import { XIcon } from '@vtj/ui';
import { Grid, AlarmClock, CloseBold } from '@vtj/icons';
import NavBar from './navbar.vue';
import { useProvider } from '@vtj/renderer';
import { renderQuestionContent } from '@/utils/questionRender';

export default defineComponent({
  name: 'SmartAnswer',
  components: { NavBar, XIcon, Transition },
  setup(props) {
    const provider = useProvider({ id: 'smart_answer', version: '1785854718491' });
    const state = reactive({
      loading: true,
      paperId: null,
      recordId: null,
      paperName: '',
      answers: '{}',
      timeLeft: 7200,
      questions: '[]',
      showResult: false,
      currentIndex: 0,
      optionLabels: ['A', 'B', 'C', 'D', 'E', 'F'],
      sheetVisible: false,
      markedQuestions: '[]',
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
    return { state, props, provider, Grid, AlarmClock, CloseBold, renderQuestionContent };
  },
  computed: {
    answeredCount() {
      try { return Object.keys(JSON.parse(this.state.answers || '{}')).length; } catch(e) { return 0; }
    },
  },
  methods: {
    isCorrect(q) {
      var answers = {}; try { answers = JSON.parse(this.state.answers || '{}'); } catch(e) {}
      var ans = answers[q.id];
      if (ans === undefined || ans === null) return false;
      if (q.type === '多选题') {
        if (!Array.isArray(ans)) return false;
        var u = ans.map(function(i) { return this.state.optionLabels[i]; }.bind(this)).sort().join('');
        return u === (q.answer || '').split('').sort().join('');
      }
      return this.state.optionLabels[ans] === q.answer;
    },
    formatTime(s) {
      s = Math.max(0, Math.floor(s));
      var h = Math.floor(s/3600), m = Math.floor((s%3600)/60), sec = s%60;
      return h.toString().padStart(2,'0')+':'+m.toString().padStart(2,'0')+':'+sec.toString().padStart(2,'0');
    },
    handleExit() { this.state.showExitDialog = true; },
    async saveAndExit() { await this.saveProgress(); this.$router.back(); },
    startTimer() {
      var self = this;
      this._timer = setInterval(function() { if (self.state.timeLeft > 0) self.state.timeLeft--; else self.handleSubmit(); }, 1000);
    },
    startAutoSave() {
      var self = this;
      this._autoSave = setInterval(function() { self.saveProgress(); }, 30000);
    },
    async saveProgress() {
      if (!this.state.paperId) return;
      try {
        await window.__VTJ_AUTH__.apiFetch('/api/smart-exam/' + this.state.paperId + '/save-progress', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ answers_json: this.state.answers, current_index: this.state.currentIndex, completed_count: this.answeredCount, marked_questions: this.state.markedQuestions, time_spent: Math.max(0, 7200 - this.state.timeLeft) }),
        });
      } catch(e) {}
    },
    toggleMark(qId) {
      var arr = []; try { arr = JSON.parse(this.state.markedQuestions || '[]'); } catch(e) {}
      var idx = arr.indexOf(qId);
      if (idx >= 0) arr.splice(idx, 1); else arr.push(qId);
      this.state.markedQuestions = JSON.stringify(arr);
    },
    handleSubmit() { this.state.showSubmitDialog = true; },
    async confirmSubmit() {
      this.state.showSubmitDialog = false;
      var answers = {}; try { answers = JSON.parse(this.state.answers || '{}'); } catch(e) {}
      var submitAnswers = {};
      var self = this;
      Object.keys(answers).forEach(function(qid) {
        var a = answers[qid];
        if (Array.isArray(a)) submitAnswers[qid] = a.map(function(i) { return self.state.optionLabels[i]; }).join(',');
        else submitAnswers[qid] = self.state.optionLabels[a] || '';
      });
      var qs = []; try { qs = JSON.parse(this.state.questions || '[]'); } catch(e) {}
      qs.forEach(function(q) { if (!(q.id in submitAnswers)) submitAnswers[q.id] = ''; });
      try {
        var timeSpent = Math.max(0, 7200 - this.state.timeLeft);
        var res = await window.__VTJ_AUTH__.apiFetch('/api/smart-exam/' + this.state.paperId + '/submit', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers: submitAnswers }),
        });
        if (!res.ok) { var e = await res.json(); throw new Error(e.detail || '提交失败'); }
        var data = await res.json();
        this.state.submitScore = data.total_score;
        this.state.submitMaxScore = data.max_score;
        this.state.submitAccuracy = data.accuracy;
        this.state.submitCorrect = data.correct_count;
        this.state.submitWrong = data.wrong_count;
        this.state.submitTimeSpent = data.time_spent;
        this.state.showResult = true;
        this.state.showResultDialog = true;
        if (this._timer) clearInterval(this._timer);
        if (this._autoSave) clearInterval(this._autoSave);
      } catch(err) { alert('提交失败: ' + (err.message || '')); }
    },
    selectOption(qId, oidx, type) {
      if (this.state.showResult) return;
      var answers = {}; try { answers = JSON.parse(this.state.answers || '{}'); } catch(e) {}
      if (type === '多选题') {
        var cur = answers[qId] || [];
        if (cur.includes(oidx)) answers[qId] = cur.filter(function(o) { return o !== oidx; });
        else answers[qId] = cur.concat([oidx]);
      } else { answers[qId] = oidx; }
      this.state.answers = JSON.stringify(answers);
    },
    jumpTo(idx) {
      this.state.currentIndex = idx;
      var qs = []; try { qs = JSON.parse(this.state.questions || '[]'); } catch(e) {}
      var el = this.$refs['q_' + qs[idx].id];
      if (el && el[0]) el[0].scrollIntoView({ behavior: 'smooth', block: 'start' });
    },
    isSelected(qId, oidx) {
      var answers = {}; try { answers = JSON.parse(this.state.answers || '{}'); } catch(e) {}
      var a = answers[qId]; if (Array.isArray(a)) return a.includes(oidx); return a === oidx;
    },
    toggleSheet() { this.state.sheetVisible = !this.state.sheetVisible; },
    async loadQuestions() {
      var paperId = this.$route.query.paper_id;
      if (!paperId) { this.state.loading = false; return; }
      this.state.paperId = parseInt(paperId);
      this.state.recordId = this.$route.query.record_id ? parseInt(this.$route.query.record_id) : null;
      this.state.paperName = this.$route.query.paper_name || '智能组卷';
      try {
        var res = await window.__VTJ_AUTH__.apiFetch('/api/smart-exam/' + paperId + '/preview?show_answer=false', { headers: window.__VTJ_AUTH__.getJsonHeaders() });
        if (!res.ok) throw new Error('加载失败');
        var data = await res.json();
        this.state.questions = JSON.stringify((data.questions || []).map(function(q) {
          var raw = q.options; var opts = [];
          if (raw) {
            if (typeof raw === 'string') { try { raw = JSON.parse(raw); } catch(e) {} }
            if (Array.isArray(raw)) opts = raw.map(function(o) { return typeof o === 'string' ? o : (o.key||'')+'. '+(o.value||o.text||''); });
          }
          if (!opts.length) opts = ['(暂无选项)'];
          return { id: q.question_id, type: q.type_name || '单选题', stem: (q.question_content||'').trim(), options: opts, answer: q.answer||'', explain: q.answer_analysis||'', subject_id: q.subject_id };
        }));
        this.state.timeLeft = (data.duration || 120) * 60;
        // 恢复进度
        if (this.state.recordId) {
          try {
            var pr = await window.__VTJ_AUTH__.apiFetch('/api/smart-exam/records/' + this.state.recordId, { headers: window.__VTJ_AUTH__.getJsonHeaders() });
            if (pr.ok) {
              var pd = await pr.json();
              if (pd.status === 'incomplete' && pd.answers_json) { this.state.answers = pd.answers_json; }
              if (pd.marked_questions) { this.state.markedQuestions = pd.marked_questions; }
              if (pd.current_index) { this.state.currentIndex = pd.current_index; }
              if (pd.time_spent) { this.state.timeLeft = Math.max(0, (data.duration||120)*60 - pd.time_spent); }
            }
          } catch(e) {}
        }
      } catch(e) {} finally { this.state.loading = false; }
    },
    goRecords() { this.$router.push('/smart-exam'); },
    goHome() { this.$router.push('/home'); },
  },
  mounted() {
    this.loadQuestions(); this.startTimer(); this.startAutoSave();
  },
  beforeUnmount() {
    if (this._timer) clearInterval(this._timer);
    if (this._autoSave) clearInterval(this._autoSave);
    this.saveProgress();
  },
});
</script>

<style lang="css" scoped>
.smart-answer-page { min-height: 100vh; background: #f1f3f8; font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif; }
.sa-main { max-width: 1380px; margin: 0 auto; padding: 16px 32px 40px; }
.sa-toolbar { display: flex; align-items: center; justify-content: space-between; background: #fff; border-radius: 14px; padding: 12px 20px; box-shadow: 0 2px 12px rgba(26,43,95,0.06); margin-bottom: 16px; position: sticky; top: 80px; z-index: 50; }
.toolbar-left { display: flex; align-items: center; gap: 16px; }
.tool-btn { display: flex; align-items: center; gap: 6px; padding: 8px 16px; border: 1px solid #e8eaf0; border-radius: 10px; background: #f8f9fc; cursor: pointer; font-size: 13px; font-weight: 600; color: #1a2b5f; }
.tool-btn:hover { background: #f0f2f5; }
.progress-text { font-size: 14px; font-weight: 700; color: #1a2b5f; }
.toolbar-right { display: flex; align-items: center; gap: 16px; }
.timer-display { display: flex; align-items: center; gap: 6px; padding: 8px 16px; background: #f8f9fc; border-radius: 10px; }
.timer-text { font-size: 18px; font-weight: 900; color: #1a2b5f; font-family: 'SF Mono', 'DIN Alternate', 'Menlo', monospace; letter-spacing: 1px; }
.timer-text.urgent { color: #c41e3a; animation: pulse 1s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.6} }
.exit-btn { display: flex; align-items: center; gap: 4px; padding: 8px 18px; border: none; border-radius: 10px; background: linear-gradient(135deg,#c41e3a,#e8384f); color: #fff; font-size: 13px; font-weight: 600; cursor: pointer; }
.exit-btn:hover { transform: scale(1.03); }
.sa-body { display: flex; gap: 20px; }
.sheet-panel { width: 240px; flex-shrink: 0; background: #fff; border-radius: 16px; padding: 20px; box-shadow: 0 2px 14px rgba(26,43,95,0.08); align-self: flex-start; position: sticky; top: 160px; }
.sheet-header { display: flex; justify-content: space-between; margin-bottom: 12px; }
.sheet-header h4 { font-size: 15px; font-weight: 700; color: #1a2b5f; margin: 0; }
.sheet-close { cursor: pointer; color: #8a8faa; }
.sheet-stats { display: flex; gap: 16px; margin-bottom: 16px; font-size: 12px; color: #5a6488; }
.sheet-stats b { color: #1a2b5f; }
.sheet-grid { display: grid; grid-template-columns: repeat(5,1fr); gap: 8px; margin-bottom: 16px; }
.sheet-num { width: 36px; height: 36px; border: 1px solid #e8eaf0; border-radius: 8px; background: #f8f9fc; font-size: 12px; font-weight: 700; color: #5a6488; cursor: pointer; display: flex; align-items: center; justify-content: center; }
.sheet-num.active { border-color: #1a2b5f; box-shadow: 0 0 0 2px rgba(26,43,95,0.3); }
.sheet-num.answered { background: #e6f7ec; border-color: #22c55e; color: #15803d; }
.sheet-num.marked { border-color: #f59e0b; background: #fffbeb; }
.submit-btn { width: 100%; padding: 10px; border: none; border-radius: 10px; background: linear-gradient(135deg,#1a2b5f,#1e3470); color: #fff; font-size: 14px; font-weight: 700; cursor: pointer; }
.submit-btn:hover { background: linear-gradient(135deg,#c41e3a,#e8384f); }
.sheet-slide-enter-active,.sheet-slide-leave-active { transition: all 0.3s; }
.sheet-slide-enter-from,.sheet-slide-leave-to { opacity: 0; transform: translateX(-20px); }
.question-area { flex: 1; min-width: 0; }
.question-scroll { display: flex; flex-direction: column; gap: 20px; }
.loading-state { text-align: center; padding: 80px 20px; color: #5a6488; }
.loading-spinner { width: 40px; height: 40px; border: 3px solid #e8eaf0; border-top-color: #1a2b5f; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 16px; }
@keyframes spin { to { transform: rotate(360deg); } }
.question-block { background: #fff; border-radius: 16px; padding: 28px; box-shadow: 0 2px 14px rgba(26,43,95,0.05); }
.q-header { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.q-number { font-size: 18px; font-weight: 900; color: #1a2b5f; }
.q-type-badge { font-size: 12px; padding: 4px 14px; border-radius: 8px; background: #eff6ff; color: #3b82f6; font-weight: 600; }
.q-type-badge.multi { background: #fef3c7; color: #d97706; }
.q-type-badge.judge { background: #f5f3ff; color: #7c3aed; }
.mark-badge { font-size: 11px; padding: 3px 10px; border-radius: 8px; background: #fffbeb; color: #b45309; font-weight: 600; }
.q-stem { font-size: 15px; line-height: 1.8; color: #1a2b5f; margin: 0 0 20px; font-weight: 500; }
.q-options { display: flex; flex-direction: column; gap: 10px; }
.multi-hint { padding: 8px 12px; background: #eff6ff; border-radius: 8px; font-size: 12px; color: #3b82f6; margin-bottom: 8px; }
.judge-hint { padding: 8px 12px; background: #f5f3ff; border-radius: 8px; font-size: 12px; color: #7c3aed; margin-bottom: 8px; }
.option-item { display: flex; align-items: center; gap: 12px; padding: 14px 16px; border: 2px solid #e8eaf0; border-radius: 12px; cursor: pointer; transition: all 0.2s; font-size: 14px; color: #333; }
.option-item:hover { border-color: #cbd5e0; background: #f8f9fc; }
.option-item.selected { border-color: #1a2b5f; background: #f0f4ff; color: #1a2b5f; font-weight: 600; }
.option-item.correct { border-color: #22c55e; background: #f0fdf4; }
.option-item.wrong { border-color: #ef4444; background: #fef2f2; }
.option-label { width: 32px; height: 32px; border-radius: 50%; background: #f8f9fc; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; flex-shrink: 0; color: #5a6488; }
.option-item.selected .option-label { background: #1a2b5f; color: #fff; }
.option-item.correct .option-label { background: #22c55e; color: #fff; }
.option-item.wrong .option-label { background: #ef4444; color: #fff; }
.option-label.multi { border-radius: 6px; }
.q-result { margin-top: 16px; padding: 12px 16px; background: #f8f9fc; border-radius: 10px; }
.result-badge { display: inline-block; padding: 4px 12px; border-radius: 8px; font-size: 12px; font-weight: 700; margin-bottom: 8px; }
.correct-badge { background: #d1fae5; color: #065f46; }
.incorrect-badge { background: #fee2e2; color: #991b1b; }
.result-explain { font-size: 13px; color: #5a6488; line-height: 1.6; margin: 0; }
.q-actions { margin-top: 16px; display: flex; justify-content: flex-end; gap: 8px; }
.mark-btn { padding: 6px 16px; border: 1px solid #e8eaf0; border-radius: 8px; background: #fff; font-size: 12px; color: #5a6488; cursor: pointer; }
.mark-btn.marked { background: #fffbeb; border-color: #f59e0b; color: #b45309; }
.modal-overlay { position: fixed; top:0;left:0;right:0;bottom:0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-dialog { background: #fff; border-radius: 16px; padding: 28px; width: 440px; max-width: 90vw; box-shadow: 0 8px 32px rgba(26,43,95,0.15); text-align: center; }
.modal-dialog h4 { margin: 0 0 8px; font-size: 17px; font-weight: 700; color: #1a2b5f; }
.modal-dialog p { font-size: 14px; color: #5a6488; margin: 0 0 20px; }
.modal-actions { display: flex; gap: 12px; justify-content: center; }
.result-icon { font-size: 48px; margin-bottom: 8px; animation: bounceIn 0.6s; }
@keyframes bounceIn { 0%{transform:scale(0.3);opacity:0} 50%{transform:scale(1.1)} 70%{transform:scale(0.9)} 100%{transform:scale(1);opacity:1} }
.result-stats { display: grid; grid-template-columns:1fr 1fr; gap:12px; margin:20px 0; padding:16px; background:#f8f9fc; border-radius:12px; }
.rs-item { text-align: center; }
.rs-label { display: block; font-size: 12px; color: #5a6488; margin-bottom: 4px; }
.rs-value { display: block; font-size: 18px; font-weight: 900; color: #1a2b5f; }
.rs-value.score { color: #c41e3a; }
.rs-value.green { color: #22c55e; }
.result-hint { font-size: 13px; color: #22c55e; font-weight: 600; margin: 0 0 16px; padding: 8px; background: #f0fdf4; border-radius: 8px; }
.se-btn { padding: 10px 24px; border-radius: 20px; font-size: 14px; font-weight: 700; cursor: pointer; transition: all 0.25s; border: none; }
.back-btn { background: #f0f2f5; color: #5a6488; border: 1.5px solid #e8eaf0; }
.back-btn:hover { background: #e8eaf0; }
.generate-btn { background: linear-gradient(135deg,#c41e3a,#e8384f); color: #fff; }
.generate-btn:hover { transform: translateY(-1px); }
.outline-btn { background: #fff; color: #1a2b5f; border: 2px solid #1a2b5f; }
.outline-btn:hover { background: #f0f4ff; }
</style>
