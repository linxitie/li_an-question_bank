<template>
  <div class="admin-page"><aside class="aside"><div class="aside-logo">砺安题库·管理端</div><a v-for="m in menu" :key="m.key" :class="['aside-item',{active:m.key==='logs'}]" @click="$router.push(m.path)"><span class="ai-icon">{{m.icon}}</span>{{m.label}}</a></aside>
    <div class="main-area"><div class="topbar">日志审计</div><div class="content">
      <div class="toolbar"><input class="si" v-model="kw" placeholder="操作人" @keyup.enter="load"/><select class="ss" v-model="fop" @change="load"><option value="">全部操作</option><option value="CREATE">创建</option><option value="UPDATE">更新</option><option value="DELETE">删除</option></select><button class="btn" @click="load">搜索</button></div>
      <div class="table-wrap"><table class="dt"><thead><tr><th>时间</th><th>用户</th><th>IP</th><th>模块</th><th>操作描述</th><th>耗时(ms)</th></tr></thead>
        <tbody><tr v-for="l in items" :key="l.log_id"><td>{{l.operation_time}}</td><td>{{l.user_name}}</td><td>{{l.ip_address}}</td><td>{{l.module_name}}</td><td>{{l.operation_desc}}</td><td>{{l.duration}}</td></tr></tbody></table></div>
    </div></div>
  </div>
</template>
<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue';
import { useProvider } from '@vtj/renderer';
export default defineComponent({
  name: 'AdminLogs', setup() {
    const provider = useProvider({ id: 'admin_logs', version: '1' });
    const kw = ref(''); const fop = ref(''); const items: any = ref([]);
    const menu = [{key:'dashboard',label:'系统总览',path:'/admin/dashboard',icon:'📊'},{key:'users',label:'用户管理',path:'/admin/users',icon:'👥'},{key:'questions',label:'题库管理',path:'/admin/questions',icon:'📋'},{key:'settings',label:'系统设置',path:'/admin/settings',icon:'⚙️'},{key:'logs',label:'日志审计',path:'/admin/logs',icon:'📝'},{key:'backup',label:'数据备份',path:'/admin/backup',icon:'💾'},{key:'permissions',label:'权限管理',path:'/admin/permissions',icon:'🔐'}];
    onMounted(load);
    async function load() { const p = new URLSearchParams(); if (kw.value) p.append('keyword', kw.value); if (fop.value) p.append('operation_type', fop.value); const r = await (window as any).__VTJ_AUTH__.apiFetch('/api/admin/logs?'+p.toString()); const d = await r.json(); if (d.success) items.value = d.items || []; }
    return { provider, kw, fop, items, menu, load };
  }
});
</script>
<style scoped>
.admin-page{display:flex;min-height:100vh;background:#F5F7FA;font-size:15px}.aside{width:200px;background:#1A3C6D;color:#fff;padding-top:16px}.aside-logo{text-align:center;font-size:15px;font-weight:600;padding:0 12px 16px;border-bottom:1px solid rgba(255,255,255,.1);margin-bottom:8px}.aside-item{display:flex;align-items:center;padding:12px 20px;color:rgba(255,255,255,.7);cursor:pointer;font-size:14px;text-decoration:none;border-left:3px solid transparent}.aside-item:hover,.aside-item.active{color:#fff;background:rgba(255,255,255,.1);border-left-color:#C41E3A}.ai-icon{margin-right:10px;font-size:16px}.main-area{flex:1;display:flex;flex-direction:column}.topbar{height:52px;padding:0 20px;background:#fff;font-weight:600;color:#1A3C6D;border-bottom:1px solid #e8e8e8;display:flex;align-items:center}.content{padding:20px}.toolbar{display:flex;gap:10px;margin-bottom:20px}.si{padding:8px 12px;border:1px solid #d9d9d9;border-radius:6px;flex:1}.ss{padding:8px 12px;border:1px solid #d9d9d9;border-radius:6px}.btn{padding:8px 18px;background:#1A3C6D;color:#fff;border:none;border-radius:6px;cursor:pointer}.table-wrap{background:#fff;border-radius:10px;box-shadow:0 2px 6px rgba(0,0,0,.05);overflow-x:auto}.dt{width:100%;border-collapse:collapse}.dt th{padding:10px 12px;background:#fafafa;text-align:left;font-weight:600;color:#1A3C6D;border-bottom:2px solid #e8e8e8;font-size:14px}.dt td{padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:14px}
</style>
