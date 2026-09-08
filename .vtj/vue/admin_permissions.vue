<template>
  <div class="admin-content">
    <div v-if="loading" class="skeleton-wrap"><div class="sk-bar"></div><div class="sk-table"></div></div>
    <div v-else>
      <div class="action-bar"><h2 class="page-title">🔐 权限管理</h2></div>
      <div class="roles-grid">
        <div v-for="(perms, role) in roles" :key="role" class="role-card">
          <div class="role-header">
            <span class="role-icon">{{ {student:'👨‍🎓',teacher:'👨‍🏫',admin:'🛡️'}[role] }}</span>
            <h3>{{ {student:'学生',teacher:'教师',admin:'管理员'}[role] }}</h3>
          </div>
          <p class="role-desc">{{ perms.description }}</p>
          <div class="perm-grid">
            <span v-for="p in perms.permissions" :key="p" class="perm-tag">{{ getPermissionName(p) }}</span>
          </div>
        </div>
      </div>
      <div v-if="!Object.keys(roles).length" class="empty-state"><div class="empty-icon">🔐</div><div>暂无权限配置</div></div>
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
    const auth = () => (window as any).__VTJ_AUTH__;
    
    // 权限名称映射
    const permissionNames: Record<string, string> = {
      'view_questions': '查看题目',
      'manage_questions': '管理题目',
      'view_users': '查看用户',
      'manage_users': '管理用户',
      'view_logs': '查看日志',
      'manage_settings': '管理设置',
      'manage_backup': '管理备份',
      'view_materials': '查看资料',
      'manage_materials': '管理资料',
      'view_papers': '查看试卷',
      'manage_papers': '管理试卷',
      'view_analytics': '查看统计',
      'manage_permissions': '管理权限',
      'view_help': '查看帮助'
    };
    
    // 获取权限中文名称
    const getPermissionName = (key: string) => {
      return permissionNames[key] || key;
    };
    
    onMounted(async () => {
      try {
        const r = await auth().apiFetch('/api/admin/permissions');
        const d = await r.json();
        if (d.success) roles.value = d.roles || {};
      } catch(e) { console.error('加载权限失败:', e); }
      loading.value = false;
    });
    return { provider, loading, roles, getPermissionName };
  }
});
</script>
<style scoped>
.admin-content{padding:20px;max-width:1000px}.skeleton-wrap{display:flex;flex-direction:column;gap:20px}.sk-bar,.sk-table{background:linear-gradient(90deg,#f0f0f0 25%,#e0e0e0 50%,#f0f0f0 75%);background-size:200% 100%;animation:sk 1.5s infinite;border-radius:10px}.sk-bar{height:60px}.sk-table{height:400px}@keyframes sk{0%{background-position:200% 0}100%{background-position:-200% 0}}
.action-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.page-title{margin:0;color:#1A3C6D}
.roles-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}
.role-card{background:#fff;border-radius:12px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,.06)}
.role-header{display:flex;align-items:center;gap:12px;margin-bottom:12px}.role-icon{font-size:32px}.role-header h3{margin:0;color:#1A3C6D}
.role-desc{font-size:13px;color:#888;margin-bottom:16px}
.perm-grid{display:flex;flex-wrap:wrap;gap:8px}.perm-tag{padding:4px 12px;background:#F5F7FA;border:1px solid #e0e0e0;border-radius:20px;font-size:13px;color:#555}
.empty-state{text-align:center;padding:60px 20px;color:#999}.empty-icon{font-size:48px;margin-bottom:16px}
</style>
