<template>
  <div class="kg-page">
    <header class="kg-head">
      <div>
        <h1>我的知识图谱</h1>
        <p class="kg-sub">
          节点大小 = 生长热度，颜色区分知识点；图谱只反映你自己的学习轨迹。
        </p>
      </div>
      <div class="kg-actions">
        <button class="kg-btn" :class="{ on: mode === 'mine' }" @click="mode = 'mine'; panelRef?.loadAll()">我的图谱</button>
        <button class="kg-btn" :class="{ on: mode === 'global' }" @click="mode = 'global'; panelRef?.loadAll()">全局图谱</button>
        <button class="kg-btn" :disabled="generating" @click="generateTasks">
          {{ generating ? '生成中…' : '生成本周个性化任务' }}
        </button>
        <button class="kg-btn" :class="{ on: view === '3d' }" @click="view = view === '3d' ? '2d' : '3d'">
          {{ view === '3d' ? '2D 视图' : '3D 星图' }}
        </button>
        <button class="kg-btn" @click="panelRef?.loadAll()">刷新</button>
      </div>
    </header>

    <div v-if="view === '3d'" class="kg-stage">
      <ForceGraph3D @select="onNodeSelect" />
      <aside v-if="selected" class="kg-panel">
        <header class="kg-panel__head">
          <span class="kg-panel__name">{{ selected.name }}</span>
          <button class="kg-panel__close" @click="selected = null">×</button>
        </header>
        <p class="kg-panel__meta">关联考点 {{ selected.degree }} 个</p>
        <div class="kg-panel__chips">
          <button v-for="n in selected.neighbors" :key="n.rel + n.id"
                  class="kg-chip" :class="'rel-' + n.rel"
                  :title="relLabel(n.rel)"
                  @click="selected = { id: n.id, name: n.name, degree: 0, neighbors: [] }">
            {{ n.name }}
          </button>
        </div>
      </aside>
    </div>
    <KnowledgeGraphPanel v-else ref="panelRef" :mode="mode" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import KnowledgeGraphPanel from '@/components/kg/KnowledgeGraphPanel.vue';
import ForceGraph3D from '@/components/kg/ForceGraph3D.vue';

const panelRef = ref<InstanceType<typeof KnowledgeGraphPanel> | null>(null);
const generating = ref(false);
const mode = ref<'mine' | 'global'>('mine');
const view = ref<'2d' | '3d'>('3d');

interface KgNodePick {
  id: number | string;
  name: string;
  degree: number;
  neighbors: { id: number | string; name: string; rel?: string }[];
}

/** 3D 图谱下钻：点击节点后展示它的一跳邻居 */
const selected = ref<KgNodePick | null>(null);

function onNodeSelect(node: any): void {
  selected.value = {
    id: node?.id,
    name: String(node?.name || '考点'),
    degree: Number(node?.degree || 0),
    neighbors: node?.neighbors || []
  };
}

function relLabel(rel?: string): string {
  if (rel === 'contains') return '包含';
  if (rel === 'prerequisite_of') return '前置';
  if (rel === 'confusable') return '易混';
  return '关联';
}

function apiFetch(url: string, init?: RequestInit): Promise<Response> {
  const auth = (window as any).__VTJ_AUTH__;
  if (auth && typeof auth.apiFetch === 'function') return auth.apiFetch(url, init);
  return fetch(url, { credentials: 'include', ...(init || {}) });
}

async function generateTasks(): Promise<void> {
  generating.value = true;
  try {
    const res = await apiFetch('/api/knowledge/kg/generate?n=2', { method: 'POST' });
    const body = await res.json();
    ElMessage.success(`已生成 ${body.created ?? 0} 个个性化任务`);
    await panelRef.value?.loadAll();
  } catch (e: any) {
    ElMessage.error(e?.message || '生成失败');
  } finally {
    generating.value = false;
  }
}
</script>

<style scoped>
.kg-stage { position: relative; }
.kg-panel { position: absolute; right: 16px; top: 16px; width: 240px; max-height: 70%; overflow: auto; background: rgba(255,255,255,.96); border: 1px solid #e8ecf4; border-radius: 12px; padding: 14px; box-shadow: 0 8px 28px rgba(17,24,39,.14); }
.kg-panel__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.kg-panel__name { font-size: 13.5px; font-weight: 700; color: #1a2b5f; }
.kg-panel__close { border: none; background: none; color: #9aa0aa; cursor: pointer; font-size: 15px; line-height: 1; }
.kg-panel__meta { margin: 6px 0 10px; font-size: 11px; color: #8a8faa; }
.kg-panel__chips { display: flex; flex-wrap: wrap; gap: 6px; }
.kg-chip { border: 1px solid #e3e6ec; background: #fff; border-radius: 999px; padding: 4px 10px; font-size: 11.5px; color: #4b5563; cursor: pointer; }
.kg-chip:hover { border-color: #4d6bfe; color: #3b5bdb; }
.kg-chip.rel-prerequisite_of { border-color: #fde68a; background: #fffdf5; }
.kg-chip.rel-confusable { border-color: #fbd5db; background: #fff7f8; }
.kg-page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px 20px 48px;
  font-family: 'Noto Sans SC', 'PingFang SC', system-ui, sans-serif;
  color: #1a1a1a;
}
.kg-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.kg-head h1 {
  margin: 0 0 6px;
  font-size: 24px;
  font-weight: 600;
}
.kg-sub {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
  line-height: 1.6;
}
.kg-actions {
  display: flex;
  gap: 8px;
}
.kg-btn {
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1d4ed8;
  border-radius: 10px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.kg-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.kg-btn.on { background: #1a365d; color: #fff; border-color: #1a365d; }

/* 移动端适配：按钮不能竖排，标题与操作区分行 */
.kg-btn { white-space: nowrap; writing-mode: horizontal-tb; }
@media (max-width: 900px) {
  .kg-head { flex-direction: column; align-items: flex-start; gap: 12px; }
  .kg-head h1 { font-size: 20px; line-height: 1.3; }
  .kg-actions { flex-wrap: wrap; width: 100%; }
  .kg-btn { flex: 0 0 auto; padding: 7px 12px; font-size: 12px; }
  .kg-stage .kg-panel { position: static; width: auto; margin-top: 12px; max-height: none; }
}
</style>