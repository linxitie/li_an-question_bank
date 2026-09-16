<!-- 帮助中心（桌面端） -->
<template>
  <div class="help-page">
    <NavBar />
    <main class="help-main">
      <header class="help-header">
        <h2><XIcon :icon="QuestionFilled" :size="26" color="#1A365D" /> 帮助中心</h2>
        <button class="btn-feedback" @click="$router.push('/feedback')">我要反馈</button>
      </header>

      <div v-for="cat in faq" :key="cat.category" class="faq-section">
        <h3 class="faq-cat">{{ cat.category }}</h3>
        <div v-for="(item, idx) in cat.items" :key="idx" class="faq-item">
          <div class="faq-q">{{ idx + 1 }}. {{ item.q }}</div>
          <div class="faq-a">{{ item.a }}</div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { XIcon } from '@vtj/ui';
import { QuestionFilled } from '@vtj/icons';
import NavBar from '$vtj/vue/navbar.vue';

const auth: any = (window as any).__VTJ_AUTH__;
const faq = ref<any[]>([]);

onMounted(async () => {
  try {
    const res = await auth.apiFetch('/api/feedback/faq');
    const data = await res.json();
    faq.value = data.items || [];
  } catch (e) {
    console.error('加载帮助中心失败', e);
  }
});
</script>

<style scoped>
.help-page {
  min-height: 100vh;
  background: linear-gradient(180deg, #f8f9fc 0%, #f1f3f8 100%);
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
.help-main { max-width: 900px; margin: 0 auto; padding: 24px 32px 40px; }
.help-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.help-header h2 { display: flex; align-items: center; gap: 10px; font-size: 22px; font-weight: 800; color: #1a2b5f; margin: 0; }
.btn-feedback { padding: 9px 20px; background: linear-gradient(135deg, #c41e3a, #d42945); color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; }

.faq-section { margin-bottom: 24px; }
.faq-cat { font-size: 16px; font-weight: 700; color: #1a2b5f; margin: 0 0 12px; }
.faq-item { background: #fff; border-radius: 12px; padding: 16px 20px; margin-bottom: 10px; box-shadow: 0 2px 10px rgba(26, 43, 95, 0.04); }
.faq-q { font-size: 14px; font-weight: 700; color: #1a2b5f; margin-bottom: 8px; }
.faq-a { font-size: 13px; color: #5a6488; line-height: 1.7; }
</style>
