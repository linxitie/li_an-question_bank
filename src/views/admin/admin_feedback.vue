<template>
  <div class="fb-page">
    <header class="fb-hd">
      <h2>问题反馈</h2>
      <span class="fb-sub">用户通过论坛/平板「反馈」按钮提交的问题</span>
      <div class="fb-tools">
        <select v-model="status" @change="reload">
          <option value="">全部状态</option>
          <option value="pending">待处理</option>
          <option value="replied">已回复</option>
          <option value="resolved">已解决</option>
        </select>
        <button class="fb-btn" :disabled="loading" @click="reload">刷新</button>
      </div>
    </header>

    <div v-if="loading" class="fb-empty">加载中…</div>
    <div v-else-if="!items.length" class="fb-empty">暂无反馈</div>
    <table v-else class="fb-table">
      <thead>
        <tr>
          <th style="width:150px">时间</th>
          <th style="width:110px">作者</th>
          <th style="width:90px">分类</th>
          <th>内容</th>
          <th style="width:90px">状态</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="f in items" :key="f.feedback_id" class="row" @click="openDetail(f.feedback_id)">
          <td class="nowrap">{{ formatTime(f.created_at) }}</td>
          <td>{{ f.user_name || '匿名' }}</td>
          <td>{{ f.category }}</td>
          <td class="content">
            <div class="text">{{ f.content }}</div>
            <div v-if="f.attachments && f.attachments.length" class="att">📎 {{ f.attachments.length }} 个附件</div>
          </td>
          <td><span :class="['pill', f.status]">{{ statusLabel(f.status) }}</span></td>
        </tr>
      </tbody>
    </table>

    <div v-if="detailVisible && detail" class="fb-mask" @click.self="closeDetail">
      <div class="fb-modal">
        <header class="fb-modal-hd">
          <h3>问题反馈详情</h3>
          <button class="fb-x" @click="closeDetail">×</button>
        </header>
        <div class="fb-modal-bd">
          <p class="fb-meta">
            作者：{{ detail.user_name || '匿名' }}
            <span v-if="detail.is_anonymous" class="fb-anon-tag">匿名</span>
            · {{ formatTime(detail.created_at) }}
            · {{ detail.category }}
            · <span :class="['pill', detail.status]">{{ statusLabel(detail.status) }}</span>
          </p>
          <p class="fb-detail-content">{{ detail.content }}</p>
          <p v-if="detail.attachments && detail.attachments.length" class="att">📎 {{ detail.attachments.length }} 个附件</p>
          <div v-if="detail.replies && detail.replies.length" class="fb-replies">
            <h4>历史回复</h4>
            <div v-for="r in detail.replies" :key="r.reply_id" class="fb-reply">
              <span class="fb-reply-time">{{ formatTime(r.created_at) }}</span>
              <span>{{ r.content }}</span>
            </div>
          </div>
          <textarea v-model="replyText" rows="4" maxlength="1000" placeholder="回复反馈人…"></textarea>
          <div class="fb-modal-ft">
            <button class="fb-btn" @click="closeDetail">关闭</button>
            <button class="fb-btn primary" :disabled="!replyText.trim() || replySubmitting" @click="submitReply">
              {{ replySubmitting ? '发送中…' : '发送回复' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <footer class="fb-ft">
      <span>共 {{ total }} 条</span>
      <button class="fb-btn" :disabled="page <= 1" @click="go(page - 1)">上一页</button>
      <span>{{ page }} / {{ totalPages }}</span>
      <button class="fb-btn" :disabled="page >= totalPages" @click="go(page + 1)">下一页</button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

const items = ref<any[]>([]);
const total = ref(0);
const page = ref(1);
const pageSize = 20;
const status = ref('');
const loading = ref(false);
const route = useRoute();
const detailVisible = ref(false);
const detail = ref<any>(null);
const replyText = ref('');
const replySubmitting = ref(false);

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

function formatTime(v: string | null) {
  if (!v) return '-';
  return String(v).replace('T', ' ').slice(0, 16);
}

function statusLabel(s: string) {
  const map: Record<string, string> = {
    pending: '待处理', claimed: '处理中', replied: '已回复', resolved: '已解决', rejected: '已驳回'
  };
  return map[s] || s;
}

async function load() {
  loading.value = true;
  try {
    const qs = new URLSearchParams({ page: String(page.value), page_size: String(pageSize) });
    if (status.value) qs.set('status', status.value);
    const res = await window.__VTJ_AUTH__.apiFetch('/api/admin/feedback?' + qs.toString());
    const data = await res.json();
    if (res.ok) {
      items.value = data.items || [];
      total.value = data.total || 0;
    }
  } finally {
    loading.value = false;
  }
}

async function openDetail(id: number) {
  try {
    const res = await window.__VTJ_AUTH__.apiFetch('/api/admin/feedback/' + id);
    const data = await res.json();
    if (res.ok) {
      detail.value = data;
      detailVisible.value = true;
      replyText.value = '';
    }
  } catch {
    /* 忽略 */
  }
}
function closeDetail() {
  detailVisible.value = false;
}
async function submitReply() {
  if (!detail.value || !replyText.value.trim()) return;
  replySubmitting.value = true;
  try {
    const res = await window.__VTJ_AUTH__.apiFetch('/api/admin/feedback/' + detail.value.feedback_id + '/reply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reply: replyText.value.trim() })
    });
    if (res.ok) {
      replyText.value = '';
      await openDetail(detail.value.feedback_id);
      await load();
    }
  } finally {
    replySubmitting.value = false;
  }
}
function reload() { page.value = 1; load(); }
function go(p: number) { page.value = p; load(); }
onMounted(async () => {
  await load();
  const openId = Number(route.query.open || 0);
  if (openId) await openDetail(openId);
});

// 已在反馈页时，从铃铛再点一条通知也要能重新打开弹窗
watch(
  () => route.query.open,
  (v) => {
    const id = Number(v || 0);
    if (id) openDetail(id);
  }
);
</script>

<style scoped>
.fb-page { padding: 20px 24px; }
.fb-hd { display: flex; align-items: baseline; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; }
.fb-hd h2 { margin: 0; font-size: 20px; color: #1a2b5f; }
.fb-sub { color: #8a8faa; font-size: 12px; }
.fb-tools { margin-left: auto; display: flex; gap: 8px; }
.fb-tools select { border: 1px solid #dfe3ee; border-radius: 8px; padding: 6px 10px; }
.fb-btn { border: 1px solid #dfe3ee; background: #fff; border-radius: 8px; padding: 6px 14px; cursor: pointer; }
.fb-table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 12px; overflow: hidden; }
.fb-table th, .fb-table td { padding: 10px 12px; border-bottom: 1px solid #f0f2f7; text-align: left; font-size: 13px; vertical-align: top; }
.fb-table th { background: #f7f9fd; color: #5a6488; font-weight: 600; }
.nowrap { white-space: nowrap; color: #6b7896; }
.content .text { color: #333; white-space: pre-wrap; word-break: break-word; }
.att { color: #8a8faa; font-size: 12px; margin-top: 4px; }
.pill { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 12px; background: #eef1f8; color: #5a6488; }
.pill.pending { background: #fff4e5; color: #b45309; }
.pill.replied { background: #e8f4ff; color: #1d4ed8; }
.pill.resolved { background: #e9f9ef; color: #1e7b3c; }
.fb-empty { padding: 40px; text-align: center; color: #8a8faa; }
.fb-ft { display: flex; align-items: center; gap: 10px; justify-content: flex-end; margin-top: 12px; color: #6b7896; font-size: 13px; }
.row { cursor: pointer; }
.row:hover td { background: #f7f9fd; }
.fb-mask { position: fixed; inset: 0; z-index: 2200; background: rgba(12,26,44,.45); display: flex; align-items: center; justify-content: center; }
.fb-modal { width: 720px; max-width: 94vw; max-height: 88vh; background: #fff; border-radius: 14px; display: flex; flex-direction: column; overflow: hidden; }
.fb-modal-hd { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid #f0f2f7; }
.fb-modal-hd h3 { margin: 0; font-size: 16px; color: #1a2b5f; }
.fb-x { border: 0; background: transparent; font-size: 20px; color: #8a8faa; cursor: pointer; }
.fb-modal-bd { padding: 16px 18px; overflow-y: auto; }
.fb-meta { color: #6b7896; font-size: 13px; margin: 0 0 10px; }
.fb-anon-tag { background: #eef1f8; border-radius: 6px; padding: 1px 6px; margin: 0 4px; }
.fb-detail-content { white-space: pre-wrap; word-break: break-word; font-size: 14px; color: #29324a; }
.fb-replies { margin: 12px 0; border-top: 1px dashed #e6ebf3; padding-top: 10px; }
.fb-replies h4 { margin: 0 0 8px; font-size: 13px; color: #5a6488; }
.fb-reply { display: grid; grid-template-columns: 120px 1fr; gap: 8px; font-size: 13px; color: #333; margin-bottom: 6px; }
.fb-reply-time { color: #8a8faa; }
.fb-modal-bd textarea { width: 100%; box-sizing: border-box; border: 1px solid #dfe3ee; border-radius: 10px; padding: 10px 12px; font-size: 14px; resize: vertical; font-family: inherit; }
.fb-modal-ft { display: flex; justify-content: flex-end; gap: 10px; margin-top: 12px; }
.fb-btn.primary { background: #2563eb; color: #fff; border-color: #2563eb; }
</style>
