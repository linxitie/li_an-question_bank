<template>
  <div class="admin-content">
    <div v-if="loading" class="skeleton-wrap"><div class="sk-bar"></div><div class="sk-table"></div></div>
    <div v-else>
      <div class="action-bar"><h2 class="page-title">📋 日志审计</h2>
        <div class="action-buttons">
          <button class="btn-secondary" @click="exportLogs">📤 导出日志</button>
          <button class="btn-refresh" @click="load">🔄 刷新</button>
        </div>
      </div>
      <div class="filter-bar">
        <input class="filter-input" v-model="kw" placeholder="操作人" @keyup.enter="load"/>
        <select class="filter-select" v-model="fop" @change="load"><option value="">全部操作</option><option value="CREATE">创建</option><option value="UPDATE">更新</option><option value="DELETE">删除</option><option value="LOGIN">登录</option></select>
        <input class="filter-input" type="date" v-model="startDate"/>
        <input class="filter-input" type="date" v-model="endDate"/>
        <button class="btn-search" @click="load">🔍 搜索</button>
        <button class="btn-reset" @click="resetFilter">🔄 重置</button>
      </div>
      <div class="table-container">
        <table class="data-table"><thead><tr><th>时间</th><th>用户</th><th>角色</th><th>IP</th><th>模块</th><th>操作描述</th><th>状态</th><th>耗时(ms)</th></tr></thead>
        <tbody><tr v-for="l in items" :key="l.log_id">
          <td>{{ formatTime(l.operation_time) }}</td><td>{{ l.user_name }}</td><td><span class="tag">{{ l.user_role || '-' }}</span></td><td>{{ l.ip_address }}</td><td>{{ l.module_name }}</td><td class="desc-cell">{{ l.operation_desc }}</td>
          <td><span class="status-badge" :class="l.success ? 'status-ok' : 'status-fail'">{{ l.success ? '成功' : '失败' }}</span></td>
          <td>{{ l.duration }}</td></tr></tbody></table>
        <div v-if="!items.length" class="empty-state"><div class="empty-icon">📋</div><div>暂无日志数据</div></div>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, onMounted } from 'vue';
import { useProvider } from '@vtj/renderer';
export default defineComponent({
  name: 'AdminLogs', setup() {
    const provider = useProvider({ id: 'admin_logs', version: '1' });
    const loading = ref(true);
    const kw = ref(''); const fop = ref(''); const items: any = ref([]);
    const startDate = ref(''); const endDate = ref('');
    const auth = () => (window as any).__VTJ_AUTH__;
    onMounted(load);
    async function load() {
      loading.value = true;
      const p = new URLSearchParams();
      if (kw.value) p.append('keyword', kw.value);
      if (fop.value) p.append('operation_type', fop.value);
      if (startDate.value) p.append('start_date', startDate.value);
      if (endDate.value) p.append('end_date', endDate.value);
      const r = await auth().apiFetch('/api/admin/logs?'+p.toString());
      const d = await r.json(); if (d.success) items.value = d.items || [];
      loading.value = false;
    }
    function resetFilter() { kw.value=''; fop.value=''; startDate.value=''; endDate.value=''; load(); }
    function formatTime(t:string) { if(!t) return '-'; return t.substring(0,19); }
    function exportLogs() {
      const params = new URLSearchParams();
      if (startDate.value) params.append('start_date', startDate.value);
      if (endDate.value) params.append('end_date', endDate.value);
      window.open('/api/admin/logs/export?' + params.toString());
    }
    return { provider, loading, kw, fop, items, startDate, endDate, load, resetFilter, formatTime, exportLogs };
  }
});
</script>
<style scoped>
.admin-content{padding:20px}.skeleton-wrap{display:flex;flex-direction:column;gap:20px}.sk-bar,.sk-table{background:linear-gradient(90deg,#f0f0f0 25%,#e0e0e0 50%,#f0f0f0 75%);background-size:200% 100%;animation:sk 1.5s infinite;border-radius:10px}.sk-bar{height:60px}.sk-table{height:400px}@keyframes sk{0%{background-position:200% 0}100%{background-position:-200% 0}}
.action-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.page-title{margin:0;color:#1A3C6D}.action-buttons{display:flex;gap:10px}
.filter-bar{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap}.filter-input{flex:1;min-width:150px;padding:8px 12px;border:1px solid #d9d9d9;border-radius:6px}.filter-select{padding:8px 12px;border:1px solid #d9d9d9;border-radius:6px}
.table-container{background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.06);overflow:hidden}.data-table{width:100%;border-collapse:collapse}.data-table th{padding:12px 16px;background:#fafafa;text-align:left;font-weight:600;color:#1A3C6D;border-bottom:2px solid #e8e8e8;font-size:14px}.data-table td{padding:12px 16px;border-bottom:1px solid #f0f0f0;font-size:14px}.data-table tr:hover{background:#f5f7fa}
.desc-cell{max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tag{padding:2px 8px;border-radius:4px;font-size:12px;background:#e6f7ff;color:#1890ff}
.status-badge{padding:4px 8px;border-radius:4px;font-size:12px}.status-ok{background:#f6ffed;color:#52c41a}.status-fail{background:#fff2f0;color:#ff4d4f}
.empty-state{text-align:center;padding:60px 20px;color:#999}.empty-icon{font-size:48px;margin-bottom:16px}
.btn-search{padding:8px 16px;background:#1A3C6D;color:#fff;border:none;border-radius:6px;cursor:pointer}.btn-secondary{padding:8px 16px;background:#fff;color:#333;border:1px solid #d9d9d9;border-radius:6px;cursor:pointer}.btn-refresh{padding:8px 16px;background:#fff;color:#666;border:1px solid #d9d9d9;border-radius:6px;cursor:pointer}.btn-reset{padding:8px 16px;background:#fff;color:#666;border:1px solid #d9d9d9;border-radius:6px;cursor:pointer}
</style>
