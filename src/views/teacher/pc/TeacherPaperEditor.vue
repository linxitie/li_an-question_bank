<template>
  <div class="paper-workspace">
    <TeacherNavHeader activeNav="papers" @logout="handleLogout" />

    <main class="pw-main">
      <!-- 试卷列表 -->
      <template v-if="view === 'list'">
        <header class="pw-head">
          <div>
            <h1>试卷管理</h1>
            <p>双栏工作台：左侧全量题库、右侧本卷题目，1:1 预览与编辑；预览包含答案解析。</p>
          </div>
          <button type="button" class="pw-primary" @click="openCreate">＋ 新建试卷</button>
        </header>

        <div class="pw-toolbar">
          <input v-model.trim="listKeyword" type="search" placeholder="搜索试卷名称">
          <select v-model="listStatus">
            <option value="">全部状态</option>
            <option value="DRAFT">草稿</option>
            <option value="PENDING">待审批</option>
            <option value="APPROVED">已审批</option>
            <option value="PUBLISHED">已发布</option>
          </select>
          <button type="button" @click="loadPapers">查询</button>
          <button type="button" @click="loadPapers">刷新</button>
        </div>

        <div class="pw-layout">
          <section class="pw-list-card">
            <table class="pw-table">
              <thead><tr><th>试卷</th><th>科目</th><th>题数</th><th>总分</th><th>状态</th><th>更新时间</th><th></th></tr></thead>
              <tbody>
                <tr v-for="p in filteredPapers" :key="p.paper_id">
                  <td><strong>{{ p.paper_name }}</strong><small>#{{ p.paper_id }}</small></td>
                  <td>{{ subjectName(p.subject_id) }}</td>
                  <td>{{ p.question_count || 0 }}</td>
                  <td>{{ p.total_score || 0 }}</td>
                  <td><span class="pw-tag">{{ statusLabel(p.paper_type || p.status) }}</span></td>
                  <td>{{ formatTime(p.update_time || p.create_time) }}</td>
                  <td>
                    <button v-if="isOwner(p)" type="button" class="pw-link" @click="openPaper(p)">编辑</button>
                    <span v-else class="pw-readonly">只读</span>
                  </td>
                </tr>
                <tr v-if="!filteredPapers.length"><td colspan="7" class="pw-empty">暂无试卷，点击右上角新建。</td></tr>
              </tbody>
            </table>
            <footer class="pw-pager">
              <button type="button" :disabled="page <= 1" @click="page--; loadPapers()">上一页</button>
              <span>第 {{ page }} 页 · 共 {{ total }} 份</span>
              <button type="button" :disabled="page * pageSize >= total" @click="page++; loadPapers()">下一页</button>
            </footer>
          </section>

          <aside class="pw-history">
            <h2>最近编辑</h2>
            <p class="pw-hint">本地记录，仅当前浏览器可见。</p>
            <button v-for="item in history" :key="item.id + '-' + item.time" type="button" class="pw-history-item" @click="openPaperById(item.id)">
              <strong>{{ item.name }}</strong>
              <span>{{ formatTime(item.time) }}</span>
            </button>
            <div v-if="!history.length" class="pw-empty">还没有编辑记录。</div>
          </aside>
        </div>
      </template>

      <!-- 编辑器 -->
      <template v-else>
        <header class="pw-editor-head">
          <button type="button" class="pw-back" @click="backToList">← 返回列表</button>
          <div class="pw-title">
            <input v-model.trim="paperForm.paper_name" class="pw-title-input" aria-label="试卷名称">
            <span class="pw-tag">{{ statusLabel(paperForm.paper_type || paperForm.status) }}</span>
          </div>
          <div class="pw-editor-actions">
            <button type="button" :class="{ on: rightMode === 'edit' }" @click="rightMode = 'edit'">编辑</button>
            <button type="button" :class="{ on: rightMode === 'preview' }" @click="rightMode = 'preview'">预览</button>
            <button type="button" @click="saveMeta">保存</button>
            <button type="button" class="pw-primary" @click="publishPaper">发布</button>
          </div>
        </header>

        <section class="pw-meta">
          <label>科目<select v-model.number="paperForm.subject_id" @change="onSubjectChange"><option :value="1">行测</option><option :value="2">申论</option><option :value="3">公专</option></select></label>
          <label>时长<input v-model.number="paperForm.duration" type="number" min="10" max="300"> 分钟</label>
          <label>总分<input v-model.number="paperForm.total_score" type="number" min="1" max="300"></label>
          <span class="pw-meta-stat">本卷 {{ paperQuestions.length }} 题 · 合计 {{ paperTotalScore }} 分</span>
        </section>

        <div class="pw-editor-grid">
          <!-- 左：题库 -->
          <section class="pw-pane">
            <header class="pw-pane-head">
              <h2>从题库添加题目</h2>
              <span>{{ availableTotal }} 道匹配</span>
            </header>
            <div class="pw-filters">
              <input v-model.trim="filters.keyword" type="search" placeholder="搜索题干关键词…" @keyup.enter="resetAndSearch">
              <select v-model.number="filters.subject_id" @change="onSubjectChange"><option :value="0">全部科目</option><option :value="1">行测</option><option :value="2">申论</option><option :value="3">公专</option></select>
              <select v-model="filters.type_name"><option value="">全部题型</option><option v-for="t in questionTypes" :key="t.type_name" :value="t.type_name">{{ t.type_name }}</option></select>
              <select v-model.number="filters.difficulty"><option :value="0">全部难度</option><option v-for="d in 5" :key="d" :value="d">{{ '★'.repeat(d) }}</option></select>
              <select v-model.number="filters.point_id"><option :value="0">全部知识点</option><option v-for="p in knowledgePoints" :key="p.point_id" :value="p.point_id">{{ p.group_name ? p.group_name + ' / ' : '' }}{{ p.point_name }}</option></select>
              <button type="button" class="pw-primary" @click="resetAndSearch">筛选</button>
              <button type="button" @click="resetFilters">重置</button>
            </div>

            <div class="pw-bulk">
              <label><input type="checkbox" :checked="allVisibleChecked" @change="toggleVisible"> 全选本页</label>
              <span>已选 {{ checked.length }} 题</span>
              <button type="button" class="pw-primary" :disabled="!checked.length" @click="addChecked">加入本卷（{{ checked.length }}）</button>
            </div>

            <div class="pw-questions" @scroll="onLeftScroll">
              <article v-for="q in availableQuestions" :key="q.question_id" class="pw-q"
                       :class="{ checked: checked.includes(q.question_id), 'in-paper': inPaper(q.question_id) }"
                       @click="toggleCheck(q.question_id)">
                <input type="checkbox" :checked="checked.includes(q.question_id)"
                       :disabled="inPaper(q.question_id)" @click.stop="toggleCheck(q.question_id)">
                <div class="pw-q-body">
                  <div class="pw-q-meta">
                    <span class="pw-tag">{{ q.type_name || '未标注' }}</span>
                    <span class="pw-tag">{{ subjectName(q.subject_id) }}</span>
                    <span v-if="q.group_id > 0" class="pw-tag group">题组 {{ q.group_id }}</span>
                    <span v-if="inPaper(q.question_id)" class="pw-tag added">已在卷</span>
                    <span class="pw-stars">{{ '★'.repeat(q.difficulty || 3) }}</span>
                    <span v-if="q.point_name" class="pw-point" :title="q.point_name">{{ q.point_name }}</span>
                  </div>
                  <p class="pw-q-text">{{ truncate(q.question_content, 96) }}</p>
                </div>
              </article>
              <div v-if="!availableQuestions.length && !pickerLoading" class="pw-empty">没有匹配题目，试试放宽筛选。</div>
              <div v-if="pickerLoading" class="pw-empty">加载中…</div>
              <button v-if="availableQuestions.length < availableTotal" type="button" class="pw-load-more" :disabled="pickerLoading" @click="loadPicker(false)">加载更多</button>
            </div>
          </section>

          <!-- 右：本卷 -->
          <section class="pw-pane">
            <header class="pw-pane-head">
              <h2>本卷题目（{{ paperQuestions.length }}）</h2>
              <div class="pw-pane-tools">
                <input v-model.trim="paperKeyword" type="search" placeholder="卷内搜索题干/题型">
                <span v-if="paperQuestions.length">{{ paperTotalScore }} 分</span>
              </div>
            </header>

            <div class="pw-questions right" :class="{ preview: rightMode === 'preview' }">
              <article v-for="(q, index) in filteredPaperQuestions" :key="q.question_id" class="pw-paper-q">
                <div class="pw-paper-q-head">
                  <span class="pw-order">{{ index + 1 }}</span>
                  <div class="pw-q-meta">
                    <span class="pw-tag">{{ q.type_name || '未标注' }}</span>
                    <span v-if="q.group_id > 0" class="pw-tag group">题组 {{ q.group_id }}</span>
                  </div>
                  <input class="pw-score" type="number" min="0.5" step="0.5" :value="q.question_score"
                         aria-label="本题分值" @change="updateScore(q, $event)">
                  <div class="pw-row-actions">
                    <button type="button" title="上移" @click="moveQuestion(q.question_id, -1)">↑</button>
                    <button type="button" title="下移" @click="moveQuestion(q.question_id, 1)">↓</button>
                    <button type="button" title="移除" @click="removeQuestion(q.question_id)">✕</button>
                  </div>
                </div>

                <div v-if="rightMode === 'preview'" class="pw-preview">
                  <div class="pw-preview-stem" v-html="render(q.question_content)"></div>
                  <div v-if="q.options && q.options.length" class="pw-preview-options">
                    <div v-for="opt in q.options" :key="opt.key" class="pw-option">
                      <b>{{ opt.key }}</b><span v-html="render(opt.value)"></span>
                    </div>
                  </div>
                  <div class="pw-answer"><b>正确答案：</b>{{ q.answer || '—' }}</div>
                  <div class="pw-analysis">
                    <b>答案解析：</b>
                    <div v-html="render(q.answer_analysis || '暂无解析')"></div>
                  </div>
                </div>
                <p v-else class="pw-q-text">{{ truncate(q.question_content, 110) }}</p>
              </article>
              <div v-if="!filteredPaperQuestions.length" class="pw-empty">本卷还没有题目，从左侧勾选后加入。</div>
            </div>
          </section>
        </div>
      </template>
    </main>

    <!-- 新建试卷 -->
    <div v-if="createOpen" class="pw-modal-mask" @click.self="createOpen = false">
      <section class="pw-modal" role="dialog" aria-label="新建试卷">
        <h2>新建试卷</h2>
        <label>试卷名称<input v-model.trim="createForm.paper_name" placeholder="例如：2026 年行测模拟卷（一）"></label>
        <div class="pw-modal-row">
          <label>科目<select v-model.number="createForm.subject_id"><option :value="1">行测</option><option :value="2">申论</option><option :value="3">公专</option></select></label>
          <label>时长<input v-model.number="createForm.duration" type="number" min="10"></label>
          <label>总分<input v-model.number="createForm.total_score" type="number" min="1"></label>
        </div>
        <p class="pw-hint">创建后进入双栏编辑器，可继续选题、调分与预览。</p>
        <footer>
          <button type="button" @click="createOpen = false">取消</button>
          <button type="button" class="pw-primary" :disabled="creating" @click="createPaper">{{ creating ? '创建中…' : '创建并编辑' }}</button>
        </footer>
      </section>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { computed, defineComponent, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import TeacherNavHeader from '$vtj/vue/TeacherNavHeader.vue';
import { renderQuestionContent, renderQuestionSummary } from '@/utils/questionRender';

const HISTORY_KEY = 'teacher-paper-editor-history';

export default defineComponent({
  name: 'TeacherPaperEditor',
  components: { TeacherNavHeader },
  setup() {
    const router = useRouter();
    const view = ref('list');
    const papers = ref<any[]>([]);
    const total = ref(0);
    const page = ref(1);
    const pageSize = 20;
    const listKeyword = ref('');
    const listStatus = ref('');
    const history = ref<any[]>([]);

    const createOpen = ref(false);
    const creating = ref(false);
    const createForm = reactive<any>({ paper_name: '', subject_id: 1, exam_type: 'SIMULATION', duration: 120, difficulty: 3, total_score: 100 });
    const paperForm = reactive<any>({ paper_id: 0, paper_name: '', subject_id: 1, duration: 120, total_score: 100, status: 'DRAFT', paper_type: 'DRAFT' });
    const paperQuestions = ref<any[]>([]);
    const paperKeyword = ref('');
    const rightMode = ref('edit');

    const availableQuestions = ref<any[]>([]);
    const availableTotal = ref(0);
    const pickerPage = ref(1);
    const pickerLoading = ref(false);
    const checked = ref<number[]>([]);
    const filters = reactive<any>({ keyword: '', subject_id: 0, type_name: '', difficulty: 0, point_id: 0 });
    const questionTypes = ref<any[]>([]);
    const knowledgePoints = ref<any[]>([]);

    const filteredPapers = computed(function () {
      const key = listKeyword.value.toLowerCase();
      if (!key) return papers.value;
      return papers.value.filter(function (p: any) {
        return String(p.paper_name || '').toLowerCase().indexOf(key) >= 0;
      });
    });

    const filteredPaperQuestions = computed(function () {
      const key = paperKeyword.value.toLowerCase();
      if (!key) return paperQuestions.value;
      return paperQuestions.value.filter(function (q: any) {
        return String(q.question_content || '').toLowerCase().indexOf(key) >= 0 ||
          String(q.type_name || '').toLowerCase().indexOf(key) >= 0;
      });
    });

    const paperTotalScore = computed(function () {
      return Math.round(paperQuestions.value.reduce(function (sum: number, q: any) {
        return sum + (Number(q.question_score) || 0);
      }, 0) * 100) / 100;
    });

    // 已加入本卷的题仍留在左栏（否则用户看不到全部题库），只是不可重复勾选。
    function inPaper(qid: number) {
      return paperQuestions.value.some(function (q: any) { return q.question_id === qid; });
    }

    const allVisibleChecked = computed(function () {
      const selectable = availableQuestions.value.filter(function (q: any) { return !inPaper(q.question_id); });
      return selectable.length > 0 && selectable.every(function (q: any) {
        return checked.value.indexOf(q.question_id) >= 0;
      });
    });

    function authFetch(url: string, options?: any) {
      const auth = (window as any).__VTJ_AUTH__;
      if (!auth || !auth.apiFetch) return Promise.reject(new Error('登录态失效，请重新登录'));
      return auth.apiFetch(url, options);
    }

    async function json(res: any) {
      return res.json().catch(function () { return {}; });
    }

    function loadHistory() {
      try {
        const raw = localStorage.getItem(HISTORY_KEY);
        history.value = raw ? JSON.parse(raw).slice(0, 8) : [];
      } catch (e) {
        history.value = [];
      }
    }

    function pushHistory(paper: any) {
      const next = [{ id: paper.paper_id, name: paper.paper_name, time: new Date().toISOString() }]
        .concat(history.value.filter(function (h: any) { return h.id !== paper.paper_id; }))
        .slice(0, 8);
      history.value = next;
      try { localStorage.setItem(HISTORY_KEY, JSON.stringify(next)); } catch (e) { /* 忽略隐私模式写入失败 */ }
    }

    async function loadPapers() {
      try {
        const params = new URLSearchParams();
        params.append('page', String(page.value));
        params.append('page_size', String(pageSize));
        if (listStatus.value) params.append('status', listStatus.value);
        const res = await authFetch('/api/teacher/papers?' + params.toString());
        const data = await json(res);
        if (data.success) { papers.value = data.items || []; total.value = data.total || 0; }
      } catch (e) {
        ElMessage.error('试卷列表加载失败');
      }
    }

    function openCreate() {
      createForm.paper_name = '';
      createForm.subject_id = 1;
      createForm.duration = 120;
      createForm.total_score = 100;
      createOpen.value = true;
    }

    async function createPaper() {
      if (!createForm.paper_name.trim()) { ElMessage.warning('请输入试卷名称'); return; }
      creating.value = true;
      try {
        const res = await authFetch('/api/teacher/papers', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(createForm),
        });
        const data = await json(res);
        if (!data.success) throw new Error(data.message || '创建失败');
        createOpen.value = false;
        await openPaperById(data.paper_id);
      } catch (e: any) {
        ElMessage.error(e.message || '创建失败');
      } finally {
        creating.value = false;
      }
    }

    function openPaper(paper: any) {
      openPaperById(paper.paper_id);
    }

    async function openPaperById(paperId: number) {
      try {
        const res = await authFetch('/api/teacher/papers/' + paperId);
        const data = await json(res);
        if (!data.success) throw new Error(data.message || '试卷不存在');
        const paper = data.paper || {};
        Object.assign(paperForm, {
          paper_id: paper.paper_id || paperId,
          paper_name: paper.paper_name || '',
          subject_id: paper.subject_id || 1,
          duration: paper.duration || 120,
          total_score: paper.total_score || 100,
          status: paper.paper_type || paper.status || 'DRAFT',
          paper_type: paper.paper_type || paper.status || 'DRAFT',
        });
        paperQuestions.value = data.questions || [];
        view.value = 'editor';
        rightMode.value = 'edit';
        checked.value = [];
        pushHistory({ paper_id: paperForm.paper_id, paper_name: paperForm.paper_name });
        filters.subject_id = paperForm.subject_id;
        await Promise.all([loadQuestionTypes(), loadKnowledgePoints(), loadPicker(true)]);
      } catch (e: any) {
        ElMessage.error(e.message || '试卷加载失败');
      }
    }

    function backToList() {
      view.value = 'list';
      loadPapers();
    }

    async function saveMeta() {
      try {
        const res = await authFetch('/api/teacher/papers/' + paperForm.paper_id, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
            paper_name: paperForm.paper_name,
            subject_id: paperForm.subject_id,
            duration: paperForm.duration,
            total_score: paperForm.total_score,
          }),
        });
        const data = await json(res);
        if (!data.success) throw new Error(data.message || '保存失败');
        ElMessage.success('已保存');
        pushHistory({ paper_id: paperForm.paper_id, paper_name: paperForm.paper_name });
      } catch (e: any) {
        ElMessage.error(e.message || '保存失败');
      }
    }

    async function publishPaper() {
      try {
        await saveMeta();
        const res = await authFetch('/api/teacher/papers/' + paperForm.paper_id + '/publish', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ publish_target: 'past_paper' }),
        });
        const data = await json(res);
        if (!data.success) throw new Error(data.message || '发布失败');
        paperForm.status = 'PUBLISHED';
        paperForm.paper_type = 'PUBLISHED';
        ElMessage.success('已发布到历年试卷');
      } catch (e: any) {
        ElMessage.error(e.message || '发布失败');
      }
    }

    async function loadQuestionTypes() {
      try {
        const res = await authFetch('/api/teacher/question-types');
        const data = await json(res);
        if (data.success) questionTypes.value = data.items || [];
      } catch (e) { /* 下拉为空时仍可搜索 */ }
    }

    // 与学生端题库同一棵树（/quick-practice/sub-categories），
    // 按「子科目 / 二级考点」分组展平，避免教师端自造一套 L3-only 口径。
    async function loadKnowledgePoints() {
      const subjects = filters.subject_id ? [filters.subject_id] : [1, 2, 3];
      try {
        const trees = await Promise.all(subjects.map(async function (sid: number) {
          const res = await authFetch('/api/quick-practice/sub-categories?subjectId=' + sid);
          const data = await json(res);
          return data.items || [];
        }));
        const flat: any[] = [];
        trees.forEach(function (items: any[]) {
          items.forEach(function (sub: any) {
            (sub.knowledge_points || []).forEach(function (l2: any) {
              flat.push({ point_id: l2.point_id, point_name: l2.point_name, group_name: sub.name });
              (l2.children || []).forEach(function (l3: any) {
                flat.push({ point_id: l3.point_id, point_name: l3.point_name, group_name: sub.name + ' / ' + l2.point_name });
              });
            });
          });
        });
        const seen: Record<number, boolean> = {};
        knowledgePoints.value = flat.filter(function (p: any) {
          if (!p.point_id || seen[p.point_id]) return false;
          seen[p.point_id] = true;
          return true;
        });
      } catch (e) { knowledgePoints.value = []; }
    }

    async function onSubjectChange() {
      filters.point_id = 0;
      await loadKnowledgePoints();
      await resetAndSearch();
    }

    async function loadPicker(reset: boolean) {
      if (reset) {
        pickerPage.value = 1;
        availableQuestions.value = [];
      }
      pickerLoading.value = true;
      try {
        const params = new URLSearchParams();
        if (filters.keyword) params.append('keyword', filters.keyword);
        if (filters.subject_id) params.append('subject_id', String(filters.subject_id));
        if (filters.type_name) params.append('type_name', filters.type_name);
        if (filters.difficulty) params.append('difficulty', String(filters.difficulty));
        if (filters.point_id) params.append('point_id', String(filters.point_id));
        params.append('page', String(pickerPage.value));
        params.append('page_size', '50');
        const res = await authFetch('/api/teacher/questions?' + params.toString());
        const data = await json(res);
        if (data.success) {
          const items = data.items || [];
          availableQuestions.value = reset ? items : availableQuestions.value.concat(items);
          availableTotal.value = data.total || items.length;
        }
      } catch (e) {
        ElMessage.error('题库加载失败');
      } finally {
        pickerLoading.value = false;
      }
    }

    async function resetAndSearch() {
      await loadPicker(true);
    }

    function resetFilters() {
      filters.keyword = '';
      filters.subject_id = 0;
      filters.type_name = '';
      filters.difficulty = 0;
      filters.point_id = 0;
      loadKnowledgePoints();
      loadPicker(true);
    }

    function onLeftScroll(ev: Event) {
      const el = ev.target as HTMLElement;
      if (!el || pickerLoading.value) return;
      if (availableQuestions.value.length >= availableTotal.value) return;
      if (el.scrollTop + el.clientHeight >= el.scrollHeight - 120) {
        pickerPage.value += 1;
        loadPicker(false);
      }
    }

    function toggleCheck(qid: number) {
      if (inPaper(qid)) return;
      const i = checked.value.indexOf(qid);
      if (i >= 0) checked.value.splice(i, 1);
      else checked.value.push(qid);
    }

    function toggleVisible() {
      if (allVisibleChecked.value) {
        const ids = availableQuestions.value.map(function (q: any) { return q.question_id; });
        checked.value = checked.value.filter(function (id) { return ids.indexOf(id) < 0; });
      } else {
        availableQuestions.value.forEach(function (q: any) {
          if (!inPaper(q.question_id) && checked.value.indexOf(q.question_id) < 0) checked.value.push(q.question_id);
        });
      }
    }

    async function addChecked() {
      if (!checked.value.length) return;
      const start = paperQuestions.value.length;
      const items = checked.value.map(function (qid, index) {
        return { question_id: qid, question_order: start + index + 1, question_score: 5 };
      });
      try {
        const res = await authFetch('/api/teacher/papers/' + paperForm.paper_id + '/questions', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ questions: items }),
        });
        const data = await json(res);
        if (!data.success) throw new Error(data.message || '添加失败');
        ElMessage.success('已加入 ' + items.length + ' 题');
        checked.value = [];
        await reloadPaperQuestions();
      } catch (e: any) {
        ElMessage.error(e.message || '添加失败');
      }
    }

    async function reloadPaperQuestions() {
      const res = await authFetch('/api/teacher/papers/' + paperForm.paper_id);
      const data = await json(res);
      if (data.success) paperQuestions.value = data.questions || [];
      await loadPicker(true);
    }

    async function removeQuestion(qid: number) {
      try {
        await authFetch('/api/teacher/papers/' + paperForm.paper_id + '/questions/' + qid, { method: 'DELETE' });
        await reloadPaperQuestions();
      } catch (e) { ElMessage.error('移除失败'); }
    }

    async function updateScore(question: any, ev: Event) {
      const value = Number((ev.target as HTMLInputElement).value);
      if (!value || value <= 0) { (ev.target as HTMLInputElement).value = question.question_score; return; }
      try {
        await authFetch('/api/teacher/papers/' + paperForm.paper_id + '/questions/' + question.question_id, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question_score: value }),
        });
        question.question_score = value;
      } catch (e) {
        ElMessage.error('更新分值失败');
        (ev.target as HTMLInputElement).value = question.question_score;
      }
    }

    async function moveQuestion(qid: number, dir: number) {
      const ids = paperQuestions.value.map(function (q: any) { return q.question_id; });
      const at = ids.indexOf(qid);
      const to = at + dir;
      if (at < 0 || to < 0 || to >= ids.length) return;
      const tmp = ids[at];
      ids[at] = ids[to];
      ids[to] = tmp;
      try {
        await authFetch('/api/teacher/papers/' + paperForm.paper_id + '/questions/order', {
          method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question_ids: ids }),
        });
        await reloadPaperQuestions();
      } catch (e) { ElMessage.error('排序失败'); }
    }

    function isOwner(paper: any) {
      try {
        const auth = (window as any).__VTJ_AUTH__;
        const info = auth && auth.parseUserInfo ? auth.parseUserInfo() : {};
        return Number(paper.creator_id) === Number(info.userId);
      } catch (e) {
        return false;
      }
    }

    function statusLabel(value: string) {
      const map: Record<string, string> = { DRAFT: '草稿', PENDING: '待审批', APPROVED: '已审批', PUBLISHED: '已发布', ENDED: '已结束' };
      return map[value] || value || '草稿';
    }
    function subjectName(id: number) { return ({ 1: '行测', 2: '申论', 3: '公专' } as any)[id] || '—'; }
    function formatTime(value: string) { return value ? String(value).substring(0, 16).replace('T', ' ') : '—'; }
    function truncate(text: string, len: number) { const clean = renderQuestionSummary(String(text || '')); return clean.length > len ? clean.substring(0, len) + '…' : clean; }
    function render(html: string) { return renderQuestionContent(html || ''); }

    function handleLogout() {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) auth.logout();
      router.push('/login');
    }

    onMounted(function () {
      loadHistory();
      loadPapers();
    });

    return {
      view, papers, total, page, pageSize, listKeyword, listStatus, history, filteredPapers,
      createOpen, creating, createForm, paperForm, paperQuestions, paperKeyword, rightMode,
      availableQuestions, availableTotal, pickerLoading, checked, filters, questionTypes, knowledgePoints,
      filteredPaperQuestions, paperTotalScore, allVisibleChecked, inPaper,
      loadPapers, openCreate, createPaper, openPaper, openPaperById, backToList, saveMeta, publishPaper,
      onSubjectChange, loadPicker, resetAndSearch, resetFilters, onLeftScroll, toggleCheck, toggleVisible,
      addChecked, removeQuestion, updateScore, moveQuestion, isOwner, statusLabel, subjectName, formatTime, truncate, render, handleLogout,
    };
  },
});
</script>

<style scoped>
.paper-workspace { min-height: 100vh; background: #f5f7fa; color: #1f2937; }
.pw-main { max-width: 1500px; margin: 0 auto; padding: 20px 22px 40px; }
.pw-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 14px; }
.pw-head h1 { margin: 0; color: #1a3c6d; font-size: 24px; }
.pw-head p { margin: 5px 0 0; color: #64748b; font-size: 13px; }
.pw-primary { border: 1px solid #1a3c6d; background: #1a3c6d; color: #fff; border-radius: 7px; padding: 8px 15px; cursor: pointer; white-space: nowrap; }
.pw-primary:disabled { opacity: .5; cursor: not-allowed; }
.pw-toolbar { display: flex; gap: 10px; align-items: center; background: #fff; border-radius: 9px; padding: 11px 14px; margin-bottom: 14px; }
.pw-toolbar input, .pw-toolbar select, .pw-filters input, .pw-filters select { border: 1px solid #cbd5e1; border-radius: 6px; padding: 7px 9px; font-size: 13px; background: #fff; }
.pw-toolbar input { min-width: 240px; }
.pw-toolbar button { border: 1px solid #cbd5e1; background: #fff; border-radius: 6px; padding: 7px 12px; cursor: pointer; }
.pw-layout { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 14px; }
.pw-list-card, .pw-history, .pw-pane { background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(15, 23, 42, .05); }
.pw-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.pw-table th { text-align: left; padding: 12px; background: #f8fafc; color: #475569; border-bottom: 1px solid #e2e8f0; }
.pw-table td { padding: 11px 12px; border-bottom: 1px solid #f1f5f9; }
.pw-table small { display: block; color: #94a3b8; margin-top: 2px; }
.pw-tag { display: inline-block; background: #eef2f7; color: #475569; border-radius: 4px; padding: 1px 7px; font-size: 11px; white-space: nowrap; }
.pw-tag.group { background: #fef3c7; color: #92400e; }
.pw-link { border: 0; background: transparent; color: #2563eb; cursor: pointer; }
.pw-readonly { color: #94a3b8; font-size: 12px; }
.pw-pager { display: flex; align-items: center; justify-content: center; gap: 16px; padding: 12px; color: #64748b; font-size: 13px; }
.pw-pager button { border: 1px solid #cbd5e1; background: #fff; border-radius: 6px; padding: 5px 11px; cursor: pointer; }
.pw-history { padding: 14px; align-self: start; }
.pw-history h2 { margin: 0 0 4px; font-size: 15px; color: #1a3c6d; }
.pw-history-item { display: block; width: 100%; text-align: left; border: 1px solid #e2e8f0; background: #fbfdff; border-radius: 7px; padding: 9px 10px; margin-top: 8px; cursor: pointer; }
.pw-history-item strong { display: block; font-size: 13px; color: #1f2937; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pw-history-item span { color: #94a3b8; font-size: 11px; }
.pw-editor-head { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.pw-back { border: 1px solid #cbd5e1; background: #fff; border-radius: 6px; padding: 7px 11px; cursor: pointer; }
.pw-title { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0; }
.pw-title-input { border: 0; border-bottom: 1px solid transparent; font-size: 19px; font-weight: 700; color: #1a3c6d; background: transparent; min-width: 280px; flex: 1; max-width: 560px; padding: 3px 2px; }
.pw-title-input:focus { border-bottom-color: #2563eb; outline: none; }
.pw-editor-actions { display: flex; gap: 8px; align-items: center; }
.pw-editor-actions button { border: 1px solid #cbd5e1; background: #fff; border-radius: 6px; padding: 7px 12px; cursor: pointer; }
.pw-editor-actions button.on { border-color: #1a3c6d; background: #e8eef8; color: #1a3c6d; font-weight: 600; }
.pw-meta { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 14px; background: #fff; border-radius: 9px; padding: 11px 14px; margin-bottom: 12px; font-size: 12px; color: #64748b; }
.pw-meta label { display: flex; flex-direction: column; gap: 4px; }
.pw-meta input, .pw-meta select { border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 8px; font-size: 13px; }
.pw-meta input[type=number] { width: 86px; }
.pw-meta-stat { margin-left: auto; color: #1a3c6d; font-weight: 600; }
.pw-editor-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: start; }
.pw-pane { overflow: hidden; }
.pw-pane-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 12px 14px; border-bottom: 1px solid #e2e8f0; }
.pw-pane-head h2 { margin: 0; font-size: 15px; color: #1a3c6d; }
.pw-pane-head span { font-size: 12px; color: #94a3b8; }
.pw-pane-tools { display: flex; align-items: center; gap: 8px; }
.pw-pane-tools input { width: 180px; border: 1px solid #cbd5e1; border-radius: 6px; padding: 5px 8px; font-size: 12px; }
.pw-filters { display: flex; flex-wrap: wrap; gap: 7px; padding: 10px 12px; border-bottom: 1px solid #f1f5f9; }
.pw-filters input { flex: 1 1 180px; min-width: 140px; }
.pw-filters select { max-width: 130px; }
.pw-filters button { border: 1px solid #cbd5e1; background: #fff; border-radius: 6px; padding: 6px 10px; cursor: pointer; }
.pw-bulk { display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: #f8fafc; font-size: 12px; color: #475569; }
.pw-bulk span { margin-left: auto; }
.pw-bulk button { padding: 5px 10px; }
.pw-questions { height: calc(100vh - 300px); min-height: 380px; overflow-y: auto; padding: 10px 12px; }
.pw-q { display: flex; gap: 9px; align-items: flex-start; padding: 10px; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 8px; cursor: pointer; }
.pw-q:hover { border-color: #93b4e0; background: #fafdff; }
.pw-q.checked { border-color: #2563eb; background: #eff6ff; }
.pw-q.in-paper { opacity: 0.62; background: #f8fafc; cursor: default; }
.pw-tag.added { background: #dcfce7; color: #166534; }
.pw-q input { margin-top: 3px; }
.pw-q-body { min-width: 0; flex: 1; }
.pw-q-meta { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; margin-bottom: 5px; }
.pw-stars { color: #f59e0b; font-size: 11px; }
.pw-point { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #64748b; font-size: 11px; border-bottom: 1px dashed #cbd5e1; }
.pw-q-text { margin: 0; color: #334155; font-size: 13px; line-height: 1.6; word-break: break-word; }
.pw-load-more { width: 100%; border: 1px dashed #cbd5e1; background: #fff; border-radius: 6px; padding: 8px; color: #475569; cursor: pointer; }
.pw-questions.right { background: #fbfcfe; }
.pw-paper-q { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 10px; }
.pw-paper-q-head { display: flex; align-items: center; gap: 8px; }
.pw-order { width: 24px; height: 24px; border-radius: 50%; background: #1a3c6d; color: #fff; font-size: 12px; display: inline-flex; align-items: center; justify-content: center; flex: none; }
.pw-score { width: 62px; border: 1px solid #cbd5e1; border-radius: 5px; padding: 3px 5px; font-size: 12px; margin-left: auto; }
.pw-row-actions { display: flex; gap: 2px; }
.pw-row-actions button { border: 1px solid #e2e8f0; background: #fff; border-radius: 4px; width: 25px; height: 25px; cursor: pointer; color: #475569; }
.pw-row-actions button:hover { border-color: #93b4e0; color: #1a3c6d; }
.pw-paper-q .pw-q-text { margin-top: 8px; }
.pw-preview { margin-top: 10px; border-top: 1px dashed #e2e8f0; padding-top: 10px; font-size: 13px; line-height: 1.8; color: #1f2937; }
.pw-preview-stem :deep(img) { max-width: 100%; height: auto; }
.pw-preview-options { margin: 8px 0; display: flex; flex-direction: column; gap: 5px; }
.pw-option { display: flex; gap: 7px; background: #f8fafc; border-radius: 5px; padding: 6px 9px; }
.pw-option b { color: #1a3c6d; flex: none; }
.pw-answer { margin-top: 8px; color: #15803d; }
.pw-analysis { margin-top: 8px; background: #fffbeb; border-left: 3px solid #f59e0b; border-radius: 4px; padding: 8px 10px; color: #78350f; }
.pw-analysis :deep(img) { max-width: 100%; height: auto; }
.pw-empty { color: #94a3b8; text-align: center; padding: 26px 10px; font-size: 13px; }
.pw-modal-mask { position: fixed; inset: 0; z-index: 1400; background: rgba(15, 23, 42, .5); display: flex; align-items: center; justify-content: center; padding: 20px; }
.pw-modal { width: min(560px, 96vw); background: #fff; border-radius: 12px; padding: 20px; }
.pw-modal h2 { margin: 0 0 14px; color: #1a3c6d; font-size: 18px; }
.pw-modal label { display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: #64748b; margin-bottom: 10px; }
.pw-modal input, .pw-modal select { border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 9px; font-size: 14px; }
.pw-modal-row { display: flex; gap: 10px; }
.pw-modal-row label { flex: 1; }
.pw-modal footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
.pw-modal footer button { border: 1px solid #cbd5e1; background: #fff; border-radius: 6px; padding: 8px 14px; cursor: pointer; }
.pw-hint { color: #94a3b8; font-size: 12px; }
@media (max-width: 1000px) {
  .pw-editor-grid { grid-template-columns: 1fr; }
  .pw-layout { grid-template-columns: 1fr; }
  .pw-questions { height: 420px; }
}
@media (prefers-reduced-motion: reduce) {
  .pw-q, .pw-paper-q { transition: none; }
}
</style>
