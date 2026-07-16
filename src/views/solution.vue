<!-- 交卷结果页 -->
<template>
  <div class="solution-page">
    <!-- 顶部 -->
    <div class="sol-header">
      <span class="sol-header-title">练习结果</span>
    </div>

    <!-- 无数据 -->
    <div class="sol-empty" v-if="!result">
      <h3>没有练习记录</h3>
      <p>请先完成一次练习后再查看结果</p>
      <button class="btn-sol-primary" @click="backToBank">返回题库</button>
    </div>

    <template v-if="result">
      <!-- 成绩卡片 -->
      <div class="sol-score-card">
        <div class="score-ring">
          <svg width="160" height="160" viewBox="0 0 160 160">
            <circle cx="80" cy="80" r="70" fill="none" stroke="#e8ecf2" stroke-width="10"></circle>
            <circle cx="80" cy="80" r="70" fill="none" stroke="url(#grad)" stroke-width="10"
              stroke-linecap="round" transform="rotate(-90 80 80)"
              :stroke-dasharray="(2 * Math.PI * 70)"
              :stroke-dashoffset="(2 * Math.PI * 70 * (1 - result.score / 100))"></circle>
            <defs>
              <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stop-color="#c41e3a"></stop>
                <stop offset="100%" stop-color="#e8384f"></stop>
              </linearGradient>
            </defs>
          </svg>
          <div class="score-text">
            <span class="score-num">{{ result.score }}</span>
            <span class="score-unit">分</span>
          </div>
        </div>
        <div class="score-stats">
          <div class="stat-item">
            <span class="stat-num correct">{{ result.correct }}</span>
            <span class="stat-label">正确</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-num wrong">{{ result.wrong }}</span>
            <span class="stat-label">错误</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-num">{{ result.total }}</span>
            <span class="stat-label">总计</span>
          </div>
        </div>
        <div class="score-time">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8899aa" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
          <span>用时 {{ formattedTime }}</span>
        </div>
      </div>

      <!-- 评价 -->
      <div class="sol-comment">
        <span :style="{ color: commentColor }">{{ commentText }}</span>
      </div>

      <!-- 答题详情 -->
      <div class="sol-details">
        <div class="sol-detail-header">
          <h3>答题详情</h3>
          <span class="sol-tag">{{ result.subject === 'xc' ? '行测' : result.subject === 'sl' ? '申论' : '公专' }} / {{ result.subcategory }}</span>
        </div>
        <div class="sol-detail-list">
          <div class="sol-q-card" v-for="(d, idx) in result.details" :key="idx" :class="{ 'q-correct': d.is_correct, 'q-wrong': !d.is_correct }">
            <div class="sol-q-header">
              <span class="sol-q-num">第 {{ idx + 1 }} 题</span>
              <span class="sol-q-result" :class="d.is_correct ? 'result-ok' : 'result-fail'">
                <svg v-if="d.is_correct" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
                <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#e8384f" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                {{ d.is_correct ? '正确' : '错误' }}
              </span>
            </div>
            <div class="sol-q-content">{{ d.question_content }}</div>
            <div class="sol-q-options" v-if="d.options && d.options.length">
              <span class="sol-opt" v-for="opt in d.options" :key="opt.key"
                :class="{ 'opt-right': opt.key === d.correct_answer, 'opt-user-wrong': opt.key === d.user_answer && !d.is_correct }">
                {{ opt.key }}. {{ opt.value }}
              </span>
            </div>
            <div class="sol-q-answers">
              <span class="sol-ans-row">
                你的答案：<strong :class="d.is_correct ? 'ans-ok' : 'ans-fail'">{{ d.user_answer }}</strong>
              </span>
              <span class="sol-ans-row" v-if="!d.is_correct">
                正确答案：<strong class="ans-ok">{{ d.correct_answer }}</strong>
              </span>
            </div>
            <div class="sol-q-analysis" v-if="d.answer_analysis && !d.is_correct">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#f5a623" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
              <span>{{ d.answer_analysis }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部操作 -->
      <div class="sol-actions">
        <button class="btn-sol-outline" @click="backToBank">返回题库</button>
        <button class="btn-sol-primary" @click="retryExercise">再练一次</button>
      </div>
    </template>
  </div>
</template>

<script>
import { defineComponent, reactive, computed } from 'vue';

export default defineComponent({
  name: 'SolutionPage',
  setup() {
    return {};
  },
  computed: {
    result() {
      try {
        var raw = sessionStorage.getItem('exercise_result');
        return raw ? JSON.parse(raw) : null;
      } catch(e) {
        return null;
      }
    },
    formattedTime() {
      if (!this.result) return '00:00';
      var sec = this.result.time || 0;
      var m = Math.floor(sec / 60);
      var s = sec % 60;
      return (m < 10 ? '0' + m : m) + '分' + (s < 10 ? '0' + s : s) + '秒';
    },
    commentText() {
      if (!this.result) return '';
      var s = this.result.score;
      if (s >= 90) return '非常出色！继续保持这份优秀！';
      if (s >= 75) return '表现良好，再接再厉！';
      if (s >= 60) return '还有提升空间，加油！';
      return '需要加强练习，别灰心！';
    },
    commentColor() {
      if (!this.result) return '#8899aa';
      var s = this.result.score;
      if (s >= 90) return '#22c55e';
      if (s >= 75) return '#3b82f6';
      if (s >= 60) return '#f5a623';
      return '#e8384f';
    },
  },
  methods: {
    retryExercise() {
      if (!this.result) return;
      var subject = this.result.subject || 'xc';
      var subcategory = this.result.subcategory || '';
      this.$router.push('/exercise?subject=' + subject + '&subcategory=' + encodeURIComponent(subcategory));
    },
    backToBank() {
      sessionStorage.setItem('refresh_practice', '1');
      this.$router.push('/');
    },
  },
});
</script>

<style scoped>
.solution-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  padding-bottom: 40px;
}
/* 顶部 */
.sol-header {
  background: linear-gradient(135deg, #0a1628 0%, #12233f 30%, #1a2a4a 100%);
  border-bottom: 2px solid rgba(200,22,30,0.25);
  padding: 20px 32px;
  text-align: center;
}
.sol-header-title { color: #ffffff; font-size: 20px; font-weight: 700; }
.sol-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px 32px;
  text-align: center;
}
.sol-empty h3 { color: #1a2b5f; margin: 16px 0 8px; }
.sol-empty p { color: #8899aa; margin-bottom: 24px; }
/* 成绩卡片 */
.sol-score-card {
  max-width: 1000px;
  margin: 32px auto;
  background: #ffffff;
  border-radius: 20px;
  padding: 36px 32px;
  box-shadow: 0 4px 24px rgba(26,43,95,0.08);
  border: 1px solid rgba(200,22,30,0.08);
  text-align: center;
}
.score-ring { position: relative; display: inline-block; margin-bottom: 20px; }
.score-text {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: baseline;
  gap: 2px;
}
.score-num { font-size: 48px; font-weight: 800; color: #c41e3a; line-height: 1; }
.score-unit { font-size: 18px; color: #8899aa; font-weight: 600; }
.score-stats {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin: 20px 0;
}
.stat-item { display: flex; flex-direction: column; align-items: center; padding: 0 28px; }
.stat-num { font-size: 28px; font-weight: 800; color: #1a2b5f; }
.stat-num.correct { color: #22c55e; }
.stat-num.wrong { color: #e8384f; }
.stat-label { font-size: 17px; color: #8899aa; margin-top: 4px; }
.stat-divider { width: 1px; height: 40px; background: #e8ecf2; }
.score-time {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #8899aa;
  font-size: 17px;
  padding-top: 16px;
  border-top: 1px solid #f0f1f5;
}
/* 评价 */
.sol-comment {
  max-width: 500px;
  margin: 0 auto 24px;
  text-align: center;
  font-size: 18px;
  font-weight: 600;
}
.btn-sol-primary {
  padding: 12px 28px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #c41e3a 0%, #e8384f 100%);
  color: #ffffff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.3s;
}
.btn-sol-primary:hover { box-shadow: 0 4px 16px rgba(200,22,30,0.4); transform: translateY(-1px); }
.btn-sol-outline {
  padding: 12px 24px;
  border: 1.5px solid rgba(26,43,95,0.15);
  border-radius: 10px;
  background: transparent;
  color: #1a2b5f;
  font-size: 18px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}
.btn-sol-outline:hover { background: rgba(26,43,95,0.04); border-color: rgba(26,43,95,0.3); }
/* 答题详情 */
.sol-details {
  max-width: 800px;
  margin: 0 auto 24px;
}
.sol-detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.sol-detail-header h3 { color: #1a2b5f; font-size: 18px; }
.sol-tag { background: rgba(26,43,95,0.08); color: #1a2b5f; padding: 3px 12px; border-radius: 8px; font-size: 12px; }
.sol-detail-list { display: flex; flex-direction: column; gap: 12px; }
.sol-q-card {
  background: #ffffff;
  border-radius: 14px;
  padding: 20px 24px;
  border-left: 4px solid #e0e4ec;
  box-shadow: 0 1px 8px rgba(26,43,95,0.03);
}
.q-correct { border-left-color: #22c55e; }
.q-wrong { border-left-color: #e8384f; }
.sol-q-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.sol-q-num { font-size: 20px; font-weight: 700; color: #1a2b5f; }
.sol-q-result { display: flex; align-items: center; gap: 4px; font-size: 13px; font-weight: 700; }
.result-ok { color: #22c55e; }
.result-fail { color: #e8384f; }
.sol-q-content { font-size: 20px; line-height: 1.7; color: #33375a; margin-bottom: 10px; }
.sol-q-options { display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px; }
.sol-opt { font-size: 17px; color: #8899aa; padding: 4px 10px; border-radius: 6px; }
.opt-right { background: rgba(34,197,94,0.08); color: #22c55e; font-weight: 600; }
.opt-user-wrong { background: rgba(232,56,79,0.06); color: #e8384f; text-decoration: line-through; }
.sol-q-answers { display: flex; gap: 24px; margin-bottom: 8px; font-size: 18px; color: #8899aa; }
.ans-ok { color: #22c55e; }
.ans-fail { color: #e8384f; }
.sol-q-analysis {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 14px;
  background: rgba(245,166,35,0.05);
  border-radius: 8px;
  font-size: 18px;
  color: #8b7355;
  line-height: 1.6;
}
/* 底部 */
.sol-actions {
  display: flex;
  gap: 16px;
  justify-content: center;
  padding: 24px 0;
}
</style>
