<template>
  <div class="admin-content">
    <!-- 骨架屏加载 -->
    <div v-if="loading" class="skeleton-container">
      <div class="skeleton-toolbar"></div>
      <div class="skeleton-table"></div>
    </div>
    
    <!-- 主内容 -->
    <div v-else class="content-wrapper">
      <!-- 顶部操作栏 -->
      <div class="action-bar">
        <h2 class="page-title">👤 用户管理</h2>
        <div class="action-buttons">
          <button class="btn-primary" @click="showCreate=true">+ 新增用户</button>
          <button class="btn-secondary" @click="batchImport">📥 批量导入</button>
          <button class="btn-secondary" @click="exportUsers">📤 导出</button>
        </div>
      </div>
      
      <!-- 筛选区 -->
      <div class="filter-bar">
        <input class="filter-input" v-model="keyword" placeholder="搜索姓名/学号" @keyup.enter="search" />
        <select class="filter-select" v-model="filterType" @change="search">
          <option value="">全部角色</option>
          <option value="student">学生</option>
          <option value="teacher">教师</option>
          <option value="admin">管理员</option>
        </select>
        <select class="filter-select" v-model="filterStatus" @change="search">
          <option value="">全部状态</option>
          <option value="normal">正常</option>
          <option value="disabled">已禁用</option>
        </select>
        <button class="btn-search" @click="search">🔍 搜索</button>
        <button class="btn-reset" @click="resetFilter">🔄 重置</button>
      </div>
      
      <!-- 批量操作栏 -->
      <div class="batch-bar" v-if="selectedUsers.length > 0">
        <span>已选择 {{ selectedUsers.length }} 项</span>
        <button class="btn-batch" @click="batchEnable">批量启用</button>
        <button class="btn-batch-danger" @click="batchDisable">批量禁用</button>
        <button class="btn-batch-danger" @click="batchDelete">批量删除</button>
      </div>
      
      <!-- 用户表格 -->
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th><input type="checkbox" @change="toggleAll" :checked="isAllSelected" /></th>
              <th>ID</th>
              <th>头像</th>
              <th>学号</th>
              <th>姓名</th>
              <th>角色</th>
              <th>班级</th>
              <th>状态</th>
              <th>最后登录</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.user_id" :class="{ 'selected': selectedUsers.includes(u.user_id) }">
              <td><input type="checkbox" :value="u.user_id" v-model="selectedUsers" /></td>
              <td>{{ u.user_id }}</td>
              <td><div class="avatar">{{ u.username.charAt(0) }}</div></td>
              <td>{{ u.user_no }}</td>
              <td>{{ u.username }}</td>
              <td><span class="tag" :class="'tag-' + u.user_type">{{ {student:'学生',teacher:'教师',admin:'管理员'}[u.user_type] }}</span></td>
              <td>{{ u.class_name || '-' }}</td>
              <td><span class="status-badge" :class="u.is_disabled ? 'status-disabled' : 'status-normal'">{{ u.is_disabled ? '已禁用' : '正常' }}</span></td>
              <td>{{ u.last_login || '-' }}</td>
              <td class="actions">
                <button class="btn-icon" @click="viewUser(u)" title="查看详情">👁️</button>
                <button class="btn-icon" @click="editUser(u)" title="编辑">✏️</button>
                <button class="btn-icon" :class="u.is_disabled ? 'btn-success' : 'btn-danger'" @click="toggleDisable(u)" :title="u.is_disabled ? '启用' : '禁用'">{{ u.is_disabled ? '✅' : '🚫' }}</button>
                <button class="btn-icon" @click="resetPwd(u.user_id)" v-if="userLevel>=3" title="重置密码">🔑</button>
              </td>
            </tr>
          </tbody>
        </table>
        
        <!-- 空状态 -->
        <div v-if="users.length === 0" class="empty-state">
          <div class="empty-icon">👤</div>
          <div class="empty-text">暂无用户数据</div>
          <button class="btn-primary" @click="showCreate=true">+ 新增用户</button>
        </div>
      </div>
      
      <!-- 分页 -->
      <div class="pagination">
        <span>共 {{ total }} 条</span>
        <button :disabled="currentPage <= 1" @click="changePage(currentPage - 1)">上一页</button>
        <span>{{ currentPage }} / {{ totalPages }}</span>
        <button :disabled="currentPage >= totalPages" @click="changePage(currentPage + 1)">下一页</button>
      </div>
    </div>
    
    <!-- 新增用户弹窗 -->
    <div class="modal" v-if="showCreate" @click.self="showCreate=false">
      <div class="modal-box">
        <h3>新增用户</h3>
        <div class="form-group">
          <label>用户名 *</label>
          <input class="form-input" v-model="form.username" placeholder="请输入用户名" />
        </div>
        <div class="form-group">
          <label>学号 *</label>
          <input class="form-input" v-model="form.user_no" placeholder="请输入学号" />
        </div>
        <div class="form-group">
          <label>密码 *</label>
          <input class="form-input" type="password" v-model="form.password" placeholder="请输入密码" />
        </div>
        <div class="form-group">
          <label>角色 *</label>
          <select class="form-input" v-model="form.user_type">
            <option value="student">学生</option>
            <option value="teacher">教师</option>
          </select>
        </div>
        <div class="form-group">
          <label>班级</label>
          <input class="form-input" v-model="form.class_name" placeholder="请输入班级" />
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showCreate=false">取消</button>
          <button class="btn-primary" @click="doCreate">确认创建</button>
        </div>
      </div>
    </div>
    
    <!-- 用户详情弹窗 -->
    <div class="modal" v-if="showDetail" @click.self="showDetail=false">
      <div class="modal-box modal-lg">
        <h3>用户详情 - {{ currentUser.username }}</h3>
        <div class="detail-grid">
          <div class="detail-item">
            <label>用户名</label>
            <span>{{ currentUser.user_no }}</span>
          </div>
          <div class="detail-item">
            <label>姓名</label>
            <span>{{ currentUser.username }}</span>
          </div>
          <div class="detail-item">
            <label>角色</label>
            <span>{{ {student:'学生',teacher:'教师',admin:'管理员'}[currentUser.user_type] }}</span>
          </div>
          <div class="detail-item">
            <label>班级</label>
            <span>{{ currentUser.class_name || '-' }}</span>
          </div>
          <div class="detail-item">
            <label>状态</label>
            <span :class="currentUser.is_disabled ? 'status-disabled' : 'status-normal'">{{ currentUser.is_disabled ? '已禁用' : '正常' }}</span>
          </div>
          <div class="detail-item">
            <label>最后登录</label>
            <span>{{ currentUser.last_login || '-' }}</span>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showDetail=false">关闭</button>
          <button class="btn-primary" @click="editUser(currentUser)">编辑</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'AdminUsers',
  setup() {
    const provider = useProvider({ id: 'admin_users', version: '1' });
    const router = useRouter();
    const loading = ref(true);
    const keyword = ref('');
    const filterType = ref('');
    const filterStatus = ref('');
    const users: any = ref([]);
    const selectedUsers: any = ref([]);
    const showCreate = ref(false);
    const showDetail = ref(false);
    const currentUser = ref({});
    const form = ref({ username: '', user_no: '', password: '', user_type: 'student', class_name: '' });
    const userLevel = ref(0);
    const currentPage = ref(1);
    const total = ref(0);
    const pageSize = ref(20);

    const auth = () => (window as any).__VTJ_AUTH__;

    const totalPages = ref(1);
    const isAllSelected = ref(false);

    onMounted(async () => {
      if (auth()) {
        userLevel.value = auth().getRoleLevel();
      }
      await load();
    });

    async function load() {
      try {
        loading.value = true;
        const p = new URLSearchParams();
        if (keyword.value) p.append('keyword', keyword.value);
        if (filterType.value) p.append('user_type', filterType.value);
        if (filterStatus.value) p.append('status', filterStatus.value);
        p.append('page', String(currentPage.value));
        p.append('page_size', String(pageSize.value));
        
        const r = await auth().apiFetch('/api/admin/users?' + p.toString());
        const d = await r.json();
        if (d.success) {
          users.value = d.items || [];
          total.value = d.total || 0;
          totalPages.value = Math.ceil(total.value / pageSize.value) || 1;
        }
      } catch (e) {
        console.error('加载用户列表失败:', e);
      } finally {
        loading.value = false;
      }
    }

    function search() {
      currentPage.value = 1;
      load();
    }

    function resetFilter() {
      keyword.value = '';
      filterType.value = '';
      filterStatus.value = '';
      currentPage.value = 1;
      load();
    }

    function changePage(page) {
      currentPage.value = page;
      load();
    }

    function toggleAll(e) {
      if (e.target.checked) {
        selectedUsers.value = users.value.map(u => u.user_id);
      } else {
        selectedUsers.value = [];
      }
    }

    function viewUser(user) {
      currentUser.value = user;
      showDetail.value = true;
    }

    function editUser(user) {
      currentUser.value = user;
      // TODO: 打开编辑弹窗
      console.log('编辑用户:', user);
    }

    async function toggleDisable(u: any) {
      try {
        await auth().apiFetch(`/api/admin/users/${u.user_id}/disable`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_disabled: !u.is_disabled, reason: u.is_disabled ? '管理员启用' : '管理员禁用' })
        });
        load();
      } catch (e) {
        console.error('操作失败:', e);
      }
    }

    async function resetPwd(id: number) {
      if (confirm('确定重置密码？')) {
        try {
          const r = await auth().apiFetch(`/api/admin/users/${id}/reset-password`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: '{}'
          });
          const d = await r.json();
          if (d.success) alert('新密码: ' + d.new_password);
        } catch (e) {
          console.error('重置密码失败:', e);
        }
      }
    }

    async function doCreate() {
      try {
        await auth().apiFetch('/api/admin/users', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(form.value)
        });
        showCreate.value = false;
        form.value = { username: '', user_no: '', password: '', user_type: 'student', class_name: '' };
        load();
      } catch (e) {
        console.error('创建用户失败:', e);
      }
    }

    function batchImport() {
      // TODO: 批量导入功能
      console.log('批量导入');
    }

    function exportUsers() {
      // TODO: 导出功能
      console.log('导出用户');
    }

    function batchEnable() {
      // TODO: 批量启用
      console.log('批量启用:', selectedUsers.value);
    }

    function batchDisable() {
      // TODO: 批量禁用
      console.log('批量禁用:', selectedUsers.value);
    }

    async function batchDelete() {
      if (!selectedUsers.value.length) { alert('请先选择用户'); return; }
      if (!confirm(`确定删除 ${selectedUsers.value.length} 个用户？`)) return;
      const auth = (window as any).__VTJ_AUTH__;
      await auth.apiFetch('/api/admin/users/batch', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: selectedUsers.value })
      });
      selectedUsers.value = [];
      load();
    }

    return {
      provider, loading, keyword, filterType, filterStatus, users, selectedUsers,
      showCreate, showDetail, currentUser, form, userLevel, currentPage, total, totalPages,
      isAllSelected, load, search, resetFilter, changePage, toggleAll, viewUser, editUser,
      toggleDisable, resetPwd, doCreate, batchImport, exportUsers, batchEnable, batchDisable, batchDelete
    };
  }
});
</script>

<style scoped>
.admin-content {
  padding: 20px;
  min-height: calc(100vh - 60px);
}

/* 骨架屏 */
.skeleton-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.skeleton-toolbar {
  height: 60px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: 10px;
}

.skeleton-table {
  height: 400px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: skeleton-loading 1.5s infinite;
  border-radius: 10px;
}

@keyframes skeleton-loading {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 操作栏 */
.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  color: #1A3C6D;
}

.action-buttons {
  display: flex;
  gap: 10px;
}

/* 筛选栏 */
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.filter-input {
  flex: 1;
  min-width: 200px;
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
}

.filter-select {
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  min-width: 120px;
}

/* 批量操作栏 */
.batch-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #e6f7ff;
  border: 1px solid #91d5ff;
  border-radius: 6px;
  margin-bottom: 16px;
}

/* 表格容器 */
.table-container {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  overflow: hidden;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th {
  padding: 12px 16px;
  background: #fafafa;
  text-align: left;
  font-weight: 600;
  color: #1A3C6D;
  border-bottom: 2px solid #e8e8e8;
  font-size: 14px;
}

.data-table td {
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 14px;
}

.data-table tr:hover {
  background: #f5f7fa;
}

.data-table tr.selected {
  background: #e6f7ff;
}

/* 头像 */
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #1A3C6D;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 14px;
}

/* 标签 */
.tag {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.tag-student { background: #e6f7ff; color: #1890ff; }
.tag-teacher { background: #f6ffed; color: #52c41a; }
.tag-admin { background: #fff7e6; color: #fa8c16; }

/* 状态徽章 */
.status-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.status-normal { background: #f6ffed; color: #52c41a; }
.status-disabled { background: #fff2f0; color: #ff4d4f; }

/* 操作按钮 */
.actions {
  display: flex;
  gap: 4px;
}

.btn-icon {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 4px;
  font-size: 14px;
  transition: background 0.2s;
}

.btn-icon:hover {
  background: #f0f0f0;
}

.btn-success:hover { background: #f6ffed; }
.btn-danger:hover { background: #fff2f0; }

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 60px 20px;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-text {
  color: #999;
  margin-bottom: 16px;
}

/* 分页 */
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  padding: 16px;
  margin-top: 16px;
}

.pagination button {
  padding: 6px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
}

.pagination button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 弹窗 */
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-box {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  width: 480px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-box.modal-lg {
  width: 640px;
}

.modal-box h3 {
  margin: 0 0 20px;
  color: #1A3C6D;
}

/* 表单 */
.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-weight: 500;
  color: #333;
}

.form-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
}

.form-input:focus {
  border-color: #1A3C6D;
  outline: none;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}

/* 详情网格 */
.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-item label {
  font-size: 12px;
  color: #999;
}

.detail-item span {
  font-size: 14px;
  color: #333;
}

/* 按钮 */
.btn-primary {
  padding: 8px 16px;
  background: #C41E3A;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary:hover {
  background: #a01830;
}

.btn-secondary {
  padding: 8px 16px;
  background: #fff;
  color: #333;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-secondary:hover {
  border-color: #1A3C6D;
  color: #1A3C6D;
}

.btn-search {
  padding: 8px 16px;
  background: #1A3C6D;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-reset {
  padding: 8px 16px;
  background: #fff;
  color: #666;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}

.btn-batch {
  padding: 6px 12px;
  background: #1890ff;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.btn-batch-danger {
  padding: 6px 12px;
  background: #ff4d4f;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
</style>


