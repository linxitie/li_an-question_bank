<template>
  <div class="admin-page"><aside class="aside"><div class="aside-logo">砺安题库·管理端</div><a v-for="m in menu" :key="m.key" :class="['aside-item',{active:m.key==='backup'}]" @click="$router.push(m.path)"><span class="ai-icon">{{m.icon}}</span>{{m.label}}</a></aside>
    <div class="main-area"><div class="topbar">数据备份</div><div class="content">
      <button class="btn-primary" @click="createBackup">+ 创建备份</button>
      <div class="table-wrap" style="margin-top:20px"><table class="dt"><thead><tr><th>备份名称</th><th>类型</th><th>大小</th><th>状态</th><th>时间</th><th>操作</th></tr></thead>
        <tbody><tr v-for="b in items" :key="b.backup_id"><td>{{b.backup_name}}</td><td>{{b.backup_type==='full'?'全量':'增量'}}</td><td>{{(b.file_size/1024).toFixed(1)}}KB</td><td>{{{running:'进行中',completed:'已完成',failed:'失败'}[b.status]}}</td><td>{{b.start_time}}</td><td><button class="bs" @click="restore(b.backup_id)" :disabled="b.status!=='completed'">恢复</button></td></tr></tbody></table></div>
      <div v-if="msg" class="msg">{{msg}}</div>
    </div></div>
  </div>
</template>
<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue';
import { useProvider } from '@vtj/renderer';
export default defineComponent({
  name: 'AdminBackup', setup() {
    const provider = useProvider({ id: 'admin_backup', version: '1' });
    const items: any = ref([]); const msg = ref('');
    const menu = [{key:'dashboard',label:'系统总览',path:'/admin/dashboard',icon:'📊'},{key:'users',label:'用户管理',path:'/admin/users',icon:'👥'},{key:'questions',label:'题库管理',path:'/admin/questions',icon:'📋'},{key:'settings',label:'系统设置',path:'/admin/settings',icon:'⚙️'},{key:'logs',label:'日志审计',path:'/admin/logs',icon:'📝'},{key:'backup',label:'数据备份',path:'/admin/backup',icon:'💾'},{key:'permissions',label:'权限管理',path:'/admin/permissions',icon:'🔐'}];
    onMounted(load);
    async function load() { const r = await (window as any).__VTJ_AUTH__.apiFetch('/api/admin/backups'); const d = await r.json(); if (d.success) items.value = d.items || []; }
    async function createBackup() { const r = await (window as any).__VTJ_AUTH__.apiFetch('/api/admin/backup', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({backup_type:'full'})}); const d = await r.json(); msg.value = d.message || '备份完成'; setTimeout(()=>msg.value='',3000); load(); }
    async function restore(id:number) { if (confirm('确定恢复此备份？')) { await (window as any).__VTJ_AUTH__.apiFetch(`/api/admin/backups/${id}/restore`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:true})}); msg.value = '恢复请求已提交'; } }
    return { provider, items, msg, menu, createBackup, restore };
  }
});
</script>
<style scoped>
.admin-page{display:flex;min-height:100vh;background:#F5F7FA;font-size:15px}.aside{width:200px;background:#1A3C6D;color:#fff;padding-top:16px}.aside-logo{text-align:center;font-size:15px;font-weight:600;padding:0 12px 16px;border-bottom:1px solid rgba(255,255,255,.1);margin-bottom:8px}.aside-item{display:flex;align-items:center;padding:12px 20px;color:rgba(255,255,255,.7);cursor:pointer;font-size:14px;text-decoration:none;border-left:3px solid transparent}.aside-item:hover,.aside-item.active{color:#fff;background:rgba(255,255,255,.1);border-left-color:#C41E3A}.ai-icon{margin-right:10px;font-size:16px}.main-area{flex:1;display:flex;flex-direction:column}.topbar{height:52px;padding:0 20px;background:#fff;font-weight:600;color:#1A3C6D;border-bottom:1px solid #e8e8e8;display:flex;align-items:center}.content{padding:20px}.btn-primary{padding:10px 22px;background:#1A3C6D;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:15px}.table-wrap{background:#fff;border-radius:10px;box-shadow:0 2px 6px rgba(0,0,0,.05);overflow-x:auto}.dt{width:100%;border-collapse:collapse}.dt th{padding:10px 12px;background:#fafafa;text-align:left;font-weight:600;color:#1A3C6D;border-bottom:2px solid #e8e8e8;font-size:14px}.dt td{padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:14px}.bs{padding:4px 10px;border:1px solid #d9d9d9;background:#fff;border-radius:4px;cursor:pointer;margin-right:4px;font-size:13px}.msg{margin-top:12px;padding:8px 16px;background:#f0f9eb;color:#67C23A;border-radius:6px}
</style>
