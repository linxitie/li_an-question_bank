<template>
  <div class="teacher-papers">
    <div class="top-nav">
      <span class="nav-logo">砺安题库 · 教师端</span>
      <div class="nav-links">
        <span v-for="tab in navTabs" :key="tab.key" :class="['nav-tab', { active: activeNav === tab.key }]" @click="goTab(tab.key)">{{ tab.label }}</span>
      </div>
      <span class="nav-user">{{ username }}</span>
    </div>

    <div class="page-content">
      <div class="toolbar">
        <button class="btn-primary" @click="createPaper">+ 创建试卷</button>
        <button class="btn-ai" @click="aiGenerate">🤖 AI智能组卷</button>
      </div>

      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr><th>试卷名称</th><th>科目</th><th>题数</th><th>总分</th><th>状态</th><th>创建时间</th><th>操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="p in papers" :key="p.paper_id">
              <td>{{ p.paper_name }}</td>
              <td>{{ p.subject_name }}</td>
              <td>{{ p.question_count }}</td>
              <td>{{ p.total_score }}</td>
              <td><span :class="statusClass(p.paper_type)">{{ statusLabel(p.paper_type) }}</span></td>
              <td>{{ p.create_time }}</td>
              <td>
                <button class="btn-sm" @click="submitApproval(p.paper_id)" v-if="p.paper_type === 'DRAFT'">提交审批</button>
                <button class="btn-sm btn-danger" @click="deletePaper(p.paper_id)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 创建试卷弹窗 -->
    <div class="modal-overlay" v-if="showCreateModal" @click.self="showCreateModal = false">
      <div class="modal-content">
        <h3>创建试卷</h3>
        <div class="form-group"><label>试卷名称</label><input class="form-input" v-model="createForm.paper_name" /></div>
        <div class="form-group"><label>科目</label><select class="form-input" v-model="createForm.subject_id"><option :value="1">行测</option><option :value="2">申论</option><option :value="3">公专</option></select></div>
        <div class="form-group"><label>时长(分钟)</label><input class="form-input" type="number" v-model="createForm.duration" /></div>
        <div class="form-group"><label>总分</label><input class="form-input" type="number" v-model="createForm.total_score" /></div>
        <button class="btn-primary" @click="doCreate" :disabled="creating">{{ creating ? '创建中...' : '确认创建' }}</button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'TeacherPapers',
  setup() {
    const provider = useProvider({ id: 'teacher_papers', version: '1' });
    const router = useRouter();
    const activeNav = ref('papers');
    const username = ref('');
    const papers: any = ref([]);
    const showCreateModal = ref(false);
    const creating = ref(false);
    const createForm = ref({ paper_name: '', subject_id: 1, duration: 120, total_score: 100 });

    const navTabs = [
      { key: 'dashboard', label: '工作台', path: '/teacher/dashboard' },
      { key: 'questions', label: '题目管理', path: '/teacher/questions' },
      { key: 'papers', label: '试卷管理', path: '/teacher/papers' },
      { key: 'scores', label: '成绩管理', path: '/teacher/scores' },
    ];

    onMounted(async () => {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) username.value = auth.getUsername() || '教师';
      await loadPapers();
    });

    async function loadPapers() {
      const auth = (window as any).__VTJ_AUTH__;
      try {
        const res = await auth.apiFetch('/api/teacher/papers');
        const data = await res.json();
        if (data.success) papers.value = data.items || [];
      } catch (e) { console.error('加载试卷失败:', e); }
    }

    function statusLabel(t: string) { return { DRAFT: '草稿', PENDING: '待审批', APPROVED: '已审批', PUBLISHED: '已发布', ENDED: '已结束' }[t] || t; }
    function statusClass(t: string) { return { DRAFT: 'tag-gray', PENDING: 'tag-orange', APPROVED: 'tag-blue', PUBLISHED: 'tag-green', ENDED: 'tag-red' }[t] || ''; }
    function goTab(key: string) { activeNav.value = key; const tab = navTabs.find(t => t.key === key); if (tab) router.push(tab.path); }

    function createPaper() { showCreateModal.value = true; }
    async function doCreate() {
      creating.value = true;
      const auth = (window as any).__VTJ_AUTH__;
      await auth.apiFetch('/api/teacher/papers', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(createForm.value)
      });
      creating.value = false;
      showCreateModal.value = false;
      createForm.value = { paper_name: '', subject_id: 1, duration: 120, total_score: 100 };
      loadPapers();
    }

    async function submitApproval(id: number) {
      const auth = (window as any).__VTJ_AUTH__;
      await auth.apiFetch(`/api/teacher/papers/${id}/submit-approval`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paper_id: id })
      });
      loadPapers();
    }

    async function deletePaper(id: number) {
      if (confirm('确定删除此试卷？')) {
        const auth = (window as any).__VTJ_AUTH__;
        await auth.apiFetch(`/api/teacher/papers/${id}`, { method: 'DELETE' });
        loadPapers();
      }
    }

    async function aiGenerate() {
      const auth = (window as any).__VTJ_AUTH__;
      await auth.apiFetch('/api/teacher/papers/auto-generate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paper_name: 'AI智能组卷', subject_id: 1, difficulty: 3, total_score: 100, duration: 120, question_config: { '单选题': 30, '多选题': 10, '判断题': 10 } })
      });
      loadPapers();
    }

    return { provider, activeNav, username, navTabs, papers, showCreateModal, creating, createForm, statusLabel, statusClass, goTab, createPaper, doCreate, submitApproval, deletePaper, aiGenerate };
  }
});
</script>

<style scoped>
.teacher-papers { min-height: 100vh; background: #F5F7FA; font-size: 15px; }
.top-nav { display: flex; align-items: center; padding: 0 24px; height: 56px; background: #1A3C6D; color: #fff; }
.nav-logo { font-size: 16px; font-weight: 600; margin-right: 32px; }
.nav-links { display: flex; gap: 4px; flex: 1; }
.nav-tab { padding: 8px 16px; border-radius: 6px; cursor: pointer; color: rgba(255,255,255,0.7); }
.nav-tab:hover, .nav-tab.active { color: #fff; background: rgba(255,255,255,0.15); font-weight: 600; }
.nav-user { font-size: 14px; }
.page-content { max-width: 1200px; margin: 0 auto; padding: 24px; }
.toolbar { display: flex; gap: 12px; margin-bottom: 20px; }
.btn-primary { padding: 10px 22px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.btn-ai { padding: 10px 22px; background: #C41E3A; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.table-wrap { background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { padding: 12px 14px; background: #fafafa; text-align: left; font-weight: 600; color: #1A3C6D; border-bottom: 2px solid #e8e8e8; font-size: 14px; }
.data-table td { padding: 12px 14px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.btn-sm { padding: 4px 10px; border: 1px solid #1A3C6D; background: #fff; color: #1A3C6D; border-radius: 4px; cursor: pointer; margin-right: 4px; font-size: 13px; }
.btn-danger { border-color: #C41E3A; color: #C41E3A; }
.btn-danger:hover { background: #C41E3A; color: #fff; }
.tag-gray { color: #888; } .tag-orange { color: #E6A23C; font-weight: 600; } .tag-blue { color: #409EFF; } .tag-green { color: #67C23A; font-weight: 600; } .tag-red { color: #C41E3A; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: #fff; border-radius: 12px; padding: 28px; max-width: 500px; width: 90%; }
.modal-content h3 { color: #1A3C6D; margin: 0 0 16px; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; margin-bottom: 4px; font-weight: 600; color: #333; }
.form-input { width: 100%; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; box-sizing: border-box; }
</style>
