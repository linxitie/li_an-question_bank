<template>
  <div class="admin-content">
    <div v-if="loading" class="skeleton-wrap">
      <div class="sk-bar"></div>
      <div class="sk-table"></div>
    </div>
    <div v-else>
      <div class="action-bar">
        <h2 class="page-title">👥 用户管理</h2>
        <div class="action-buttons">
          <button class="btn-primary" @click="showAddDialog">➕ 新增用户</button>
          <button class="btn-refresh" @click="load">🔄 刷新</button>
        </div>
      </div>
      
      <!-- 筛选区 -->
      <div class="filter-bar">
        <select class="filter-select" v-model="filters.user_type" @change="load">
          <option value="">全部角色</option>
          <option value="student">学生</option>
          <option value="teacher">教师</option>
          <option value="admin">管理员</option>
        </select>
        <select class="filter-select" v-model="filters.is_disabled" @change="load">
          <option value="">全部状态</option>
          <option value="0">正常</option>
          <option value="1">禁用</option>
        </select>
        <input class="filter-input" v-model="filters.keyword" placeholder="搜索用户名/手机号" @keyup.enter="load"/>
        <button class="btn-search" @click="load">🔍 查询</button>
        <button class="btn-reset" @click="resetFilter">🔄 重置</button>
      </div>

      <!-- 用户列表 -->
      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>头像</th>
              <th>用户名</th>
              <th>角色</th>
              <th>手机号</th>
              <th>部门</th>
              <th>状态</th>
              <th>注册时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in userList" :key="user.user_id">
              <td>{{ user.user_id }}</td>
              <td>
                <div class="avatar-small" :style="{backgroundImage: user.avatar ? `url(${user.avatar})` : 'none'}">
                  {{ !user.avatar ? user.username?.charAt(0)?.toUpperCase() : '' }}
                </div>
              </td>
              <td>{{ user.username }}</td>
              <td>
                <span class="role-tag" :class="'role-' + user.user_type">
                  {{ {student:'学生',teacher:'教师',admin:'管理员'}[user.user_type] || user.user_type }}
                </span>
              </td>
              <td>{{ user.phone }}</td>
              <td>{{ user.department || '-' }}</td>
              <td>
                <span class="status-badge" :class="user.is_disabled ? 'status-disabled' : 'status-normal'">
                  {{ user.is_disabled ? '禁用' : '正常' }}
                </span>
              </td>
              <td>{{ formatTime(user.register_time) }}</td>
              <td class="actions">
                <button class="btn-icon" @click="editUser(user)" title="编辑">✏️</button>
                <button v-if="!user.is_disabled" class="btn-icon btn-warning" @click="disableUser(user)" title="禁用">🚫</button>
                <button v-else class="btn-icon btn-success" @click="enableUser(user)" title="启用">✅</button>
                <button class="btn-icon" @click="resetPassword(user)" title="重置密码">🔑</button>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!userList.length" class="empty-state">
          <div class="empty-icon">👥</div>
          <div>暂无用户数据</div>
        </div>
      </div>

      <!-- 分页 -->
      <div class="pagination" v-if="total > 0">
        <button class="btn-page" :disabled="currentPage <= 1" @click="changePage(currentPage - 1)">上一页</button>
        <span class="page-info">第 {{ currentPage }} / {{ totalPages }} 页，共 {{ total }} 条</span>
        <button class="btn-page" :disabled="currentPage >= totalPages" @click="changePage(currentPage + 1)">下一页</button>
      </div>
    </div>

    <!-- 编辑用户弹窗 -->
    <div class="modal-overlay" v-if="showEditModal" @click.self="showEditModal = false">
      <div class="modal-content modal-large">
        <h3>编辑用户信息</h3>
        <div class="form-grid">
          <div class="fg">
            <label>用户编号</label>
            <input class="fi" v-model="editForm.user_no" disabled />
          </div>
          <div class="fg">
            <label>用户名</label>
            <input class="fi" v-model="editForm.username" disabled />
          </div>
          <div class="fg">
            <label>手机号</label>
            <input class="fi" v-model="editForm.phone" placeholder="请输入手机号"/>
          </div>
          <div class="fg">
            <label>邮箱</label>
            <input class="fi" v-model="editForm.email" placeholder="请输入邮箱"/>
          </div>
          <div class="fg">
            <label>用户类型</label>
            <select class="fi" v-model="editForm.user_type">
              <option value="student">学生</option>
              <option value="teacher">教师</option>
              <option value="admin">管理员</option>
            </select>
          </div>
          <div class="fg">
            <label>部门</label>
            <input class="fi" v-model="editForm.department" placeholder="请输入部门"/>
          </div>
          <div class="fg">
            <label>班级</label>
            <input class="fi" v-model="editForm.class_name" placeholder="请输入班级"/>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showEditModal = false">取消</button>
          <button class="btn-primary" @click="submitEdit">保存修改</button>
        </div>
      </div>
    </div>

    <!-- 新增用户弹窗 -->
    <div class="modal-overlay" v-if="showAddModal" @click.self="showAddModal = false">
      <div class="modal-content modal-large">
        <h3>新增用户</h3>
        <div class="form-grid">
          <div class="fg">
            <label>用户编号 <span class="required">*</span></label>
            <input class="fi" v-model="addForm.user_no" placeholder="请输入用户编号"/>
          </div>
          <div class="fg">
            <label>用户名 <span class="required">*</span></label>
            <input class="fi" v-model="addForm.username" placeholder="请输入用户名"/>
          </div>
          <div class="fg">
            <label>密码 <span class="required">*</span></label>
            <input class="fi" type="password" v-model="addForm.password" placeholder="请输入密码"/>
          </div>
          <div class="fg">
            <label>手机号 <span class="required">*</span></label>
            <input class="fi" v-model="addForm.phone" placeholder="请输入手机号"/>
          </div>
          <div class="fg">
            <label>用户类型</label>
            <select class="fi" v-model="addForm.user_type">
              <option value="student">学生</option>
              <option value="teacher">教师</option>
              <option value="admin">管理员</option>
            </select>
          </div>
          <div class="fg">
            <label>部门</label>
            <input class="fi" v-model="addForm.department" placeholder="请输入部门"/>
          </div>
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showAddModal = false">取消</button>
          <button class="btn-primary" @click="submitAdd">确认创建</button>
        </div>
      </div>
    </div>

    <div class="msg" v-if="msg">{{ msg }}</div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, reactive, onMounted } from 'vue';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'AdminUsers',
  setup() {
    const provider = useProvider({ id: 'admin_users', version: '1' });
    const loading = ref(true);
    const userList = ref<any[]>([]);
    const total = ref(0);
    const currentPage = ref(1);
    const pageSize = ref(20);
    const msg = ref('');
    const showEditModal = ref(false);
    const showAddModal = ref(false);

    const filters = reactive({
      user_type: '',
      is_disabled: '',
      keyword: ''
    });

    const editForm = ref({
      user_id: null,
      user_no: '',
      username: '',
      phone: '',
      email: '',
      user_type: 'student',
      department: '',
      class_name: ''
    });

    const addForm = ref({
      user_no: '',
      username: '',
      password: '',
      phone: '',
      user_type: 'student',
      department: ''
    });

    const auth = () => (window as any).__VTJ_AUTH__;
    const totalPages = ref(1);

    onMounted(load);

    async function load() {
      loading.value = true;
      try {
        const params = new URLSearchParams({
          page: currentPage.value.toString(),
          page_size: pageSize.value.toString()
        });
        if (filters.user_type) params.append('user_type', filters.user_type);
        if (filters.is_disabled !== '') params.append('is_disabled', filters.is_disabled);
        if (filters.keyword) params.append('keyword', filters.keyword);

        const r = await auth().apiFetch('/api/admin/users?' + params.toString());
        const d = await r.json();
        if (d.success) {
          userList.value = d.items || [];
          total.value = d.total || 0;
          totalPages.value = Math.ceil(total.value / pageSize.value);
        }
      } catch (e) {
        console.error('加载用户列表失败:', e);
      }
      loading.value = false;
    }

    function resetFilter() {
      filters.user_type = '';
      filters.is_disabled = '';
      filters.keyword = '';
      currentPage.value = 1;
      load();
    }

    function changePage(page: number) {
      currentPage.value = page;
      load();
    }

    function showAddDialog() {
      addForm.value = {
        user_no: '',
        username: '',
        password: '',
        phone: '',
        user_type: 'student',
        department: ''
      };
      showAddModal.value = true;
    }

    async function editUser(user: any) {
      try {
        const r = await auth().apiFetch('/api/admin/users/' + user.user_id);
        const d = await r.json();
        if (d.success && d.user) {
          editForm.value = {
            user_id: d.user.user_id,
            user_no: d.user.user_no,
            username: d.user.username,
            phone: d.user.phone || '',
            email: d.user.email || '',
            user_type: d.user.user_type,
            department: d.user.department || '',
            class_name: d.user.class_name || ''
          };
          showEditModal.value = true;
        }
      } catch (e) {
        msg.value = '获取用户信息失败';
        setTimeout(() => msg.value = '', 3000);
      }
    }

    async function submitEdit() {
      try {
        const r = await auth().apiFetch('/api/admin/users/' + editForm.value.user_id, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(editForm.value)
        });
        const d = await r.json();
        if (d.success) {
          msg.value = '✅ 用户信息已更新';
          showEditModal.value = false;
          load();
        } else {
          msg.value = '❌ ' + (d.message || '更新失败');
        }
        setTimeout(() => msg.value = '', 3000);
      } catch (e) {
        msg.value = '❌ 更新失败';
        setTimeout(() => msg.value = '', 3000);
      }
    }

    async function submitAdd() {
      if (!addForm.value.user_no || !addForm.value.username || !addForm.value.password || !addForm.value.phone) {
        msg.value = '❌ 请填写必填项';
        setTimeout(() => msg.value = '', 3000);
        return;
      }
      try {
        const r = await auth().apiFetch('/api/admin/users', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(addForm.value)
        });
        const d = await r.json();
        if (d.success) {
          msg.value = '✅ 用户创建成功';
          showAddModal.value = false;
          load();
        } else {
          msg.value = '❌ ' + (d.message || '创建失败');
        }
        setTimeout(() => msg.value = '', 3000);
      } catch (e) {
        msg.value = '❌ 创建失败';
        setTimeout(() => msg.value = '', 3000);
      }
    }

    async function disableUser(user: any) {
      if (!confirm('确定要禁用用户 ' + user.username + ' 吗？')) return;
      try {
        const r = await auth().apiFetch('/api/admin/users/' + user.user_id + '/disable', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_disabled: 1, reason: '管理员操作禁用' })
        });
        const d = await r.json();
        if (d.success) {
          msg.value = '✅ 用户已禁用';
          load();
        }
        setTimeout(() => msg.value = '', 3000);
      } catch (e) {
        msg.value = '❌ 操作失败';
        setTimeout(() => msg.value = '', 3000);
      }
    }

    async function enableUser(user: any) {
      try {
        const r = await auth().apiFetch('/api/admin/users/' + user.user_id + '/disable', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ is_disabled: 0, reason: '' })
        });
        const d = await r.json();
        if (d.success) {
          msg.value = '✅ 用户已启用';
          load();
        }
        setTimeout(() => msg.value = '', 3000);
      } catch (e) {
        msg.value = '❌ 操作失败';
        setTimeout(() => msg.value = '', 3000);
      }
    }

    async function resetPassword(user: any) {
      if (!confirm('确定要重置用户 ' + user.username + ' 的密码吗？')) return;
      try {
        const r = await auth().apiFetch('/api/admin/users/' + user.user_id + '/reset-password', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        });
        const d = await r.json();
        if (d.success) {
          msg.value = '✅ 密码已重置为: ' + d.new_password;
        }
        setTimeout(() => msg.value = '', 5000);
      } catch (e) {
        msg.value = '❌ 重置失败';
        setTimeout(() => msg.value = '', 3000);
      }
    }

    function formatTime(t: string) {
      if (!t) return '-';
      return t.replace('T', ' ').substring(0, 19);
    }

    return {
      provider, loading, userList, total, currentPage, pageSize, totalPages,
      filters, msg, showEditModal, showAddModal, editForm, addForm,
      load, resetFilter, changePage, showAddDialog, editUser,
      submitEdit, submitAdd, disableUser, enableUser, resetPassword, formatTime
    };
  }
});
</script>

<style scoped>
.admin-content { padding: 20px; }
.skeleton-wrap { display: flex; flex-direction: column; gap: 20px; }
.sk-bar, .sk-table {
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: sk 1.5s infinite;
  border-radius: 10px;
}
.sk-bar { height: 60px; }
.sk-table { height: 400px; }
@keyframes sk { 0% { background-position: 200% 0 } 100% { background-position: -200% 0 } }

.action-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-title { margin: 0; color: #1A3C6D; }
.action-buttons { display: flex; gap: 10px; }

.filter-bar { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
.filter-input { flex: 1; min-width: 150px; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; }
.filter-select { padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; }

.table-container { background: #fff; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.06); overflow: hidden; }
.data-table { width: 100%; border-collapse: collapse; }
.data-table th { padding: 12px 16px; background: #fafafa; text-align: left; font-weight: 600; color: #1A3C6D; border-bottom: 2px solid #e8e8e8; font-size: 14px; }
.data-table td { padding: 12px 16px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.data-table tr:hover { background: #f5f7fa; }

.avatar-small {
  width: 36px; height: 36px; border-radius: 50%;
  background: #409eff; color: #fff; font-size: 14px; font-weight: bold;
  display: flex; align-items: center; justify-content: center;
  background-size: cover; background-position: center;
}

.role-tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.role-student { background: #f0f9eb; color: #67C23A; }
.role-teacher { background: #ecf5ff; color: #409eff; }
.role-admin { background: #fef0f0; color: #f56c6c; }

.status-badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; }
.status-normal { background: #f6ffed; color: #52c41a; }
.status-disabled { background: #fff2f0; color: #ff4d4f; }

.actions { display: flex; gap: 4px; }
.btn-icon { width: 28px; height: 28px; border: none; background: transparent; cursor: pointer; border-radius: 4px; font-size: 14px; }
.btn-icon:hover { background: #f0f0f0; }
.btn-warning:hover { background: #fff7e6; }
.btn-success:hover { background: #f6ffed; }

.empty-state { text-align: center; padding: 60px 20px; color: #999; }
.empty-icon { font-size: 48px; margin-bottom: 16px; }

.pagination { display: flex; justify-content: center; align-items: center; gap: 16px; margin-top: 20px; padding: 16px; }
.page-info { color: #666; font-size: 14px; }

.btn-primary { padding: 8px 16px; background: #C41E3A; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.btn-primary:hover { background: #a01830; }
.btn-secondary { padding: 8px 16px; background: #fff; color: #333; border: 1px solid #d9d9d9; border-radius: 6px; cursor: pointer; }
.btn-refresh { padding: 8px 16px; background: #fff; color: #666; border: 1px solid #d9d9d9; border-radius: 6px; cursor: pointer; }
.btn-search { padding: 8px 16px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.btn-reset { padding: 8px 16px; background: #fff; color: #666; border: 1px solid #d9d9d9; border-radius: 6px; cursor: pointer; }
.btn-page { padding: 6px 12px; background: #fff; color: #333; border: 1px solid #d9d9d9; border-radius: 4px; cursor: pointer; }
.btn-page:disabled { opacity: 0.5; cursor: not-allowed; }

.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-content { background: #fff; border-radius: 12px; padding: 24px; min-width: 400px; max-width: 90vw; }
.modal-large { min-width: 600px; }
.modal-content h3 { margin: 0 0 20px; color: #1A3C6D; }
.modal-actions { display: flex; justify-content: flex-end; gap: 12px; margin-top: 20px; }

.form-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
.fg { margin-bottom: 12px; }
.fg label { display: block; margin-bottom: 6px; font-weight: 500; color: #333; }
.fg .required { color: #f56c6c; }
.fi { width: 100%; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 14px; box-sizing: border-box; }
.fi:disabled { background: #f5f5f5; color: #999; }

.msg { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); padding: 12px 24px; background: #f0f9eb; color: #67C23A; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 2000; }
</style>