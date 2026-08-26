<!-- 备考资料入口：三科目卡片（重构自静态tabs，spec v2.2 §7.2） -->
<template>
  <div class="materials-entry">
    <div class="panel-header">
      <div class="header-left">
        <XIcon :icon="ReadingLamp" :size="22" color="#c8161e"></XIcon>
        <span class="header-title"> 备考资料</span>
      </div>
      <span class="header-desc"> 精选干货，助你上岸</span>
    </div>
    <div class="subject-grid">
      <div
        v-for="s in state.subjects"
        :key="s.key"
        class="subject-card"
        :style="{ '--c': s.color }"
        @click="goSubject(s.key)">
        <div class="s-top">
          <div class="s-icon"><span>{{ s.emoji }}</span></div>
          <div class="s-body">
            <span class="s-name">{{ s.name }}</span>
            <span class="s-desc">{{ s.desc }}</span>
          </div>
        </div>
        <span class="s-count">资料 {{ state.counts[s.key] }} 项</span>
        <div class="s-progress">
          <div class="bar"><i :style="{ width: (state.progress[s.key] || 0) + '%' }"></i></div>
          <span class="pct">{{ state.progress[s.key] }}%</span>
        </div>
        <button class="s-btn">进入学习 →</button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
// @ts-nocheck
import { defineComponent, reactive } from 'vue';
import { XIcon } from '@vtj/ui';
import { ReadingLamp } from '@vtj/icons';
import { useProvider } from '@vtj/renderer';

export default defineComponent({
  name: 'StudyMaterials',
  components: { XIcon },
  setup(props) {
    const provider = useProvider({ id: 'study_materials', version: '1778915843581' });
    const state = reactive({
      subjects: [
        { key: 'xingce', name: '行测备考', desc: '解题规律与速算技巧', color: '#3B82F6', emoji: '📘' },
        { key: 'shenlun', name: '申论备考', desc: '写作技巧与热点素材', color: '#10B981', emoji: '📗' },
        { key: 'gongzhuan', name: '公专备考', desc: '职业素养与警务技能', color: '#F59E0B', emoji: '📕' }
      ],
      counts: { xingce: 0, shenlun: 0, gongzhuan: 0 },
      progress: { xingce: null, shenlun: null, gongzhuan: null },
      loggedIn: false
    });
    return { state, props, provider, ReadingLamp };
  },
  methods: {
    async fetchCounts() {
      for (const s of this.state.subjects) {
        try {
          const resp = await window.__VTJ_AUTH__.apiFetch(
            `/api/materials?subject=${s.key}&page_size=1`);
          const data = await resp.json();
          if (data && typeof data.total === 'number') {
            this.state.counts[s.key] = data.total;
          }
        } catch (e) {
          console.warn('[StudyMaterials] count failed:', e && e.message);
        }
      }
    },
    async fetchProgress() {
      try {
        const auth = window.__VTJ_AUTH__ || {};
        this.state.loggedIn = !!(auth.isLoggedIn && auth.isLoggedIn());
      } catch (e) {
        this.state.loggedIn = false;
      }
      if (!this.state.loggedIn) return;
      for (const s of this.state.subjects) {
        try {
          const resp = await window.__VTJ_AUTH__.apiFetch(
            `/api/materials/progress-summary?subject=${s.key}`);
          if (resp.ok) {
            const d = await resp.json();
            this.state.progress[s.key] = Math.round(d.percentage || 0);
          }
        } catch (e) {
          console.warn('[StudyMaterials] progress failed:', e && e.message);
        }
      }
    },
    goSubject(key) {
      this.$router.push(`/materials/${key}`);
    }
  },
  mounted() {
    this.fetchCounts();
    this.fetchProgress();
  }
})
</script>

<style lang="css" scoped>
.materials-entry {
  background: #ffffff;
  border-radius: 16px;
  padding: 24px;
  border: 1px solid #e8ecf1;
  box-shadow: 0 4px 20px rgba(10, 22, 40, 0.06);
}
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  padding-bottom: 14px;
  border-bottom: 2px solid #f0f2f5;
}
.header-left { display: flex; align-items: center; gap: 10px; }
.header-title {
  font-size: 19px;
  font-weight: 700;
  background: linear-gradient(135deg, #1a2a4a 0%, #2c3e50 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.header-desc { font-size: 12px; color: #8899aa; font-weight: 500; }
.subject-grid { display: flex; gap: 16px; flex-wrap: wrap; }
.subject-card {
  --c: #3b82f6;
  flex: 1;
  min-width: 220px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px;
  border-radius: 12px;
  border: 1px solid #eef1f6;
  background: linear-gradient(180deg, #fbfcfe 0%, #ffffff 100%);
  cursor: pointer;
  transition: all 0.3s ease;
}
.subject-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 10px 24px rgba(10, 22, 40, 0.1);
  border-color: var(--c);
}
.s-top { display: flex; align-items: center; gap: 12px; }
.s-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  background: rgba(200, 22, 30, 0.05);
}
.s-body { display: flex; flex-direction: column; }
.s-name { font-size: 16px; font-weight: 700; color: #1a2a4a; }
.s-desc { font-size: 12px; color: #8899aa; margin-top: 2px; }
.s-count { font-size: 11px; color: var(--c); font-weight: 600; }
.s-progress { display: flex; align-items: center; gap: 8px; }
.bar { flex: 1; height: 6px; border-radius: 3px; background: #eef1f6; overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--c); border-radius: 3px; transition: width 0.6s; }
.pct { font-size: 11px; font-weight: 700; color: var(--c); min-width: 32px; text-align: right; }
.s-btn {
  align-self: flex-end;
  border: none;
  background: none;
  color: var(--c);
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  padding: 4px 0;
  opacity: 0.85;
}
@media (max-width: 768px) {
  .subject-grid { flex-direction: column; }
}
</style>
