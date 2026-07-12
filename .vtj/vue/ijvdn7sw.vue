<template>
  <header class="navbar-container">
    <div class="navbar-inner">
      <div class="navbar-brand" @click="navigateTo('jjvdntly')">
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
        <button class="btn-download" @click="navigateTo('pjvds138')">
          <XIcon :icon="Download" :size="16" color="#ffffff"></XIcon>
          <span> 下载客户端</span>
        </button>
        <div class="user-avatar" @click="handleUserClick">
          <div class="avatar-circle">
            <XIcon :icon="UserFilled" :size="20" color="#ffffff"></XIcon>
          </div>
          <span class="login-text"> 登录</span>
          <XIcon :icon="CaretBottom" :size="12" color="#ffffff"></XIcon>
        </div>
      </div>
    </div>
    <div class="navbar-glow"></div>
  </header>
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
      const provider = useProvider({ id: 'ijvdn7sw', version: '1778917634433' });
      const state = reactive({ activeMenu: 'jjvdntly' });
      return { state, props, provider, Download, UserFilled, CaretBottom };
    },
    computed: {
      menuItems() {
        return [
          { id: 'jjvdntly', label: '首页' },
          { id: 'mjvdqdu1', label: '题库' },
          { id: 'njvdr28b', label: '关于砺安题库' },
          { id: 'ojvdrg4v', label: '论坛' }
        ];
      }
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
        if (this.$message) {
          this.$message.info('登录功能开发中，敬请期待');
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
</style>
