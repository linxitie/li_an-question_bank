<template>
  <div class="teacher-layout">
    <!-- 顶部导航 -->
    <header class="teacher-header">
      <div class="header-left">
        <span class="logo-text">砺安题库 · 教师端</span>
      </div>
      <nav class="header-nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: currentPath.startsWith(item.path) }"
        >
          {{ item.label }}
        </router-link>
      </nav>
      <div class="header-right">
        <span class="user-name">{{ username }}</span>
        <button class="logout-btn" @click="handleLogout">退出</button>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="teacher-main">
      <router-view />
    </main>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';

export default defineComponent({
  name: 'TeacherLayout',
  setup() {
    const router = useRouter();
    const route = useRoute();
    const username = ref('');

    const navItems = [
      { label: '工作台', path: '/teacher/dashboard' },
      { label: '题目管理', path: '/teacher/questions' },
      { label: '试卷管理', path: '/teacher/papers' },
      { label: '成绩管理', path: '/teacher/scores' },
    ];

    const currentPath = computed(() => route.path);

    onMounted(() => {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) {
        username.value = auth.getUsername() || '教师';
      }
    });

    function handleLogout() {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) auth.logout();
      router.push('/login');
    }

    return { navItems, currentPath, username, handleLogout };
  }
});
</script>

<style scoped>
.teacher-layout {
  min-height: 100vh;
  background: #F5F7FA;
  display: flex;
  flex-direction: column;
}

.teacher-header {
  display: flex;
  align-items: center;
  height: 56px;
  padding: 0 24px;
  background: #1A3C6D;
  color: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left {
  margin-right: 40px;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 1px;
}

.header-nav {
  display: flex;
  gap: 4px;
  flex: 1;
}

.nav-item {
  padding: 8px 20px;
  color: rgba(255,255,255,0.75);
  text-decoration: none;
  font-size: 15px;
  border-radius: 6px;
  transition: all 0.2s;
}

.nav-item:hover {
  color: #fff;
  background: rgba(255,255,255,0.12);
}

.nav-item.active {
  color: #fff;
  background: rgba(255,255,255,0.2);
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-name {
  font-size: 14px;
  color: rgba(255,255,255,0.85);
}

.logout-btn {
  padding: 6px 16px;
  border: 1px solid rgba(255,255,255,0.5);
  border-radius: 4px;
  background: transparent;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  background: #C41E3A;
  border-color: #C41E3A;
}

.teacher-main {
  flex: 1;
  padding: 24px;
  max-width: 1400px;
  width: 100%;
  margin: 0 auto;
}
</style>
