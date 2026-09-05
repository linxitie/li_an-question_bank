<template>
  <div class="admin-content">
    <div v-if="loading" class="skeleton-wrap"><div class="sk-bar"></div><div class="sk-table"></div></div>
    <div v-else>
      <div class="action-bar"><h2 class="page-title">📝 试卷审批</h2>
        <div class="action-buttons"><button class="btn-refresh" @click="load">🔄 刷新</button></div>
      </div>
      <div class="filter-bar">
        <input class="filter-input" v-model="kw" placeholder="搜索试卷名称或教师姓名" @keyup.enter="load"/>
        <select class="filter-select" v-model="fstatus" @change="load"><option value="">全部状态</option><option value="pending">待审批</option><option value="approved">已批准</option><option value="rejected">已驳回</option></select>
        <select class="filter-select" v-model="fsubject" @change="load"><option value="">全部科目</option><option :value="1">行测</option><option :value="2">申论</option><option :value="3">公专</option></select>
        <button class="btn-search" @click="load">🔍 搜索</button>
      </div>
      <div class="table-container">
        <table class="data-table"><thead><tr><th>试卷名称</th><th>提交教师</th><th>科目</th><th>题数</th><th>总分</th><th>提交时间</th><th>审批状态</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="p in items" :key="p.paper_id">
            <td><a class="lnk" @click="openDetail(p.paper_id)">{{ p.paper_name }}</a></td>
            <td>{{ p.creator_name || '-' }}</td><td>{{ p.subject_name || '-' }}</td><td>{{ p.question_count }}</td><td>{{ p.total_score }}</td>
            <td>{{ formatTime(p.submit_time || p.create_time) }}</td>
            <td><span :class="statusClass(p.approval_status)">{{ statusLabel(p.approval_status) }}</span>
              <div v-if="p.approval_status === 'rejected' && p.approval_opinion" class="rej-reason">{{ p.approval_opinion }}</div>
            </td>
            <td class="actions">
              <button class="btn-icon" @click="openDetail(p.paper_id)">👁️</button>
              <button class="btn-icon btn-success" v-if="p.approval_status === 'pending'" @click="doApprove(p.paper_id)">✅</button>
              <button class="btn-icon btn-danger" v-if="p.approval_status === 'pending'" @click="openReject(p.paper_id)">❌</button>
            </td>
          </tr>
        </tbody></table>
        <div v-if="!items.length" class="empty-state"><div class="empty-icon">📝</div><div>暂无审批记录</div></div>
      </div>
    </div>

    <!-- 详情弹层 -->
    <div class="modal-overlay" v-if="showDetail" @click.self="closeDetail">
      <div class="modal-content detail-modal">
        <div class="modal-head"><h3>试卷详情</h3><button class="btn-x" @click="closeDetail">✕</button></div>
        <div v-if="detail.paper" class="info-card">
          <div class="info-row"><span class="il">试卷名称</span><span class="iv">{{ detail.paper.paper_name }}</span></div>
          <div class="info-row"><span class="il">提交教师</span><span class="iv">{{ detail.paper.creator_name }}（{{ detail.paper.creator_no || '-' }}）</span></div>
          <div class="info-row"><span class="il">科目</span><span class="iv">{{ detail.paper.subject_name }}</span></div>
          <div class="info-row"><span class="il">题数 / 总分</span><span class="iv">{{ detail.paper.question_count }} 题 / {{ detail.paper.total_score }} 分</span></div>
          <div class="info-row"><span class="il">当前状态</span><span class="iv"><span :class="statusClass(statusOf(detail.paper.paper_type))">{{ statusLabel(statusOf(detail.paper.paper_type)) }}</span></span></div>
        </div>
        <div class="issue-summary" v-if="detail.issues && detail.issues.length">⚠️ 检测到 {{ detail.issues.length }} 个问题（{{ errorCount() }} 错误 / {{ warnCount() }} 警告）</div>
        <div class="q-list">
          <div v-for="q in detail.questions" :key="q.question_id" :class="['q-item', issueLevel(q.question_id)]">
            <div class="q-head"><span class="q-no">第 {{ q.question_no }} 题</span><span class="q-type">{{ q.type_name || '-' }}</span><span class="q-score">{{ q.score }} 分</span></div>
            <div class="q-content">{{ q.question_content }}</div>
            <div class="q-answer">答案：{{ q.answer || '（无）' }}</div>
            <div v-for="(iss, i) in issuesOf(q.question_id)" :key="i" :class="['issue-tag', iss.severity]">{{ iss.description }}</div>
          </div>
        </div>

        <div class="log-box" v-if="logs.length">
          <h4>审批日志</h4>
          <div v-for="l in logs" :key="l.workflow_id" class="log-item">
            <span :class="['log-dot', l.status]"></span>
            <span class="log-t">{{ formatTime(l.submit_time) }}</span>
            <span class="log-s">{{ {pending:'待审批', approved:'已通过', rejected:'已驳回'}[l.status] || l.status }}</span>
            <span class="log-o">{{ l.opinion }}</span>
            <span class="log-who">{{ l.approver_name || l.submitter_name }}</span>
          </div>
        </div>

        <div class="action-bar" v-if="detail.paper && detail.paper.paper_type === 'PENDING'">
          <textarea class="opinion" v-model="opinion" placeholder="审批意见（驳回时必填）"></textarea>
          <div class="ab-btns">
            <button class="btn ok-btn" @click="doApprove(detail.paper.paper_id)">✅ 通过并发布</button>
            <button class="btn bad-btn" @click="doReject(detail.paper.paper_id)">❌ 驳回</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, ref, onMounted } from 'vue';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'PaperApproval',
  setup() {
    const provider = useProvider({ id: 'paper_approval', version: '1' });
    const kw = ref('');
    const fstatus = ref('');
    const fsubject = ref('');
    const items: any = ref([]);
    const showDetail = ref(false);
    const detail: any = ref({});
    const logs: any = ref([]);
    const opinion = ref('');
    const loading = ref(true);

    const auth = () => (window as any).__VTJ_AUTH__;

    function statusLabel(s: string) {
      return ({ pending: '待审批', approved: '已批准', rejected: '已驳回', draft: '草稿', other: '其他' } as any)[s] || s || '-';
    }
    function statusClass(s: string) {
      return 'tag ' + ({ pending: 'tag-orange', approved: 'tag-green', rejected: 'tag-red', draft: 'tag-gray', other: 'tag-gray' } as any)[s || 'other'];
    }
    function statusOf(paper_type: string) {
      if (paper_type === 'PENDING') return 'pending';
      if (paper_type === 'APPROVED' || paper_type === 'PUBLISHED') return 'approved';
      if (paper_type === 'DRAFT') return 'rejected';
      return 'other';
    }
    function formatTime(t: string) {
      if (!t) return '-';
      const d = new Date(t);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
    }
    function issuesOf(qid: number) {
      return (detail.value.issues || []).filter((i: any) => i.question_id === qid);
    }
    function issueLevel(qid: number) {
      const iss = issuesOf(qid);
      if (!iss.length) return '';
      return iss.some((i: any) => i.severity === 'error') ? 'q-has-error' : 'q-has-warn';
    }
    function errorCount() {
      return (detail.value.issues || []).filter((i: any) => i.severity === 'error').length;
    }
    function warnCount() {
      return (detail.value.issues || []).filter((i: any) => i.severity === 'warn').length;
    }

    async function load() {
      loading.value = true;
      const p = new URLSearchParams();
      if (kw.value) p.append('keyword', kw.value);
      if (fstatus.value) p.append('status', fstatus.value);
      if (fsubject.value) p.append('subject_id', fsubject.value);
      const r = await auth().apiFetch('/api/admin/approval/papers?' + p.toString());
      const d = await r.json();
      if (d.success) items.value = d.items || [];
      loading.value = false;
    }

    async function openDetail(id: number) {
      opinion.value = '';
      const r = await auth().apiFetch(`/api/admin/approval/papers/${id}`);
      const d = await r.json();
      if (d.success) detail.value = d;
      const lr = await auth().apiFetch(`/api/admin/approval/papers/${id}/logs`);
      const ld = await lr.json();
      if (ld.success) logs.value = ld.items || [];
      showDetail.value = true;
    }
    function closeDetail() { showDetail.value = false; }

    function openReject(id: number) { openDetail(id); }

    async function doApprove(id: number) {
      if (!confirm('确认通过并发布该试卷？')) return;
      const r = await auth().apiFetch(`/api/admin/approval/papers/${id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ opinion: opinion.value || '' })
      });
      const d = await r.json();
      if (d.success) { alert('已通过并发布'); closeDetail(); load(); }
      else { alert(d.detail || d.message || '操作失败'); }
    }

    async function doReject(id: number) {
      if (!opinion.value.trim()) { alert('请填写驳回理由'); return; }
      const r = await auth().apiFetch(`/api/admin/approval/papers/${id}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ opinion: opinion.value.trim() })
      });
      const d = await r.json();
      if (d.success) { alert('已驳回'); closeDetail(); load(); }
      else { alert(d.detail || d.message || '操作失败'); }
    }

    onMounted(load);

    return {
      provider, loading, kw, fstatus, fsubject, items, showDetail, detail, logs, opinion,
      load, openDetail, closeDetail, openReject, doApprove, doReject,
      statusLabel, statusClass, statusOf, formatTime, issuesOf, issueLevel, errorCount, warnCount
    };
  }
});
</script>

<style scoped>
.admin-content{padding:20px}
.skeleton-wrap{display:flex;flex-direction:column;gap:20px}.sk-bar,.sk-table{background:linear-gradient(90deg,#f0f0f0 25%,#e0e0e0 50%,#f0f0f0 75%);background-size:200% 100%;animation:sk 1.5s infinite;border-radius:10px}.sk-bar{height:60px}.sk-table{height:400px}
@keyframes sk{0%{background-position:200% 0}100%{background-position:-200% 0}}
.action-bar{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.page-title{margin:0;color:#1A3C6D}.btn-refresh{padding:8px 16px;background:#fff;border:1px solid #d9d9d9;border-radius:6px;cursor:pointer}
.filter-bar{display:flex;gap:10px;margin-bottom:20px}.filter-input{padding:8px 12px;border:1px solid #d9d9d9;border-radius:6px;flex:1}.filter-select{padding:8px 12px;border:1px solid #d9d9d9;border-radius:6px}.btn-search{padding:8px 18px;background:#1A3C6D;color:#fff;border:none;border-radius:6px;cursor:pointer}
.table-container{background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.06);overflow:hidden}.data-table{width:100%;border-collapse:collapse}.data-table th{padding:12px 16px;background:#fafafa;text-align:left;font-weight:600;color:#1A3C6D;border-bottom:2px solid #e8e8e8;font-size:14px}.data-table td{padding:12px 16px;border-bottom:1px solid #f0f0f0;font-size:14px}.data-table tr:hover{background:#f5f7fa}
.lnk{color:#1A3C6D;cursor:pointer;text-decoration:underline}.rej-reason{font-size:12px;color:#f56c6c;margin-top:4px}
.actions{display:flex;gap:4px}.btn-icon{width:28px;height:28px;border:none;background:transparent;cursor:pointer;border-radius:4px;font-size:14px}.btn-icon:hover{background:#f0f0f0}.btn-success{color:#52c41a}.btn-danger{color:#ff4d4f}
.empty-state{text-align:center;padding:60px 20px;color:#999}.empty-icon{font-size:48px;margin-bottom:16px}
.tag{padding:2px 10px;border-radius:10px;font-size:12px;display:inline-block}.tag-orange{background:#fdf6ec;color:#e6a23c}.tag-green{background:#f0f9eb;color:#67c23a}.tag-red{background:#fef0f0;color:#f56c6c}.tag-gray{background:#f4f4f5;color:#909399}
.modal-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;z-index:1000}.modal-content{background:#fff;border-radius:12px;width:90%;max-width:800px;max-height:85vh;overflow-y:auto;padding:24px}.modal-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.modal-head h3{margin:0;color:#1A3C6D}.btn-x{border:none;background:transparent;font-size:20px;cursor:pointer}
.info-card{background:#f8f9fa;border-radius:8px;padding:16px;margin-bottom:16px}.info-row{display:flex;padding:6px 0}.il{width:120px;color:#999;font-size:13px}.iv{flex:1;font-size:14px;color:#333}
.issue-summary{padding:8px 16px;background:#fff7e6;border-radius:6px;margin-bottom:16px;color:#fa8c16;font-size:13px}
.q-list{display:flex;flex-direction:column;gap:12px}.q-item{padding:12px;border-radius:8px;border:1px solid #e8e8e8}.q-has-error{border-color:#ff4d4f;background:#fff2f0}.q-has-warn{border-color:#faad14;background:#fffbe6}
.q-head{display:flex;gap:12px;align-items:center;margin-bottom:8px}.q-no{font-weight:600;color:#1A3C6D}.q-type{font-size:12px;color:#999;background:#f5f7fa;padding:2px 8px;border-radius:4px}.q-score{font-size:12px;color:#52c41a}
.q-content{font-size:13px;color:#333;margin-bottom:4px;line-height:1.6}.q-answer{font-size:12px;color:#666}
.issue-tag{font-size:12px;padding:4px 8px;border-radius:4px;margin-top:6px;display:inline-block}.issue-tag.error{background:#fff2f0;color:#ff4d4f}.issue-tag.warn{background:#fffbe6;color:#faad14}
.log-box{margin-top:16px}.log-box h4{margin:0 0 12px;color:#1A3C6D;font-size:14px}.log-item{display:flex;gap:8px;align-items:center;padding:6px 0;border-bottom:1px solid #f0f0f0;font-size:13px}.log-dot{width:8px;height:8px;border-radius:50%}.log-dot.pending{background:#fa8c16}.log-dot.approved{background:#52c41a}.log-dot.rejected{background:#ff4d4f}.log-t{color:#999}.log-s{font-weight:600}.log-o{color:#666;flex:1}.log-who{color:#999}
.detail-modal .action-bar{display:flex;flex-direction:column;gap:12px}.opinion{width:100%;min-height:80px;padding:10px;border:1px solid #d9d9d9;border-radius:6px;resize:vertical;font-size:14px}.ab-btns{display:flex;gap:10px}.ok-btn{background:#52c41a;color:#fff;border:none;padding:8px 20px;border-radius:6px;cursor:pointer}.bad-btn{background:#ff4d4f;color:#fff;border:none;padding:8px 20px;border-radius:6px;cursor:pointer}
</style>
