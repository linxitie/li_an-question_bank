<template>
  <div class="admin-content">
    <div v-if="loading" class="skeleton-wrap"><div class="sk-bar"></div><div class="sk-table"></div></div>
    <div v-else>
      <div class="action-bar"><h2 class="page-title">💾 数据备份</h2>
        <div class="action-buttons">
          <button class="btn-primary" @click="createBackup">📦 立即备份</button>
        </div>
      </div>
      <div class="stats-row">
        <div class="stat-card"><div class="stat-icon">💿</div><div><div class="stat-value">{{ dbSize }}</div><div class="stat-label">数据库大小</div></div></div>
        <div class="stat-card"><div class="stat-icon">📁</div><div><div class="stat-value">{{ backupSize }}</div><div class="stat-label">备份存储</div></div></div>
        <div class="stat-card"><div class="stat-icon">⏰</div><div><div class="stat-value">{{ autoBackup ? '已开启' : '已关闭' }}</div><div class="stat-label">自动备份</div></div></div>
      </div>
      <div class="table-container">
        <table class="data-table"><thead><tr><th>备份名称</th><th>类型</th><th>大小</th><th>状态</th><th>时间</th><th>操作</th></tr></thead>
        <tbody><tr v-for="b in items" :key="b.backup_id">
          <td>{{ b.backup_name }}</td><td><span class="tag">{{ b.backup_type==='full'?'全量':'增量' }}</span></td><td>{{ formatSize(b.file_size) }}</td>
          <td><span class="status-badge" :class="'status-'+b.status">{{ {running:'进行中',completed:'已完成',failed:'失败'}[b.status] }}</span></td>
          <td>{{ formatChineseTime(b.start_time) }}</td>
          <td class="actions"><button class="btn-icon" @click="downloadBackup(b)" :disabled="b.status!=='completed'" title="下载">📥</button><button class="btn-icon btn-danger" @click="restore(b.backup_id)" :disabled="b.status!=='completed'" title="恢复">🔄</button></td>
        </tr></tbody></table>
        <div v-if="!items.length" class="empty-state"><div class="empty-icon">💾</div><div>暂无备份文件</div></div>
      </div>
      <div class="msg" v-if="msg">{{ msg }}</div>
    </div>
  </div>
</template>
<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, onMounted } from 'vue';
import { useProvider } from '@vtj/renderer';
export default defineComponent({
  name: 'AdminBackup', setup() {
    const provider = useProvider({ id: 'admin_backup', version: '1' });
    const loading = ref(true);
    const items: any = ref([]);
    const dbSize = ref('--');
    const backupSize = ref('--');
    const autoBackup = ref(true);
    const msg = ref('');
    const auth = () => (window as any).__VTJ_AUTH__;
    onMounted(load);
    async function load() {
      loading.value = true;
      const r = await auth().apiFetch('/api/admin/backups');
      const d = await r.json(); if (d.success) items.value = d.items || [];
      try {
        const statsRes = await auth().apiFetch('/api/admin/backup/stats');
        const statsData = await statsRes.json();
        if (statsData.success) {
          dbSize.value = statsData.db_size || '--';
          backupSize.value = statsData.backup_size || '--';
          autoBackup.value = statsData.auto_backup ?? true;
        }
      } catch (e) { /* 统计接口可选 */ }
      loading.value = false;
    }
    async function createBackup() {
      msg.value = '正在创建备份...';
      // 生成中文备份名称
      const now = new Date();
      const year = now.getFullYear();
      const month = String(now.getMonth() + 1).padStart(2, '0');
      const day = String(now.getDate()).padStart(2, '0');
      const hours = String(now.getHours()).padStart(2, '0');
      const minutes = String(now.getMinutes()).padStart(2, '0');
      const backupName = `系统全量备份_${year}年${month}月${day}日_${hours}点${minutes}分`;
      
      const r = await auth().apiFetch('/api/admin/backup', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          backup_type:'full',
          backup_name: backupName
        })
      });
      const d = await r.json(); msg.value = d.message || '✅ 备份完成';
      setTimeout(()=>msg.value='',3000); load();
    }
    async function restore(id:number) {
      if (confirm('⚠️ 确定恢复此备份？此操作不可逆！')) {
        await auth().apiFetch(`/api/admin/backups/${id}/restore`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:true})});
        msg.value = '恢复请求已提交';
      }
    }
    function downloadBackup(b:any) { console.log('下载备份:', b.backup_name); }
    function formatSize(bytes:number) { return bytes ? (bytes/1024/1024).toFixed(1)+'MB' : '--'; }
    
    // 格式化时间为中文格式
    function formatChineseTime(timeStr:string) {
      if (!timeStr) return '-';
      const date = new Date(timeStr);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');
      return `${year}年${month}月${day}日 ${hours}:${minutes}:${seconds}`;
    }
    return { provider, loading, items, dbSize, backupSize, autoBackup, msg, load, createBackup, restore, downloadBackup, formatSize };
  }
});
</script>
<style scoped>
.admin-content{padding:20px}.skeleton-wrap{display:flex;flex-direction:column;gap:20px}.sk-bar,.sk-table{background:linear-gradient(90deg,#f0f0f0 25%,#e0e0e0 50%,#f0f0f0 75%);background-size:200% 100%;animation:sk 1.5s infinite;border-radius:10px}.sk-bar{height:60px}.sk-table{height:400px}@keyframes sk{0%{background-position:200% 0}100%{background-position:-200% 0}}
.action-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.page-title{margin:0;color:#1A3C6D}
.stats-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:20px}.stat-card{background:#fff;border-radius:12px;padding:20px;display:flex;align-items:center;gap:16px;box-shadow:0 2px 8px rgba(0,0,0,.06)}.stat-icon{font-size:32px}.stat-value{font-size:20px;font-weight:700;color:#1A3C6D}.stat-label{font-size:13px;color:#999}
.table-container{background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.06);overflow:hidden}.data-table{width:100%;border-collapse:collapse}.data-table th{padding:12px 16px;background:#fafafa;text-align:left;font-weight:600;color:#1A3C6D;border-bottom:2px solid #e8e8e8;font-size:14px}.data-table td{padding:12px 16px;border-bottom:1px solid #f0f0f0;font-size:14px}.data-table tr:hover{background:#f5f7fa}
.tag{padding:2px 8px;border-radius:4px;font-size:12px;background:#e6f7ff;color:#1890ff}
.status-badge{padding:4px 8px;border-radius:4px;font-size:12px}.status-running{background:#fff7e6;color:#fa8c16}.status-completed{background:#f6ffed;color:#52c41a}.status-failed{background:#fff2f0;color:#ff4d4f}
.actions{display:flex;gap:4px}.btn-icon{width:28px;height:28px;border:none;background:transparent;cursor:pointer;border-radius:4px;font-size:14px}.btn-icon:hover{background:#f0f0f0}.btn-icon:disabled{opacity:.4;cursor:not-allowed}.btn-danger:hover{background:#fff2f0}
.empty-state{text-align:center;padding:60px 20px;color:#999}.empty-icon{font-size:48px;margin-bottom:16px}
.msg{margin-top:12px;padding:8px 16px;background:#f0f9eb;color:#67C23A;border-radius:6px}
.btn-primary{padding:8px 16px;background:#C41E3A;color:#fff;border:none;border-radius:6px;cursor:pointer}
</style>
