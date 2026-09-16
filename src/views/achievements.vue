<!-- 我的成就页（桌面端） -->
<template>
  <div class="achievements-page">
    <NavBar />
    <main class="ach-main">
      <header class="ach-header">
        <h2><XIcon :icon="Trophy" :size="26" color="#f59e0b" /> 我的成就</h2>
        <span class="ach-progress">已获得 {{ data.earned_count }} / {{ data.total }}</span>
      </header>

      <div v-for="(items, category) in data.categories" :key="category" class="cat-section">
        <h3 class="cat-title">{{ categoryLabel(category) }}</h3>
        <div class="ach-grid">
          <div
            v-for="a in items"
            :key="a.achievement_id"
            :class="['ach-card', { earned: a.earned }]"
          >
            <div class="ach-icon">{{ a.icon }}</div>
            <div class="ach-body">
              <div class="ach-name">{{ a.name }}</div>
              <div class="ach-desc">{{ a.condition_desc }}</div>
              <div class="ach-progress-bar" v-if="!a.earned && a.threshold > 0">
                <div class="ach-progress-fill" :style="{ width: Math.min(100, (a.current / a.threshold) * 100) + '%' }"></div>
              </div>
              <div class="ach-reward">🪙 {{ a.reward_coins }}</div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue';
import { XIcon } from '@vtj/ui';
import { Trophy } from '@vtj/icons';
import NavBar from '$vtj/vue/navbar.vue';

const auth: any = (window as any).__VTJ_AUTH__;
const data = reactive<any>({ total: 0, earned_count: 0, categories: {} });

const CATEGORY_LABEL: Record<string, string> = {
  '坚持': '🔥 学习坚持',
  '数量': '📝 做题数量',
  '正确率': '🎯 正确率',
  '错题': '❌ 错题管理',
  '社交': '💬 社交互动',
  '综合': '🏆 综合成就',
};

function categoryLabel(cat: any) {
  return CATEGORY_LABEL[cat] || cat;
}

onMounted(async () => {
  try {
    const res = await auth.apiFetch('/api/achievements');
    const d = await res.json();
    data.total = d.total || 0;
    data.earned_count = d.earned_count || 0;
    data.categories = d.categories || {};
  } catch (e) {
    console.error('加载成就失败', e);
  }
});
</script>

<style scoped>
.achievements-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
.ach-main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 32px 40px;
}
.ach-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.ach-header h2 {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 22px;
  font-weight: 800;
  color: #1a2b5f;
  margin: 0;
}
.ach-progress { font-size: 14px; color: #8a8faa; }

.cat-section { margin-bottom: 28px; }
.cat-title { font-size: 16px; font-weight: 700; color: #1a2b5f; margin: 0 0 14px; }
.ach-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.ach-card {
  display: flex;
  gap: 14px;
  padding: 16px;
  background: #ffffff;
  border-radius: 14px;
  box-shadow: 0 2px 12px rgba(26, 43, 95, 0.04);
  opacity: 0.85;
  transition: all 0.2s;
}
.ach-card.earned { opacity: 1; border: 1px solid rgba(245, 158, 11, 0.4); }
.ach-icon { width: 48px; height: 48px; font-size: 26px; display: flex; align-items: center; justify-content: center; background: #f8f9fc; border-radius: 12px; flex-shrink: 0; }
.ach-body { flex: 1; min-width: 0; }
.ach-name { font-size: 15px; font-weight: 700; color: #1a2b5f; }
.ach-desc { font-size: 12px; color: #8a8faa; margin: 4px 0 8px; }
.ach-progress-bar { height: 5px; background: #f0f2f5; border-radius: 3px; overflow: hidden; margin-bottom: 6px; }
.ach-progress-fill { height: 100%; background: linear-gradient(90deg, #f59e0b, #d97706); border-radius: 3px; }
.ach-reward { font-size: 12px; color: #b45309; font-weight: 600; }
</style>
