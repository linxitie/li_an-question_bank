<template>
  <div class="memories-page">
    <div class="memories-head">
      <button class="back-btn" @click="goBack">‹ 返回</button>
      <div>
        <h1>🧠 长期记忆</h1>
        <p>联考小智记住的关于你的一切，可随时查看或删除</p>
      </div>
    </div>

    <div v-if="state.loading" class="empty">加载中…</div>
    <div v-else-if="state.memories.length === 0" class="empty">
      还没有记忆。完成画像问卷、生成学习计划、完成任务后，联考小智会慢慢了解你。
    </div>

    <div class="mem-list">
      <div v-for="m in state.memories" :key="m.memory_id" class="mem-card" :class="'t-' + (m.memory_type || 'other')">
        <div class="mem-top">
          <span class="mem-tag">{{ typeLabel(m.memory_type) }}</span>
          <span class="mem-time">{{ m.create_time ? m.create_time.slice(0, 10) : '' }}</span>
          <button class="del-btn" @click="del(m.memory_id)" title="删除该记忆">✕</button>
        </div>
        <div class="mem-content">{{ m.content }}</div>
        <div class="mem-src">来源：{{ sourceLabel(m.source) }}</div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive, onMounted } from 'vue';

  export default defineComponent({
    name: 'MemoriesView',
    setup() {
      const state = reactive({ loading: true, memories: [] });

      function typeLabel(t: string) {
        return { profile: '画像', milestone: '里程碑', study: '学情', other: '其他' }[t] || t;
      }
      function sourceLabel(s: string) {
        return { 'profile-auto': '画像问卷', 'milestone-auto': '自动里程碑', manual: '手动', system: '系统' }[s] || s || '—';
      }
      function goBack() {
        if (window.history.length > 1) window.history.back();
        else window.location.href = '/#/ai-assistant';
      }
      async function load() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/agent/memories');
          const d = await res.json();
          if (res.ok) state.memories = d.memories || [];
        } catch (e) { /* 空列表 */ }
        state.loading = false;
      }
      async function del(id: number) {
        if (!confirm('删除这条记忆？删除后对话中将不再引用。')) return;
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/agent/memory/' + id, { method: 'DELETE' });
          if (res.ok) state.memories = state.memories.filter((m) => m.memory_id !== id);
          else alert('删除失败');
        } catch (e) { alert('网络异常'); }
      }
      onMounted(load);
      return { state, typeLabel, sourceLabel, goBack, del };
    },
  });
</script>

<style scoped>
  .memories-page {
    max-width: 860px; margin: 0 auto; padding: 20px 16px 40px;
    font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }
  .memories-head { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }
  .back-btn {
    border: 1px solid #d8dee9; background: #fff; border-radius: 8px;
    padding: 6px 12px; font-size: 13px; cursor: pointer;
  }
  .memories-head h1 { font-size: 20px; margin: 0; }
  .memories-head p { margin: 4px 0 0; color: #667; font-size: 13px; }
  .empty { text-align: center; color: #889; padding: 60px 0; font-size: 14px; }
  .mem-list { display: flex; flex-direction: column; gap: 12px; }
  .mem-card {
    background: #fff; border: 1px solid #e5eaf1; border-radius: 12px;
    padding: 14px 16px; box-shadow: 0 1px 3px rgba(20,30,60,0.05);
  }
  .mem-card.t-milestone { border-left: 4px solid #f0a63a; }
  .mem-card.t-profile { border-left: 4px solid #3a7bd5; }
  .mem-top { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
  .mem-tag {
    font-size: 11px; font-weight: 600; padding: 2px 10px; border-radius: 999px;
    background: #eef2f8; color: #3a7bd5;
  }
  .mem-card.t-milestone .mem-tag { background: #fdf0dc; color: #b8791a; }
  .mem-time { font-size: 12px; color: #99a; }
  .del-btn {
    margin-left: auto; border: none; background: transparent; color: #cc4a4a;
    font-size: 13px; cursor: pointer; padding: 2px 6px; border-radius: 6px;
  }
  .del-btn:hover { background: #fdecec; }
  .mem-content { font-size: 14px; line-height: 1.6; color: #223; white-space: pre-wrap; }
  .mem-src { font-size: 12px; color: #99a; margin-top: 8px; }
</style>
