<template>
  <div class="admin-content">
    <div v-if="loading" class="skeleton-wrap"><div class="sk-bar"></div><div class="sk-table"></div></div>
    <div v-else>
      <div class="action-bar">
        <h2 class="page-title">🔐 权限管理</h2>
        <div v-if="isSuperAdmin" class="action-buttons">
          <button class="btn-secondary" @click="cancelEdit" v-if="editingRole">取消编辑</button>
          <button class="btn-primary" @click="saveEdit" v-if="editingRole">保存修改</button>
        </div>
      </div>
      <div v-if="isSuperAdmin && !editingRole" class="edit-tip">
        💡 超级管理员可点击下方「编辑权限」调整各角色权限
      </div>
      <div class="roles-grid">
        <div v-for="(perms, role) in roles" :key="role" class="role-card">
          <div class="role-header">
            <span class="role-icon">{{ {student:'👨‍🎓',teacher:'👨‍🏫',admin:'🛡️'}[role] }}</span>
            <h3>{{ perms.role_name || {student:'学生',teacher:'教师',admin:'管理员'}[role] }}</h3>
            <button v-if="isSuperAdmin && editingRole !== role" class="btn-edit" @click="startEdit(role)">编辑权限</button>
          </div>
          <p class="role-desc">{{ perms.description }}</p>
          <!-- 编辑模式：勾选权限 -->
          <div v-if="editingRole === role" class="perm-edit-grid">
            <label v-for="(name, code) in allPermissionNames" :key="code" class="perm-checkbox">
              <input type="checkbox" :value="code" v-model="editPermissions" />
              <span>{{ name }}</span>
            </label>
          </div>
          <!-- 展示模式：标签 -->
          <div v-else class="perm-grid">
            <span v-for="p in perms.permissions" :key="p" class="perm-tag">{{ getPermissionName(p) }}</span>
          </div>
        </div>
      </div>
      <div v-if="!Object.keys(roles).length" class="empty-state"><div class="empty-icon">🔐</div><div>暂无权限配置</div></div>
      <div class="msg" v-if="msg">{{ msg }}</div>
    </div>
  </div>
</template>
<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, onMounted } from 'vue';
import { useProvider } from '@vtj/renderer';
export default defineComponent({
  name: 'AdminPermissions', setup() {
    const provider = useProvider({ id: 'admin_permissions', version: '1' });
    const loading = ref(true);
    const roles: any = ref({});
    const allPermissionNames: any = ref({});
    const isSuperAdmin = ref(false);
    const editingRole = ref('');
    const editPermissions: any = ref([]);
    const msg = ref('');
    const auth = () => (window as any).__VTJ_AUTH__;

    // 获取权限中文名称：优先用后端返回的 permission_names 映射
    const getPermissionName = (key: string) => {
      return allPermissionNames.value[key] || key;
    };

    onMounted(async () => {
      try {
        // 判断是否超级管理员（role_level >= 3）
        const parsed = auth()?.parseUserInfo?.() || {};
        isSuperAdmin.value = (parsed.roleLevel >= 3) || (auth()?.getRoleLevel?.() >= 3);

        const r = await auth().apiFetch('/api/admin/permissions');
        const d = await r.json();
        if (d.success) {
          roles.value = d.roles || {};
          allPermissionNames.value = d.permission_names || {};
        }
      } catch(e) { console.error('加载权限失败:', e); }
      loading.value = false;
    });

    function startEdit(role: string) {
      editingRole.value = role;
      editPermissions.value = [...(roles.value[role].permissions || [])];
    }

    function cancelEdit() {
      editingRole.value = '';
      editPermissions.value = [];
    }

    async function saveEdit() {
      try {
        const r = await auth().apiFetch('/api/admin/permissions', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ role: editingRole.value, permissions: editPermissions.value })
        });
        const d = await r.json();
        if (d.success) {
          msg.value = '✅ 权限已更新';
          // 重新加载
          const rr = await auth().apiFetch('/api/admin/permissions');
          const dd = await rr.json();
          if (dd.success) {
            roles.value = dd.roles || {};
            allPermissionNames.value = dd.permission_names || {};
          }
          editingRole.value = '';
          editPermissions.value = [];
        } else {
          msg.value = '❌ ' + (d.message || '更新失败');
        }
        setTimeout(() => msg.value = '', 3000);
      } catch(e) {
        msg.value = '❌ 更新失败';
        setTimeout(() => msg.value = '', 3000);
      }
    }

    return { provider, loading, roles, allPermissionNames, isSuperAdmin, editingRole, editPermissions, msg, getPermissionName, startEdit, cancelEdit, saveEdit };
  }
});
</script>
<style scoped>
.admin-content{padding:20px;max-width:1100px}.skeleton-wrap{display:flex;flex-direction:column;gap:20px}.sk-bar,.sk-table{background:linear-gradient(90deg,#f0f0f0 25%,#e0e0e0 50%,#f0f0f0 75%);background-size:200% 100%;animation:sk 1.5s infinite;border-radius:10px}.sk-bar{height:60px}.sk-table{height:400px}@keyframes sk{0%{background-position:200% 0}100%{background-position:-200% 0}}
.action-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.page-title{margin:0;color:#1A3C6D}.action-buttons{display:flex;gap:10px}
.edit-tip{padding:10px 16px;background:#e6f7ff;border:1px solid #91d5ff;border-radius:8px;color:#1890ff;font-size:13px;margin-bottom:16px}
.roles-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px}
.role-card{background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.role-header{display:flex;align-items:center;gap:12px;margin-bottom:12px}.role-icon{font-size:32px}.role-header h3{margin:0;color:#1A3C6D;flex:1}
.role-desc{font-size:13px;color:#888;margin-bottom:16px}
.perm-grid{display:flex;flex-wrap:wrap;gap:8px}.perm-tag{padding:4px 12px;background:#F5F7FA;border:1px solid #e0e0e0;border-radius:20px;font-size:13px;color:#555}
.perm-edit-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:8px}
.perm-checkbox{display:flex;align-items:center;gap:6px;font-size:13px;color:#333;cursor:pointer;padding:6px 8px;background:#F5F7FA;border-radius:6px}
.perm-checkbox input{accent-color:#1A3C6D}
.btn-edit{padding:4px 12px;border:1px solid #1A3C6D;border-radius:6px;background:transparent;color:#1A3C6D;cursor:pointer;font-size:13px}
.btn-edit:hover{background:#1A3C6D;color:#fff}
.btn-primary{padding:8px 16px;background:#C41E3A;color:#fff;border:none;border-radius:6px;cursor:pointer}
.btn-secondary{padding:8px 16px;background:#fff;color:#333;border:1px solid #d9d9d9;border-radius:6px;cursor:pointer}
.empty-state{text-align:center;padding:60px 20px;color:#999}.empty-icon{font-size:48px;margin-bottom:16px}
.msg{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);padding:12px 24px;background:#f0f9eb;color:#67C23A;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);z-index:2000}
</style>
