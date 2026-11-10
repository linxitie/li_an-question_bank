<!-- 自定义刷题：科目 → 子科目 → 知识点/其他 → 题型/难度/年份 的统一配置页 -->
<template>
  <div class="cp-page">
    <div class="cp-header">
      <button class="cp-back" @click="goBack">← 返回题库</button>
      <div>
        <h1>自定义刷题</h1>
        <p>按科目、知识点与题型自由组合；没有细分考点的题目会归入「其他」，同样可以直接练。</p>
      </div>
    </div>

    <div class="cp-layout">
      <section class="cp-card cp-config">
        <h2 class="cp-card-title">练习配置</h2>

        <div class="cp-field">
          <label>练习科目</label>
          <div class="cp-segment">
            <button
              v-for="s in subjects"
              :key="s.key"
              :class="{ active: form.subject === s.key }"
              @click="selectSubject(s.key)">{{ s.name }}</button>
          </div>
        </div>

        <div class="cp-field">
          <label>具体子科目</label>
          <select v-model="form.subCategoryId" @change="onSubCategoryChange">
            <option value="">请选择子科目</option>
            <option v-for="sc in subCategories" :key="sc.id" :value="sc.id">{{ sc.name }}（{{ sc.total_questions || 0 }} 题）</option>
          </select>
        </div>

        <div class="cp-field">
          <label>知识点范围</label>
          <select v-model="form.scopeKey">
            <option value="">全部子科目题目</option>
            <option v-for="opt in scopeOptions" :key="opt.key" :value="opt.key">{{ opt.label }}</option>
          </select>
          <p class="cp-hint" v-if="selectedScope">已选：{{ selectedScope.label }} · 约 {{ selectedScope.total || 0 }} 题</p>
          <p class="cp-hint" v-else-if="currentSub">不限定知识点，抽取该子科目全部题目 · 约 {{ currentSub.total_questions || 0 }} 题</p>
        </div>

        <div class="cp-field">
          <label>题型</label>
          <div class="cp-chips">
            <button
              v-for="t in typeOptions"
              :key="t.type_id"
              :class="{ active: form.typeIds.indexOf(t.type_id) >= 0 }"
              @click="toggleType(t.type_id)">{{ t.type_name }} · {{ t.count }}</button>
            <span class="cp-empty" v-if="!typeOptions.length">不限题型</span>
          </div>
        </div>

        <div class="cp-field">
          <label>难度</label>
          <div class="cp-chips">
            <button
              v-for="d in difficultyOptions"
              :key="d.difficulty"
              :class="{ active: form.difficulties.indexOf(d.difficulty) >= 0 }"
              @click="toggleDifficulty(d.difficulty)">{{ starText(d.difficulty) }} · {{ d.count }}</button>
            <span class="cp-empty" v-if="!difficultyOptions.length">不限难度</span>
          </div>
        </div>

        <div class="cp-row">
          <div class="cp-field">
            <label>出题年份</label>
            <select v-model="form.yearRange">
              <option value="0">不限年份</option>
              <option value="3">近三年</option>
              <option value="5">近五年</option>
            </select>
          </div>
          <div class="cp-field">
            <label>出题顺序</label>
            <select v-model="form.order">
              <option value="random">随机练习</option>
              <option value="weak">优先薄弱题</option>
              <option value="unseen">优先未做题</option>
            </select>
          </div>
        </div>

        <div class="cp-row">
          <div class="cp-field">
            <label>练习数量（5–100）</label>
            <input type="number" v-model.number="form.count" min="5" max="100" />
          </div>
          <div class="cp-field">
            <label>练习时间（分钟，0 为不限）</label>
            <input type="number" v-model.number="form.timeLimit" min="0" max="180" />
          </div>
        </div>
      </section>

      <aside class="cp-side">
        <div class="cp-card cp-summary">
          <h3>本次练习</h3>
          <div class="cp-sum-row"><span>科目</span><b>{{ subjectName }}</b></div>
          <div class="cp-sum-row"><span>子科目</span><b>{{ currentSub ? currentSub.name : '未选择' }}</b></div>
          <div class="cp-sum-row"><span>范围</span><b>{{ selectedScope ? selectedScope.label : '全部题目' }}</b></div>
          <div class="cp-sum-row"><span>题型 / 难度</span><b>{{ typeSummary() }} / {{ difficultySummary() }}</b></div>
          <div class="cp-sum-row"><span>预计可抽</span><b>{{ estimatedCount }} 题</b></div>
          <button class="cp-start" :disabled="!canStart" @click="startPractice">开始自定义练习</button>
          <p class="cp-warn" v-if="!canStart">请选择子科目后再开始</p>
        </div>

        <div class="cp-card">
          <h3>快捷预设</h3>
          <div class="cp-presets">
            <button @click="applyPreset(10)">快速 10 题</button>
            <button @click="applyPreset(20)">标准 20 题</button>
            <button @click="applyPreset(30)">强化 30 题</button>
          </div>
        </div>

        <div class="cp-card" v-if="history.length">
          <h3>最近配置</h3>
          <button class="cp-history" v-for="(h, i) in history" :key="i" @click="applyHistory(h)">
            <span>{{ h.subjectName }} · {{ h.scopeName }}</span>
            <small>{{ h.count }} 题 · {{ h.timeLabel }}</small>
          </button>
        </div>
      </aside>
    </div>
  </div>
</template>

<script>
import { defineComponent, reactive, ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';

var HISTORY_KEY = 'quick-custom-practice-history-v1';
var SUBJECT_MAP = { xc: 1, sl: 2, ga: 3 };
var SUBJECT_NAME = { xc: '行测', sl: '申论', ga: '公专' };

export default defineComponent({
  name: 'CustomPractice',
  setup() {
    var router = useRouter();
    var subCategories = ref([]);
    var history = ref([]);
    var form = reactive({
      subject: 'xc',
      subCategoryId: '',
      scopeKey: '',
      typeIds: [],
      difficulties: [],
      yearRange: '3',
      order: 'random',
      count: 20,
      timeLimit: 0,
    });

    function getFetch() {
      return (window.__VTJ_AUTH__ && window.__VTJ_AUTH__.apiFetch)
        ? window.__VTJ_AUTH__.apiFetch
        : window.fetch;
    }

    async function loadSubjects() {
      form.subCategoryId = '';
      form.scopeKey = '';
      subCategories.value = [];
      try {
        var res = await getFetch()('/api/quick-practice/sub-categories?subjectId=' + SUBJECT_MAP[form.subject], {
          headers: { 'Content-Type': 'application/json' },
        });
        if (!res.ok) return;
        var data = await res.json();
        subCategories.value = Array.isArray(data.items) ? data.items : [];
      } catch (e) {
        subCategories.value = [];
      }
    }

    var currentSub = computed(function() {
      // 空字符串表示「尚未选择」，不能 Number('')=0 误命中 id=0 的「未分类」。
      if (form.subCategoryId === '' || form.subCategoryId == null) return null;
      var id = Number(form.subCategoryId);
      for (var i = 0; i < subCategories.value.length; i++) {
        if (Number(subCategories.value[i].id) === id) return subCategories.value[i];
      }
      return null;
    });

    var scopeOptions = computed(function() {
      var sc = currentSub.value;
      if (!sc) return [];
      var opts = [];
      var points = Array.isArray(sc.display_points) ? sc.display_points : (sc.knowledge_points || []);
      points.forEach(function(l2) {
        if (!(l2.total_questions > 0)) return;
        var l2Scope = l2.scope || { type: l2.is_direct ? 'other' : 'l2', scope_id: l2.point_id || 0 };
        opts.push({
          key: 'l2:' + (l2.key || l2.point_id),
          label: l2.point_name + (l2.is_direct ? '（直接练）' : '（含全部子考点）'),
          total: l2.total_questions || 0,
          scope: {
            type: l2.is_direct ? 'other' : 'l2',
            scope_id: l2Scope.scope_id || l2.point_id || 0,
            sub_category_id: sc.id,
            l2_id: l2.point_id || 0,
            include_descendants: true,
            include_other: true,
          },
        });
        (l2.children || []).forEach(function(l3) {
          if (!(l3.total_questions > 0)) return;
          var l3Scope = l3.scope || { type: 'l3', scope_id: l3.point_id || 0 };
          opts.push({
            key: 'l3:' + (l3.key || l3.point_id) + ':' + (l2.point_id || 0),
            label: '　└ ' + l3.point_name,
            total: l3.total_questions || 0,
            scope: {
              type: l3Scope.type || 'l3',
              scope_id: l3Scope.scope_id || l3.point_id || 0,
              sub_category_id: sc.id,
              l2_id: l2.point_id || 0,
            },
          });
        });
      });
      return opts;
    });

    var selectedScope = computed(function() {
      for (var i = 0; i < scopeOptions.value.length; i++) {
        if (scopeOptions.value[i].key === form.scopeKey) return scopeOptions.value[i];
      }
      return null;
    });

    function uniqFilters(field) {
      var sc = currentSub.value;
      var list = (sc && sc.filters && sc.filters[field]) || [];
      return Array.isArray(list) ? list : [];
    }

    var typeOptions = computed(function() { return uniqFilters('types'); });
    var difficultyOptions = computed(function() { return uniqFilters('difficulties'); });
    var subjectName = computed(function() { return SUBJECT_NAME[form.subject] || '行测'; });

    var estimatedCount = computed(function() {
      var total = selectedScope.value ? (selectedScope.value.total || 0) : (currentSub.value ? (currentSub.value.total_questions || 0) : 0);
      return Math.max(0, Math.min(total, Number(form.count) || 0));
    });

    var canStart = computed(function() {
      return !!currentSub.value && Number(form.count) >= 5;
    });

    function toggleType(id) {
      var idx = form.typeIds.indexOf(id);
      if (idx >= 0) form.typeIds.splice(idx, 1);
      else form.typeIds.push(id);
    }
    function toggleDifficulty(d) {
      var idx = form.difficulties.indexOf(d);
      if (idx >= 0) form.difficulties.splice(idx, 1);
      else form.difficulties.push(d);
    }
    function starText(d) {
      return '★'.repeat(Math.max(1, Number(d) || 1));
    }
    function typeSummary() {
      if (!form.typeIds.length) return '不限';
      var names = typeOptions.value.filter(function(t) { return form.typeIds.indexOf(t.type_id) >= 0; }).map(function(t) { return t.type_name; });
      return names.join('、') || '不限';
    }
    function difficultySummary() {
      return form.difficulties.length ? form.difficulties.map(starText).join('、') : '不限';
    }

    function buildScopeQuery() {
      var sc = currentSub.value;
      var opt = selectedScope.value;
      var scope = opt ? opt.scope : { type: 'subcategory', scope_id: sc.id, sub_category_id: sc.id };
      var params = [
        'subject=' + form.subject,
        'scope=' + scope.type,
        'scopeId=' + (scope.scope_id || 0),
        'scopeName=' + encodeURIComponent(opt ? opt.label.replace('　└ ', '') : sc.name),
        'subCategoryId=' + sc.id,
        'count=' + form.count,
        'order=' + form.order,
      ];
      if (scope.l2_id) params.push('l2Id=' + scope.l2_id);
      if (scope.include_descendants) params.push('includeDescendants=1');
      if (scope.include_other) params.push('includeOther=1');
      if (form.yearRange !== '0') params.push('yearRange=' + form.yearRange);
      if (form.typeIds.length) params.push('typeIds=' + form.typeIds.join(','));
      if (form.difficulties.length) params.push('difficulties=' + form.difficulties.join(','));
      if (form.timeLimit > 0) params.push('timeLimit=' + form.timeLimit);
      return params.join('&');
    }

    function startPractice() {
      if (!canStart.value) return;
      var sc = currentSub.value;
      var opt = selectedScope.value;
      var record = {
        subject: form.subject,
        subjectName: subjectName.value,
        scopeName: opt ? opt.label.replace('　└ ', '') : sc.name,
        count: form.count,
        timeLabel: new Date().toLocaleDateString('zh-CN'),
        query: buildScopeQuery(),
      };
      var next = [record].concat(history.value.filter(function(h) { return h.query !== record.query; })).slice(0, 3);
      history.value = next;
      try { localStorage.setItem(HISTORY_KEY, JSON.stringify(next)); } catch (e) {}
      router.push('/exercise?' + record.query);
    }

    function applyPreset(n) {
      form.count = n;
    }
    function applyHistory(h) {
      if (h && h.query) router.push('/exercise?' + h.query);
    }
    function selectSubject(key) {
      if (form.subject === key) return;
      form.subject = key;
      loadSubjects();
    }
    function onSubCategoryChange() {
      form.scopeKey = '';
    }
    function goBack() {
      router.push('/question-bank');
    }

    onMounted(function() {
      try {
        var raw = localStorage.getItem(HISTORY_KEY);
        history.value = raw ? JSON.parse(raw).slice(0, 3) : [];
      } catch (e) { history.value = []; }
      loadSubjects();
    });

    return {
      subjects: [
        { key: 'xc', name: '行测' },
        { key: 'sl', name: '申论' },
        { key: 'ga', name: '公专' },
      ],
      form: form,
      subCategories: subCategories,
      currentSub: currentSub,
      scopeOptions: scopeOptions,
      selectedScope: selectedScope,
      typeOptions: typeOptions,
      difficultyOptions: difficultyOptions,
      subjectName: subjectName,
      estimatedCount: estimatedCount,
      canStart: canStart,
      history: history,
      toggleType: toggleType,
      toggleDifficulty: toggleDifficulty,
      starText: starText,
      typeSummary: typeSummary,
      difficultySummary: difficultySummary,
      startPractice: startPractice,
      applyPreset: applyPreset,
      applyHistory: applyHistory,
      selectSubject: selectSubject,
      onSubCategoryChange: onSubCategoryChange,
      goBack: goBack,
    };
  },
});
</script>

<style scoped>
.cp-page { min-height: 100vh; background: #f5f7fb; padding: 28px 32px 48px; font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif; color: #1a2b5f; }
.cp-header { max-width: 1240px; margin: 0 auto 20px; display: flex; gap: 18px; align-items: flex-start; }
.cp-back { border: 1px solid #dbe3ef; background: #fff; color: #1a3c6d; border-radius: 8px; padding: 8px 14px; cursor: pointer; }
.cp-header h1 { margin: 0 0 6px; font-size: 26px; }
.cp-header p { margin: 0; color: #6b7a99; font-size: 13px; }
.cp-layout { max-width: 1240px; margin: 0 auto; display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 20px; align-items: start; }
.cp-card { background: #fff; border: 1px solid #e6ecf5; border-radius: 14px; padding: 20px; box-shadow: 0 8px 24px rgba(26, 60, 109, 0.05); }
.cp-card-title { margin: 0 0 16px; font-size: 17px; }
.cp-field { margin-bottom: 18px; }
.cp-field > label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 8px; }
.cp-field select, .cp-field input { width: 100%; box-sizing: border-box; border: 1px solid #dbe3ef; border-radius: 9px; padding: 10px 12px; font-size: 13px; background: #fbfcfe; color: #1a2b5f; }
.cp-segment { display: flex; background: #f1f4fa; border-radius: 10px; padding: 4px; }
.cp-segment button { flex: 1; border: 0; background: transparent; padding: 9px; border-radius: 8px; color: #5a6488; cursor: pointer; font-weight: 600; }
.cp-segment button.active { background: #1a3c6d; color: #fff; }
.cp-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.cp-chips button { border: 1px solid #dbe3ef; background: #fff; border-radius: 999px; padding: 6px 12px; font-size: 12px; color: #4a5878; cursor: pointer; }
.cp-chips button.active { background: #e8f0ff; border-color: #1a3c6d; color: #1a3c6d; font-weight: 600; }
.cp-empty { font-size: 12px; color: #98a3ba; }
.cp-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.cp-hint { margin: 8px 0 0; font-size: 12px; color: #6b7a99; }
.cp-side { display: flex; flex-direction: column; gap: 14px; position: sticky; top: 20px; }
.cp-summary h3, .cp-card h3 { margin: 0 0 14px; font-size: 15px; }
.cp-sum-row { display: flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-bottom: 1px dashed #edf1f7; font-size: 12px; color: #6b7a99; }
.cp-sum-row b { color: #1a2b5f; text-align: right; }
.cp-start { width: 100%; margin-top: 16px; border: 0; border-radius: 10px; background: #1a3c6d; color: #fff; padding: 12px; font-size: 14px; font-weight: 700; cursor: pointer; }
.cp-start:disabled { background: #c6cfdf; cursor: not-allowed; }
.cp-warn { margin: 8px 0 0; font-size: 12px; color: #b7791f; }
.cp-presets { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
.cp-presets button { border: 1px solid #dbe3ef; background: #fbfcfe; border-radius: 9px; padding: 10px 4px; font-size: 12px; cursor: pointer; color: #1a3c6d; }
.cp-history { width: 100%; display: flex; flex-direction: column; gap: 3px; text-align: left; border: 0; border-bottom: 1px dashed #edf1f7; background: transparent; padding: 9px 0; cursor: pointer; color: #1a2b5f; font-size: 12px; }
.cp-history small { color: #8a96ad; }
@media (max-width: 960px) { .cp-layout { grid-template-columns: 1fr; } .cp-side { position: static; } }
</style>
