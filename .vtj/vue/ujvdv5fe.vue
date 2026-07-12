<template>
  <div class="answer-page">
    <NavBar></NavBar>
    <main class="ap-main">
      <div class="ap-toolbar">
        <div class="toolbar-left">
          <button class="tool-btn" @click="toggleAnswerSheet">
            <XIcon :icon="Grid" :size="18" color="#1a2b5f"></XIcon>
            <span> 答题卡</span>
            <span v-if="state.sheetVisible" class="tool-indicator"></span>
          </button>
          <div class="progress-info">
            <span class="progress-text">
              <span>
                <span> {{ state.currentIndex + 1 }}</span>
                <span> /</span>
                <span> {{ state.questions.length }}</span></span
              ></span
            >
          </div>
        </div>
        <div class="toolbar-right">
          <div class="timer-display">
            <XIcon
              :icon="AlarmClock"
              :size="18"
              :color="state.timeLeft < 300 ? '#c41e3a' : '#1a2b5f'"></XIcon>
            <span :class="['timer-text', { urgent: state.timeLeft < 300 }]">
              {{ formatTime(state.timeLeft) }}</span
            >
          </div>
          <button class="exit-btn" @click="handleExit">
            <XIcon :icon="CloseBold" :size="16" color="#ffffff"></XIcon>
            <span> 退出</span>
          </button>
        </div>
      </div>
      <div class="ap-body">
        <Transition name="sheet-slide">
          <div v-if="state.sheetVisible" class="answer-sheet-panel">
            <div class="sheet-header">
              <h4>答题卡</h4>
              <span class="sheet-close" @click="state.sheetVisible = false">
                ✕</span
              >
            </div>
            <div class="sheet-stats">
              <span class="stat-item">
                <span> 已答</span>
                <b> {{ answeredCount }}</b></span
              >
              <span class="stat-item">
                <span> 未答</span>
                <b> {{ state.questions.length - answeredCount }}</b></span
              >
            </div>
            <div class="sheet-grid">
              <button
                v-for="(q, idx) in state.questions"
                :key="q.id"
                :class="[
                  'sheet-num',
                  {
                    active: idx === state.currentIndex,
                    answered: state.answers[q.id] !== undefined,
                    marked: state.markedQuestions.includes(q.id)
                  }
                ]"
                @click="jumpToQuestion(idx)">
                {{ idx + 1 }}
              </button>
            </div>
            <button class="submit-btn" @click="handleSubmit">交卷</button>
          </div></Transition
        >
        <div ref="questionAreaRef" class="question-area">
          <div ref="scrollContainerRef" class="question-scroll">
            <div
              v-for="(q, idx) in state.questions"
              :key="q.id"
              :ref="'question_' + q.id"
              class="question-block">
              <div class="q-header">
                <span class="q-number">
                  <span>
                    <span> {{ idx + 1 }}</span>
                    <span> .</span></span
                  ></span
                >
                <span class="q-type-badge"> {{ q.type }}</span>
                <span
                  v-if="state.markedQuestions.includes(q.id)"
                  class="mark-badge">
                  已标记</span
                >
              </div>
              <p class="q-stem">
                {{ q.stem }}
              </p>
              <div class="q-options">
                <div
                  v-for="(opt, oidx) in q.options"
                  :key="oidx"
                  :class="[
                    'option-item',
                    {
                      selected: isOptionSelected(q.id, oidx),
                      correct: state.showResult && oidx === q.answer,
                      wrong:
                        state.showResult &&
                        isOptionSelected(q.id, oidx) &&
                        oidx !== q.answer
                    }
                  ]"
                  @click="selectOption(q.id, oidx, q.type)">
                  <span class="option-label">
                    {{ state.optionLabels[oidx] }}</span
                  >
                  <span class="option-text"> {{ opt }}</span>
                </div>
              </div>
              <div v-if="state.showResult" class="q-result">
                <span class="result-badge">
                  {{ isCorrect(q) ? '✓ 回答正确' : '✗ 回答错误' }}</span
                >
                <p v-if="q.explain" class="result-explain">
                  {{ q.explain }}
                </p>
              </div>
              <div class="q-actions">
                <button
                  :class="[
                    'mark-btn',
                    { marked: state.markedQuestions.includes(q.id) }
                  ]"
                  @click="toggleMark(q.id)">
                  {{
                    state.markedQuestions.includes(q.id) ? '取消标记' : '标记'
                  }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive, Transition } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { Grid, AlarmClock, CloseBold } from '@vtj/icons';
  import NavBar from './ijvdn7sw.vue';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'AnswerPage',
    components: { NavBar, XIcon, Transition },
    setup(props) {
      const provider = useProvider({ id: 'ujvdv5fe', version: '1778918968644' });
      const state = reactive({
        answers: {},
        timeLeft: 7200,
        questions: [],
        showResult: false,
        currentIndex: 0,
        optionLabels: ['A', 'B', 'C', 'D', 'E', 'F'],
        sheetVisible: false,
        markedQuestions: []
      });
      return { state, props, provider, Grid, AlarmClock, CloseBold };
    },
    computed: {
      answeredCount() {
        return Object.keys(this.state.answers).length;
      }
    },
    methods: {
      isCorrect(q) {
        return this.state.answers[q.id] === q.answer;
      },
      formatTime(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;
        return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
      },
      handleExit() {
        this.$router.back();
      },
      startTimer() {
        this._timer = setInterval(() => {
          if (this.state.timeLeft > 0) {
            this.state.timeLeft--;
          } else {
            this.handleSubmit();
          }
        }, 1000);
      },
      toggleMark(qId) {
        const idx = this.state.markedQuestions.indexOf(qId);
        if (idx >= 0) {
          this.state.markedQuestions.splice(idx, 1);
        } else {
          this.state.markedQuestions.push(qId);
        }
      },
      handleSubmit() {
        this.state.showResult = true;
        this.$message.success('试卷已提交');
      },
      selectOption(qId, oidx, type) {
        if (this.state.showResult) return;
        if (type === '单选') {
          this.state.answers[qId] = oidx;
        } else {
          const current = this.state.answers[qId] || [];
          if (current.includes(oidx)) {
            this.state.answers[qId] = current.filter((o) => o !== oidx);
          } else {
            this.state.answers[qId] = [...current, oidx];
          }
        }
      },
      loadQuestions() {
        this.state.questions = [
          {
            id: 1,
            type: '单选',
            stem: '根据《公安机关组织管理条例》，下列哪项不属于公安机关的法定职责？',
            options: [
              '维护社会治安秩序',
              '管理户籍',
              '审理刑事案件',
              '管理特种行业'
            ],
            answer: 2,
            explain: '审理刑事案件属于人民法院的职责，公安机关负责侦查。'
          },
          {
            id: 2,
            type: '单选',
            stem: '人民警察在非工作时间，遇有其职责范围内的紧急情况，应当：',
            options: ['立即回避', '履行职责', '向上级请示', '等待工作时间处理'],
            answer: 1,
            explain:
              '《人民警察法》第十九条规定，人民警察在非工作时间，遇有其职责范围内的紧急情况，应当履行职责。'
          },
          {
            id: 3,
            type: '多选',
            stem: '下列哪些属于公安行政执法的基本原则？（多选）',
            options: [
              '合法性原则',
              '合理性原则',
              '效率优先原则',
              '程序正当原则',
              '便民原则'
            ],
            answer: 0,
            explain:
              '公安行政执法应遵循合法性、合理性、程序正当等基本原则。多选题答案为ABD。'
          },
          {
            id: 4,
            type: '单选',
            stem: '下列哪项不属于治安管理处罚的种类？',
            options: ['警告', '罚款', '拘役', '行政拘留'],
            answer: 2,
            explain: '拘役属于刑罚种类，不属于治安管理处罚。'
          },
          {
            id: 5,
            type: '单选',
            stem: '公安民警在现场处置时，应当优先采取的措施是：',
            options: [
              '立即使用武力',
              '疏散围观群众',
              '语言控制与劝导',
              '呼叫增援'
            ],
            answer: 2,
            explain: '现场处置应坚持最小武力原则，优先采用语言控制与劝导。'
          }
        ];
      },
      jumpToQuestion(idx) {
        this.state.currentIndex = idx;
        const el = this.$refs['question_' + this.state.questions[idx].id];
        if (el && el[0]) {
          el[0].scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      },
      isOptionSelected(qId, oidx) {
        const ans = this.state.answers[qId];
        if (Array.isArray(ans)) return ans.includes(oidx);
        return ans === oidx;
      },
      toggleAnswerSheet() {
        this.state.sheetVisible = !this.state.sheetVisible;
      }
    },
    mounted() {
      this.loadQuestions();
      this.startTimer();
    },
    beforeUnmount() {
      if (this._timer) {
        clearInterval(this._timer);
        this._timer = null;
      }
    }
  })
</script>
<style lang="css" scoped>
  .answer-page {
    min-height: 100vh;
    background: #f1f3f8;
    font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }
  .ap-main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 16px 32px 40px;
  }
  /* 工具栏 */
  .ap-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #ffffff;
    border-radius: 14px;
    padding: 12px 20px;
    box-shadow: 0 2px 12px rgba(26, 43, 95, 0.06);
    margin-bottom: 16px;
    position: sticky;
    top: 80px;
    z-index: 50;
  }
  .toolbar-left {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .tool-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border: 1px solid #e8eaf0;
    border-radius: 10px;
    background: #f8f9fc;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    color: #1a2b5f;
    transition: all 0.3s;
    position: relative;
  }
  .tool-btn:hover {
    background: #f0f2f5;
  }
  .tool-indicator {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #c41e3a;
    position: absolute;
    top: 6px;
    right: 6px;
  }
  .progress-text {
    font-size: 14px;
    font-weight: 700;
    color: #1a2b5f;
  }
  .toolbar-right {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .timer-display {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    background: #f8f9fc;
    border-radius: 10px;
  }
  .timer-text {
    font-size: 18px;
    font-weight: 900;
    color: #1a2b5f;
    font-family: 'SF Mono', 'DIN Alternate', 'Menlo', monospace;
    letter-spacing: 1px;
  }
  .timer-text.urgent {
    color: #c41e3a;
    animation: pulse 1s ease-in-out infinite;
  }
  @keyframes pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.6;
    }
  }
  .exit-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 8px 18px;
    border: none;
    border-radius: 10px;
    background: linear-gradient(135deg, #c41e3a, #e8384f);
    color: #fff;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
  }
  .exit-btn:hover {
    transform: scale(1.03);
    box-shadow: 0 2px 10px rgba(196, 30, 58, 0.3);
  }
  .ap-body {
    display: flex;
    gap: 20px;
    position: relative;
  }
  /* 答题卡面板 */
  .answer-sheet-panel {
    width: 240px;
    flex-shrink: 0;
    background: #ffffff;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 14px rgba(26, 43, 95, 0.08);
    align-self: flex-start;
    position: sticky;
    top: 160px;
  }
  .sheet-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }
  .sheet-header h4 {
    font-size: 15px;
    font-weight: 700;
    color: #1a2b5f;
    margin: 0;
  }
  .sheet-close {
    font-size: 16px;
    color: #8a8faa;
    cursor: pointer;
  }
  .sheet-stats {
    display: flex;
    gap: 16px;
    margin-bottom: 16px;
    font-size: 12px;
    color: #5a6488;
  }
  .sheet-stats b {
    color: #1a2b5f;
  }
  .sheet-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 8px;
    margin-bottom: 16px;
  }
  .sheet-num {
    width: 36px;
    height: 36px;
    border: 1px solid #e8eaf0;
    border-radius: 8px;
    background: #f8f9fc;
    font-size: 12px;
    font-weight: 700;
    color: #5a6488;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .sheet-num.active {
    border-color: #1a2b5f;
    box-shadow: 0 0 0 2px rgba(26, 43, 95, 0.3);
  }
  .sheet-num.answered {
    background: #e6f7ec;
    border-color: #22c55e;
    color: #15803d;
  }
  .sheet-num.marked {
    border-color: #f59e0b;
    background: #fffbeb;
  }
  .submit-btn {
    width: 100%;
    padding: 10px;
    border: none;
    border-radius: 10px;
    background: linear-gradient(135deg, #1a2b5f, #1e3470);
    color: #fff;
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s;
  }
  .submit-btn:hover {
    background: linear-gradient(135deg, #c41e3a, #e8384f);
  }
  .sheet-slide-enter-active,
  .sheet-slide-leave-active {
    transition: all 0.3s ease;
  }
  .sheet-slide-enter-from,
  .sheet-slide-leave-to {
    opacity: 0;
    transform: translateX(-20px);
  }
  /* 题目区域 */
  .question-area {
    flex: 1;
    min-width: 0;
  }
  .question-scroll {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  .question-block {
    background: #ffffff;
    border-radius: 16px;
    padding: 28px;
    box-shadow: 0 2px 14px rgba(26, 43, 95, 0.05);
  }
  .q-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 16px;
  }
  .q-number {
    font-size: 18px;
    font-weight: 900;
    color: #1a2b5f;
  }
  .q-type-badge {
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 8px;
    background: #eff6ff;
    color: #3b82f6;
    font-weight: 600;
  }
  .mark-badge {
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 8px;
    background: #fffbeb;
    color: #b45309;
    font-weight: 600;
  }
  .q-stem {
    font-size: 15px;
    line-height: 1.8;
    color: #1a2b5f;
    margin: 0 0 20px;
    font-weight: 500;
  }
  .q-options {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .option-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 16px;
    border: 2px solid #e8eaf0;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.2s;
    font-size: 14px;
    color: #333;
  }
  .option-item:hover {
    border-color: #cbd5e0;
    background: #f8f9fc;
  }
  .option-item.selected {
    border-color: #1a2b5f;
    background: #f0f4ff;
    color: #1a2b5f;
    font-weight: 600;
  }
  .option-item.correct {
    border-color: #22c55e;
    background: #f0fdf4;
  }
  .option-item.wrong {
    border-color: #ef4444;
    background: #fef2f2;
  }
  .option-label {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: #f8f9fc;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 14px;
    flex-shrink: 0;
    color: #5a6488;
  }
  .option-item.selected .option-label {
    background: #1a2b5f;
    color: #fff;
  }
  .option-item.correct .option-label {
    background: #22c55e;
    color: #fff;
  }
  .option-item.wrong .option-label {
    background: #ef4444;
    color: #fff;
  }
  .q-result {
    margin-top: 16px;
    padding: 12px 16px;
    background: #f8f9fc;
    border-radius: 10px;
  }
  .result-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 700;
    margin-bottom: 8px;
  }
  .result-badge.correct {
    background: #d1fae5;
    color: #065f46;
  }
  .result-badge.incorrect {
    background: #fee2e2;
    color: #991b1b;
  }
  .result-explain {
    font-size: 13px;
    color: #5a6488;
    line-height: 1.6;
    margin: 0;
  }
  .q-actions {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }
  .mark-btn {
    padding: 6px 16px;
    border: 1px solid #e8eaf0;
    border-radius: 8px;
    background: #fff;
    font-size: 12px;
    color: #5a6488;
    cursor: pointer;
    transition: all 0.2s;
  }
  .mark-btn.marked {
    background: #fffbeb;
    border-color: #f59e0b;
    color: #b45309;
  }
</style>
