<template>
  <div class="admin-page"><aside class="aside"><div class="aside-logo">砺安题库·管理端</div><a v-for="m in menu" :key="m.key" :class="['aside-item', { active: m.key === 'users' }]" @click="$router.push(m.path)"><span class="ai-icon">{{ m.icon }}</span>{{ m.label }}</a></aside>
    <div class="main-area"><div class="topbar"><span>用户管理</span><span>{{ username }}</span></div>
    <div class="content">
      <div class="toolbar">
        <input class="si" v-model="keyword" placeholder="搜索姓名/学号" @keyup.enter="search" />
        <select class="ss" v-model="filterType" @change="search"><option value="">全部角色</option><option value="student">学生</option><option value="teacher">教师</option><option value="admin">管理员</option></select>
        <button class="btn" @click="search">搜索</button>
        <div class="spacer"></div>
        <button class="btn-primary" @click="showCreate=true">+ 新增用户</button>
      </div>
      <div class="table-wrap"><table class="dt"><thead><tr><th>ID</th><th>学号</th><th>姓名</th><th>角色</th><th>班级</th><th>状态</th><th>最后登录</th><th>操作</th></tr></thead>
        <tbody><tr v-for="u in users" :key="u.user_id">
          <td>{{ u.user_id }}</td><td>{{ u.user_no }}</td><td>{{ u.username }}</td>
          <td>{{ {student:'学生',teacher:'教师',admin:'管理员'}[u.user_type] }}</td>
          <td>{{ u.class_name || '-' }}</td>
          <td><span :style="{color: u.is_disabled?'#C41E3A':'#67C23A'}">{{ u.is_disabled ? '已禁用' : '正常' }}</span></td>
          <td>{{ u.last_login || '-' }}</td>
          <td>
            <button class="bs" @click="toggleDisable(u)" :style="{color: u.is_disabled?'#67C23A':'#C41E3A'}">{{ u.is_disabled ? '启用' : '禁用' }}</button>
            <button class="bs" @click="resetPwd(u.user_id)" v-if="userLevel>=3">重置密码</button>
          </td>
        </tr></tbody></table></div>
    </div></div>
    <div class="modal" v-if="showCreate" @click.self="showCreate=false"><div class="modal-box"><h3>新增用户</h3>
      <div class="fg"><label>用户名</label><input class="fi" v-model="form.username" /></div>
      <div class="fg"><label>学号</label><input class="fi" v-model="form.user_no" /></div>
      <div class="fg"><label>密码</label><input class="fi" type="password" v-model="form.password" /></div>
      <div class="fg"><label>角色</label><select class="fi" v-model="form.user_type"><option value="student">学生</option><option value="teacher">教师</option></select></div>
      <button class="btn-primary" @click="doCreate">确认创建</button>
    </div></div>
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
    const username = ref(''); const userLevel = ref(0);
    const keyword = ref(''); const filterType = ref('');
    const users: any = ref([]);
    const showCreate = ref(false);
    const form = ref({ username: '', user_no: '', password: '', user_type: 'student' });
    const menu = [
      { key: 'dashboard', label: '系统总览', path: '/admin/dashboard', icon: '📊' },
      { key: 'users', label: '用户管理', path: '/admin/users', icon: '👥' },
      { key: 'questions', label: '题库管理', path: '/admin/questions', icon: '📋' },
      { key: 'settings', label: '系统设置', path: '/admin/settings', icon: '⚙️' },
      { key: 'logs', label: '日志审计', path: '/admin/logs', icon: '📝' },
      { key: 'backup', label: '数据备份', path: '/admin/backup', icon: '💾' },
      { key: 'permissions', label: '权限管理', path: '/admin/permissions', icon: '🔐' },
    ];

    onMounted(async () => { const a = (window as any).__VTJ_AUTH__; if (a) { username.value = a.getUsername() || ''; userLevel.value = a.getRoleLevel(); } await load(); });
    async function load() {
      const p = new URLSearchParams(); if (keyword.value) p.append('keyword', keyword.value); if (filterType.value) p.append('user_type', filterType.value);
      const r = await (window as any).__VTJ_AUTH__.apiFetch('/api/admin/users?' + p.toString());
      const d = await r.json(); if (d.success) users.value = d.items || [];
    }
    function search() { load(); }
    async function toggleDisable(u: any) {
      await (window as any).__VTJ_AUTH__.apiFetch(`/api/admin/users/${u.user_id}/disable`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_disabled: !u.is_disabled, reason: u.is_disabled ? '管理员启用' : '管理员禁用' })
      }); load();
    }
    async function resetPwd(id: number) {
      if (confirm('确定重置密码？')) {
        const r = await (window as any).__VTJ_AUTH__.apiFetch(`/api/admin/users/${id}/reset-password`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        const d = await r.json(); if (d.success) alert('新密码: ' + d.new_password);
      }
    }
    async function doCreate() {
      await (window as any).__VTJ_AUTH__.apiFetch('/api/admin/users', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form.value) });
      showCreate.value = false; form.value = { username: '', user_no: '', password: '', user_type: 'student' }; load();
    }
    return { provider, username, userLevel, keyword, filterType, users, showCreate, form, menu, search, toggleDisable, resetPwd, doCreate };
  }
});
</script>

<style scoped>
.admin-page { display: flex; min-height: 100vh; background: #F5F7FA; font-size: 15px; }
.aside { width: 200px; background: #1A3C6D; color: #fff; padding-top: 16px; flex-shrink: 0; }
.aside-logo { text-align: center; font-size: 15px; font-weight: 600; padding: 0 12px 16px; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 8px; }
.aside-item { display: flex; align-items: center; padding: 12px 20px; color: rgba(255,255,255,0.7); text-decoration: none; cursor: pointer; font-size: 14px; border-left: 3px solid transparent; }
.aside-item:hover, .aside-item.active { color: #fff; background: rgba(255,255,255,0.1); border-left-color: #C41E3A; }
.ai-icon { margin-right: 10px; font-size: 16px; }
.main-area { flex: 1; display: flex; flex-direction: column; }
.topbar { display: flex; justify-content: space-between; height: 52px; padding: 0 20px; background: #fff; font-weight: 600; color: #1A3C6D; border-bottom: 1px solid #e8e8e8; align-items: center; }
.content { padding: 20px; }
.toolbar { display: flex; gap: 10px; margin-bottom: 20px; align-items: center; }
.si { padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; flex: 1; } .ss { padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; }
.btn { padding: 8px 18px; background: #1A3C6D; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.btn-primary { padding: 8px 18px; background: #C41E3A; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.spacer { flex: 1; }
.table-wrap { background: #fff; border-radius: 10px; box-shadow: 0 2px 6px rgba(0,0,0,0.05); overflow-x: auto; }
.dt { width: 100%; border-collapse: collapse; } .dt th { padding: 10px 12px; background: #fafafa; text-align: left; font-weight: 600; color: #1A3C6D; border-bottom: 2px solid #e8e8e8; font-size: 14px; }
.dt td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
.bs { padding: 4px 10px; border: 1px solid #d9d9d9; background: #fff; border-radius: 4px; cursor: pointer; margin-right: 4px; font-size: 13px; }
.modal { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: #fff; border-radius: 12px; padding: 24px; width: 420px; }
.modal-box h3 { color: #1A3C6D; margin: 0 0 16px; }
.fg { margin-bottom: 12px; } .fg label { display: block; margin-bottom: 4px; font-weight: 600; }
.fi { width: 100%; padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; box-sizing: border-box; }
</style>
