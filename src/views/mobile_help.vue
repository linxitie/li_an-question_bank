<!-- 手机端帮助中心（独立移动端壳层：含返回键，不复用电脑端 NavBar） -->
<template>
  <div class="page">
    <header class="topbar">
      <button class="back-btn" @click="goBack" aria-label="返回">←</button>
      <h1 class="title">帮助中心</h1>
      <span class="spacer"></span>
    </header>

    <main class="list">
      <div class="feedback-entry" @click="goFeedback">
        <span class="feedback-text">💬 我要反馈</span>
        <span class="feedback-arrow">›</span>
      </div>

      <template v-for="cat in faq" :key="cat.category">
        <h3 class="cat-title">{{ cat.category }}</h3>
        <div
          v-for="(item, idx) in cat.items"
          :key="idx"
          :class="['faq-item', { open: openKey === cat.category + '-' + idx }]"
          @click="toggle(cat.category, idx)"
        >
          <div class="faq-q">
            <span class="faq-no">{{ idx + 1 }}.</span>{{ item.q }}
            <span class="faq-mark">{{ openKey === cat.category + '-' + idx ? '−' : '+' }}</span>
          </div>
          <div v-if="openKey === cat.category + '-' + idx" class="faq-a">{{ item.a }}</div>
        </div>
      </template>

      <div v-if="loading" class="empty">加载中...</div>
      <div v-else-if="!faq.length" class="empty">暂无帮助内容</div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const auth: any = (window as any).__VTJ_AUTH__;
interface FaqItem { q: string; a: string; }
interface FaqCategory { category: string; items: FaqItem[]; }
const faq = ref<FaqCategory[]>([]);
const loading = ref(false);
// 移动端单条展开（桌面端全部平铺，手机上全部展开会过长）
const openKey = ref('');

// 统一返回机制：有历史则回退，无历史则回「我的」，避免退到空白页
const goBack = () => {
  if (window.history.length > 1) router.back();
  else router.push('/mobile/profile');
};

const goFeedback = () => router.push('/mobile/feedback');

const toggle = (category: string, idx: number) => {
  const key = category + '-' + idx;
  openKey.value = openKey.value === key ? '' : key;
};

onMounted(async () => {
  loading.value = true;
  try {
    const res = await auth.apiFetch('/api/feedback/faq');
    const data = await res.json();
    faq.value = data.items || [];
  } catch (e) {
    console.error('加载帮助中心失败', e);
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
  min-width: 44px;
  min-height: 44px;
  padding: 4px 8px;
}
.title { font-size: 16px; font-weight: 600; color: #1a2b5f; margin: 0; }
.spacer { width: 32px; }

.list { flex: 1; padding: 12px 12px 24px; }

.feedback-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 12px;
  min-height: 44px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
}
.feedback-text { font-size: 14px; font-weight: 600; color: #1a2b5f; }
.feedback-arrow { font-size: 20px; color: #8899aa; }

.cat-title { font-size: 15px; font-weight: 700; color: #1a2b5f; margin: 16px 0 10px; }

.faq-item {
  background: #fff;
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 10px;
  box-shadow: 0 2px 8px rgba(26, 54, 95, 0.04);
  cursor: pointer;
}
.faq-q {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #1a2b5f;
  line-height: 1.5;
}
.faq-no { flex-shrink: 0; }
.faq-mark { margin-left: auto; color: #8899aa; font-weight: 400; flex-shrink: 0; }
.faq-a {
  font-size: 13px;
  color: #5a6488;
  line-height: 1.7;
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #f0f2f5;
}

.empty { text-align: center; color: #8899aa; padding: 40px 0; }
</style>
