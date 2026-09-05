<!-- 智能组卷页面 — 三步流程：参数配置 → 预览微调 → 确认生成 -->
<template>
  <div class="smart-exam-page">
    <NavBar></NavBar>
    <main class="se-main">
      <!-- ===== Step 1: 参数配置 ===== -->
      <div v-if="state.step === 1" class="se-step">
        <div class="se-hero">
          <h1 class="se-title">🎯 智能组卷</h1>
          <p class="se-subtitle">根据你的需求，智能生成专属练习试卷</p>
        </div>
        <!-- 科目选择 -->
        <div class="se-card">
          <h3 class="card-title">📚 科目选择</h3>
          <div class="subject-options">
            <button v-for="opt in subjectOptions" :key="opt.value"
              :class="['subject-btn', { active: state.fm_subjectMode === opt.value }]"
              @click="selectSubject(opt.value)">
              <span class="subject-icon">{{ opt.icon }}</span>
              <span class="subject-label">{{ opt.label }}</span>
            </button>
          </div>
          <div v-if="state.fm_subjectMode === 'mixed'" class="mixed-ratio">
            <label>行测 {{ state.fm_xingceRatio }}%</label>
            <input type="range" v-model.number="state.fm_xingceRatio" min="10" max="90" step="5" />
            <label>公专 {{ 100 - state.fm_xingceRatio }}%</label>
          </div>
        </div>
        <!-- 年份范围 -->
        <div class="se-card">
          <h3 class="card-title">📅 年份范围</h3>
          <div class="year-options">
            <button v-for="yr in yearOptions" :key="yr.value"
              :class="['year-btn', { active: state.fm_yearRange === yr.value }]"
              @click="state.fm_yearRange = yr.value">{{ yr.label }}</button>
          </div>
        </div>
        <!-- 难度分布 -->
        <div class="se-card">
          <h3 class="card-title">📊 难度分布</h3>
          <div class="difficulty-sliders">
            <div class="diff-item">
              <div class="diff-header"><span>简单</span><span>{{ state.fm_difficultyEasy }}%</span></div>
              <input type="range" v-model.number="state.fm_difficultyEasy" min="0" max="100" step="5" />
            </div>
            <div class="diff-item">
              <div class="diff-header"><span>中等</span><span>{{ state.fm_difficultyMedium }}%</span></div>
              <input type="range" v-model.number="state.fm_difficultyMedium" min="0" max="100" step="5" />
            </div>
            <div class="diff-item">
              <div class="diff-header"><span>困难</span><span>{{ state.fm_difficultyHard }}%</span></div>
              <input type="range" v-model.number="state.fm_difficultyHard" min="0" max="100" step="5" />
            </div>
          </div>
        </div>
        <!-- 题型配置 -->
        <div class="se-card">
          <h3 class="card-title">📝 题型配置</h3>
          <div class="type-configs">
            <div v-for="(cfg, idx) in questionConfigParsed" :key="idx" class="type-row">
              <span class="type-name">{{ cfg.label }}</span>
              <input type="number" v-model.number="cfg.count" min="0" max="200" class="type-input" />
              <span class="type-unit">题 ×</span>
              <input type="number" v-model.number="cfg.score" min="0.5" max="50" step="0.5" class="type-input score-input" />
              <span class="type-unit">分</span>
            </div>
          </div>
          <div class="type-summary">
            <span>总题量: <b>{{ totalQuestions }}</b></span>
            <span>总分: <b>{{ totalScore }}</b></span>
            <span>建议用时: <b>{{ estimatedDuration }}</b>分钟</span>
          </div>
        </div>
        <div class="se-actions">
          <button class="se-btn back-btn" @click="goBack">← 返回</button>
          <button class="se-btn generate-btn" @click="doGenerate" :disabled="state.generating">
            <span v-if="state.generating" class="btn-spinner"></span>
            {{ state.generating ? '正在智能生成...' : '✨ 智能生成' }}
          </button>
        </div>
      </div>

      <!-- ===== Step 2: 预览微调 ===== -->
      <div v-if="state.step === 2" class="se-step">
        <div class="se-hero preview-hero">
          <h1 class="se-title">📋 试卷预览</h1>
          <p class="se-subtitle">{{ state.gp_paperName }} · {{ state.gp_questionCount }}题 · 总分{{ state.gp_totalScore }}分</p>
          <div class="preview-stats">
            <span class="stat-tag easy-tag">简单 {{ state.gp_difficultyEasy }}题</span>
            <span class="stat-tag medium-tag">中等 {{ state.gp_difficultyMedium }}题</span>
            <span class="stat-tag hard-tag">困难 {{ state.gp_difficultyHard }}题</span>
          </div>
        </div>
        <div class="se-card question-list-card">
          <div v-for="(q, idx) in gp_questionsParsed" :key="q.question_id"
            :class="['question-item', { expanded: state.expandedQuestion === q.question_id }]"
            @click="toggleDetail(q.question_id)">
            <div class="qi-header">
              <span class="qi-number">#{{ idx + 1 }}</span>
              <span :class="['qi-type', q.difficulty <= 2 ? 'easy' : q.difficulty >= 4 ? 'hard' : '']">{{ q.type_name }}</span>
              <span class="qi-difficulty">{{ '★'.repeat(q.difficulty) }}{{ '☆'.repeat(5 - q.difficulty) }}</span>
              <span v-if="q.subcategory" class="qi-subcat">{{ q.subcategory }}</span>
            </div>
            <p class="qi-content">{{ q.question_content }}</p>
            <div class="qi-actions">
              <button class="qi-btn replace-btn" @click.stop="openReplace(q, idx)">🔄 换一题</button>
            </div>
          </div>
        </div>
        <!-- 替换弹窗 -->
        <div v-if="state.showReplaceDialog" class="replace-overlay" @click.self="closeReplace">
          <div class="replace-dialog">
            <h4>🔄 替换题目</h4>
            <p class="replace-tip">点击下方按钮向服务器请求同类型候选题并自动替换</p>
            <div class="replace-actions">
              <button class="se-btn back-btn" @click="closeReplace">取消</button>
              <button class="se-btn generate-btn" @click="doReplace" :disabled="state.replaceLoading">
                {{ state.replaceLoading ? '替换中...' : '确认替换（随机抽取）' }}
              </button>
            </div>
          </div>
        </div>
        <div class="se-actions">
          <button class="se-btn back-btn" @click="regenerate">🔄 重新生成</button>
          <button class="se-btn outline-btn" @click="state.step = 1">📝 修改参数</button>
          <button class="se-btn generate-btn" @click="confirmPaper">✅ 确认生成</button>
        </div>
      </div>

      <!-- ===== Step 3: 确认与答题入口 ===== -->
      <div v-if="state.step === 3" class="se-step">
        <div class="se-card confirm-card">
          <div class="confirm-icon">✅</div>
          <h2>试卷已生成成功！</h2>
          <div class="confirm-info">
            <div class="ci-row"><span>📄 试卷名称</span><span>{{ state.gp_paperName }}</span></div>
            <div class="ci-row"><span>📚 题量与分数</span><span>{{ state.gp_questionCount }}题 · 总分{{ state.gp_totalScore }}分</span></div>
            <div class="ci-row"><span>⏱ 建议用时</span><span>{{ state.gp_duration }}分钟</span></div>
          </div>
          <div class="confirm-actions">
            <button class="se-btn outline-btn" @click="state.step = 2">📝 微调题目</button>
            <button class="se-btn back-btn" @click="regenerate">🔄 重新生成</button>
          </div>
          <button class="start-answer-btn" @click="startAnswer">
            <span>🚀 开始答题</span>
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive } from 'vue';
import NavBar from './navbar.vue';
import { useProvider } from '@vtj/renderer';

const XINGCE_PRESET = [
  { subject_id: 1, type_id: 1, label: '常识判断', count: 20, score: 1.0, subcategory: '常识判断' },
  { subject_id: 1, type_id: 1, label: '言语理解', count: 30, score: 1.0, subcategory: '言语理解与表达' },
  { subject_id: 1, type_id: 1, label: '数量关系', count: 10, score: 1.0, subcategory: '数量关系' },
  { subject_id: 1, type_id: 1, label: '判断推理', count: 35, score: 1.0, subcategory: '判断推理' },
  { subject_id: 1, type_id: 1, label: '资料分析', count: 15, score: 1.0, subcategory: '资料分析' },
  { subject_id: 1, type_id: 1, label: '政治理论', count: 10, score: 1.0, subcategory: '政治理论' },
];
const SHENLUN_PRESET = [
  { subject_id: 2, type_id: 4, label: '归纳概括', count: 1, score: 20.0, subcategory: '归纳概括' },
  { subject_id: 2, type_id: 4, label: '综合分析', count: 1, score: 25.0, subcategory: '综合分析' },
  { subject_id: 2, type_id: 4, label: '应用文写作', count: 1, score: 25.0, subcategory: '应用文写作' },
  { subject_id: 2, type_id: 5, label: '议论文写作', count: 1, score: 30.0, subcategory: '议论文写作' },
];
const GONGZHUAN_PRESET = [
  { subject_id: 3, type_id: 1, label: '单选题', count: 50, score: 1.0, subcategory: '' },
  { subject_id: 3, type_id: 2, label: '多选题', count: 20, score: 1.5, subcategory: '' },
  { subject_id: 3, type_id: 3, label: '情境题', count: 30, score: 1.0, subcategory: '' },
];

const SUBJECT_OPTIONS = [
  { value: 'xingce', label: '行测', icon: '📝' },
  { value: 'shenlun', label: '申论', icon: '📄' },
  { value: 'gongzhuan', label: '公专', icon: '🛡️' },
  { value: 'mixed', label: '混合', icon: '🔀' },
];
const YEAR_OPTIONS = [
  { value: '3', label: '近三年' },
  { value: '5', label: '近五年' },
  { value: '10', label: '近十年' },
  { value: 'all', label: '全部年份' },
];

export default defineComponent({
  name: 'SmartExam',
  components: { NavBar },
  setup(props) {
    const provider = useProvider({ id: 'smart_exam', version: '1785854718491' });

    const state = reactive({
      step: 1,
      generating: false,
      // 生成结果字段 (gp_)
      gp_paperId: null,
      gp_paperName: '',
      gp_paperCode: '',
      gp_questions: '[]',
      gp_totalScore: 0,
      gp_questionCount: 0,
      gp_difficultyEasy: 0,
      gp_difficultyMedium: 0,
      gp_difficultyHard: 0,
      gp_subjectBreakdown: '{}',
      gp_duration: 120,
      // 表单字段 (fm_)
      fm_subjectMode: 'xingce',
      fm_yearRange: 'all',
      fm_difficultyEasy: 20,
      fm_difficultyMedium: 50,
      fm_difficultyHard: 30,
      fm_xingceRatio: 60,
      fm_gongzhuanRatio: 40,
      fm_questionConfigs: '[]',
      // 替换弹窗
      expandedQuestion: null,
      showReplaceDialog: false,
      replaceLoading: false,
      replaceQid: null,
      replaceIdx: -1,
    });

    // 初始化默认题型配置
    state.fm_questionConfigs = JSON.stringify(XINGCE_PRESET);

    return { state, props, provider, subjectOptions: SUBJECT_OPTIONS, yearOptions: YEAR_OPTIONS };
  },
  computed: {
    questionConfigParsed() {
      try { return JSON.parse(this.state.fm_questionConfigs); } catch(e) { return []; }
    },
    gp_questionsParsed() {
      try { return JSON.parse(this.state.gp_questions); } catch(e) { return []; }
    },
    totalQuestions() {
      var cfgs = this.questionConfigParsed;
      return cfgs.reduce(function(s, c) { return s + (c.count || 0); }, 0);
    },
    totalScore() {
      var cfgs = this.questionConfigParsed;
      return cfgs.reduce(function(s, c) { return s + (c.count || 0) * (c.score || 1); }, 0);
    },
    estimatedDuration() {
      var q = this.totalQuestions;
      if (this.state.fm_subjectMode === 'shenlun') return 150;
      return Math.round(q * 1.0);
    },
  },
  methods: {
    // ===== 科目切换 =====
    selectSubject(mode) {
      this.state.fm_subjectMode = mode;
      var cfgs;
      if (mode === 'xingce') cfgs = JSON.parse(JSON.stringify(XINGCE_PRESET));
      else if (mode === 'shenlun') cfgs = JSON.parse(JSON.stringify(SHENLUN_PRESET));
      else if (mode === 'gongzhuan') cfgs = JSON.parse(JSON.stringify(GONGZHUAN_PRESET));
      else if (mode === 'mixed') {
        var xc = JSON.parse(JSON.stringify(XINGCE_PRESET));
        var gz = JSON.parse(JSON.stringify(GONGZHUAN_PRESET));
        xc.forEach(function(c) { c.count = Math.round(c.count * 0.6); });
        gz.forEach(function(c) { c.count = Math.round(c.count * 0.4); });
        cfgs = xc.concat(gz);
      }
      this.state.fm_questionConfigs = JSON.stringify(cfgs);
    },

    // ===== 智能生成 =====
    async doGenerate() {
      var self = this;
      if (this.totalQuestions === 0) return;

      this.state.generating = true;
      try {
        var cfgs = this.questionConfigParsed.filter(function(c) { return c.count > 0; });
        var configs = cfgs.map(function(c) {
          return { subject_id: c.subject_id, type_id: c.type_id, subcategory: c.subcategory || null, count: c.count, score_per_question: c.score || 1.0 };
        });

        var body = {
          subject_mode: this.state.fm_subjectMode,
          year_range: this.state.fm_yearRange,
          difficulty_easy_pct: this.state.fm_difficultyEasy,
          difficulty_medium_pct: this.state.fm_difficultyMedium,
          difficulty_hard_pct: this.state.fm_difficultyHard,
          question_configs: configs,
          duration: this.estimatedDuration,
        };
        if (this.state.fm_subjectMode === 'mixed') {
          body.xingce_ratio = this.state.fm_xingceRatio;
          body.gongzhuan_ratio = 100 - this.state.fm_xingceRatio;
        }

        var res = await window.__VTJ_AUTH__.apiFetch('/api/smart-exam/generate', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
        });
        if (!res.ok) { var e = await res.json(); throw new Error(e.detail || '生成失败'); }
        var data = await res.json();

        this.state.gp_paperId = data.paper_id;
        this.state.gp_paperName = data.paper_name;
        this.state.gp_paperCode = data.paper_code;
        this.state.gp_questions = JSON.stringify(data.questions || []);
        this.state.gp_totalScore = data.total_score;
        this.state.gp_questionCount = data.question_count;
        this.state.gp_difficultyEasy = data.difficulty_distribution ? (data.difficulty_distribution.easy || 0) : 0;
        this.state.gp_difficultyMedium = data.difficulty_distribution ? (data.difficulty_distribution.medium || 0) : 0;
        this.state.gp_difficultyHard = data.difficulty_distribution ? (data.difficulty_distribution.hard || 0) : 0;
        this.state.gp_duration = data.duration || 120;
        this.state.step = 2;
      } catch (err) {
        alert('生成失败: ' + (err.message || '网络错误'));
      } finally {
        this.state.generating = false;
      }
    },

    // ===== 预览微调 =====
    toggleDetail(qid) {
      this.state.expandedQuestion = this.state.expandedQuestion === qid ? null : qid;
    },
    openReplace(q, idx) {
      this.state.showReplaceDialog = true;
      this.state.replaceQid = q.question_id;
      this.state.replaceIdx = idx;
    },
    closeReplace() {
      this.state.showReplaceDialog = false;
      this.state.replaceQid = null;
      this.state.replaceIdx = -1;
    },
    async doReplace() {
      if (!this.state.replaceQid) return;
      this.state.replaceLoading = true;
      try {
        var res = await window.__VTJ_AUTH__.apiFetch(
          '/api/smart-exam/' + this.state.gp_paperId + '/replace/' + this.state.replaceQid,
          { method: 'POST', headers: { 'Content-Type': 'application/json' } }
        );
        if (!res.ok) { var e = await res.json(); throw new Error(e.detail || '替换失败'); }
        var data = await res.json();

        if (data.new_question && this.state.replaceIdx >= 0) {
          var qs = JSON.parse(this.state.gp_questions || '[]');
          qs[this.state.replaceIdx] = Object.assign({}, qs[this.state.replaceIdx], data.new_question);
          this.state.gp_questions = JSON.stringify(qs);
        }
        this.closeReplace();
      } catch (err) {
        alert('替换失败: ' + (err.message || ''));
      } finally {
        this.state.replaceLoading = false;
      }
    },
    regenerate() {
      this.state.step = 1;
      this.state.gp_paperId = null;
      this.state.gp_paperName = '';
      this.state.gp_questions = '[]';
    },

    // ===== 确认并开始答题 =====
    async confirmPaper() {
      try {
        var res = await window.__VTJ_AUTH__.apiFetch('/api/smart-exam/' + this.state.gp_paperId + '/confirm', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
        });
        if (!res.ok) { var e = await res.json(); throw new Error(e.detail || '确认失败'); }
        this.state.step = 3;
      } catch (err) {
        alert('确认失败: ' + (err.message || ''));
      }
    },
    async startAnswer() {
      try {
        var res = await window.__VTJ_AUTH__.apiFetch('/api/smart-exam/' + this.state.gp_paperId + '/start', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
        });
        if (!res.ok) { var e = await res.json(); throw new Error(e.detail || '启动失败'); }
        var data = await res.json();
        this.$router.push({
          path: '/smart-answer',
          query: { paper_id: this.state.gp_paperId, record_id: data.record_id, paper_name: this.state.gp_paperName }
        });
      } catch (err) {
        alert('启动失败: ' + (err.message || ''));
      }
    },
    goBack() {
      if (this.state.step > 1) { this.state.step--; } else { this.$router.back(); }
    },
  },
  mounted() {
    console.log('[SmartExam] mounted v1785854718491');
  },
});
</script>

<style lang="css" scoped>
.smart-exam-page { min-height: 100vh; background: #F5F6FA; font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif; }
.se-main { max-width: 960px; margin: 0 auto; padding: 24px 32px 60px; }
.se-hero { text-align: center; padding: 32px 0 20px; }
.se-hero.preview-hero { padding: 16px 0 12px; }
.se-title { font-size: 28px; font-weight: 900; color: #1F3A60; margin: 0 0 6px; }
.se-subtitle { font-size: 14px; color: #5A6488; margin: 0; }
.se-card { background: #FFFFFF; border-radius: 16px; padding: 24px; margin-bottom: 16px; box-shadow: 0 2px 12px rgba(26,43,95,0.06); }
.card-title { font-size: 16px; font-weight: 700; color: #1F3A60; margin: 0 0 16px; }
.subject-options { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.subject-btn { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 14px 8px; border: 2px solid #E8EAF0; border-radius: 14px; background: #FAFBFC; cursor: pointer; transition: all 0.25s; }
.subject-btn:hover { border-color: #C41E3A; background: #FFF5F7; }
.subject-btn.active { border-color: #C41E3A; background: linear-gradient(135deg, #FFF5F7, #FFEBEE); box-shadow: 0 2px 8px rgba(196,30,58,0.15); }
.subject-icon { font-size: 24px; }
.subject-label { font-size: 14px; font-weight: 700; color: #1A1A1A; }
.mixed-ratio { margin-top: 16px; padding: 12px 16px; background: #FFF8E1; border-radius: 10px; display: flex; gap: 16px; align-items: center; }
.mixed-ratio label { font-size: 13px; font-weight: 600; color: #1F3A60; }
.mixed-ratio input[type="range"] { flex:1; accent-color: #C41E3A; }
.year-options { display: flex; gap: 10px; }
.year-btn { flex:1; padding: 10px 16px; border: 2px solid #E8EAF0; border-radius: 20px; background: #FAFBFC; font-size: 14px; font-weight: 600; color: #1F3A60; cursor: pointer; transition: all 0.25s; }
.year-btn:hover { border-color: #1F3A60; }
.year-btn.active { border-color: #1F3A60; background: #1F3A60; color: #FFFFFF; }
.difficulty-sliders { display: flex; flex-direction: column; gap: 14px; }
.diff-item {  }
.diff-header { display: flex; justify-content: space-between; font-size: 13px; font-weight: 600; color: #1F3A60; margin-bottom: 2px; }
.diff-item input[type="range"] { width: 100%; accent-color: #1F3A60; }
.type-configs { display: flex; flex-direction: column; gap: 8px; }
.type-row { display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: #FAFBFC; border-radius: 10px; }
.type-name { flex:1; font-size: 14px; font-weight: 600; color: #1A1A1A; }
.type-input { width: 55px; padding: 6px 8px; border: 1.5px solid #E0E3E8; border-radius: 8px; font-size: 14px; text-align: center; color: #1F3A60; outline: none; }
.type-input:focus { border-color: #C41E3A; }
.score-input { width: 50px; }
.type-unit { font-size: 13px; color: #5A6488; }
.type-summary { margin-top: 16px; padding: 12px 16px; background: #EFF6FF; border-radius: 10px; display: flex; gap: 24px; font-size: 13px; color: #1F3A60; }
.type-summary b { color: #C41E3A; }
.preview-stats { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; margin-top: 12px; }
.stat-tag { padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; background: #EFF6FF; color: #3B82F6; }
.stat-tag.easy-tag { background: #D1FAE5; color: #065F46; }
.stat-tag.medium-tag { background: #FEF3C7; color: #92400E; }
.stat-tag.hard-tag { background: #FEE2E2; color: #991B1B; }
.question-list-card { display: flex; flex-direction: column; gap: 2px; }
.question-item { padding: 16px; border-radius: 12px; border: 1.5px solid transparent; cursor: pointer; transition: all 0.2s; }
.question-item:hover { border-color: #E0E3E8; background: #FAFBFC; }
.question-item.expanded { border-color: #1F3A60; background: #F8F9FC; }
.qi-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.qi-number { font-size: 14px; font-weight: 900; color: #1F3A60; }
.qi-type { padding: 2px 10px; border-radius: 8px; font-size: 11px; font-weight: 600; background: #EFF6FF; color: #3B82F6; }
.qi-type.easy { background: #D1FAE5; color: #065F46; }
.qi-type.hard { background: #FEE2E2; color: #991B1B; }
.qi-difficulty { font-size: 12px; color: #F59E0B; letter-spacing: 2px; }
.qi-subcat { font-size: 11px; color: #5A6488; padding: 2px 8px; background: #F0F2F5; border-radius: 6px; }
.qi-content { font-size: 14px; color: #1A1A1A; line-height: 1.6; margin: 0; }
.qi-actions { display: flex; gap: 8px; margin-top: 8px; }
.qi-btn { padding: 4px 12px; border: 1px solid #FDE2E6; border-radius: 8px; background: #FFF5F7; font-size: 12px; color: #C41E3A; cursor: pointer; transition: all 0.2s; }
.qi-btn:hover { background: #FDE2E6; }
.replace-overlay { position: fixed; top:0; left:0; right:0; bottom:0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.replace-dialog { background: #FFF; border-radius: 16px; padding: 28px; width: 440px; max-width: 90vw; box-shadow: 0 8px 32px rgba(26,43,95,0.15); }
.replace-dialog h4 { margin: 0 0 8px; font-size: 16px; color: #1F3A60; }
.replace-tip { font-size: 13px; color: #5A6488; margin: 0 0 20px; }
.replace-actions { display: flex; gap: 10px; justify-content: flex-end; }
.confirm-card { text-align: center; padding: 40px; }
.confirm-icon { font-size: 48px; margin-bottom: 12px; animation: bounceIn 0.6s ease; }
@keyframes bounceIn { 0% { transform: scale(0.3); opacity:0; } 50% { transform: scale(1.1); } 70% { transform: scale(0.9); } 100% { transform: scale(1); opacity:1; } }
.confirm-card h2 { font-size: 22px; font-weight: 900; color: #1F3A60; margin: 0 0 24px; }
.confirm-info { text-align: left; margin: 0 auto 24px; max-width: 400px; }
.ci-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #F0F2F5; font-size: 14px; }
.ci-row span:first-child { color: #5A6488; font-weight: 600; }
.ci-row span:last-child { color: #1A1A1A; font-weight: 700; }
.confirm-actions { display: flex; gap: 12px; justify-content: center; margin-bottom: 24px; }
.start-answer-btn { display: inline-flex; align-items: center; gap: 8px; padding: 16px 48px; border: none; border-radius: 20px; background: linear-gradient(135deg, #1F3A60, #2B4F8E); color: #FFF; font-size: 18px; font-weight: 800; cursor: pointer; transition: all 0.3s; box-shadow: 0 4px 16px rgba(31,58,96,0.3); }
.start-answer-btn:hover { transform: translateY(-2px); box-shadow: 0 6px 24px rgba(31,58,96,0.4); }
.se-actions { display: flex; gap: 12px; justify-content: center; padding: 24px 0; }
.se-btn { padding: 12px 28px; border-radius: 20px; font-size: 14px; font-weight: 700; cursor: pointer; transition: all 0.25s; border: none; }
.se-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.back-btn { background: #F0F2F5; color: #5A6488; border: 1.5px solid #E8EAF0; }
.back-btn:hover { background: #E8EAF0; }
.generate-btn { background: linear-gradient(135deg, #C41E3A, #E8384F); color: #FFF; box-shadow: 0 2px 8px rgba(196,30,58,0.25); }
.generate-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(196,30,58,0.35); }
.outline-btn { background: #FFF; color: #1F3A60; border: 2px solid #1F3A60; }
.outline-btn:hover { background: #F0F4FF; }
.btn-spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-top-color: #FFF; border-radius: 50%; animation: spin 0.6s linear infinite; vertical-align: middle; margin-right: 6px; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
