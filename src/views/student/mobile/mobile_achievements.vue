<!-- 手机端我的成就（独立移动端壳层，P2-55 接入 growth store） -->
<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">我的成就</h1>
      <span class="spacer"></span>
    </header>

    <div class="summary">
      <span class="summary-icon">🏆</span>
      <span class="summary-text">已获得 {{ store.earnedCount }} / {{ store.total }}</span>
    </div>

    <main class="list">
      <div v-if="store.error" class="error">{{ store.error }}</div>

      <template v-for="group in store.achievementGroups" :key="group.category">
        <h3 class="cat-title">{{ group.label }}</h3>
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
            <div
              class="ach-progress-bar"
              v-if="!a.earned && a.threshold > 0 && !isHidden(a)"
            >
              <div class="ach-progress-fill" :style="{ width: a.progressPercent + '%' }"></div>
            </div>
            <div class="ach-reward">🪙 {{ a.reward_coins }}</div>
          </div>
        </div>
      </template>

      <div v-if="store.loading" class="empty">加载中...</div>
      <div v-else-if="!hasAny" class="empty">暂无成就数据</div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useGrowthStore, tierColor, tierLabel } from '@/modules/growth/store';
import { subscribeGrowthEvents } from '@/modules/growth/events';

const router = useRouter();
const store = useGrowthStore();
let unsubscribe: (() => void) | null = null;

const hasAny = computed(() => store.achievementGroups.length > 0);

const isHidden = (a: { is_hidden?: number; earned?: boolean }) =>
  a.is_hidden === 1 && !a.earned;

const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/profile');
};

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
.page {
  min-height: 100vh;
  background: #F5F7FA;
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  display: flex;
  flex-direction: column;
}
.topbar {
  height: 48px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 12px;
  border-bottom: 1px solid #e8ecf1;
  position: sticky;
  top: 0;
  z-index: 10;
}
.back-btn {
  background: none;
  border: none;
  font-size: 22px;
  color: #1a2b5f;
  cursor: pointer;
  /* 触控区不小于 44px（design-tokens --touch-target-min） */
  min-width: 44px;
  min-height: 44px;
  padding: 4px 8px;
}
.title { font-size: 16px; font-weight: 600; color: #1a2b5f; margin: 0; }
.spacer { width: 32px; }

.summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px 0;
}
.summary-icon { font-size: 22px; }
.summary-text { font-size: 14px; color: #5a6488; }

.list { flex: 1; padding: 12px 12px 24px; }
.cat-title { font-size: 15px; font-weight: 700; color: #1a2b5f; margin: 16px 0 10px; }
.error { color: #dc2626; font-size: 13px; padding: 8px 4px; }

.ach-card {
  position: relative;
  display: flex;
  gap: 12px;
  background: #fff;
  border: 1px solid #eef1f5;
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 10px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
}
.ach-card.locked { opacity: 0.72; }
.ach-icon {
  width: 46px;
  height: 46px;
  flex-shrink: 0;
  border-radius: 12px;
  background: #f0f3f7;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}
.ach-earned-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  font-size: 10px;
  color: #fff;
  border-radius: 10px;
  padding: 2px 8px;
}
.ach-body { flex: 1; min-width: 0; padding-right: 40px; }
.ach-name { font-size: 14px; font-weight: 700; color: #1a2b5f; }
.ach-desc { font-size: 12px; color: #5a6488; line-height: 1.6; margin-top: 4px; }
.ach-progress-bar {
  height: 6px;
  background: #e8ecf1;
  border-radius: 3px;
  margin-top: 8px;
  overflow: hidden;
}
.ach-progress-fill { height: 100%; background: #1A365D; border-radius: 3px; }
.ach-reward { font-size: 12px; color: #f59e0b; margin-top: 6px; }

.empty { text-align: center; color: #8899aa; padding: 40px 0; }
</style>
