<template>
  <div class="admin-layout">
    <!-- 左侧导航 -->
    <aside class="admin-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <span v-if="!sidebarCollapsed" class="logo-text">砺安题库</span>
        <span class="logo-sub">管理端</span>
      </div>
      <nav class="sidebar-nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="sidebar-item"
          :class="{ active: currentPath.startsWith(item.path) }"
        >
          <span class="sidebar-icon">{{ item.icon }}</span>
          <span v-if="!sidebarCollapsed" class="sidebar-label">{{ item.label }}</span>
        </router-link>
      </nav>
      <div class="sidebar-footer">
        <button class="collapse-btn" @click="sidebarCollapsed = !sidebarCollapsed">
          {{ sidebarCollapsed ? '▶' : '◀' }}
        </button>
      </div>
    </aside>

    <!-- 右侧内容 -->
    <div class="admin-right">
      <header class="admin-header">
        <span class="breadcrumb">{{ pageTitle }}</span>
        <div class="header-actions">
          <span class="user-name">{{ username }}</span>
          <button class="logout-btn" @click="handleLogout">退出</button>
        </div>
      </header>
      <main class="admin-main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';

export default defineComponent({
  name: 'AdminLayout',
  setup() {
    const router = useRouter();
    const route = useRoute();
    const username = ref('');
    const sidebarCollapsed = ref(false);

    const navItems = [
      { label: '系统总览', path: '/admin/dashboard', icon: '📊' },
      { label: '用户管理', path: '/admin/users', icon: '👥' },
      { label: '题库管理', path: '/admin/questions', icon: '📋' },
      { label: '系统设置', path: '/admin/settings', icon: '⚙️' },
      { label: '日志审计', path: '/admin/logs', icon: '📝' },
      { label: '数据备份', path: '/admin/backup', icon: '💾' },
      { label: '权限管理', path: '/admin/permissions', icon: '🔐' },
    ];

    const currentPath = computed(() => route.path);

    const pageTitle = computed(() => {
      const item = navItems.find(n => route.path.startsWith(n.path));
      return item ? item.label : '管理端';
    });

    onMounted(() => {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) {
        username.value = auth.getUsername() || '管理员';
      }
    });

    function handleLogout() {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) auth.logout();
      router.push('/login');
    }

    return { navItems, currentPath, pageTitle, username, sidebarCollapsed, handleLogout };
  }
});
</script>

<style scoped>
.admin-layout {
  display: flex;
  min-height: 100vh;
  background: #F5F7FA;
}

/* 侧边栏 */
.admin-sidebar {
  width: 220px;
  background: #1A3C6D;
  color: #fff;
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
  z-index: 100;
}

.admin-sidebar.collapsed {
  width: 64px;
}

.sidebar-header {
  padding: 20px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  text-align: center;
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 1px;
}

.logo-sub {
  font-size: 12px;
  color: rgba(255,255,255,0.6);
  display: block;
  margin-top: 2px;
}

.sidebar-nav {
  flex: 1;
  padding: 12px 0;
}

.sidebar-item {
  display: flex;
  align-items: center;
  padding: 12px 20px;
  color: rgba(255,255,255,0.7);
  text-decoration: none;
  font-size: 15px;
  transition: all 0.2s;
  border-left: 3px solid transparent;
}

.sidebar-item:hover {
  color: #fff;
  background: rgba(255,255,255,0.08);
}

.sidebar-item.active {
  color: #fff;
  background: rgba(255,255,255,0.12);
  border-left-color: #C41E3A;
  font-weight: 600;
}

.sidebar-icon {
  font-size: 18px;
  margin-right: 12px;
  width: 24px;
  text-align: center;
}

.sidebar-label {
  white-space: nowrap;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid rgba(255,255,255,0.1);
}

.collapse-btn {
  width: 100%;
  padding: 8px;
  border: none;
  background: rgba(255,255,255,0.1);
  color: #fff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

/* 右侧区域 */
.admin-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}

.breadcrumb {
  font-size: 16px;
  font-weight: 600;
  color: #1A3C6D;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-name {
  font-size: 14px;
  color: #666;
}

.logout-btn {
  padding: 6px 16px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #fff;
  color: #606266;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  color: #C41E3A;
  border-color: #C41E3A;
}

.admin-main {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
}
</style>
