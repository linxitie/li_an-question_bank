<template>
  <div class="paper-result-page">
    <main class="pr-main">
      <!-- 返回 -->
      <div class="pr-back"><button class="back-link" @click="$router.push('/student/papers')">← 返回试卷列表</button></div>

      <!-- 加载状态 -->
      <div v-if="state.loading" class="loading-state">
        <div class="loading-spinner"></div>
        <p>正在加载成绩报告...</p>
      </div>

      <!-- 成绩摘要 -->
      <div v-else-if="state.record" class="pr-content">
        <div class="result-header">
          <div class="header-top">
            <h2>📊 {{ state.record.paper_name || '试卷成绩报告' }}</h2>
          </div>
          <div class="score-summary">
            <div class="score-main">
              <span class="score-big">{{ state.record.total_score || 0 }}</span>
              <span class="score-divider">/</span>
              <span class="score-max">{{ state.record.max_score || 100 }}</span>
            </div>
            <div class="score-meta">
              <div class="meta-item">
                <span class="meta-label">正确率</span>
                <span class="meta-value green">{{ state.accuracy }}%</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">用时</span>
                <span class="meta-value">{{ formatTime(state.record.duration_used || 0) }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">正确/错误</span>
                <span class="meta-value">{{ state.correctCount }} / {{ state.wrongCount }}</span>
              </div>
              <div class="meta-item">
                <span class="meta-label">完成时间</span>
                <span class="meta-value" style="font-size:13px">{{ formatDate(state.record.end_time) }}</span>
              </div>
            </div>
          </div>
          <div class="result-actions">
            <button class="pr-btn primary" @click="$router.push('/student/papers')">返回试卷列表</button>
            <button class="pr-btn outline" @click="retakeExam">再考一次</button>
            <button class="pr-btn outline" @click="goWrongQuestions">查看错题集</button>
          </div>
        </div>

        <!-- 逐题回顾 -->
        <div class="question-review-list">
          <h3>📝 逐题回顾</h3>
          <div v-for="(d, idx) in state.details" :key="d.question_id" class="review-card">
            <div class="review-header">
              <span class="review-num">第 {{ idx + 1 }} 题</span>
              <span :class="['review-type', getTypeClass(d.question_type)]">{{ getTypeLabel(d.question_type) }}</span>
              <span :class="['review-result', d.is_correct ? 'correct' : 'incorrect']">
                {{ d.is_correct ? '✓ 正确' : '✗ 错误' }}
              </span>
              <span class="review-score" v-if="d.score_obtained !== undefined">+{{ d.score_obtained }}分</span>
            </div>
            <p class="review-stem" v-html="d.question_content"></p>

            <!-- 选项回顾 -->
            <div class="review-options" v-if="d.options && d.options.length">
              <div v-for="(opt, oidx) in d.options" :key="oidx"
                :class="['review-option', {
                  'is-correct-answer': isCorrectAnswer(opt, d.correct_answer),
                  'is-user-wrong': isUserWrongAnswer(opt, oidx, d)
                }]">
                <span class="ro-marker">{{ String.fromCharCode(65 + oidx) }}.</span>
                <span class="ro-text" v-html="opt"></span>
                <span v-if="isCorrectAnswer(opt, d.correct_answer)" class="ro-tag correct-tag">✓ 正确答案</span>
                <span v-if="isUserWrongAnswer(opt, oidx, d)" class="ro-tag wrong-tag">✗ 你的答案</span>
              </div>
            </div>

            <!-- 答案对比 -->
            <div class="review-answers" v-if="d.correct_answer">
              <div class="answer-row">
                <span class="answer-label">你的答案：</span>
                <span :class="d.is_correct ? 'text-green' : 'text-red'">{{ d.student_answer || '(未作答)' }}</span>
              </div>
              <div class="answer-row">
                <span class="answer-label">正确答案：</span>
                <span class="text-green">{{ d.correct_answer }}</span>
              </div>
            </div>

            <!-- 解析 -->
            <div class="review-analysis" v-if="d.answer_analysis">
              <div class="analysis-toggle" @click="toggleAnalysis(d.question_id)">
                📖 答案解析 {{ state.expandedAnalysis[d.question_id] ? '▲' : '▼' }}
              </div>
              <div v-if="state.expandedAnalysis[d.question_id]" class="analysis-content">
                {{ d.answer_analysis }}
              </div>
            </div>
          </div>

          <!-- 无数据 -->
          <div v-if="state.details.length === 0" class="empty-state">
            <p>暂无答题详情</p>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive, onMounted } from 'vue';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'PaperResult',
  setup() {
    const provider = useProvider({ id: 'paper_result', version: '1' });
    const state = reactive({
      loading: true,
      record: null,
      details: [],
      correctCount: 0,
      wrongCount: 0,
      accuracy: 0,
      expandedAnalysis: {},
    });
    return { state, provider };
  },
  methods: {
    formatTime(s) {
      s = Math.max(0, Math.floor(s || 0));
      var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
      if (h > 0) return h + '时' + m + '分' + sec + '秒';
      if (m > 0) return m + '分' + sec + '秒';
      return sec + '秒';
    },
    formatDate(d) {
      if (!d) return '-';
      return new Date(d).toLocaleString('zh-CN');
    },
    getTypeLabel(type) {
      var map = {
        '单选题': '[单选]', '单选': '[单选]', '多选题': '[多选]', '不定项': '[多选]', '多选': '[多选]',
        '判断题': '[判断]', '论述题': '[论述]', '简答题': '[简答]', '案例分析题': '[案例]', '写作题': '[写作]'
      };
      return map[type] || '[单选]';
    },
    getTypeClass(type) {
      if (['多选题', '不定项', '多选'].indexOf(type) >= 0) return 'multi';
      if (['论述题', '简答题', '案例分析题', '写作题'].indexOf(type) >= 0) return 'essay';
      return '';
    },

    // 解析选项（从question_content中提取，或使用detail数据）
    parseOptions(detail) {
      if (detail.options && Array.isArray(detail.options)) return detail.options;
      // 如果后端没返回options，从question_content提取
      var content = detail.question_content || '';
      var parts = content.split(/[A-H][.、．)）]/);
      if (parts.length > 1) {
        var options = [];
        var matches = content.match(/([A-H])[.、．)）]\s*([^\n]+)/g);
        if (matches) {
          return matches.map(function(m) { return m.replace(/^[A-H][.、．)）]\s*/, '').trim(); });
        }
      }
      return [];
    },

    isCorrectAnswer(opt, correctAnswer) {
      if (!correctAnswer) return false;
      // 选项文本包含正确答案字母标记
      var label = opt.match(/^([A-H])/);
      if (label && correctAnswer.indexOf(label[1]) >= 0) return true;
      // 检查答案文本匹配（前5个字符）
      var optText = opt.replace(/^[A-H][.、．)）]\s*/, '').trim();
      return optText.length > 0 && correctAnswer.indexOf(optText.substring(0, 5)) >= 0;
    },

    isUserWrongAnswer(opt, oidx, detail) {
      if (detail.is_correct) return false;
      var studentAns = detail.student_answer || '';
      var letter = String.fromCharCode(65 + oidx);
      return studentAns.indexOf(letter) >= 0;
    },

    toggleAnalysis(qid) {
      this.state.expandedAnalysis[qid] = !this.state.expandedAnalysis[qid];
    },

    async loadResult() {
      var recordId = this.$route.query.record_id;
      if (!recordId) { this.state.loading = false; return; }

      try {
        var res = await window.__VTJ_AUTH__.apiFetch('/api/exams/records/' + recordId, {
          headers: window.__VTJ_AUTH__.getJsonHeaders()
        });
        if (!res.ok) throw new Error('加载失败');
        var data = await res.json();

        this.state.record = data;
        var details = data.details || [];
        this.state.details = details;
        this.state.correctCount = details.filter(function(d) { return d.is_correct; }).length;
        this.state.wrongCount = details.length - this.state.correctCount;
        this.state.accuracy = details.length > 0
          ? Math.round((this.state.correctCount / details.length) * 100)
          : 0;
      } catch(e) {
        console.error('[PaperResult] 加载失败:', e);
      } finally {
        this.state.loading = false;
      }
    },

    async retakeExam() {
      if (!this.state.record || !this.state.record.paper_id) return;
      try {
        var res = await window.__VTJ_AUTH__.apiFetch('/api/exams/' + this.state.record.paper_id + '/start', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }
        });
        var data = await res.json();
        if (data.record_id) {
          this.$router.push('/paper-answer?record_id=' + data.record_id + '&paper_id=' + this.state.record.paper_id);
        }
      } catch(e) {
        alert('重新开始失败: ' + (e.message || '网络错误'));
      }
    },

    goWrongQuestions() {
      this.$router.push('/page/wrong_questions');
    },
  },
  mounted() {
    this.loadResult();
  },
});
</script>

<style scoped>
.paper-result-page { min-height: 100vh; background: #f0f2f5; font-size: 15px; }
.pr-main { max-width: 800px; margin: 0 auto; padding: 24px 16px; }
.pr-back { margin-bottom: 16px; }
.back-link { background: none; border: none; color: #409EFF; cursor: pointer; font-size: 14px; }

/* 成绩摘要 */
.result-header { background: #fff; border-radius: 12px; padding: 32px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); margin-bottom: 24px; }
.header-top { margin-bottom: 20px; }
.header-top h2 { margin: 0; color: #1A3C6D; font-size: 22px; }
.score-summary { display: flex; align-items: center; gap: 32px; margin-bottom: 24px; padding-bottom: 24px; border-bottom: 1px solid #f0f0f0; }
.score-main { display: flex; align-items: baseline; gap: 4px; }
.score-big { font-size: 48px; font-weight: 800; color: #1A3C6D; line-height: 1; }
.score-divider { font-size: 28px; color: #ccc; }
.score-max { font-size: 24px; color: #999; }
.score-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; flex: 1; }
.meta-item { display: flex; flex-direction: column; gap: 4px; }
.meta-label { font-size: 12px; color: #999; }
.meta-value { font-size: 18px; font-weight: 700; color: #1A3C6D; }
.meta-value.green { color: #67c23a; }
.result-actions { display: flex; gap: 12px; }
.pr-btn { padding: 10px 24px; border-radius: 6px; cursor: pointer; font-size: 14px; border: none; }
.pr-btn.primary { background: #1A3C6D; color: #fff; }
.pr-btn.outline { background: #fff; color: #1A3C6D; border: 1px solid #1A3C6D; }

/* 逐题回顾 */
.question-review-list { display: flex; flex-direction: column; gap: 16px; }
.question-review-list h3 { color: #1A3C6D; margin: 0 0 8px; }
.review-card { background: #fff; border-radius: 8px; padding: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.review-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.review-num { font-weight: 700; color: #1A3C6D; }
.review-type { padding: 2px 8px; border-radius: 10px; font-size: 12px; background: #e6f0ff; color: #409EFF; }
.review-type.multi { background: #fff7e6; color: #e6a23c; }
.review-type.essay { background: #f0f5e8; color: #67c23a; }
.review-result { padding: 2px 10px; border-radius: 10px; font-size: 12px; font-weight: 600; }
.review-result.correct { background: #f0f9eb; color: #67c23a; }
.review-result.incorrect { background: #fef0f0; color: #f56c6c; }
.review-score { font-size: 12px; color: #999; }
.review-stem { line-height: 1.8; color: #333; margin: 0 0 12px; }
.review-stem :deep(img) { max-width: 100%; border-radius: 4px; }

/* 选项回顾 */
.review-options { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.review-option { display: flex; align-items: flex-start; gap: 8px; padding: 8px 12px; border: 1px solid #e8e8e8; border-radius: 6px; }
.review-option.is-correct-answer { background: #f0f9eb; border-color: #67c23a; }
.review-option.is-user-wrong { background: #fef0f0; border-color: #f56c6c; }
.ro-marker { font-weight: 600; color: #666; min-width: 20px; }
.ro-text { flex: 1; }
.ro-tag { font-size: 11px; padding: 1px 6px; border-radius: 8px; font-weight: 600; white-space: nowrap; }
.correct-tag { background: #67c23a; color: #fff; }
.wrong-tag { background: #f56c6c; color: #fff; }

/* 答案对比 */
.review-answers { display: flex; flex-direction: column; gap: 6px; padding: 12px; background: #f9f9f9; border-radius: 6px; margin-bottom: 12px; }
.answer-row { display: flex; gap: 8px; font-size: 14px; }
.answer-label { color: #999; min-width: 80px; }
.text-green { color: #67c23a; font-weight: 600; }
.text-red { color: #f56c6c; font-weight: 600; }

/* 解析 */
.review-analysis { margin-top: 8px; }
.analysis-toggle { cursor: pointer; padding: 8px 12px; background: #f5f7fa; border-radius: 6px; font-size: 14px; color: #409EFF; }
.analysis-content { margin-top: 8px; padding: 12px; background: #fafafa; border-radius: 6px; line-height: 1.8; color: #666; font-size: 14px; }

.loading-state, .empty-state { text-align: center; padding: 60px 0; color: #999; }
.loading-spinner { width: 40px; height: 40px; border: 3px solid #e8e8e8; border-top-color: #409EFF;
  border-radius: 50%; animation: spin .8s linear infinite; margin: 0 auto 16px; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
