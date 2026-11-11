<template>
  <router-link class="radar-entry" to="/recruitment/radar">
    <span class="radar-entry__dot"></span>
    <span>进入警考雷达</span>
    <span class="radar-entry__arrow" aria-hidden="true">→</span>
  </router-link>
</template>

<script setup lang="ts"></script>

<style scoped>
.radar-entry {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 8px 14px;
  border: 1px solid rgba(200, 22, 30, 0.22);
  border-radius: 999px;
  background: #fff;
  color: #c8161e;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.2s ease;
}

.radar-entry:hover {
  border-color: #c8161e;
  background: #fff7f7;
  box-shadow: 0 5px 14px rgba(200, 22, 30, 0.12);
}

.radar-entry__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #c8161e;
}

.radar-entry__arrow {
  font-size: 15px;
  line-height: 1;
}
</style>
