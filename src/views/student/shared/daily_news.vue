<template>
  <div class="daily-news-page">
    <DailyNewsPanel />
  </div>
</template>

<script setup lang="ts">
import DailyNewsPanel from '@/components/news/DailyNewsPanel.vue';
</script>

<style scoped>
.daily-news-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px 18px 48px;
  box-sizing: border-box;
  min-height: 100vh;
  background: #fbfaf7;
}
</style>
