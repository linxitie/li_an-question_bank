<template>
  <div class="mobile-app">
    <header class="app-header">
      <button class="back-btn" @click="goBack">←</button>
      <div class="title">砺安题库</div>
      <div class="placeholder"></div>
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
import { useRouter } from 'vue-router'

const router = useRouter()

const goBack = () => {
  router.back()
}
</script>

<style scoped>
.mobile-app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #F5F7FA;
}

.app-header {
  height: 48px;
  background: white;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  border-bottom: 1px solid #E5E7EB;
}

.back-btn {
  background: none;
  border: none;
  font-size: 20px;
  color: #1F2937;
}

.title {
  font-size: 16px;
  font-weight: 600;
}

.placeholder {
  width: 24px;
}

.app-main {
  flex: 1;
  overflow-y: auto;
}

.app-nav {
  height: 52px;
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
  font-size: 18px;
}

.nav-text {
  font-size: 12px;
  margin-top: 2px;
}
</style>
