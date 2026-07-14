<template>
  <div class="admin-page"><aside class="aside"><div class="aside-logo">砺安题库·管理端</div><a v-for="m in menu" :key="m.key" :class="['aside-item', { active: m.key === 'questions' }]" @click="$router.push(m.path)"><span class="ai-icon">{{ m.icon }}</span>{{ m.label }}</a></aside>
    <div class="main-area"><div class="topbar">题库管理</div><div class="content">
      <div class="toolbar"><input class="si" v-model="kw" placeholder="搜索题目" @keyup.enter="load"/><select class="ss" v-model="faudit" @change="load"><option value="">全部状态</option><option :value="0">待审核</option><option :value="1">已通过</option><option :value="2">已驳回</option></select><button class="btn" @click="load">搜索</button></div>
      <div class="table-wrap"><table class="dt"><thead><tr><th>ID</th><th>题干</th><th>审核状态</th><th>操作</th></tr></thead>
        <tbody><tr v-for="q in items" :key="q.question_id"><td>{{ q.question_id }}</td><td>{{ q.question_content?.substring(0,60) }}</td><td>{{ {0:'待审核',1:'已通过',2:'已驳回'}[q.audit_status] }}</td><td>
          <button class="bs" @click="audit(q.question_id, 1)">✅通过</button>
          <button class="bs" style="color:#C41E3A" @click="audit(q.question_id, 2)">❌驳回</button>
          <button class="bs" @click="archive(q.question_id)">📦归档</button>
        </td></tr></tbody></table></div>
    </div></div>
  </div>
</template>
<script lang="ts">
import { defineComponent, ref, onMounted } from 'vue';
import { useProvider } from '@vtj/renderer';
export default defineComponent({
  name: 'AdminQuestions', setup() {
    const provider = useProvider({ id: 'admin_questions', version: '1' });
    const kw = ref(''); const faudit = ref(''); const items: any = ref([]);
    const menu = [{key:'dashboard',label:'系统总览',path:'/admin/dashboard',icon:'📊'},{key:'users',label:'用户管理',path:'/admin/users',icon:'👥'},{key:'questions',label:'题库管理',path:'/admin/questions',icon:'📋'},{key:'settings',label:'系统设置',path:'/admin/settings',icon:'⚙️'},{key:'logs',label:'日志审计',path:'/admin/logs',icon:'📝'},{key:'backup',label:'数据备份',path:'/admin/backup',icon:'💾'},{key:'permissions',label:'权限管理',path:'/admin/permissions',icon:'🔐'}];
    onMounted(load);
    async function load() { const p = new URLSearchParams(); if (kw.value) p.append('keyword', kw.value); if (faudit.value) p.append('audit_status', faudit.value); const r = await (window as any).__VTJ_AUTH__.apiFetch('/api/admin/questions?'+p.toString()); const d = await r.json(); if (d.success) items.value = d.items || []; }
    async function audit(id:number, status:number) { await (window as any).__VTJ_AUTH__.apiFetch(`/api/admin/questions/${id}/audit`, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({audit_status:status,audit_comment:status===1?'审核通过':''})}); load(); }
    async function archive(id:number) { await (window as any).__VTJ_AUTH__.apiFetch(`/api/admin/questions/${id}/archive`, {method:'PUT'}); load(); }
    return { provider, kw, faudit, items, menu, load, audit, archive };
  }
});
</script>
<style scoped>
.admin-page{display:flex;min-height:100vh;background:#F5F7FA;font-size:15px}.aside{width:200px;background:#1A3C6D;color:#fff;padding-top:16px}.aside-logo{text-align:center;font-size:15px;font-weight:600;padding:0 12px 16px;border-bottom:1px solid rgba(255,255,255,.1);margin-bottom:8px}.aside-item{display:flex;align-items:center;padding:12px 20px;color:rgba(255,255,255,.7);cursor:pointer;font-size:14px;text-decoration:none;border-left:3px solid transparent}.aside-item:hover,.aside-item.active{color:#fff;background:rgba(255,255,255,.1);border-left-color:#C41E3A}.ai-icon{margin-right:10px;font-size:16px}.main-area{flex:1;display:flex;flex-direction:column}.topbar{height:52px;padding:0 20px;background:#fff;font-weight:600;color:#1A3C6D;border-bottom:1px solid #e8e8e8;display:flex;align-items:center}.content{padding:20px}.toolbar{display:flex;gap:10px;margin-bottom:20px}.si{padding:8px 12px;border:1px solid #d9d9d9;border-radius:6px;flex:1}.ss{padding:8px 12px;border:1px solid #d9d9d9;border-radius:6px}.btn{padding:8px 18px;background:#1A3C6D;color:#fff;border:none;border-radius:6px;cursor:pointer}.table-wrap{background:#fff;border-radius:10px;box-shadow:0 2px 6px rgba(0,0,0,.05);overflow-x:auto}.dt{width:100%;border-collapse:collapse}.dt th{padding:10px 12px;background:#fafafa;text-align:left;font-weight:600;color:#1A3C6D;border-bottom:2px solid #e8e8e8;font-size:14px}.dt td{padding:10px 12px;border-bottom:1px solid #f0f0f0;font-size:14px}.bs{padding:4px 10px;border:1px solid #d9d9d9;background:#fff;border-radius:4px;cursor:pointer;margin-right:4px;font-size:13px}
</style>
