<!-- 导航栏其他模块 -->
<template>
  <header class="navbar-container">
    <div class="navbar-inner">
      <div class="navbar-brand" @click="navigateTo('home_page')">
        <div class="brand-icon">
          <span class="icon-shield"> 🛡️</span>
        </div>
        <span class="brand-title"> 警大砺安</span>
      </div>
      <nav class="navbar-menu">
        <a
          v-for="(item, index) in menuItems"
          :key="item.id"
          :class="['menu-item', { active: state.activeMenu === item.id }]"
          @click="handleMenuClick(item.id)">
          <span class="menu-text"> {{ item.label }}</span></a
        >
      </nav>
      <div class="navbar-actions">
        <button class="btn-download" @click="navigateTo('download_client')">
          <XIcon :icon="Download" :size="16" color="#ffffff"></XIcon>
          <span> 下载客户端</span>
        </button>
        <div class="user-avatar" @click="handleUserClick">
          <div :class="['avatar-circle', { 'avatar-logged-in': state.loggedIn }]">
            <XIcon :icon="UserFilled" :size="20" color="#ffffff"></XIcon>
          </div>
          <span class="login-text">{{ state.loggedIn ? state.username : '登录' }}</span>
          <XIcon :icon="CaretBottom" :size="12" color="#ffffff"></XIcon>
        </div>
      </div>
    </div>
    <div class="navbar-glow"></div>
  </header>

  <!-- 个人信息面板 -->
  <div class="profile-overlay" v-if="state.showProfile" @click.self="state.showProfile = false">
    <div class="profile-panel">
      <h3>个人中心</h3>
      <div class="pf-row"><label>用户名</label><span>{{ state.profile.username }}</span></div>
      <div class="pf-row"><label>手机号</label><input v-model="state.profile.phone" placeholder="请输入手机号"/></div>
      <div class="pf-row"><label>性别</label>
        <select v-model="state.profile.gender"><option>男</option><option>女</option><option>未知</option></select>
      </div>
      <div class="pf-row"><label>学院/部门</label><input v-model="state.profile.department" placeholder="请输入学院"/></div>
      <div class="pf-row"><label>班级</label><input v-model="state.profile.class_name" placeholder="请输入班级"/></div>
      <div class="pf-row"><label>邮箱</label><input v-model="state.profile.email" placeholder="请输入邮箱"/></div>
      <div class="pf-actions">
        <button class="pf-btn-save" @click="saveProfile">保存</button>
        <button class="pf-btn-cancel" @click="state.showProfile = false">取消</button>
        <button class="pf-btn-logout" @click="handleLogout">退出登录</button>
      </div>
    </div>
  </div>
</template>
<script lang="ts">
  // @ts-nocheck
  import { defineComponent, reactive } from 'vue';
  import { XIcon } from '@vtj/ui';
  import { Download, UserFilled, CaretBottom } from '@vtj/icons';
  import { useProvider } from '@vtj/renderer';
  export default defineComponent({
    name: 'NavBar',
    components: { XIcon },
    setup(props) {
      const provider = useProvider({ id: 'navbar', version: '1778917634433' });
      const state = reactive({
        activeMenu: 'home_page',
        loggedIn: false,
        username: '',
        showProfile: false,
        profile: { username: '', phone: '', gender: '未知', department: '', class_name: '', email: '', school: '' }
      });
      return { state, props, provider, Download, UserFilled, CaretBottom };
    },
    computed: {
      menuItems() {
        return [
          { id: 'home_page', label: '首页' },
          { id: 'question_bank', label: '题库' },
          { id: 'about', label: '关于砺安题库' },
          { id: 'forum', label: '论坛' }
        ];
      }
    },
    mounted() {
      this.updateLoginState();
    },
    methods: {
      navigateTo(id) {
        if (this.$router) {
          this.$router.push('/page/' + id);
        }
      },
      handleMenuClick(id) {
        this.state.activeMenu = id;
        this.navigateTo(id);
      },
      handleUserClick() {
        if (this.state.loggedIn) {
          // 已登录 → 显示个人信息面板
          this.state.showProfile = true;
          this.loadProfile();
        } else if (this.$router) {
          this.$router.push('/login');
        }
      },
      async loadProfile() {
        const auth = window.__VTJ_AUTH__;
        if (!auth) return;
        try {
          const res = await auth.apiFetch('/api/auth/profile');
          const data = await res.json();
          if (data.user_id) {
            this.state.profile = {
              username: data.username || '',
              phone: data.phone || '',
              gender: data.gender || '未知',
              department: data.department || '',
              class_name: data.class_name || '',
              email: data.email || '',
              school: data.school || '',
            };
          }
        } catch(e) { console.error('加载个人信息失败:', e); }
      },
      async saveProfile() {
        const auth = window.__VTJ_AUTH__;
        if (!auth) return;
        try {
          const res = await auth.apiFetch('/api/auth/profile', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(this.state.profile)
          });
          const data = await res.json();
          if (data.success) {
            if (this.$message) this.$message.success('个人信息已保存');
            this.state.showProfile = false;
          }
        } catch(e) { console.error('保存失败:', e); }
      },
      handleLogout() {
        window.__VTJ_AUTH__ && window.__VTJ_AUTH__.logout();
        this.state.loggedIn = false;
        this.state.username = '';
        this.state.showProfile = false;
        if (this.$message) this.$message.success('已退出登录');
        if (this.$router) this.$router.push('/login');
      },
      updateLoginState() {
        if (window.__VTJ_AUTH__) {
          this.state.loggedIn = window.__VTJ_AUTH__.isLoggedIn();
          if (this.state.loggedIn) {
            this.state.username = window.__VTJ_AUTH__.getUsername() || '用户';
          }
        }
      }
    }
  })
</script>
<style lang="css" scoped>
  .navbar-container {
    position: sticky;
    top: 0;
    z-index: 1000;
    width: 100%;
    height: 64px;
    background: linear-gradient(135deg, #1a2b5f 0%, #1e3470 40%, #1a2b5f 100%);
    box-shadow: 0 2px 20px rgba(26, 43, 95, 0.35);
    font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }
  .navbar-inner {
    max-width: 1400px;
    margin: 0 auto;
    height: 100%;
    display: flex;
    align-items: center;
    padding: 0 32px;
    gap: 24px;
  }
  .navbar-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    padding: 4px 12px 4px 4px;
    border-radius: 30px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    user-select: none;
  }
  .navbar-brand:hover {
    background: rgba(255, 255, 255, 0.08);
    transform: scale(1.02);
  }
  .brand-icon {
    width: 40px;
    height: 40px;
    background: linear-gradient(135deg, #c41e3a, #e8384f);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 4px 12px rgba(196, 30, 58, 0.4);
  }
  .icon-shield {
    font-size: 22px;
  }
  .brand-title {
    font-size: 20px;
    font-weight: 900;
    color: #ffffff;
    letter-spacing: 3px;
    text-shadow: 0 2px 8px rgba(255, 255, 255, 0.2);
  }
  .navbar-menu {
    display: flex;
    align-items: center;
    gap: 4px;
    flex: 1;
    justify-content: center;
  }
  .menu-item {
    position: relative;
    padding: 8px 18px;
    font-size: 15px;
    font-weight: 600;
    color: rgba(255, 255, 255, 0.75);
    cursor: pointer;
    border-radius: 8px;
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    text-decoration: none;
    letter-spacing: 1px;
    user-select: none;
  }
  .menu-item:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.06);
  }
  .menu-item.active {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.1);
    text-shadow: 0 0 12px rgba(255, 255, 255, 0.3);
  }
  .menu-item::after {
    content: '';
    position: absolute;
    bottom: 2px;
    left: 50%;
    transform: translateX(-50%) scaleX(0);
    width: 60%;
    height: 2px;
    background: linear-gradient(90deg, #c41e3a, #ff4d5a);
    border-radius: 1px;
    transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .menu-item.active::after {
    transform: translateX(-50%) scaleX(1);
  }
  .navbar-actions {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  .btn-download {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
    color: #ffffff;
    background: linear-gradient(135deg, #c41e3a, #d42945);
    border: none;
    border-radius: 20px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    letter-spacing: 1px;
    box-shadow: 0 2px 10px rgba(196, 30, 58, 0.3);
  }
  .btn-download:hover {
    background: linear-gradient(135deg, #d42945, #e8384f);
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(196, 30, 58, 0.45);
  }
  .btn-download:active {
    transform: scale(0.96);
  }
  .user-avatar {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px 6px 6px;
    border-radius: 24px;
    cursor: pointer;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    background: rgba(255, 255, 255, 0.06);
    user-select: none;
  }
  .user-avatar:hover {
    background: rgba(255, 255, 255, 0.14);
    transform: scale(1.03);
  }
  .avatar-circle {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: linear-gradient(135deg, #c41e3a, #e8384f);
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 8px rgba(196, 30, 58, 0.4);
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  }
  .avatar-circle.avatar-logged-in {
    background: linear-gradient(135deg, #0F3460, #1a4a8a);
    box-shadow: 0 2px 10px rgba(15, 52, 96, 0.5);
  }
  .login-text {
    font-size: 13px;
    color: #ffffff;
    font-weight: 500;
  }
  .navbar-glow {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(
      90deg,
      transparent 0%,
      #c41e3a 30%,
      #ff4d5a 50%,
      #c41e3a 70%,
      transparent 100%
    );
    opacity: 0.6;
  }
  /* ===== 响应式 ===== */
  @media (max-width: 860px) {
    .navbar-inner {
      padding: 0 16px;
      gap: 12px;
    }
    .navbar-menu {
      gap: 2px;
    }
    .menu-item {
      padding: 6px 10px;
      font-size: 13px;
    }
    .brand-title {
      font-size: 16px;
      letter-spacing: 1px;
    }
    .btn-download {
      padding: 6px 10px;
      font-size: 12px;
    }
    .user-avatar {
      padding: 4px 8px 4px 4px;
    }
    .login-text {
      display: none;
    }
  }
  @media (max-width: 600px) {
    .navbar-inner {
      padding: 0 10px;
      gap: 6px;
    }
    .navbar-menu {
      display: none;
    }
    .brand-title {
      font-size: 14px;
    }
    .btn-download span {
      display: none;
    }
    .btn-download {
      padding: 6px 8px;
    }
    .avatar-circle {
      width: 28px;
      height: 28px;
    }
  }
  /* 个人信息面板 */
  .profile-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.4); display:flex; align-items:center; justify-content:center; z-index:2000; }
  .profile-panel { background:#fff; border-radius:14px; padding:28px; width:420px; max-width:90vw; box-shadow:0 8px 32px rgba(0,0,0,0.15); }
  .profile-panel h3 { color:#1A3C6D; margin:0 0 20px; font-size:18px; }
  .pf-row { display:flex; align-items:center; margin-bottom:14px; }
  .pf-row label { width:80px; font-weight:600; color:#555; font-size:14px; }
  .pf-row span { flex:1; padding:8px 12px; background:#F5F7FA; border-radius:6px; font-size:15px; color:#333; }
  .pf-row input, .pf-row select { flex:1; padding:8px 12px; border:1px solid #d9d9d9; border-radius:6px; font-size:15px; }
  .pf-actions { display:flex; gap:10px; margin-top:20px; justify-content:flex-end; }
  .pf-btn-save { padding:8px 20px; background:#1A3C6D; color:#fff; border:none; border-radius:6px; cursor:pointer; font-size:14px; }
  .pf-btn-cancel { padding:8px 20px; background:#f0f0f0; color:#666; border:none; border-radius:6px; cursor:pointer; font-size:14px; }
  .pf-btn-logout { padding:8px 20px; background:transparent; color:#C41E3A; border:1px solid #C41E3A; border-radius:6px; cursor:pointer; font-size:14px; margin-left:auto; }
  .pf-btn-logout:hover { background:#C41E3A; color:#fff; }
</style>
