wrong_questions.vue
<!-- 错题集模块 -->
<template>
  <div class="wrong-question-page">
    <NavBar></NavBar>
    <main class="wq-main">
      <div class="wq-filter-bar">
        <div class="filter-group">
          <label> 收录时间</label>
          <select v-model="state.filter.time">
            <option value="all">全部</option>
            <option value="week">最近一周</option>
            <option value="month">最近一月</option>
            <option value="3months">最近三月</option>
          </select>
        </div>
        <div class="filter-group">
          <label> 知识点</label>
          <select v-model="state.filter.knowledge">
            <option value="all">全部知识点</option>
            <option value="zzll">政治理论</option>
            <option value="pdtl">判断推理</option>
            <option value="slgx">数量关系</option>
            <option value="zlfx">资料分析</option>
            <option value="yylj">语言理解</option>
          </select>
        </div>
        <button class="filter-btn" @click="applyFilter">筛选</button>
      </div>
      <div class="wq-body">
        <nav class="wq-nav">
          <div
            v-for="(nav, index) in navList"
            :key="nav.key"
            :class="['nav-item', { active: state.activeNav === nav.key }]"
            @click="switchNav(nav.key)">
            <XIcon
              :icon="nav.icon"
              :size="18"
              :color="
                state.activeNav === nav.key ? '#ffffff' : '#5a6488'
              "></XIcon>
            <span> {{ nav.name }}</span>
            <span v-if="nav.badge" class="nav-badge"> {{ nav.badge }}</span>
          </div>
        </nav>
        <div class="wq-content">
          <div v-if="state.activeNav === 'zhanti'" class="zhanti-section">
            <div class="section-top">
              <h3>我的斩题</h3>
              <span class="section-tip"> 斩题保存10天，过期自动删除</span>
            </div>
            <div v-if="state.zhantiList.length === 0" class="empty-state">
              <span class="empty-icon"> 📭</span>
              <p>暂无斩题记录</p>
            </div>
            <div class="zhanti-grid">
              <div
                v-for="(item, idx) in state.zhantiList"
                :key="idx"
                :class="['zhanti-card', { expiring: item.daysLeft <= 2 }]">
                <div class="card-top">
                  <span class="card-subject"> {{ item.subject }}</span>
                  <span class="card-days">
                    <span>
                      <span> {{ item.daysLeft }}</span>
                      <span> 天后过期</span></span
                    ></span
                  >
                </div>
                <p class="card-title-text">
                  {{ item.title }}
                </p>
                <div class="card-bottom">
                  <span> {{ item.createTime }}</span>
                  <button @click="reviewZhanti(item)">复习</button>
                  <button @click="restoreZhanti(item)" class="restore-btn">恢复</button>
                </div>
              </div>
            </div>
            <div v-if="state.zhantiExpiringNotice" class="expiring-notice">
              ⚠️ 您有斩题要离开了哦，请及时复习！
            </div>
          </div>
          <div v-if="state.activeNav === 'review'" class="review-section">
            <div class="section-top">
              <h3>错题复习</h3>
            </div>
            <div class="review-options">
              <div class="review-option" @click="startReview('knowledge')">
                <div
                  class="option-icon div_26tyjveifkr"
                  :style="{ background: '#eff6ff' }">
                  📚
                </div>
                <span> 按知识点复习</span>
              </div>
              <div class="review-option" @click="startReview('time')">
                <div
                  class="option-icon div_26u1jveifkr"
                  :style="{ background: '#fef2f2' }">
                  📅
                </div>
                <span> 按收录时间复习</span>
              </div>
              <div class="review-option" @click="startReview('subject')">
                <div
                  class="option-icon div_26u4jveifkr"
                  :style="{ background: '#fffbeb' }">
                  📋
                </div>
                <span> 按科目复习</span>
              </div>
            </div>
          </div>
          <div
            v-if="['xc', 'sl', 'ga'].includes(state.activeNav)"
            class="question-list">
            <div class="section-top">
              <h3>
                <span>
                  <span> {{ state.navNameMap[state.activeNav] }}</span>
                  <span> 错题</span></span
                >
              </h3>
              <span>
                <span>
                  <span> 共</span>
                  <span> {{ filteredQuestions.length }}</span>
                  <span> 题</span></span
                ></span
              >
            </div>
            <div v-if="filteredQuestions.length === 0" class="empty-state">
              <span class="empty-icon"> 🎉</span>
              <p>暂无错题，继续保持！</p>
            </div>
            <div class="question-items">
              <div
                v-for="(q, index) in filteredQuestions"
                :key="q.id"
                class="q-item"
                @click="goToQuestion(q)">
                <div class="q-header">
                  <span class="q-type"> {{ q.type }}</span>
                  <span class="q-date"> {{ q.date }}</span>
                  <span class="q-status" :class="q.status">{{ q.statusText }}</span>
                </div>
                <p class="q-title">
                  {{ q.title }}
                </p>
                <div class="q-tags">
                  <span v-for="(tag, index) in q.tags" :key="tag" class="tag">
                    {{ tag }}</span
                  >
                  <button class="wq-note-btn" @click.stop="openNoteEditor(q.id)">笔记</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- 复习模式弹窗 -->
      <div v-if="state.showReviewModal" class="modal-overlay" @click="closeReviewModal">
        <div class="modal-content" @click.stop>
          <h3>选择复习模式</h3>
          <div class="review-mode-options">
            <div class="mode-option" @click="selectReviewMode('sequential')">
              <span class="mode-icon">➡️</span>
              <span>顺序复习</span>
            </div>
            <div class="mode-option" @click="selectReviewMode('knowledge')">
              <span class="mode-icon">📚</span>
              <span>按知识点复习</span>
            </div>
            <div class="mode-option" @click="selectReviewMode('subject')">
              <span class="mode-icon">📋</span>
              <span>按科目复习</span>
            </div>
          </div>
          <button class="close-modal-btn" @click="closeReviewModal">取消</button>
        </div>
      </div>
      
      <!-- 答题界面 -->
      <div v-if="state.inReviewMode" class="review-container">
        <div class="review-header">
          <h2>{{ state.currentQuestion.title }}</h2>
          <div class="review-controls">
            <button @click="exitReviewMode">退出复习</button>
          </div>
        </div>
        <div class="question-content">
          <div class="options" v-if="state.currentQuestion.options">
            <div 
              v-for="(option, idx) in state.currentQuestion.options" 
              :key="idx"
              :class="['option', { selected: state.selectedAnswer === option.value }]"
              @click="selectOption(option.value)">
              <span class="option-letter">{{ String.fromCharCode(65 + idx) }}.</span>
              <span>{{ option.text }}</span>
            </div>
          </div>
          <div v-else class="text-answer">
            <textarea 
              v-model="state.userTextAnswer" 
              placeholder="请输入您的答案..."
              rows="5"></textarea>
          </div>
        </div>
        <div class="review-actions">
          <button @click="submitAnswer" :disabled="!canSubmitAnswer">提交答案</button>
          <button @click="skipQuestion" class="secondary">跳过</button>
        </div>
      </div>
      
      <!-- 解析与斩题确认 -->
      <div v-if="state.showAnalysis" class="modal-overlay" @click="closeAnalysis">
        <div class="analysis-modal" @click.stop>
          <h3>题目解析</h3>
          <div class="analysis-content">
            <div class="correct-answer">
              <h4>正确答案：{{ state.currentQuestion.correctAnswer }}</h4>
              <p><strong>解析：</strong>{{ state.currentQuestion.analysis || '暂无解析' }}</p>
              <p><strong>知识点：</strong>{{ state.currentQuestion.tags.join(', ') }}</p>
              <p><strong>难度：</strong>{{ state.currentQuestion.difficulty || '中等' }}</p>
              <p><strong>掌握度：</strong>{{ state.currentQuestion.masteryLevel || 0 }}%</p>
            </div>
            
            <div class="recommendation-section" v-if="!state.questionCorrect">
              <h4>强化训练</h4>
              <p>您答错了这道题，系统为您推荐相似题目进行巩固：</p>
              <div class="similar-questions">
                <div 
                  v-for="(q, idx) in state.similarQuestions" 
                  :key="'sim-' + idx"
                  class="similar-q-item"
                  @click="handleSimilarQuestion(q)">
                  <span>{{ idx + 1 }}. {{ q.title.substring(0, 50) }}...</span>
                </div>
              </div>
            </div>
            
            <div class="chop-question-section" v-if="state.questionCorrect && !state.currentQuestion.chopped">
              <h4>斩题确认</h4>
              <p>您已答对此题，是否将其标记为"已掌握"（斩题）？</p>
              <div class="chop-verification">
                <p>验证信息：</p>
                <ul>
                  <li>是否首次斩题：{{ !state.currentQuestion.chopped ? '是' : '否' }}</li>
                  <li>掌握度：{{ state.currentQuestion.masteryLevel >= 80 ? '≥80%' : '<80%' }}</li>
                  <li>保护期：{{ state.currentQuestion.protected ? '是' : '否' }}</li>
                </ul>
                <div class="chop-actions">
                  <button @click="confirmChopQuestion" :disabled="!canChopQuestion">确认斩题</button>
                  <button @click="cancelChopQuestion" class="secondary">暂不斩题</button>
                </div>
              </div>
            </div>
          </div>
          <div class="analysis-actions">
            <button @click="continueReview">继续复习</button>
            <button @click="closeAnalysis" class="secondary">返回列表</button>
          </div>
        </div>
      </div>
      
      <!-- 错题复现页面 -->
      <div v-if="state.inWrongQuestionPractice" class="wrong-question-practice">
        <div class="practice-header">
          <h2>错题专项练习</h2>
          <div class="practice-info">
            <span>当前练习：{{ state.currentWrongQuestionIndex + 1 }} / {{ state.wrongQuestionList.length }}</span>
            <button @click="exitWrongQuestionPractice">退出练习</button>
          </div>
        </div>
        <div class="practice-content">
          <div class="current-question">
            <h3>{{ state.wrongQuestionList[state.currentWrongQuestionIndex].title }}</h3>
            <div class="options" v-if="state.wrongQuestionList[state.currentWrongQuestionIndex].options">
              <div 
                v-for="(option, idx) in state.wrongQuestionList[state.currentWrongQuestionIndex].options" 
                :key="idx"
                :class="['option', { selected: state.selectedAnswers[state.currentWrongQuestionIndex] === option.value }]"
                @click="selectPracticeOption(option.value, state.currentWrongQuestionIndex)">
                <span class="option-letter">{{ String.fromCharCode(65 + idx) }}.</span>
                <span>{{ option.text }}</span>
              </div>
            </div>
            <div v-else class="text-answer">
              <textarea 
                v-model="state.practiceTextAnswers[state.currentWrongQuestionIndex]" 
                placeholder="请输入您的答案..."
                rows="5"></textarea>
            </div>
          </div>
          <div class="practice-navigation">
            <button @click="prevQuestion" :disabled="state.currentWrongQuestionIndex <= 0">上一题</button>
            <button @click="nextQuestion" :disabled="state.currentWrongQuestionIndex >= state.wrongQuestionList.length - 1">下一题</button>
            <button @click="submitPracticeAnswer" :disabled="!canSubmitPracticeAnswer">提交答案</button>
          </div>
        </div>
      </div>
    </main>

    <!-- 笔记编辑弹窗 -->
    <div v-if="state.showNoteEditor" class="wq-note-overlay" @click.self="closeNoteEditor">
      <div class="wq-note-panel">
        <div class="wq-note-header">
          <h3>题目笔记</h3>
          <button class="wq-note-close" @click="closeNoteEditor">×</button>
        </div>
        <textarea v-model="state.noteText" class="wq-note-textarea" placeholder="在此输入笔记内容..." rows="5"></textarea>
        <div class="wq-note-footer">
          <button class="wq-note-btn-delete" @click="deleteNote">删除笔记</button>
          <button class="wq-note-btn-save" @click="saveNote">保存笔记</button>
        </div>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { EditPen, Document, Reading, DeleteFilled, Clock } from '@vtj/icons';
  import NavBar from './navbar.vue';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'WrongQuestionSet',
    components: { NavBar, XIcon },
    setup(props) {
      const provider = useProvider({ id: 'wrong_questions', version: '1778918487696' });
      const state = reactive({
        filter: { time: 'all', knowledge: 'all' },
        activeNav: 'xc',
        navNameMap: { xc: '行测', sl: '申论', ga: '公专' },
        zhantiList: [],
        allQuestions: [],
        zhantiExpiringNotice: false,
        // 复习相关状态
        showReviewModal: false,
        inReviewMode: false,
        reviewMode: null,
        currentQuestion: null,
        selectedAnswer: '',
        userTextAnswer: '',
        questionCorrect: false,
        showAnalysis: false,
        similarQuestions: [],
        // 斩题相关状态
        choppingQuestion: null,
        analyzedQuestions: [],
        personalizedList: [],
        reviewMode: 'sequential',
        // 错题复现状态
        inWrongQuestionPractice: false,
        wrongQuestionList: [],
        currentWrongQuestionIndex: 0,
        selectedAnswers: {},
        practiceTextAnswers: {},
        // 笔记相关
        showNoteEditor: false,
        noteText: '',
        currentNoteQuestionId: null
      });
      return {
        state,
        props,
        provider,
        EditPen,
        Document,
        Reading,
        DeleteFilled,
        Clock
      };
    },
    computed: {
      navList() {
        return [
          { key: 'xc', name: '行测', icon: EditPen, badge: this.getSubjectBadgeCount('xc') },
          { key: 'sl', name: '申论', icon: Document, badge: this.getSubjectBadgeCount('sl') },
          { key: 'ga', name: '公专', icon: Reading, badge: this.getSubjectBadgeCount('ga') },
          { key: 'zhanti', name: '我的斩题', icon: DeleteFilled, badge: this.state.zhantiList.length },
          { key: 'review', name: '错题复习', icon: Clock }
        ];
      },
      filteredQuestions() {
        let list = this.state.allQuestions.filter(
          (q) => q.subject === this.state.activeNav
        );
        
        // 时间筛选
        if (this.state.filter.time !== 'all') {
          const now = new Date();
          list = list.filter(q => {
            const questionDate = new Date(q.date);
            if (this.state.filter.time === 'week') {
              return (now.getTime() - questionDate.getTime()) <= 7 * 24 * 60 * 60 * 1000;
            } else if (this.state.filter.time === 'month') {
              return (now.getTime() - questionDate.getTime()) <= 30 * 24 * 60 * 60 * 1000;
            } else if (this.state.filter.time === '3months') {
              return (now.getTime() - questionDate.getTime()) <= 90 * 24 * 60 * 60 * 1000;
            }
            return true;
          });
        }
        
        // 知识点筛选
        if (this.state.filter.knowledge !== 'all') {
          list = list.filter((q) => q.tags.includes(this.state.filter.knowledge));
        }
        
        return list;
      },
      canSubmitAnswer() {
        if (!this.state.currentQuestion) return false;
        if (this.state.currentQuestion.options) {
          return this.state.selectedAnswer !== '';
        } else {
          return this.state.userTextAnswer.trim() !== '';
        }
      },
      canChopQuestion() {
        // 验证斩题条件
        if (!this.state.currentQuestion) return false;
        // 检查是否已经斩过题
        if (this.state.currentQuestion.chopped) return false;
        // 检查掌握度是否超过80%
        if ((this.state.currentQuestion.masteryLevel || 0) < 80) return false;
        // 检查保护期（假设题目创建后有保护期）
        const creationDate = new Date(this.state.currentQuestion.date);
        const now = new Date();
        const diffDays = (now.getTime() - creationDate.getTime()) / (1000 * 60 * 60 * 24);
        return diffDays >= 1; // 至少创建一天后才能斩题
      },
      canSubmitPracticeAnswer() {
        const currentQ = this.state.wrongQuestionList[this.state.currentWrongQuestionIndex];
        if (!currentQ) return false;
        
        if (currentQ.options) {
          return this.state.selectedAnswers[this.state.currentWrongQuestionIndex] !== undefined;
        } else {
          return this.state.practiceTextAnswers[this.state.currentWrongQuestionIndex]?.trim() !== '';
        }
      }
    },
    methods: {
      getSubjectBadgeCount(subject) {
        return this.filteredQuestions.filter(q => q.subject === subject && !q.chopped).length;
      },
      
      loadData() {
        this.state.allQuestions = [];
        this.ensureLogin().then(() => {
          const headers = this.getJsonHeaders();
          fetch('/api/questions/?page=1&page_size=100', { headers: headers })
            .then(res => res.json())
            .then(data => {
              const items = data.items || [];
              if (items.length) {
                this.state.allQuestions = items.map(item => {
                  const sc = item.subject_category || '';
                  const subjectMap = { '行测': 'xc', '申论': 'sl', '公专': 'ga' };
                  const subjectKey = subjectMap[sc] || 'ga';
                  let optionsArr = [];
                  try {
                    optionsArr = item.options ? (typeof item.options === 'string' ? JSON.parse(item.options) : item.options) : [];
                  } catch(e) {}
                  return {
                    id: item.question_id,
                    subject: subjectKey,
                    type: item.question_type_detail || '选择题',
                    date: item.created_at || '',
                    title: item.question_content || '',
                    tags: (item.tags || '').split(',').filter(Boolean),
                    status: 'needs-review',
                    statusText: '待复习',
                    options: Array.isArray(optionsArr) ? optionsArr.map((o, i) => ({
                      value: o.key || String.fromCharCode(65+i),
                      text: o.value || o.text || o
                    })) : [],
                    correctAnswer: item.answer || '',
                    analysis: item.answer_analysis || '',
                    difficulty: item.difficulty || 3,
                    masteryLevel: 50,
                    chopped: false,
                    category: sc
                  };
                });
              }
            }).catch(() => {
              console.log('WrongQuestionSet: 无法连接后端');
            });
        });
        this.state.zhantiList = [];
        this.state.zhantiExpiringNotice = false;
      },
      ensureLogin() {
        return window.__VTJ_AUTH__.ensureAuth();
      },
      getAuthHeaders() {
        return window.__VTJ_AUTH__.getAuthHeaders();
      },
      getJsonHeaders() {
        return window.__VTJ_AUTH__.getJsonHeaders();
      },
      
      switchNav(key) {
        this.state.activeNav = key;
      },
      
      navigateTo(id) {
        this.$router.push('/page/' + id);
      },
      // ========== 笔记功能 ==========
      openNoteEditor(qId) {
        this.state.showNoteEditor = true;
        this.state.currentNoteQuestionId = qId;
        this.state.noteText = '';
        var self = this;
        window.__VTJ_AUTH__.apiFetch('/api/questions/' + qId + '/note', {
          headers: this.getJsonHeaders()
        }).then(function(res) { return res.json(); })
          .then(function(data) {
            if (data.has_note) { self.state.noteText = data.note_text || ''; }
          }).catch(function() {});
      },
      closeNoteEditor() {
        this.state.showNoteEditor = false;
        this.state.noteText = '';
      },
      async saveNote() {
        var qId = this.state.currentNoteQuestionId;
        if (!qId || !this.state.noteText.trim()) return;
        try {
          await window.__VTJ_AUTH__.apiFetch('/api/questions/' + qId + '/note', {
            method: 'POST',
            headers: this.getJsonHeaders(),
            body: JSON.stringify({ note_text: this.state.noteText.trim() })
          });
          this.state.showNoteEditor = false;
        } catch(e) { console.warn('保存笔记失败:', e); }
      },
      async deleteNote() {
        var qId = this.state.currentNoteQuestionId;
        if (!qId) return;
        try {
          await window.__VTJ_AUTH__.apiFetch('/api/questions/' + qId + '/note', {
            method: 'DELETE', headers: this.getJsonHeaders()
          });
          this.state.showNoteEditor = false;
          this.state.noteText = '';
        } catch(e) { console.warn('删除笔记失败:', e); }
      },
      
      applyFilter() {
        this.$message.success('筛选条件已更新');
      },
      
      startReview(mode) {
        this.state.reviewMode = mode;
        this.openReviewModal();
      },
      
      openReviewModal() {
        this.state.showReviewModal = true;
      },
      
      closeReviewModal() {
        this.state.showReviewModal = false;
      },
      
      selectReviewMode(mode) {
        this.state.reviewMode = mode;
        this.closeReviewModal();
        this.startReviewProcess();
      },
      
      startReviewProcess() {
        // 根据复习模式筛选题目
        let questionsToReview = [];
        if (this.state.reviewMode === 'knowledge') {
          // 按知识点复习 - 可能需要额外参数
          questionsToReview = this.state.allQuestions.filter(q => q.subject === this.state.activeNav);
        } else if (this.state.reviewMode === 'subject') {
          // 按科目复习
          questionsToReview = this.state.allQuestions.filter(q => q.subject === this.state.activeNav);
        } else {
          // 默认顺序复习
          questionsToReview = this.state.allQuestions.filter(q => q.subject === this.state.activeNav);
        }
        
        // 排除已斩题的题目
        questionsToReview = questionsToReview.filter(q => !q.chopped);
        
        if (questionsToReview.length === 0) {
          this.$message.warning('没有需要复习的题目');
          return;
        }
        
        this.state.inReviewMode = true;
        this.setNextQuestion(questionsToReview);
      },
      
      setNextQuestion(questions) {
        // 从问题列表中随机选择一个或按顺序选择
        if (questions.length > 0) {
          this.state.currentQuestion = questions[0]; // 简化处理，实际可能需要随机选择
          this.resetQuestionState();
        }
      },
      
      resetQuestionState() {
        this.state.selectedAnswer = '';
        this.state.userTextAnswer = '';
        this.state.questionCorrect = false;
      },
      
      selectOption(value) {
        if (this.state.currentQuestion.options) {
          this.state.selectedAnswer = value;
        }
      },
      
      submitAnswer() {
        if (!this.canSubmitAnswer) return;
        
        // 判断答案是否正确
        let userAnswer;
        if (this.state.currentQuestion.options) {
          userAnswer = this.state.selectedAnswer;
        } else {
          userAnswer = this.state.userTextAnswer;
        }
        
        this.state.questionCorrect = this.checkAnswer(userAnswer);
        
        // 更新题目掌握度
        this.updateMasteryLevel(this.state.currentQuestion.id, this.state.questionCorrect);
        
        // 如果答错，获取相似题目
        if (!this.state.questionCorrect) {
          this.getSimilarQuestions();
        }
        
        // 显示解析
        this.showAnalysis();
      },
      
      checkAnswer(userAnswer) {
        if (this.state.currentQuestion.options) {
          return userAnswer === this.state.currentQuestion.correctAnswer;
        } else {
          // 文字题暂时简化处理，实际应用中需要智能评分
          return Math.random() > 0.5; // 模拟判断
        }
      },
      
      updateMasteryLevel(questionId, isCorrect) {
        const question = this.state.allQuestions.find(q => q.id == questionId);
        if (question) {
          if (isCorrect) {
            // 答对增加掌握度
            question.masteryLevel = Math.min(100, (question.masteryLevel || 0) + 10);
          } else {
            // 答错减少掌握度
            question.masteryLevel = Math.max(0, (question.masteryLevel || 0) - 5);
          }
          
          // 更新状态文本
          if (question.masteryLevel >= 80 && question.chopped) {
            question.status = 'mastered';
            question.statusText = '已掌握';
          } else if (question.chopped) {
            question.status = 'chopped';
            question.statusText = '已斩题';
          } else {
            question.status = 'needs-review';
            question.statusText = '待复习';
          }
        }
      },
      
      getSimilarQuestions() {
        this.state.similarQuestions = [];
      },
      
      showAnalysis() {
        this.state.showAnalysis = true;
      },
      
      closeAnalysis() {
        this.state.showAnalysis = false;
      },
      
      confirmChopQuestion() {
        if (!this.state.currentQuestion) return;
        
        // 执行斩题逻辑
        this.chopQuestion(this.state.currentQuestion);
        
        // 移动到斩题列表
        this.moveToZhanti(this.state.currentQuestion);
        
        this.$message.success('题目已斩题，10天后自动删除');
        this.closeAnalysis();
        this.continueReview();
      },
      
      cancelChopQuestion() {
        this.closeAnalysis();
        this.continueReview();
      },
      
      chopQuestion(question) {
        question.chopped = true;
        question.status = 'chopped';
        question.statusText = '已斩题';
      },
      
      moveToZhanti(question) {
        // 添加到斩题列表
        const zhantiItem = {
          id: Date.now(),
          subject: this.state.navNameMap[question.subject],
          title: question.title,
          createTime: new Date().toISOString().split('T')[0],
          daysLeft: 10, // 10天后过期
          originalQuestionId: question.id
        };
        this.state.zhantiList.push(zhantiItem);
        
        // 更新过期通知
        this.state.zhantiExpiringNotice = this.state.zhantiList.some(i => i.daysLeft <= 2);
      },
      
      continueReview() {
        this.closeAnalysis();
        
        // 获取剩余待复习题目
        const remainingQuestions = this.state.allQuestions
          .filter(q => q.subject === this.state.activeNav && !q.chopped);
        
        if (remainingQuestions.length > 0) {
          // 继续下一道题
          this.setNextQuestion(remainingQuestions);
        } else {
          this.exitReviewMode();
          this.$message.success('恭喜您完成本轮复习！');
        }
      },
      
      exitReviewMode() {
        this.state.inReviewMode = false;
        this.state.showAnalysis = false;
      },
      
      skipQuestion() {
        // 获取下一个题目
        const remainingQuestions = this.state.allQuestions
          .filter(q => q.subject === this.state.activeNav && !q.chopped);
        
        if (remainingQuestions.length > 0) {
          this.setNextQuestion(remainingQuestions);
        } else {
          this.exitReviewMode();
        }
      },
      
      handleSimilarQuestion(similarQ) {
        // 处理相似题目
        this.$message.info('正在加载相似题目...');
        // 这里可以导航到具体的相似题目页面
      },
      
      goToQuestion(q) {
        // 启动错题专项练习
        this.startWrongQuestionPractice(q);
      },
      
      startWrongQuestionPractice(clickedQuestion) {
        // 获取当前科目的所有错题
        const subjectQuestions = this.state.allQuestions.filter(
          q => q.subject === clickedQuestion.subject && !q.chopped
        );
        
        // 将点击的题目排在第一位，其余保持顺序
        const sortedQuestions = [clickedQuestion, ...subjectQuestions.filter(q => q.id !== clickedQuestion.id)];
        
        this.state.wrongQuestionList = sortedQuestions;
        this.state.currentWrongQuestionIndex = 0;
        this.state.selectedAnswers = {};
        this.state.practiceTextAnswers = {};
        this.state.inWrongQuestionPractice = true;
      },
      
      selectPracticeOption(value, index) {
        this.$set(this.state.selectedAnswers, index, value);
      },
      
      prevQuestion() {
        if (this.state.currentWrongQuestionIndex > 0) {
          this.state.currentWrongQuestionIndex--;
        }
      },
      
      nextQuestion() {
        if (this.state.currentWrongQuestionIndex < this.state.wrongQuestionList.length - 1) {
          this.state.currentWrongQuestionIndex++;
        }
      },
      
      submitPracticeAnswer() {
        if (!this.canSubmitPracticeAnswer) return;
        
        const currentQ = this.state.wrongQuestionList[this.state.currentWrongQuestionIndex];
        let userAnswer;
        
        if (currentQ.options) {
          userAnswer = this.state.selectedAnswers[this.state.currentWrongQuestionIndex];
        } else {
          userAnswer = this.state.practiceTextAnswers[this.state.currentWrongQuestionIndex];
        }
        
        const isCorrect = this.checkAnswerInPractice(currentQ, userAnswer);
        
        // 更新题目掌握度
        this.updateMasteryLevel(currentQ.id, isCorrect);
        
        // 显示结果反馈
        if (isCorrect) {
          this.$message.success('回答正确！');
        } else {
          this.$message.error('回答错误，继续努力！');
        }
      },
      
      checkAnswerInPractice(question, userAnswer) {
        if (question.options) {
          return userAnswer === question.correctAnswer;
        } else {
          // 文字题暂时简化处理
          return Math.random() > 0.5; // 模拟判断
        }
      },
      
      exitWrongQuestionPractice() {
        this.state.inWrongQuestionPractice = false;
        this.state.wrongQuestionList = [];
        this.state.selectedAnswers = {};
        this.state.practiceTextAnswers = {};
      },
      
      reviewZhanti(item) {
        // 从斩题列表中恢复题目
        this.$message.info('开始复习：' + item.title);
        
        // 查找原题并从斩题状态恢复
        const originalQuestion = this.state.allQuestions.find(q => q.id == item.originalQuestionId);
        if (originalQuestion) {
          originalQuestion.chopped = false;
          originalQuestion.status = 'needs-review';
          originalQuestion.statusText = '待复习';
        }
        
        // 从斩题列表中移除
        this.state.zhantiList = this.state.zhantiList.filter(z => z.id != item.id);
        this.state.zhantiExpiringNotice = this.state.zhantiList.some(i => i.daysLeft <= 2);
      },
      
      restoreZhanti(item) {
        // 恢复斩题到错题列表
        const originalQuestion = this.state.allQuestions.find(q => q.id == item.originalQuestionId);
        if (originalQuestion) {
          originalQuestion.chopped = false;
          originalQuestion.status = 'needs-review';
          originalQuestion.statusText = '待复习';
        }
        
        // 从斩题列表中移除
        this.state.zhantiList = this.state.zhantiList.filter(z => z.id != item.id);
        this.state.zhantiExpiringNotice = this.state.zhantiList.some(i => i.daysLeft <= 2);
        
        this.$message.success('题目已恢复到错题列表');
      },
      
      // 交卷后收录错题的方法
      collectWrongQuestionsAfterExam(examResults) {
        examResults.forEach(result => {
          if (!result.isCorrect) {
            // 题目答错，加入对应错题门类
            const wrongQuestion = {
              ...result.question,
              status: 'needs-review',
              statusText: '待复习',
              chopped: false,
              masteryLevel: 0,
              date: new Date().toISOString().split('T')[0]
            };
            
            // 检查是否已存在该错题
            const existingIndex = this.state.allQuestions.findIndex(q => q.id === wrongQuestion.id);
            if (existingIndex === -1) {
              // 不存在则添加到错题列表
              this.state.allQuestions.push(wrongQuestion);
            } else {
              // 已存在则更新状态
              this.state.allQuestions[existingIndex].status = 'needs-review';
              this.state.allQuestions[existingIndex].statusText = '待复习';
              this.state.allQuestions[existingIndex].chopped = false;
            }
            
            this.$message.info(`错题已收录到${this.state.navNameMap[wrongQuestion.subject]}门类`);
          }
        });
      },
      
      // 多源错题收集
      collectWrongQuestions(source) {
        // 根据source参数从不同数据源获取错题
        this.provider.call('collectWrongQuestions', { source }).then((data) => {
          // 添加来源标识
          const newQuestions = data.map(q => ({
            ...q,
            source: source,
            status: 'needs-review',
            statusText: '待复习',
            chopped: false,
            masteryLevel: 0
          }));
          
          this.state.allQuestions = [...this.state.allQuestions, ...newQuestions];
          
          // 更新导航徽章数
          this.updateBadges();
        });
      },
      
      // 智能分析错题
      analyzeWrongQuestions() {
        this.provider.call('analyzeWrongQuestions', { questions: this.state.allQuestions }).then((result) => {
          this.state.analyzedQuestions = result;
          
          // 根据分析结果更新题目属性
          result.forEach(analysis => {
            const question = this.state.allQuestions.find(q => q.id == analysis.questionId);
            if (question) {
              question.tags = [...new Set([...question.tags, ...analysis.tags])]; // 合并标签
              question.difficulty = analysis.difficulty;
              question.masteryLevel = analysis.masteryLevel || 0;
            }
          });
        });
      },
      
      // 生成个性化清单
      generatePersonalizedList(criteria) {
        this.provider.call('generatePersonalizedList', { criteria }).then((list) => {
          this.state.personalizedList = list;
        });
      },
      
      // 切换复习模式
      switchReviewMode(mode) {
        this.state.reviewMode = mode;
        this.$message.success(`已切换至${mode}复习模式`);
      },
      
      // 处理斩题逻辑
      handleZhanti(item) {
        if (item.daysLeft <= 0) {
          this.state.zhantiList = this.state.zhantiList.filter(i => i !== item);
          return;
        }
        this.state.zhantiList.push({ ...item, daysLeft: 10 });
        this.state.zhantiExpiringNotice = this.state.zhantiList.some(i => i.daysLeft <= 2);
      },
      
      // 更新导航徽章
      updateBadges() {
        // 重新计算各科目的待复习题目数量
        setTimeout(() => {
          // 触发重新计算
        }, 100);
      }
    },
    mounted() {
      this.loadData();
    }
  })
</script>
<style lang="css" scoped>
  .wrong-question-page {
    min-height: 100vh;
    background: #f8f9fc;
    font-family: 'Noto Sans SC', 'PingFang SC', sans-serif;
  }
  .wq-main {
    max-width: 1400px;
    margin: 0 auto;
    padding: 24px 32px 40px;
  }
  .wq-filter-bar {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 24px;
    background: #fff;
    padding: 16px 20px;
    border-radius: 14px;
    box-shadow: 0 1px 8px rgba(26, 43, 95, 0.04);
  }
  .filter-group {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .filter-group label {
    font-size: 13px;
    color: #5a6488;
    font-weight: 600;
  }
  .filter-group select {
    padding: 6px 12px;
    border: 1px solid #e8eaf0;
    border-radius: 8px;
    font-size: 13px;
    color: #1a2b5f;
    outline: none;
  }
  .filter-btn {
    padding: 8px 20px;
    background: linear-gradient(135deg, #1a2b5f, #1e3470);
    color: #fff;
    border: none;
    border-radius: 10px;
    cursor: pointer;
    font-weight: 600;
  }
  .wq-body {
    display: grid;
    grid-template-columns: 200px 1fr;
    gap: 24px;
  }
  .wq-nav {
    display: flex;
    flex-direction: column;
    gap: 4px;
    background: #fff;
    border-radius: 14px;
    padding: 12px;
    box-shadow: 0 1px 8px rgba(26, 43, 95, 0.04);
  }
  .nav-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.3s;
    font-size: 14px;
    font-weight: 600;
    color: #5a6488;
    position: relative;
  }
  .nav-item:hover {
    background: #f8f9fc;
  }
  .nav-item.active {
    background: #1a2b5f;
    color: #fff;
  }
  .nav-badge {
    margin-left: auto;
    background: #c41e3a;
    color: #fff;
    font-size: 10px;
    padding: 2px 7px;
    border-radius: 10px;
  }
  .wq-content {
    background: #fff;
    border-radius: 14px;
    padding: 24px;
    box-shadow: 0 1px 8px rgba(26, 43, 95, 0.04);
  }
  .section-top {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    margin-bottom: 20px;
  }
  .section-top h3 {
    font-size: 18px;
    font-weight: 800;
    color: #1a2b5f;
    margin: 0;
  }
  .section-tip {
    font-size: 12px;
    color: #8a8faa;
  }
  .empty-state {
    text-align: center;
    padding: 60px 0;
    color: #8a8faa;
  }
  .empty-icon {
    font-size: 48px;
  }
  .zhanti-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
  .zhanti-card {
    border: 1px solid #e8eaf0;
    border-radius: 12px;
    padding: 16px;
    transition: all 0.3s;
    cursor: pointer;
  }
  .zhanti-card.expiring {
    border-color: #fecaca;
    background: #fff5f5;
  }
  .card-top {
    display: flex;
    justify-content: space-between;
    margin-bottom: 8px;
  }
  .card-subject {
    font-size: 12px;
    font-weight: 700;
    color: #1a2b5f;
  }
  .card-days {
    font-size: 11px;
    color: #ef4444;
  }
  .card-title-text {
    font-size: 14px;
    color: #333;
    margin: 0 0 12px;
    line-height: 1.5;
  }
  .card-bottom {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 11px;
    color: #8a8faa;
  }
  .card-bottom button {
    padding: 4px 12px;
    background: #1a2b5f;
    color: #fff;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 11px;
    margin-left: 5px;
  }
  .card-bottom .restore-btn {
    background: #dc2626;
  }
  .expiring-notice {
    margin-top: 16px;
    padding: 12px;
    background: #fef3c7;
    border-radius: 10px;
    font-size: 13px;
    color: #92400e;
    text-align: center;
  }
  .review-options {
    display: flex;
    gap: 16px;
  }
  .review-option {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 24px;
    border-radius: 14px;
    border: 2px dashed #e8eaf0;
    cursor: pointer;
    transition: all 0.3s;
    flex: 1;
    font-size: 14px;
    font-weight: 600;
    color: #1a2b5f;
  }
  .review-option:hover {
    border-color: #c41e3a;
    background: #fef2f2;
  }
  .option-icon {
    width: 52px;
    height: 52px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
  }
  .question-items {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .q-item {
    padding: 16px;
    border: 1px solid #e8eaf0;
    border-radius: 12px;
    cursor: pointer;
    transition: all 0.3s;
  }
  .q-item:hover {
    border-color: #cbd5e0;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  }
  .q-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 6px;
  }
  .q-type {
    font-size: 11px;
    background: #eff6ff;
    color: #3b82f6;
    padding: 2px 8px;
    border-radius: 6px;
    font-weight: 600;
  }
  .q-date {
    font-size: 11px;
    color: #8a8faa;
  }
  .q-status {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 6px;
    font-weight: 600;
  }
  .q-status.needs-review {
    background: #fef3c7;
    color: #92400e;
  }
  .q-status.chopped {
    background: #d1fae5;
    color: #065f46;
  }
  .q-status.mastered {
    background: #ddd6fe;
    color: #5b21b6;
  }
  .q-title {
    font-size: 14px;
    color: #1a2b5f;
    margin: 0 0 8px;
  }
  .q-tags {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .q-tags .tag {
    font-size: 10px;
    padding: 2px 8px;
    background: #f8f9fc;
    border-radius: 6px;
    color: #5a6488;
  }
  
  /* 新增样式：复习模式 */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  .modal-content {
    background: white;
    padding: 24px;
    border-radius: 12px;
    width: 500px;
    max-width: 90vw;
  }
  .review-mode-options {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin: 20px 0;
  }
  .mode-option {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    border: 1px solid #e8eaf0;
    border-radius: 8px;
    cursor: pointer;
  }
  .mode-option:hover {
    background: #f8f9fc;
  }
  .mode-icon {
    font-size: 20px;
  }
  .close-modal-btn {
    padding: 8px 16px;
    background: #e8eaf0;
    border: none;
    border-radius: 6px;
    cursor: pointer;
  }
  
  /* 答题界面样式 */
  .review-container {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: white;
    z-index: 1001;
    display: flex;
    flex-direction: column;
    padding: 20px;
  }
  .review-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 20px;
    border-bottom: 1px solid #e8eaf0;
  }
  .review-controls button {
    padding: 8px 16px;
    background: #e8eaf0;
    border: none;
    border-radius: 6px;
    cursor: pointer;
  }
  .question-content {
    flex: 1;
    overflow-y: auto;
    padding: 20px 0;
  }
  .options {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .option {
    padding: 12px;
    border: 1px solid #e8eaf0;
    border-radius: 8px;
    cursor: pointer;
  }
  .option:hover {
    background: #f8f9fc;
  }
  .option.selected {
    border-color: #1a2b5f;
    background: #eff6ff;
  }
  .option .option-letter {
    font-weight: bold;
    margin-right: 8px;
  }
  .text-answer textarea {
    width: 100%;
    padding: 12px;
    border: 1px solid #e8eaf0;
    border-radius: 8px;
    resize: vertical;
  }
  .review-actions {
    display: flex;
    gap: 10px;
    justify-content: center;
    padding-top: 20px;
  }
  .review-actions button {
    padding: 10px 20px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
  }
  .review-actions button:not(.secondary) {
    background: #1a2b5f;
    color: white;
  }
  .review-actions button.secondary {
    background: #e8eaf0;
  }
  
  /* 解析模态框样式 */
  .analysis-modal {
    background: white;
    padding: 24px;
    border-radius: 12px;
    width: 700px;
    max-width: 90vw;
    max-height: 80vh;
    overflow-y: auto;
  }
  .analysis-content {
    margin: 20px 0;
  }
  .correct-answer h4 {
    color: #16a34a;
    margin: 10px 0;
  }
  .recommendation-section {
    margin: 20px 0;
    padding: 15px;
    background: #fef2f2;
    border-radius: 8px;
  }
  .similar-questions {
    margin-top: 10px;
  }
  .similar-q-item {
    padding: 8px;
    background: #fef7ed;
    border-radius: 6px;
    margin: 5px 0;
    cursor: pointer;
  }
  .similar-q-item:hover {
    background: #fde6c7;
  }
  .chop-question-section {
    margin: 20px 0;
    padding: 15px;
    background: #f0fdf4;
    border-radius: 8px;
  }
  .chop-verification ul {
    margin: 10px 0;
    padding-left: 20px;
  }
  .chop-verification li {
    margin: 5px 0;
  }
  .chop-actions {
    display: flex;
    gap: 10px;
    margin-top: 10px;
  }
  .analysis-actions {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
    margin-top: 20px;
  }
  .analysis-actions button {
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
  }
  .analysis-actions button:not(.secondary) {
    background: #1a2b5f;
    color: white;
  }
  .analysis-actions button.secondary {
    background: #e8eaf0;
  }
  
  /* 错题复现页面样式 */
  .wrong-question-practice {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: white;
    z-index: 1002;
    display: flex;
    flex-direction: column;
    padding: 20px;
  }
  .practice-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 20px;
    border-bottom: 1px solid #e8eaf0;
  }
  .practice-info {
    display: flex;
    align-items: center;
    gap: 15px;
  }
  .practice-info button {
    padding: 8px 16px;
    background: #e8eaf0;
    border: none;
    border-radius: 6px;
    cursor: pointer;
  }
  .practice-content {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  .current-question {
    flex: 1;
    overflow-y: auto;
    padding: 20px 0;
  }
  .current-question h3 {
    margin-bottom: 20px;
  }
  .practice-navigation {
    display: flex;
    gap: 10px;
    justify-content: center;
    padding-top: 20px;
  }
  .practice-navigation button {
    padding: 10px 20px;
    border: none;
    border-radius: 6px;
    cursor: pointer;
  }
  .practice-navigation button:not(:disabled) {
    background: #1a2b5f;
    color: white;
  }
  .practice-navigation button:disabled {
    background: #e8eaf0;
    color: #8a8faa;
    cursor: not-allowed;
  }
  /* 笔记按钮 */
  .wq-note-btn {
    padding: 2px 10px; border: 1px solid #dbeafe; border-radius: 10px;
    background: #eff6ff; font-size: 11px; color: #3b82f6; cursor: pointer;
    transition: all 0.2s; margin-left: auto;
  }
  .wq-note-btn:hover { background: #dbeafe; border-color: #3b82f6; }
  /* 笔记弹窗 */
  .wq-note-overlay {
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.45); display: flex; align-items: center;
    justify-content: center; z-index: 1000;
  }
  .wq-note-panel {
    background: #fff; border-radius: 16px; padding: 24px;
    width: 440px; max-width: 90vw; box-shadow: 0 8px 32px rgba(26,43,95,0.15);
  }
  .wq-note-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
  .wq-note-header h3 { margin: 0; font-size: 15px; font-weight: 700; color: #1a2b5f; }
  .wq-note-close { width: 28px; height: 28px; border: none; background: transparent; font-size: 20px; color: #8a8faa; cursor: pointer; border-radius: 8px; }
  .wq-note-close:hover { background: #f0f2f5; color: #1a2b5f; }
  .wq-note-textarea {
    width: 100%; padding: 12px; border: 1.5px solid #e0e3e8; border-radius: 10px;
    font-size: 13px; color: #1a2b5f; font-family: inherit; resize: vertical;
    outline: none; box-sizing: border-box; margin-bottom: 14px;
  }
  .wq-note-textarea:focus { border-color: #c41e3a; }
  .wq-note-footer { display: flex; gap: 10px; justify-content: flex-end; }
  .wq-note-btn-delete { padding: 7px 18px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; background: #fee2e2; color: #dc2626; }
  .wq-note-btn-delete:hover { background: #fecaca; }
  .wq-note-btn-save { padding: 7px 18px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; background: #1a2b5f; color: #fff; }
  .wq-note-btn-save:hover { background: #c41e3a; }
</style>