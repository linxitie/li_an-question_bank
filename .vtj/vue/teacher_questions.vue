<template>
  <div class="teacher-questions">
    <div class="top-nav">
      <span class="nav-logo">砺安题库 · 教师端</span>
      <div class="nav-links">
        <span v-for="tab in navTabs" :key="tab.key" :class="['nav-tab', { active: activeNav === tab.key }]" @click="goTab(tab.key)">{{ tab.label }}</span>
      </div>
      <span class="nav-user">{{ username }}</span>
    </div>

    <div class="page-content">
      <!-- 操作栏 -->
      <div class="toolbar">
        <input class="search-input" v-model="keyword" placeholder="搜索题干关键词..." @keyup.enter="doSearch" />
        <select class="filter-select" v-model="filterSubject" @change="doSearch">
          <option value="">全部科目</option>
          <option :value="1">行测</option>
          <option :value="2">申论</option>
          <option :value="3">公专</option>
        </select>
        <select class="filter-select" v-model="filterDifficulty" @change="doSearch">
          <option value="">全部难度</option>
          <option :value="1">★</option>
          <option :value="2">★★</option>
          <option :value="3">★★★</option>
          <option :value="4">★★★★</option>
          <option :value="5">★★★★★</option>
        </select>
        <button class="btn-search" @click="doSearch">搜索</button>
        <div class="toolbar-spacer"></div>
        <button class="btn-import" @click="goImport">📤 题目导入</button>
      </div>

      <!-- 题目表格 -->
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>题目ID</th>
              <th>题干摘要</th>
              <th>科目</th>
              <th>题型</th>
              <th>难度</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="q in questions" :key="q.question_id">
              <td>{{ q.question_id }}</td>
              <td class="td-content" @click="showDetail(q)">{{ truncate(q.question_content, 60) }}</td>
              <td>{{ subjectName(q.subject_id) }}</td>
              <td>{{ q.type_id || '-' }}</td>
              <td>{{ '★'.repeat(q.difficulty || 1) }}</td>
              <td class="td-actions">
                <button class="btn-action" @click="editQuestion(q)">✏️</button>
                <button class="btn-action btn-danger" @click="deleteQuestion(q.question_id)">🗑️</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div class="pagination">
        <button :disabled="page <= 1" @click="changePage(page - 1)">◀</button>
        <span>第 {{ page }} / {{ totalPages }} 页，共 {{ total }} 条</span>
        <button :disabled="page >= totalPages" @click="changePage(page + 1)">▶</button>
      </div>
    </div>

    <!-- 题目详情弹窗 -->
    <div class="modal-overlay" v-if="showModal" @click.self="showModal = false">
      <div class="modal-content">
        <h3>题目详情 #{{ currentQuestion.question_id }}</h3>
        <div class="detail-field"><strong>题干：</strong><div v-html="currentQuestion.full_content"></div></div>
        <div class="detail-field"><strong>答案：</strong>{{ currentQuestion.answer }}</div>
        <div class="detail-field"><strong>解析：</strong>{{ currentQuestion.answer_analysis || '暂无' }}</div>
        <button class="btn-close" @click="showModal = false">关闭</button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'TeacherQuestions',
  setup() {
    const provider = useProvider({ id: 'teacher_questions', version: '1' });
    const router = useRouter();

    const activeNav = ref('questions');
    const username = ref('');
    const keyword = ref('');
    const filterSubject = ref('');
    const filterDifficulty = ref('');
    const questions: any = ref([]);
    const page = ref(1);
    const pageSize = 20;
    const total = ref(0);
    const showModal = ref(false);
    const currentQuestion: any = ref({});

    const navTabs = [
      { key: 'dashboard', label: '工作台', path: '/teacher/dashboard' },
      { key: 'questions', label: '题目管理', path: '/teacher/questions' },
      { key: 'papers', label: '试卷管理', path: '/teacher/papers' },
      { key: 'scores', label: '成绩管理', path: '/teacher/scores' },
    ];

    const totalPages = ref(0);

    onMounted(async () => {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) username.value = auth.getUsername() || '教师';
      await loadQuestions();
    });

    async function loadQuestions() {
      const auth = (window as any).__VTJ_AUTH__;
      const params = new URLSearchParams();
      if (keyword.value) params.append('keyword', keyword.value);
      if (filterSubject.value) params.append('subject_id', filterSubject.value);
      if (filterDifficulty.value) params.append('difficulty', filterDifficulty.value);
      params.append('page', String(page.value));
      params.append('page_size', String(pageSize));

      try {
        const res = await auth.apiFetch(`/api/teacher/questions?${params.toString()}`);
        const data = await res.json();
        if (data.success) {
          questions.value = data.items || [];
          total.value = data.total;
          totalPages.value = Math.ceil(data.total / pageSize);
        }
      } catch (e) { console.error('加载题目失败:', e); }
    }

    function doSearch() { page.value = 1; loadQuestions(); }
    function changePage(p: number) { page.value = p; loadQuestions(); }
    function showDetail(q: any) { currentQuestion.value = q; showModal.value = true; }
    function subjectName(id: number) { return { 1: '行测', 2: '申论', 3: '公专' }[id] || '-'; }
    function truncate(text: string, len: number) { return text && text.length > len ? text.substring(0, len) + '...' : text || ''; }
    function goTab(key: string) { activeNav.value = key; const tab = navTabs.find(t => t.key === key); if (tab) router.push(tab.path); }
    function goImport() { router.push('/question-import'); }

    async function editQuestion(q: any) {
      const newContent = prompt('编辑题干：', q.full_content || q.question_content);
      if (newContent !== null) {
        const auth = (window as any).__VTJ_AUTH__;
        await auth.apiFetch(`/api/teacher/questions/${q.question_id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question_content: newContent })
        });
        loadQuestions();
      }
    }

    async function deleteQuestion(id: number) {
      if (confirm('确定要删除这道题目吗？')) {
        const auth = (window as any).__VTJ_AUTH__;
        await auth.apiFetch(`/api/teacher/questions/${id}`, { method: 'DELETE' });
        loadQuestions();
      }
    }

    return { provider, activeNav, username, navTabs, keyword, filterSubject, filterDifficulty, questions, page, total, totalPages, showModal, currentQuestion, doSearch, changePage, showDetail, subjectName, truncate, goTab, goImport, editQuestion, deleteQuestion };
  }
});
</script>

<style scoped>
.teacher-questions { min-height: 100vh; background: #F5F7FA; font-size: 15px; }
.top-nav { display: flex; align-items: center; padding: 0 24px; height: 56px; background: #1A3C6D; color: #fff; }
.nav-logo { font-size: 16px; font-weight: 600; margin-right: 32px; }
.nav-links { display: flex; gap: 4px; flex: 1; }
.nav-tab { padding: 8px 16px; border-radius: 6px; cursor: pointer; color: rgba(255,255,255,0.7); }
.nav-tab:hover, .nav-tab.active { color: #fff; background: rgba(255,255,255,0.15); font-weight: 600; }
.nav-user { font-size: 14px; }
.page-content { max-width: 1300px; margin: 0 auto; padding: 24px; }
.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 20px; flex-wrap: wrap; }
.search-input { flex: 1; min-width: 200px; padding: 8px 14px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; }
.filter-select { padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; }
.btn-search { padding: 8px 20px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.btn-import { padding: 8px 20px; background: #C41E3A; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.toolbar-spacer { flex: 1; }
.table-wrap { background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { padding: 12px 14px; background: #fafafa; text-align: left; font-weight: 600; color: #1A3C6D; border-bottom: 2px solid #e8e8e8; font-size: 14px; }
.data-table td { padding: 12px 14px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.td-content { color: #1A3C6D; cursor: pointer; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.td-content:hover { text-decoration: underline; }
.td-actions { white-space: nowrap; }
.btn-action { padding: 4px 8px; border: 1px solid #d9d9d9; background: #fff; border-radius: 4px; cursor: pointer; margin-right: 4px; }
.btn-danger:hover { background: #C41E3A; color: #fff; border-color: #C41E3A; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 16px; margin-top: 20px; }
.pagination button { padding: 8px 16px; border: 1px solid #d9d9d9; background: #fff; border-radius: 6px; cursor: pointer; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: #fff; border-radius: 12px; padding: 28px; max-width: 700px; width: 90%; max-height: 80vh; overflow-y: auto; }
.modal-content h3 { color: #1A3C6D; margin: 0 0 16px; }
.detail-field { margin-bottom: 12px; line-height: 1.7; }
.btn-close { margin-top: 16px; padding: 8px 24px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
</style>
