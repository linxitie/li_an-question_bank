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
          <div class="notification-bell" @click.stop="showNotifications = !showNotifications">
            <span class="bell-icon">🔔</span>
            <span v-if="unreadCount > 0" class="badge">{{ unreadCount }}</span>
            <div v-if="showNotifications" class="notification-dropdown">
              <div class="notification-header">消息中心</div>
              <div v-for="n in notifications" :key="n.id" class="notification-item" :class="{ unread: !n.read }" @click="notificationService.markAsRead(n.id)">
                <span class="notification-type">{{ {system:'系统',approval:'审批',security:'安全',message:'消息'}[n.type] }}</span>
                <span class="notification-title">{{ n.title }}</span>
                <span class="notification-time">{{ n.time }}</span>
              </div>
              <div v-if="!notifications.length" class="notification-empty">暂无消息</div>
            </div>
          </div>
          <div class="user-menu" @click.stop="showUserMenu = !showUserMenu">
            <img v-if="avatarUrl" :src="avatarUrl" class="avatar-img" :alt="username" />
            <div v-else class="avatar-circle">{{ username?.charAt(0) || 'A' }}</div>
            <span class="user-name">{{ username }}</span>
            <span class="menu-arrow">▼</span>
            <div v-if="showUserMenu" class="user-dropdown">
              <a class="dropdown-item" @click="$router.push('/admin/profile')">📋 个人信息</a>
              <a class="dropdown-item" @click="showPasswordDialog = true">🔑 修改密码</a>
              <a class="dropdown-item" @click="$router.push('/admin/settings')">⚙️ 系统设置</a>
              <a class="dropdown-item" @click="$router.push('/admin/logs')">📝 我的操作日志</a>
              <a class="dropdown-item" href="https://help.example.com" target="_blank">📖 帮助文档</a>
              <div class="dropdown-divider"></div>
              <a class="dropdown-item logout-item" @click="confirmLogout">🚪 退出登录</a>
            </div>
          </div>
        </div>
      </header>
      <main class="admin-main">
        <router-view />
      </main>
    </div>

    <!-- 修改密码弹窗 -->
    <div class="modal-overlay" v-if="showPasswordDialog" @click.self="showPasswordDialog = false">
      <div class="modal-content">
        <h3>修改密码</h3>
        <input type="password" v-model="oldPassword" placeholder="当前密码" />
        <input type="password" v-model="newPassword" placeholder="新密码" />
        <input type="password" v-model="confirmPassword" placeholder="确认密码" />
        <div class="modal-actions">
          <button @click="showPasswordDialog = false">取消</button>
          <button @click="changePassword">确认</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted, onUnmounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { notificationService, type Notification } from '@/services/NotificationService';

export default defineComponent({
  name: 'AdminLayout',
  setup() {
    const router = useRouter();
    const route = useRoute();
    const username = ref('');
    const sidebarCollapsed = ref(false);
    const showUserMenu = ref(false);
    const showNotifications = ref(false);
    const showPasswordDialog = ref(false);
    const notifications = ref<Notification[]>([]);
    const unreadCount = ref(0);
    const newPassword = ref('');
    const confirmPassword = ref('');
    const oldPassword = ref('');
    const avatarUrl = ref('');

    const navItems = [
      { label: '系统总览', path: '/admin/dashboard', icon: '📊' },
      { label: '用户管理', path: '/admin/users', icon: '👥' },
      { label: '题库管理', path: '/admin/questions', icon: '📋' },
      { label: '资料管理', path: '/admin/materials', icon: '📚' },
      { label: '试卷审批', path: '/admin/papers', icon: '📝' },
      { label: '论坛管理', path: '/admin/forum', icon: '💬' },
      { label: '系统设置', path: '/admin/settings', icon: '⚙️' },
      { label: '日志审计', path: '/admin/logs', icon: '📋' },
      { label: '数据备份', path: '/admin/backup', icon: '💾' },
      { label: '权限管理', path: '/admin/permissions', icon: '🔐' },
      { label: '帮助文档', path: '/admin/help', icon: '📖' },
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
      loadAvatar();
      // 监听头像更新事件：个人信息/用户管理页更换头像后刷新下拉框头像
      window.addEventListener('avatar-updated', loadAvatar);
      notificationService.startPolling();
      notificationService.subscribe((notifs: Notification[]) => {
        notifications.value = notifs;
        unreadCount.value = notificationService.getUnreadCount();
      });
    });

    onUnmounted(() => {
      window.removeEventListener('avatar-updated', loadAvatar);
      notificationService.stopPolling();
    });

    // 加载当前用户头像
    async function loadAvatar() {
      try {
        const auth = (window as any).__VTJ_AUTH__;
        if (!auth) return;
        const r = await auth.apiFetch('/api/auth/profile');
        const d = await r.json();
        if (d && d.avatar) {
          avatarUrl.value = d.avatar;
        }
      } catch (e) {
        // 头像加载失败不阻断页面
      }
    }

    function handleLogout() {
      const auth = (window as any).__VTJ_AUTH__;
      if (auth) auth.logout();
      router.push('/login');
    }

    function confirmLogout() {
      if (confirm('确定要退出登录吗？')) {
        handleLogout();
      }
    }

    async function changePassword() {
      if (!oldPassword.value) {
        alert('请输入当前密码');
        return;
      }
      if (newPassword.value !== confirmPassword.value) {
        alert('两次密码不一致');
        return;
      }
      if (!newPassword.value || newPassword.value.length < 6) {
        alert('新密码至少6位');
        return;
      }
      try {
        const auth = (window as any).__VTJ_AUTH__;
        const r = await auth.apiFetch('/api/auth/change-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ old_password: oldPassword.value, new_password: newPassword.value })
        });
        const d = await r.json();
        if (d.success) {
          alert('密码修改成功');
          showPasswordDialog.value = false;
          oldPassword.value = '';
          newPassword.value = '';
          confirmPassword.value = '';
        } else {
          alert(d.message || '密码修改失败');
        }
      } catch (e) {
        alert('密码修改失败');
      }
    }

    return {
      navItems,
      currentPath,
      pageTitle,
      username,
      sidebarCollapsed,
      handleLogout,
      showUserMenu,
      showNotifications,
      showPasswordDialog,
      notifications,
      unreadCount,
      newPassword,
      confirmPassword,
      oldPassword,
      avatarUrl,
      confirmLogout,
      changePassword,
      notificationService
    };
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

/* 用户菜单 */
.user-menu { position: relative; cursor: pointer; display: flex; align-items: center; gap: 8px; }
.avatar-circle { width: 32px; height: 32px; border-radius: 50%; background: #C41E3A; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; }
.avatar-img { width: 32px; height: 32px; border-radius: 50%; object-fit: cover; }
.menu-arrow { font-size: 10px; color: #999; }
.user-dropdown { position: absolute; top: 100%; right: 0; background: #fff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,.15); min-width: 180px; z-index: 1000; padding: 8px 0; }
.dropdown-item { display: block; padding: 10px 16px; color: #333; text-decoration: none; cursor: pointer; font-size: 14px; }
.dropdown-item:hover { background: #f5f7fa; }
.logout-item { color: #C41E3A; }
.dropdown-divider { height: 1px; background: #e8e8e8; margin: 4px 0; }

/* 通知铃铛 */
.notification-bell { position: relative; cursor: pointer; padding: 8px; }
.bell-icon { font-size: 18px; }
.badge { position: absolute; top: 2px; right: 2px; background: #C41E3A; color: #fff; font-size: 10px; padding: 2px 6px; border-radius: 10px; }
.notification-dropdown { position: absolute; top: 100%; right: 0; background: #fff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,.15); width: 300px; z-index: 1000; }
.notification-header { padding: 12px 16px; font-weight: 600; border-bottom: 1px solid #e8e8e8; }
.notification-item { padding: 10px 16px; cursor: pointer; border-bottom: 1px solid #f5f5f5; display: flex; align-items: center; gap: 8px; }
.notification-item:hover { background: #f5f7fa; }
.notification-item.unread { background: #f0f9eb; }
.notification-type { font-size: 12px; padding: 2px 6px; border-radius: 4px; background: #e8e8e8; }
.notification-title { flex: 1; font-size: 13px; }
.notification-time { font-size: 12px; color: #999; }
.notification-empty { padding: 20px; text-align: center; color: #999; }

/* 密码弹窗 */
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,.5); display: flex; align-items: center; justify-content: center; z-index: 2000; }
.modal-content { background: #fff; border-radius: 12px; padding: 24px; width: 400px; }
.modal-content h3 { margin: 0 0 16px; color: #1A3C6D; }
.modal-content input { width: 100%; padding: 10px; border: 1px solid #d9d9d9; border-radius: 6px; margin-bottom: 12px; font-size: 14px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; }
.modal-actions button { padding: 8px 16px; border-radius: 6px; border: 1px solid #d9d9d9; cursor: pointer; }
.modal-actions button:last-child { background: #1A3C6D; color: #fff; border-color: #1A3C6D; }
</style>
