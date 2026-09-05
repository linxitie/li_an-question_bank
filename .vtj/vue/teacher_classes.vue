<template>
  <div class="teacher-classes">
    <TeacherNavHeader activeNav="classes" @logout="handleLogout" />

    <div class="page-content">
      <div class="toolbar">
        <div class="toolbar-spacer"></div>
        <button class="btn-primary" @click="showCreateModal = true">+ 创建班级</button>
      </div>

      <!-- 班级卡片列表 -->
      <div class="class-grid" v-if="classes.length > 0">
        <div class="class-card" v-for="cls in classes" :key="cls.class_id">
          <div class="card-header">
            <h3>{{ cls.class_name }}</h3>
            <button class="btn-sm btn-danger" @click="deleteClass(cls.class_id)">删除</button>
          </div>
          <div class="card-stats">
            <div class="stat-item">
              <div class="stat-value">{{ cls.student_count }}</div>
              <div class="stat-label">学生数</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ cls.avg_score || '--' }}</div>
              <div class="stat-label">平均分</div>
            </div>
          </div>
          <div class="card-footer">
            <span class="create-time">创建于 {{ formatDate(cls.create_time) }}</span>
            <button class="btn-sm btn-primary" @click="openDetail(cls)">查看详情</button>
          </div>
        </div>
      </div>
      <div v-else class="empty-state">
        <div class="empty-icon">🏫</div>
        <div class="empty-text">暂无班级，点击「创建班级」开始</div>
      </div>
    </div>

    <!-- 创建班级弹窗 -->
    <div class="modal-overlay" v-if="showCreateModal" @click.self="showCreateModal = false">
      <div class="modal-content">
        <h3>创建班级</h3>
        <div class="form-group">
          <label>班级名称</label>
          <input class="form-input" v-model="newClassName" placeholder="如：刑侦2201" />
        </div>
        <div class="modal-footer">
          <button class="btn-save" @click="createClass" :disabled="creating">
            {{ creating ? '创建中...' : '创建' }}
          </button>
          <button class="btn-close" @click="showCreateModal = false">取消</button>
        </div>
      </div>
    </div>

    <!-- 班级详情弹窗（设计文档 §2.5.3） -->
    <div class="modal-overlay" v-if="showDetailModal" @click.self="showDetailModal = false">
      <div class="modal-content detail-modal">
        <h3>{{ detailClass.class_name }} — 班级详情</h3>
        
        <!-- 班级信息栏 -->
        <div class="detail-info-row">
          <span>👥 学生数：{{ detailClass.student_count }}</span>
          <span>📊 平均分：{{ detailClass.avg_score || '--' }}</span>
          <span>📅 创建于：{{ formatDate(detailClass.create_time) }}</span>
        </div>

        <!-- 添加学生 -->
        <div class="add-student-bar">
          <input class="form-input" v-model="addStudentKeyword" placeholder="输入学号或姓名搜索学生..." @keyup.enter="searchStudents" style="width:300px" />
          <button class="btn-sm btn-primary" @click="searchStudents">搜索</button>
          <button class="btn-sm" @click="showAddStudentList = !showAddStudentList">{{ showAddStudentList ? '收起' : '添加学生' }}</button>
        </div>

        <!-- 搜索结果列表 -->
        <div v-if="showAddStudentList" class="add-student-results">
          <div v-if="searchResults.length === 0" class="empty-hint">未找到匹配学生</div>
          <div v-for="s in searchResults" :key="s.user_id" class="search-result-item">
            <span>{{ s.username }} ({{ s.user_no || '无学号' }})</span>
            <button class="btn-sm" @click="addStudentToClass(s.user_id)">添加到班级</button>
          </div>
        </div>

        <!-- 学生列表 -->
        <div class="table-wrap" style="margin-top:16px">
          <table class="data-table">
            <thead>
              <tr><th>学号</th><th>姓名</th><th>学习进度</th><th>平均正确率</th><th>操作</th></tr>
            </thead>
            <tbody>
              <tr v-for="s in detailClass.students" :key="s.user_id">
                <td>{{ s.user_no || '-' }}</td>
                <td>{{ s.username }}</td>
                <td>
                  <div class="progress-bar"><div class="progress-fill" :style="{ width: (s.progress || 0) + '%' }"></div></div>
                  <span class="progress-text">{{ s.progress || 0 }}%</span>
                </td>
                <td :class="s.avg_accuracy >= 60 ? 'accuracy-good' : 'accuracy-bad'">{{ s.avg_accuracy || '--' }}%</td>
                <td>
                  <button class="btn-sm btn-danger" @click="removeStudent(s.user_id)">移除</button>
                </td>
              </tr>
              <tr v-if="detailClass.students.length === 0">
                <td colspan="5" class="empty-hint">暂无学生，点击上方「添加学生」开始</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="modal-footer">
          <button class="btn-close" @click="showDetailModal = false">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import TeacherNavHeader from './TeacherNavHeader.vue';

export default defineComponent({
  name: 'TeacherClasses',
  components: { TeacherNavHeader },
  setup() {
    const router = useRouter();
    const classes: any = ref([]);
    const showCreateModal = ref(false);
    const showDetailModal = ref(false);
    const newClassName = ref('');
    const creating = ref(false);
    const detailClass: any = ref({ class_name: '', student_count: 0, avg_score: 0, students: [], create_time: '' });
    const addStudentKeyword = ref('');
    const showAddStudentList = ref(false);
    const searchResults: any = ref([]);

    onMounted(async () => { await loadClasses(); });

    async function loadClasses() {
      const auth = (window as any).__VTJ_AUTH__;
      if (!auth) return;
      try {
        const res = await auth.apiFetch('/api/teacher/classes');
        const data = await res.json();
        if (data.success) classes.value = data.items || [];
      } catch (e) { console.error('加载班级失败:', e); }
    }

    async function createClass() {
      if (!newClassName.value.trim()) { ElMessage.warning('请输入班级名称'); return; }
      creating.value = true;
      const auth = (window as any).__VTJ_AUTH__;
      try {
        const res = await auth.apiFetch('/api/teacher/classes', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ class_name: newClassName.value }),
        });
        const data = await res.json();
        if (data.success) {
          ElMessage.success('班级创建成功');
          showCreateModal.value = false;
          newClassName.value = '';
          await loadClasses();
        } else { ElMessage.error(data.detail || '创建失败'); }
      } catch (e) { ElMessage.error('创建失败'); }
      finally { creating.value = false; }
    }

    async function deleteClass(id: number) {
      if (!confirm('确定删除此班级？')) return;
      const auth = (window as any).__VTJ_AUTH__;
      try {
        await auth.apiFetch(`/api/teacher/classes/${id}`, { method: 'DELETE' });
        ElMessage.success('班级已删除');
        await loadClasses();
      } catch (e) { ElMessage.error('删除失败'); }
    }

    async function openDetail(cls: any) {
      const auth = (window as any).__VTJ_AUTH__;
      try {
        const res = await auth.apiFetch(`/api/teacher/classes/${cls.class_id}`);
        const data = await res.json();
        if (data.success) {
          detailClass.value = data;
          showDetailModal.value = true;
        }
      } catch (e) { ElMessage.error('加载详情失败'); }
    }

    async function searchStudents() {
      if (!addStudentKeyword.value.trim()) { ElMessage.warning('请输入学号或姓名'); return; }
      const auth = (window as any).__VTJ_AUTH__;
      try {
        const res = await auth.apiFetch(`/api/teacher/classes/search-student?keyword=${encodeURIComponent(addStudentKeyword.value)}`);
        const data = await res.json();
        if (data.success) { searchResults.value = data.items || []; showAddStudentList.value = true; }
      } catch (e) { ElMessage.error('搜索失败'); }
    }

    async function addStudentToClass(userId: number) {
      if (!detailClass.value.class_id) return;
      const auth = (window as any).__VTJ_AUTH__;
      try {
        const res = await auth.apiFetch(`/api/teacher/classes/${detailClass.value.class_id}/students`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: userId }),
        });
        const data = await res.json();
        if (data.success) {
          ElMessage.success('学生已添加');
          await openDetail({ class_id: detailClass.value.class_id });
          searchResults.value = [];
          showAddStudentList.value = false;
          addStudentKeyword.value = '';
        } else { ElMessage.error(data.detail || '添加失败'); }
      } catch (e) { ElMessage.error('添加失败'); }
    }

    async function removeStudent(userId: number) {
      if (!detailClass.value.class_id || !confirm('确定将该学生从班级中移除？')) return;
      const auth = (window as any).__VTJ_AUTH__;
      try {
        await auth.apiFetch(`/api/teacher/classes/${detailClass.value.class_id}/students/${userId}`, { method: 'DELETE' });
        ElMessage.success('学生已移除');
        await openDetail({ class_id: detailClass.value.class_id });
        await loadClasses();
      } catch (e) { ElMessage.error('移除失败'); }
    }

    function formatDate(t: string) { return t ? t.substring(0, 10) : '-'; }
    function handleLogout() { const auth = (window as any).__VTJ_AUTH__; if (auth) auth.logout(); router.push('/login'); }

    return { classes, showCreateModal, showDetailModal, newClassName, creating, detailClass, addStudentKeyword, showAddStudentList, searchResults, createClass, deleteClass, openDetail, searchStudents, addStudentToClass, removeStudent, formatDate, handleLogout };
  }
});
</script>

<style scoped>
.teacher-classes { min-height: 100vh; background: #F5F7FA; font-size: 15px; }
.page-content { max-width: 1200px; margin: 0 auto; padding: 24px; }
.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 20px; }
.toolbar-spacer { flex: 1; }
.btn-primary { padding: 10px 22px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.btn-sm { padding: 5px 12px; border: 1px solid #d9d9d9; background: #fff; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-sm:hover { background: #f0f0f0; }
.btn-sm.btn-primary { background: #1A3C6D; color: #fff; border-color: #1A3C6D; }
.btn-sm.btn-danger { color: #C41E3A; border-color: #f5c6cb; }
.class-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
.class-card { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.card-header h3 { color: #1A3C6D; margin: 0; font-size: 18px; }
.card-stats { display: flex; gap: 24px; margin-bottom: 16px; }
.stat-item { text-align: center; }
.stat-value { font-size: 28px; font-weight: 700; color: #1A3C6D; }
.stat-label { font-size: 13px; color: #888; }
.card-footer { display: flex; justify-content: space-between; align-items: center; padding-top: 12px; border-top: 1px solid #f0f0f0; }
.create-time { font-size: 12px; color: #aaa; }
.empty-state { text-align: center; padding: 60px 0; }
.empty-icon { font-size: 48px; margin-bottom: 12px; }
.empty-text { color: #999; font-size: 16px; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: #fff; border-radius: 12px; padding: 28px; max-width: 500px; width: 90%; max-height: 85vh; overflow-y: auto; }
.modal-content h3 { color: #1A3C6D; margin: 0 0 20px; }
.detail-modal { max-width: 800px; }
.detail-stats { display: flex; gap: 24px; margin-bottom: 16px; color: #666; }
.detail-info-row { display: flex; gap: 24px; margin-bottom: 16px; color: #666; font-size: 14px; padding: 12px 16px; background: #f5f7fa; border-radius: 8px; }
.add-student-bar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.add-student-results { border: 1px solid #e8e8e8; border-radius: 8px; padding: 12px; margin-bottom: 12px; max-height: 200px; overflow-y: auto; }
.search-result-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.search-result-item:last-child { border-bottom: none; }
.progress-bar { display: inline-block; width: 80px; height: 6px; background: #f0f0f0; border-radius: 3px; overflow: hidden; vertical-align: middle; }
.progress-fill { height: 100%; background: #409EFF; border-radius: 3px; transition: width 0.3s; }
.progress-text { font-size: 12px; color: #666; margin-left: 6px; }
.accuracy-good { color: #67C23A; font-weight: 600; }
.accuracy-bad { color: #F56C6C; font-weight: 600; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; margin-bottom: 6px; font-weight: 600; color: #1A3C6D; font-size: 14px; }
.form-input { width: 100%; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; box-sizing: border-box; }
.modal-footer { display: flex; gap: 12px; justify-content: flex-end; margin-top: 20px; }
.btn-save { padding: 10px 28px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.btn-save:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-close { padding: 10px 28px; background: #f0f0f0; color: #666; border: none; border-radius: 6px; cursor: pointer; font-size: 15px; }
.table-wrap { background: #fff; border-radius: 10px; overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { padding: 12px 14px; background: #fafafa; text-align: left; font-weight: 600; color: #1A3C6D; border-bottom: 2px solid #e8e8e8; font-size: 14px; }
.data-table td { padding: 12px 14px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.empty-hint { text-align: center; color: #999; padding: 20px; }
</style>
