<!-- 答题练习页面（含答题卡、收藏/笔记/标记） -->
<template>
  <div class="exercise-page">
    <!-- 顶部导航栏 -->
    <div class="ex-header">
      <button class="ex-back-btn" @click="handleBack">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
        <span>返回题库</span>
      </button>
      <div class="ex-title">
        <span class="ex-subject-tag">{{ subjectLabel }}</span>
        <span class="ex-subcat-name">{{ subcategory }}</span>
      </div>
      <div class="ex-header-right">
        <!-- 答题卡按钮 -->
        <button class="ex-answer-sheet-btn" @click="toggleAnswerSheet" title="答题卡">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
          <span>答题卡</span>
        </button>
        <div class="ex-timer" v-if="state.questions.length">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8899aa" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
          <span>{{ formattedTime }}</span>
        </div>
      </div>
    </div>

    <!-- 加载/空状态 -->
    <div class="ex-loading" v-if="state.loading">
      <div class="loading-spinner"></div>
      <span>正在加载题目...</span>
    </div>
    <div class="ex-empty" v-else-if="!state.questions.length && !state.loading">
      <div class="empty-icon">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#c41e3a" stroke-width="1" opacity="0.4"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
      </div>
      <h3>暂无题目</h3>
      <p>该分类下没有可练习的题目，请先去题库导入</p>
      <button class="btn-ex-primary" @click="handleBack">返回题库</button>
    </div>

    <!-- 答题区域 -->
    <template v-if="state.questions.length && !state.loading && state.currentIndex < state.questions.length">
      <!-- 进度条 -->
      <div class="ex-progress-bar">
        <div class="progress-fill" :style="{ width: ((state.currentIndex / state.questions.length) * 100) + '%' }"></div>
      </div>
      <div class="ex-progress-label">
        第 {{ state.currentIndex + 1 }} / {{ state.questions.length }} 题
      </div>

      <!-- 题目卡片 -->
      <div class="ex-question-card">
        <div class="ex-q-header">
          <span class="ex-q-num">第 {{ state.currentIndex + 1 }} 题</span>
          <span class="ex-q-type-badge" :class="getTypeBadgeClass(currentQ)" v-if="currentQ.question_type_detail">
            {{ getTypeBadgeLabel(currentQ.question_type_detail) }}
          </span>
          <span class="ex-q-difficulty" v-if="currentQ.difficulty">
            难度：{{ getDifficultyLabel(currentQ.difficulty) }}
          </span>
          <!-- 操作按钮组 -->
          <div class="ex-q-actions">
            <button
              class="ex-action-btn"
              :class="{ 'action-active': currentActions.favorited }"
              @click="toggleFavorite"
              :title="currentActions.favorited ? '取消收藏' : '收藏'"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" :fill="currentActions.favorited ? '#f5a623' : 'none'" :stroke="currentActions.favorited ? '#f5a623' : '#8899aa'" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
              <span>{{ currentActions.favorited ? '已收藏' : '收藏' }}</span>
            </button>
            <button
              class="ex-action-btn"
              :class="{ 'action-active': currentActions.hasNote }"
              @click="openNoteEditor"
              title="笔记"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" :stroke="currentActions.hasNote ? '#4a90d9' : '#8899aa'" stroke-width="2" stroke-linecap="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
              <span>{{ currentActions.hasNote ? '已笔记' : '笔记' }}</span>
            </button>
            <button
              class="ex-action-btn"
              :class="{ 'action-active': currentActions.hasMarker }"
              @click="openMarkerPopup"
              title="标记"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" :fill="currentActions.hasMarker ? '#e8384f' : 'none'" :stroke="currentActions.hasMarker ? '#e8384f' : '#8899aa'" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>
              <span>{{ currentActions.markerLabel || '标记' }}</span>
            </button>
          </div>
        </div>
        <!-- B4: 复合题材料（可折叠，仅 group_id>0 时显示） -->
        <div v-if="currentQ.group_id" class="ex-group-material">
          <button class="ex-material-toggle" @click="state.materialExpanded = !state.materialExpanded">
            <span>📑 题组材料</span>
            <span class="material-arrow">{{ state.materialExpanded ? '▲' : '▼' }}</span>
          </button>
          <div v-show="state.materialExpanded" class="ex-material-body" v-html="renderContent(state.groupMaterial)"></div>
        </div>
        <div class="ex-q-content" v-html="renderContent(currentQ.question_content)"></div>

        <!-- P1-6: 主观题作答区（无选项，纯文本作答） -->
        <div v-if="currentQ.is_subjective" class="ex-subjective">
          <div class="ex-subjective-meta" v-if="hasSubjectiveMeta">
            <span v-if="currentQ.score !== null && currentQ.score !== undefined && currentQ.score !== ''" class="ex-subjective-score">
              分值：{{ currentQ.score }} 分
            </span>
            <span v-if="currentQ.requirements" class="ex-subjective-req">
              <strong>作答要求：</strong>
              <span v-html="renderContent(currentQ.requirements)"></span>
            </span>
          </div>
          <textarea
            v-model="subjectiveAnswer"
            class="ex-subjective-input"
            rows="10"
            placeholder="请在此作答..."
          ></textarea>
          <div class="ex-subjective-count">已写 {{ subjectiveWordCount }} 字</div>
        </div>

        <!-- 选项（主观题不渲染选项） -->
        <div class="ex-options" v-if="!currentQ.is_subjective">
          <label
            v-if="isMultiSelect(currentQ)"
            class="ex-option"
            :class="{ 'opt-selected': isMultiOptSelected(opt.key) }"
            v-for="opt in parsedOptions"
            :key="opt.key"
          >
            <input type="checkbox" :value="opt.key" v-model="multiAnswers" class="ex-checkbox" />
            <span class="opt-key">{{ opt.key }}</span>
            <span class="opt-value" v-html="renderContent(opt.value)"></span>
          </label>
          <div
            v-else
            class="ex-option"
            :class="{ 'opt-selected': state.userAnswers[state.currentIndex] === opt.key }"
            v-for="opt in parsedOptions"
            :key="opt.key"
            @click="selectAnswer(opt.key)"
          >
            <span class="opt-key">{{ opt.key }}</span>
            <span class="opt-value" v-html="renderContent(opt.value)"></span>
          </div>
        </div>
      </div>

      <!-- 底部操作栏 -->
      <div class="ex-actions">
        <button class="btn-ex-outline" :disabled="state.currentIndex === 0" @click="prevQuestion">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="15 18 9 12 15 6"></polyline></svg>
          上一题
        </button>
        <div class="ex-dot-nav">
          <span
            v-for="(_, idx) in state.questions"
            :key="idx"
            class="dot"
            :class="{ 'dot-active': idx === state.currentIndex, 'dot-done': state.userAnswers[idx] }"
            @click="state.currentIndex = idx"
          ></span>
        </div>
        <button v-if="state.currentIndex < state.questions.length - 1" class="btn-ex-primary" @click="nextQuestion">
          下一题
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"></polyline></svg>
        </button>
        <button v-else class="btn-ex-submit" @click="handleSubmit">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
          交卷
        </button>
      </div>
    </template>

    <!-- ========== 答题卡弹窗 ========== -->
    <div class="ex-sheet-overlay" v-if="state.showAnswerSheet" @click.self="toggleAnswerSheet">
      <div class="ex-sheet-panel">
        <div class="ex-sheet-header">
          <h3>答题卡</h3>
          <div class="ex-sheet-stats">
            <span class="stat-item">已答 <b>{{ answeredCount }}</b></span>
            <span class="stat-item">未答 <b>{{ unansweredCount }}</b></span>
            <span class="stat-item">收藏 <b>{{ favoritedCount }}</b></span>
            <span class="stat-item">标记 <b>{{ markedCount }}</b></span>
          </div>
          <button class="ex-sheet-close" @click="toggleAnswerSheet">&times;</button>
        </div>
        <div class="ex-sheet-grid">
          <div
            v-for="(q, idx) in state.questions"
            :key="idx"
            class="ex-sheet-cell"
            :class="{
              'cell-current': idx === state.currentIndex,
              'cell-answered': state.userAnswers[idx],
              'cell-fav': (state.questionActions[q.question_id] || {}).favorited,
              'cell-marked': (state.questionActions[q.question_id] || {}).hasMarker
            }"
            @click="jumpToQuestion(idx)"
          >
            <span class="cell-num">{{ idx + 1 }}</span>
            <span class="cell-ans" v-if="state.userAnswers[idx]">{{ state.userAnswers[idx] }}</span>
            <span class="cell-dot" v-else>·</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ========== 笔记编辑弹窗 ========== -->
    <div class="ex-sheet-overlay" v-if="state.showNoteEditor" @click.self="closeNoteEditor">
      <div class="ex-note-panel">
        <div class="ex-sheet-header">
          <h3>题目笔记</h3>
          <button class="ex-sheet-close" @click="closeNoteEditor">&times;</button>
        </div>
        <textarea
          class="ex-note-textarea"
          v-model="state.noteText"
          placeholder="记录你的解题思路、易错点..."
          rows="6"
        ></textarea>
        <div class="ex-note-actions">
          <button class="btn-ex-outline" v-if="currentActions.hasNote" @click="deleteNote">删除笔记</button>
          <button class="btn-ex-primary" @click="saveNote">保存笔记</button>
        </div>
      </div>
    </div>

    <!-- ========== 标记类型选择弹窗 ========== -->
    <div class="ex-sheet-overlay" v-if="state.showMarkerPopup" @click.self="closeMarkerPopup">
      <div class="ex-marker-panel">
        <div class="ex-sheet-header">
          <h3>选择标记类型</h3>
          <button class="ex-sheet-close" @click="closeMarkerPopup">&times;</button>
        </div>
        <div class="ex-marker-grid">
          <button
            v-for="mt in markerTypes"
            :key="mt.value"
            class="ex-marker-option"
            :class="{ 'marker-active': currentActions.markerType === mt.value }"
            @click="setMarker(mt.value, mt.label)"
          >
            <span class="marker-icon">{{ mt.icon }}</span>
            <span class="marker-label">{{ mt.label }}</span>
          </button>
        </div>
        <button v-if="currentActions.hasMarker" class="btn-ex-outline marker-remove" @click="removeMarker">取消标记</button>
      </div>
    </div>
  </div>
</template>

<script>
import { defineComponent, reactive, computed, watch } from 'vue';
import { sanitizeHtml } from '@/utils/questionRender';

var apiBase = '/api/questions';

export default defineComponent({
  name: 'ExercisePage',
  setup() {
    var state = reactive({
      questions: [],
      currentIndex: 0,
      userAnswers: {},
      loading: true,
      seconds: 0,
      timerInterval: null,
      // 答题卡
      showAnswerSheet: false,
      // 操作状态: { question_id: { favorited, hasNote, hasMarker, markerType, markerLabel } }
      questionActions: {},
      // 笔记编辑
      showNoteEditor: false,
      noteText: '',
      // 标记选择
      showMarkerPopup: false,
      // B4: 复合题材料（可折叠）
      materialExpanded: true,
      groupMaterial: '',       // 当前题组共享材料（HTML）
      _groupCache: {},         // group_id → 材料（会话内缓存）
    });

    var markerTypes = [
      { value: 'important', label: '重要', icon: '⭐' },
      { value: 'difficult', label: '难题', icon: '🔴' },
      { value: 'confusing', label: '易混', icon: '🔄' },
      { value: 'tricky', label: '陷阱', icon: '⚠️' },
      { value: 'frequent', label: '高频', icon: '🔥' },
    ];

    return { state, markerTypes };
  },
  computed: {
    subjectLabel() {
      var m = { xc: '行测', sl: '申论', ga: '公专' };
      return m[this.$route.query.subject] || '练习';
    },
    subcategory() {
      // 优先显示考点名称（快速练习三级分类）
      var kpName = this.$route.query.kpName;
      if (kpName) return decodeURIComponent(kpName);
      return this.$route.query.subcategory || '';
    },
    currentQ() {
      return this.state.questions[this.state.currentIndex] || {};
    },
    // 多选答案数组(自动同步checkbox v-model)
    multiAnswers: {
      get() {
        var ans = this.state.userAnswers[this.state.currentIndex];
        return Array.isArray(ans) ? ans : (ans ? [ans] : []);
      },
      set(val) {
        this.state.userAnswers[this.state.currentIndex] = val;
      }
    },
    // P1-6: 主观题作答文本（存于 userAnswers，与客观题同一容器，切题自动保留）
    subjectiveAnswer: {
      get() {
        var ans = this.state.userAnswers[this.state.currentIndex];
        return typeof ans === 'string' ? ans : '';
      },
      set(val) {
        this.state.userAnswers[this.state.currentIndex] = val;
      }
    },
    // 字数统计：非空白字符数
    subjectiveWordCount() {
      return (this.subjectiveAnswer || '').replace(/\s/g, '').length;
    },
    hasSubjectiveMeta() {
      var q = this.currentQ || {};
      var hasScore = q.score !== null && q.score !== undefined && q.score !== '';
      return !!(hasScore || q.requirements);
    },
    parsedOptions() {
      // P1-6: 主观题没有选项，直接返回空数组，避免补全 A-D「待补充」
      if (this.currentQ.is_subjective) return [];
      var raw = this.currentQ.options;
      var opts = [];

      // 防御1: 如果是JSON字符串，先parse
      if (typeof raw === 'string') {
        try { raw = JSON.parse(raw); } catch(e) { raw = []; }
      }
      if (!Array.isArray(raw)) raw = [];

      // 防御2: 遍历，将各种格式统一为 {key, value}
      var labels = ['A', 'B', 'C', 'D'];
      for (var i = 0; i < raw.length; i++) {
        var item = raw[i];
        if (item && typeof item === 'object' && !Array.isArray(item)) {
          // 对象格式: {key: "A", value: "xxx"} 或 {label: "A", text: "xxx"}
          var k = (item.key || item.label || '').toString().toUpperCase();
          var v = item.value || item.text || '';
          if (typeof v === 'object') { v = JSON.stringify(v); }
          if (k && labels.indexOf(k) >= 0) {
            opts.push({ key: k, value: String(v) });
          }
        } else if (typeof item === 'string') {
          // 字符串格式: "A. xxx" 或纯文本
          var m = item.match(/^([A-D])[.\、\s]+(.+)/);
          if (m) {
            opts.push({ key: m[1], value: m[2] });
          }
        }
      }

      // 防御3: 补全缺失的A/B/C/D
      var existing = {};
      for (var j = 0; j < opts.length; j++) {
        existing[opts[j].key] = true;
      }
      for (var n = 0; n < labels.length; n++) {
        if (!existing[labels[n]]) {
          opts.push({ key: labels[n], value: '(待补充)' });
        }
      }

      // 只保留A-D，排序
      opts = opts.filter(function(o) { return labels.indexOf(o.key) >= 0; });
      opts.sort(function(a, b) { return a.key.localeCompare(b.key); });
      return opts;
    },
    formattedTime() {
      var m = Math.floor(this.state.seconds / 60);
      var s = this.state.seconds % 60;
      return (m < 10 ? '0' + m : m) + ':' + (s < 10 ? '0' + s : s);
    },
    currentActions() {
      var qid = this.currentQ.question_id;
      return this.state.questionActions[qid] || { favorited: false, hasNote: false, hasMarker: false, markerType: '', markerLabel: '' };
    },
    answeredCount() {
      var questions = this.state.questions;
      var cnt = 0;
      for (var i = 0; i < questions.length; i++) {
        if (this.state.userAnswers[i]) cnt++;
      }
      return cnt;
    },
    unansweredCount() {
      return this.state.questions.length - this.answeredCount;
    },
    favoritedCount() {
      var actions = this.state.questionActions;
      var cnt = 0;
      var questions = this.state.questions;
      for (var i = 0; i < questions.length; i++) {
        var act = actions[questions[i].question_id];
        if (act && act.favorited) cnt++;
      }
      return cnt;
    },
    markedCount() {
      var actions = this.state.questionActions;
      var cnt = 0;
      var questions = this.state.questions;
      for (var i = 0; i < questions.length; i++) {
        var act = actions[questions[i].question_id];
        if (act && act.hasMarker) cnt++;
      }
      return cnt;
    },
  },
  watch: {
    currentQ: function() {
      this.loadQuestionActions();
      this.ensureGroupMaterial();
    }
  },
  mounted() {
    this.loadQuestions();
  },
  beforeUnmount() {
    if (this.state.timerInterval) clearInterval(this.state.timerInterval);
  },
  methods: {
    // === B4: 复合题材料加载（会话内缓存，切题不重复请求） ===
    ensureGroupMaterial() {
      var q = this.currentQ || {};
      var gid = q.group_id;
      if (!gid) {
        this.state.groupMaterial = '';
        return;
      }
      if (this.state._groupCache[gid]) {
        this.state.groupMaterial = this.state._groupCache[gid];
        return;
      }
      var self = this;
      fetch('/api/questions/group/' + gid)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data && data.group) {
            var html = data.group.shared_content || '';
            self.state._groupCache[gid] = html;
            // 仅当用户仍停留在此题组时更新（防竞态）
            if ((self.currentQ || {}).group_id === gid) {
              self.state.groupMaterial = html;
            }
          }
        })
        .catch(function (e) { console.error('题组材料加载失败:', e); });
    },

    // === 题型判定 ===
    isMultiSelect(q) {
      var t = (q.question_type_detail || '').toLowerCase();
      return t.indexOf('多选') >= 0 || t.indexOf('不定项') >= 0;
    },
    isMultiOptSelected(key) {
      var ans = this.state.userAnswers[this.state.currentIndex];
      if (Array.isArray(ans)) return ans.indexOf(key) >= 0;
      return ans === key;
    },
    getTypeBadgeLabel(type) {
      if (!type) return '';
      var t = type.toString();
      if (t.indexOf('多选') >= 0 || t.indexOf('不定项') >= 0) return '[多选]';
      if (t.indexOf('单选') >= 0 || t.indexOf('选择') >= 0) return '[单选]';
      if (t.indexOf('论述') >= 0 || t.indexOf('论证') >= 0) return '[论述]';
      if (t.indexOf('写作') >= 0 || t.indexOf('作文') >= 0 || t.indexOf('应用文') >= 0) return '[写作]';
      if (t.indexOf('案例') >= 0) return '[案例]';
      if (t.indexOf('简答') >= 0) return '[简答]';
      return '[单选]';
    },
    getTypeBadgeClass(q) {
      var t = (q.question_type_detail || '').toString();
      if (t.indexOf('多选') >= 0 || t.indexOf('不定项') >= 0) return 'type-multi';
      if (t.indexOf('论述') >= 0 || t.indexOf('论证') >= 0) return 'type-discuss';
      if (t.indexOf('写作') >= 0 || t.indexOf('作文') >= 0 || t.indexOf('应用文') >= 0) return 'type-writing';
      if (t.indexOf('案例') >= 0) return 'type-case';
      if (t.indexOf('简答') >= 0) return 'type-essay';
      return 'type-single';
    },
    // === 内容渲染（第9层防线：前端智能重试） ===
    renderContent(text) {
      if (!text) return '';
      // 先白名单清洗服务端内容，再做占位符转换。
      // 顺序很关键：清洗会剥掉内联 onerror，而本页面自建的 <img> 需要保留
      // onerror="window.__retryImg(...)" 以实现多级重试，因此必须「先清洗、后转换」。
      var html = sanitizeHtml(text);
      // 支持 uuid_x_y 和 x_y 两种 IMAGE 占位符格式
      html = html.replace(/\[?IMAGE:([a-f0-9]+_\d+_\d+|\d+_\d+)\]?/gi, function(match, marker) {
        // 初始 src 使用扁平路径，onerror 调用全局 __retryImg 智能重试
        return '<img src="/static/questions/' + marker + '.png" class="q-img" loading="lazy" ' +
               'data-marker="' + marker + '" onerror="window.__retryImg && window.__retryImg(this)" />';
      });
      return html;
    },
    getDifficultyLabel(d) {
      var labels = ['', '★', '★★', '★★★', '★★★★', '★★★★★'];
      return labels[d] || '★★★';
    },

    getFetch() {
      return (window.__VTJ_AUTH__ && window.__VTJ_AUTH__.apiFetch)
        ? window.__VTJ_AUTH__.apiFetch
        : function(url, opts) { return fetch(url, opts); };
    },

    // 前端兜底去重：移除题干内容高度相似的题目（>80%相似度）
    dedupQuestions(questions) {
      if (!questions || questions.length <= 1) return questions || [];
      var seen = [];
      var result = [];
      for (var i = 0; i < questions.length; i++) {
        var q = questions[i];
        var content = q.question_content || q.title || '';
        if (!content.trim()) {
          result.push(q);
          continue;
        }
        // 标准化：去除HTML标签和空白
        var norm = content.replace(/<[^>]+>/g, '').replace(/\s+/g, '').substring(0, 200);
        if (norm.length < 5) {
          result.push(q);
          continue;
        }
        var isDup = false;
        for (var j = 0; j < seen.length; j++) {
          var existNorm = seen[j];
          // 快速长度检查
          var lenRatio = Math.min(norm.length, existNorm.length) / Math.max(norm.length, existNorm.length);
          if (lenRatio < 0.5) continue;
          // 简单相似度：公共字符比例
          var common = 0;
          var shorter = norm.length < existNorm.length ? norm : existNorm;
          var longer = norm.length < existNorm.length ? existNorm : norm;
          for (var k = 0; k < shorter.length; k++) {
            if (longer.indexOf(shorter[k]) >= 0) common++;
          }
          var similarity = common / Math.max(norm.length, existNorm.length);
          if (similarity > 0.8) {
            isDup = true;
            break;
          }
        }
        if (!isDup) {
          seen.push(norm);
          result.push(q);
        }
      }
      return result;
    },

    async loadQuestions() {
      var self = this;
      self.state.loading = true;
      try {
        // === 认证守卫 ===
        if (window.__VTJ_AUTH__ && window.__VTJ_AUTH__.ensureAuth) {
          var isAuthed = await window.__VTJ_AUTH__.ensureAuth();
          if (!isAuthed) {
            self.state.loading = false;
            window.location.href = '/#/login';
            return;
          }
        }
        var subject = self.$route.query.subject || 'xc';
        var kpId = self.$route.query.kpId || '';
        var scId = self.$route.query.scId || '';
        var count = parseInt(self.$route.query.count || '20', 10);
        var yearRange = self.$route.query.yearRange || '';

        var url;
        if (kpId) {
          // 通过考点ID加载题目（快速练习三级分类）
          url = '/api/quick-practice/questions?knowledge_point_ids=' + kpId + '&limit=' + count;
          if (yearRange && yearRange !== '0') {
            url += '&year=' + yearRange;
          }
        } else if (scId) {
          // 通过子科目ID加载题目（自定义刷题）
          url = '/api/quick-practice/questions?knowledge_point_ids=' + scId + '&limit=' + count + '&bySubCategory=true';
          if (yearRange && yearRange !== '0') {
            url += '&year=' + yearRange;
          }
        } else {
          // 回退到旧版API
          var subcategory = self.$route.query.subcategory || '';
          url = '/api/questions/exercise/questions?subject=' + subject +
            '&subcategory=' + encodeURIComponent(subcategory) + '&count=' + count;
        }

        var fetchFn = self.getFetch();
        var res = await fetchFn(url, { headers: { 'Content-Type': 'application/json' } });
        if (!res.ok) return;
        var data = await res.json();
        if (data && data.items && data.items.length) {
          // 新API格式 (quick-practice) — 前端兜底去重
          self.state.questions = self.dedupQuestions(data.items);
          self.state.currentIndex = 0;
          self.state.userAnswers = {};
          self.state.questionActions = {};
          self.state.timerInterval = setInterval(function() {
            self.state.seconds++;
          }, 1000);
          self.loadQuestionActions();
        } else if (data && data.questions && data.questions.length) {
          // 旧API格式 — 前端兜底去重
          self.state.questions = self.dedupQuestions(data.questions);
          self.state.currentIndex = 0;
          self.state.userAnswers = {};
          self.state.questionActions = {};
          self.state.timerInterval = setInterval(function() {
            self.state.seconds++;
          }, 1000);
          self.loadQuestionActions();
        } else {
          self.state.questions = [];
        }
      } catch (e) {
        console.warn('加载题目失败:', e);
      } finally {
        self.state.loading = false;
      }
    },

    async loadQuestionActions() {
      var qid = this.currentQ.question_id;
      if (!qid) return;
      // 如果已加载过则跳过
      if (this.state.questionActions[qid]) return;
      try {
        var fetchFn = this.getFetch();
        var res = await fetchFn(apiBase + '/' + qid + '/actions', {
          headers: { 'Content-Type': 'application/json' }
        });
        if (!res.ok) return;
        var data = await res.json();
        this.state.questionActions[qid] = {
          favorited: data.favorited || false,
          hasNote: data.note ? data.note.has_note : false,
          noteText: data.note ? data.note.note_text : '',
          hasMarker: data.marker ? data.marker.has_marker : false,
          markerType: data.marker ? data.marker.marker_type : '',
          markerLabel: data.marker ? data.marker.marker_label : '',
        };
      } catch (e) {
        console.warn('加载操作状态失败:', e);
      }
    },

    selectAnswer(key) {
      // 多选题由v-model数组自动管理，单选直接赋值
      var q = this.currentQ;
      if (this.isMultiSelect(q)) {
        var ans = this.state.userAnswers[this.state.currentIndex] || [];
        if (!Array.isArray(ans)) ans = [];
        var idx = ans.indexOf(key);
        if (idx >= 0) { ans.splice(idx, 1); }
        else { ans.push(key); }
        this.state.userAnswers[this.state.currentIndex] = ans;
      } else {
        this.state.userAnswers[this.state.currentIndex] = key;
      }
    },
    prevQuestion() {
      if (this.state.currentIndex > 0) this.state.currentIndex--;
    },
    nextQuestion() {
      if (this.state.currentIndex < this.state.questions.length - 1) {
        this.state.currentIndex++;
      }
    },

    // ========== 答题卡 ==========
    toggleAnswerSheet() {
      this.state.showAnswerSheet = !this.state.showAnswerSheet;
    },
    jumpToQuestion(idx) {
      this.state.currentIndex = idx;
      this.state.showAnswerSheet = false;
    },

    // ========== 收藏 ==========
    async toggleFavorite() {
      var qid = this.currentQ.question_id;
      if (!qid) return;
      try {
        var fetchFn = this.getFetch();
        var res = await fetchFn(apiBase + '/' + qid + '/favorite', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        if (!res.ok) return;
        var data = await res.json();
        // 更新本地状态
        if (!this.state.questionActions[qid]) {
          this.state.questionActions[qid] = { favorited: false, hasNote: false, hasMarker: false, markerType: '', markerLabel: '' };
        }
        this.state.questionActions[qid].favorited = data.favorited;
      } catch (e) {
        console.warn('收藏操作失败:', e);
      }
    },

    // ========== 笔记 ==========
    openNoteEditor() {
      var qid = this.currentQ.question_id;
      var act = this.state.questionActions[qid] || {};
      this.state.showNoteEditor = true;
      this.state.noteText = act.noteText || '';
    },
    closeNoteEditor() {
      this.state.showNoteEditor = false;
      this.state.noteText = '';
    },
    async saveNote() {
      var qid = this.currentQ.question_id;
      if (!qid || !this.state.noteText.trim()) return;
      try {
        var fetchFn = this.getFetch();
        var res = await fetchFn(apiBase + '/' + qid + '/note', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ note_text: this.state.noteText.trim() })
        });
        if (!res.ok) return;
        if (!this.state.questionActions[qid]) {
          this.state.questionActions[qid] = { favorited: false, hasNote: false, hasMarker: false, markerType: '', markerLabel: '' };
        }
        this.state.questionActions[qid].hasNote = true;
        this.state.questionActions[qid].noteText = this.state.noteText.trim();
        this.state.showNoteEditor = false;
        this.state.noteText = '';
      } catch (e) {
        console.warn('保存笔记失败:', e);
      }
    },
    async deleteNote() {
      var qid = this.currentQ.question_id;
      if (!qid) return;
      try {
        var fetchFn = this.getFetch();
        var res = await fetchFn(apiBase + '/' + qid + '/note', {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' }
        });
        if (!res.ok) return;
        if (this.state.questionActions[qid]) {
          this.state.questionActions[qid].hasNote = false;
          this.state.questionActions[qid].noteText = '';
        }
        this.state.showNoteEditor = false;
        this.state.noteText = '';
      } catch (e) {
        console.warn('删除笔记失败:', e);
      }
    },

    // ========== 标记 ==========
    openMarkerPopup() {
      this.state.showMarkerPopup = true;
    },
    closeMarkerPopup() {
      this.state.showMarkerPopup = false;
    },
    async setMarker(type, label) {
      var qid = this.currentQ.question_id;
      if (!qid) return;
      try {
        var fetchFn = this.getFetch();
        var res = await fetchFn(apiBase + '/' + qid + '/marker', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ marker_type: type, marker_label: label })
        });
        if (!res.ok) return;
        if (!this.state.questionActions[qid]) {
          this.state.questionActions[qid] = { favorited: false, hasNote: false, hasMarker: false, markerType: '', markerLabel: '' };
        }
        this.state.questionActions[qid].hasMarker = true;
        this.state.questionActions[qid].markerType = type;
        this.state.questionActions[qid].markerLabel = label;
        this.state.showMarkerPopup = false;
      } catch (e) {
        console.warn('设置标记失败:', e);
      }
    },
    async removeMarker() {
      var qid = this.currentQ.question_id;
      if (!qid) return;
      try {
        var fetchFn = this.getFetch();
        var res = await fetchFn(apiBase + '/' + qid + '/marker', {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' }
        });
        if (!res.ok) return;
        if (this.state.questionActions[qid]) {
          this.state.questionActions[qid].hasMarker = false;
          this.state.questionActions[qid].markerType = '';
          this.state.questionActions[qid].markerLabel = '';
        }
        this.state.showMarkerPopup = false;
      } catch (e) {
        console.warn('取消标记失败:', e);
      }
    },

    collectWrongAnswers(details) {
      // 对答错的题目异步收录到错题集 (fire-and-forget)
      var self = this;
      var subjectMap = { xc: 1, sl: 2, ga: 3 };
      var routeSubject = self.$route.query.subject || 'xc';
      var subjectId = subjectMap[routeSubject] || null;

      details.forEach(function(d) {
        // P1-6: 主观题不自动判分（is_correct=null），不收录为错题
        if (d.is_correct === false && d.question_id) {
          var fetchFn = self.getFetch();
          fetchFn('/api/wrong-questions/collect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              question_id: d.question_id,
              subject_id: subjectId,
              is_correct: false
            })
          }).catch(function() { /* 静默 — 后端practice.py已做兜底收录 */ });
        }
      });
    },

    async submitPracticeRecords(details) {
      try {
        var self = this;
        var fetchFn = this.getFetch();
        // 从路由参数映射 subject_id
        var subjectMap = { xc: 1, sl: 2, ga: 3 };
        var routeSubject = self.$route.query.subject || 'xc';
        var subjectId = subjectMap[routeSubject] || null;

        var records = details.map(function(d) {
          return {
            question_id: d.question_id,
            subject_id: subjectId,
            is_correct: d.is_correct,
            user_answer: d.user_answer,
            time_spent: Math.round((self.state.seconds || 0) / (self.state.questions.length || 1)),
            source: '快速练习'
          };
        });

        var res = await fetchFn('/api/practice/batch-record', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ records: records })
        });

        if (!res.ok) {
          var errText = '';
          try { var errData = await res.json(); errText = errData.detail || errData.message || ''; } catch(e) {}
          return { success: false, error: '提交失败(HTTP ' + res.status + '): ' + (errText || '请检查网络连接') };
        }
        var data = await res.json();
        console.log('练习记录提交成功: ' + data.count + ' 条');
        return { success: true, count: data.count };
      } catch (e) {
        console.warn('提交练习记录失败:', e);
        return { success: false, error: '网络连接失败，请检查网络后重试' };
      }
    },

    async handleSubmit() {
      var unanswered = 0;
      var questions = this.state.questions;
      for (var i = 0; i < questions.length; i++) {
        var ans = this.state.userAnswers[i];
        if (questions[i].is_subjective) {
          if (!ans || !String(ans).trim()) unanswered++;
        } else if (!ans) {
          unanswered++;
        }
      }
      if (unanswered > 0) {
        if (!confirm('还有 ' + unanswered + ' 道题未作答，确定交卷吗？')) return;
      }
      var correct = 0;
      var wrong = 0;
      var objectiveTotal = 0;
      var details = [];
      for (var j = 0; j < questions.length; j++) {
        var q = questions[j];
        var rawAns = this.state.userAnswers[j];
        // P1-6: 主观题不自动判分，不计入正确/错误，也不进错题集
        if (q.is_subjective) {
          var text = typeof rawAns === 'string' ? rawAns.trim() : '';
          details.push({
            question_id: q.question_id,
            question_content: q.question_content,
            options: [],
            user_answer: text || '未答',
            correct_answer: q.answer || '',
            is_correct: null,
            is_subjective: true,
            answer_analysis: q.answer_analysis || '',
            question_type_detail: q.question_type_detail || '主观题',
            difficulty: q.difficulty || 3,
          });
          continue;
        }
        objectiveTotal++;
        var userAns;
        if (Array.isArray(rawAns)) {
          userAns = rawAns.length ? rawAns.sort().join('') : '未答';
        } else {
          userAns = rawAns || '未答';
        }
        var correctAns = q.answer || '';
        // 多选题/数组答案：排序后比较字母串
        var isCorrect;
        if (Array.isArray(rawAns) && correctAns.length > 1) {
          var sortedUser = rawAns.slice().sort().join('');
          var sortedCorrect = correctAns.split('').sort().join('');
          isCorrect = sortedUser === sortedCorrect;
        } else {
          isCorrect = userAns === correctAns;
        }
        if (isCorrect) correct++; else wrong++;
        details.push({
          question_id: q.question_id,
          question_content: q.question_content,
          options: q.options,
          user_answer: userAns,
          correct_answer: correctAns,
          is_correct: isCorrect,
          is_subjective: false,
          answer_analysis: q.answer_analysis || '',
          question_type_detail: q.question_type_detail || '选择题',
          difficulty: q.difficulty || 3,
        });
      }
      // 得分分母只计客观题；全为主观题时记 0 分，避免除零
      var score = objectiveTotal ? Math.round((correct / objectiveTotal) * 100) : 0;
      var result = {
        total: questions.length,
        correct: correct,
        wrong: wrong,
        score: score,
        time: this.state.seconds,
        details: details,
        subject: this.$route.query.subject,
        subcategory: this.$route.query.subcategory,
      };
      sessionStorage.setItem('exercise_result', JSON.stringify(result));

      // 提交练习记录到后端 (await 确保完成后再跳转)
      var submitResult = await this.submitPracticeRecords(details);
      if (!submitResult.success) {
        alert('练习记录提交失败: ' + (submitResult.error || '未知错误') + '\n\n答题结果已保存，返回后可重试提交。');
      }

      // 自动收录错题（fire-and-forget，不阻塞跳转）
      this.collectWrongAnswers(details);

      if (this.state.timerInterval) clearInterval(this.state.timerInterval);
      this.$router.push('/solution');
    },
    handleBack() {
      if (this.state.timerInterval) clearInterval(this.state.timerInterval);
      this.$router.push('/');
    },
  },
});
</script>

 <style scoped>
.exercise-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  padding-bottom: 40px;
}
/* 顶部导航 */
.ex-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 32px;
  background: linear-gradient(135deg, #0a1628 0%, #12233f 30%, #1a2a4a 100%);
  border-bottom: 2px solid rgba(200,22,30,0.25);
  box-shadow: 0 2px 10px rgba(0,0,0,0.3);
}
.ex-back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 8px;
  color: #cfd8e3;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s;
}
.ex-back-btn:hover { background: rgba(200,22,30,0.15); color: #fff; }
.ex-title { display: flex; align-items: center; gap: 12px; }
.ex-subject-tag {
  background: rgba(200,22,30,0.2);
  color: #e8384f;
  padding: 4px 14px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 700;
}
.ex-subcat-name { color: #ffffff; font-size: 16px; font-weight: 600; }
.ex-header-right { display: flex; align-items: center; gap: 16px; }
/* 答题卡按钮 */
.ex-answer-sheet-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255,255,255,0.1);
  border: 1px solid rgba(255,255,255,0.15);
  border-radius: 8px;
  color: #cfd8e3;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s;
  font-weight: 500;
}
.ex-answer-sheet-btn:hover { background: rgba(200,22,30,0.2); color: #fff; border-color: rgba(200,22,30,0.4); }
.ex-timer {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #8899aa;
  font-size: 18px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
/* 加载 */
.ex-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px;
  color: #8899aa;
  gap: 16px;
}
.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(200,22,30,0.15);
  border-top: 3px solid #c41e3a;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.ex-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 80px 32px;
  text-align: center;
}
.ex-empty h3 { color: #1a2b5f; margin: 16px 0 8px; font-size: 20px; }
.ex-empty p { color: #8899aa; margin-bottom: 24px; }
/* 进度条 */
.ex-progress-bar {
  max-width: 1380px;
  margin: 20px auto 8px;
  height: 4px;
  background: rgba(200,22,30,0.08);
  border-radius: 2px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #c41e3a 0%, #e8384f 100%);
  border-radius: 2px;
  transition: width 0.4s ease;
}
.ex-progress-label {
  max-width: 1380px;
  margin: 0 auto 16px;
  text-align: center;
  font-size: 20px;
  color: #8899aa;
}
/* 题目卡片 */
.ex-question-card {
  max-width: 1380px;
  margin: 0 auto;
  background: #ffffff;
  border-radius: 16px;
  padding: 28px 32px;
  box-shadow: 0 2px 20px #1a2b5f0f;
  border: 1px solid rgba(26,43,95,0.06);
  border-left: 4px solid #c41e3a;
}
.ex-q-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid #f0f1f5;
  flex-wrap: wrap;
}
.ex-q-num {
  font-size: 16px;
  font-weight: 700;
  color: #c41e3a;
}
.ex-q-difficulty {
  font-size: 16px;
  color: #f5a623;
  letter-spacing: 2px;
}
/* 题型徽章 */
.ex-q-type-badge {
  font-size: 17px;
  padding: 4px 14px;
  border-radius: 8px;
  font-weight: 700;
  display: inline-block;
}
.type-single { background: #eff6ff; color: #3b82f6; }
.type-multi  { background: #fef3c7; color: #d97706; }
.type-discuss { background: #f5f3ff; color: #7c3aed; }
.type-writing { background: #ecfdf5; color: #059669; }
.type-case { background: #fef2f2; color: #dc2626; }
.type-essay { background: #f5f3ff; color: #7c3aed; }
/* 图片 */
.ex-q-content :deep(img.q-img),
.opt-value :deep(img.q-img) {
  max-width: 100%; max-height: 300px;
  display: block; margin: 10px auto; border-radius: 8px;
}
/* checkbox样式 */
.ex-checkbox {
  width: 18px; height: 18px;
  accent-color: #c41e3a; flex-shrink: 0;
  cursor: pointer;
}
/* 操作按钮组 */
.ex-q-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
}
.ex-action-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  color: #8899aa;
  padding: 6px 10px;
  font-size: 16px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}
.ex-action-btn:hover { background: rgba(26,43,95,0.04); border-color: #e0e4ec; color: #555876; }
.ex-action-btn.action-active {
  border-color: rgba(26,43,95,0.08);
  background: rgba(26,43,95,0.03);
}
.ex-group-material {
  margin-bottom: 16px;
  border: 1px solid #d8e3f3;
  border-radius: 8px;
  background: #f5f8fd;
  overflow: hidden
}
.ex-material-toggle {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #eaf1fb;
  border: none;
  cursor: pointer;
  font-size: 14px;
  color: #2c5aa0;
  font-weight: 600
}
.material-arrow { font-size: 12px }
.ex-material-body {
  padding: 12px 14px;
  font-size: 15px;
  line-height: 1.8;
  color: #33375a;
  word-break: break-word
}
.ex-q-content {
  font-size: 16px;
  line-height: 1.8;
  color: #33375a;
  margin-bottom: 24px;
  word-break: break-word;
}
/* 选项 */
.ex-options {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ex-option {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 14px 18px;
  border: 1.5px solid #e8ecf2;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.25s;
  background: #fafbfd;
}
.ex-option:hover { border-color: rgba(200,22,30,0.3); background: #fef5f6; }
.opt-selected {
  border-color: #c41e3a;
  background: linear-gradient(135deg, rgba(200,22,30,0.06) 0%, rgba(200,22,30,0.02) 100%);
  box-shadow: 0 0 0 3px rgba(200,22,30,0.12);
}
.opt-key {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(26,43,95,0.06);
  color: #1a2b5f;
  font-weight: 700;
  font-size: 14px;
  flex-shrink: 0;
  transition: all 0.25s;
}
.opt-selected .opt-key {
  background: #c41e3a;
  color: #ffffff;
}
.opt-value {
  font-size: 15px;
  color: #555876;
  line-height: 1.6;
  padding-top: 4px;
}
/* ===== P1-6: 主观题作答区 ===== */
.ex-subjective {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.ex-subjective-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 20px;
  padding: 10px 14px;
  background: #f8f9fc;
  border: 1px solid #e8ecf2;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.7;
  color: #555876;
  word-break: break-word;
}
.ex-subjective-score { color: #c41e3a; font-weight: 700; flex-shrink: 0; }
.ex-subjective-req { flex: 1; min-width: 200px; }
.ex-subjective-req strong { color: #1a2b5f; }
.ex-subjective-input {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  border: 1.5px solid #e8ecf2;
  border-radius: 12px;
  padding: 14px 16px;
  font-size: 15px;
  line-height: 1.8;
  color: #33375a;
  font-family: inherit;
  background: #fafbfd;
  outline: none;
  transition: border-color 0.2s, background 0.2s;
}
.ex-subjective-input:focus { border-color: #c41e3a; background: #ffffff; }
.ex-subjective-count { text-align: right; font-size: 13px; color: #8899aa; }
/* 底部操作 */
.ex-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
  max-width: 1380px;
  margin: 28px auto 0;
  padding: 20px 32px;
  background: #ffffff;
  border-radius: 16px;
  box-shadow: 0 2px 20px rgba(26,43,95,0.04);
  border: 1px solid rgba(26,43,95,0.04);
}
.btn-ex-outline {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 24px;
  border: 1.5px solid rgba(26,43,95,0.15);
  border-radius: 10px;
  background: transparent;
  color: #1a2b5f;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}
.btn-ex-outline:hover:not(:disabled) { background: rgba(26,43,95,0.04); border-color: rgba(26,43,95,0.3); }
.btn-ex-outline:disabled { opacity: 0.35; cursor: not-allowed; }
.btn-ex-primary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 12px 28px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #0a1628 0%, #1a2a4a 100%);
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}
.btn-ex-primary:hover { box-shadow: 0 4px 16px rgba(10,22,40,0.3); transform: translateY(-1px); }
.btn-ex-submit {
  display: flex;
  align-items: center;
  gap: 6px;
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
.btn-ex-submit:hover { box-shadow: 0 4px 16px rgba(200,22,30,0.4); transform: translateY(-1px); }
.ex-dot-nav {
  display: flex;
  gap: 6px;
  flex: 1;
  justify-content: center;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #e0e4ec;
  cursor: pointer;
  transition: all 0.3s;
}
.dot-done { background: #8899aa; }
.dot-active { background: #c41e3a; width: 28px; border-radius: 5px; }

/* ========== 弹窗通用 ========== */
.ex-sheet-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  animation: fadeIn 0.2s ease;
}
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

/* ========== 答题卡面板 ========== */
.ex-sheet-panel {
  background: #ffffff;
  border-radius: 16px;
  padding: 28px 32px;
  width: 480px;
  max-width: 90vw;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 8px 40px rgba(0,0,0,0.2);
  animation: slideUp 0.25s ease;
}
@keyframes slideUp { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
.ex-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f1f5;
}
.ex-sheet-header h3 { font-size: 18px; color: #1a2b5f; margin: 0; }
.ex-sheet-close {
  background: none; border: none;
  font-size: 24px; color: #8899aa;
  cursor: pointer; padding: 0 4px;
  line-height: 1;
}
.ex-sheet-close:hover { color: #c41e3a; }
.ex-sheet-stats {
  display: flex;
  gap: 16px;
  margin-left: 16px;
}
.stat-item {
  font-size: 12px;
  color: #8899aa;
  background: #f8f9fc;
  padding: 4px 10px;
  border-radius: 6px;
}
.stat-item b { color: #1a2b5f; margin-left: 2px; }
/* 答题卡网格 */
.ex-sheet-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 10px;
}
.ex-sheet-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 10px 4px;
  border-radius: 10px;
  background: #f8f9fc;
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
  min-height: 52px;
}
.ex-sheet-cell:hover { border-color: #c41e3a; background: #fef5f6; }
.cell-current { border-color: #c41e3a; background: rgba(200,22,30,0.06); box-shadow: 0 0 0 2px rgba(200,22,30,0.15); }
.cell-answered { background: #e8f5e9; border-color: #a5d6a7; }
.cell-answered.cell-current { border-color: #c41e3a; background: rgba(200,22,30,0.06); }
.cell-fav::after {
  content: '★';
  position: absolute;
  top: 1px;
  right: 4px;
  font-size: 8px;
  color: #f5a623;
}
.cell-marked::before {
  content: '';
  position: absolute;
  top: 3px;
  left: 4px;
  width: 6px;
  height: 6px;
  background: #e8384f;
  border-radius: 50%;
}
.cell-num {
  font-size: 14px;
  font-weight: 700;
  color: #1a2b5f;
}
.cell-ans {
  font-size: 12px;
  color: #43a047;
  font-weight: 600;
  margin-top: 2px;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cell-dot { color: #ccc; font-size: 12px; }

/* ========== 笔记面板 ========== */
.ex-note-panel {
  background: #ffffff;
  border-radius: 16px;
  padding: 28px 32px;
  width: 500px;
  max-width: 90vw;
  box-shadow: 0 8px 40px rgba(0,0,0,0.2);
  animation: slideUp 0.25s ease;
}
.ex-note-textarea {
  width: 100%;
  border: 1.5px solid #e8ecf2;
  border-radius: 10px;
  padding: 14px 16px;
  font-size: 14px;
  line-height: 1.7;
  color: #33375a;
  resize: vertical;
  font-family: inherit;
  outline: none;
  transition: border-color 0.2s;
  box-sizing: border-box;
}
.ex-note-textarea:focus { border-color: #4a90d9; }
.ex-note-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 16px;
}

/* ========== 标记面板 ========== */
.ex-marker-panel {
  background: #ffffff;
  border-radius: 16px;
  padding: 28px 32px;
  width: 440px;
  max-width: 90vw;
  box-shadow: 0 8px 40px rgba(0,0,0,0.2);
  animation: slideUp 0.25s ease;
}
.ex-marker-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 12px;
}
.ex-marker-option {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border: 1.5px solid #e8ecf2;
  border-radius: 10px;
  background: #fafbfd;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 14px;
  color: #555876;
}
.ex-marker-option:hover { border-color: rgba(200,22,30,0.3); background: #fef5f6; }
.marker-active {
  border-color: #c41e3a;
  background: linear-gradient(135deg, rgba(200,22,30,0.06) 0%, rgba(200,22,30,0.02) 100%);
  color: #c41e3a;
  font-weight: 600;
}
.marker-icon { font-size: 18px; }
.marker-label { font-size: 14px; }
.marker-remove {
  display: block;
  margin: 12px auto 0;
  padding: 6px 20px !important;
}
</style>
