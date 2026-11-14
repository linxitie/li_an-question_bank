<template>
  <div class="pc-wrap">
    <header class="pc-header">
      <button class="pc-back" type="button" aria-label="返回" @click="goBack">‹</button>
      <div class="pc-title-group">
        <h1 class="pc-title">练习中心</h1>
        <p class="pc-subtitle">{{ subtitle }}</p>
      </div>
      <div class="pc-header-right">
        <span class="pc-total">本范围 {{ currentAvailable }} 题</span>
      </div>
    </header>

    <nav class="pc-subjects" role="tablist" aria-label="科目">
      <button
        v-for="s in subjects"
        :key="s.key"
        type="button"
        role="tab"
        class="pc-subject"
        :class="{ active: state.subject === s.key }"
        :aria-selected="state.subject === s.key"
        @click="switchSubject(s.key)">
        {{ s.name }}
      </button>
    </nav>

    <section v-if="state.loading" class="pc-loading" aria-live="polite">
      <span class="pc-spinner"></span>
      <span>正在加载考点数据…</span>
    </section>

    <section v-else-if="state.error" class="pc-error" role="alert">
      <p>{{ state.error }}</p>
      <button type="button" class="pc-primary" @click="loadSubject">重试</button>
    </section>

    <main v-else class="pc-main">
      <!-- 左：按考点练 -->
      <section class="pc-panel pc-tree-panel" aria-labelledby="tree-heading">
        <div class="pc-panel-head">
          <h2 id="tree-heading" class="pc-panel-title">按考点练习</h2>
          <span class="pc-hint">只有存在下级考点的条目才可展开，其余点击即练</span>
        </div>

        <div v-if="!state.subCategories.length" class="pc-empty">
          该科目暂无可用题目
        </div>

        <div v-for="sub in visibleSubCategories" :key="sub.id + '-' + sub.name" class="pc-sub-block">
          <button type="button" class="pc-sub-row" @click="toggleSub(sub.id)">
            <span class="pc-sub-name">{{ sub.name }}</span>
            <span class="pc-count">{{ sub.done_count || 0 }}/{{ sub.total_questions || 0 }}</span>
            <span class="pc-caret" :class="{ open: state.openSub === sub.id }">›</span>
          </button>

          <div v-if="state.openSub === sub.id" class="pc-tree">
            <template v-for="l2 in sub.knowledge_points" :key="l2.point_id">
              <div class="pc-l2">
                <button
                  v-if="l2.drillable"
                  type="button"
                  class="pc-kp-row pc-kp-l2"
                  :aria-expanded="isL2Open(sub.id, l2.point_id)"
                  @click="toggleL2(sub.id, l2.point_id)">
                  <span class="pc-kp-name">{{ l2.point_name }}</span>
                  <span class="pc-kp-count">{{ l2.done_count || 0 }}/{{ l2.total_questions || 0 }}</span>
                  <span class="pc-caret" :class="{ open: isL2Open(sub.id, l2.point_id) }">›</span>
                </button>
                <button
                  v-else
                  type="button"
                  class="pc-kp-row pc-kp-l2 pc-kp-leaf"
                  @click="startByPoint(sub, l2)">
                  <span class="pc-kp-name">{{ l2.point_name }}</span>
                  <span class="pc-kp-count">{{ l2.done_count || 0 }}/{{ l2.total_questions || 0 }}</span>
                  <span class="pc-go">练习</span>
                </button>

                <div v-if="l2.drillable && isL2Open(sub.id, l2.point_id)" class="pc-l3-list">
                  <button
                    v-for="l3 in l2.children"
                    :key="l3.point_id"
                    type="button"
                    class="pc-kp-row pc-kp-l3"
                    @click="startByPoint(sub, l3)">
                    <span class="pc-kp-name">{{ l3.point_name }}</span>
                    <span class="pc-kp-count">{{ l3.done_count || 0 }}/{{ l3.total_questions || 0 }}</span>
                    <span class="pc-go">练习</span>
                  </button>
                </div>
              </div>
            </template>

            <!-- 「其他（未细分）」：不再是分类名，而是收纳箱——直接开练 -->
            <button
              v-if="sub.fallback && sub.fallback.total_questions"
              type="button"
              class="pc-kp-row pc-fallback-row"
              @click="startFallback(sub)">
              <span class="pc-kp-name">
                {{ sub.fallback.name }}
                <span class="pc-capsule">未细分类</span>
              </span>
              <span class="pc-kp-count">{{ sub.fallback.done_count || 0 }}/{{ sub.fallback.total_questions }}</span>
              <span class="pc-go">直接练习</span>
            </button>

            <p v-if="!sub.knowledge_points.length && !(sub.fallback && sub.fallback.total_questions)" class="pc-empty">
              该分类下暂无题目
            </p>
          </div>
        </div>
      </section>

      <!-- 右：自定义刷题（练习蓝图） -->
      <aside class="pc-panel pc-blueprint-panel" aria-labelledby="bp-heading">
        <div class="pc-panel-head">
          <h2 id="bp-heading" class="pc-panel-title">自定义刷题</h2>
          <span class="pc-hint">先算清题量与时长，再开始</span>
        </div>

        <div class="pc-field">
          <span class="pc-label">
            范围
            <span class="pc-label-sub">{{ subjectWide ? '未选＝' + scopeName : '已选 ' + state.bpSubIds.length + ' 个分类' }}</span>
          </span>
          <div class="pc-chips">
            <button
              v-for="sub in blueprintSubCategories"
              :key="sub.id + '-' + sub.name"
              type="button"
              class="pc-chip"
              :class="{ active: state.bpSubIds.indexOf(sub.id) >= 0 }"
              @click="toggleBpSub(sub.id)">
              {{ sub.name }}
              <span class="pc-chip-count">{{ sub.total_questions || 0 }}</span>
            </button>
          </div>
        </div>

        <label class="pc-field pc-toggle">
          <input v-model="state.includeFallback" type="checkbox" />
          <span>包含「其他（未细分）」收容题</span>
        </label>
        <p v-if="!state.includeFallback" class="pc-warn" role="status">
          当前题库大量题目落在「其他（未细分）」，不勾选时范围可能为空。
        </p>

        <div class="pc-field pc-field-inline">
          <label class="pc-label" for="bp-year">年份</label>
          <select id="bp-year" v-model="state.yearRange" class="pc-select">
            <option value="1">近 1 年</option>
            <option value="3">近 3 年</option>
            <option value="5">近 5 年</option>
            <option value="0">不限</option>
          </select>

          <label class="pc-label" for="bp-order">顺序</label>
          <select id="bp-order" v-model="state.order" class="pc-select">
            <option value="random">随机</option>
            <option value="year_desc">年份新→旧</option>
            <option value="hard_first">难度高→低</option>
          </select>
        </div>

        <div class="pc-field">
          <span class="pc-label">题型</span>
          <div class="pc-chips">
            <button
              v-for="t in typeOptions"
              :key="t.id"
              type="button"
              class="pc-chip"
              :class="{ active: state.types.indexOf(t.id) >= 0 }"
              @click="toggleType(t.id)">
              {{ t.name }}
            </button>
            <button type="button" class="pc-chip pc-chip-reset" @click="state.types = []">不限</button>
          </div>
        </div>

        <div class="pc-field">
          <label class="pc-label" for="bp-count">题量：{{ state.count }} 题</label>
          <input
            id="bp-count"
            v-model.number="state.count"
            class="pc-range"
            type="range"
            min="5"
            max="100"
            step="5"
            @change="previewBlueprint" />
        </div>

        <div class="pc-field pc-field-inline">
          <label class="pc-label" for="bp-minutes">时长</label>
          <select id="bp-minutes" v-model.number="state.minutes" class="pc-select">
            <option :value="0">不限时</option>
            <option :value="5">5 分钟</option>
            <option :value="10">10 分钟</option>
            <option :value="15">15 分钟</option>
            <option :value="20">20 分钟</option>
            <option :value="30">30 分钟</option>
            <option :value="45">45 分钟</option>
          </select>
        </div>

        <div class="pc-preview" aria-live="polite">
          <div v-if="state.previewLoading" class="pc-preview-line">正在计算…</div>
          <template v-else>
            <div class="pc-preview-scope">{{ scopeName }}</div>
            <div class="pc-preview-line">
              预计 <strong>{{ state.preview.picked || 0 }}</strong> 题 ·
              约 <strong>{{ state.preview.estimatedMinutes || 0 }}</strong> 分钟
              <span v-if="state.preview.available !== undefined" class="pc-preview-sub">
                （范围可用 {{ state.preview.available }} 题）
              </span>
            </div>
            <ul v-if="state.preview.distribution && state.preview.distribution.length" class="pc-dist">
              <li v-for="d in state.preview.distribution" :key="d.sub_category_id + '-' + d.name">
                {{ d.name }} · {{ d.count }}
              </li>
            </ul>
            <p v-if="state.preview.note" class="pc-warn">{{ state.preview.note }}</p>
          </template>
        </div>

        <button
          type="button"
          class="pc-primary pc-start"
          :disabled="!canStart"
          @click="startBlueprint">
          开始练习
        </button>
      </aside>
    </main>
  </div>
</template>

<script lang="ts">
// 练习中心（手写页）：把"快速练习"和"自定义刷题"统一到一套 Practice Blueprint。
// 为什么新建手写页而不改 question_bank.vue 模板：
//   1) .vtj 页面的 <template> 按 AGENTS.md R3 禁止 AI 直接改，只能由设计器或 DSL 写；
//   2) 该页 1780 行、模板与 5 个下拉耦合，任何模板级重构都会和 DSL 回存互相覆盖；
//   3) 手写页可直接用 Vue SFC 表达"可下钻/不可下钻"分支，改动可测、可回滚。
// 后端唯一真源：GET /api/quick-practice/sub-categories 与 POST /api/quick-practice/blueprint。
import { defineComponent, reactive, computed, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';

interface PointNode {
  point_id: number;
  point_name: string;
  level: number;
  total_questions: number;
  done_count: number;
  drillable?: boolean;
  is_fallback?: boolean;
  children?: PointNode[];
}

interface FallbackBlock {
  id: number;
  name: string;
  total_questions: number;
  done_count: number;
  point_ids: number[];
}

interface SubCategoryItem {
  id: number;
  name: string;
  total_questions: number;
  done_count: number;
  knowledge_points: PointNode[];
  fallback?: FallbackBlock | null;
}

export default defineComponent({
  name: 'PracticeCenter',
  setup() {
    const router = useRouter();
    const route = useRoute();

    const subjects = [
      { key: 'xc', name: '行测', subjectId: 1 },
      { key: 'sl', name: '申论', subjectId: 2 },
      { key: 'ga', name: '公安专业', subjectId: 3 }
    ];
    const subjectIdMap: Record<string, number> = { xc: 1, sl: 2, ga: 3 };

    const typeOptions = [
      { id: 1, name: '单选' },
      { id: 4, name: '多选' },
      { id: 5, name: '判断' }
    ];

    const state = reactive({
      subject: (route.query.subject as string) || 'xc',
      loading: true,
      error: '',
      subCategories: [] as SubCategoryItem[],
      openSub: null as number | null,
      openL2: {} as Record<string, boolean>,
      // 练习蓝图（与后端 BlueprintRequest 字段同名）
      bpSubIds: [] as number[],
      includeFallback: true,
      yearRange: '3',
      types: [] as number[],
      count: 20,
      minutes: 0,
      order: 'random',
      preview: {} as any,
      previewLoading: false,
      previewSeq: 0
    });

    const getFetch = () => {
      const auth = (window as any).__VTJ_AUTH__;
      return auth && auth.apiFetch ? auth.apiFetch : (url: string, opts?: any) => fetch(url, opts);
    };

    const subjectId = computed(() => subjectIdMap[state.subject] || 1);
    const subtitle = computed(() => {
      const s = subjects.find(item => item.key === state.subject);
      return s ? s.name + ' · 按考点练习或自定义刷题' : '按考点练习或自定义刷题';
    });

    const visibleSubCategories = computed(() =>
      state.subCategories.filter(sub => (sub.total_questions || 0) > 0)
    );

    const blueprintSubCategories = computed(() =>
      state.subCategories.filter(sub => (sub.total_questions || 0) > 0 && sub.id !== 0)
    );

    const currentAvailable = computed(() =>
      visibleSubCategories.value.reduce((sum, sub) => sum + (sub.total_questions || 0), 0)
    );

    // 未勾选任何子科目时，范围默认=当前整个科目。
    // 为什么：进来时 6 个 chip 全不选，预览恒为「0 题 / 请先选择练习范围」、按钮灰，
    // 用户会以为系统没题可练（实测截图）。默认整科目是唯一不需要教学就能开始的语义。
    const subjectWide = computed(() => state.bpSubIds.length === 0);
    const effectiveSubIds = computed(() =>
      subjectWide.value ? blueprintSubCategories.value.map(sub => sub.id) : state.bpSubIds.slice()
    );
    const scopeName = computed(() => {
      const s = subjects.find(item => item.key === state.subject);
      const subjectLabel = s ? s.name : '当前科目';
      if (!subjectWide.value) {
        const names = blueprintSubCategories.value
          .filter(sub => state.bpSubIds.indexOf(sub.id) >= 0)
          .map(sub => sub.name);
        return names.join('、');
      }
      return '整个' + subjectLabel;
    });

    const canStart = computed(() => {
      const preview = state.preview || {};
      return Number(preview.picked || 0) > 0;
    });

    const loadSubject = async () => {
      state.loading = true;
      state.error = '';
      state.openSub = null;
      state.openL2 = {};
      state.bpSubIds = [];
      try {
        const res = await getFetch()(
          '/api/quick-practice/sub-categories?subjectId=' + subjectId.value,
          { headers: { 'Content-Type': 'application/json' } }
        );
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        state.subCategories = Array.isArray(data.items) ? data.items : [];
        // 默认展开第一个有题的子科目：用户进来就能看到考点，而不是面对 8 个折叠行
        const first = state.subCategories.find(sub => (sub.total_questions || 0) > 0);
        if (first) state.openSub = first.id;
      } catch (e: any) {
        state.error = '考点数据加载失败：' + (e && e.message ? e.message : '网络异常');
      } finally {
        state.loading = false;
      }
      previewBlueprint();
    };

    const switchSubject = (key: string) => {
      if (state.subject === key) return;
      state.subject = key;
      router.replace({ query: { ...route.query, subject: key } });
      loadSubject();
    };

    const toggleSub = (id: number) => {
      state.openSub = state.openSub === id ? null : id;
    };

    const isL2Open = (subId: number, pointId: number) => !!state.openL2[subId + ':' + pointId];
    const toggleL2 = (subId: number, pointId: number) => {
      const key = subId + ':' + pointId;
      state.openL2[key] = !state.openL2[key];
    };

    const toggleBpSub = (id: number) => {
      const index = state.bpSubIds.indexOf(id);
      if (index >= 0) state.bpSubIds.splice(index, 1);
      else state.bpSubIds.push(id);
    };

    const toggleType = (id: number) => {
      const index = state.types.indexOf(id);
      if (index >= 0) state.types.splice(index, 1);
      else state.types.push(id);
      previewBlueprint();
    };

    const encodeBlueprint = (bp: any) => {
      // URL 传参统一用 base64(JSON)：手写页与 exercise.vue 都不依赖额外 store，
      // 刷新/分享链接也能原样复原同一份练习蓝图。
      const json = JSON.stringify(bp);
      return btoa(unescape(encodeURIComponent(json)));
    };

    const gotoPractice = (bp: any, label: string) => {
      const payload = Object.assign({
        subject: state.subject,
        subjectId: subjectId.value,
        includeFallback: true,
        yearRange: '0',
        types: [],
        difficulty: 'mix',
        count: 20,
        minutes: 0,
        order: 'random'
      }, bp, { label });
      // 带上 subject：答题页顶部科目标签与练习记录 subject_id 都读 route.query.subject
      router.push(
        '/exercise?subject=' + state.subject +
        '&blueprint=' + encodeURIComponent(encodeBlueprint(payload))
      );
    };

    const startByPoint = (sub: SubCategoryItem, point: PointNode) => {
      gotoPractice(
        { pointIds: [point.point_id], subCategoryIds: [sub.id], count: state.count, minutes: state.minutes, order: state.order },
        sub.name + '·' + point.point_name
      );
    };

    const startFallback = (sub: SubCategoryItem) => {
      gotoPractice(
        {
          subCategoryIds: [sub.id],
          pointIds: (sub.fallback && sub.fallback.point_ids) || [],
          includeFallback: true,
          count: state.count,
          minutes: state.minutes
        },
        sub.name + '·其他（未细分）'
      );
    };

    const buildBlueprintBody = () => ({
      subject: state.subject,
      subjectId: subjectId.value,
      subCategoryIds: effectiveSubIds.value,
      pointIds: [],
      includeFallback: state.includeFallback,
      yearRange: state.yearRange,
      types: state.types.slice(),
      difficulty: 'mix',
      count: state.count,
      minutes: state.minutes
    });

    const previewBlueprint = async () => {
      if (!effectiveSubIds.value.length) {
        state.preview = { available: 0, picked: 0, estimatedMinutes: 0, distribution: [], note: '当前科目没有可练习的题目' };
        return;
      }
      const seq = ++state.previewSeq;
      state.previewLoading = true;
      try {
        const res = await getFetch()('/api/quick-practice/blueprint', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(buildBlueprintBody())
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        if (seq === state.previewSeq) state.preview = data; // 丢弃过期响应，避免乱序覆盖
      } catch (e: any) {
        if (seq === state.previewSeq) {
          state.preview = { available: 0, picked: 0, estimatedMinutes: 0, distribution: [], note: '预览计算失败，请稍后重试' };
        }
      } finally {
        if (seq === state.previewSeq) state.previewLoading = false;
      }
    };

    const startBlueprint = () => {
      if (!canStart.value) return;
      gotoPractice(
        {
          subCategoryIds: effectiveSubIds.value,
          includeFallback: state.includeFallback,
          yearRange: state.yearRange,
          types: state.types.slice(),
          count: state.count,
          minutes: state.minutes,
          order: state.order
        },
        scopeName.value || '自定义范围'
      );
    };

    const goBack = () => {
      if (window.history.length > 1) router.back();
      else router.push('/question-bank');
    };

    watch(() => [state.bpSubIds.length, state.includeFallback, state.yearRange, state.count], previewBlueprint);

    onMounted(async () => {
      await loadSubject();
      previewBlueprint();
      // 从题库页「自定义刷题」Tab 进来（focus=blueprint）时直接定位到蓝图表单，
      // 否则移动端用户要先往下翻一整屏考点树才看到刷题条件。
      if (route.query.focus === 'blueprint') {
        const el = document.querySelector('.pc-blueprint-panel');
        if (el && typeof (el as HTMLElement).scrollIntoView === 'function') {
          (el as HTMLElement).scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    });

    return {
      subjects,
      typeOptions,
      state,
      subtitle,
      visibleSubCategories,
      blueprintSubCategories,
      currentAvailable,
      subjectWide,
      scopeName,
      canStart,
      switchSubject,
      toggleSub,
      isL2Open,
      toggleL2,
      toggleBpSub,
      toggleType,
      startByPoint,
      startFallback,
      previewBlueprint,
      startBlueprint,
      loadSubject,
      goBack
    };
  }
});
</script>

<style scoped>
.pc-wrap {
  min-height: 100vh;
  background: #f5f7fb;
  color: var(--color-text, #1a1a1a);
  padding: 16px 24px 40px;
  box-sizing: border-box;
}
.pc-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.pc-back {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  color: #1a2b5f;
}
.pc-back:focus-visible,
.pc-subject:focus-visible,
.pc-sub-row:focus-visible,
.pc-kp-row:focus-visible,
.pc-chip:focus-visible,
.pc-primary:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 2px;
}
.pc-title {
  font-size: 20px;
  line-height: 1.25;
  margin: 0;
}
.pc-subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
}
.pc-header-right {
  margin-left: auto;
  font-size: 12px;
  color: #64748b;
}
.pc-subjects {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}
.pc-subject {
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #1a2b5f;
  padding: 8px 20px;
  border-radius: 999px;
  font-size: 14px;
  cursor: pointer;
}
.pc-subject.active {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}
.pc-main {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 1fr);
  gap: 16px;
  align-items: start;
}
.pc-panel {
  background: #fff;
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
}
.pc-panel-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 12px;
}
.pc-panel-title {
  font-size: 16px;
  margin: 0;
}
.pc-hint {
  font-size: 12px;
  color: #94a3b8;
}
.pc-loading,
.pc-error {
  background: #fff;
  border-radius: 16px;
  padding: 32px;
  text-align: center;
  color: #64748b;
  font-size: 14px;
}
.pc-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid #cbd5e1;
  border-top-color: #2563eb;
  border-radius: 50%;
  margin-right: 8px;
  animation: pc-spin 0.8s linear infinite;
  vertical-align: -2px;
}
@keyframes pc-spin {
  to { transform: rotate(360deg); }
}
@media (prefers-reduced-motion: reduce) {
  .pc-spinner { animation: none; }
}
.pc-empty {
  font-size: 13px;
  color: #94a3b8;
  padding: 12px 4px;
  margin: 0;
}
.pc-sub-block {
  border-top: 1px solid #f1f5f9;
}
.pc-sub-block:first-of-type {
  border-top: none;
}
.pc-sub-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 4px;
  background: none;
  border: none;
  cursor: pointer;
  text-align: left;
}
.pc-sub-name {
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
}
.pc-count {
  margin-left: auto;
  font-size: 12px;
  color: #94a3b8;
}
.pc-caret {
  color: #cbd5e1;
  transition: transform 0.15s ease;
  font-size: 14px;
}
.pc-caret.open {
  transform: rotate(90deg);
}
.pc-tree {
  padding: 0 0 8px 12px;
  border-left: 2px solid #eff3fa;
  margin-left: 6px;
}
.pc-kp-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  margin: 4px 0;
  background: #f8fafc;
  border: 1px solid transparent;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  font-size: 13px;
  color: #1f2937;
}
.pc-kp-row:hover {
  border-color: #dbeafe;
  background: #f0f7ff;
}
.pc-kp-l3 {
  margin-left: 12px;
  background: #fff;
}
.pc-kp-name {
  font-weight: 500;
}
.pc-kp-count {
  margin-left: auto;
  font-size: 12px;
  color: #94a3b8;
}
.pc-go {
  font-size: 12px;
  color: #2563eb;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  padding: 2px 10px;
}
.pc-fallback-row {
  border-style: dashed;
  border-color: #e2e8f0;
  background: #fbfcfe;
}
.pc-capsule {
  font-size: 12px;
  color: #64748b;
  background: #eef2f7;
  border-radius: 999px;
  padding: 1px 8px;
  margin-left: 6px;
}
.pc-field {
  margin-bottom: 14px;
}
.pc-field-inline {
  display: flex;
  align-items: center;
  gap: 8px;
}
.pc-label {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
}
.pc-field-inline .pc-label {
  margin-bottom: 0;
}
/* 范围标题的补充说明：只在需要解释「默认范围」时出现，弱化处理 */
.pc-label-sub {
  margin-left: 6px;
  font-size: 12px;
  color: #94a3b8;
}
/* 预演区顶部的「实际作用范围」：让用户明确这次会从哪些分类出题 */
.pc-preview-scope {
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 4px;
}
.pc-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.pc-chip {
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #334155;
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
}
.pc-chip.active {
  border-color: #2563eb;
  color: #1d4ed8;
  background: #eff6ff;
}
.pc-chip-count {
  color: #94a3b8;
  margin-left: 4px;
}
.pc-chip-reset {
  color: #94a3b8;
}
.pc-select {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 13px;
  background: #fff;
  color: #1f2937;
}
.pc-range {
  width: 100%;
}
.pc-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #334155;
  cursor: pointer;
}
.pc-warn {
  font-size: 12px;
  color: #b45309;
  background: #fffbeb;
  border-radius: 8px;
  padding: 8px 10px;
  margin: 8px 0 0;
}
.pc-preview {
  background: #f8fafc;
  border-radius: 12px;
  padding: 12px;
  margin: 12px 0;
  font-size: 13px;
  color: #334155;
}
.pc-preview-line strong {
  color: #2563eb;
}
.pc-preview-sub {
  color: #94a3b8;
  font-size: 12px;
}
.pc-dist {
  list-style: none;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 0 0;
  margin: 0;
}
.pc-dist li {
  font-size: 12px;
  color: #475569;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  padding: 2px 10px;
}
.pc-primary {
  width: 100%;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 12px;
  padding: 12px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.pc-primary:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}
@media (max-width: 900px) {
  .pc-wrap {
    padding: 12px 12px 32px;
  }
  .pc-main {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
