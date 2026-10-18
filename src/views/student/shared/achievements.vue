<!-- 我的成就页（三端响应式，P2-55 接入 growth store） -->
<template>
  <div class="achievements-page">
    <NavBar />
    <main class="ach-main">
      <header class="ach-header">
        <h2><XIcon :icon="Trophy" :size="26" color="#f59e0b" /> 我的成就</h2>
        <span class="ach-progress">已获得 {{ store.earnedCount }} / {{ store.total }}</span>
      </header>

      <div v-if="store.error" class="ach-error">{{ store.error }}</div>

      <div v-for="group in store.achievementGroups" :key="group.category" class="cat-section">
        <h3 class="cat-title">{{ group.label }}</h3>
        <div class="ach-grid">
          <div
            v-for="a in group.items"
            :key="a.achievement_id"
            :class="['ach-card', { earned: a.earned, locked: !a.earned }]"
            :style="a.earned ? { borderColor: tierColor(a.tier) } : {}"
          >
            <div class="ach-icon" :style="a.earned ? { background: tierColor(a.tier) + '22' } : {}">
              {{ isHidden(a) ? '❓' : a.icon }}
            </div>
            <div v-if="a.earned" class="ach-earned-badge" :style="{ background: tierColor(a.tier) }">
              ✓ {{ tierLabel(a.tier) }}
            </div>
            <div class="ach-body">
              <div class="ach-name">{{ isHidden(a) ? '神秘成就' : a.name }}</div>
              <div class="ach-desc">{{ isHidden(a) ? '继续探索解锁' : a.condition_desc }}</div>
              <div class="ach-progress-bar" v-if="!a.earned && a.threshold > 0 && !isHidden(a)">
                <div class="ach-progress-fill" :style="{ width: a.progressPercent + '%' }"></div>
              </div>
              <div class="ach-reward">🪙 {{ a.reward_coins }}</div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="store.loading" class="ach-empty">加载中...</div>
      <div v-else-if="store.initialized && !store.achievementGroups.length" class="ach-empty">
        暂无成就数据
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue';
import { XIcon } from '@vtj/ui';
import { Trophy } from '@vtj/icons';
import NavBar from '$vtj/vue/navbar.vue';
import { useGrowthStore, tierColor, tierLabel } from '@/modules/growth/store';
import { subscribeGrowthEvents } from '@/modules/growth/events';

const store = useGrowthStore();
let unsubscribe: (() => void) | null = null;

function isHidden(a: { is_hidden?: number; earned?: boolean }) {
  return a.is_hidden === 1 && !a.earned;
}

onMounted(async () => {
  await store.load();
  unsubscribe = subscribeGrowthEvents(() => {
    void store.refreshAchievements();
  });
});

onUnmounted(() => {
  unsubscribe?.();
  unsubscribe = null;
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
.ach-error { margin-bottom: 16px; color: #dc2626; font-size: 13px; }
.ach-empty { padding: 24px; text-align: center; color: #8a8faa; font-size: 14px; }

.cat-section { margin-bottom: 28px; }
.cat-title { font-size: 16px; font-weight: 700; color: #1a2b5f; margin: 0 0 14px; }
.ach-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
.ach-card {
  position: relative;
  display: flex;
  gap: 14px;
  padding: 16px;
  background: #ffffff;
  border-radius: 14px;
  box-shadow: 0 2px 12px rgba(26, 43, 95, 0.04);
  border: 1px solid transparent;
  transition: all 0.2s;
}
.ach-card.locked { opacity: 0.7; }
.ach-card.locked .ach-icon { filter: grayscale(1); }
.ach-earned-badge {
  position: absolute;
  top: -8px;
  right: -6px;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 10px;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
}
.ach-icon { width: 48px; height: 48px; font-size: 26px; display: flex; align-items: center; justify-content: center; background: #f8f9fc; border-radius: 12px; flex-shrink: 0; }
.ach-body { flex: 1; min-width: 0; }
.ach-name { font-size: 15px; font-weight: 700; color: #1a2b5f; }
.ach-desc { font-size: 12px; color: #8a8faa; margin: 4px 0 8px; }
.ach-progress-bar { height: 5px; background: #f0f2f5; border-radius: 3px; overflow: hidden; margin-bottom: 6px; }
.ach-progress-fill { height: 100%; background: linear-gradient(90deg, #f59e0b, #d97706); border-radius: 3px; }
.ach-reward { font-size: 12px; color: #b45309; font-weight: 600; }

@media (max-width: 1024px) {
  .ach-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 768px) {
  .ach-main { padding: 16px; }
  .ach-grid { grid-template-columns: repeat(2, 1fr); gap: 10px; }
  .ach-card { flex-direction: column; align-items: center; text-align: center; gap: 8px; padding: 14px 8px; }
  .ach-icon { width: 44px; height: 44px; font-size: 22px; }
  .ach-name { font-size: 13px; }
  .ach-desc { font-size: 11px; }
}
</style>
