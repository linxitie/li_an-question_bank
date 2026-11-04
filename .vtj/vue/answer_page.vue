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
                    answered: isAnswered(q.id),
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
              <!-- P1-2: 复合题共享材料（可折叠，仅该题组首个出现时渲染） -->
              <div
                v-if="materialOf(q) && isGroupFirstOccurrence(q.id)"
                class="group-material-block">
                <div class="group-material-header" @click="toggleGroupCollapse(materialKey(q))">
                  <span class="group-material-title">📖 {{ materialOf(q).title || '题组材料' }}</span>
                  <span class="group-material-toggle">{{ state.groupCollapsed[materialKey(q)] ? '展开 ▾' : '收起 ▴' }}</span>
                </div>
                <div
                  v-if="!state.groupCollapsed[materialKey(q)]"
                  class="group-material-content"
                  v-html="renderQuestionContent(materialOf(q).shared_content)"></div>
              </div>
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
              <p class="q-stem" v-html="renderQuestionContent(q.stem)"></p>
              <div v-if="q.requirements" class="q-requirements" style="margin:8px 0;padding:8px 12px;background:#f7f8fa;border-radius:6px;color:#666;font-size:14px;line-height:1.7;">
                <strong style="color:#333;">题目要求：</strong><span v-html="renderQuestionContent(q.requirements)"></span>
              </div>
              <div class="q-options" v-if="!isEssay(q)">
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
                  <span class="option-text" v-html="renderQuestionContent(opt)"></span>
                </div>
              </div>
              <!-- 主观题（申论/简答/论述/写作）：多行文本作答，不能套用选择题控件 -->
              <div class="q-essay" v-else>
                <div class="essay-hint">主观题 · 请在下方作答（按材料与题目要求分点书写）</div>
                <textarea
                  class="essay-input"
                  :rows="9"
                  :disabled="state.showResult"
                  :placeholder="state.showResult ? '已交卷，不可修改' : '请在此输入你的作答内容…'"
                  :value="getEssayAnswer(q.id)"
                  @input="setEssayAnswer(q.id, $event)"></textarea>
                <div class="essay-counter">{{ (getEssayAnswer(q.id) || '').length }} 字</div>
              </div>
              <div v-if="state.showResult" class="q-result">
                <template v-if="isEssay(q)">
                  <span class="result-badge essay-badge">主观题 · 参考作答</span>
                  <div v-if="q.answer" class="essay-reference">
                    <strong>参考答案：</strong>
                    <div v-html="renderQuestionContent(q.answer)"></div>
                  </div>
                  <div v-if="q.explain" class="result-explain" v-html="q.explainHtml"></div>
                </template>
                <template v-else>
                  <span class="result-badge">
                    {{ isCorrect(q) ? '✓ 回答正确' : '✗ 回答错误' }}</span
                  >
                  <div v-if="q.explain" class="result-explain" v-html="q.explainHtml"></div>
                </template>
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
                <button
                  :class="['fav-btn', { favorited: state.favorites[q.id] }]"
                  @click="toggleFavorite(q)">
                  {{ state.favorites[q.id] ? '已收藏' : '收藏' }}
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
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive, Transition } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { Grid, AlarmClock, CloseBold } from '@vtj/icons';
  import NavBar from './navbar.vue';
  import { useProvider } from '@vtj/renderer';
  import { ElMessage } from 'element-plus';
  import { renderQuestionContent } from '@/utils/questionRender';
import { formatMaterialHtml, ensureMaterialStyles } from '@/utils/materialDock';
  import { emitWrongQuestionsChanged } from '@/modules/practice/events';
  export default defineComponent({
    name: 'AnswerPage',
    components: { NavBar, XIcon, Transition },
    setup(props) {
      const provider = useProvider({ id: 'answer_page', version: '1778918968644' });
      const state = reactive({
        answers: {},
        timeLeft: 7200,
        questions: [],
        showResult: false,
        currentIndex: 0,
        optionLabels: ['A', 'B', 'C', 'D', 'E', 'F'],
        sheetVisible: false,
        markedQuestions: [],
        // 笔记相关
        showNoteEditor: false,
        noteText: '',
        currentNoteQuestionId: null,
        // 收藏状态：{ [question_id]: boolean }
        favorites: {},
        // P1-2: 题组聚合材料缓存 { [group_id]: { title, shared_content, group_type } }
        groupMaterials: {},
        // P1-2: 材料折叠状态 { [group_id]: boolean }（默认展开）
        groupCollapsed: {},
        // 练习提交状态：防重复提交 + 会话拉取结果
        submitting: false,
        sessionId: null,
        sessionStats: null
      });
      return { state, props, provider, Grid, AlarmClock, CloseBold, renderQuestionContent };
    },
    computed: {
      answeredCount() {
        var self = this;
        return (this.state.questions || []).filter(function(q) { return self.isAnswered(q.id); }).length;
      }
    },
    methods: {
      // 主观题判定：题型名同时兼容后端原始名与映射后的短名
      isEssay(q) {
        if (!q) return false;
        var t = q.type || '';
        if (['简答题', '论述题', '写作题', '综合分析题', '申论', '材料分析题',
             '简答', '论述', '写作', '综合分析', '材料分析'].indexOf(t) >= 0) return true;
        var objective = ['单选题', '多选题', '不定项', '多选', '判断题', '填空', '判断',
                         '单选', '多选'];
        return (!q.options || q.options.length === 0) && objective.indexOf(t) < 0;
      },
      // 已作答判定：选择题看下标是否存在，主观题看文本是否非空
      isAnswered(qId) {
        var v = this.state.answers[qId];
        if (v === undefined || v === null) return false;
        if (typeof v === 'string') return v.trim().length > 0;
        return Array.isArray(v) ? v.length > 0 : true;
      },
      getEssayAnswer(qId) {
        var v = this.state.answers[qId];
        return typeof v === 'string' ? v : '';
      },
      setEssayAnswer(qId, evt) {
        if (this.state.showResult) return;
        this.state.answers[qId] = (evt && evt.target && evt.target.value) || '';
      },
      isCorrect(q) {
        var userChoice = this.state.answers[q.id];
        if (userChoice === undefined || userChoice === null) return false;
        // 多选题：数组转字母后排序比较
        if (q.type === '多选题') {
          if (!Array.isArray(userChoice)) return false;
          var userLetters = userChoice.map(function(idx) { return this.state.optionLabels[idx]; }.bind(this)).sort().join('');
          var correctLetters = (q.answer || '').split('').sort().join('');
          return userLetters === correctLetters;
        }
        // 单选题：索引映射字母
        var userLetter = this.state.optionLabels[userChoice];
        return userLetter === q.answer;
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
      // ========== 收藏功能 ==========
      async toggleFavorite(q) {
        // 乐观更新：先切换 UI 状态，提升响应速度
        const prev = !!this.state.favorites[q.id];
        this.state.favorites[q.id] = !prev;
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/questions/' + q.id + '/favorite', {
            method: 'POST',
            headers: this.getJsonHeaders()
          });
          const data = await res.json();
          if (!res.ok) {
            // 回滚
            this.state.favorites[q.id] = prev;
            ElMessage.error(data.detail || data.message || '操作失败');
            return;
          }
          this.state.favorites[q.id] = !!data.favorited;
          ElMessage.success(data.message || (data.favorited ? '已收藏' : '已取消收藏'));
        } catch (e) {
          // 回滚
          this.state.favorites[q.id] = prev;
          console.warn('收藏操作失败:', e);
          ElMessage.error('收藏操作失败，请检查登录状态');
        }
      },
      async loadFavoritesStatus() {
        // 批量加载当前题目列表的收藏状态，避免每题单独请求
        const ids = this.state.questions.map(function(q) { return q.id; }).filter(function(id) { return id; });
        if (!ids.length) return;
        // 复用已有接口 /api/questions/favorites 获取用户收藏列表，再在前端比对
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/questions/favorites?page_size=100', {
            headers: this.getJsonHeaders()
          });
          if (!res.ok) return;
          const data = await res.json();
          const favIds = {};
          (data.items || []).forEach(function(item) {
            favIds[item.question_id] = true;
          });
          const favorites = {};
          ids.forEach(function(id) {
            favorites[id] = !!favIds[id];
          });
          this.state.favorites = favorites;
        } catch (e) {
          /* 静默失败，收藏按钮保持默认未收藏状态 */
        }
      },
      // P1-2: 批量加载题组材料（复合题小题聚合展示）
      async loadGroupMaterials() {
        var self = this;
        var gids = {};
        this.state.questions.forEach(function(q) {
          if (q.group_id) gids[q.group_id] = true;
        });
        var groupIds = Object.keys(gids);
        if (!groupIds.length) return;
        // 串行加载（题组通常较少，避免并发风暴）
        groupIds.forEach(function(gid) {
          window.__VTJ_AUTH__.apiFetch('/api/questions/group/' + gid, {
            headers: self.getJsonHeaders()
          }).then(function(res) { return res.json(); }).then(function(data) {
            if (data && data.group) {
              self.state.groupMaterials[gid] = data.group;
              // 复合题小题的「题目要求」：题组聚合的 members[] 是权威来源。
              // 出题接口（/api/questions/random）逐题返回 requirements，但历史题组
              // 存在成员行未回写的记录；这里只在本地为空时补齐，绝不覆盖已有值，
              // 也不触碰 isGroupFirstOccurrence（材料仍只在组内首题渲染一次）。
              if (data.members && data.members.length) {
                data.members.forEach(function(m) {
                  if (m.question_id == null) return;
                  var reqText = self.normalizeRequirements(m.requirements);
                  if (!reqText) return;
                  for (var i = 0; i < self.state.questions.length; i++) {
                    var t = self.state.questions[i];
                    if (!t.group_id || String(t.group_id) !== String(gid)) continue;
                    if (String(t.id) === String(m.question_id) && !self.normalizeRequirements(t.requirements)) {
                      t.requirements = reqText;
                    }
                  }
                });
              }
            }
          }).catch(function() { /* 静默：材料加载失败不影响答题 */ });
        });
      },
      // P1-2: 切换题组材料折叠
      toggleGroupCollapse(gid) {
        this.state.groupCollapsed[gid] = !this.state.groupCollapsed[gid];
      },
      async handleSubmit() {
        if (this.state.submitting || this.state.showResult) return;
        this.state.submitting = true;
        this.state.showResult = true;
        ElMessage.success('试卷已提交');
        await this.submitPracticeRecords();
        this.state.submitting = false;
        // 触发自动签到
        this.triggerCheckin();
      },
      async submitPracticeRecords() {
        var self = this;
        var questions = this.state.questions || [];
        var records = [];
        for (var i = 0; i < questions.length; i++) {
          var q = questions[i];
          var userAns = this.state.answers[q.id];
          if (userAns === undefined) continue;
          // 主观题：提交文本本身。若按选项下标映射会把整段作答弄丢（旧逻辑的隐性 bug）。
          if (this.isEssay(q)) {
            var text = String(userAns === null ? '' : userAns).trim();
            if (!text) continue;
            records.push({
              question_id: q.id,
              subject_id: q.subject_id || null,
              user_answer: text,
              time_spent: 0,
              source: '随机练习'
            });
            continue;
          }
          var userLetter;
          if (Array.isArray(userAns)) {
            userLetter = userAns.map(function(idx) { return self.state.optionLabels[idx]; }).sort().join('');
          } else {
            userLetter = self.state.optionLabels[userAns] || '';
          }
          records.push({
            question_id: q.id,
            subject_id: q.subject_id || null,
            user_answer: userLetter,
            time_spent: 0,
            source: '随机练习'
          });
        }
        if (!records.length) return;
        try {
          var res = await window.__VTJ_AUTH__.apiFetch('/api/practice/batch-record', {
            method: 'POST',
            headers: this.getJsonHeaders(),
            body: JSON.stringify({ records: records, session_id: this.state.sessionId })
          });
          var data = await res.json();
          if (!res.ok) throw new Error(data.detail || data.message || '提交失败');
          this.state.sessionStats = data;
          var stats = data.wrong_question_stats || {};
          if (data.has_new_wrong || (stats.new || 0) > 0 || (stats.updated || 0) > 0) {
            emitWrongQuestionsChanged({ action: 'added', source: 'practice' });
          }
        } catch (e) {
          console.warn('练习记录提交失败:', e);
          ElMessage.error('练习记录提交失败，请稍后重试');
        }
      },
      async loadPracticeSession() {
        var query = (this.$route && this.$route.query) || {};
        if (query.session_id) {
          this.state.sessionId = String(query.session_id);
        }
        try {
          var res = await window.__VTJ_AUTH__.apiFetch('/api/practice/stats-card');
          if (res.ok) {
            this.state.sessionStats = await res.json();
          }
        } catch (e) {
          /* 会话拉取失败不阻断答题 */
        }
      },
      triggerCheckin() {
        window.__VTJ_AUTH__.apiFetch('/api/stats/auto-checkin', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        }).catch(function() { /* 静默 */ });
      },
      selectOption(qId, oidx, type) {
        if (this.state.showResult) return;
        // 多选题/不定项：支持toggle多选
        if (type === '多选题' || type === '不定项' || type === '多选') {
          var current = this.state.answers[qId] || [];
          if (current.includes(oidx)) {
            this.state.answers[qId] = current.filter(function(o) { return o !== oidx; });
          } else {
            this.state.answers[qId] = current.concat([oidx]);
          }
        } else {
          // 单选题：直接替换
          this.state.answers[qId] = oidx;
        }
      },
      getTypeLabel(type) {
        var map = {
          '单选题': '[单选]', '单选': '[单选]',
          '多选题': '[多选]', '不定项': '[多选]', '多选': '[多选]',
          '判断题': '[判断]', '判断': '[判断]',
          '简答题': '[简答]', '简答': '[简答]',
          '论述题': '[论述]', '论述': '[论述]',
          '写作题': '[写作]', '写作': '[写作]',
          '综合分析题': '[综合分析]', '综合分析': '[综合分析]',
          '材料分析题': '[材料分析]', '材料分析': '[材料分析]', '申论': '[申论]'
        };
        return map[type] || '[单选]';
      },
      getTypeClass(type) {
        var map = {
          '多选题': 'multi', '不定项': 'multi', '多选': 'multi',
          '判断题': 'judge', '判断': 'judge',
          '简答题': 'essay', '简答': 'essay',
          '论述题': 'essay', '论述': 'essay',
          '写作题': 'essay', '写作': 'essay',
          '综合分析题': 'essay', '综合分析': 'essay',
          '材料分析题': 'essay', '材料分析': 'essay', '申论': 'essay'
        };
        return map[type] || '';
      },
      // P1-2: 判断当前题目是否为其题组在当前列表中的首个出现（用于仅渲染一次共享材料）
      isGroupFirstOccurrence(qId) {
        var q = this.state.questions.find(function(x) { return x.id === qId; });
        if (!q) return false;
        if (q.group_id) {
          var firstIdx = -1;
          for (var i = 0; i < this.state.questions.length; i++) {
            if (this.state.questions[i].group_id === q.group_id) { firstIdx = i; break; }
          }
          return firstIdx >= 0 && this.state.questions[firstIdx].id === qId;
        }
        // 行测资料题常以 group_id=0 入库，材料随题返回（shared_content），
        // 此时按"同材料只渲染一次"去重，避免每题重复整段材料。
        if (!q.shared_content) return false;
        var firstInline = this.state.questions.find(function(x) {
          return x.shared_content === q.shared_content;
        });
        return !!firstInline && firstInline.id === qId;
      },
      // 材料来源：优先题组接口缓存，其次随题返回的 shared_content（兜底）
      materialOf(q) {
        if (!q) return null;
        var mat = null;
        if (q.group_id && this.state.groupMaterials[q.group_id]) {
          mat = this.state.groupMaterials[q.group_id];
        } else if (q.shared_content) {
          mat = { title: '题组材料', shared_content: q.shared_content };
        }
        if (!mat) return null;
        // 材料分段在数据出口统一做：模板只消费 shared_content，
        // 这样教师/管理/学生三端拿到的是同一套「材料N」高亮与段间距。
        mat.shared_content = formatMaterialHtml(mat.shared_content || '');
        return mat;
      },
      // 折叠状态键：题组用 group_id，随题材料用 q<id> 区分
      materialKey(q) {
        if (!q) return '';
        return q.group_id || ('q' + q.id);
      },
      // 「题目要求」归一：后端 requirements 为 Text 列，可能是单字符串，
      // 也可能是 JSON 数组（申论常有多条采分点依据，导入管线两形态都写过库）。
      // 模板的 v-html 渲染位只消费字符串，数组直接交给 renderQuestionContent 会
      // String() 成 "a,b,c" 之类的粘合文本，且换行全丢。这里两形态统一成
      // 以 \n 拼接的单一字符串，保持原有内容语义而不改写内容本身。
      normalizeRequirements(req) {
        if (!req) return '';
        if (typeof req !== 'string' && !Array.isArray(req)) return String(req);
        if (Array.isArray(req)) {
          return req
            .map(function(r) { return String(r == null ? '' : r).trim(); })
            .filter(function(s) { return !!s; })
            .join('\n');
        }
        return req.trim();
      },
      loadQuestions() {
        console.log('[AnswerPage] loadQuestions v20260623 - real API');
        this.state.questions = [];
        this.ensureLogin().then(() => {
          const headers = this.getJsonHeaders();
          // Use GET with query params for random endpoint
          let params = new URLSearchParams({ count: 20 });
          fetch('/api/questions/random?' + params.toString(), {
            method: 'GET',
            headers: headers
          }).then(res => res.json()).then(data => {
            if (data.questions && data.questions.length) {
              this.state.questions = data.questions.map(q => {
                // 稳健解析选项：支持多种存储格式
                var rawOpts = q.options;
                var parsedOpts = [];
                if (rawOpts) {
                  // 格式1: JSON字符串
                  if (typeof rawOpts === 'string') {
                    try { rawOpts = JSON.parse(rawOpts); } catch(e) { parsedOpts = [rawOpts]; }
                  }
                  // 格式2: 数组 [{key:"A",value:"..."}, ...] 或 ["text", ...]
                  if (Array.isArray(rawOpts)) {
                    parsedOpts = rawOpts.map(function(o) {
                      if (typeof o === 'string') return o;
                      if (o && typeof o === 'object') {
                        var key = (o.key || '');
                        var text = (o.value || o.text || '');
                        text = text.replace(/[\.。、'；;：:，,！!？?]+$/g, '').trim();
                        return (key ? key + '. ' : '') + (text || '(空)');
                      }
                      return String(o);
                    });
                  }
                }
                // 是否存在真实选项：必须在补 '(暂无选项)' 占位前判定，
                // 否则所有主观题都会被当成"有选项"而误判成单选题（申论答题卡的根因）。
                var rawHasOptions = false;
                if (q.options) {
                  if (Array.isArray(q.options)) rawHasOptions = q.options.length > 0;
                  else if (typeof q.options === 'string') {
                    var _t = q.options.trim();
                    rawHasOptions = _t.length > 2 && _t !== '[]' && _t !== 'null';
                  }
                }
                if (!parsedOpts.length) parsedOpts = ['(暂无选项)'];
                // 题目内容统一走渲染真源 src/utils/questionRender.js
                // 由其负责：[IMAGE:题号_序号] 标记转 <img>、白名单清洗、onerror 占位兜底
                parsedOpts = parsedOpts.map(function(opt) {
                  return typeof opt === 'string' ? renderQuestionContent(opt) : opt;
                });
                // 清理题干中嵌入的选项行 + 图片占位
                var stem = renderQuestionContent(q.question_content || '', { stripInlineOption: true }).trim();
                return {
                  id: q.question_id,
                  group_id: q.group_id || 0,
                  // 题组材料随题返回（后端 QuestionResponse 有 shared_content 字段），
                  // 作为题组接口失败/未返回时的兜底，避免材料与子题断裂。
                  shared_content: q.shared_content || '',
                  type: (function() {
                    // 题型映射必须覆盖主观题：原实现只映射单选/多选，申论题
                    // (question_type_detail 为空或无选项) 会兜底成"单选"，
                    // 渲染出"(暂无选项)"的选择题页面 —— 这正是申论答题卡失效的根因。
                    var rawType = q.question_type_detail || '';
                    var typeMap = {
                      '单选题': '单选', '选择题': '单选', '单选': '单选',
                      '多选题': '多选题', '不定项': '多选', '多选': '多选',
                      '判断题': '判断',
                      '简答题': '简答', '论述题': '论述', '写作题': '写作',
                      '综合分析题': '综合分析', '材料分析题': '材料分析', '申论': '申论'
                    };
                    var mapped = typeMap[rawType];
                    if (!mapped) {
                      if (!rawHasOptions) mapped = '简答';
                      else if (q.answer && q.answer.length > 1) mapped = '多选题';
                    }
                    return mapped || '单选';
                  })(),
                  stem: stem || q.question_content || '',
                  options: parsedOpts,
                  answer: q.answer || '',
                  explain: q.answer_analysis || '暂未提供解析',
                  // 「题目要求」归一为单一字符串（string/array 两形态都由
                  // normalizeRequirements 收口），模板 v-html 位直接消费。
                  requirements: this.normalizeRequirements(q.requirements),
                  // ★ 答案解析必须走公共渲染器：解析里可能含图片说明（申论思维导图等）。
                  //   此前模板用 {{ q.explain }} 纯文本插值，<img> 会被当字面量显示成
                  //   '<img src="/static/questions/...">' —— 用户看到的是一串路径。
                  explainHtml: renderQuestionContent(
                    q.answer_analysis || '暂未提供解析', { stripInlineOption: false })
                };
              });
            }
            if (!this.state.questions.length) {
              this.state.questions = [{
                id: 0, type: '提示', stem: '题库暂无题目数据，请先在题目导入页面添加题目',
                options: [], answer: '', explain: ''
              }];
            }
            // P1-2: 批量加载题组材料（复合题小题聚合展示）
            this.loadGroupMaterials();
            // 题目加载完成后批量加载收藏状态
            this.loadFavoritesStatus();
          }).catch(() => {
            this.state.questions = [{
              id: 0, type: '提示', stem: '无法连接到后端服务器，请检查服务是否运行',
              options: [], answer: '', explain: ''
            }];
          });
        });
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
            if (data.has_note) {
              self.state.noteText = data.note_text || '';
            }
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
        } catch(e) {
          console.warn('保存笔记失败:', e);
        }
      },
      async deleteNote() {
        var qId = this.state.currentNoteQuestionId;
        if (!qId) return;
        try {
          await window.__VTJ_AUTH__.apiFetch('/api/questions/' + qId + '/note', {
            method: 'DELETE',
            headers: this.getJsonHeaders()
          });
          this.state.showNoteEditor = false;
          this.state.noteText = '';
        } catch(e) {
          console.warn('删除笔记失败:', e);
        }
      }
    },
    // ===== 三端实时同步：题目导入后仅提示，不打断作答 =====
    // 关键约束：作答页绝不能重载题目或切换当前题，否则会清空用户
    // 已填写的内容与进度。因此这里只弹一个非阻塞提示，由用户自行决定。
    _syncTimer: null,
    _onVTJSync(e) {
      const d = e && e.detail && e.detail.data;
      if (!d || d.scope !== 'question_bank') return;
      if (this._syncTimer) clearTimeout(this._syncTimer);
      this._syncTimer = setTimeout(() => {
        this._syncTimer = null;
        const n = d.count || 0;
        ElMessage.info(n > 0 ? `题库已更新（新增 ${n} 题），本题不受影响` : '题库已更新');
      }, 1500);
    },
    mounted() {
      console.log('[AnswerPage] mounted v20260623 - VUE SOURCE loaded');
      ensureMaterialStyles();
      this.loadQuestions();
      this.loadPracticeSession();
      this.startTimer();
      window.addEventListener('__VTJ_SYNC__', this._onVTJSync);
    },
    beforeUnmount() {
      if (this._timer) {
        clearInterval(this._timer);
        this._timer = null;
      }
      if (this._syncTimer) {
        clearTimeout(this._syncTimer);
        this._syncTimer = null;
      }
      window.removeEventListener('__VTJ_SYNC__', this._onVTJSync);
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
  /* P1-2: 复合题共享材料块 */
  .group-material-block {
    margin-bottom: 16px;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    overflow: hidden;
    background: #f8fafc;
  }
  .group-material-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    cursor: pointer;
    background: #f1f5f9;
    user-select: none;
  }
  .group-material-header:hover { background: #eef2f7; }
  .group-material-title {
    font-size: 14px;
    font-weight: 700;
    color: #1a2b5f;
  }
  .group-material-toggle {
    font-size: 13px;
    color: #64748b;
  }
  .group-material-content {
    padding: 14px 16px;
    font-size: 14px;
    line-height: 1.8;
    color: #334155;
    white-space: pre-wrap;
    word-break: break-word;
  }
  .group-material-content :deep(img.q-img) {
    max-width: 100%;
    border-radius: 8px;
    margin: 8px 0;
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
    font-size: 17px;
    padding: 5px 16px;
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
    background: #f5f3ff;
    color: #7c3aed;
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
  /* 主观题作答区：申论/简答/论述用多行文本，不再出现选项按钮 */
  .q-essay {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .essay-hint {
    padding: 8px 12px; background: #fef7ed;
    border-radius: 8px; font-size: 12px; color: #b45309;
  }
  .essay-input {
    width: 100%; box-sizing: border-box;
    min-height: 200px; padding: 12px 14px;
    border: 1px solid #e5e7eb; border-radius: 10px;
    font-size: 14px; line-height: 1.8; color: #1f2937;
    background: #fff; resize: vertical;
    font-family: inherit;
  }
  .essay-input:focus {
    outline: none; border-color: #c41e3a;
    box-shadow: 0 0 0 3px rgba(196, 30, 58, 0.08);
  }
  .essay-input:disabled {
    background: #f9fafb; color: #6b7280; cursor: not-allowed;
  }
  .essay-counter {
    text-align: right; font-size: 12px; color: #9ca3af;
  }
  .essay-badge {
    background: #fef3c7; color: #92400e;
  }
  .essay-reference {
    margin-top: 8px; padding: 10px 12px;
    background: #f9fafb; border-left: 3px solid #d1d5db;
    border-radius: 6px; font-size: 14px; line-height: 1.8; color: #374151;
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
    gap: 8px;
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
  /* 收藏按钮 - 与标记/笔记按钮风格统一，已收藏时红色高亮 */
  .fav-btn {
    padding: 6px 16px; border: 1px solid #fde2e6; border-radius: 8px;
    background: #fff5f7; font-size: 12px; color: #c41e3a; cursor: pointer;
    transition: all 0.2s;
  }
  .fav-btn:hover { background: #fde2e6; border-color: #c41e3a; }
  .fav-btn.favorited {
    background: linear-gradient(135deg, #c41e3a, #e8384f);
    color: #ffffff; border-color: #c41e3a; font-weight: 600;
  }
  .fav-btn.favorited:hover { box-shadow: 0 2px 8px rgba(196, 30, 58, 0.3); }
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
