<template>
  <div class="admin-content">
    <div v-if="loading" class="skeleton-wrap"><div class="sk-bar"></div><div class="sk-table"></div></div>
    <div v-else>
      <div class="action-bar"><h2 class="page-title">📋 题库管理</h2>
        <div class="action-buttons">
          <button class="btn-secondary" @click="batchAudit(1)">✅ 批量通过</button>
          <button class="btn-danger" @click="batchAudit(2)">❌ 批量驳回</button>
        </div>
      </div>
      <div class="filter-bar">
        <input class="filter-input" v-model="kw" placeholder="搜索题目" @keyup.enter="load"/>
        <select class="filter-select" v-model="faudit" @change="load"><option value="">全部状态</option><option :value="0">待审核</option><option :value="1">已通过</option><option :value="2">已驳回</option></select>
        <button class="btn-search" @click="load">🔍 搜索</button>
      </div>
      <div class="batch-bar" v-if="selectedIds.length"><span>已选 {{ selectedIds.length }} 项</span><button class="btn-batch" @click="batchAudit(1)">批量通过</button><button class="btn-batch-danger" @click="batchAudit(2)">批量驳回</button></div>
      <div class="table-container">
        <table class="data-table"><thead><tr><th><input type="checkbox" @change="toggleAll" :checked="isAllSelected"/></th><th>ID</th><th>科目</th><th>题干摘要</th><th>题型</th><th>难度</th><th>审核状态</th><th>操作</th></tr></thead>
        <tbody><tr v-for="q in items" :key="q.question_id" :class="{selected:selectedIds.includes(q.question_id)}"><td><input type="checkbox" :value="q.question_id" v-model="selectedIds"/></td><td>{{ q.question_id }}</td><td><span class="tag">{{ subjectName(q.subject_id) }}</span></td><td class="question-summary">{{ stripPromoText(q.question_content)?.substring(0,80) }}...</td><td><span class="type-badge" :class="typeBadgeClass(q.type_name)">{{ q.type_name }}</span></td><td>{{ difficultyStars(q.difficulty) }}</td><td><span class="status-badge" :class="'status-'+q.audit_status">{{ {0:'待审核',1:'已通过',2:'已驳回'}[q.audit_status] }}</span></td>
          <td class="actions"><button class="btn-icon" @click="view(q)">👁️</button><button class="btn-icon btn-success" @click="audit(q.question_id,1)" v-if="q.audit_status===0">✅</button><button class="btn-icon btn-danger" @click="audit(q.question_id,2)" v-if="q.audit_status===0">❌</button><button class="btn-icon" @click="archive(q.question_id)">📦</button></td></tr></tbody></table>
        <div v-if="!items.length" class="empty-state"><div class="empty-icon">📋</div><div>暂无题目数据</div></div>
      </div>
    </div>
    <div class="modal-overlay" v-if="showDetail" @click.self="showDetail=false"><div class="modal-content">
      <div class="modal-header"><h3>题目详情 #{{ current?.question_id }}</h3><span class="type-badge">{{ typeName(current?.type_name) }}</span><span class="close" @click="showDetail=false">✕</span></div>
      <div class="f"><strong>科目：</strong>{{ subjectName(current?.subject_id) }}　<strong>难度：</strong>{{ '★'.repeat(current?.difficulty||1) }}　<strong>分值：</strong>{{ current?.score }}</div>
      <div class="f"><strong>题干：</strong><div class="box" v-html="current?.full_content || current?.question_content"></div></div>
      <div class="f" v-if="hasOpts(current?.options)"><strong>选项：</strong><div v-for="(opt,key) in parseOpts(current?.options)" :key="key" :class="['opt', isCorrect(key,current?.answer)?'ok':'']"><b>{{ key }}.</b><span class="opt-v" v-html="opt"></span><span v-if="isCorrect(key,current?.answer)" class="mark">✅</span></div></div>
      <div class="f"><strong>答案：</strong><span class="ans">{{ current?.answer }}</span></div>
      <div class="f"><strong>解析：</strong><div class="box" v-if="current?.answer_analysis" v-html="current?.answer_analysis"></div><span v-else class="none">暂无</span></div>
    </div></div>
  </div>
</template>
<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, onMounted } from 'vue';
import { useProvider } from '@vtj/renderer';
export default defineComponent({
  name: 'AdminQuestions', setup() {
    const provider = useProvider({ id: 'admin_questions', version: '1' });
    const loading = ref(true);
    const kw = ref(''); const faudit = ref(''); const items: any = ref([]);
    const selectedIds: any = ref([]);
    const showDetail = ref(false); const current: any = ref(null);
    const isAllSelected = ref(false);
    const auth = () => (window as any).__VTJ_AUTH__;
    onMounted(load);
    async function load() { loading.value = true; const p = new URLSearchParams(); if (kw.value) p.append('keyword', kw.value); if (faudit.value) p.append('audit_status', faudit.value); const r = await auth().apiFetch('/api/admin/questions?'+p.toString()); const d = await r.json(); if (d.success) items.value = d.items || []; loading.value = false; }
    async function audit(id:number, status:number) { await auth().apiFetch(`/api/admin/questions/${id}/audit`, {method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({audit_status:status,audit_comment:status===1?'审核通过':''})}); load(); }
    async function archive(id:number) { await auth().apiFetch(`/api/admin/questions/${id}/archive`, {method:'PUT'}); load(); }
    function view(q:any) { current.value = q; showDetail.value = true; }
    function subjectName(id:any) { return ({1:'行测',2:'申论',3:'公专'} as any)[id] || '-'; }
    function stripPromoText(text: string): string {
      if (!text) return '';
      return text
        .replace(/来源[:：].*$/gm, '')
        .replace(/\[图片\]/g, '')
        .replace(/<[^>]+>/g, '')
        .trim();
    }
    function typeBadgeClass(typeName: string): string {
      const map: Record<string, string> = {
        '单选题': 'type-single',
        '多选题': 'type-multi',
        '论述题': 'type-essay',
        '写作题': 'type-writing'
      };
      return map[typeName] || 'type-default';
    }
    function difficultyStars(level: number): string {
      return '⭐'.repeat(Math.min(level || 1, 5));
    }
    function typeName(t:any) { return t || '-'; }
    function hasOpts(o:any) { if (!o) return false; if (Array.isArray(o)) return o.length>0; if (typeof o==='object') return Object.keys(o).length>0; if (typeof o==='string') { try { return (JSON.parse(o)||[]).length>0; } catch(e){ return false; } } return false; }
    function parseOpts(o:any) { if (!o) return {}; if (Array.isArray(o)) { const r:any={}; o.forEach((x:any,i:number)=>{ r[String.fromCharCode(65+i)] = (x && typeof x==='object') ? (x.value||x.text||'') : String(x); }); return r; } if (typeof o==='object') return o; if (typeof o==='string') { try { return parseOpts(JSON.parse(o)); } catch(e){ return {}; } } return {}; }
    function isCorrect(k:string, a:any) { if (!a) return false; const n=String(a).trim().toUpperCase().replace(/[^A-D]/g,''); return n.includes(k); }
    function toggleAll(e:any) { selectedIds.value = e.target.checked ? items.value.map((q:any)=>q.question_id) : []; }
    async function batchAudit(status:number) { for (const id of selectedIds.value) { await audit(id, status); } selectedIds.value = []; }
    return { provider, loading, kw, faudit, items, selectedIds, isAllSelected, showDetail, current, load, audit, archive, view, subjectName, stripPromoText, typeBadgeClass, difficultyStars, typeName, hasOpts, parseOpts, isCorrect, toggleAll, batchAudit };
  }
});
</script>
<style scoped>
.admin-content{padding:20px}.skeleton-wrap{display:flex;flex-direction:column;gap:20px}.sk-bar,.sk-table{background:linear-gradient(90deg,#f0f0f0 25%,#e0e0e0 50%,#f0f0f0 75%);background-size:200% 100%;animation:sk 1.5s infinite;border-radius:10px}.sk-bar{height:60px}.sk-table{height:400px}@keyframes sk{0%{background-position:200% 0}100%{background-position:-200% 0}}
.action-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.page-title{margin:0;color:#1A3C6D}.action-buttons{display:flex;gap:10px}
.filter-bar{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap}.filter-input{flex:1;min-width:200px;padding:8px 12px;border:1px solid #d9d9d9;border-radius:6px}.filter-select{padding:8px 12px;border:1px solid #d9d9d9;border-radius:6px}
.batch-bar{display:flex;align-items:center;gap:12px;padding:12px 16px;background:#e6f7ff;border:1px solid #91d5ff;border-radius:6px;margin-bottom:16px}
.table-container{background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.06);overflow:hidden}.data-table{width:100%;border-collapse:collapse}.data-table th{padding:12px 16px;background:#fafafa;text-align:left;font-weight:600;color:#1A3C6D;border-bottom:2px solid #e8e8e8;font-size:14px}.data-table td{padding:12px 16px;border-bottom:1px solid #f0f0f0;font-size:14px}.data-table tr:hover{background:#f5f7fa}.data-table tr.selected{background:#e6f7ff}
.q-content{max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tag{padding:2px 8px;border-radius:4px;font-size:12px;background:#e6f7ff;color:#1890ff}
.status-badge{padding:4px 8px;border-radius:4px;font-size:12px}.status-0{background:#fff7e6;color:#fa8c16}.status-1{background:#f6ffed;color:#52c41a}.status-2{background:#fff2f0;color:#ff4d4f}
.actions{display:flex;gap:4px}.btn-icon{width:28px;height:28px;border:none;background:transparent;cursor:pointer;border-radius:4px;font-size:14px}.btn-icon:hover{background:#f0f0f0}.btn-success:hover{background:#f6ffed}.btn-danger:hover{background:#fff2f0}
.empty-state{text-align:center;padding:60px 20px;color:#999}.empty-icon{font-size:48px;margin-bottom:16px}
.modal-overlay{position:fixed;inset:0;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;z-index:1000}.modal-content{background:#fff;border-radius:12px;padding:24px;max-width:1100px;width:90%;max-height:80vh;overflow-y:auto}
.modal-header{display:flex;align-items:center;gap:10px;margin-bottom:16px}.modal-header h3{color:#1A3C6D;margin:0;flex:1}.type-badge{background:#409EFF;color:#fff;padding:3px 12px;border-radius:12px;font-size:13px}.close{cursor:pointer;font-size:20px;color:#909399}
.f{margin-bottom:12px;line-height:1.8}.f strong{color:#1A3C6D}.box{margin-top:6px;padding:10px 14px;background:#f9fafb;border-radius:8px;line-height:1.8}
.opt{display:flex;align-items:flex-start;gap:8px;padding:6px 12px;border:1px solid #e8e8e8;border-radius:6px;margin-top:4px;background:#fafafa}.opt.ok{background:#f0fdf4;border-color:#86efac}.opt-v{flex:1}.mark{color:#22c55e;font-weight:700}.ans{color:#22c55e;font-weight:700;font-size:16px}.none{color:#909399}
.btn-search{padding:8px 16px;background:#1A3C6D;color:#fff;border:none;border-radius:6px;cursor:pointer}.btn-secondary{padding:8px 16px;background:#fff;color:#333;border:1px solid #d9d9d9;border-radius:6px;cursor:pointer}.btn-danger{padding:8px 16px;background:#ff4d4f;color:#fff;border:none;border-radius:6px;cursor:pointer}.btn-batch{padding:6px 12px;background:#1890ff;color:#fff;border:none;border-radius:4px;cursor:pointer}.btn-batch-danger{padding:6px 12px;background:#ff4d4f;color:#fff;border:none;border-radius:4px;cursor:pointer}
.type-badge { padding: 2px 8px; border-radius: 4px; font-size: 12px; }
.type-single { background: #e6f7ff; color: #1890ff; }
.type-multi { background: #fff7e6; color: #fa8c16; }
.type-essay { background: #fff1f0; color: #f5222d; }
.type-writing { background: #f6ffed; color: #52c41a; }
.type-default { background: #f5f5f5; color: #999; }
.question-summary { max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
