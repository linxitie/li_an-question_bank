<template>
  <div class="paper-answer-page">
    <main class="pa-main">
      <!-- 顶部工具栏 -->
      <div class="pa-toolbar">
        <div class="toolbar-left">
          <button class="tool-btn" @click="toggleSheet">
            <span>📋 答题卡</span>
          </button>
          <span class="progress-text">{{ state.currentIndex + 1 }} / {{ totalQuestions }}</span>
          <span class="paper-name" v-if="state.paperName">{{ state.paperName }}</span>
        </div>
        <div class="toolbar-right">
          <div class="timer-display">
            <span :class="['timer-text', { urgent: state.timeLeft < 300 }]">⏱ {{ formatTime(state.timeLeft) }}</span>
          </div>
          <button class="exit-btn" @click="handleExit">✕ 退出</button>
        </div>
      </div>

      <div class="pa-body">
        <!-- 答题卡面板 -->
        <div v-if="state.sheetVisible" class="sheet-panel">
          <div class="sheet-header">
            <h4>答题卡</h4>
            <span class="sheet-close" @click="state.sheetVisible = false">✕</span>
          </div>
          <div class="sheet-stats">
            <span>已答 <b>{{ answeredCount }}</b></span>
            <span>未答 <b>{{ totalQuestions - answeredCount }}</b></span>
          </div>
          <div class="sheet-grid">
            <button v-for="(q, idx) in questionsParsed" :key="q.id"
              :class="['sheet-num', {
                active: idx === state.currentIndex,
                answered: answersParsed[q.id] !== undefined,
                marked: markedParsed.includes(q.id)
              }]"
              @click="jumpTo(idx)">{{ idx + 1 }}</button>
          </div>
          <button class="submit-btn" @click="handleSubmit">交卷</button>
        </div>

        <!-- 题目区域 -->
        <div class="question-area">
          <div class="question-scroll">
            <!-- 加载状态 -->
            <div v-if="state.loading" class="loading-state">
              <div class="loading-spinner"></div>
              <p>正在加载试卷...</p>
            </div>

            <!-- 题目列表 -->
            <div v-for="(q, idx) in questionsParsed" v-else :key="q.id" :ref="'q_' + q.id" class="question-block">
              <div class="q-header">
                <span class="q-number">{{ idx + 1 }}.</span>
                <span :class="['q-type-badge', getTypeClass(q.type)]">{{ getTypeLabel(q.type) }}</span>
                <span class="q-score">{{ q.score || 0 }}分</span>
                <span v-if="markedParsed.includes(q.id)" class="mark-badge">🔖 已标记</span>
              </div>
              <p class="q-stem" v-html="renderQuestionContent(q.stem, { stripInlineOption: true })"></p>

              <!-- 客观题：选项 -->
              <div v-if="getRenderMode(q.type) !== 'textarea'" class="q-options">
                <div v-if="getRenderMode(q.type) === 'checkbox'" class="multi-hint">
                  <strong>多选题</strong> — 点击多个选项
                </div>
                <div v-for="(opt, oidx) in q.options" :key="oidx"
                  :class="['option-item', {
                    selected: isOptionSelected(q.id, oidx),
                    correct: state.showResult && isCorrectOption(q, oidx),
                    wrong: state.showResult && isOptionSelected(q.id, oidx) && !isCorrectOption(q, oidx)
                  }]"
                  @click="selectOption(q.id, oidx, q.type)">
                  <span :class="['option-marker', getRenderMode(q.type) === 'checkbox' ? 'checkbox' : 'radio']">
                    {{ getRenderMode(q.type) === 'checkbox' ? '☐' : '○' }}
                  </span>
                  <span class="option-label">{{ state.optionLabels[oidx] }}.</span>
                  <span class="option-text" v-html="renderQuestionContent(opt)"></span>
                </div>
              </div>

              <!-- 主观题：文本框 -->
              <div v-else class="q-textarea">
                <textarea
                  :value="getTextAnswer(q.id)"
                  @input="e => selectOption(q.id, e.target.value, q.type)"
                  :placeholder="q.type === '写作题' ? '请在此输入你的文章...' : '请在此输入你的答案...'"
                  :class="['answer-textarea', q.type === '写作题' ? 'writing' : '']"
                  :rows="q.type === '写作题' ? 20 : 8"
                ></textarea>
              </div>

              <!-- 结果显示 -->
              <div v-if="state.showResult" class="q-result">
                <span :class="['result-badge', isCorrect(q) ? 'correct-badge' : 'incorrect-badge']">
                  {{ isCorrect(q) ? '✓ 正确' : '✗ 错误' }}
                </span>
                <p v-if="q.explain" class="result-explain">📖 {{ q.explain }}</p>
              </div>

              <!-- 操作按钮 -->
              <div class="q-actions">
                <button :class="['mark-btn', { marked: markedParsed.includes(q.id) }]" @click="toggleMark(q.id)">
                  {{ markedParsed.includes(q.id) ? '取消标记' : '标记' }}
                </button>
              </div>
            </div>

            <!-- 空状态 -->
            <div v-if="!state.loading && questionsParsed.length === 0" class="empty-state">
              <p>📭 暂无题目数据</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部导航 -->
      <div class="pa-nav">
        <button class="nav-btn" :disabled="state.currentIndex === 0" @click="state.currentIndex--">← 上一题</button>
        <span class="nav-progress">{{ state.currentIndex + 1 }} / {{ totalQuestions }}</span>
        <button class="nav-btn" :disabled="state.currentIndex >= totalQuestions - 1" @click="state.currentIndex++">下一题 →</button>
        <button class="submit-main-btn" @click="handleSubmit">📝 交卷</button>
      </div>
    </main>

    <!-- 退出弹窗 -->
    <div v-if="state.showExitDialog" class="modal-overlay" @click.self="state.showExitDialog = false">
      <div class="modal-dialog">
        <h4>确定退出？</h4>
        <p>答题进度将被保存到本地，下次可继续作答。</p>
        <div class="modal-actions">
          <button class="pa-btn back-btn" @click="state.showExitDialog = false">继续答题</button>
          <button class="pa-btn generate-btn" @click="saveAndExit">保存并退出</button>
        </div>
      </div>
    </div>

    <!-- 交卷确认弹窗 -->
    <div v-if="state.showSubmitDialog" class="modal-overlay" @click.self="state.showSubmitDialog = false">
      <div class="modal-dialog">
        <h4>确认交卷？</h4>
        <p>已答 <b>{{ answeredCount }}</b> / <b>{{ totalQuestions }}</b> 题，未答题将按0分处理。</p>
        <div class="modal-actions">
          <button class="pa-btn back-btn" @click="state.showSubmitDialog = false">继续检查</button>
          <button class="pa-btn generate-btn" @click="confirmSubmit">确认交卷</button>
        </div>
      </div>
    </div>

    <!-- 成绩弹窗 -->
    <div v-if="state.showResultDialog" class="modal-overlay">
      <div class="modal-dialog result-dialog">
        <div class="result-icon">🎉</div>
        <h3>交卷成功！</h3>
        <div class="result-stats">
          <div class="rs-item"><span class="rs-label">得分</span><span class="rs-value score">{{ state.submitScore }} / {{ state.submitMaxScore }}</span></div>
          <div class="rs-item"><span class="rs-label">正确率</span><span class="rs-value green">{{ state.submitAccuracy }}%</span></div>
          <div class="rs-item"><span class="rs-label">正确/错误</span><span class="rs-value">{{ state.submitCorrect }} / {{ state.submitWrong }}</span></div>
          <div class="rs-item"><span class="rs-label">用时</span><span class="rs-value">{{ formatTime(state.submitTimeSpent) }}</span></div>
        </div>
        <p class="result-hint">✅ 成绩已同步到「成绩分析 → 自测」</p>
        <div class="modal-actions">
          <button class="pa-btn generate-btn" @click="viewDetails">查看详情</button>
          <button class="pa-btn outline-btn" @click="goBackToList">返回试卷列表</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive, onMounted, onBeforeUnmount } from 'vue';
import { useProvider } from '@vtj/renderer';
import { renderQuestionContent } from '@/utils/questionRender';
import { formatMaterialHtml, ensureMaterialStyles } from '@/utils/materialDock';

export default defineComponent({
  name: 'PaperAnswer',
  setup() {
    const provider = useProvider({ id: 'paper_answer', version: '1' });
    const state = reactive({
      loading: true,
      paperId: null,
      recordId: null,
      paperName: '',
      totalDuration: 7200,
      timeLeft: 7200,
      questions: '[]',
      answers: '{}',
      markedQuestions: '[]',
      currentIndex: 0,
      optionLabels: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'],
      sheetVisible: false,
      showResult: false,
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
    return { state, provider, renderQuestionContent };
  },
  computed: {
    questionsParsed() {
      try { return JSON.parse(this.state.questions || '[]'); } catch(e) { return []; }
    },
    answersParsed() {
      try { return JSON.parse(this.state.answers || '{}'); } catch(e) { return {}; }
    },
    markedParsed() {
      try { return JSON.parse(this.state.markedQuestions || '[]'); } catch(e) { return []; }
    },
    answeredCount() {
      return Object.keys(this.answersParsed).length;
    },
    totalQuestions() {
      return this.questionsParsed.length;
    },
  },
  methods: {
    // ===== 工具函数 =====
    formatTime(s) {
      s = Math.max(0, Math.floor(s));
      var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
      return h.toString().padStart(2, '0') + ':' + m.toString().padStart(2, '0') + ':' + sec.toString().padStart(2, '0');
    },

    getTypeLabel(type) {
      var map = {
        '单选题': '[单选]', '单选': '[单选]',
        '多选题': '[多选]', '不定项': '[多选]', '多选': '[多选]',
        '判断题': '[判断]',
        '论述题': '[论述]', '简答题': '[简答]', '案例分析题': '[案例]',
        '写作题': '[写作]'
      };
      return map[type] || '[单选]';
    },

    getTypeClass(type) {
      if (['多选题', '不定项', '多选'].indexOf(type) >= 0) return 'multi';
      if (['论述题', '简答题', '案例分析题', '写作题'].indexOf(type) >= 0) return 'essay';
      return '';
    },

    getRenderMode(type) {
      if (['多选题', '不定项', '多选'].indexOf(type) >= 0) return 'checkbox';
      if (['论述题', '写作题', '简答题', '案例分析题'].indexOf(type) >= 0) return 'textarea';
      return 'radio';
    },

    // ===== 题目加载 =====
    async loadQuestions() {
      var paperId = this.$route.query.paper_id;
      var recordId = this.$route.query.record_id;
      if (!paperId) { this.state.loading = false; return; }

      this.state.paperId = parseInt(paperId);
      this.state.recordId = recordId ? parseInt(recordId) : null;

      try {
        var res = await window.__VTJ_AUTH__.apiFetch('/api/exams/' + paperId + '/questions', {
          headers: window.__VTJ_AUTH__.getJsonHeaders()
        });
        if (!res.ok) throw new Error('加载试卷失败');
        var data = await res.json();

        this.state.paperName = data.paper_name || '';
        this.state.totalDuration = (data.duration || 120) * 60;
        this.state.timeLeft = this.state.totalDuration;

        // 转换题目格式
        // 复合题：同一 group_id 的连续子题共用一份材料，只在每组第一题挂载材料块。
        // 材料由后端 exam API 随题目返回（group_id/shared_content/shared_content_images），
        // 前端不再自行拼接，避免与导入时建立的材料-子题关系脱节。
        var prevGroupId = 0;
        var questions = (data.questions || []).map(function(q) {
          var opts = this.parseOptions(q.options);
          // IMAGE占位替换
          var stem = this.replaceImages(q.question_content || '');
          opts = opts.map(function(o) { return this.replaceImages(o); }.bind(this));

          var gid = parseInt(q.group_id || 0, 10) || 0;
          var materialHtml = '';
          if (gid > 0 && gid !== prevGroupId) {
            materialHtml = this.buildGroupMaterial(q);
          }
          // 连续组只挂一次；组被打断时（理论上不应出现）重新挂载，保证材料不缺
          prevGroupId = gid;

          return {
            id: q.question_id,
            type: q.type_name || '单选题',
            stem: stem,
            options: opts,
            score: q.question_score || 0,
            explain: '',  // 考试模式不含答案
            answer: '',   // 考试模式不含答案
            subject_id: q.subject_id,
            groupId: gid,
            materialHtml: materialHtml,
          };
        }.bind(this));

        this.state.questions = JSON.stringify(questions);

        // 恢复localStorage进度
        this.restoreProgress();
        // 等 v-for 渲染完成后，把材料块插到每组首题的题干上方
        this.$nextTick(this.mountGroupMaterials);
      } catch(e) {
        console.error('[PaperAnswer] 加载题目失败:', e);
      } finally {
        this.state.loading = false;
      }
    },

    // 选项解析（4种格式兼容）
    parseOptions(raw) {
      if (!raw) return ['(暂无选项)'];
      if (Array.isArray(raw) && raw.length > 0) {
        return raw.map(function(o) {
          if (typeof o === 'string') return o;
          return (o.key || '') + '. ' + (o.value || o.text || '');
        });
      }
      if (typeof raw === 'string') {
        var parsed = raw;
        while (typeof parsed === 'string') {
          try { parsed = JSON.parse(parsed); } catch(e) { break; }
        }
        if (Array.isArray(parsed)) {
          return parsed.map(function(o) {
            if (typeof o === 'string') return o;
            return (o.key || '') + '. ' + (o.value || o.text || '');
          });
        }
      }
      return ['(暂无选项)'];
    },

    // IMAGE占位替换（复用answer_page逻辑）
    // 兼容两种 marker：{hash}_{行号} 与 {hash}_{行号}_{序号}。
    // 旧正则只能匹配两段，三段 marker 会被截成 "115_0.png" 导致裂图。
    replaceImages(text) {
      if (!text) return '';
      return String(text).replace(/\[?IMAGE:([a-fA-F0-9]+_\d+(?:_\d+)?)\]?/gi, function(m, marker) {
        return '<img src="/static/questions/' + marker + '.png" class="q-img" loading="lazy" onerror="this.onerror=null;this.src=\'/static/images/placeholder.png\';this.alt=\'图片加载失败\'" />';
      });
    },

    // 组装题组材料 HTML（仅用于组内首题）
    buildGroupMaterial(q) {
      var parts = [];
      var shared = q.shared_content ? String(q.shared_content) : '';
      if (shared) parts.push(shared);

      // shared_content_images 是 JSON 数组：可能是 URL，也可能是 [IMAGE:] marker
      var imgs = q.shared_content_images;
      if (typeof imgs === 'string' && imgs) {
        try { imgs = JSON.parse(imgs); } catch (e) { imgs = []; }
      }
      if (Array.isArray(imgs)) {
        imgs.forEach(function(item) {
          var s = String(item || '').trim();
          if (!s) return;
          // 组材料正文里已经渲染过的图片不能再追加一次，否则一图两遍。
          // 历史数据里 shared_content 与 shared_content_images 同时存在是常态。
          if (shared && shared.indexOf(s) >= 0) return;
          if (s.indexOf('<img') === 0) parts.push(s);
          else if (s.indexOf('[IMAGE:') === 0) parts.push(this.replaceImages(s));
          else parts.push('<img src="' + s + '" class="q-img" />');
        }.bind(this));
      }

      if (!parts.length) return '';
      // 复用统一渲染入口：白名单清洗 + [IMAGE:] 转 <img> + onerror 兜底；
      // 再经 materialDock 切段，保证「材料N」高亮与段间距和教师端一致。
      var html = this.renderQuestionContent(parts.join(''), { stripInlineOption: false });
      return formatMaterialHtml(html);
    },

    // ===== 吸顶材料面板（script-only，遵守 raw 页 template 红线）=====
    // 目标：滚动到组内任意一题时，本组材料始终固定在顶栏下方，可独立滚动/收起；
    // 组首题的内联材料块隐藏，避免同一份材料在首题处出现两遍。
    getTopOffset() {
      var toolbar = this.$el && this.$el.querySelector ? this.$el.querySelector('.pa-toolbar') : null;
      var h = (toolbar && toolbar.offsetHeight) || 56;
      var panel = this._materialPanel;
      if (panel && panel.style.display !== 'none') {
        h += panel.offsetHeight || 0;
      }
      return h + 8;
    },

    getCurrentMaterialQuestion() {
      var qs = this.questionsParsed || [];
      if (!qs.length) return null;
      var idx = Math.max(0, Math.min(this.state.currentIndex || 0, qs.length - 1));
      var cur = qs[idx];
      var curGid = parseInt((cur && cur.groupId) || 0, 10);
      // 独立题没有组材料；不能沿用上一组的材料面板。
      if (curGid <= 0) return null;
      if (cur.materialHtml) return cur;
      // 材料只挂在组首题：先在当前题之前、且仍属同一组的连续区间内回溯。
      for (var i = idx - 1; i >= 0; i--) {
        var prev = qs[i];
        if (parseInt((prev && prev.groupId) || 0, 10) !== curGid) break;
        if (prev.materialHtml) return prev;
      }
      // 题组跨页/乱序时再按 groupId 全局兜底，但不跨组。
      for (var j = 0; j < qs.length; j++) {
        var q = qs[j];
        if (parseInt((q && q.groupId) || 0, 10) === curGid && q.materialHtml) return q;
      }
      return null;
    },

    // 材料分层：把「材料一：」「资料2、」等标注渲染成高亮胶囊，
    // 用块级间距把多则材料分开。只处理文本节点，不碰 img/table。
    formatMaterialBody(root) {
      if (!root) return;
      root.style.whiteSpace = 'pre-wrap';
      root.style.wordBreak = 'break-word';
      // 标注可能写作「材料一：」「材料1\n」「给定资料2」，冒号可有可无；
      // 只认行首，避免把正文中的“资料3份”当成分段标题。
      var pattern = /(^|\n)[ \t]*((?:材料|给定资料|资料)[ \t]*[0-9一二三四五六七八九十]+)[ \t]*[：:]?/g;
      var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
      var textNodes = [];
      while (walker.nextNode()) textNodes.push(walker.currentNode);
      textNodes.forEach(function(node) {
        var text = node.nodeValue || '';
        if (!pattern.test(text)) return;
        pattern.lastIndex = 0;
        var frag = document.createDocumentFragment();
        var last = 0;
        var m;
        var first = true;
        while ((m = pattern.exec(text))) {
          if (m.index > last) {
            frag.appendChild(document.createTextNode(text.slice(last, m.index)));
          }
          var label = document.createElement('span');
          label.textContent = m[2];
          // block + fit-content：标注独占一行，材料一则与材料二之间才有真正的垂直间距
          label.style.cssText = 'display:block;width:fit-content;max-width:100%;margin:' +
            (first ? '0' : '18px') + ' 0 8px;padding:2px 10px;border-radius:999px;' +
            'background:#E8F0FB;color:#1A3C6D;font-weight:700;font-size:13px;line-height:1.6;';
          frag.appendChild(label);
          last = m.index + m[0].length;
          first = false;
        }
        if (last < text.length) frag.appendChild(document.createTextNode(text.slice(last)));
        node.parentNode.replaceChild(frag, node);
      });
      var tables = root.querySelectorAll('table');
      for (var t = 0; t < tables.length; t++) {
        tables[t].style.maxWidth = '100%';
        tables[t].style.borderCollapse = 'collapse';
      }
      var images = root.querySelectorAll('img');
      for (var k = 0; k < images.length; k++) {
        images[k].style.maxWidth = '100%';
        images[k].style.height = 'auto';
      }
    },

    initMaterialPanel() {
      if (!this.$el || !document.body || this._materialPanel) return;
      var toolbar = this.$el.querySelector('.pa-toolbar');
      var top = (toolbar && toolbar.offsetHeight) || 56;

      var panel = document.createElement('div');
      panel.className = 'pa-material-dock';
      panel.style.cssText = 'position:fixed;left:50%;transform:translateX(-50%);' +
        'width:min(960px,100%);z-index:950;background:#fff;border-bottom:1px solid #E5EAF2;' +
        'box-shadow:0 4px 14px rgba(15,23,42,.08);box-sizing:border-box;display:none;';

      var head = document.createElement('div');
      head.style.cssText = 'display:flex;align-items:center;justify-content:space-between;' +
        'gap:12px;padding:8px 16px;background:#F7F9FC;border-bottom:1px solid #EDF1F7;';
      var title = document.createElement('div');
      title.textContent = '📄 本组材料';
      title.style.cssText = 'font-size:14px;font-weight:700;color:#1A3C6D;';
      var toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.textContent = '收起';
      toggle.style.cssText = 'border:1px solid #D8E0EC;background:#fff;color:#1A3C6D;' +
        'border-radius:999px;padding:3px 12px;font-size:12px;cursor:pointer;';
      head.appendChild(title);
      head.appendChild(toggle);

      var body = document.createElement('div');
      body.style.cssText = 'padding:12px 16px;max-height:30vh;overflow:auto;' +
        'overscroll-behavior:contain;line-height:1.8;color:#333;font-size:14px;';

      panel.appendChild(head);
      panel.appendChild(body);
      // 挂在页面根节点内，和顶栏处于同一 stacking context，避免被遮罩层压住
      this.$el.appendChild(panel);

      this._materialPanel = panel;
      this._materialBody = body;
      this._materialTitle = title;
      this._materialToggle = toggle;
      this._matCollapsed = false;
      var self = this;
      toggle.onclick = function() {
        self._matCollapsed = !self._matCollapsed;
        self.applyMaterialPanelLayout();
      };
      this.applyMaterialPanelLayout();
    },

    applyMaterialPanelLayout() {
      var panel = this._materialPanel;
      if (!panel) return;
      var toolbar = this.$el && this.$el.querySelector ? this.$el.querySelector('.pa-toolbar') : null;
      var top = (toolbar && toolbar.offsetHeight) || 56;
      panel.style.top = top + 'px';
      if (this._materialBody) {
        this._materialBody.style.display = this._matCollapsed ? 'none' : 'block';
      }
      if (this._materialToggle) {
        this._materialToggle.textContent = this._matCollapsed ? '展开' : '收起';
      }
      var main = this.$el ? this.$el.querySelector('.pa-main') : null;
      if (main) {
        var extra = panel.style.display === 'none' ? 0 : (panel.offsetHeight || 0);
        main.style.paddingTop = (top + extra) + 'px';
      }
    },

    syncMaterialPanel() {
      if (!this._materialPanel) this.initMaterialPanel();
      var panel = this._materialPanel;
      if (!panel) return;
      var q = this.getCurrentMaterialQuestion();
      if (!q) {
        panel.style.display = 'none';
        this.applyMaterialPanelLayout();
        return;
      }
      panel.style.display = 'block';
      var gid = String(q.groupId || '');
      if (panel.getAttribute('data-group-id') !== gid) {
        panel.setAttribute('data-group-id', gid);
        if (this._materialBody) {
          this._materialBody.innerHTML = q.materialHtml;
          this.formatMaterialBody(this._materialBody);
          this._materialBody.scrollTop = 0;
        }
        if (this._materialTitle) {
          var qs = this.questionsParsed || [];
          var first = -1, last = -1;
          for (var i = 0; i < qs.length; i++) {
            if (String(qs[i].groupId || '') === gid) {
              if (first < 0) first = i;
              last = i;
            }
          }
          this._materialTitle.textContent = '📄 本组材料' +
            (first >= 0 && last > first ? ' · 第 ' + (first + 1) + '–' + (last + 1) + ' 题' : '');
        }
      }
      this.applyMaterialPanelLayout();
    },

    // 把材料块插入到每组首题的题干之前（不改模板，遵守 raw 页 template 红线）
    mountGroupMaterials() {
      if (!this.$el || !this.$el.querySelectorAll) return;
      var qs = this.questionsParsed;
      var blocks = this.$el.querySelectorAll('.question-block');
      if (!blocks.length) return;

      for (var i = 0; i < qs.length && i < blocks.length; i++) {
        var q = qs[i];
        var block = blocks[i];
        var existing = block.querySelector('.pa-group-material');
        if (!q.materialHtml) {
          if (existing) existing.parentNode.removeChild(existing);
          continue;
        }
        if (existing && existing.getAttribute('data-group-id') === String(q.groupId)) continue;
        if (existing) existing.parentNode.removeChild(existing);

        var box = document.createElement('div');
        box.className = 'pa-group-material';
        box.setAttribute('data-group-id', String(q.groupId));
        // 内联样式：避免改动 raw 页的 <style> 与 <template>
        box.style.cssText = 'margin:0 0 16px;padding:14px 16px;background:#f7f9fc;' +
          'border-left:3px solid #1A3C6D;border-radius:6px;line-height:1.8;color:#333;' +
          'word-break:break-word;overflow-x:auto;';

        var label = document.createElement('div');
        label.textContent = '材料';
        label.style.cssText = 'font-weight:700;color:#1A3C6D;margin-bottom:8px;font-size:14px;';
        box.appendChild(label);

        var body = document.createElement('div');
        body.innerHTML = q.materialHtml;
        // 表格/图片在窄屏下不撑破卡片
        var tables = body.querySelectorAll('table');
        for (var t = 0; t < tables.length; t++) {
          tables[t].style.maxWidth = '100%';
          tables[t].style.borderCollapse = 'collapse';
        }
        var images = body.querySelectorAll('img');
        for (var k = 0; k < images.length; k++) {
          images[k].style.maxWidth = '100%';
          images[k].style.height = 'auto';
        }
        box.appendChild(body);

        var stem = block.querySelector('.q-stem');
        if (stem) block.insertBefore(box, stem);
        else block.insertBefore(box, block.firstChild);
      }

      // 组首内联材料在吸顶面板中出现一次即可，避免同屏重复两遍；
      // 面板收起时仍可通过固定栏“展开”重新查看。
      var inlines = this.$el.querySelectorAll('.pa-group-material');
      for (var m = 0; m < inlines.length; m++) inlines[m].style.display = 'none';
      this.initMaterialPanel();
      this.syncMaterialPanel();
    },

    // 顶栏固定在视口顶部：XMask 内容区常带 overflow:hidden，
    // 原生 position:sticky 会失效（实测滚动后工具栏消失）。改由脚本设 fixed，
    // 并给主体补同高 padding，避免第一题被遮住。
    ensureToolbarFixed() {
      if (!this.$el || !this.$el.querySelector) return;
      var toolbar = this.$el.querySelector('.pa-toolbar');
      if (!toolbar) return;
      var height = toolbar.offsetHeight || 56;
      toolbar.style.position = 'fixed';
      toolbar.style.top = '0';
      toolbar.style.left = '0';
      toolbar.style.right = '0';
      toolbar.style.width = '100%';
      toolbar.style.zIndex = '1000';
      toolbar.style.boxSizing = 'border-box';
      var main = this.$el.querySelector('.pa-main');
      if (main) main.style.paddingTop = height + 'px';
      // 吸顶材料面板若已创建，padding 需同时让出面板高度
      this.applyMaterialPanelLayout();
    },

    // ===== 滚动联动 =====
    // 找到题块所在的可滚动祖先（XMask 内容区通常是内部滚动容器，不是 window）
    getScrollParent(el) {
      var node = el && el.parentElement;
      while (node && node !== document.body && node !== document.documentElement) {
        var style = window.getComputedStyle(node);
        var oy = style.overflowY;
        if ((oy === 'auto' || oy === 'scroll' || oy === 'overlay') &&
            node.scrollHeight > node.clientHeight + 2) {
          return node;
        }
        node = node.parentElement;
      }
      return null;
    },

    // 主动滚动到第 idx 题；顶部留出吸顶工具栏高度
    scrollToIndex(idx, smooth) {
      var qs = this.questionsParsed;
      if (idx < 0 || idx >= qs.length) return;
      var ref = this.$refs['q_' + qs[idx].id];
      var el = Array.isArray(ref) ? ref[0] : ref;
      if (!el || !el.getBoundingClientRect) return;

      this._scrollLockUntil = Date.now() + 900; // 平滑滚动期间忽略 scroll 回写
      var scroller = this.getScrollParent(el);
      var offset = this.getTopOffset(); // 工具栏 + 吸顶材料面板高度 + 间距
      if (scroller) {
        var top = el.getBoundingClientRect().top - scroller.getBoundingClientRect().top +
          scroller.scrollTop - offset;
        scroller.scrollTo({ top: Math.max(0, top), behavior: smooth ? 'smooth' : 'auto' });
      } else {
        var winTop = el.getBoundingClientRect().top + (window.pageYOffset || 0) - offset;
        window.scrollTo({ top: Math.max(0, winTop), behavior: smooth ? 'smooth' : 'auto' });
      }
    },

    // 滚动时反推当前题号：取最后一个已到达顶部阈值（72px 工具栏下方）的题块
    onScroll() {
      if (this._scrollRaf) return;
      var self = this;
      this._scrollRaf = requestAnimationFrame(function() {
        self._scrollRaf = null;
        if (Date.now() < (self._scrollLockUntil || 0)) return;
        if (!self.$el || !self.$el.querySelectorAll) return;
        var blocks = self.$el.querySelectorAll('.question-block');
        if (!blocks.length) return;

        var threshold = self.getTopOffset() + 4;
        var idx = 0;
        for (var i = 0; i < blocks.length; i++) {
          if (blocks[i].getBoundingClientRect().top <= threshold) idx = i;
          else break;
        }
        // 滚到底部时，最后几题可能永远到不了阈值，直接判为最后一题
        var scroller = self.getScrollParent(blocks[0]);
        if (scroller && scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 4) {
          idx = blocks.length - 1;
        } else if (!scroller) {
          var doc = document.documentElement;
          if ((window.pageYOffset || 0) + window.innerHeight >= doc.scrollHeight - 4) {
            idx = blocks.length - 1;
          }
        }

        if (idx !== self.state.currentIndex) {
          self._syncingFromScroll = true;
          self.state.currentIndex = idx;
          self.$nextTick(function() {
            setTimeout(function() { self._syncingFromScroll = false; }, 50);
          });
        }
      });
    },

    // ===== 计时器 =====
    startTimer() {
      var self = this;
      this._timer = setInterval(function() {
        if (self.state.timeLeft > 0) {
          self.state.timeLeft--;
        } else {
          self.confirmSubmit();
        }
      }, 1000);
    },

    // ===== 自动保存 =====
    startAutoSave() {
      var self = this;
      this._autoSave = setInterval(function() { self.saveProgress(); }, 30000);
    },

    saveProgress() {
      if (!this.state.paperId || !this.state.recordId) return;
      try {
        var progress = {
          answers: this.state.answers,
          markedQuestions: this.state.markedQuestions,
          currentIndex: this.state.currentIndex,
          timeLeft: this.state.timeLeft,
          timestamp: Date.now(),
        };
        localStorage.setItem('paper_progress_' + this.state.recordId, JSON.stringify(progress));
      } catch(e) {}
    },

    restoreProgress() {
      if (!this.state.recordId) return;
      try {
        var raw = localStorage.getItem('paper_progress_' + this.state.recordId);
        if (!raw) return;
        var progress = JSON.parse(raw);
        // 24小时内有效
        if (Date.now() - progress.timestamp > 86400000) return;
        if (progress.answers) this.state.answers = progress.answers;
        if (progress.markedQuestions) this.state.markedQuestions = progress.markedQuestions;
        if (progress.currentIndex !== undefined) this.state.currentIndex = progress.currentIndex;
        if (progress.timeLeft !== undefined) this.state.timeLeft = progress.timeLeft;
      } catch(e) {}
    },

    // ===== 选项操作 =====
    selectOption(qId, value, type) {
      if (this.state.showResult) return;
      var answers = JSON.parse(this.state.answers || '{}');

      if (this.getRenderMode(type) === 'textarea') {
        // 主观题：直接存储文本
        answers[qId] = value;
      } else if (this.getRenderMode(type) === 'checkbox') {
        // 多选题：toggle
        var cur = answers[qId] || [];
        if (!Array.isArray(cur)) cur = [cur];
        if (cur.indexOf(value) >= 0) {
          answers[qId] = cur.filter(function(v) { return v !== value; });
        } else {
          answers[qId] = cur.concat([value]);
        }
      } else {
        // 单选题：替换
        answers[qId] = value;
      }
      this.state.answers = JSON.stringify(answers);
    },

    isOptionSelected(qId, oidx) {
      var answers = this.answersParsed;
      var ans = answers[qId];
      if (Array.isArray(ans)) return ans.indexOf(oidx) >= 0;
      return ans === oidx;
    },

    getTextAnswer(qId) {
      var answers = this.answersParsed;
      var ans = answers[qId];
      return (typeof ans === 'string' && !['0','1','2','3','4','5','6','7'].includes(ans)) ? ans : '';
    },

    // ===== 标记 =====
    toggleMark(qId) {
      var arr = this.markedParsed.slice();
      var idx = arr.indexOf(qId);
      if (idx >= 0) { arr.splice(idx, 1); }
      else { arr.push(qId); }
      this.state.markedQuestions = JSON.stringify(arr);
    },

    // ===== 导航 =====
    jumpTo(idx) {
      var qs = this.questionsParsed;
      if (idx < 0 || idx >= qs.length) return;
      this.state.sheetVisible = false;
      // 本方法自己负责滚动，屏蔽 currentIndex watcher 的二次滚动
      this._suppressScrollWatch = true;
      this.state.currentIndex = idx;
      var self = this;
      this.$nextTick(function() {
        self.scrollToIndex(idx, true);
        setTimeout(function() { self._suppressScrollWatch = false; }, 100);
      });
    },

    toggleSheet() {
      this.state.sheetVisible = !this.state.sheetVisible;
    },

    // ===== 退出 =====
    handleExit() { this.state.showExitDialog = true; },
    saveAndExit() {
      this.saveProgress();
      this.$router.push('/student/papers');
    },

    // ===== 交卷 =====
    handleSubmit() { this.state.showSubmitDialog = true; },

    async confirmSubmit() {
      this.state.showSubmitDialog = false;
      var answers = this.answersParsed;
      var qs = this.questionsParsed;
      var self = this;

      // 构建提交格式：{qid: answer_letter_string}
      var submitAnswers = {};
      Object.keys(answers).forEach(function(qid) {
        var a = answers[qid];
        if (Array.isArray(a)) {
          submitAnswers[qid] = a.map(function(i) { return self.state.optionLabels[i]; }).sort().join(',');
        } else if (typeof a === 'string' && isNaN(parseInt(a))) {
          // 文本答案（主观题）
          submitAnswers[qid] = a;
        } else if (typeof a === 'number' || (typeof a === 'string' && !isNaN(parseInt(a)))) {
          // 数字索引 → 字母
          submitAnswers[qid] = self.state.optionLabels[parseInt(a)] || '';
        }
      });

      // 补充未答题为空
      qs.forEach(function(q) {
        if (!(q.id in submitAnswers)) {
          submitAnswers[q.id] = '';
        }
      });

      try {
        var timeSpent = Math.max(0, this.state.totalDuration - this.state.timeLeft);
        var res = await window.__VTJ_AUTH__.apiFetch('/api/exams/' + this.state.recordId + '/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          // 后端 /api/exams/{record_id}/submit 的请求体就是 {题目ID: 答案}，不能再包一层 answers
          body: JSON.stringify(submitAnswers),
        });
        if (!res.ok) {
          var e = await res.json();
          throw new Error(e.detail || '提交失败');
        }
        var data = await res.json();
        this.state.submitScore = data.data ? data.data.total_score : (data.total_score || 0);
        this.state.submitMaxScore = data.data ? data.data.max_score : (data.max_score || 100);
        this.state.submitAccuracy = data.data ? Math.round((this.state.submitScore / this.state.submitMaxScore) * 100) : 0;
        this.state.submitCorrect = data.data ? (data.data.scored_count || 0) : 0;
        this.state.submitWrong = this.totalQuestions - this.state.submitCorrect;
        this.state.submitTimeSpent = timeSpent;
        this.state.showResult = true;
        this.state.showResultDialog = true;

        if (this._timer) clearInterval(this._timer);
        if (this._autoSave) clearInterval(this._autoSave);
        // 清除进度
        localStorage.removeItem('paper_progress_' + this.state.recordId);
      } catch(err) {
        alert('提交失败: ' + (err.message || '网络错误'));
      }
    },

    // ===== 结果 =====
    isCorrect(q) {
      // 仅在showResult后有效（考试模式下没有answer字段，无法判断）
      return false;
    },

    isCorrectOption(q, oidx) {
      if (!this.state.showResult) return false;
      var correctLetter = q.answer;
      if (!correctLetter) return false;
      return this.state.optionLabels[oidx] === correctLetter;
    },

    viewDetails() {
      this.$router.push('/paper-result?record_id=' + this.state.recordId);
    },

    goBackToList() {
      this.$router.push('/student/papers');
    },
  },

  mounted() {
    // 上一题/下一题按钮直接改 state.currentIndex，模板不能改，
    // 因此用 watcher 把题号变化接到滚动上；滚动反推题号时用 _syncingFromScroll 防回环。
    var self = this;
    this._unwatchIndex = this.$watch(
      function() { return self.state.currentIndex; },
      function(nv, ov) {
        if (nv === ov) return;
        // 题号先变、滚动后到：材料面板必须先跟随题号切换，
        // 即使是滚动反推的题号也要更新面板，否则组间滚动时材料会滞后一题。
        self.syncMaterialPanel();
        if (self._suppressScrollWatch || self._syncingFromScroll) return;
        self.scrollToIndex(nv, true);
      }
    );
    this._onScroll = this.onScroll.bind(this);
    // capture=true：滚动事件不冒泡，但捕获阶段能收到内部滚动容器的事件
    window.addEventListener('scroll', this._onScroll, true);

    ensureMaterialStyles();
    this.ensureToolbarFixed();
    this._onResize = this.ensureToolbarFixed.bind(this);
    window.addEventListener('resize', this._onResize);

    this.loadQuestions();
    this.startTimer();
    this.startAutoSave();
  },

  beforeUnmount() {
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
    if (this._autoSave) { clearInterval(this._autoSave); this._autoSave = null; }
    if (this._scrollRaf) { cancelAnimationFrame(this._scrollRaf); this._scrollRaf = null; }
    if (this._unwatchIndex) { this._unwatchIndex(); this._unwatchIndex = null; }
    if (this._onScroll) {
      window.removeEventListener('scroll', this._onScroll, true);
      this._onScroll = null;
    }
    if (this._onResize) {
      window.removeEventListener('resize', this._onResize);
      this._onResize = null;
    }
    if (this._materialPanel && this._materialPanel.parentNode) {
      this._materialPanel.parentNode.removeChild(this._materialPanel);
    }
    this._materialPanel = null;
    this._materialBody = null;
    this._materialTitle = null;
    this._materialToggle = null;
    this.saveProgress();
  },
});
</script>

<style scoped>
.paper-answer-page { min-height: 100vh; background: #f0f2f5; font-size: 15px; }
.pa-main { max-width: 960px; margin: 0 auto; padding-bottom: 72px; }

/* 工具栏 */
.pa-toolbar { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px;
  background: #fff; border-bottom: 1px solid #e8e8e8; position: sticky; top: 0; z-index: 100; }
.toolbar-left { display: flex; align-items: center; gap: 12px; }
.toolbar-right { display: flex; align-items: center; gap: 12px; }
.tool-btn { display: flex; align-items: center; gap: 4px; padding: 6px 14px; background: #f0f2f5;
  border: 1px solid #d9d9d9; border-radius: 6px; cursor: pointer; font-size: 14px; }
.paper-name { font-size: 14px; color: #666; font-weight: 500; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.progress-text { font-weight: 600; color: #1A3C6D; }
.timer-display { display: flex; align-items: center; gap: 4px; padding: 4px 12px; background: #f5f5f5; border-radius: 20px; }
.timer-text { font-weight: 700; font-size: 16px; color: #1A3C6D; font-variant-numeric: tabular-nums; }
.timer-text.urgent { color: #c41e3a; animation: pulse 1s infinite; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
.exit-btn { display: flex; align-items: center; gap: 4px; padding: 6px 14px; background: #c41e3a;
  color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }

/* 主体 */
.pa-body { display: flex; gap: 0; margin-top: 8px; }

/* 答题卡 */
.sheet-panel { width: 280px; min-width: 280px; background: #fff; border-radius: 8px; padding: 16px;
  margin-right: 12px; height: fit-content; position: sticky; top: 72px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.sheet-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.sheet-header h4 { margin: 0; color: #1A3C6D; }
.sheet-close { cursor: pointer; font-size: 18px; color: #999; }
.sheet-stats { display: flex; gap: 16px; margin-bottom: 12px; font-size: 13px; color: #666; }
.sheet-stats b { color: #1A3C6D; }
.sheet-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-bottom: 16px; }
.sheet-num { width: 100%; aspect-ratio: 1; border: 1px solid #d9d9d9; border-radius: 4px; background: #fff;
  cursor: pointer; font-size: 13px; display: flex; align-items: center; justify-content: center; }
.sheet-num.answered { background: #e6f0ff; border-color: #409EFF; color: #409EFF; }
.sheet-num.active { border-color: #1A3C6D; box-shadow: 0 0 0 2px rgba(26,60,109,0.3); font-weight: 700; }
.sheet-num.marked { background: #fff7e6; border-color: #fa8c16; }
.submit-btn { width: 100%; padding: 10px; background: #c41e3a; color: #fff; border: none; border-radius: 6px;
  cursor: pointer; font-size: 15px; font-weight: 600; }

/* 题目区 */
.question-area { flex: 1; min-width: 0; }
.question-scroll { display: flex; flex-direction: column; gap: 16px; }
.question-block { background: #fff; border-radius: 8px; padding: 24px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
.q-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.q-number { font-weight: 700; font-size: 16px; color: #1A3C6D; }
.q-type-badge { padding: 2px 8px; border-radius: 10px; font-size: 12px; background: #e6f0ff; color: #409EFF; }
.q-type-badge.multi { background: #fff7e6; color: #e6a23c; }
.q-type-badge.essay { background: #f0f5e8; color: #67c23a; }
.q-score { font-size: 12px; color: #999; }
.mark-badge { font-size: 12px; color: #fa8c16; }
.q-stem { line-height: 1.8; color: #333; margin: 0 0 16px; word-break: break-word; }
.q-stem :deep(img.q-img) { max-width: 100%; border-radius: 4px; margin: 8px 0; }

/* 选项 */
.q-options { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.multi-hint { font-size: 13px; color: #e6a23c; margin-bottom: 4px; }
.option-item { display: flex; align-items: flex-start; gap: 10px; padding: 12px 16px;
  border: 1px solid #e8e8e8; border-radius: 8px; cursor: pointer; transition: all 0.15s; }
.option-item:hover { border-color: #409EFF; background: #f0f7ff; }
.option-item.selected { border-color: #409EFF; background: #e6f0ff; font-weight: 500; }
.option-item.correct { border-color: #67c23a; background: #f0f9eb; }
.option-item.wrong { border-color: #f56c6c; background: #fef0f0; }
.option-marker { font-size: 18px; color: #bbb; min-width: 20px; }
.option-item.selected .option-marker { color: #409EFF; }
.option-label { font-weight: 600; color: #666; min-width: 22px; }
.option-text { flex: 1; line-height: 1.6; }
.option-text :deep(img.q-img) { max-width: 200px; max-height: 150px; border-radius: 4px; }

/* 文本框 */
.q-textarea { margin-bottom: 16px; }
.answer-textarea { width: 100%; padding: 16px; border: 2px solid #d9d9d9; border-radius: 8px;
  font-size: 15px; line-height: 1.8; resize: vertical; font-family: inherit; outline: none; box-sizing: border-box; }
.answer-textarea:focus { border-color: #409EFF; }
.answer-textarea.writing { min-height: 400px; font-size: 16px; line-height: 2; }

/* 结果 */
.q-result { padding: 12px; background: #f9f9f9; border-radius: 6px; margin-top: 8px; }
.result-badge { display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 13px; font-weight: 600; }
.correct-badge { background: #f0f9eb; color: #67c23a; }
.incorrect-badge { background: #fef0f0; color: #f56c6c; }
.result-explain { margin-top: 8px; color: #666; font-size: 14px; line-height: 1.6; }

/* 操作 */
.q-actions { display: flex; gap: 8px; margin-top: 8px; }
.mark-btn { padding: 6px 16px; border: 1px solid #d9d9d9; border-radius: 16px; background: #fff;
  cursor: pointer; font-size: 13px; color: #666; }
.mark-btn.marked { background: #fff7e6; border-color: #fa8c16; color: #fa8c16; }

/* 底部导航 */
.pa-nav { display: flex; align-items: center; justify-content: center; gap: 16px; padding: 12px 16px;
  background: #fff; border-top: 1px solid #e8e8e8; position: fixed; bottom: 0; left: 0; right: 0; z-index: 100; }
.nav-btn { padding: 8px 20px; background: #f0f2f5; border: 1px solid #d9d9d9; border-radius: 6px;
  cursor: pointer; font-size: 14px; }
.nav-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.nav-progress { font-weight: 600; color: #1A3C6D; min-width: 80px; text-align: center; }
.submit-main-btn { padding: 8px 24px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px;
  cursor: pointer; font-size: 15px; font-weight: 600; }
.submit-main-btn:hover { background: #2a4f80; }

/* 模态弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.35); display: flex;
  align-items: center; justify-content: center; z-index: 1000; }
.modal-dialog { background: #fff; border-radius: 12px; padding: 32px; max-width: 420px; width: 90%;
  text-align: center; box-shadow: 0 8px 32px rgba(0,0,0,0.12); }
.modal-dialog h4 { margin: 0 0 12px; color: #1A3C6D; font-size: 18px; }
.modal-dialog p { color: #666; margin: 0 0 20px; }
.modal-actions { display: flex; gap: 12px; justify-content: center; }
.pa-btn { padding: 10px 24px; border-radius: 6px; cursor: pointer; font-size: 14px; border: none; }
.back-btn { background: #f0f2f5; color: #666; }
.generate-btn { background: #1A3C6D; color: #fff; }
.outline-btn { background: #fff; color: #1A3C6D; border: 1px solid #1A3C6D; }

/* 成绩弹窗 */
.result-dialog { max-width: 480px; }
.result-icon { font-size: 48px; margin-bottom: 8px; }
.result-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 16px; }
.rs-item { display: flex; flex-direction: column; gap: 4px; padding: 12px; background: #f5f7fa; border-radius: 8px; }
.rs-label { font-size: 12px; color: #999; }
.rs-value { font-size: 20px; font-weight: 700; color: #1A3C6D; }
.rs-value.score { color: #c41e3a; }
.rs-value.green { color: #67c23a; }
.result-hint { font-size: 13px; color: #67c23a; margin-bottom: 20px; }

/* 加载/空状态 */
.loading-state, .empty-state { text-align: center; padding: 60px 0; color: #999; }
.loading-spinner { width: 40px; height: 40px; border: 3px solid #e8e8e8; border-top-color: #409EFF;
  border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 16px; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
