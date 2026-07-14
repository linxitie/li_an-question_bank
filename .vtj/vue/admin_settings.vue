<template>
  <div class="admin-page"><aside class="aside"><div class="aside-logo">砺安题库·管理端</div><a v-for="m in menu" :key="m.key" :class="['aside-item',{active:m.key==='settings'}]" @click="$router.push(m.path)"><span class="ai-icon">{{m.icon}}</span>{{m.label}}</a></aside>
    <div class="main-area"><div class="topbar">系统设置</div><div class="content">
      <div class="panel"><h3>基本设置</h3>
        <div class="fg"><label>站点名称</label><input class="fi" v-model="settings.site_name"/></div>
        <div class="fg"><label>最大登录尝试</label><input class="fi" type="number" v-model="settings.max_login_attempts"/></div>
        <div class="fg"><label>开放注册</label><select class="fi" v-model="settings.register_open"><option value="true">是</option><option value="false">否</option></select></div>
      </div>
      <div class="panel"><h3>考试设置</h3>
        <div class="fg"><label>自动提交时间(分钟)</label><input class="fi" type="number" v-model="settings.exam_auto_submit_minutes"/></div>
        <div class="fg"><label>密码最小长度</label><input class="fi" type="number" v-model="settings.password_min_length"/></div>
      </div>
      <button class="btn-primary" @click="save">保存设置</button>
      <div v-if="msg" class="msg">{{msg}}</div>
    </div></div>
  </div>
</template>
<script lang="ts">
import { defineComponent, ref, reactive, onMounted } from 'vue';
import { useProvider } from '@vtj/renderer';
export default defineComponent({
  name: 'AdminSettings', setup() {
    const provider = useProvider({ id: 'admin_settings', version: '1' });
    const settings = reactive({ site_name: '', max_login_attempts: '5', register_open: 'true', exam_auto_submit_minutes: '120', password_min_length: '6' });
    const msg = ref('');
    const menu = [{key:'dashboard',label:'系统总览',path:'/admin/dashboard',icon:'📊'},{key:'users',label:'用户管理',path:'/admin/users',icon:'👥'},{key:'questions',label:'题库管理',path:'/admin/questions',icon:'📋'},{key:'settings',label:'系统设置',path:'/admin/settings',icon:'⚙️'},{key:'logs',label:'日志审计',path:'/admin/logs',icon:'📝'},{key:'backup',label:'数据备份',path:'/admin/backup',icon:'💾'},{key:'permissions',label:'权限管理',path:'/admin/permissions',icon:'🔐'}];
    onMounted(async () => {
      const r = await (window as any).__VTJ_AUTH__.apiFetch('/api/admin/settings');
      const d = await r.json();
      if (d.success && d.settings) { Object.keys(settings).forEach(k => { if (d.settings[k]) settings[k as keyof typeof settings] = d.settings[k].value; }); }
    });
    async function save() {
      const s: any = {}; Object.keys(settings).forEach(k => { s[k] = (settings as any)[k]; });
      await (window as any).__VTJ_AUTH__.apiFetch('/api/admin/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ settings: s }) });
      msg.value = '设置已保存'; setTimeout(() => msg.value = '', 2000);
    }
    return { provider, settings, msg, menu, save };
  }
});
</script>
<style scoped>
.admin-page{display:flex;min-height:100vh;background:#F5F7FA;font-size:15px}.aside{width:200px;background:#1A3C6D;color:#fff;padding-top:16px}.aside-logo{text-align:center;font-size:15px;font-weight:600;padding:0 12px 16px;border-bottom:1px solid rgba(255,255,255,.1);margin-bottom:8px}.aside-item{display:flex;align-items:center;padding:12px 20px;color:rgba(255,255,255,.7);cursor:pointer;font-size:14px;text-decoration:none;border-left:3px solid transparent}.aside-item:hover,.aside-item.active{color:#fff;background:rgba(255,255,255,.1);border-left-color:#C41E3A}.ai-icon{margin-right:10px;font-size:16px}.main-area{flex:1;display:flex;flex-direction:column}.topbar{height:52px;padding:0 20px;background:#fff;font-weight:600;color:#1A3C6D;border-bottom:1px solid #e8e8e8;display:flex;align-items:center}.content{padding:20px;max-width:700px}.panel{background:#fff;border-radius:10px;padding:20px;margin-bottom:20px;box-shadow:0 2px 6px rgba(0,0,0,.05)}.panel h3{color:#1A3C6D;margin:0 0 16px}.fg{margin-bottom:14px}.fg label{display:block;margin-bottom:4px;font-weight:600}.fi{width:100%;padding:8px 12px;border:1px solid #d9d9d9;border-radius:6px;font-size:15px;box-sizing:border-box}.btn-primary{padding:10px 24px;background:#C41E3A;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:15px}.msg{margin-top:12px;padding:8px 16px;background:#f0f9eb;color:#67C23A;border-radius:6px}
</style>
