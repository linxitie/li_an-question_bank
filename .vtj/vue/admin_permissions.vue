<template>
  <div class="admin-page"><aside class="aside"><div class="aside-logo">砺安题库·管理端</div><a v-for="m in menu" :key="m.key" :class="['aside-item',{active:m.key==='permissions'}]" @click="$router.push(m.path)"><span class="ai-icon">{{m.icon}}</span>{{m.label}}</a></aside>
    <div class="main-area"><div class="topbar">权限管理</div><div class="content">
      <div class="panel"><h3>角色权限配置（只读视图）</h3>
        <div v-for="(perms, role) in roles" :key="role" class="role-section">
          <h4>{{ {student:'👨‍🎓 学生',teacher:'👨‍🏫 教师',admin:'🛡️ 管理员'}[role] }}</h4>
          <div class="perm-grid">
            <span v-for="p in perms.permissions" :key="p" class="perm-tag">{{ p }}</span>
          </div>
          <p class="role-desc">{{ perms.description }}</p>
        </div>
      </div>
    </div></div>
  </div>
</template>
<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue';
import { useProvider } from '@vtj/renderer';
export default defineComponent({
  name: 'AdminPermissions', setup() {
    const provider = useProvider({ id: 'admin_permissions', version: '1' });
    const roles: any = ref({});
    const menu = [{key:'dashboard',label:'系统总览',path:'/admin/dashboard',icon:'📊'},{key:'users',label:'用户管理',path:'/admin/users',icon:'👥'},{key:'questions',label:'题库管理',path:'/admin/questions',icon:'📋'},{key:'settings',label:'系统设置',path:'/admin/settings',icon:'⚙️'},{key:'logs',label:'日志审计',path:'/admin/logs',icon:'📝'},{key:'backup',label:'数据备份',path:'/admin/backup',icon:'💾'},{key:'permissions',label:'权限管理',path:'/admin/permissions',icon:'🔐'}];
    onMounted(async () => {
      const r = await (window as any).__VTJ_AUTH__.apiFetch('/api/admin/permissions');
      const d = await r.json();
      if (d.success) roles.value = d.roles || {};
    });
    return { provider, roles, menu };
  }
});
</script>
<style scoped>
.admin-page{display:flex;min-height:100vh;background:#F5F7FA;font-size:15px}.aside{width:200px;background:#1A3C6D;color:#fff;padding-top:16px}.aside-logo{text-align:center;font-size:15px;font-weight:600;padding:0 12px 16px;border-bottom:1px solid rgba(255,255,255,.1);margin-bottom:8px}.aside-item{display:flex;align-items:center;padding:12px 20px;color:rgba(255,255,255,.7);cursor:pointer;font-size:14px;text-decoration:none;border-left:3px solid transparent}.aside-item:hover,.aside-item.active{color:#fff;background:rgba(255,255,255,.1);border-left-color:#C41E3A}.ai-icon{margin-right:10px;font-size:16px}.main-area{flex:1;display:flex;flex-direction:column}.topbar{height:52px;padding:0 20px;background:#fff;font-weight:600;color:#1A3C6D;border-bottom:1px solid #e8e8e8;display:flex;align-items:center}.content{padding:20px;max-width:900px}.panel{background:#fff;border-radius:10px;padding:24px;box-shadow:0 2px 6px rgba(0,0,0,.05)}.panel h3{color:#1A3C6D;margin:0 0 20px}.role-section{margin-bottom:24px;padding-bottom:20px;border-bottom:1px solid #f0f0f0}.role-section:last-child{border-bottom:none}.role-section h4{color:#1A3C6D;margin:0 0 10px;font-size:16px}.perm-grid{display:flex;flex-wrap:wrap;gap:8px}.perm-tag{padding:4px 12px;background:#F5F7FA;border:1px solid #e0e0e0;border-radius:20px;font-size:13px;color:#555}.role-desc{font-size:13px;color:#888;margin-top:8px}
</style>
