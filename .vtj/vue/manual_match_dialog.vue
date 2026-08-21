<template>
  <div class="manual-match-dialog">
    <div class="match-header">
      <h3>手动匹配 - 题目与答案对照</h3>
      <div class="match-stats">
        <span>已匹配：{{ matchedCount }}/{{ totalCount }}</span>
        <span style="margin-left: 16px">匹配率：{{ matchRate }}%</span>
      </div>
    </div>

    <div class="match-content">
      <!-- 左侧：题目列表 -->
      <div class="question-list">
        <div class="list-title">题目列表</div>
        <div class="scroll-area">
          <div
            v-for="question in questions"
            :key="question.question_number"
            :class="['question-item', { matched: question.isMatched, selected: selectedQuestion && selectedQuestion.question_number === question.question_number }]"
            @click="selectQuestion(question)"
          >
            <div class="question-number">第{{ question.question_number }}题</div>
            <div class="question-content">{{ question.content }}</div>
            <div class="question-options" v-if="question.options && question.options.length">
              <div v-for="(opt, idx) in question.options" :key="idx">{{ opt }}</div>
            </div>
            <div class="question-answer" v-if="question.answer">
              <span class="answer-tag">答案：{{ question.answer }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 中间：匹配操作区 -->
      <div class="match-operation">
        <div class="operation-title">匹配操作</div>
        <div class="operation-content">
          <template v-if="selectedQuestion">
            <div class="current-question">
              <div class="label">当前题目：</div>
              <div class="value">第{{ selectedQuestion.question_number }}题</div>
            </div>

            <div class="recommendations" v-if="recommendations.length">
              <div class="label">智能推荐：</div>
              <div
                v-for="(rec, idx) in recommendations"
                :key="idx"
                :class="['recommendation-item', { selected: manualAnswer === rec.answer }]"
                @click="selectRecommendation(rec)"
              >
                <span class="rec-answer">{{ rec.answer }}</span>
                <span class="rec-confidence">置信度：{{ rec.confidence }}%</span>
              </div>
            </div>

            <div class="manual-input">
              <div class="label">手动输入答案：</div>
              <input
                v-model="manualAnswer"
                placeholder="如：A"
                class="answer-input"
                @keyup.enter="confirmMatch"
              />
            </div>

            <button class="btn-confirm" @click="confirmMatch">确认匹配</button>
          </template>
          <div v-else class="no-selection">请在左侧选择题目</div>
        </div>
      </div>

      <!-- 右侧：答案列表 -->
      <div class="answer-list">
        <div class="list-title">答案列表</div>
        <div class="scroll-area">
          <div
            v-for="answer in answers"
            :key="answer.question_number"
            :class="['answer-item', { matched: answer.isMatched }]"
            @click="selectAnswer(answer)"
          >
            <div class="answer-number">答案{{ answer.question_number }}</div>
            <div class="answer-content">{{ answer.answer }}</div>
            <div class="answer-analysis" v-if="answer.analysis">解析：{{ answer.analysis }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="match-footer">
      <button class="btn-auto" @click="autoMatchAll">自动匹配全部</button>
      <button class="btn-save" @click="confirmAllMatches">确认所有匹配</button>
      <button class="btn-cancel" @click="cancelMatch">取消</button>
    </div>
  </div>
</template>

<script>
// @ts-nocheck
import { defineComponent } from 'vue';
import { useProvider } from '@vtj/renderer';
import { ElMessage } from 'element-plus';

export default defineComponent({
  name: 'ManualMatchDialog',
  setup(props) {
    const provider = useProvider({ id: 'manual_match_dialog', version: Date.now().toString() });
    return { provider };
  },
  props: {
    questions: {
      type: Array,
      default: () => []
    },
    answers: {
      type: Array,
      default: () => []
    }
  },
  emits: ['confirm', 'cancel'],
  data() {
    return {
      selectedQuestion: null,
      selectedAnswer: null,
      manualAnswer: '',
      recommendations: []
    };
  },
  computed: {
    matchedCount() {
      return this.questions.filter(function(q) { return q.isMatched; }).length;
    },
    totalCount() {
      return this.questions.length;
    },
    matchRate() {
      if (this.totalCount === 0) return 0;
      return Math.round((this.matchedCount / this.totalCount) * 100);
    }
  },
  methods: {
    selectQuestion(question) {
      this.selectedQuestion = question;
      this.manualAnswer = question.answer || '';
      this.generateRecommendations(question);
    },
    selectAnswer(answer) {
      this.selectedAnswer = answer;
    },
    generateRecommendations(question) {
      var self = this;
      var recommendations = [];
      this.answers.forEach(function(ans) {
        if (!ans.isMatched) {
          var similarity = self.calculateSimilarity(question, ans);
          if (similarity > 0.3) {
            recommendations.push({
              answer: ans.answer,
              confidence: Math.round(similarity * 100),
              answerNumber: ans.question_number
            });
          }
        }
      });
      this.recommendations = recommendations.sort(function(a, b) {
        return b.confidence - a.confidence;
      }).slice(0, 5);
    },
    calculateSimilarity(question, answer) {
      var qText = (question.content || '').toLowerCase();
      var aText = (answer.answer || '').toLowerCase();
      if (!qText || !aText) return 0;
      if (qText === aText) return 1;
      var qLen = qText.length;
      var aLen = aText.length;
      var minLen = Math.min(qLen, aLen);
      if (minLen === 0) return 0;
      var matches = 0;
      for (var i = 0; i < minLen; i++) {
        if (qText[i] === aText[i]) matches++;
      }
      return matches / Math.max(qLen, aLen);
    },
    selectRecommendation(rec) {
      this.manualAnswer = rec.answer;
    },
    confirmMatch() {
      if (this.selectedQuestion && this.manualAnswer) {
        this.selectedQuestion.answer = this.manualAnswer;
        this.selectedQuestion.isMatched = true;
        if (this.selectedAnswer) {
          this.selectedAnswer.isMatched = true;
        }
        ElMessage.success('第 ' + this.selectedQuestion.question_number + ' 题匹配成功：' + this.manualAnswer);
        this.selectedQuestion = null;
        this.manualAnswer = '';
        this.recommendations = [];
      } else {
        ElMessage.warning('请选择题目并输入答案');
      }
    },
    autoMatchAll() {
      var self = this;
      var answerIndex = {};
      this.answers.forEach(function(ans) {
        answerIndex[ans.question_number] = ans;
      });
      var matched = 0;
      this.questions.forEach(function(q) {
        if (!q.isMatched) {
          var ans = answerIndex[q.question_number];
          if (ans) {
            q.answer = ans.answer;
            q.isMatched = true;
            ans.isMatched = true;
            matched++;
          }
        }
      });
      ElMessage.success('自动匹配完成，共匹配 ' + matched + ' 题');
    },
    confirmAllMatches() {
      this.$emit('confirm', {
        questions: this.questions,
        matchRate: this.matchRate
      });
    },
    cancelMatch() {
      this.$emit('cancel');
    }
  }
});
</script>

<style lang="css" scoped>
.manual-match-dialog {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}
.match-header {
  padding: 16px 20px;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fafafa;
}
.match-header h3 {
  margin: 0;
  font-size: 16px;
  color: #333;
}
.match-stats {
  font-size: 14px;
  color: #666;
}
.match-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}
.question-list,
.answer-list {
  width: 30%;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e8e8e8;
}
.answer-list {
  border-right: none;
  border-left: 1px solid #e8e8e8;
}
.list-title {
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  color: #333;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
}
.scroll-area {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.question-item,
.answer-item {
  padding: 12px;
  margin: 4px 0;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}
.question-item:hover,
.answer-item:hover {
  background: #f5f5f5;
}
.question-item.selected {
  background: #e6f7ff;
  border-color: #1890ff;
}
.question-item.matched {
  background: #f6ffed;
  border-color: #52c41a;
}
.answer-item.matched {
  background: #f6ffed;
  border-color: #52c41a;
}
.question-number,
.answer-number {
  font-size: 13px;
  font-weight: 600;
  color: #1890ff;
  margin-bottom: 4px;
}
.question-content {
  font-size: 13px;
  color: #333;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.question-options {
  margin-top: 6px;
  font-size: 12px;
  color: #666;
}
.question-answer {
  margin-top: 6px;
}
.answer-tag {
  font-size: 12px;
  color: #52c41a;
  background: #f6ffed;
  padding: 2px 8px;
  border-radius: 4px;
}
.answer-content {
  font-size: 14px;
  color: #333;
  font-weight: 600;
}
.answer-analysis {
  margin-top: 6px;
  font-size: 12px;
  color: #999;
}
.match-operation {
  width: 40%;
  display: flex;
  flex-direction: column;
  padding: 16px;
}
.operation-title {
  font-size: 15px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
}
.operation-content {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.current-question {
  margin-bottom: 16px;
}
.label {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
}
.value {
  font-size: 14px;
  color: #333;
  font-weight: 600;
}
.recommendations {
  margin-bottom: 16px;
}
.recommendation-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  margin: 4px 0;
  border-radius: 6px;
  cursor: pointer;
  border: 1px solid #e8e8e8;
  transition: all 0.2s;
}
.recommendation-item:hover {
  background: #f5f5f5;
}
.recommendation-item.selected {
  background: #e6f7ff;
  border-color: #1890ff;
}
.rec-answer {
  font-size: 14px;
  color: #333;
  font-weight: 600;
}
.rec-confidence {
  font-size: 12px;
  color: #999;
}
.manual-input {
  margin-bottom: 16px;
}
.answer-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}
.answer-input:focus {
  border-color: #1890ff;
}
.btn-confirm {
  padding: 8px 16px;
  background: #1890ff;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}
.btn-confirm:hover {
  background: #40a9ff;
}
.no-selection {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  font-size: 14px;
}
.match-footer {
  padding: 12px 20px;
  border-top: 1px solid #e8e8e8;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  background: #fafafa;
}
.btn-auto,
.btn-save,
.btn-cancel {
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  border: 1px solid #d9d9d9;
  transition: all 0.2s;
}
.btn-auto {
  background: #fff;
  color: #666;
}
.btn-auto:hover {
  border-color: #1890ff;
  color: #1890ff;
}
.btn-save {
  background: #52c41a;
  color: #fff;
  border-color: #52c41a;
}
.btn-save:hover {
  background: #73d13d;
}
.btn-cancel {
  background: #fff;
  color: #666;
}
.btn-cancel:hover {
  border-color: #ff4d4f;
  color: #ff4d4f;
}
</style>
