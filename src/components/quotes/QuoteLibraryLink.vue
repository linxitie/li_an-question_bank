<template>
  <router-link class="quote-library-link" to="/quotes">
    金句库 <span aria-hidden="true">→</span>
  </router-link>
</template>

<script setup lang="ts"></script>

<style scoped>
.quote-library-link {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  flex: 0 0 auto;
  padding: 4px 9px;
  border: 1px solid #e3ded4;
  border-radius: 999px;
  background: #fff;
  color: #2f5d50;
  font-size: 12px;
  text-decoration: none;
  white-space: nowrap;
}

.quote-library-link:hover {
  border-color: #2f5d50;
  background: #f5f8f6;
}
</style>
