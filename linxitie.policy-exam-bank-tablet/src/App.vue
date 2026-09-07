<template>
  <div class="tablet-app">
    <header class="app-header">
      <div class="logo">砺安题库</div>
      <div class="user-info">{{ user?.real_name }}</div>
    </header>
    
    <main class="app-main">
      <router-view />
    </main>
    
    <nav class="app-nav">
      <router-link to="/home" class="nav-item">
        <span class="nav-icon">🏠</span>
        <span class="nav-text">首页</span>
      </router-link>
      <router-link to="/questions" class="nav-item">
        <span class="nav-icon">📚</span>
        <span class="nav-text">题库</span>
      </router-link>
      <router-link to="/practice" class="nav-item">
        <span class="nav-icon">✏️</span>
        <span class="nav-text">练习</span>
      </router-link>
      <router-link to="/forum" class="nav-item">
        <span class="nav-icon">💬</span>
        <span class="nav-text">论坛</span>
      </router-link>
      <router-link to="/profile" class="nav-item">
        <span class="nav-icon">👤</span>
        <span class="nav-text">我的</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '@linxi/shared-store'

const authStore = useAuthStore()
const user = computed(() => authStore.currentUser)
</script>

<style scoped>
.tablet-app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #F0F2F5;
}

.app-header {
  height: 60px;
  background: #1A365D;
  color: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
}

.app-main {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.app-nav {
  height: 56px;
  background: white;
  display: flex;
  border-top: 1px solid #E5E7EB;
}

.nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  color: #6B7280;
}

.nav-item.active {
  color: #1A365D;
}

.nav-icon {
  font-size: 20px;
}

.nav-text {
  font-size: 13px;
  margin-top: 4px;
}
</style>
