<!-- 答题卡模块 -->
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
                <span :class="['q-type-badge', getTypeClass(q.type)]"> {{ getTypeLabel(q.type) }}</span>
                <span
                  v-if="state.markedQuestions.includes(q.id)"
                  class="mark-badge">
                  已标记</span
                >
              </div>
              <p class="q-stem" v-html="q.stem"></p>
              <div class="q-options">
                <div v-if="q.type === '多选题' || q.type === '不定项' || q.type === '多选'" class="multi-hint">
                  <strong>多选题</strong> — 点击多个选项进行选择
                </div>
                <div
                  v-for="(opt, oidx) in q.options"
                  :key="oidx"
                  :class="[
                    'option-item',
                    {
                      selected: isOptionSelected(q.id, oidx),
                      correct: state.showResult && state.optionLabels[oidx] === q.answer,
                      wrong:
                        state.showResult &&
                        isOptionSelected(q.id, oidx) &&
                        state.optionLabels[oidx] !== q.answer
                    }
                  ]"
                  @click="selectOption(q.id, oidx, q.type)">
                  <span :class="['option-label', { multi: q.type === '多选题' || q.type === '不定项' || q.type === '多选' }]">
                    {{ state.optionLabels[oidx] }}
                    <span v-if="isOptionSelected(q.id, oidx) && (q.type === '多选题' || q.type === '不定项' || q.type === '多选')" class="check-icon">&#10003;</span>
                  </span>
                  <span class="option-text" v-html="opt"></span>
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
                <button class="note-btn" @click="openNoteEditor(q.id)">笔记</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 笔记编辑弹窗 -->
    <div v-if="state.showNoteEditor" class="note-panel-overlay" @click.self="closeNoteEditor">
      <div class="note-panel">
        <div class="note-panel-header">
          <h3>题目笔记</h3>
          <button class="note-panel-close" @click="closeNoteEditor">×</button>
        </div>
        <div class="note-panel-body">
          <textarea
            v-model="state.noteText"
            class="note-textarea"
            placeholder="在此输入笔记内容..."
            rows="6"></textarea>
        </div>
        <div class="note-panel-footer">
          <button class="note-panel-btn delete-note-btn" @click="deleteNote">删除笔记</button>
          <button class="note-panel-btn save-note-btn" @click="saveNote">保存笔记</button>
        </div>
      </div>
    </div>
  </div>
</template>
    .q-type-badge {
      font-size: 17px;
      padding: 4px 14px;
      border-radius: 8px;
      background: #eff6ff;
      color: #3b82f6;
      font-weight: 700;
    }
<style lang="css" scoped>
  .answer-page {
    min-height: 100vh;
    background: #f1f3f8;
    font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }
  .ap-main {
    max-width: 1380px;
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
  .q-type-badge.multi {
    background: #fef3c7;
    color: #d97706;
  }
  .q-type-badge.judge {
    background: #f0fdf4;
    color: #065f46;
  }
  .q-type-badge.fill {
    background: #fef2f2;
    color: #dc2626;
  }
  .q-type-badge.essay {
    background: #f5f3ff;
    color: #7c3aed;
  }
  .q-stem :deep(img.q-img) {
    max-width: 100%; height: auto; max-height: 300px;
    display: block; margin: 10px auto; border-radius: 8px;
    border: 1px solid rgba(0,0,0,0.08); object-fit: contain;
  }
  .option-text :deep(img.q-img) {
    max-width: 100%; height: auto; max-height: 150px;
    display: block; margin: 6px 0; border-radius: 6px;
    border: 1px solid rgba(0,0,0,0.06); object-fit: contain;
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
  .multi-hint {
    padding: 8px 12px; background: #eff6ff;
    border-radius: 8px; font-size: 12px;
    color: #3b82f6; margin-bottom: 8px;
  }
  .multi-hint strong {
    font-weight: 700; color: #1d4ed8;
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
  .option-label.multi {
    border-radius: 6px;
    position: relative;
  }
  .option-label .check-icon {
    position: absolute;
    top: -4px; right: -4px;
    width: 16px; height: 16px;
    background: #1a2b5f; color: #fff;
    border-radius: 50%;
    font-size: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
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
  .note-btn {
    padding: 6px 16px; border: 1px solid #dbeafe; border-radius: 8px;
    background: #eff6ff; font-size: 12px; color: #3b82f6; cursor: pointer;
    transition: all 0.2s;
  }
  .note-btn:hover { background: #dbeafe; border-color: #3b82f6; }
  /* 笔记弹窗 */
  .note-panel-overlay {
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.45); display: flex; align-items: center;
    justify-content: center; z-index: 1000;
  }
  .note-panel {
    background: #fff; border-radius: 16px; padding: 24px;
    width: 440px; max-width: 90vw; box-shadow: 0 8px 32px rgba(26,43,95,0.15);
  }
  .note-panel-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
  .note-panel-header h3 { margin: 0; font-size: 15px; font-weight: 700; color: #1a2b5f; }
  .note-panel-close { width: 28px; height: 28px; border: none; background: transparent; font-size: 20px; color: #8a8faa; cursor: pointer; border-radius: 8px; }
  .note-panel-close:hover { background: #f0f2f5; color: #1a2b5f; }
  .note-textarea {
    width: 100%; padding: 12px; border: 1.5px solid #e0e3e8; border-radius: 10px;
    font-size: 13px; color: #1a2b5f; font-family: inherit; resize: vertical;
    outline: none; box-sizing: border-box;
  }
  .note-textarea:focus { border-color: #c41e3a; }
  .note-panel-footer { display: flex; gap: 10px; justify-content: flex-end; margin-top: 14px; }
  .note-panel-btn { padding: 7px 18px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; transition: all 0.25s; }
  .delete-note-btn { background: #fee2e2; color: #dc2626; }
  .delete-note-btn:hover { background: #fecaca; }
  .save-note-btn { background: #1a2b5f; color: #fff; }
  .save-note-btn:hover { background: #c41e3a; }
</style>
