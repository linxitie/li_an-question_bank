<template>
  <div class="kb-page">
    <!-- 顶栏 -->
    <div class="kb-top">
      <button class="kb-back" @click="goBack"><span>‹</span></button>
      <div class="kb-title">知识库 · Obsidian 自生长</div>
      <div class="kb-sub">法条 / 报考 / 考点 / 错题 · 提交 → 审批 → 入库</div>
    </div>

    <div class="kb-body">
      <!-- 分类与状态切换 -->
      <div class="kb-tabs">
        <span
          v-for="c in catTabs"
          :key="c.key"
          class="kb-tab"
          :class="{ active: state.category === c.key }"
          @click="switchCat(c.key)"
        >{{ c.name }}</span>
      </div>
      <div class="kb-status">
        <span
          v-for="s in statusTabs"
          :key="s.key"
          class="kb-st"
          :class="{ active: state.status === s.key }"
          @click="switchStatus(s.key)"
        >{{ s.name }}</span>
      </div>

      <!-- 提交表单 -->
      <div class="kb-submit">
        <div class="kb-submit-head">
          <span>➕ 提交新知识（待审批入库）</span>
          <button class="kb-btn ghost" :disabled="state.importing" @click="importVault()">
            {{ state.importing ? '导入中…' : '📥 从 Vault 导入' }}
          </button>
        </div>
        <div v-if="state.importMsg" class="import-msg">{{ state.importMsg }}</div>
        <div class="kb-form">
          <input v-model="state.form.title" class="kb-input" placeholder="标题（2-200字）" />
          <select v-model="state.form.category" class="kb-input kb-sel">
            <option v-for="c in catTabs" :key="c.key" :value="c.key">{{ c.name }}</option>
          </select>
          <textarea v-model="state.form.content" class="kb-input kb-area" rows="3" placeholder="内容（Markdown，≥5字）"></textarea>
          <button class="kb-btn primary" :disabled="state.submitting" @click="submitNode()">
            {{ state.submitting ? '提交中…' : '提交待审批' }}
          </button>
        </div>
      </div>

      <!-- 图谱视图 -->
      <div v-if="state.view === 'graph'" class="kb-graph">
        <svg :viewBox="'0 0 640 320'" class="kb-svg">
          <line
            v-for="(r, i) in graphRels"
            :key="'l' + i"
            :x1="nodePos(r.from).x" :y1="nodePos(r.from).y"
            :x2="nodePos(r.to).x" :y2="nodePos(r.to).y"
            stroke="#8aa0c8" stroke-width="1" stroke-dasharray="4 3"
          />
          <g v-for="(n, i) in graphNodes" :key="'n' + i">
            <circle :cx="nodePos(n.node_id).x" :cy="nodePos(n.node_id).y" r="22" fill="#1a2a4a" opacity="0.92" />
            <text :x="nodePos(n.node_id).x" :y="nodePos(n.node_id).y" text-anchor="middle" dominant-baseline="central"
              fill="#fff" font-size="11">{{ catShort(n.category) }}</text>
            <text :x="nodePos(n.node_id).x" :y="nodePos(n.node_id).y + 34" text-anchor="middle" font-size="10" fill="#334" class="kb-node-title">{{ shortTitle(n.title) }}</text>
          </g>
        </svg>
        <div v-if="graphNodes.length === 0" class="kb-empty">图谱为空：先把笔记提交并通过审批</div>

        <!-- 关系管理：自动推荐 + 关系列表 -->
        <div class="kb-rel-panel">
          <div class="kb-rel-head">
            <span>关系管理</span>
            <button class="kb-btn mini ok" @click="suggestRelations" :disabled="state.suggesting">💡 推荐关系{{ state.suggesting ? '…' : '' }}</button>
          </div>
          <div v-if="state.suggestions.length" class="kb-rel-sugs">
            <div v-for="(s, i) in state.suggestions" :key="'s' + i" class="kb-rel-sug">
              <span class="kb-rel-line">{{ s.from_title }} → {{ s.to_title }}</span>
              <button class="kb-btn mini ok" @click="addRelation(s)">添加</button>
            </div>
          </div>
          <div v-if="state.relList.length" class="kb-rel-list">
            <div v-for="(r, i) in state.relList" :key="'r' + i" class="kb-rel-item">
              <span class="kb-rel-line">{{ r.from_title }} → {{ r.to_title }} <em class="kb-rel-type">{{ r.type }}</em></span>
              <button class="kb-btn mini no" @click="delRelation(r)">删除</button>
            </div>
          </div>
          <div v-else-if="!state.suggestions.length" class="kb-rel-empty">暂无关系：点“推荐关系”自动发现，或手动添加（开发中）</div>
        </div>
      </div>

      <!-- 节点列表 -->
      <div v-else class="kb-list">
        <div v-if="state.loading" class="kb-empty">加载中…</div>
        <div v-else-if="state.nodes.length === 0" class="kb-empty">暂无节点（切换分类或状态试试）</div>
        <div v-for="n in state.nodes" :key="n.node_id" class="kb-card" :class="{ pending: n.status === 'pending' }">
          <div class="kb-card-head">
            <span class="kb-card-title">{{ n.title }}</span>
            <span class="kb-card-tag" :class="n.category">{{ n.category_name }}</span>
            <span class="kb-card-st" :class="n.status">{{ n.status === 'approved' ? '已入库' : '待审批' }}</span>
          </div>
          <div class="kb-card-body">{{ n.content }}</div>
          <div class="kb-card-foot">
            <span class="kb-card-src" v-if="n.source">来源：{{ n.source }}</span>
            <span class="kb-card-time" v-if="n.update_time">{{ fmtTime(n.update_time) }}</span>
            <span class="kb-card-ops">
              <button v-if="n.status === 'pending'" class="kb-btn mini ok" @click="approveNode(n)">通过入库</button>
              <button v-if="n.status === 'pending'" class="kb-btn mini no" @click="rejectNode(n)">驳回</button>
            </span>
          </div>
        </div>
      </div>

      <div v-if="state.notice" class="kb-notice">{{ state.notice }}</div>
    </div>
  </div>
</template>

<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive, onMounted, computed } from 'vue';
  import { useProvider } from '@vtj/renderer';

  export default defineComponent({
    name: 'KnowledgeView',
    setup() {
      const provider = useProvider({ id: 'knowledge_view', version: '20261028002' });

      const catTabs = [
        { key: '', name: '全部' },
        { key: 'law', name: '法条' },
        { key: 'recruit', name: '报考' },
        { key: 'exam_point', name: '考点' },
        { key: 'wrong', name: '错题' },
      ];
      const statusTabs = [
        { key: 'approved', name: '已入库' },
        { key: 'pending', name: '待审批' },
        { key: 'graph', name: '图谱' },
      ];

      const state = reactive({
        category: '',
        status: 'approved',
        view: 'list',
        nodes: [],
        graph: { nodes: [], relations: [] },
        loading: false,
        submitting: false,
        importing: false,
        importMsg: '',
        notice: '',
        suggestions: [],
        suggesting: false,
        relList: [],
        form: { title: '', category: 'law', content: '' },
      });

      function fmtTime(t) {
        if (!t) return '';
        const d = new Date(t);
        const p = (x) => (x < 10 ? '0' + x : '' + x);
        return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
      }

      function goBack() {
        if (window.history.length > 1) window.history.back();
        else window.location.href = '/#/';
      }

      async function loadNodes() {
        state.loading = true;
        try {
          const q = new URLSearchParams({ status: state.status });
          if (state.category) q.set('category', state.category);
          const res = await window.__VTJ_AUTH__.apiFetch('/api/knowledge/nodes?' + q.toString());
          const d = await res.json();
          if (res.ok) state.nodes = d.items || [];
          else state.notice = d.detail || '加载失败';
        } catch (e) {
          state.notice = '网络异常，加载失败';
        } finally {
          state.loading = false;
        }
      }

      async function loadGraph() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/knowledge/graph');
          const d = await res.json();
          if (res.ok) state.graph = d;
          else state.notice = d.detail || '图谱加载失败';
        } catch (e) {
          state.notice = '网络异常，图谱加载失败';
        }
      }

      const graphNodes = computed(() => state.graph.nodes || []);
      const graphRels = computed(() => state.graph.relations || []);

      function nodePos(id) {
        const ns = graphNodes.value;
        const idx = Math.max(0, ns.findIndex((n) => n.node_id === id));
        const total = Math.max(ns.length, 1);
        // 环形布局：4列概念改为圆周均分，避免重叠
        const angle = (2 * Math.PI * idx) / total - Math.PI / 2;
        const cx = 320, cy = 160, R = Math.min(270, 60 + total * 22);
        return { x: Math.round(cx + R * Math.cos(angle)), y: Math.round(cy + R * Math.sin(angle)) };
      }

      function catShort(c) {
        return { law: '法', recruit: '报', exam_point: '点', wrong: '错' }[c] || '知';
      }

      function shortTitle(t) {
        return t && t.length > 8 ? t.slice(0, 8) + '…' : (t || '');
      }

      function switchCat(key) {
        state.category = key;
        if (state.status !== 'graph') loadNodes();
      }

      function switchStatus(key) {
        state.status = key;
        state.view = key === 'graph' ? 'graph' : 'list';
        if (key === 'graph') loadGraph();
        else loadNodes();
      }

      async function importVault() {
        state.importing = true;
        state.importMsg = '';
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/knowledge/vault/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
          });
          const d = await res.json();
          if (res.ok) {
            state.importMsg = d.message;
            if (d.imported > 0 && state.status !== 'pending') state.status = 'pending';
            loadNodes();
          } else {
            state.importMsg = d.detail || '导入失败';
          }
        } catch (e) {
          state.importMsg = '网络异常，导入失败';
        } finally {
          state.importing = false;
        }
      }

      // ==================== 图谱关系管理（自动推荐 + 手动确认/删除） ====================
      async function loadRelations() {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/knowledge/relations');
          const d = await res.json();
          if (res.ok) state.relList = d.items || [];
        } catch (e) { /* 静默 */ }
      }

      async function suggestRelations() {
        state.suggesting = true;
        state.notice = '';
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/knowledge/relation/suggest', { method: 'POST' });
          const d = await res.json();
          if (res.ok) {
            state.suggestions = d.items || [];
            state.notice = state.suggestions.length ? `发现 ${state.suggestions.length} 条候选关系，点“添加”确认` : '暂无可推荐的关系';
          } else {
            state.notice = d.detail || '推荐失败';
          }
        } catch (e) {
          state.notice = '网络异常，推荐失败';
        } finally {
          state.suggesting = false;
        }
      }

      async function addRelation(s) {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/knowledge/relation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ from_node: s.from, to_node: s.to, rel_type: s.type || 'related' }),
          });
          const d = await res.json();
          state.notice = d.message || '添加失败';
          state.suggestions = state.suggestions.filter((x) => !(x.from === s.from && x.to === s.to));
          loadGraph();
          loadRelations();
        } catch (e) {
          state.notice = '网络异常，添加失败';
        }
      }

      async function delRelation(r) {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/knowledge/relation/' + r.rel_id, { method: 'DELETE' });
          const d = await res.json();
          state.notice = d.message || '删除失败';
          loadGraph();
          loadRelations();
        } catch (e) {
          state.notice = '网络异常，删除失败';
        }
      }

      async function submitNode() {
        const title = state.form.title.trim();
        const content = state.form.content.trim();
        if (title.length < 2 || content.length < 5) {
          state.notice = '标题至少2字、内容至少5字';
          return;
        }
        state.submitting = true;
        state.notice = '';
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/knowledge/nodes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, category: state.form.category, content }),
          });
          const d = await res.json();
          if (res.ok) {
            state.notice = d.message + '（可切到“待审批”查看）';
            state.form.title = '';
            state.form.content = '';
            if (state.status === 'pending') loadNodes();
          } else {
            state.notice = d.detail || '提交失败';
          }
        } catch (e) {
          state.notice = '网络异常，提交失败';
        } finally {
          state.submitting = false;
        }
      }

      async function approveNode(n) {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/knowledge/nodes/' + n.node_id + '/approve', {
            method: 'POST',
          });
          const d = await res.json();
          state.notice = res.ok ? `「${n.title}」${d.message}` : (d.detail || '审批失败');
          if (res.ok) loadNodes();
        } catch (e) {
          state.notice = '网络异常，审批失败';
        }
      }

      async function rejectNode(n) {
        try {
          const res = await window.__VTJ_AUTH__.apiFetch('/api/knowledge/nodes/' + n.node_id + '/reject', {
            method: 'POST',
          });
          const d = await res.json();
          state.notice = res.ok ? `「${n.title}」已驳回` : (d.detail || '驳回失败');
          if (res.ok) loadNodes();
        } catch (e) {
          state.notice = '网络异常，驳回失败';
        }
      }

      onMounted(() => {
        loadNodes();
        loadRelations();
      });

      return {
        state, catTabs, statusTabs,
        graphNodes, graphRels,
        nodePos, catShort, shortTitle,
        goBack, switchCat, switchStatus,
        submitNode, approveNode, rejectNode, importVault,
        loadRelations, suggestRelations, addRelation, delRelation,
        fmtTime,
      };
    },
  });
</script>

<style lang="css" scoped>
  .kb-page { min-height: 100vh; background: #f3f5f9; }
  .kb-top { padding: 14px 16px 10px; background: #1a2a4a; color: #fff; position: sticky; top: 0; z-index: 10; }
  .kb-back { position: absolute; left: 12px; top: 18px; width: 30px; height: 30px; border-radius: 50%; border: none; background: rgba(255,255,255,.12); color: #fff; font-size: 20px; line-height: 1; cursor: pointer; }
  .kb-title { font-size: 17px; font-weight: 600; padding-left: 38px; }
  .kb-sub { font-size: 11px; color: #b8c4dd; margin-top: 3px; padding-left: 38px; }
  .kb-body { padding: 10px 12px 24px; }
  .kb-tabs { display: flex; gap: 8px; flex-wrap: wrap; }
  .kb-tab { padding: 5px 14px; border-radius: 14px; background: #fff; color: #334; font-size: 13px; cursor: pointer; border: 1px solid #e2e6ef; }
  .kb-tab.active { background: #1a2a4a; color: #fff; border-color: #1a2a4a; }
  .kb-status { display: flex; gap: 14px; margin: 10px 2px 12px; }
  .kb-st { font-size: 13px; color: #889; cursor: pointer; padding: 3px 2px; border-bottom: 2px solid transparent; }
  .kb-st.active { color: #1a2a4a; font-weight: 600; border-bottom-color: #d33; }
  .kb-submit { background: #fff; border-radius: 10px; padding: 10px 12px; margin-bottom: 12px; border: 1px solid #e2e6ef; }
  .kb-submit-head { font-size: 13px; font-weight: 600; color: #1a2a4a; margin-bottom: 8px; }
  .kb-form { display: flex; flex-direction: column; gap: 8px; }
  .kb-input { border: 1px solid #dbe0ea; border-radius: 8px; padding: 8px 10px; font-size: 13px; font-family: inherit; }
  .kb-sel { background: #fff; }
  .kb-area { resize: vertical; }
  .kb-btn { border: none; border-radius: 8px; padding: 9px 0; font-size: 13px; cursor: pointer; background: #d33; color: #fff; }
  .kb-btn:disabled { opacity: .5; cursor: default; }
  .kb-btn.mini { padding: 3px 10px; font-size: 12px; border-radius: 11px; }
  .kb-btn.ok { background: #1a2a4a; }
  .kb-btn.no { background: #fff; color: #999; border: 1px solid #dbe0ea; }
  .kb-graph { background: #fff; border-radius: 10px; padding: 12px; border: 1px solid #e2e6ef; }
  .kb-svg { width: 100%; height: auto; }
  .kb-node-title { pointer-events: none; }
  .kb-list { display: flex; flex-direction: column; gap: 10px; }
  .kb-card { background: #fff; border-radius: 10px; padding: 10px 12px; border: 1px solid #e2e6ef; }
  .kb-card.pending { border-color: #e8b35c; }
  .kb-card-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .kb-card-title { font-size: 14px; font-weight: 600; color: #1a2a4a; }
  .kb-card-tag { font-size: 11px; padding: 2px 8px; border-radius: 9px; background: #eef1f7; color: #556; }
  .kb-card-tag.law { background: #e8f0fb; color: #2a6bb8; }
  .kb-card-tag.recruit { background: #eaf7ee; color: #2e8b57; }
  .kb-card-tag.exam_point { background: #fdf3e3; color: #c98a2b; }
  .kb-card-tag.wrong { background: #fbeaea; color: #c0392b; }
  .kb-card-st { font-size: 11px; padding: 2px 8px; border-radius: 9px; }
  .kb-card-st.approved { background: #eaf7ee; color: #2e8b57; }
  .kb-card-st.pending { background: #fdf3e3; color: #c98a2b; }
  .kb-card-body { font-size: 12px; color: #445; margin: 8px 0; line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
  .kb-card-foot { display: flex; align-items: center; gap: 10px; font-size: 11px; color: #99a; flex-wrap: wrap; }
  .kb-card-ops { margin-left: auto; display: flex; gap: 8px; }
  .kb-empty { text-align: center; color: #99a; font-size: 13px; padding: 28px 0; background: #fff; border-radius: 10px; border: 1px dashed #dbe0ea; }
  .kb-notice { margin-top: 10px; padding: 8px 12px; border-radius: 8px; background: #fdf3e3; color: #7a5a10; font-size: 12px; }
  .kb-rel-panel { margin-top: 12px; border-top: 1px dashed #dbe0ea; padding-top: 10px; }
  .kb-rel-head { display: flex; align-items: center; justify-content: space-between; font-size: 13px; font-weight: 600; color: #1a2a4a; }
  .kb-rel-sugs, .kb-rel-list { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
  .kb-rel-sug, .kb-rel-item { display: flex; align-items: center; justify-content: space-between; gap: 8px; background: #f7f9fc; border-radius: 8px; padding: 6px 10px; font-size: 12px; color: #445; }
  .kb-rel-line { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .kb-rel-type { font-style: normal; color: #8aa0c8; margin-left: 6px; font-size: 11px; }
  .kb-rel-empty { color: #99a; font-size: 12px; padding: 10px 0 2px; }
</style>
