<template>
  <div class="teacher-messages">
    <TeacherNavHeader activeNav="messages" @logout="handleLogout" />

    <div class="page-content">
      <div class="toolbar">
        <select class="filter-select" v-model="filterType" @change="loadMessages">
          <option value="">全部类型</option>
          <option value="system">系统通知</option>
          <option value="approval">审批反馈</option>
          <option value="student">学生提问</option>
        </select>
        <div class="toolbar-spacer"></div>
        <span class="unread-info" v-if="unreadCount > 0">未读 {{ unreadCount }} 条</span>
        <button class="btn-sm" @click="markAllRead" v-if="unreadCount > 0">全部标记已读</button>
      </div>

      <div class="message-list" v-if="messages.length > 0">
        <div v-for="msg in messages" :key="msg.message_id"
          :class="['message-item', { unread: !msg.is_read }]"
          @click="markRead(msg)">
          <div class="msg-icon">{{ typeIcon(msg.message_type) }}</div>
          <div class="msg-body">
            <div class="msg-title">{{ msg.title }}</div>
            <div class="msg-content" v-if="msg.content">{{ msg.content }}</div>
            <div class="msg-time">{{ formatTime(msg.created_at) }}</div>
          </div>
          <div class="msg-status" v-if="!msg.is_read">
            <span class="unread-dot"></span>
          </div>
        </div>
      </div>
      <div v-else class="empty-state">
        <div class="empty-icon">💬</div>
        <div class="empty-text">暂无消息</div>
      </div>

      <div class="pagination" v-if="total > pageSize">
        <button class="btn-sm" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
        <span>第 {{ page }} / {{ totalPages }} 页 · 共 {{ total }} 条</span>
        <button class="btn-sm" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import TeacherNavHeader from './TeacherNavHeader.vue';

export default defineComponent({
  name: 'TeacherMessages',
  components: { TeacherNavHeader },
  setup() {
    const router = useRouter();
    const messages: any = ref([]);
    const filterType = ref('');
    const page = ref(1);
    const pageSize = 20;
    const total = ref(0);
    const unreadCount = ref(0);
    const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

    onMounted(async () => { await loadMessages(); });

    async function loadMessages() {
      const auth = (window as any).__VTJ_AUTH__;
      if (!auth) return;
      const params = new URLSearchParams();
      params.append('page', String(page.value));
      params.append('page_size', String(pageSize));
      if (filterType.value) params.append('message_type', filterType.value);
      try {
        const res = await auth.apiFetch(`/api/teacher/messages?${params.toString()}`);
        const data = await res.json();
        if (data.success) {
          messages.value = data.items || [];
          total.value = data.total || 0;
          unreadCount.value = data.unread_count || 0;
        }
      } catch (e) { console.error('加载消息失败:', e); }
    }

    async function markRead(msg: any) {
      if (msg.is_read) return;
      const auth = (window as any).__VTJ_AUTH__;
      try {
        await auth.apiFetch(`/api/teacher/messages/${msg.message_id}/read`, { method: 'PUT' });
        msg.is_read = true;
        unreadCount.value = Math.max(0, unreadCount.value - 1);
      } catch (e) { /* ignore */ }
    }

    async function markAllRead() {
      const auth = (window as any).__VTJ_AUTH__;
      try {
        await auth.apiFetch('/api/teacher/messages/read-all', { method: 'PUT' });
        messages.value.forEach((m: any) => m.is_read = true);
        unreadCount.value = 0;
      } catch (e) { /* ignore */ }
    }

    function typeIcon(type: string) {
      const map: Record<string, string> = { system: '📢', approval: '📋', student: '💬' };
      return map[type] || '📩';
    }

    function formatTime(t: string) { return t ? t.substring(0, 16).replace('T', ' ') : ''; }
    function changePage(p: number) { page.value = p; loadMessages(); }
    function handleLogout() { const auth = (window as any).__VTJ_AUTH__; if (auth) auth.logout(); router.push('/login'); }

    return { messages, filterType, page, pageSize, total, totalPages, unreadCount, loadMessages, markRead, markAllRead, typeIcon, formatTime, changePage, handleLogout };
  }
});
</script>

<style scoped>
.teacher-messages { min-height: 100vh; background: #F5F7FA; font-size: 15px; }
.page-content { max-width: 900px; margin: 0 auto; padding: 24px; }
.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 20px; }
.toolbar-spacer { flex: 1; }
.filter-select { padding: 8px 12px; border: 1px solid #d9d9d9; border-radius: 6px; font-size: 15px; }
.btn-sm { padding: 5px 12px; border: 1px solid #d9d9d9; background: #fff; border-radius: 4px; cursor: pointer; font-size: 13px; }
.btn-sm:hover { background: #f0f0f0; }
.btn-sm:disabled { opacity: 0.5; cursor: not-allowed; }
.unread-info { color: #F56C6C; font-weight: 600; font-size: 14px; }
.message-list { background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow: hidden; }
.message-item { display: flex; gap: 14px; padding: 16px 20px; border-bottom: 1px solid #f0f0f0; cursor: pointer; transition: background 0.2s; }
.message-item:hover { background: #f9fafb; }
.message-item.unread { background: #f0f7ff; }
.msg-icon { font-size: 24px; flex-shrink: 0; }
.msg-body { flex: 1; min-width: 0; }
.msg-title { font-weight: 600; color: #1A3C6D; margin-bottom: 4px; }
.msg-content { color: #666; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.msg-time { color: #aaa; font-size: 12px; margin-top: 4px; }
.msg-status { flex-shrink: 0; display: flex; align-items: center; }
.unread-dot { width: 8px; height: 8px; background: #F56C6C; border-radius: 50%; }
.empty-state { text-align: center; padding: 60px 0; }
.empty-icon { font-size: 48px; margin-bottom: 12px; }
.empty-text { color: #999; font-size: 16px; }
.pagination { display: flex; gap: 12px; align-items: center; justify-content: center; margin-top: 16px; }
</style>
