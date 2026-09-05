<!-- 错题集模块 -->
<template>
  <div class="wrong-question-page">
    <NavBar></NavBar>
    <!-- 斩题过期提醒横幅 -->
    <div v-if="state.zhantiExpiringNotice" class="zhanti-expiring-banner">
      <span>{{ state.zhantiExpiringMessage }}（{{ state.zhantiExpiringCount }}题即将删除）</span>
      <button @click="switchNav('zhanti')">查看</button>
    </div>
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
          <label> 子科目</label>
          <select v-model="state.filter.knowledge">
            <option value="all">全部知识点</option>
            <option value="基础知识">基础知识</option>
            <option value="基本警务能力">基本警务能力</option>
            <option value="职业素养">职业素养</option>
            <option value="政治理论">政治理论</option>
            <option value="常识判断">常识判断</option>
            <option value="归纳概括">归纳概括</option>
            <option value="综合分析">综合分析</option>
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
              <p class="review-desc">选择复习方式，开始针对性练习</p>
            </div>

            <div class="review-cards">
              <!-- 按知识点复习卡片 -->
              <div class="review-card" :class="{ active: state.reviewMode === 'knowledge' }" @click="setReviewMode('knowledge')">
                <div class="card-header">
                  <span class="card-icon">📚</span>
                  <span class="card-title">按知识点</span>
                </div>
                <div class="card-body">
                  <div v-if="state.subcategories.length === 0" class="card-empty">暂无错题分类</div>
                  <div v-else class="subcategory-list">
                    <div v-for="sc in state.subcategories" :key="sc.subject_id + '_' + sc.subcategory"
                         class="subcategory-item"
                         :class="{ selected: state.selectedSubcategory === sc.subcategory }"
                         @click.stop="selectSubcategory(sc)">
                      <span class="sc-name">{{ sc.subcategory }}</span>
                      <span class="sc-count">{{ sc.count }}题</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 按收录时间复习卡片 -->
              <div class="review-card" :class="{ active: state.reviewMode === 'time' }" @click="setReviewMode('time')">
                <div class="card-header">
                  <span class="card-icon">📅</span>
                  <span class="card-title">按收录时间</span>
                </div>
                <div class="card-body">
                  <div class="time-options">
                    <div class="time-option" :class="{ selected: state.selectedTime === 'week' }" @click.stop="selectTime('week')">
                      最近一周
                    </div>
                    <div class="time-option" :class="{ selected: state.selectedTime === 'month' }" @click.stop="selectTime('month')">
                      最近一月
                    </div>
                    <div class="time-option" :class="{ selected: state.selectedTime === 'all' }" @click.stop="selectTime('all')">
                      全部
                    </div>
                  </div>
                </div>
              </div>

              <!-- 按科目复习卡片 -->
              <div class="review-card" :class="{ active: state.reviewMode === 'subject' }" @click="setReviewMode('subject')">
                <div class="card-header">
                  <span class="card-icon">📋</span>
                  <span class="card-title">按科目</span>
                </div>
                <div class="card-body">
                  <div class="subject-options">
                    <div class="subject-option" :class="{ selected: state.selectedSubject === 1 }" @click.stop="selectSubject(1)">
                      行测 <span class="count">{{ getSubjectCount(1) }}题</span>
                    </div>
                    <div class="subject-option" :class="{ selected: state.selectedSubject === 2 }" @click.stop="selectSubject(2)">
                      申论 <span class="count">{{ getSubjectCount(2) }}题</span>
                    </div>
                    <div class="subject-option" :class="{ selected: state.selectedSubject === 3 }" @click.stop="selectSubject(3)">
                      公专 <span class="count">{{ getSubjectCount(3) }}题</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 混合复习卡片 -->
              <div class="review-card" :class="{ active: state.reviewMode === 'mixed' }" @click="setReviewMode('mixed')">
                <div class="card-header">
                  <span class="card-icon">🔀</span>
                  <span class="card-title">混合复习</span>
                </div>
                <div class="card-body">
                  <div class="mixed-desc">所有错题随机混合，综合复习</div>
                  <div class="mixed-count">共 {{ state.allQuestions.length }} 道错题</div>
                </div>
              </div>
            </div>

            <div class="review-confirm">
              <button class="confirm-btn" @click="confirmReview" :disabled="!canConfirmReview">确认开始复习</button>
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
                  <span class="q-type"> {{ getTypeLabel(q.type) }}</span>
                  <span class="q-date"> {{ formatDate(q.date) }}</span>
                  <span class="q-status" :class="q.status">{{ q.statusText }}</span>
                </div>
                <p class="q-title">
                  {{ q.title }}
                </p>
                <div class="q-tags">
                  <span v-for="(tag, index) in q.tags" :key="tag" class="tag">
                    {{ tag }}</span
                  >
                  <button v-if="!q.chopped" class="wq-chop-btn" @click.stop="chopQuestionDirect(q)">斩</button>
                  <button v-if="q.chopped" class="wq-unchop-btn" @click.stop="unchopQuestion(q)">恢复</button>
                  <button class="wq-note-btn" @click.stop="openNoteEditor(q.id)">笔记</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 答题界面（重构为答题卡风格） -->
      <div v-if="state.inReviewMode" class="review-container">
        <div class="review-toolbar">
          <div class="review-progress-info">
            <span class="progress-text">第 {{ state.currentWrongQuestionIndex + 1 }} / {{ state.wrongQuestionList.length }} 题</span>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: reviewProgressPercent + '%' }"></div>
            </div>
            <span class="answered-count">已答 {{ answeredCount }} / {{ state.wrongQuestionList.length }}</span>
          </div>
          <button class="review-exit-btn" @click="exitReviewMode">退出复习</button>
        </div>
        <div class="review-body">
          <!-- 左侧答题卡面板 -->
          <aside class="answer-sheet-panel">
            <div class="sheet-title">答题卡</div>
            <div class="sheet-grid">
              <div
                v-for="(q, idx) in state.wrongQuestionList"
                :key="q.id"
                :class="['sheet-cell', {
                  current: idx === state.currentWrongQuestionIndex,
                  answered: isQuestionAnswered(idx)
                }]"
                @click="jumpToQuestion(idx)">
                {{ idx + 1 }}
              </div>
            </div>
          </aside>
          <!-- 右侧题目区 -->
          <section class="question-block" v-if="state.currentQuestion">
            <div class="q-block-header">
              <span :class="['q-type-badge', getTypeClass(state.currentQuestion.type)]">{{ getTypeLabel(state.currentQuestion.type) }}</span>
              <span class="q-difficulty">难度：{{ '★'.repeat(state.currentQuestion.difficulty || 3) }}</span>
            </div>
            <div class="q-block-stem" v-html="renderImageMarkers(state.currentQuestion.title, state.currentQuestion.image_map)"></div>
            <!-- 多选提示 -->
            <div v-if="state.currentQuestion.type === '多选题'" class="multi-hint">
              <strong>多选题</strong> — 点击多个选项进行选择
            </div>
            <!-- 选项区 -->
            <div class="q-block-options" v-if="state.currentQuestion.options && state.currentQuestion.options.length">
              <div
                v-for="(opt, oidx) in state.currentQuestion.options"
                :key="oidx"
                :class="['option-item', {
                  selected: isOptionSelected(state.currentWrongQuestionIndex, oidx),
                  multi: state.currentQuestion.type === '多选题'
                }]"
                @click="selectReviewOption(state.currentWrongQuestionIndex, oidx, state.currentQuestion.type)">
                <span class="option-label" :class="{ multi: state.currentQuestion.type === '多选题' }">
                  {{ String.fromCharCode(65 + oidx) }}
                  <span v-if="isOptionSelected(state.currentWrongQuestionIndex, oidx) && state.currentQuestion.type === '多选题'" class="check-icon">&#10003;</span>
                </span>
                <span class="option-text" v-html="renderImageMarkers(opt.text || opt.value, state.currentQuestion.image_map)"></span>
              </div>
            </div>
            <!-- 论述题/写作题文本输入区 -->
            <div v-else class="q-block-textarea">
              <textarea
                v-model="state.practiceTextAnswers[state.currentWrongQuestionIndex]"
                :placeholder="state.currentQuestion.type === '写作题' ? '请输入您的写作内容...' : '请输入您的答案...'"
                :rows="state.currentQuestion.type === '写作题' ? 10 : 5"></textarea>
            </div>
          </section>
        </div>
        <!-- 底部导航 -->
        <div class="review-nav">
          <button class="nav-btn prev-btn" @click="prevReviewQuestion" :disabled="state.currentWrongQuestionIndex <= 0">上一题</button>
          <button class="nav-btn submit-btn" @click="submitReviewAnswers">交卷</button>
          <button class="nav-btn next-btn" @click="nextReviewQuestion" :disabled="state.currentWrongQuestionIndex >= state.wrongQuestionList.length - 1">下一题</button>
        </div>
      </div>

      <!-- 题目详情弹窗 -->
      <div v-if="state.showQuestionDetail" class="wq-detail-overlay" @click.self="closeQuestionDetail">
        <div class="wq-detail-modal">
          <div class="wq-detail-header">
            <div class="detail-meta">
              <span :class="['detail-type', getTypeClass(state.detailQuestion.type)]">{{ getTypeLabel(state.detailQuestion.type) }}</span>
              <span class="detail-difficulty">难度：{{ '★'.repeat(state.detailQuestion.difficulty || 3) }}</span>
              <span class="detail-rate">全网正确率：{{ state.detailQuestion.globalAccuracy || 0 }}%</span>
            </div>
            <button class="detail-close-btn" @click="closeQuestionDetail">关闭</button>
          </div>
          <div class="wq-detail-body">
            <div class="detail-question-content">
              <p class="detail-stem" v-html="renderImageMarkers(state.detailQuestion.content, state.detailQuestion.image_map)"></p>
            </div>
            <div class="detail-options" v-if="state.detailQuestion.options && state.detailQuestion.options.length">
              <div
                v-for="(opt, idx) in state.detailQuestion.options"
                :key="idx"
                :class="['detail-option', {
                  correct: isCorrectOption(opt.key, state.detailQuestion.correctAnswer),
                  wrong: isWrongOption(opt.key, state.detailQuestion.userAnswer, state.detailQuestion.correctAnswer)
                }]">
                <span class="option-letter">{{ opt.key || String.fromCharCode(65 + idx) }}.</span>
                <span class="option-text" v-html="renderImageMarkers(opt.value || opt.text, state.detailQuestion.image_map)"></span>
              </div>
            </div>
            <div class="detail-user-answer" v-if="state.detailQuestion.userAnswer">
              <strong>您的答案：</strong><span class="user-answer-text">{{ state.detailQuestion.userAnswer }}</span>
            </div>
            <div class="detail-analysis-section">
              <h4>答案解析</h4>
              <p v-html="renderImageMarkers(state.detailQuestion.analysis, state.detailQuestion.image_map)"></p>
            </div>
          </div>
        </div>
      </div>

      <!-- 批改结果页 -->
      <div v-if="state.showReviewResult" class="review-result-page">
        <div class="result-header">
          <h2>复习结果</h2>
          <div class="result-summary">
            <span class="result-stat correct">正确：{{ state.reviewResult.correct_count }}</span>
            <span class="result-stat wrong">错误：{{ state.reviewResult.wrong_count }}</span>
            <span class="result-stat total">总计：{{ state.reviewResult.total }}</span>
            <span class="result-stat auto-chop" v-if="state.reviewResult.auto_chopped && state.reviewResult.auto_chopped.length">
              自动斩题：{{ state.reviewResult.auto_chopped.length }}题
            </span>
          </div>
        </div>
        <div class="result-body">
          <div
            v-for="(r, idx) in state.reviewResult.results"
            :key="idx"
            :class="['result-item', { correct: r.is_correct, wrong: !r.is_correct }]">
            <div class="result-item-header">
              <span class="result-q-num">第{{ idx + 1 }}题</span>
              <span :class="['q-type-badge', getTypeClass(r.type)]">{{ getTypeLabel(r.type) }}</span>
              <span :class="['result-badge', r.is_correct ? 'correct' : 'wrong']">
                {{ r.is_correct ? '✓ 回答正确' : '✗ 回答错误' }}
              </span>
            </div>
            <p class="result-q-stem" v-html="r.content"></p>
            <div class="result-options" v-if="r.options && r.options.length">
              <div
                v-for="(opt, oidx) in r.options"
                :key="oidx"
                :class="['result-option', {
                  correct: isCorrectOption(opt.key, r.correct_answer),
                  wrong: isWrongOption(opt.key, r.user_answer, r.correct_answer)
                }]">
                <span class="option-letter">{{ opt.key || String.fromCharCode(65 + oidx) }}.</span>
                <span class="option-text" v-html="opt.value || opt.text"></span>
              </div>
            </div>
            <div class="result-user-answer">
              <strong>您的答案：</strong><span>{{ r.user_answer || '未作答' }}</span>
            </div>
            <div class="result-correct-answer">
              <strong>正确答案：</strong><span class="correct-answer-text">{{ r.correct_answer }}</span>
            </div>
            <div class="result-analysis" v-if="r.analysis">
              <strong>解析：</strong><span v-html="r.analysis"></span>
            </div>
          </div>
        </div>
        <div class="result-actions">
          <button class="result-btn continue-btn" @click="continueReviewSameMode">继续复习</button>
          <button class="result-btn close-btn" @click="closeReviewResult">关闭</button>
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
  import { ElMessage } from 'element-plus';
  export default defineComponent({
    name: 'WrongQuestionSet',
    components: { NavBar, XIcon },
    setup(props) {
      const provider = useProvider({ id: 'wrong_questions', version: '1785754600000' });
      const state = reactive({
        filter: { time: 'all', knowledge: 'all' },
        activeNav: 'xc',
        navNameMap: { xc: '行测', sl: '申论', ga: '公专' },
        zhantiList: [],
        allQuestions: [],
        zhantiExpiringNotice: false,
        zhantiExpiringMessage: '您有斩题进入观察期，请去看看',
        zhantiExpiringCount: 0,
        // 复习相关状态
        showReviewModal: false,
        // 卡片式复习相关
        reviewMode: '',           // knowledge/time/subject/mixed
        subcategories: [],        // 动态加载的子科目列表
        selectedSubcategory: '',  // 选中的子科目
        selectedTime: '',         // 选中的时间范围 week/month/all
        selectedSubject: 0,       // 选中的科目ID 1/2/3
        inReviewMode: false,
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
        // 错题复现状态
        inWrongQuestionPractice: false,
        wrongQuestionList: [],
        currentWrongQuestionIndex: 0,
        selectedAnswers: {},
        practiceTextAnswers: {},
        // 笔记相关
        showNoteEditor: false,
        noteText: '',
        currentNoteQuestionId: null,
        // 题目详情弹窗
        showQuestionDetail: false,
        detailQuestion: null,
        // 批改结果页
        showReviewResult: false,
        reviewResult: null,
        // 复习模式记录
        currentReviewMode: ''
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
          (q) => q.subject === this.state.activeNav && !q.chopped
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
      reviewProgressPercent() {
        if (!this.state.wrongQuestionList.length) return 0;
        return Math.round(((this.state.currentWrongQuestionIndex + 1) / this.state.wrongQuestionList.length) * 100);
      },
      answeredCount() {
        var count = 0;
        for (var i = 0; i < this.state.wrongQuestionList.length; i++) {
          if (this.isQuestionAnswered(i)) count++;
        }
        return count;
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
        // 直接从未过滤的allQuestions计算，而非filteredQuestions（后者已按activeNav过滤）
        return this.state.allQuestions.filter(function(q) {
          return q.subject === subject && !q.chopped;
        }).length;
      },
      
      loadData() {
        this.state.allQuestions = [];
        var self = this;
        this.ensureLogin().then(function() {
          var headers = self.getJsonHeaders();
          // 调用正确的错题API（非全部题目API）
          window.__VTJ_AUTH__.apiFetch('/api/wrong-questions?page_size=100', { headers: headers })
            .then(function(res) { return res.json(); })
            .then(function(data) {
              var items = data.items || [];
              if (items.length) {
                self.state.allQuestions = items.map(function(item) {
                  // 用 subject_id 精确映射科目
                  var subjectIdMap = { 1: 'xc', 2: 'sl', 3: 'ga' };
                  var subjectKey = subjectIdMap[item.subject_id] || 'ga';
                  var optionsArr = [];
                  try {
                    optionsArr = item.options ? (typeof item.options === 'string' ? JSON.parse(item.options) : item.options) : [];
                  } catch(e) {}
                  return {
                    id: item.question_id,
                    wrong_id: item.wrong_id,
                    subject: subjectKey,
                    type: item.question_type_detail || '单选题',
                    date: item.add_time || '',
                    title: item.question_content || '',
                    tags: item.sub_category ? [item.sub_category] : [],
                    status: item.is_cut ? 'chopped' : (item.mastery_level === 'MASTERED' ? 'mastered' : 'needs-review'),
                    statusText: item.is_cut ? '已斩题' : (item.mastery_level === 'MASTERED' ? '已掌握' : '待复习'),
                    options: Array.isArray(optionsArr) ? optionsArr.map(function(o, i) {
                      return {
                        value: o.key || String.fromCharCode(65+i),
                        text: o.value || o.text || o
                      };
                    }) : [],
                    correctAnswer: item.answer || '',
                    analysis: item.answer_analysis || '',
                    difficulty: item.difficulty || 3,
                    masteryLevel: item.mastery_level === 'MASTERED' ? 100 : (item.mastery_level === 'PARTIAL' ? 50 : 0),
                    chopped: !!item.is_cut,
                    errorCount: item.error_count || 1,
                    category: item.subject_name || ''
                  };
                });
              }
            }).catch(function() {
              console.warn('WrongQuestionSet: 无法连接后端，请检查网络');
            });
        }).catch(function() {
          console.warn('WrongQuestionSet: 登录验证失败');
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
        ElMessage.success('筛选条件已更新');
      },
      
      // 设置复习模式
      setReviewMode(mode) {
        this.state.reviewMode = mode;
        // 重置选择
        if (mode !== 'knowledge') this.state.selectedSubcategory = '';
        if (mode !== 'time') this.state.selectedTime = '';
        if (mode !== 'subject') this.state.selectedSubject = 0;
        // 知识点模式自动加载子科目
        if (mode === 'knowledge' && this.state.subcategories.length === 0) {
          this.loadSubcategories();
        }
      },

      // 加载子科目分类
      async loadSubcategories() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/wrong-questions/subcategories', {
            headers: this.getJsonHeaders()
          });
          const data = await res.json();
          this.state.subcategories = data.items || [];
        } catch(e) {
          console.warn('加载子科目失败:', e);
        }
      },

      // 选择子科目
      selectSubcategory(sc) {
        this.state.selectedSubcategory = sc.subcategory;
      },

      // 选择时间范围
      selectTime(time) {
        this.state.selectedTime = time;
      },

      // 选择科目
      selectSubject(subjectId) {
        this.state.selectedSubject = subjectId;
      },

      // 获取科目错题数量
      getSubjectCount(subjectId) {
        var subjectKey = { 1: 'xc', 2: 'sl', 3: 'ga' }[subjectId];
        return this.state.allQuestions.filter(q => q.subject === subjectKey && !q.chopped).length;
      },

      // 是否可以确认复习
      canConfirmReview() {
        if (!this.state.reviewMode) return false;
        if (this.state.reviewMode === 'knowledge' && !this.state.selectedSubcategory) return false;
        if (this.state.reviewMode === 'time' && !this.state.selectedTime) return false;
        if (this.state.reviewMode === 'subject' && !this.state.selectedSubject) return false;
        return true;
      },

      // 确认开始复习
      async confirmReview() {
        if (!this.canConfirmReview()) return;

        var mode = this.state.reviewMode;
        this.state.currentReviewMode = mode;
        var params = 'mode=' + mode + '&limit=50';

        if (mode === 'knowledge') {
          params += '&subcategory=' + encodeURIComponent(this.state.selectedSubcategory);
        } else if (mode === 'subject') {
          params += '&subject_id=' + this.state.selectedSubject;
        }

        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/wrong-questions/review/queue?' + params, {
            headers: this.getJsonHeaders()
          });
          const data = await res.json();

          if (!data.items || data.items.length === 0) {
            ElMessage.warning('没有需要复习的题目');
            return;
          }

          // 转换为复习格式
          var questionsToReview = data.items.map(item => this.mapWrongQuestion(item));

          // 混合模式：随机打乱顺序
          if (mode === 'mixed') {
            questionsToReview.sort(function() { return Math.random() - 0.5; });
          }

          this.state.wrongQuestionList = questionsToReview;
          this.state.currentWrongQuestionIndex = 0;
          this.state.selectedAnswers = {};
          this.state.practiceTextAnswers = {};
          this.state.currentQuestion = questionsToReview[0];
          this.state.inReviewMode = true;
        } catch(e) {
          ElMessage.error('加载复习队列失败');
          console.error(e);
        }
      },

      // 映射错题数据为复习格式
      mapWrongQuestion(item) {
        var subjectIdMap = { 1: 'xc', 2: 'sl', 3: 'ga' };
        var subjectKey = subjectIdMap[item.subject_id] || 'ga';
        var optionsArr = [];
        try {
          optionsArr = item.question_options ? (typeof item.question_options === 'string' ? JSON.parse(item.question_options) : item.question_options) : [];
        } catch(e) {}
        // 统一题型映射
        var rawType = item.question_type_detail || item.type || '单选题';
        var typeMap = {
          '单选题': '单选题', '选择题': '单选题', '无': '单选题',
          '多选题': '多选题', '不定项': '多选题', '多选': '多选题',
          '论述题': '论述题', '简答题': '论述题', '案例分析题': '论述题',
          '写作题': '写作题'
        };
        var unifiedType = typeMap[rawType] || '单选题';
        return {
          id: item.question_id,
          wrong_id: item.wrong_id,
          subject: subjectKey,
          type: unifiedType,
          date: item.add_time || '',
          title: item.question_content || '',
          tags: item.subcategory ? [item.subcategory] : [],
          status: item.is_cut ? 'chopped' : 'needs-review',
          statusText: item.is_cut ? '已斩题' : '待复习',
          options: Array.isArray(optionsArr) ? optionsArr.map(function(o, i) {
            return { value: o.key || String.fromCharCode(65+i), text: o.value || o.text || o, key: o.key || String.fromCharCode(65+i) };
          }) : [],
          correctAnswer: item.question_answer || '',
          analysis: item.answer_analysis || '',
          difficulty: item.question_difficulty || 3,
          masteryLevel: item.mastery_level === 'MASTERED' ? 100 : 0,
          chopped: !!item.is_cut,
          errorCount: item.error_count || 1
        };
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
          ElMessage.warning('没有需要复习的题目');
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
        var q = this.state.currentQuestion;
        if (!q) return false;
        if (q.options && q.options.length) {
          return String(userAnswer).trim() === String(q.correctAnswer).trim();
        } else {
          // 无选项题目(填空/简答)：模糊比较，忽略首尾空格
          var user = String(userAnswer || '').trim().toLowerCase();
          var correct = String(q.correctAnswer || '').trim().toLowerCase();
          if (!user || !correct) return false;
          // 完全匹配或包含核心答案
          return user === correct || correct.indexOf(user) >= 0 || user.indexOf(correct) >= 0;
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
      
      async confirmChopQuestion() {
        if (!this.state.currentQuestion || !this.state.currentQuestion.wrong_id) return;
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/wrong-questions/' + this.state.currentQuestion.wrong_id + '/chop', {
            method: 'PUT',
            headers: this.getJsonHeaders()
          });
          if (res.ok) {
            this.state.currentQuestion.chopped = true;
            ElMessage.success('已斩题，10天后自动删除');
          }
        } catch(e) {
          console.warn('斩题失败:', e);
        }
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
          ElMessage.success('恭喜您完成本轮复习！');
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
        ElMessage.info('正在加载相似题目...');
        // 这里可以导航到具体的相似题目页面
      },
      
      goToQuestion(q) {
        // 打开题目详情弹窗
        this.openQuestionDetail(q);
      },

      // ========== 题目详情弹窗 ==========
      async openQuestionDetail(q) {
        if (!q || !q.wrong_id) {
          ElMessage.warning('无法查看详情：缺少错题ID');
          return;
        }
        try {
          ElMessage.info('加载题目详情...');
          const res = await window.__VTJ_AUTH__.apiFetch('/api/wrong-questions/' + q.wrong_id + '/detail', {
            headers: this.getJsonHeaders()
          });
          if (!res.ok) {
            ElMessage.error('获取详情失败');
            return;
          }
          const data = await res.json();
          this.state.detailQuestion = {
            wrong_id: data.wrong_id,
            question_id: data.question_id,
            content: data.content,
            options: data.options || [],
            correctAnswer: data.correct_answer || '',
            userAnswer: data.user_answer || '',
            analysis: data.analysis || '',
            difficulty: data.difficulty || 3,
            type: data.type || '单选题',
            globalAccuracy: data.global_accuracy || 0,
            is_cut: data.is_cut,
            image_map: data.image_map || {}
          };
          this.state.showQuestionDetail = true;
        } catch(e) {
          console.warn('获取题目详情失败:', e);
          ElMessage.error('获取详情失败：' + (e.message || '网络错误'));
        }
      },
      closeQuestionDetail() {
        this.state.showQuestionDetail = false;
        this.state.detailQuestion = null;
      },

      // ========== 图片占位符替换 ==========
      renderImageMarkers(html, imageMap) {
        if (!html) return '';
        var imgMap = imageMap || {};
        return html.replace(/\[IMAGE:(\d+)_(\d+)\]/g, function(match, num, seq) {
          var key = num + '_' + seq;
          var src = imgMap[key];
          if (!src) {
            // 无映射记录，隐藏占位符
            return '';
          }
          return '<img src="' + src + '" onerror="this.style.display=\'none\'" ' +
                 'style="max-width:100%;height:auto;border:1px solid #e8eaf0;' +
                 'border-radius:8px;margin:4px 0;" alt="题目图片" />';
        });
      },

      // ========== 选项高亮判断 ==========
      isCorrectOption(key, correctAnswer) {
        if (!key || !correctAnswer) return false;
        var correctSet = correctAnswer.split(',').map(function(s) { return s.trim().toUpperCase(); });
        return correctSet.indexOf(String(key).toUpperCase()) >= 0;
      },
      isWrongOption(key, userAnswer, correctAnswer) {
        if (!key || !userAnswer) return false;
        var userSet = userAnswer.split(',').map(function(s) { return s.trim().toUpperCase(); });
        var correctSet = correctAnswer.split(',').map(function(s) { return s.trim().toUpperCase(); });
        return userSet.indexOf(String(key).toUpperCase()) >= 0 && correctSet.indexOf(String(key).toUpperCase()) < 0;
      },

      // ========== 题型映射（统一4种类型） ==========
      getTypeLabel(type) {
        var map = {
          '单选题': '[单选]', '选择题': '[单选]', '无': '[单选]',
          '多选题': '[多选]', '不定项': '[多选]', '多选': '[多选]',
          '论述题': '[论述]', '简答题': '[论述]', '案例分析题': '[论述]',
          '写作题': '[写作]'
        };
        return map[type] || '[单选]';
      },
      getTypeClass(type) {
        var map = {
          '多选题': 'multi', '不定项': 'multi', '多选': 'multi',
          '论述题': 'essay', '简答题': 'essay', '案例分析题': 'essay',
          '写作题': 'writing'
        };
        return map[type] || '';
      },

      // ========== 复习界面：选项选择 ==========
      selectReviewOption(qIndex, optIndex, type) {
        if (type === '多选题') {
          var current = this.state.selectedAnswers[qIndex] || [];
          if (current.indexOf(optIndex) >= 0) {
            this.state.selectedAnswers[qIndex] = current.filter(function(o) { return o !== optIndex; });
          } else {
            this.state.selectedAnswers[qIndex] = current.concat([optIndex]);
          }
        } else {
          this.state.selectedAnswers[qIndex] = [optIndex];
        }
      },
      isOptionSelected(qIndex, optIndex) {
        var selected = this.state.selectedAnswers[qIndex];
        if (!selected) return false;
        return selected.indexOf(optIndex) >= 0;
      },
      isQuestionAnswered(qIndex) {
        var q = this.state.wrongQuestionList[qIndex];
        if (!q) return false;
        if (q.options && q.options.length) {
          return this.state.selectedAnswers[qIndex] && this.state.selectedAnswers[qIndex].length > 0;
        } else {
          return this.state.practiceTextAnswers[qIndex] && this.state.practiceTextAnswers[qIndex].trim() !== '';
        }
      },
      jumpToQuestion(idx) {
        this.state.currentWrongQuestionIndex = idx;
        this.state.currentQuestion = this.state.wrongQuestionList[idx];
      },
      prevReviewQuestion() {
        if (this.state.currentWrongQuestionIndex > 0) {
          this.state.currentWrongQuestionIndex--;
          this.state.currentQuestion = this.state.wrongQuestionList[this.state.currentWrongQuestionIndex];
        }
      },
      nextReviewQuestion() {
        if (this.state.currentWrongQuestionIndex < this.state.wrongQuestionList.length - 1) {
          this.state.currentWrongQuestionIndex++;
          this.state.currentQuestion = this.state.wrongQuestionList[this.state.currentWrongQuestionIndex];
        }
      },

      // ========== 提交复习答案（调用后端批量判分） ==========
      async submitReviewAnswers() {
        var unanswered = 0;
        for (var i = 0; i < this.state.wrongQuestionList.length; i++) {
          if (!this.isQuestionAnswered(i)) unanswered++;
        }
        if (unanswered > 0) {
          if (!confirm('还有 ' + unanswered + ' 题未作答，确定要交卷吗？')) return;
        }

        var answers = [];
        for (var i = 0; i < this.state.wrongQuestionList.length; i++) {
          var q = this.state.wrongQuestionList[i];
          var userAnswer = '';
          if (q.options && q.options.length) {
            var selected = this.state.selectedAnswers[i] || [];
            // 统一提交字母格式（A/B/C/D），多选题排序后拼接
            var letters = selected.map(function(idx) {
              return String.fromCharCode(65 + idx);
            }).sort();
            userAnswer = letters.join('');
          } else {
            userAnswer = this.state.practiceTextAnswers[i] || '';
          }
          answers.push({
            wrong_id: q.wrong_id,
            question_id: q.id,
            user_answer: userAnswer
          });
        }

        try {
          ElMessage.info('正在提交...');
          const res = await window.__VTJ_AUTH__.apiFetch('/api/wrong-questions/review/submit', {
            method: 'POST',
            headers: this.getJsonHeaders(),
            body: JSON.stringify({
              mode: this.state.currentReviewMode,
              answers: answers
            })
          });
          if (!res.ok) {
            ElMessage.error('提交失败');
            return;
          }
          const data = await res.json();
          this.state.reviewResult = data;
          this.state.showReviewResult = true;
          this.state.inReviewMode = false;
          if (data.auto_chopped && data.auto_chopped.length) {
            ElMessage.success('本次答对3次的 ' + data.auto_chopped.length + ' 道题已自动斩题');
          }
          this.loadZhantiList();
        } catch(e) {
          console.warn('提交复习答案失败:', e);
          ElMessage.error('提交失败：' + (e.message || '网络错误'));
        }
      },

      // ========== 继续复习（同一模式重新加载） ==========
      continueReviewSameMode() {
        this.state.showReviewResult = false;
        this.state.reviewResult = null;
        // 重新加载错题列表后重新开始复习
        this.loadData();
        var self = this;
        setTimeout(function() {
          self.confirmReview();
        }, 800);
      },
      closeReviewResult() {
        this.state.showReviewResult = false;
        this.state.reviewResult = null;
        this.state.inReviewMode = false;
        this.loadData();
        this.loadZhantiList();
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
          ElMessage.success('回答正确！');
        } else {
          ElMessage.error('回答错误，继续努力！');
        }
      },
      
      checkAnswerInPractice(question, userAnswer) {
        if (!question) return false;
        if (question.options && question.options.length) {
          return String(userAnswer).trim() === String(question.correctAnswer).trim();
        } else {
          var user = String(userAnswer || '').trim().toLowerCase();
          var correct = String(question.correctAnswer || '').trim().toLowerCase();
          if (!user || !correct) return false;
          return user === correct || correct.indexOf(user) >= 0 || user.indexOf(correct) >= 0;
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
        ElMessage.info('开始复习：' + item.title);
        
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
      
      async restoreZhanti(item) {
        // 恢复斩题到错题列表 — 调用后端 API 确保数据一致
        if (!item || !item.id) {
          ElMessage.warning('无法恢复：缺少错题ID');
          return;
        }
        try {
          await this.ensureLogin();
          const res = await window.__VTJ_AUTH__.apiFetch('/api/wrong-questions/' + item.id + '/unchop', {
            method: 'POST',
            headers: this.getJsonHeaders()
          });
          if (res.ok) {
            // 从斩题列表中移除（前端即时更新）
            this.state.zhantiList = this.state.zhantiList.filter(z => z.id != item.id);
            this.state.zhantiExpiringNotice = this.state.zhantiList.some(i => i.daysLeft <= 2);
            ElMessage.success('题目已恢复到错题列表');
            // 重新加载错题列表和斩题列表，确保前后端数据一致
            this.loadData();
            this.loadZhantiList();
          } else {
            const errData = await res.json().catch(() => ({}));
            ElMessage.error('恢复失败：' + (errData.detail || '服务器错误'));
          }
        } catch(e) {
          console.warn('恢复失败:', e);
          ElMessage.error('恢复失败：' + (e.message || '网络错误'));
        }
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
            
            ElMessage.info(`错题已收录到${this.state.navNameMap[wrongQuestion.subject]}门类`);
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
        ElMessage.success(`已切换至${mode}复习模式`);
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
      },

      // ========== 日期格式化（年-月-日-时-分） ==========
      formatDate(dateStr) {
        if (!dateStr) return '';
        var d = new Date(dateStr);
        if (isNaN(d.getTime())) return String(dateStr);
        var pad = function(n) { return n < 10 ? '0' + n : String(n); };
        return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
          + '-' + pad(d.getHours()) + '-' + pad(d.getMinutes());
      },

      // ========== 斩题功能（列表直接斩） ==========
      async chopQuestionDirect(q) {
        if (!q || !q.wrong_id) {
          ElMessage.warning('无法斩题：缺少错题ID');
          return;
        }
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/wrong-questions/' + q.wrong_id + '/chop', {
            method: 'PUT',
            headers: this.getJsonHeaders()
          });
          if (res.ok) {
            // 从 allQuestions 中移除该题（filteredQuestions 会自动过滤）
            var idx = this.state.allQuestions.indexOf(q);
            if (idx >= 0) {
              this.state.allQuestions.splice(idx, 1);
            }
            ElMessage.success('已斩题，10天后自动删除');
            this.loadZhantiList();
          } else {
            ElMessage.error('斩题失败');
          }
        } catch(e) {
          console.warn('斩题失败:', e);
          ElMessage.error('斩题失败：' + (e.message || '网络错误'));
        }
      },

      // ========== 取消斩题（恢复到错题列表） ==========
      async unchopQuestion(q) {
        if (!q || !q.wrong_id) {
          ElMessage.warning('无法恢复：缺少错题ID');
          return;
        }
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/wrong-questions/' + q.wrong_id + '/unchop', {
            method: 'POST',
            headers: this.getJsonHeaders()
          });
          if (res.ok) {
            q.chopped = false;
            q.status = 'needs-review';
            q.statusText = '待复习';
            ElMessage.success('题目已恢复到错题列表');
            this.loadZhantiList();
          } else {
            ElMessage.error('恢复失败');
          }
        } catch(e) {
          console.warn('恢复失败:', e);
          ElMessage.error('恢复失败：' + (e.message || '网络错误'));
        }
      },

      // ========== 加载斩题列表 ==========
      async loadZhantiList() {
        try {
          await this.ensureLogin();
          const res = await window.__VTJ_AUTH__.apiFetch('/api/wrong-questions/zhanti/list', {
            headers: this.getJsonHeaders()
          });
          const data = await res.json();
          var items = data.items || [];
          this.state.zhantiList = items.map(function(item) {
            var createTime = item.cut_time || item.add_time || '';
            var daysLeft = 10;
            if (item.auto_delete_time) {
              var now = new Date().getTime();
              var del = new Date(item.auto_delete_time).getTime();
              daysLeft = Math.max(0, Math.ceil((del - now) / (1000 * 60 * 60 * 24)));
            }
            return {
              id: item.wrong_id,
              originalQuestionId: item.question_id,
              subject: item.subject_name || '',
              title: item.question_content || '',
              createTime: createTime,
              daysLeft: daysLeft
            };
          });
          this.state.zhantiExpiringNotice = this.state.zhantiList.some(function(i) { return i.daysLeft <= 2; });
        } catch(e) {
          console.warn('加载斩题列表失败:', e);
          this.state.zhantiList = [];
        }
      },

      // ========== 加载斩题过期提醒 ==========
      async loadZhantiExpiring() {
        try {
          await this.ensureLogin();
          const res = await window.__VTJ_AUTH__.apiFetch('/api/wrong-questions/zhanti/expiring', {
            headers: this.getJsonHeaders()
          });
          const data = await res.json();
          var count = data.count || 0;
          if (count > 0) {
            this.state.zhantiExpiringNotice = true;
            this.state.zhantiExpiringMessage = '您有斩题进入观察期，请去看看';
            this.state.zhantiExpiringCount = count;
          } else {
            this.state.zhantiExpiringNotice = false;
          }
        } catch(e) {
          console.warn('加载斩题提醒失败:', e);
        }
      }
    },
    mounted() {
      this.loadData();
      this.loadZhantiList();
      this.loadZhantiExpiring();
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

  /* 卡片式复习界面样式 */
  .review-cards {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    margin-top: 20px;
  }
  .review-card {
    background: #fff;
    border: 2px solid #e8e8e8;
    border-radius: 12px;
    padding: 20px;
    cursor: pointer;
    transition: all 0.3s;
  }
  .review-card:hover {
    border-color: #409eff;
    box-shadow: 0 2px 12px rgba(64, 158, 255, 0.15);
  }
  .review-card.active {
    border-color: #409eff;
    background: #f0f9ff;
  }
  .card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
  }
  .card-icon { font-size: 24px; }
  .card-title { font-size: 16px; font-weight: 600; color: #333; }
  .card-body { min-height: 80px; }
  .card-empty { color: #999; font-size: 14px; text-align: center; padding: 20px 0; }
  .subcategory-list, .time-options, .subject-options {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .subcategory-item, .time-option, .subject-option {
    padding: 6px 12px;
    border: 1px solid #e8e8e8;
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .subcategory-item:hover, .time-option:hover, .subject-option:hover {
    border-color: #409eff;
    color: #409eff;
  }
  .subcategory-item.selected, .time-option.selected, .subject-option.selected {
    background: #409eff;
    color: #fff;
    border-color: #409eff;
  }
  .sc-count, .count { font-size: 12px; color: #999; }
  .subcategory-item.selected .sc-count, .subject-option.selected .count { color: #fff; }
  .mixed-desc { color: #666; font-size: 14px; margin-bottom: 8px; }
  .mixed-count { color: #409eff; font-size: 14px; font-weight: 600; }
  .review-confirm {
    text-align: center;
    margin-top: 24px;
  }
  .confirm-btn {
    padding: 10px 40px;
    font-size: 15px;
    color: #fff;
    background: #409eff;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.3s;
  }
  .confirm-btn:hover { background: #66b1ff; }
  .confirm-btn:disabled { background: #c0c4cc; cursor: not-allowed; }
  .review-desc { color: #999; font-size: 14px; margin-top: 4px; }

  /* ===== 斩题按钮样式 ===== */
  .wq-chop-btn {
    padding: 2px 12px;
    border: 1px solid #dc2626;
    border-radius: 12px;
    background: linear-gradient(135deg, #dc2626, #b91c1c);
    color: #fff;
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.25s;
    margin-left: auto;
    letter-spacing: 1px;
    box-shadow: 0 2px 6px rgba(220, 38, 38, 0.25);
  }
  .wq-chop-btn:hover {
    background: linear-gradient(135deg, #b91c1c, #991b1b);
    transform: translateY(-1px);
    box-shadow: 0 4px 10px rgba(220, 38, 38, 0.35);
  }
  .wq-unchop-btn {
    padding: 2px 10px;
    border: 1px solid #16a34a;
    border-radius: 12px;
    background: #f0fdf4;
    color: #16a34a;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.25s;
    margin-left: auto;
  }
  .wq-unchop-btn:hover {
    background: #dcfce7;
    border-color: #15803d;
  }
  /* 斩题过期提醒横幅 */
  .zhanti-expiring-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    margin-bottom: 16px;
    background: linear-gradient(90deg, #fef3c7, #fee2e2);
    border-left: 4px solid #dc2626;
    border-radius: 10px;
    font-size: 13px;
    color: #92400e;
    font-weight: 600;
  }
  .zhanti-expiring-banner button {
    padding: 4px 14px;
    background: #dc2626;
    color: #fff;
    border: none;
    border-radius: 8px;
    font-size: 12px;
    cursor: pointer;
    font-weight: 600;
  }
  .zhanti-expiring-banner button:hover {
    background: #b91c1c;
  }

  /* ===== 题型徽章样式（4种类型） ===== */
  .q-type-badge {
    font-size: 12px;
    padding: 3px 10px;
    border-radius: 6px;
    background: #eff6ff;
    color: #3b82f6;
    font-weight: 600;
  }
  .q-type-badge.multi { background: #fef3c7; color: #d97706; }
  .q-type-badge.essay { background: #f5f3ff; color: #7c3aed; }
  .q-type-badge.writing { background: #fef2f2; color: #dc2626; }

  /* ===== 复习界面（答题卡风格） ===== */
  .review-container {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: #f8f9fc;
    z-index: 1001;
    display: flex;
    flex-direction: column;
  }
  .review-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 24px;
    background: #1a2b5f;
    color: #fff;
  }
  .review-progress-info {
    display: flex;
    align-items: center;
    gap: 16px;
    flex: 1;
  }
  .progress-text { font-size: 15px; font-weight: 600; min-width: 100px; }
  .progress-bar {
    flex: 1;
    max-width: 400px;
    height: 8px;
    background: rgba(255,255,255,0.2);
    border-radius: 4px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #c41e3a, #f97316);
    transition: width 0.3s;
  }
  .answered-count { font-size: 13px; color: rgba(255,255,255,0.8); }
  .review-exit-btn {
    padding: 6px 18px;
    background: rgba(255,255,255,0.15);
    color: #fff;
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
  }
  .review-exit-btn:hover { background: rgba(255,255,255,0.25); }

  .review-body {
    flex: 1;
    display: flex;
    overflow: hidden;
  }
  .answer-sheet-panel {
    width: 220px;
    background: #fff;
    border-right: 1px solid #e8eaf0;
    padding: 16px;
    overflow-y: auto;
  }
  .sheet-title {
    font-size: 14px;
    font-weight: 700;
    color: #1a2b5f;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 2px solid #1a2b5f;
  }
  .sheet-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 8px;
  }
  .sheet-cell {
    aspect-ratio: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 1.5px solid #e8eaf0;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    color: #5a6488;
    transition: all 0.2s;
  }
  .sheet-cell:hover { border-color: #c41e3a; color: #c41e3a; }
  .sheet-cell.current { background: #1a2b5f; color: #fff; border-color: #1a2b5f; }
  .sheet-cell.answered { background: #d1fae5; color: #065f46; border-color: #6ee7b7; }

  .question-block {
    flex: 1;
    padding: 28px 32px;
    overflow-y: auto;
  }
  .q-block-header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 18px;
  }
  .q-difficulty { font-size: 13px; color: #c41e3a; }
  .q-block-stem {
    font-size: 15px;
    color: #1a2b5f;
    line-height: 1.8;
    margin-bottom: 20px;
  }
  .multi-hint {
    padding: 8px 14px;
    background: #fef3c7;
    border-radius: 8px;
    font-size: 13px;
    color: #92400e;
    margin-bottom: 14px;
  }
  .q-block-options {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .option-item {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 16px;
    border: 1.5px solid #e8eaf0;
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .option-item:hover { border-color: #c41e3a; background: #fef2f2; }
  .option-item.selected {
    border-color: #1a2b5f;
    background: #eff6ff;
  }
  .option-label {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px; height: 28px;
    border-radius: 50%;
    background: #f8f9fc;
    font-size: 13px;
    font-weight: 700;
    color: #5a6488;
    flex-shrink: 0;
  }
  .option-label.multi { border-radius: 6px; }
  .option-item.selected .option-label {
    background: #1a2b5f;
    color: #fff;
  }
  .check-icon { margin-left: 2px; }
  .option-text { font-size: 14px; color: #333; line-height: 1.6; }
  .q-block-textarea textarea {
    width: 100%;
    padding: 14px;
    border: 1.5px solid #e8eaf0;
    border-radius: 10px;
    font-size: 14px;
    font-family: inherit;
    resize: vertical;
    outline: none;
    box-sizing: border-box;
  }
  .q-block-textarea textarea:focus { border-color: #c41e3a; }

  .review-nav {
    display: flex;
    gap: 12px;
    justify-content: center;
    padding: 16px 24px;
    background: #fff;
    border-top: 1px solid #e8eaf0;
  }
  .nav-btn {
    padding: 10px 32px;
    border: none;
    border-radius: 10px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    transition: all 0.2s;
  }
  .nav-btn.prev-btn, .nav-btn.next-btn {
    background: #e8eaf0;
    color: #1a2b5f;
  }
  .nav-btn.prev-btn:hover, .nav-btn.next-btn:hover { background: #cbd5e0; }
  .nav-btn.submit-btn {
    background: linear-gradient(135deg, #c41e3a, #dc2626);
    color: #fff;
  }
  .nav-btn.submit-btn:hover { background: linear-gradient(135deg, #b91c1c, #c41e3a); }
  .nav-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  /* ===== 题目详情弹窗 ===== */
  .wq-detail-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
  }
  .wq-detail-modal {
    background: #fff;
    border-radius: 16px;
    width: 1400px;
    max-width: 95vw;
    height: 800px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 12px 48px rgba(26,43,95,0.2);
  }
  .wq-detail-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 28px;
    background: #1a2b5f;
    color: #fff;
  }
  .detail-meta {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .detail-type {
    padding: 4px 12px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    background: rgba(255,255,255,0.15);
  }
  .detail-type.multi { background: rgba(217,119,6,0.3); }
  .detail-type.essay { background: rgba(124,58,237,0.3); }
  .detail-type.writing { background: rgba(220,38,38,0.3); }
  .detail-difficulty, .detail-rate { font-size: 13px; color: rgba(255,255,255,0.85); }
  .detail-close-btn {
    padding: 6px 20px;
    background: #c41e3a;
    color: #fff;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
  }
  .detail-close-btn:hover { background: #b91c1c; }
  .wq-detail-body {
    flex: 1;
    overflow-y: auto;
    padding: 28px 32px;
  }
  .detail-question-content { margin-bottom: 24px; }
  .detail-stem {
    font-size: 16px;
    color: #1a2b5f;
    line-height: 1.8;
    margin: 0;
  }
  .detail-options {
    display: flex;
    flex-direction: column;
    gap: 10px;
    margin-bottom: 20px;
  }
  .detail-option {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 16px;
    border: 1.5px solid #e8eaf0;
    border-radius: 10px;
  }
  .detail-option.correct {
    border-color: #16a34a;
    background: #f0fdf4;
  }
  .detail-option.wrong {
    border-color: #dc2626;
    background: #fef2f2;
  }
  .detail-option .option-letter { font-weight: 700; color: #5a6488; }
  .detail-option.correct .option-letter { color: #16a34a; }
  .detail-option.wrong .option-letter { color: #dc2626; }
  .detail-option .option-text { font-size: 14px; color: #333; line-height: 1.6; }
  .detail-user-answer {
    padding: 12px 16px;
    background: #f8f9fc;
    border-radius: 8px;
    margin-bottom: 16px;
    font-size: 14px;
  }
  .user-answer-text { color: #dc2626; font-weight: 600; }
  .detail-analysis-section h4 {
    color: #1a2b5f;
    margin: 0 0 10px;
    font-size: 15px;
  }
  .detail-analysis-section p {
    font-size: 14px;
    color: #333;
    line-height: 1.8;
    margin: 0;
  }

  /* ===== 批改结果页 ===== */
  .review-result-page {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: #f8f9fc;
    z-index: 1001;
    display: flex;
    flex-direction: column;
  }
  .result-header {
    padding: 18px 28px;
    background: #1a2b5f;
    color: #fff;
  }
  .result-header h2 { margin: 0 0 8px; font-size: 20px; }
  .result-summary {
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
  }
  .result-stat {
    padding: 4px 14px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    background: rgba(255,255,255,0.15);
  }
  .result-stat.correct { background: rgba(22,163,74,0.3); }
  .result-stat.wrong { background: rgba(220,38,38,0.3); }
  .result-stat.auto-chop { background: rgba(217,119,6,0.3); }
  .result-body {
    flex: 1;
    overflow-y: auto;
    padding: 20px 28px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .result-item {
    background: #fff;
    border-radius: 12px;
    padding: 20px;
    border-left: 4px solid #e8eaf0;
  }
  .result-item.correct { border-left-color: #16a34a; }
  .result-item.wrong { border-left-color: #dc2626; }
  .result-item-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
  }
  .result-q-num { font-size: 14px; font-weight: 700; color: #1a2b5f; }
  .result-badge {
    padding: 3px 12px;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
  }
  .result-badge.correct { background: #d1fae5; color: #065f46; }
  .result-badge.wrong { background: #fee2e2; color: #991b1b; }
  .result-q-stem {
    font-size: 14px;
    color: #333;
    line-height: 1.7;
    margin: 0 0 12px;
  }
  .result-options {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
  }
  .result-option {
    display: flex;
    gap: 10px;
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 13px;
  }
  .result-option.correct { background: #f0fdf4; border: 1px solid #6ee7b7; }
  .result-option.wrong { background: #fef2f2; border: 1px solid #fca5a5; }
  .result-user-answer, .result-correct-answer, .result-analysis {
    font-size: 13px;
    margin-bottom: 6px;
    color: #5a6488;
  }
  .correct-answer-text { color: #16a34a; font-weight: 600; }
  .result-actions {
    display: flex;
    gap: 16px;
    justify-content: center;
    padding: 16px 28px;
    background: #fff;
    border-top: 1px solid #e8eaf0;
  }
  .result-btn {
    padding: 10px 40px;
    border: none;
    border-radius: 10px;
    cursor: pointer;
    font-size: 15px;
    font-weight: 600;
    transition: all 0.2s;
  }
  .continue-btn {
    background: linear-gradient(135deg, #c41e3a, #dc2626);
    color: #fff;
  }
  .continue-btn:hover { background: linear-gradient(135deg, #b91c1c, #c41e3a); }
  .close-btn {
    background: #e8eaf0;
    color: #1a2b5f;
  }
  .close-btn:hover { background: #cbd5e0; }
</style>