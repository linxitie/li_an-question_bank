<!-- 手机端我的成就（独立移动端壳层：含返回键，不复用电脑端 NavBar） -->
<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">我的成就</h1>
      <span class="spacer"></span>
    </header>

    <div class="summary">
      <span class="summary-icon">🏆</span>
      <span class="summary-text">已获得 {{ data.earned_count }} / {{ data.total }}</span>
    </div>

    <main class="list">
      <template v-for="(items, category) in data.categories" :key="category">
        <h3 class="cat-title">{{ categoryLabel(category) }}</h3>
        <div
          v-for="a in items"
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
              <div
                class="ach-progress-fill"
                :style="{ width: Math.min(100, (a.current / a.threshold) * 100) + '%' }"
              ></div>
            </div>
            <div class="ach-reward">🪙 {{ a.reward_coins }}</div>
          </div>
        </div>
      </template>

      <div v-if="loading" class="empty">加载中...</div>
      <div v-else-if="!hasAny" class="empty">暂无成就数据</div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { reactive, computed, ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const auth: any = (window as any).__VTJ_AUTH__;
const data = reactive<any>({ total: 0, earned_count: 0, categories: {} });
const loading = ref(false);

const CATEGORY_LABEL: Record<string, string> = {
  '坚持': '🔥 学习坚持',
  '数量': '📝 做题数量',
  '正确率': '🎯 正确率',
  '错题': '❌ 错题管理',
  '社交': '💬 社交互动',
  '综合': '🏆 综合成就',
  '联考特色': '🎖️ 联考特色',
  '隐藏': '🔒 隐藏成就',
  '赛季限定': '🏅 赛季限定',
};
const TIER_COLORS: Record<number, string> = {
  1: '#b87333', 2: '#c0c0c0', 3: '#ffd700', 4: '#e5e4e2', 5: '#b9f2ff',
};
const TIER_LABELS: Record<number, string> = {
  1: '铜', 2: '银', 3: '金', 4: '铂金', 5: '钻石',
};

const hasAny = computed(() => Object.keys(data.categories || {}).length > 0);

const categoryLabel = (cat: any) => CATEGORY_LABEL[cat] || cat;
const tierColor = (tier: number) => TIER_COLORS[tier] || '#b87333';
const tierLabel = (tier: number) => TIER_LABELS[tier] || '铜';
const isHidden = (a: any) => (a.is_hidden === 1) && !a.earned;

// 统一返回机制：有历史则回退，无历史则回「我的」，避免退到空白页
const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/profile');
};

onMounted(async () => {
  loading.value = true;
  try {
    const res = await auth.apiFetch('/api/achievements');
    if (res.ok) {
      const d = await res.json();
      data.total = d.total || 0;
      data.earned_count = d.earned_count || 0;
      data.categories = d.categories || {};
    }
  } catch (e) {
    console.error('加载成就失败', e);
  } finally {
    loading.value = false;
  }
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
